import asyncio

from sqlalchemy import select

from app.agents.source_discovery import SourceDiscoveryAgent
from app.db.session import SessionLocal
from app.models import Source
from app.schemas import FrontAnalysisRequest
from app.services.agent_orchestrator import run_agent, run_scheduled_agents
from app.services.frontoffice_analysis import execute_frontoffice_analysis
from app.worker import celery_app


@celery_app.task(name="app.tasks.run_source")
def run_source(source_id: int) -> dict:
    async def _run() -> dict:
        with SessionLocal() as db:
            source = db.get(Source, source_id)
            if not source:
                return {"status": "not_found", "source_id": source_id}
            run = await SourceDiscoveryAgent(db).run_source(source)
            return {
                "source_run_id": run.id,
                "status": run.status.value,
                "fetched_count": run.fetched_count,
                "created_count": run.created_count,
                "error": run.error_message,
            }

    return asyncio.run(_run())


@celery_app.task(name="app.tasks.run_frontoffice_analysis")
def run_frontoffice_analysis_task(payload: dict) -> dict:
    async def _run() -> dict:
        with SessionLocal() as db:
            request = FrontAnalysisRequest.model_validate(payload)
            return await execute_frontoffice_analysis(db, request)

    return asyncio.run(_run())


@celery_app.task(name="app.tasks.discover_active_sources")
def discover_active_sources() -> list[dict]:
    async def _run_all() -> list[dict]:
        with SessionLocal() as db:
            run = await run_agent(db, "source_discovery")
            return [{"agent": "source_discovery", "status": run.status.value, "created_count": run.output_count}]

    return asyncio.run(_run_all())


@celery_app.task(name="app.tasks.run_agent")
def run_agent_task(slug: str) -> dict:
    async def _run() -> dict:
        with SessionLocal() as db:
            run = await run_agent(db, slug)
            return {
                "agent": slug,
                "status": run.status.value,
                "input_count": run.input_count,
                "output_count": run.output_count,
                "total_tokens": run.total_tokens,
            }

    return asyncio.run(_run())


@celery_app.task(name="app.tasks.run_scheduled_agents")
def run_scheduled_agents_task() -> list[dict]:
    async def _run() -> list[dict]:
        with SessionLocal() as db:
            runs = await run_scheduled_agents(db)
            return [
                {
                    "agent_id": run.agent_id,
                    "status": run.status.value,
                    "input_count": run.input_count,
                    "output_count": run.output_count,
                    "total_tokens": run.total_tokens,
                }
                for run in runs
            ]

    return asyncio.run(_run())
