from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only

from app.models import Agent, Opportunity, OpportunityStatus
from app.schemas import FrontAnalysisRequest, OpportunityListItem
from app.services.agent_orchestrator import ensure_default_agents, run_agent


DEFAULT_LIVE_KEYWORDS = [
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
    "spectacle vivant",
    "activation de lieu",
    "commercialisation d'espaces",
    "concession culturelle",
    "DSP culturelle",
    "appel à projets culturel",
]

SUMMARY_COLUMNS = (
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


def _agent_keywords(agent: Agent | None) -> list[str]:
    configured = (agent.config or {}).get("keywords") if agent else None
    if isinstance(configured, list):
        keywords = [str(keyword).strip() for keyword in configured if str(keyword).strip()]
        seen = {keyword.casefold() for keyword in keywords}
        for keyword in DEFAULT_LIVE_KEYWORDS:
            if keyword.casefold() not in seen:
                keywords.append(keyword)
                seen.add(keyword.casefold())
        return keywords
    return DEFAULT_LIVE_KEYWORDS


async def execute_frontoffice_analysis(db: Session, payload: FrontAnalysisRequest) -> dict:
    ensure_default_agents(db)
    analysis_date = payload.analysis_date or date.today()
    source_agent = db.scalar(select(Agent).where(Agent.slug == "source_discovery"))
    keywords = payload.keywords or _agent_keywords(source_agent)
    latest_opportunity_id = db.scalar(select(func.coalesce(func.max(Opportunity.id), 0))) or 0

    discovery_run = await run_agent(
        db,
        "source_discovery",
        config_override={
            "analysis_date": analysis_date.isoformat(),
            "days_back": payload.days_back,
            "keywords": keywords,
            "departments": payload.departments,
            "limit": payload.limit,
            "min_live_score": payload.min_live_score,
        },
    )

    hidden_statuses = [OpportunityStatus.NOT_RELEVANT, OpportunityStatus.NO_GO, OpportunityStatus.ARCHIVED]
    new_opportunities = list(
        db.scalars(
            select(Opportunity)
            .options(load_only(*SUMMARY_COLUMNS))
            .where(Opportunity.id > latest_opportunity_id, Opportunity.status.notin_(hidden_statuses))
            .order_by(Opportunity.created_at.desc())
        ).all()
    )

    logs = discovery_run.logs or []
    metadata = discovery_run.metadata_json or {}
    rejected_candidates = [
        {
            "source": str(log.get("source") or "BOAMP"),
            "source_reference": log.get("source_reference"),
            "opportunity_id": log.get("opportunity_id"),
            "title": log.get("title"),
            "score": float(log.get("score") or 0),
            "reason": log.get("reason"),
        }
        for log in logs
        if log.get("event") in {"skipped_not_live_relevant", "skipped_low_live_score"}
    ][:12]

    return {
        "analysis_date": analysis_date.isoformat(),
        "days_back": payload.days_back,
        "status": discovery_run.status.value,
        "fetched_count": sum(int(log.get("fetched") or 0) for log in logs),
        "new_count": len(new_opportunities),
        "already_known_count": int(metadata.get("already_known") or 0),
        "skipped_low_score_count": int(metadata.get("skipped_low_live_score") or 0),
        "analyzed_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "run_id": discovery_run.id,
        "new_opportunities": [
            OpportunityListItem.model_validate(opportunity).model_dump(mode="json") for opportunity in new_opportunities
        ],
        "rejected_candidates": rejected_candidates,
    }
