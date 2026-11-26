from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors import connector_for
from app.models import Opportunity, OpportunityStatus, Source, SourceRun, SourceRunStatus
from app.services.opportunities import create_opportunity_from_notice, load_keyword_configs
from app.services.scoring import LIVE_PREFILTER_MIN_SCORE, ScoreResult, prequalification_result, score_opportunity


class SourceDiscoveryAgent:
    def __init__(self, db: Session) -> None:
        self.db = db

    async def run_source(self, source: Source, config_override: dict[str, Any] | None = None) -> SourceRun:
        run = SourceRun(source_id=source.id, status=SourceRunStatus.RUNNING, logs=[])
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        run_id = run.id
        run_started = perf_counter()
        try:
            connector = connector_for(source.connector_type)
            runtime_config = {**(source.config or {}), **(config_override or {})}
            runtime_source = SimpleNamespace(
                id=source.id,
                name=source.name,
                connector_type=source.connector_type,
                url=source.url,
                api_endpoint=source.api_endpoint,
                config=runtime_config,
            )
            fetch_started = perf_counter()
            result = await connector.fetch(runtime_source)  # type: ignore[arg-type]
            fetch_seconds = perf_counter() - fetch_started
            processing_started = perf_counter()
            created = 0
            already_known = 0
            rejected_count = 0
            rejected_created = 0
            rejection_logs: list[dict[str, Any]] = []
            prequalification_enabled = runtime_config.get("prequalification_enabled", True) is not False
            min_live_score = runtime_config.get("min_live_score")
            keyword_configs = load_keyword_configs(self.db) if prequalification_enabled else []
            min_live_score_value = max(float(min_live_score or LIVE_PREFILTER_MIN_SCORE), LIVE_PREFILTER_MIN_SCORE)
            notice_references = [notice.source_reference for notice in result.notices if notice.source_reference]
            notice_sources = {
                str(notice.normalized.get("source") or source.name)
                for notice in result.notices
            }
            known_keys = {
                (str(source_name), str(source_reference))
                for source_name, source_reference in self.db.execute(
                    select(Opportunity.source, Opportunity.source_reference).where(
                        Opportunity.source.in_(notice_sources),
                        Opportunity.source_reference.in_(notice_references),
                    )
                ).all()
                if source_reference
            } if notice_references and notice_sources else set()
            for notice in result.notices:
                notice_key = (str(notice.normalized.get("source") or source.name), str(notice.source_reference))
                if notice.source_reference and notice_key in known_keys:
                    already_known += 1
                    continue
                prequalification_score: ScoreResult | None = None
                rejection_reason: str | None = None
                if prequalification_enabled:
                    prequalification_score = score_opportunity(notice.normalized, keyword_configs)
                    qualified, reason = prequalification_result(prequalification_score, minimum_score=min_live_score_value)
                    rejection_reason = None if qualified else reason
                opportunity, is_created = create_opportunity_from_notice(self.db, source, notice)
                if prequalification_score:
                    _apply_prequalification_score(opportunity, prequalification_score, rejected_reason=rejection_reason)
                    self.db.add(opportunity)
                if rejection_reason:
                    rejected_count += 1
                    rejected_created += 1 if is_created else 0
                    event = "skipped_low_live_score" if rejection_reason.startswith("score_insuffisant") else "skipped_not_live_relevant"
                    rejection_logs.append(
                        {
                            "event": event,
                            "source_reference": notice.source_reference,
                            "opportunity_id": opportunity.id,
                            "title": opportunity.title,
                            "score": prequalification_score.global_score if prequalification_score else 0,
                            "reason": rejection_reason,
                        }
                    )
                created += 1 if is_created else 0
                already_known += 0 if is_created else 1
                if notice.source_reference:
                    known_keys.add(notice_key)
            run.status = SourceRunStatus.SUCCESS
            run.fetched_count = len(result.notices)
            run.created_count = created
            run.logs = [
                *result.logs,
                *rejection_logs,
                {
                    "event": "live_filter_summary",
                    "created": created,
                    "already_known": already_known,
                    "skipped_low_live_score": rejected_count,
                    "rejected_created": rejected_created,
                    "min_live_score": min_live_score_value if prequalification_enabled else None,
                    "prequalification_enabled": prequalification_enabled,
                    "filter_mode": "prequalification",
                    "keywords": runtime_config.get("keywords") or [],
                    "days_back": runtime_config.get("days_back"),
                    "limit": runtime_config.get("limit"),
                },
                {
                    "event": "performance_summary",
                    "fetch_seconds": round(fetch_seconds, 3),
                    "processing_seconds": round(perf_counter() - processing_started, 3),
                    "total_seconds": round(perf_counter() - run_started, 3),
                },
            ]
            run.finished_at = datetime.now(timezone.utc)
            source.last_run_at = run.finished_at
            self.db.commit()
            self.db.refresh(run)
            return run
        except Exception as exc:
            self.db.rollback()
            run = self.db.get(SourceRun, run_id) or run
            run.status = SourceRunStatus.FAILED
            run.error_message = str(exc)
            run.finished_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(run)
            return run


def _rejection_summary(score: ScoreResult, reason: str) -> str:
    if reason.startswith("score_insuffisant"):
        label = "score inférieur au seuil LIVE"
    elif reason.startswith("hors_enjeux_live"):
        label = "objet hors enjeux LIVE"
    else:
        label = "préqualification LIVE négative"
    details = [str(malus.get("details")) for malus in score.maluses if malus.get("details")]
    detail_text = f" {details[0]}" if details else ""
    return f"Écarté par IA: {label}. Score LIVE {score.global_score}/100.{detail_text}"


def _apply_prequalification_score(opportunity: Opportunity, score: ScoreResult, rejected_reason: str | None = None) -> None:
    opportunity.global_score = score.global_score
    opportunity.score_by_family = score.score_by_family
    opportunity.keyword_traces = [match.__dict__ for match in score.matched_keywords]
    payload = dict(opportunity.normalized_payload or {})
    payload["live_prequalification"] = {
        "qualified": rejected_reason is None,
        "reason": rejected_reason,
        "score": score.global_score,
        "decision": score.decision,
        "live_core_hits": score.breakdown.get("live_core_hits") or [],
        "noise_hits": score.breakdown.get("noise_hits") or [],
    }
    opportunity.normalized_payload = payload
    if rejected_reason:
        if opportunity.status not in {OpportunityStatus.GO, OpportunityStatus.WATCH, OpportunityStatus.NO_GO, OpportunityStatus.ARCHIVED}:
            opportunity.status = OpportunityStatus.NOT_RELEVANT
            opportunity.ai_summary = _rejection_summary(score, rejected_reason)
        return
    if opportunity.status == OpportunityStatus.NOT_RELEVANT:
        opportunity.status = OpportunityStatus.NEW
        opportunity.ai_summary = None
