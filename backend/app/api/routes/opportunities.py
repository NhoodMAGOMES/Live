from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import load_only

from app.api.deps import DbSession, get_current_user
from app.models import AiReport, AuditLog, DocumentChunk, Opportunity, OpportunityDocument, OpportunityScore, OpportunityStatus, User
from app.schemas import (
    AnalysisResponse,
    OpportunityAuditRead,
    OpportunityBatchAnalyzeRequest,
    OpportunityBatchAnalyzeResponse,
    OpportunityDocumentRead,
    OpportunityImport,
    OpportunityListResponse,
    OpportunityRead,
    OpportunitySearchResponse,
    OpportunityStatusUpdate,
)
from app.services.documents import extract_text_from_bytes, chunk_text
from app.services.normalization import normalize_manual_notice
from app.services.agent_orchestrator import run_agent
from app.services.audit import action_label, actor_from_audit, actor_snapshot, status_snapshot, status_transition, transition_from_audit
from app.services.opportunities import create_manual_opportunity
from app.services.opportunity_search import search_opportunities
from app.services.reports import simple_pdf_bytes
from app.services.storage import save_local_file


router = APIRouter(prefix="/opportunities", tags=["opportunities"])

OPPORTUNITY_LIST_COLUMNS = (
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


def _apply_deadline_filter(query, *, deadline: str | None, deadline_from: date | None, deadline_to: date | None):
    now = datetime.now(timezone.utc)
    if deadline == "soon":
        query = query.where(Opportunity.deadline.is_not(None), Opportunity.deadline >= now, Opportunity.deadline <= now + timedelta(days=7))
    elif deadline == "overdue":
        query = query.where(Opportunity.deadline.is_not(None), Opportunity.deadline < now)
    elif deadline == "future":
        query = query.where(Opportunity.deadline.is_not(None), Opportunity.deadline >= now)
    elif deadline == "missing":
        query = query.where(Opportunity.deadline.is_(None))
    if deadline_from:
        query = query.where(Opportunity.deadline >= datetime.combine(deadline_from, time.min, tzinfo=timezone.utc))
    if deadline_to:
        query = query.where(Opportunity.deadline <= datetime.combine(deadline_to, time.max, tzinfo=timezone.utc))
    return query


def _processed_opportunity_filter():
    return (
        Opportunity.status.notin_(
            [
                OpportunityStatus.NEW,
                OpportunityStatus.NOT_RELEVANT,
                OpportunityStatus.NO_GO,
                OpportunityStatus.ARCHIVED,
            ]
        )
    ) | (
        Opportunity.ai_report.is_not(None)
        & Opportunity.status.notin_(
            [
                OpportunityStatus.NOT_RELEVANT,
                OpportunityStatus.NO_GO,
                OpportunityStatus.ARCHIVED,
            ]
        )
    )


def _local_event_trends_section(opportunity: Opportunity) -> dict[str, list[str] | str]:
    location = opportunity.location or "Non disponible"
    buyer = opportunity.buyer or "Non disponible"
    title = opportunity.title or "Non disponible"
    return {
        "title": "Analyse locale événementielle",
        "content": [
            f"Territoire analysé: {location}.",
            f"Signal de contexte: acheteur {buyer}, AO {title}.",
            "Synthèse IA à consolider: identifier les événements déjà tenus localement, les formats appréciés par les habitants, la saisonnalité, les publics dominants et les partenaires culturels ou commerçants activables.",
            "Hypothèse de réponse LIVE: proposer une programmation ancrée localement, mesurable, compatible avec les usages quotidiens du lieu et capable de créer du trafic utile pour le territoire.",
        ],
        "evidence": [
            f"Localisation AO: {location}",
            f"Acheteur: {buyer}",
            f"Titre AO: {title}",
        ],
    }


def _market_positioning_section(opportunity: Opportunity) -> dict[str, list[str] | str]:
    buyer = opportunity.buyer or "Non disponible"
    location = opportunity.location or "Non disponible"
    return {
        "title": "Positionnement marché et AO comparables",
        "content": [
            "AO comparables passés: Non disponible dans les preuves actuellement attachées.",
            "Attributaires ou confrères identifiés: Non disponible.",
            "Ordres de grandeur financiers publics: Non disponible.",
            "Critères de jugement ou note technique observés: Non disponible.",
            "Recherche recommandée: croiser BOAMP, avis d'attribution, données essentielles de marchés publics, profils acheteurs et dossiers similaires avant une étude réponse.",
        ],
        "evidence": [
            f"Acheteur à comparer: {buyer}",
            f"Territoire à comparer: {location}",
        ],
    }


def _section_to_html(section: dict[str, Any]) -> str:
    content = "".join(f"<li>{escape(str(item))}</li>" for item in section.get("content") or [])
    evidence = "".join(f"<blockquote>{escape(str(item))}</blockquote>" for item in (section.get("evidence") or [])[:6])
    return f"<section><h2>{escape(str(section.get('title') or 'Analyse locale événementielle'))}</h2><ul>{content}</ul>{evidence}</section>"


def _report_payload(report: AiReport, opportunity: Opportunity) -> dict[str, Any]:
    report_json = dict(report.report_json or {})
    local_section = report_json.get("local_event_trends")
    if not isinstance(local_section, dict):
        local_section = _local_event_trends_section(opportunity)
        report_json["local_event_trends"] = local_section
    market_section = report_json.get("market_positioning")
    if not isinstance(market_section, dict):
        market_section = _market_positioning_section(opportunity)
        report_json["market_positioning"] = market_section

    html = report.html or ""
    if "Analyse locale événementielle" not in html:
        section_html = _section_to_html(local_section)
        lower_html = html.lower()
        body_index = lower_html.rfind("</body>")
        html = f"{html[:body_index]}{section_html}{html[body_index:]}" if body_index >= 0 else f"{html}{section_html}"
    if "Positionnement marché et AO comparables" not in html:
        section_html = _section_to_html(market_section)
        lower_html = html.lower()
        body_index = lower_html.rfind("</body>")
        html = f"{html[:body_index]}{section_html}{html[body_index:]}" if body_index >= 0 else f"{html}{section_html}"

    return {"report": report_json, "html": html, "model": report.model}


@router.get("", response_model=OpportunityListResponse)
def list_opportunities(
    db: DbSession,
    source: str | None = None,
    status: OpportunityStatus | None = None,
    processed: bool = False,
    min_score: float | None = None,
    family: str | None = None,
    keyword: str | None = None,
    buyer: str | None = None,
    location: str | None = None,
    deadline: str | None = None,
    deadline_from: date | None = None,
    deadline_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    query = select(Opportunity).where(Opportunity.source != "fixture")
    if processed:
        query = query.where(_processed_opportunity_filter())
    elif status is None:
        query = query.where(Opportunity.status != OpportunityStatus.ARCHIVED)
    if source:
        query = query.where(Opportunity.source == source)
    if status:
        query = query.where(Opportunity.status == status)
        if status == OpportunityStatus.NEW and not processed:
            query = query.where(Opportunity.ai_report.is_(None))
    if min_score is not None:
        query = query.where(Opportunity.global_score >= min_score)
    if buyer:
        query = query.where(Opportunity.buyer.ilike(f"%{buyer}%"))
    if location:
        query = query.where(Opportunity.location.ilike(f"%{location}%"))
    query = _apply_deadline_filter(query, deadline=deadline, deadline_from=deadline_from, deadline_to=deadline_to)
    if family:
        query = query.where(Opportunity.score_by_family.has_key(family))  # noqa: W601
    if keyword:
        query = query.where(Opportunity.keyword_traces.contains([{"keyword": keyword}]))
    total = db.scalar(query.with_only_columns(func.count(Opportunity.id)).order_by(None)) or 0
    items = db.scalars(
        query.options(load_only(*OPPORTUNITY_LIST_COLUMNS))
        .order_by(Opportunity.global_score.desc(), Opportunity.deadline.asc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "total": total}


@router.get("/search", response_model=OpportunitySearchResponse)
async def search(
    db: DbSession,
    q: str,
    source: str | None = None,
    status: OpportunityStatus | None = None,
    min_score: float | None = None,
    buyer: str | None = None,
    location: str | None = None,
    deadline: str | None = None,
    deadline_from: date | None = None,
    deadline_to: date | None = None,
    limit: int = 25,
) -> dict:
    result = await search_opportunities(
        db,
        query=q,
        source=source,
        status=status,
        min_score=min_score,
        buyer=buyer,
        location=location,
        deadline=deadline,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        limit=limit,
    )
    return {**result, "total": len(result["items"])}


@router.post("/analyze-batch", response_model=OpportunityBatchAnalyzeResponse)
async def analyze_batch(
    payload: OpportunityBatchAnalyzeRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    opportunities = db.scalars(
        select(Opportunity)
        .where(Opportunity.id.in_(payload.opportunity_ids), Opportunity.source != "fixture")
        .order_by(Opportunity.created_at.asc())
    ).all()
    found_ids = {opportunity.id for opportunity in opportunities}
    before_status_by_id = {opportunity.id: opportunity.status for opportunity in opportunities}
    errors = [
        {"opportunity_id": opportunity_id, "error": "Opportunity not found"}
        for opportunity_id in payload.opportunity_ids
        if opportunity_id not in found_ids
    ]
    run = None
    updated: list[Opportunity] = []
    if found_ids:
        run = await run_agent(
            db,
            "ao_analyzer",
            config_override={"opportunity_ids": sorted(found_ids), "manual_selection": True},
        )
        errors.extend(
            {"opportunity_id": log.get("opportunity_id"), "error": log.get("error") or "Analyse échouée"}
            for log in (run.logs or [])
            if log.get("status") == "failed"
        )
        success_ids = [int(log["opportunity_id"]) for log in (run.logs or []) if log.get("status") == "success" and log.get("opportunity_id")]
        updated = (
            list(
                db.scalars(
                    select(Opportunity)
                    .where(Opportunity.id.in_(success_ids))
                    .order_by(Opportunity.created_at.asc())
                ).all()
            )
            if success_ids
            else []
        )
        for opportunity in updated:
            before_status = before_status_by_id.get(opportunity.id)
            db.add(
                AuditLog(
                    actor_user_id=current_user.id,
                    entity_type="opportunity",
                    entity_id=str(opportunity.id),
                    action="analysis_run",
                    before=status_snapshot(before_status),
                    after={
                        **status_snapshot(opportunity.status),
                        "run_id": run.id,
                        "score": opportunity.global_score,
                        "actor": actor_snapshot(current_user),
                        "origin": "batch_analysis",
                    },
                )
            )
        if updated:
            db.commit()
    return {
        "run_id": run.id if run else None,
        "analyzed_count": len(updated),
        "failed_count": len(errors),
        "input_tokens": run.input_tokens if run else 0,
        "output_tokens": run.output_tokens if run else 0,
        "total_tokens": run.total_tokens if run else 0,
        "opportunities": updated,
        "errors": errors,
    }


@router.get("/{opportunity_id}", response_model=OpportunityRead)
def get_opportunity(opportunity_id: int, db: DbSession) -> Opportunity:
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity or opportunity.source == "fixture":
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opportunity


@router.get("/{opportunity_id}/documents", response_model=list[OpportunityDocumentRead])
def list_documents(opportunity_id: int, db: DbSession) -> list[OpportunityDocument]:
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return list(
        db.scalars(
            select(OpportunityDocument)
            .where(OpportunityDocument.opportunity_id == opportunity_id)
            .order_by(OpportunityDocument.created_at.desc())
        ).all()
    )


@router.get("/{opportunity_id}/audit", response_model=list[OpportunityAuditRead])
def list_audit(opportunity_id: int, db: DbSession) -> list[dict[str, Any]]:
    rows = db.execute(
        select(AuditLog, User)
        .outerjoin(User, AuditLog.actor_user_id == User.id)
        .where(AuditLog.entity_type == "opportunity", AuditLog.entity_id == str(opportunity_id))
        .order_by(AuditLog.created_at.desc())
        .limit(50)
    ).all()
    return [
        _audit_payload(log, user)
        for log, user in rows
    ]


def _audit_payload(log: AuditLog, user: User | None) -> dict[str, Any]:
    actor = actor_from_audit(log, user)
    return {
        "id": log.id,
        "action": log.action,
        "action_label": action_label(log.action),
        "actor_user_id": log.actor_user_id,
        "actor_label": actor["label"],
        "actor_role": actor.get("role"),
        "before": log.before,
        "after": log.after,
        "transition": transition_from_audit(log),
        "created_at": log.created_at,
    }


@router.get("/{opportunity_id}/documents/{document_id}/download")
def download_document(opportunity_id: int, document_id: int, db: DbSession) -> FileResponse:
    document = db.get(OpportunityDocument, document_id)
    if not document or document.opportunity_id != opportunity_id:
        raise HTTPException(status_code=404, detail="Document not found")
    path = Path(document.storage_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Document file not found")
    return FileResponse(
        path,
        media_type=document.content_type or "application/octet-stream",
        filename=document.filename,
    )


@router.post("/{opportunity_id}/analyze", response_model=AnalysisResponse)
async def analyze(
    opportunity_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    before_status = opportunity.status
    run = await run_agent(db, "ao_analyzer", config_override={"opportunity_ids": [opportunity_id], "manual_selection": True})
    if run.failure_count:
        failure = next((log for log in (run.logs or []) if log.get("status") == "failed"), {})
        raise HTTPException(status_code=500, detail=failure.get("error") or "Analysis failed")
    updated = db.get(Opportunity, opportunity_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            entity_type="opportunity",
            entity_id=str(updated.id),
            action="analysis_run",
            before=status_snapshot(before_status),
            after={
                **status_snapshot(updated.status),
                "run_id": run.id,
                "score": updated.global_score,
                "actor": actor_snapshot(current_user),
                "origin": "detail_analysis",
            },
        )
    )
    db.commit()
    db.refresh(updated)
    latest_score = db.scalar(
        select(OpportunityScore)
        .where(OpportunityScore.opportunity_id == opportunity_id)
        .order_by(OpportunityScore.created_at.desc())
    )
    latest_report = db.scalar(
        select(AiReport)
        .where(AiReport.opportunity_id == opportunity_id)
        .order_by(AiReport.created_at.desc())
    )
    score = latest_score.raw_payload if latest_score else {}
    report = latest_report.report_json if latest_report else {}
    return {"opportunity": updated, "score": score, "report": report}


@router.patch("/{opportunity_id}/status", response_model=OpportunityRead)
def update_status(
    opportunity_id: int,
    payload: OpportunityStatusUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Opportunity:
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if opportunity.status == payload.status:
        return opportunity
    before_status = opportunity.status
    opportunity.status = payload.status
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            entity_type="opportunity",
            entity_id=str(opportunity.id),
            action="status_update",
            before=status_snapshot(before_status),
            after={
                **status_snapshot(payload.status),
                "actor": actor_snapshot(current_user),
                "origin": payload.origin or "manual_status_update",
                "transition": status_transition(before_status, payload.status),
            },
        )
    )
    db.commit()
    db.refresh(opportunity)
    return opportunity


@router.post("/import-url", response_model=OpportunityRead)
async def import_url(payload: OpportunityImport, db: DbSession) -> Opportunity:
    opportunity = create_manual_opportunity(db, payload.model_dump())
    return opportunity


@router.post("/import-file", response_model=OpportunityRead)
async def import_file(file: UploadFile, db: DbSession) -> Opportunity:
    content = await file.read()
    text = extract_text_from_bytes(file.filename or "upload.txt", content, file.content_type)
    path, digest = save_local_file(file.filename or "upload.txt", content)
    opportunity = create_manual_opportunity(
        db,
        {
            "source": "manual_upload",
            "source_reference": digest[:24],
            "title": file.filename or "AO importé",
            "description": text,
        },
    )
    document = OpportunityDocument(
        opportunity_id=opportunity.id,
        filename=file.filename or "upload.txt",
        content_type=file.content_type,
        storage_path=path,
        content_hash=digest,
        extracted_text=text,
    )
    db.add(document)
    db.flush()
    for index, chunk in enumerate(chunk_text(text)):
        db.add(DocumentChunk(opportunity_id=opportunity.id, document_id=document.id, chunk_index=index, text=chunk))
    db.commit()
    db.refresh(opportunity)
    return opportunity


@router.get("/{opportunity_id}/report")
def get_report(opportunity_id: int, db: DbSession) -> dict:
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    report = db.scalar(select(AiReport).where(AiReport.opportunity_id == opportunity_id).order_by(AiReport.created_at.desc()))
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_payload(report, opportunity)


@router.get("/{opportunity_id}/export/pdf")
def export_pdf(opportunity_id: int, db: DbSession) -> Response:
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    report = db.scalar(select(AiReport).where(AiReport.opportunity_id == opportunity_id).order_by(AiReport.created_at.desc()))
    lines = [opportunity.title, f"Score: {opportunity.global_score}/100", f"Statut: {opportunity.status.value}"]
    if report:
        report_payload = _report_payload(report, opportunity)
        for section in report_payload["report"].values():
            if isinstance(section, dict):
                lines.extend(section.get("content") or [])
    pdf = simple_pdf_bytes("Rapport AO LIVE Pulse", lines)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=opportunity-{opportunity_id}-report.pdf"},
    )
