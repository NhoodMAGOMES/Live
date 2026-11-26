from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select

from app.api.deps import DbSession, require_admin
from app.models import Agent, AgentRun, AgentRunStatus
from app.schemas import AgentRead, AgentRunRead, AgentRunRequest, AgentStats, AgentUpdate
from app.services.agent_orchestrator import ensure_default_agents, normalize_schedule, run_agent
from app.services.agent_usage import is_orchestration_agent


router = APIRouter(prefix="/agents", tags=["agents"], dependencies=[Depends(require_admin)])


def _status_value(status: AgentRunStatus | str) -> str:
    return status.value if isinstance(status, AgentRunStatus) else str(status)


def _agent_payload(db: DbSession, agent: Agent) -> dict:
    recent_runs = db.scalars(
        select(AgentRun).where(AgentRun.agent_id == agent.id).order_by(AgentRun.started_at.desc()).limit(25)
    ).all()
    stats_row = db.execute(
        select(
            func.count(AgentRun.id),
            func.coalesce(func.sum(case((AgentRun.status == AgentRunStatus.SUCCESS, 1), else_=0)), 0),
            func.coalesce(func.sum(case((AgentRun.status == AgentRunStatus.FAILED, 1), else_=0)), 0),
            func.coalesce(func.sum(case((AgentRun.status == AgentRunStatus.SKIPPED, 1), else_=0)), 0),
            func.coalesce(func.sum(AgentRun.total_tokens), 0),
            func.coalesce(func.sum(AgentRun.input_tokens), 0),
            func.coalesce(func.sum(AgentRun.output_tokens), 0),
        ).where(AgentRun.agent_id == agent.id)
    ).one()
    run_count = int(stats_row[0] or 0)
    success_count = int(stats_row[1] or 0)
    failure_count = int(stats_row[2] or 0)
    skipped_count = int(stats_row[3] or 0)
    input_tokens = int(stats_row[5] or 0)
    output_tokens = int(stats_row[6] or 0)
    total_tokens = int(stats_row[4] or 0)
    is_orchestration = is_orchestration_agent(agent.slug)
    measured_count = success_count + failure_count
    stats = AgentStats(
        run_count=run_count,
        success_count=success_count,
        failure_count=failure_count,
        skipped_count=skipped_count,
        success_rate=round((success_count / measured_count) * 100, 1) if measured_count else 0,
        total_tokens=0 if is_orchestration else total_tokens,
        input_tokens=0 if is_orchestration else input_tokens,
        output_tokens=0 if is_orchestration else output_tokens,
        orchestrated_tokens=total_tokens if is_orchestration else 0,
        orchestrated_input_tokens=input_tokens if is_orchestration else 0,
        orchestrated_output_tokens=output_tokens if is_orchestration else 0,
        last_status=_status_value(recent_runs[0].status) if recent_runs else None,
    )
    return {
        "id": agent.id,
        "slug": agent.slug,
        "name": agent.name,
        "description": agent.description,
        "task": agent.task,
        "is_active": agent.is_active,
        "sort_order": agent.sort_order,
        "config": agent.config,
        "last_run_at": agent.last_run_at,
        "schedule_enabled": agent.schedule_enabled,
        "schedule_frequency": agent.schedule_frequency,
        "schedule_interval": agent.schedule_interval,
        "schedule_time": agent.schedule_time,
        "schedule_weekday": agent.schedule_weekday,
        "next_run_at": agent.next_run_at,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
        "stats": stats,
        "recent_runs": recent_runs[:5],
    }


@router.get("", response_model=list[AgentRead])
def list_agents(db: DbSession) -> list[dict]:
    ensure_default_agents(db)
    agents = db.scalars(select(Agent).order_by(Agent.sort_order, Agent.name)).all()
    return [_agent_payload(db, agent) for agent in agents]


@router.patch("/{slug}", response_model=AgentRead)
def update_agent(slug: str, payload: AgentUpdate, db: DbSession) -> dict:
    ensure_default_agents(db)
    agent = db.scalar(select(Agent).where(Agent.slug == slug))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(agent, field, value)
    if any(field.startswith("schedule_") for field in changes):
        normalize_schedule(agent)
    db.commit()
    db.refresh(agent)
    return _agent_payload(db, agent)


@router.post("/{slug}/run", response_model=AgentRunRead)
async def run_agent_route(slug: str, db: DbSession, payload: AgentRunRequest | None = None) -> AgentRun:
    try:
        override = payload.config_override if payload else None
        return await run_agent(db, slug, config_override=override or None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
