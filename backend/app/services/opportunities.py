from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, load_only, selectinload

from app.connectors.base import ConnectorNotice
from app.core.config import get_settings
from app.models import (
    Agent,
    AgentRun,
    AgentRunStatus,
    AiReport,
    DocumentChunk,
    Keyword,
    KeywordMatch,
    Notification,
    NotificationType,
    Opportunity,
    OpportunityDocument,
    OpportunityScore,
    OpportunityStatus,
    RawNotice,
    Source,
)
from app.services.documents import chunk_text, extract_text_from_bytes
from app.services.agent_usage import ORCHESTRATION_AGENT_SLUGS
from app.services.market_intelligence import collect_market_intelligence
from app.services.normalization import content_hash, normalize_manual_notice
from app.services.opportunity_map import build_map_points
from app.services.reports import build_heuristic_report, build_report, report_to_html
from app.services.scoring import KeywordConfig, prequalification_result, score_opportunity
from app.services.storage import save_local_file, sha256_bytes


DOCUMENT_LINK_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".txt", ".rtf")
MAX_DOCUMENT_CONTEXT_CHARS = 12000

DASHBOARD_OPPORTUNITY_COLUMNS = (
    Opportunity.id,
    Opportunity.source,
    Opportunity.source_url,
    Opportunity.source_reference,
    Opportunity.title,
    Opportunity.buyer,
    Opportunity.object,
    Opportunity.description,
    Opportunity.location,
    Opportunity.publication_date,
    Opportunity.deadline,
    Opportunity.status,
    Opportunity.global_score,
    Opportunity.ai_summary,
    Opportunity.created_at,
    Opportunity.updated_at,
)

MAP_OPPORTUNITY_COLUMNS = (
    Opportunity.id,
    Opportunity.source_reference,
    Opportunity.title,
    Opportunity.buyer,
    Opportunity.location,
    Opportunity.deadline,
    Opportunity.status,
    Opportunity.global_score,
    Opportunity.created_at,
)


def opportunity_to_payload(opportunity: Opportunity) -> dict[str, Any]:
    return {
        "source": opportunity.source,
        "source_url": opportunity.source_url,
        "source_reference": opportunity.source_reference,
        "title": opportunity.title,
        "buyer": opportunity.buyer,
        "buyer_type": opportunity.buyer_type,
        "object": opportunity.object,
        "description": opportunity.description,
        "lots": opportunity.lots,
        "cpv": opportunity.cpv,
        "procedure": opportunity.procedure,
        "market_type": opportunity.market_type,
        "location": opportunity.location,
        "publication_date": opportunity.publication_date,
        "deadline": opportunity.deadline,
        "estimated_budget": opportunity.estimated_budget,
    }


def _safe_filename(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in "-._" else "_" for char in value)
    return safe[:180] or "document"


def _document_context(db: Session, opportunity_id: int, max_chars: int = MAX_DOCUMENT_CONTEXT_CHARS) -> str:
    chunks = db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.opportunity_id == opportunity_id)
        .order_by(DocumentChunk.document_id.asc().nullsfirst(), DocumentChunk.chunk_index.asc())
        .limit(20)
    ).all()
    context: list[str] = []
    remaining = max_chars
    for chunk in chunks:
        if remaining <= 0:
            break
        text = (chunk.text or "").strip()
        if not text:
            continue
        context.append(text[:remaining])
        remaining -= len(context[-1])
    return "\n\n".join(context)


def _rejection_summary(score: Any, reason: str) -> str:
    if reason.startswith("score_insuffisant"):
        label = "score inférieur au seuil LIVE"
    elif reason.startswith("hors_enjeux_live"):
        label = "objet hors enjeux LIVE"
    else:
        label = "préqualification LIVE négative"
    details = [str(malus.get("details")) for malus in score.maluses if malus.get("details")]
    detail_text = f" {details[0]}" if details else ""
    return f"Écarté par IA: {label}. Score LIVE {score.global_score}/100.{detail_text}"


def _store_document_bytes(
    db: Session,
    opportunity: Opportunity,
    *,
    filename: str,
    content: bytes,
    content_type: str | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    digest = sha256_bytes(content)
    existing = db.scalar(
        select(OpportunityDocument).where(
            OpportunityDocument.opportunity_id == opportunity.id,
            OpportunityDocument.content_hash == digest,
        )
    )
    if existing:
        return {"created": False, "document_id": existing.id, "chunks_created": 0, "filename": existing.filename}

    path, digest = save_local_file(filename, content)
    try:
        extracted_text = extract_text_from_bytes(filename, content, content_type)
    except Exception as exc:
        extracted_text = ""
        metadata = {**metadata, "extraction_error": str(exc)}
    document = OpportunityDocument(
        opportunity_id=opportunity.id,
        filename=filename,
        content_type=content_type,
        storage_path=path,
        content_hash=digest,
        extracted_text=extracted_text,
        metadata_json=metadata,
    )
    db.add(document)
    db.flush()

    chunks_created = 0
    for index, chunk in enumerate(chunk_text(extracted_text)):
        db.add(
            DocumentChunk(
                opportunity_id=opportunity.id,
                document_id=document.id,
                chunk_index=index,
                text=chunk,
                metadata_json={"rag_ready": True, "filename": filename, "source": metadata.get("source")},
            )
        )
        chunks_created += 1
    db.flush()
    return {"created": True, "document_id": document.id, "chunks_created": chunks_created, "filename": filename}


def _platform_notice_payload(db: Session, opportunity: Opportunity) -> bytes:
    raw_notice = db.get(RawNotice, opportunity.raw_notice_id) if opportunity.raw_notice_id else None
    payload = {
        "source": opportunity.source,
        "source_reference": opportunity.source_reference,
        "source_url": opportunity.source_url,
        "normalized": opportunity_to_payload(opportunity),
        "raw_notice_payload": raw_notice.payload if raw_notice else None,
        "raw_notice_text": raw_notice.raw_text if raw_notice else None,
    }
    return json.dumps(payload, ensure_ascii=False, default=str, indent=2).encode("utf-8")


def _document_links_from_html(html: bytes, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        absolute = urljoin(base_url, href)
        suffix = Path(urlparse(absolute).path).suffix.casefold()
        if suffix not in DOCUMENT_LINK_EXTENSIONS or absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)
    return links


async def prepare_opportunity_rag(db: Session, opportunity: Opportunity, max_linked_documents: int = 4) -> dict[str, Any]:
    stats: dict[str, Any] = {"created_documents": 0, "existing_documents": 0, "chunks_created": 0, "errors": []}

    notice_result = _store_document_bytes(
        db,
        opportunity,
        filename=_safe_filename(f"{opportunity.source_reference or opportunity.id}-annonce-plateforme.json"),
        content=_platform_notice_payload(db, opportunity),
        content_type="application/json",
        metadata={"source": "platform_payload", "source_url": opportunity.source_url},
    )
    stats["created_documents" if notice_result["created"] else "existing_documents"] += 1
    stats["chunks_created"] += notice_result["chunks_created"]

    if opportunity.source_url:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.get(opportunity.source_url)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";")[0] or None
                page_filename = _safe_filename(f"{opportunity.source_reference or opportunity.id}-page-plateforme.html")
                page_result = _store_document_bytes(
                    db,
                    opportunity,
                    filename=page_filename,
                    content=response.content,
                    content_type=content_type,
                    metadata={"source": "platform_page", "source_url": opportunity.source_url},
                )
                stats["created_documents" if page_result["created"] else "existing_documents"] += 1
                stats["chunks_created"] += page_result["chunks_created"]

                if content_type and "html" in content_type:
                    for index, document_url in enumerate(_document_links_from_html(response.content, opportunity.source_url)[:max_linked_documents]):
                        try:
                            document_response = await client.get(document_url)
                            document_response.raise_for_status()
                            document_content_type = document_response.headers.get("content-type", "").split(";")[0] or None
                            filename = _safe_filename(Path(urlparse(document_url).path).name or f"piece-{index + 1}")
                            document_result = _store_document_bytes(
                                db,
                                opportunity,
                                filename=filename,
                                content=document_response.content,
                                content_type=document_content_type,
                                metadata={"source": "platform_document", "source_url": document_url},
                            )
                            stats["created_documents" if document_result["created"] else "existing_documents"] += 1
                            stats["chunks_created"] += document_result["chunks_created"]
                        except Exception as exc:  # pragma: no cover - external platform variability
                            stats["errors"].append({"url": document_url, "error": str(exc)})
        except Exception as exc:  # pragma: no cover - external platform variability
            stats["errors"].append({"url": opportunity.source_url, "error": str(exc)})
    embedding_stats = await _embed_missing_chunks(db, opportunity)
    stats["embedded_chunks"] = embedding_stats["embedded_chunks"]
    stats["embedding_input_tokens"] = embedding_stats.get("input_tokens", 0)
    stats["embedding_total_tokens"] = embedding_stats.get("total_tokens", 0)
    if embedding_stats.get("error"):
        stats["errors"].append({"step": "embedding", "error": embedding_stats["error"]})
    return stats


async def _embed_missing_chunks(db: Session, opportunity: Opportunity, max_chunks: int = 32) -> dict[str, Any]:
    settings = get_settings()
    if not settings.llm_enabled:
        return {"embedded_chunks": 0, "enabled": False}
    chunks = db.scalars(
        select(DocumentChunk)
        .where(
            DocumentChunk.opportunity_id == opportunity.id,
            DocumentChunk.embedding.is_(None),
        )
        .order_by(DocumentChunk.document_id.asc().nullsfirst(), DocumentChunk.chunk_index.asc())
        .limit(max_chunks)
    ).all()
    if not chunks:
        return {"embedded_chunks": 0, "enabled": True}
    try:
        from openai import AsyncOpenAI

        http_client = httpx.AsyncClient(verify=settings.openai_verify_ssl)
        client = AsyncOpenAI(api_key=settings.openai_api_key, http_client=http_client)
        try:
            response = await client.embeddings.create(
                model=settings.embedding_model,
                input=[chunk.text[:8000] for chunk in chunks],
            )
        finally:
            await http_client.aclose()
        for chunk, embedding in zip(chunks, response.data):
            chunk.embedding = embedding.embedding
            chunk.metadata_json = {**(chunk.metadata_json or {}), "embedding_model": settings.embedding_model, "rag_ready": True}
        db.flush()
        usage = getattr(response, "usage", None)
        input_tokens = int(
            getattr(usage, "input_tokens", None)
            or getattr(usage, "prompt_tokens", None)
            or 0
        )
        total_tokens = int(getattr(usage, "total_tokens", None) or input_tokens)
        return {"embedded_chunks": len(response.data), "enabled": True, "input_tokens": input_tokens, "total_tokens": total_tokens}
    except Exception as exc:  # pragma: no cover - provider/network fallback
        return {"embedded_chunks": 0, "enabled": True, "error": str(exc)}


def _usage_value(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        if usage.get(key) is not None:
            return int(usage.get(key) or 0)
    return 0


def _with_combined_usage(raw_model_json: dict[str, Any], rag_stats: dict[str, Any]) -> dict[str, Any]:
    raw_usage = dict(raw_model_json.get("usage") or {})
    report_input = _usage_value(raw_usage, "input_tokens", "prompt_tokens")
    report_output = _usage_value(raw_usage, "output_tokens", "completion_tokens")
    report_total = _usage_value(raw_usage, "total_tokens") or report_input + report_output
    embedding_total = int(rag_stats.get("embedding_total_tokens") or 0)
    embedding_input = int(rag_stats.get("embedding_input_tokens") or embedding_total)
    return {
        **raw_model_json,
        "rag": rag_stats,
        "report_usage": raw_usage,
        "embedding_usage": {
            "input_tokens": embedding_input,
            "output_tokens": 0,
            "total_tokens": embedding_total,
        },
        "usage": {
            "input_tokens": report_input + embedding_input,
            "output_tokens": report_output,
            "total_tokens": report_total + embedding_total,
        },
    }


def _status_after_analysis(current_status: OpportunityStatus, *, qualified: bool, score: float) -> OpportunityStatus:
    if not qualified:
        return OpportunityStatus.NOT_RELEVANT
    if score >= 65:
        return OpportunityStatus.RELEVANT
    if current_status in {OpportunityStatus.NEW, OpportunityStatus.NOT_RELEVANT, OpportunityStatus.RELEVANT}:
        return OpportunityStatus.ANALYZED
    return current_status


def load_keyword_configs(db: Session) -> list[KeywordConfig]:
    keywords = db.scalars(
        select(Keyword)
        .options(selectinload(Keyword.category), selectinload(Keyword.synonyms))
        .where(Keyword.is_active.is_(True))
    ).all()
    return [
        KeywordConfig(
            id=keyword.id,
            category=keyword.category.name,
            term=keyword.term,
            weight=keyword.weight,
            synonyms=[synonym.term for synonym in keyword.synonyms],
            exclusions=keyword.exclusions or [],
        )
        for keyword in keywords
        if keyword.category and keyword.category.is_active
    ]


def create_opportunity_from_normalized(
    db: Session,
    normalized: dict[str, Any],
    *,
    raw_notice: RawNotice | None = None,
    source_model: Source | None = None,
) -> tuple[Opportunity, bool]:
    source = normalized.get("source") or (source_model.name if source_model else "manual")
    source_reference = normalized.get("source_reference")
    query = select(Opportunity).where(Opportunity.source == source)
    if source_reference:
        existing = db.scalar(query.where(Opportunity.source_reference == source_reference))
        if existing:
            return existing, False

    opportunity = Opportunity(
        raw_notice_id=raw_notice.id if raw_notice else None,
        source_id=source_model.id if source_model else None,
        source=source,
        source_url=normalized.get("source_url"),
        source_reference=source_reference or content_hash(normalized)[:24],
        title=normalized.get("title") or "AO sans titre",
        buyer=normalized.get("buyer"),
        buyer_type=normalized.get("buyer_type"),
        object=normalized.get("object"),
        description=normalized.get("description"),
        lots=jsonable_encoder(normalized.get("lots") or []),
        cpv=jsonable_encoder(normalized.get("cpv") or []),
        procedure=normalized.get("procedure"),
        market_type=normalized.get("market_type"),
        location=normalized.get("location"),
        publication_date=normalized.get("publication_date"),
        deadline=normalized.get("deadline"),
        estimated_budget=normalized.get("estimated_budget"),
        normalized_payload=jsonable_encoder(normalized.get("normalized_payload") or normalized),
    )
    try:
        with db.begin_nested():
            db.add(opportunity)
            db.flush()
    except IntegrityError:
        # A scheduled and a manual run can discover the same notice concurrently.
        # The savepoint keeps the outer ingestion transaction usable after the race.
        existing = db.scalar(query.where(Opportunity.source_reference == opportunity.source_reference))
        if existing:
            return existing, False
        raise
    source_text = " ".join(
        str(part)
        for part in [opportunity.title, opportunity.object, opportunity.description, normalized.get("document_context")]
        if part
    )
    for index, text in enumerate(chunk_text(source_text)):
        db.add(DocumentChunk(opportunity_id=opportunity.id, chunk_index=index, text=text))
    db.flush()
    return opportunity, True


def create_opportunity_from_notice(db: Session, source: Source, notice: ConnectorNotice) -> tuple[Opportunity, bool]:
    digest = content_hash(notice.payload)
    raw_notice = db.scalar(
        select(RawNotice).where(
            RawNotice.source_id == source.id,
            RawNotice.source_reference == notice.source_reference,
        )
    )
    if not raw_notice:
        candidate = RawNotice(
            source_id=source.id,
            source_reference=notice.source_reference,
            source_url=notice.source_url,
            content_hash=digest,
            payload=notice.payload,
            raw_text=notice.raw_text,
        )
        try:
            with db.begin_nested():
                db.add(candidate)
                db.flush()
            raw_notice = candidate
        except IntegrityError:
            # Another source run won the insert race. Reuse its row without
            # poisoning the SQLAlchemy session for the remaining notices.
            raw_notice = db.scalar(
                select(RawNotice).where(
                    RawNotice.source_id == source.id,
                    RawNotice.source_reference == notice.source_reference,
                )
            )
            if not raw_notice:
                raise
    elif raw_notice.content_hash != digest:
        raw_notice.source_url = notice.source_url
        raw_notice.content_hash = digest
        raw_notice.payload = notice.payload
        raw_notice.raw_text = notice.raw_text
    return create_opportunity_from_normalized(db, notice.normalized, raw_notice=raw_notice, source_model=source)


def create_manual_opportunity(db: Session, payload: dict[str, Any]) -> Opportunity:
    normalized = normalize_manual_notice(payload)
    opportunity, _ = create_opportunity_from_normalized(db, normalized)
    db.commit()
    db.refresh(opportunity)
    return opportunity


async def analyze_opportunity(db: Session, opportunity: Opportunity) -> tuple[Opportunity, dict[str, Any], dict[str, Any]]:
    keyword_configs = load_keyword_configs(db)
    rag_stats = await prepare_opportunity_rag(db, opportunity)
    payload = opportunity_to_payload(opportunity)
    document_context = _document_context(db, opportunity.id)
    if document_context:
        payload["document_context"] = document_context
    score = score_opportunity(payload, keyword_configs)
    qualified, rejection_reason = prequalification_result(score)
    market_context = await collect_market_intelligence(payload, score)
    payload["market_intelligence"] = market_context
    if qualified:
        report, raw_model_json, model = await build_report(payload, score)
    else:
        report = build_heuristic_report(payload, score)
        raw_model_json = {
            "provider": "prequalification",
            "reason": rejection_reason,
            "skipped_llm": True,
        }
        model = "live-prequalification"
    raw_model_json = _with_combined_usage(raw_model_json, rag_stats)
    report_json = report.model_dump(mode="json")
    html = report_to_html(report)

    db.execute(delete(KeywordMatch).where(KeywordMatch.opportunity_id == opportunity.id))
    for match in score.matched_keywords:
        db.add(
            KeywordMatch(
                opportunity_id=opportunity.id,
                keyword_id=match.keyword_id,
                category_name=match.category,
                keyword_term=match.keyword,
                matched_term=match.matched_term,
                excerpt=match.excerpt,
                weight=match.weight,
                match_type=match.match_type,
            )
        )
    score_record = OpportunityScore(
        opportunity_id=opportunity.id,
        global_score=score.global_score,
        decision=score.decision,
        confidence_score=score.confidence_score,
        human_review_required=score.human_review_required,
        breakdown=score.breakdown,
        matched_keywords=[match.__dict__ for match in score.matched_keywords],
        maluses=score.maluses,
        raw_payload=score.to_dict()
        | {"rag": rag_stats, "qualified": qualified, "rejection_reason": rejection_reason, "market_intelligence": market_context},
    )
    ai_report = AiReport(
        opportunity_id=opportunity.id,
        model=model,
        report_json=report_json,
        html=html,
        raw_model_json=raw_model_json,
        confidence_score=report.confidence_score,
        human_review_required=report.human_review_required,
    )
    db.add(score_record)
    db.add(ai_report)
    opportunity.global_score = score.global_score
    opportunity.score_by_family = score.score_by_family
    opportunity.keyword_traces = [match.__dict__ for match in score.matched_keywords]
    opportunity.ai_report = report_json
    opportunity.normalized_payload = {
        **(opportunity.normalized_payload or {}),
        "rag": rag_stats,
        "live_prequalification": {
            "qualified": qualified,
            "reason": None if qualified else rejection_reason,
            "score": score.global_score,
            "decision": score.decision,
            "live_core_hits": score.breakdown.get("live_core_hits") or [],
            "noise_hits": score.breakdown.get("noise_hits") or [],
        },
        "market_intelligence": market_context,
    }
    next_status = _status_after_analysis(opportunity.status, qualified=qualified, score=score.global_score)
    opportunity.status = next_status
    if next_status == OpportunityStatus.NOT_RELEVANT:
        opportunity.ai_summary = _rejection_summary(score, rejection_reason)
    else:
        opportunity.ai_summary = "\n".join(report.executive_summary.content[:6])

    db.add(
        Notification(
            type=NotificationType.HIGH_SCORE if score.global_score >= 65 else NotificationType.NEW_OPPORTUNITY,
            title="AO analysé",
            message=f"{opportunity.title} - score {score.global_score}/100",
            opportunity_id=opportunity.id,
            payload={"decision": score.decision, "score": score.global_score},
        )
    )
    db.commit()
    db.refresh(opportunity)
    return opportunity, score.to_dict(), report_json


def dashboard_stats(db: Session) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    business_visible = (
        (Opportunity.source != "fixture")
        & Opportunity.status.notin_([OpportunityStatus.NOT_RELEVANT, OpportunityStatus.NO_GO, OpportunityStatus.ARCHIVED])
    )
    metrics = db.execute(
        select(
            func.count(Opportunity.id).filter(business_visible),
            func.count(Opportunity.id).filter(
                Opportunity.source != "fixture", Opportunity.status == OpportunityStatus.NOT_RELEVANT
            ),
            func.count(Opportunity.id).filter(business_visible, Opportunity.global_score >= 80),
            func.count(Opportunity.id).filter(
                business_visible, Opportunity.status == OpportunityStatus.NEW, Opportunity.ai_report.is_(None)
            ),
            func.count(Opportunity.id).filter(
                business_visible, (Opportunity.status != OpportunityStatus.NEW) | Opportunity.ai_report.is_not(None)
            ),
            func.count(Opportunity.id).filter(
                business_visible,
                (Opportunity.global_score >= 65)
                | Opportunity.status.in_(
                    [
                        OpportunityStatus.RELEVANT,
                        OpportunityStatus.TO_QUALIFY,
                        OpportunityStatus.GO,
                        OpportunityStatus.WATCH,
                    ]
                ),
            ),
            func.count(Opportunity.id).filter(business_visible, Opportunity.status == OpportunityStatus.GO),
            func.count(Opportunity.id).filter(
                business_visible,
                Opportunity.deadline.is_not(None),
                Opportunity.deadline >= now,
                Opportunity.deadline <= datetime.fromtimestamp(now.timestamp() + 7 * 86400, tz=timezone.utc),
            ),
        )
    ).one()
    total, rejected, high, to_analyze, analyzed, relevant, study, deadlines = (int(value or 0) for value in metrics)
    active_sources = db.scalar(select(func.count(Source.id)).where(Source.is_active.is_(True))) or 0
    opportunities = db.scalars(
        select(Opportunity)
        .options(load_only(*DASHBOARD_OPPORTUNITY_COLUMNS))
        .where(business_visible)
        .order_by(Opportunity.created_at.desc())
        .limit(8)
    ).all()
    urgent_opportunities = db.scalars(
        select(Opportunity)
        .options(load_only(*DASHBOARD_OPPORTUNITY_COLUMNS))
        .where(business_visible, Opportunity.deadline.is_not(None), Opportunity.deadline >= now)
        .order_by(Opportunity.deadline.asc(), Opportunity.global_score.desc())
        .limit(6)
    ).all()
    token_row = db.execute(
        select(
            func.coalesce(func.sum(AgentRun.total_tokens), 0),
            func.coalesce(func.sum(AgentRun.input_tokens), 0),
            func.coalesce(func.sum(AgentRun.output_tokens), 0),
            func.count(AgentRun.id),
            func.max(AgentRun.finished_at),
        )
        .select_from(AgentRun)
        .join(Agent, Agent.id == AgentRun.agent_id)
        .where(Agent.slug.notin_(list(ORCHESTRATION_AGENT_SLUGS)))
    ).one()
    orchestration_row = db.execute(
        select(
            func.coalesce(func.sum(AgentRun.total_tokens), 0),
            func.count(AgentRun.id),
        )
        .select_from(AgentRun)
        .join(Agent, Agent.id == AgentRun.agent_id)
        .where(Agent.slug.in_(list(ORCHESTRATION_AGENT_SLUGS)))
    ).one()
    latest_model = db.scalar(
        select(AgentRun.model)
        .join(Agent, Agent.id == AgentRun.agent_id)
        .where(AgentRun.model.is_not(None))
        .where(Agent.slug.notin_(list(ORCHESTRATION_AGENT_SLUGS)))
        .order_by(AgentRun.started_at.desc())
        .limit(1)
    )
    run_status_counts = {
        (status.value if isinstance(status, AgentRunStatus) else str(status)): count
        for status, count in db.execute(
            select(AgentRun.status, func.count(AgentRun.id))
            .join(Agent, Agent.id == AgentRun.agent_id)
            .where(Agent.slug.notin_(list(ORCHESTRATION_AGENT_SLUGS)))
            .group_by(AgentRun.status)
        ).all()
    }
    buckets = {"0-44": 0, "45-64": 0, "65-79": 0, "80-100": 0}
    for score_value in db.scalars(select(Opportunity.global_score).where(business_visible)).all():
        if score_value >= 80:
            buckets["80-100"] += 1
        elif score_value >= 65:
            buckets["65-79"] += 1
        elif score_value >= 45:
            buckets["45-64"] += 1
        else:
            buckets["0-44"] += 1
    status_counts = {status.value: 0 for status in OpportunityStatus}
    for status_value, count in db.execute(
        select(Opportunity.status, func.count(Opportunity.id)).where(business_visible).group_by(Opportunity.status)
    ).all():
        status_counts[status_value.value if isinstance(status_value, OpportunityStatus) else str(status_value)] = count
    return {
        "total_opportunities": total,
        "rejected_opportunities": rejected,
        "high_relevance": high,
        "to_analyze": to_analyze,
        "analyzed_opportunities": analyzed,
        "relevant_opportunities": relevant,
        "study_opportunities": study,
        "deadlines_soon": deadlines,
        "active_sources": active_sources,
        "token_usage": {
            "total_tokens": int(token_row[0] or 0),
            "input_tokens": int(token_row[1] or 0),
            "output_tokens": int(token_row[2] or 0),
            "run_count": int(token_row[3] or 0),
            "orchestration_run_count": int(orchestration_row[1] or 0),
            "orchestrated_tokens": int(orchestration_row[0] or 0),
            "success_count": int(run_status_counts.get(AgentRunStatus.SUCCESS.value, 0)),
            "failure_count": int(run_status_counts.get(AgentRunStatus.FAILED.value, 0)),
            "last_run_at": token_row[4],
            "last_model": latest_model,
        },
        "score_buckets": buckets,
        "status_counts": status_counts,
        "latest_opportunities": opportunities,
        "urgent_opportunities": urgent_opportunities,
        "map_points": [],
    }


def dashboard_map_points(db: Session) -> list[dict[str, Any]]:
    business_visible = (
        (Opportunity.source != "fixture")
        & Opportunity.status.notin_([OpportunityStatus.NOT_RELEVANT, OpportunityStatus.NO_GO, OpportunityStatus.ARCHIVED])
    )
    opportunities = db.scalars(
        select(Opportunity)
        .options(load_only(*MAP_OPPORTUNITY_COLUMNS))
        .where(business_visible)
        .order_by(Opportunity.created_at.desc())
    ).all()
    return build_map_points(list(opportunities))
