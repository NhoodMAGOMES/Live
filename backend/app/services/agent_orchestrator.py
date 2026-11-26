from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.pulse_strategy import PulseStrategyAgent
from app.agents.source_discovery import SourceDiscoveryAgent
from app.models import (
    Agent,
    AgentRun,
    AgentRunStatus,
    AiReport,
    Notification,
    NotificationType,
    Opportunity,
    OpportunityStatus,
    Source,
)
from app.services.opportunities import analyze_opportunity
from app.services.reports import extract_token_usage


PARIS_TZ = ZoneInfo("Europe/Paris")
VALID_SCHEDULE_FREQUENCIES = {"manual", "hourly", "daily", "weekly"}


DEFAULT_AGENTS: list[dict[str, Any]] = [
    {
        "slug": "verification_cycle",
        "name": "Cycle de vérification AO",
        "description": "Orchestre la chaîne active: sources, analyse, classement et alertes.",
        "task": "Lancer les agents actifs dans l'ordre et consolider les métriques du cycle.",
        "is_active": True,
        "sort_order": 10,
        "config": {"mode": "active_agents"},
        "schedule_enabled": True,
        "schedule_frequency": "daily",
        "schedule_interval": 1,
        "schedule_time": "08:00",
        "schedule_weekday": 0,
    },
    {
        "slug": "source_discovery",
        "name": "Recherche plateformes LIVE",
        "description": "Cherche les AO sur les plateformes avec les mots-clés orientés événementiel, lieux vivants et stratégie LIVE.",
        "task": "Exécuter les connecteurs actifs avec une recherche ciblée et créer le vivier brut des AO détectés par mots-clés.",
        "is_active": True,
        "sort_order": 20,
        "config": {
            "keywords": [
                "AMO",
                "assistance à maîtrise d'ouvrage",
                "prestation intellectuelle",
                "marché de prestation intellectuelle",
                "mission de conseil",
                "mission d'étude",
                "étude de faisabilité",
                "étude de potentiel",
                "audit stratégique",
                "programmation événementielle",
                "programmation culturelle",
                "programmation artistique",
                "exploitation événementielle",
                "gestion événementielle de site",
                "lieu culturel",
                "équipement culturel",
                "espaces d'exposition",
                "médiation culturelle",
                "valorisation patrimoniale",
                "transformation d'édifice",
                "reconversion de site",
                "spectacle vivant",
                "activation de lieu",
                "commercialisation d'espaces",
                "concession culturelle",
                "DSP culturelle",
                "appel à projets culturel",
            ],
            "days_back": 14,
            "limit": 300,
            "min_live_score": 25,
            "departments": [],
            "prequalification_enabled": True,
            "use_live_query_expansion": True,
        },
        "schedule_enabled": False,
        "schedule_frequency": "manual",
        "schedule_interval": 1,
        "schedule_time": "08:00",
        "schedule_weekday": 0,
    },
    {
        "slug": "ao_analyzer",
        "name": "Analyse AO et rapport",
        "description": "Récupère l'annonce complète, prépare les documents en RAG, score les AO non analysés et génère le rapport IA structuré.",
        "task": "Analyser les AO sélectionnés ou entrants, récupérer les pièces disponibles, indexer le RAG, calculer les scores et répartir entre pertinent, analysé et écarté par IA.",
        "is_active": True,
        "sort_order": 30,
        "config": {"max_items_per_run": 5},
        "schedule_enabled": False,
        "schedule_frequency": "manual",
        "schedule_interval": 1,
        "schedule_time": "08:00",
        "schedule_weekday": 0,
    },
    {
        "slug": "ao_classifier",
        "name": "Classement AO",
        "description": "Classe les AO analysés en GO, WATCH ou NO-GO.",
        "task": "Transformer les scores en décision opérationnelle sans réappeler le LLM.",
        "is_active": True,
        "sort_order": 40,
        "config": {"max_items_per_run": 100},
        "schedule_enabled": False,
        "schedule_frequency": "manual",
        "schedule_interval": 1,
        "schedule_time": "08:00",
        "schedule_weekday": 0,
    },
    {
        "slug": "alert_dispatcher",
        "name": "Alertes et priorités",
        "description": "Crée les notifications utiles pour les AO prioritaires et deadlines proches.",
        "task": "Surveiller les signaux business et alimenter la file de notifications.",
        "is_active": True,
        "sort_order": 50,
        "config": {"deadline_days": 7},
        "schedule_enabled": False,
        "schedule_frequency": "manual",
        "schedule_interval": 1,
        "schedule_time": "08:00",
        "schedule_weekday": 0,
    },
    {
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
    },
]


def ensure_default_agents(db: Session) -> None:
    changed = False
    existing = {agent.slug: agent for agent in db.scalars(select(Agent)).all()}
    for definition in DEFAULT_AGENTS:
        agent = existing.get(definition["slug"])
        if not agent:
            new_agent = Agent(**definition)
            normalize_schedule(new_agent)
            db.add(new_agent)
            changed = True
            continue
        for field in ("name", "description", "task", "sort_order"):
            value = definition[field]
            if getattr(agent, field) != value:
                setattr(agent, field, value)
                changed = True
        if not agent.config:
            agent.config = definition["config"]
            changed = True
        elif agent.slug == "source_discovery":
            config = dict(agent.config or {})
            default_config = definition["config"]
            config_changed = False
            current_keywords = [str(keyword).strip() for keyword in config.get("keywords") or [] if str(keyword).strip()]
            seen_keywords = {keyword.casefold() for keyword in current_keywords}
            for keyword in default_config.get("keywords") or []:
                if str(keyword).casefold() not in seen_keywords:
                    current_keywords.append(str(keyword))
                    seen_keywords.add(str(keyword).casefold())
            if current_keywords != config.get("keywords"):
                config["keywords"] = current_keywords
                config_changed = True
            if float(config.get("min_live_score") or 0) < float(default_config.get("min_live_score") or 25):
                config["min_live_score"] = default_config.get("min_live_score")
                config_changed = True
            if "departments" not in config:
                config["departments"] = []
                config_changed = True
            if config_changed:
                agent.config = config
                changed = True
        if agent.schedule_enabled and not agent.next_run_at:
            agent.next_run_at = compute_next_run_at(agent)
            changed = True
    if changed:
        db.commit()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _start_run(db: Session, agent: Agent, *, target_type: str | None = None, target_id: str | None = None) -> AgentRun:
    run = AgentRun(
        agent_id=agent.id,
        status=AgentRunStatus.RUNNING,
        task_name=agent.task,
        target_type=target_type,
        target_id=target_id,
        logs=[],
        metadata_json={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _finish_run(
    db: Session,
    run: AgentRun,
    *,
    status: AgentRunStatus,
    input_count: int = 0,
    output_count: int = 0,
    success_count: int = 0,
    failure_count: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    model: str | None = None,
    error_message: str | None = None,
    logs: list[dict[str, Any]] | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> AgentRun:
    run.status = status
    run.finished_at = _now()
    run.input_count = input_count
    run.output_count = output_count
    run.success_count = success_count
    run.failure_count = failure_count
    run.input_tokens = input_tokens
    run.output_tokens = output_tokens
    run.total_tokens = total_tokens
    run.model = model
    run.error_message = error_message
    run.logs = jsonable_encoder(logs or [])
    run.metadata_json = jsonable_encoder(metadata_json or {})
    run.agent.last_run_at = run.finished_at
    db.commit()
    db.refresh(run)
    return run


def _int_config(agent: Agent, key: str, default: int) -> int:
    try:
        return int((agent.config or {}).get(key, default))
    except (TypeError, ValueError):
        return default


def _parse_schedule_time(value: str | None) -> tuple[int, int]:
    try:
        hour_raw, minute_raw = (value or "08:00").split(":", 1)
        hour = min(23, max(0, int(hour_raw)))
        minute = min(59, max(0, int(minute_raw)))
        return hour, minute
    except (TypeError, ValueError):
        return 8, 0


def normalize_schedule(agent: Agent) -> None:
    if agent.schedule_frequency not in VALID_SCHEDULE_FREQUENCIES:
        agent.schedule_frequency = "manual"
    agent.schedule_interval = max(1, int(agent.schedule_interval or 1))
    agent.schedule_weekday = min(6, max(0, int(agent.schedule_weekday or 0)))
    hour, minute = _parse_schedule_time(agent.schedule_time)
    agent.schedule_time = f"{hour:02d}:{minute:02d}"
    if agent.schedule_frequency == "manual":
        agent.schedule_enabled = False
        agent.next_run_at = None
    elif agent.schedule_enabled:
        agent.next_run_at = compute_next_run_at(agent)
    else:
        agent.next_run_at = None


def compute_next_run_at(agent: Agent, *, from_time: datetime | None = None) -> datetime | None:
    if not agent.schedule_enabled or agent.schedule_frequency == "manual":
        return None
    interval = max(1, int(agent.schedule_interval or 1))
    current = from_time or _now()
    current_local = current.astimezone(PARIS_TZ)
    hour, minute = _parse_schedule_time(agent.schedule_time)

    if agent.schedule_frequency == "hourly":
        return (current + timedelta(hours=interval)).astimezone(timezone.utc)

    if agent.schedule_frequency == "daily":
        candidate = current_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        while candidate <= current_local:
            candidate += timedelta(days=interval)
        return candidate.astimezone(timezone.utc)

    if agent.schedule_frequency == "weekly":
        weekday = min(6, max(0, int(agent.schedule_weekday or 0)))
        days_ahead = (weekday - current_local.weekday()) % 7
        candidate = (current_local + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        while candidate <= current_local:
            candidate += timedelta(weeks=interval)
        return candidate.astimezone(timezone.utc)

    return None


async def run_agent(db: Session, slug: str, config_override: dict[str, Any] | None = None) -> AgentRun:
    ensure_default_agents(db)
    agent = db.scalar(select(Agent).where(Agent.slug == slug))
    if not agent:
        raise ValueError(f"Agent inconnu: {slug}")

    run = _start_run(db, agent, target_type="manual_search" if config_override else None)
    if not agent.is_active:
        return _finish_run(
            db,
            run,
            status=AgentRunStatus.SKIPPED,
            logs=[{"message": "Agent inactif, exécution ignorée."}],
        )

    try:
        if slug == "verification_cycle":
            return await _run_verification_cycle(db, agent, run)
        if slug == "source_discovery":
            return await _run_source_discovery(db, agent, run, config_override=config_override)
        if slug == "ao_analyzer":
            return await _run_ao_analyzer(db, agent, run, config_override=config_override)
        if slug == "ao_search":
            return _finish_run(
                db,
                run,
                status=AgentRunStatus.SKIPPED,
                logs=[{"message": "Agent déclenché uniquement par le moteur de recherche IA avec une requête utilisateur."}],
            )
        if slug == "ao_classifier":
            return await _run_ao_classifier(db, agent, run)
        if slug == "alert_dispatcher":
            return await _run_alert_dispatcher(db, agent, run)
        return _finish_run(db, run, status=AgentRunStatus.FAILED, error_message="Aucun handler associé.")
    except Exception as exc:
        db.rollback()
        return _finish_run(db, run, status=AgentRunStatus.FAILED, error_message=str(exc))


async def run_scheduled_agents(db: Session) -> list[AgentRun]:
    ensure_default_agents(db)
    now = _now()
    due_agents = db.scalars(
        select(Agent)
        .where(
            Agent.is_active.is_(True),
            Agent.schedule_enabled.is_(True),
            Agent.next_run_at.is_not(None),
            Agent.next_run_at <= now,
        )
        .order_by(Agent.sort_order, Agent.next_run_at)
    ).all()
    runs: list[AgentRun] = []
    for agent in due_agents:
        run = await run_agent(db, agent.slug)
        refreshed_agent = db.get(Agent, agent.id)
        if refreshed_agent:
            refreshed_agent.next_run_at = compute_next_run_at(refreshed_agent, from_time=run.finished_at or now)
            db.commit()
        runs.append(run)
    return runs


async def _run_verification_cycle(db: Session, agent: Agent, run: AgentRun) -> AgentRun:
    child_agents = db.scalars(
        select(Agent)
        .where(Agent.slug.notin_(["verification_cycle", "ao_search"]), Agent.is_active.is_(True))
        .order_by(Agent.sort_order)
    ).all()
    logs: list[dict[str, Any]] = []
    totals = {
        "input_count": 0,
        "output_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    failed = 0
    for child in child_agents:
        child_run = await run_agent(db, child.slug)
        failed += 1 if child_run.status == AgentRunStatus.FAILED else 0
        totals["input_count"] += child_run.input_count
        totals["output_count"] += child_run.output_count
        totals["success_count"] += 1 if child_run.status == AgentRunStatus.SUCCESS else 0
        totals["failure_count"] += 1 if child_run.status == AgentRunStatus.FAILED else 0
        totals["input_tokens"] += child_run.input_tokens
        totals["output_tokens"] += child_run.output_tokens
        totals["total_tokens"] += child_run.total_tokens
        logs.append(
            {
                "agent": child.slug,
                "status": child_run.status.value,
                "run_id": child_run.id,
                "tokens": child_run.total_tokens,
                "processed": child_run.input_count,
            }
        )
    return _finish_run(
        db,
        run,
        status=AgentRunStatus.FAILED if failed else AgentRunStatus.SUCCESS,
        logs=logs,
        metadata_json={"active_agents": [agent.slug for agent in child_agents]},
        **totals,
    )


async def _run_source_discovery(db: Session, agent: Agent, run: AgentRun, config_override: dict[str, Any] | None = None) -> AgentRun:
    sources = db.scalars(select(Source).where(Source.is_active.is_(True)).order_by(Source.name)).all()
    logs: list[dict[str, Any]] = []
    created_total = 0
    already_known_total = 0
    skipped_low_score_total = 0
    success_count = 0
    failure_count = 0
    source_agent = SourceDiscoveryAgent(db)
    run_config = {**(agent.config or {}), **(config_override or {})}
    for source in sources:
        source_run = await source_agent.run_source(source, config_override=run_config)
        created_total += source_run.created_count
        summary = next((entry for entry in source_run.logs if entry.get("event") == "live_filter_summary"), {})
        already_known_total += int(summary.get("already_known") or 0)
        skipped_low_score_total += int(summary.get("skipped_low_live_score") or 0)
        if source_run.status.value == "success":
            success_count += 1
        else:
            failure_count += 1
        for entry in source_run.logs or []:
            if entry.get("event") in {"skipped_not_live_relevant", "skipped_low_live_score"}:
                logs.append(
                    {
                        **entry,
                        "source_id": source.id,
                        "source": source.name,
                        "status": source_run.status.value,
                    }
                )
        logs.append(
            {
                "source_id": source.id,
                "source": source.name,
                "status": source_run.status.value,
                "fetched": source_run.fetched_count,
                "created": source_run.created_count,
                "already_known": int(summary.get("already_known") or 0),
                "skipped_low_live_score": int(summary.get("skipped_low_live_score") or 0),
                "error": source_run.error_message,
            }
        )
    return _finish_run(
        db,
        run,
        status=AgentRunStatus.FAILED if failure_count else AgentRunStatus.SUCCESS,
        input_count=len(sources),
        output_count=created_total,
        success_count=success_count,
        failure_count=failure_count,
        logs=logs,
        metadata_json={
            "config": run_config,
            "manual_override": bool(config_override),
            "already_known": already_known_total,
            "skipped_low_live_score": skipped_low_score_total,
        },
    )


async def _run_ao_analyzer(db: Session, agent: Agent, run: AgentRun, config_override: dict[str, Any] | None = None) -> AgentRun:
    run_config = {**(agent.config or {}), **(config_override or {})}
    requested_ids = [
        int(opportunity_id)
        for opportunity_id in (run_config.get("opportunity_ids") or [])
        if str(opportunity_id).isdigit()
    ]
    if requested_ids:
        opportunities = db.scalars(
            select(Opportunity)
            .where(
                Opportunity.id.in_(requested_ids),
                Opportunity.source != "fixture",
                Opportunity.status.notin_([OpportunityStatus.ARCHIVED]),
            )
            .order_by(Opportunity.created_at.asc())
        ).all()
    else:
        limit = max(1, int(run_config.get("max_items_per_run") or _int_config(agent, "max_items_per_run", 5)))
        opportunities = db.scalars(
            select(Opportunity)
            .where(
                Opportunity.ai_report.is_(None),
                Opportunity.status.notin_([OpportunityStatus.NOT_RELEVANT, OpportunityStatus.NO_GO, OpportunityStatus.ARCHIVED]),
            )
            .order_by(Opportunity.created_at.asc())
            .limit(limit)
        ).all()
    logs: list[dict[str, Any]] = []
    success_count = 0
    failure_count = 0
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    last_model: str | None = None
    for opportunity in opportunities:
        try:
            await analyze_opportunity(db, opportunity)
            latest_report = db.scalar(
                select(AiReport)
                .where(AiReport.opportunity_id == opportunity.id)
                .order_by(AiReport.created_at.desc())
            )
            usage = extract_token_usage(latest_report.raw_model_json if latest_report else None)
            input_tokens += usage["input_tokens"]
            output_tokens += usage["output_tokens"]
            total_tokens += usage["total_tokens"]
            last_model = latest_report.model if latest_report else last_model
            success_count += 1
            logs.append(
                {
                    "opportunity_id": opportunity.id,
                    "title": opportunity.title,
                    "status": "success",
                    "tokens": usage["total_tokens"],
                    "model": latest_report.model if latest_report else None,
                }
            )
        except Exception as exc:
            db.rollback()
            failure_count += 1
            logs.append({"opportunity_id": opportunity.id, "title": opportunity.title, "status": "failed", "error": str(exc)})
    return _finish_run(
        db,
        run,
        status=AgentRunStatus.FAILED if failure_count else AgentRunStatus.SUCCESS,
        input_count=len(opportunities),
        output_count=success_count,
        success_count=success_count,
        failure_count=failure_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model=last_model,
        logs=logs,
        metadata_json={"config": run_config, "manual_selection": bool(requested_ids)},
    )


async def _run_ao_classifier(db: Session, agent: Agent, run: AgentRun) -> AgentRun:
    limit = max(1, _int_config(agent, "max_items_per_run", 100))
    opportunities = db.scalars(
        select(Opportunity)
        .where(Opportunity.status.in_([OpportunityStatus.ANALYZED, OpportunityStatus.TO_QUALIFY]))
        .order_by(Opportunity.global_score.desc(), Opportunity.deadline.asc())
        .limit(limit)
    ).all()
    strategy = PulseStrategyAgent()
    status_map = {"GO": OpportunityStatus.GO, "WATCH": OpportunityStatus.WATCH, "NO-GO": OpportunityStatus.NO_GO}
    logs: list[dict[str, Any]] = []
    changed = 0
    for opportunity in opportunities:
        recommendation = strategy.recommend(
            type("ScoreProxy", (), {"global_score": opportunity.global_score})()  # lightweight adapter for existing agent
        )
        next_status = status_map[recommendation]
        before = opportunity.status.value
        opportunity.status = next_status
        changed += 1 if before != next_status.value else 0
        logs.append(
            {
                "opportunity_id": opportunity.id,
                "title": opportunity.title,
                "before": before,
                "after": next_status.value,
                "score": opportunity.global_score,
            }
        )
    db.commit()
    return _finish_run(
        db,
        run,
        status=AgentRunStatus.SUCCESS,
        input_count=len(opportunities),
        output_count=changed,
        success_count=len(opportunities),
        logs=logs,
    )


async def _run_alert_dispatcher(db: Session, agent: Agent, run: AgentRun) -> AgentRun:
    deadline_days = max(1, _int_config(agent, "deadline_days", 7))
    now = _now()
    soon = now + timedelta(days=deadline_days)
    high_score = db.scalars(select(Opportunity).where(Opportunity.global_score >= 80)).all()
    deadlines = db.scalars(
        select(Opportunity).where(
            Opportunity.deadline.is_not(None),
            Opportunity.deadline >= now,
            Opportunity.deadline <= soon,
        )
    ).all()

    created = 0
    logs: list[dict[str, Any]] = []

    def add_once(opportunity: Opportunity, *, title: str, message: str, notification_type: NotificationType) -> None:
        nonlocal created
        exists = db.scalar(
            select(func.count(Notification.id)).where(
                Notification.opportunity_id == opportunity.id,
                Notification.title == title,
            )
        )
        if exists:
            return
        db.add(
            Notification(
                type=notification_type,
                title=title,
                message=message,
                opportunity_id=opportunity.id,
                payload={"agent_slug": agent.slug, "score": opportunity.global_score},
            )
        )
        created += 1
        logs.append({"opportunity_id": opportunity.id, "title": opportunity.title, "notification": title})

    for opportunity in high_score:
        add_once(
            opportunity,
            title="Agent alerte: AO très pertinent",
            message=f"{opportunity.title} - score {opportunity.global_score}/100",
            notification_type=NotificationType.HIGH_SCORE,
        )
    for opportunity in deadlines:
        deadline_text = opportunity.deadline.isoformat() if opportunity.deadline else "Non disponible"
        add_once(
            opportunity,
            title="Agent alerte: deadline proche",
            message=f"{opportunity.title} - réponse avant {deadline_text}",
            notification_type=NotificationType.DEADLINE_SOON,
        )
    db.commit()
    return _finish_run(
        db,
        run,
        status=AgentRunStatus.SUCCESS,
        input_count=len(high_score) + len(deadlines),
        output_count=created,
        success_count=created,
        logs=logs,
    )
