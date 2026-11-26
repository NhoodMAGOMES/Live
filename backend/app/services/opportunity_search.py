from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Agent, AgentRun, AgentRunStatus, DocumentChunk, Opportunity, OpportunityStatus


SEARCH_AGENT_DEFINITION = {
    "slug": "ao_search",
    "name": "Recherche IA AO",
    "description": "Recherche sémantique dans les AO et les chunks RAG documentaires.",
    "task": "Transformer une requête utilisateur en embedding, interroger le RAG AO et retourner les opportunités les plus proches.",
    "is_active": True,
    "sort_order": 60,
    "config": {"max_results": 25},
    "schedule_enabled": False,
    "schedule_frequency": "manual",
    "schedule_interval": 1,
    "schedule_time": "08:00",
    "schedule_weekday": 0,
}


def _ensure_search_agent(db: Session) -> Agent:
    agent = db.scalar(select(Agent).where(Agent.slug == SEARCH_AGENT_DEFINITION["slug"]))
    if agent:
        return agent
    agent = Agent(**SEARCH_AGENT_DEFINITION)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def _finish_search_run(
    db: Session,
    run: AgentRun,
    *,
    status: AgentRunStatus,
    input_count: int,
    output_count: int,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    model: str | None,
    logs: list[dict[str, Any]],
    error_message: str | None = None,
) -> AgentRun:
    run.status = status
    run.finished_at = datetime.now(timezone.utc)
    run.input_count = input_count
    run.output_count = output_count
    run.success_count = 1 if status == AgentRunStatus.SUCCESS else 0
    run.failure_count = 1 if status == AgentRunStatus.FAILED else 0
    run.input_tokens = input_tokens
    run.output_tokens = output_tokens
    run.total_tokens = total_tokens
    run.model = model
    run.logs = logs
    run.error_message = error_message
    run.agent.last_run_at = run.finished_at
    db.commit()
    db.refresh(run)
    return run


def _base_opportunity_query(
    *,
    source: str | None,
    status: OpportunityStatus | None,
    min_score: float | None,
    buyer: str | None,
    location: str | None,
    deadline: str | None = None,
    deadline_from: date | None = None,
    deadline_to: date | None = None,
) -> list[Any]:
    filters: list[Any] = [Opportunity.source != "fixture"]
    if status is None:
        filters.append(Opportunity.status != OpportunityStatus.ARCHIVED)
    else:
        filters.append(Opportunity.status == status)
    if source:
        filters.append(Opportunity.source == source)
    if min_score is not None:
        filters.append(Opportunity.global_score >= min_score)
    if buyer:
        filters.append(Opportunity.buyer.ilike(f"%{buyer}%"))
    if location:
        filters.append(Opportunity.location.ilike(f"%{location}%"))
    now = datetime.now(timezone.utc)
    if deadline == "soon":
        filters.extend([Opportunity.deadline.is_not(None), Opportunity.deadline >= now, Opportunity.deadline <= now + timedelta(days=7)])
    elif deadline == "overdue":
        filters.extend([Opportunity.deadline.is_not(None), Opportunity.deadline < now])
    elif deadline == "future":
        filters.extend([Opportunity.deadline.is_not(None), Opportunity.deadline >= now])
    elif deadline == "missing":
        filters.append(Opportunity.deadline.is_(None))
    if deadline_from:
        filters.append(Opportunity.deadline >= datetime.combine(deadline_from, time.min, tzinfo=timezone.utc))
    if deadline_to:
        filters.append(Opportunity.deadline <= datetime.combine(deadline_to, time.max, tzinfo=timezone.utc))
    return filters


def _clean_highlight(text: str | None, query: str, max_len: int = 260) -> str:
    compact = " ".join((text or "").split())
    if not compact:
        return ""
    lower = compact.casefold()
    terms = [term for term in query.casefold().split() if len(term) > 2]
    first_hit = min([lower.find(term) for term in terms if lower.find(term) >= 0] or [0])
    start = max(0, first_hit - 80)
    end = min(len(compact), start + max_len)
    prefix = "..." if start else ""
    suffix = "..." if end < len(compact) else ""
    return f"{prefix}{compact[start:end]}{suffix}"


async def _query_embedding(query: str) -> tuple[list[float], dict[str, int], str]:
    settings = get_settings()
    if not settings.llm_enabled:
        raise RuntimeError("OpenAI API key missing")
    from openai import AsyncOpenAI

    http_client = httpx.AsyncClient(verify=settings.openai_verify_ssl)
    client = AsyncOpenAI(api_key=settings.openai_api_key, http_client=http_client)
    try:
        response = await client.embeddings.create(model=settings.embedding_model, input=query)
    finally:
        await http_client.aclose()
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None) or 0)
    total_tokens = int(getattr(usage, "total_tokens", None) or input_tokens)
    return response.data[0].embedding, {"input_tokens": input_tokens, "output_tokens": 0, "total_tokens": total_tokens}, settings.embedding_model


def _fallback_text_search(
    db: Session,
    *,
    query: str,
    source: str | None,
    status: OpportunityStatus | None,
    min_score: float | None,
    buyer: str | None,
    location: str | None,
    deadline: str | None,
    deadline_from: date | None,
    deadline_to: date | None,
    limit: int,
) -> tuple[list[Opportunity], dict[int, list[str]]]:
    like = f"%{query}%"
    filters = _base_opportunity_query(
        source=source,
        status=status,
        min_score=min_score,
        buyer=buyer,
        location=location,
        deadline=deadline,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
    )
    opportunities = db.scalars(
        select(Opportunity)
        .where(
            *filters,
            or_(
                Opportunity.title.ilike(like),
                Opportunity.object.ilike(like),
                Opportunity.description.ilike(like),
                Opportunity.buyer.ilike(like),
                Opportunity.location.ilike(like),
                Opportunity.source_reference.ilike(like),
            ),
        )
        .order_by(Opportunity.global_score.desc(), Opportunity.updated_at.desc())
        .limit(limit)
    ).all()
    highlights = {
        opportunity.id: [
            highlight
            for highlight in [
                _clean_highlight(opportunity.title, query),
                _clean_highlight(opportunity.description or opportunity.object, query),
            ]
            if highlight
        ][:2]
        for opportunity in opportunities
    }
    return list(opportunities), highlights


async def search_opportunities(
    db: Session,
    *,
    query: str,
    source: str | None = None,
    status: OpportunityStatus | None = None,
    min_score: float | None = None,
    buyer: str | None = None,
    location: str | None = None,
    deadline: str | None = None,
    deadline_from: date | None = None,
    deadline_to: date | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    safe_query = " ".join(query.split())
    limit = min(50, max(1, limit))
    agent = _ensure_search_agent(db)
    run = AgentRun(
        agent_id=agent.id,
        status=AgentRunStatus.RUNNING,
        task_name=agent.name,
        target_type="opportunity_search",
        target_id=safe_query[:120],
        logs=[],
        metadata_json={"query": safe_query},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    if not safe_query:
        run = _finish_search_run(
            db,
            run,
            status=AgentRunStatus.FAILED,
            input_count=0,
            output_count=0,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            model=None,
            logs=[],
            error_message="Empty query",
        )
        return {"query": safe_query, "mode": "empty", "run_id": run.id, "items": [], "highlights": {}, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    model: str | None = None
    logs: list[dict[str, Any]] = []
    mode = "lexical"
    items: list[Opportunity] = []
    highlights: dict[int, list[str]] = {}

    try:
        embedding, usage, model = await _query_embedding(safe_query)
        distance = DocumentChunk.embedding.cosine_distance(embedding).label("distance")
        filters = _base_opportunity_query(
            source=source,
            status=status,
            min_score=min_score,
            buyer=buyer,
            location=location,
            deadline=deadline,
            deadline_from=deadline_from,
            deadline_to=deadline_to,
        )
        rows = db.execute(
            select(Opportunity, DocumentChunk.text, distance)
            .join(DocumentChunk, DocumentChunk.opportunity_id == Opportunity.id)
            .where(*filters, DocumentChunk.embedding.is_not(None))
            .order_by(distance.asc())
            .limit(limit * 4)
        ).all()
        seen: set[int] = set()
        for opportunity, chunk_text, score_distance in rows:
            if opportunity.id in seen:
                if len(highlights.get(opportunity.id, [])) < 2:
                    highlights.setdefault(opportunity.id, []).append(_clean_highlight(chunk_text, safe_query))
                continue
            seen.add(opportunity.id)
            items.append(opportunity)
            highlights[opportunity.id] = [_clean_highlight(chunk_text, safe_query)]
            logs.append({"opportunity_id": opportunity.id, "distance": float(score_distance or 0), "title": opportunity.title})
            if len(items) >= limit:
                break
        if items:
            mode = "semantic"
        else:
            items, highlights = _fallback_text_search(
                db,
                query=safe_query,
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
            mode = "semantic_then_lexical"
    except Exception as exc:
        logs.append({"event": "semantic_search_failed", "error": str(exc)})
        items, highlights = _fallback_text_search(
            db,
            query=safe_query,
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
        mode = "lexical"

    run = _finish_search_run(
        db,
        run,
        status=AgentRunStatus.SUCCESS,
        input_count=1,
        output_count=len(items),
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        total_tokens=usage["total_tokens"],
        model=model,
        logs=logs,
    )
    return {
        "query": safe_query,
        "mode": mode,
        "run_id": run.id,
        "items": items,
        "highlights": highlights,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "total_tokens": usage["total_tokens"],
    }
