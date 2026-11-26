from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from app.connectors.base import ConnectorNotice, ConnectorRunResult
from app.connectors.boamp import LIVE_QUERY_GROUPS, _clean_terms
from app.core.config import get_settings
from app.models import Source
from app.services.normalization import normalize_ted_record


TED_FIELDS = [
    "publication-number",
    "publication-date",
    "notice-title",
    "buyer-name",
    "buyer-country",
    "classification-cpv",
    "contract-nature",
    "deadline-receipt-tender-date-lot",
    "place-of-performance",
    "procedure-type",
]
MAX_RESULT_LIMIT = 1000
MAX_TERMS_PER_QUERY = 8
MAX_RETRY_DELAY_SECONDS = 15.0


def _ted_term(value: str) -> str:
    return value.replace('"', "").strip()


class TEDConnector:
    """Official, anonymous TED Search API connector for active EU notices."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def _date_from(self, config: dict[str, Any]) -> date:
        analysis_date = config.get("analysis_date")
        end_date = date.fromisoformat(str(analysis_date)[:10]) if analysis_date else datetime.now(timezone.utc).date()
        return end_date - timedelta(days=max(1, int(config.get("days_back") or 14)) - 1)

    def _query_groups(self, config: dict[str, Any]) -> list[list[str]]:
        groups: list[list[str]] = []
        configured = _clean_terms(config.get("keywords"))
        if configured:
            groups.append(configured)
        if config.get("use_live_query_expansion", True) is not False:
            groups.extend(LIVE_QUERY_GROUPS)
        unique: list[list[str]] = []
        seen: set[tuple[str, ...]] = set()
        for group in groups:
            clean = [_ted_term(term) for term in group if _ted_term(term)][:MAX_TERMS_PER_QUERY]
            key = tuple(term.casefold() for term in clean)
            if clean and key not in seen:
                seen.add(key)
                unique.append(clean)
        return unique

    def _query(self, config: dict[str, Any], terms: list[str]) -> str:
        country = str(config.get("buyer_country") or "FRA").upper()
        since = self._date_from(config).strftime("%Y%m%d")
        term_query = " OR ".join(f'FT~"{term}"' if " " in term else f"FT~{term}" for term in terms)
        return f"buyer-country={country} AND publication-date>={since} AND ({term_query}) SORT BY publication-date DESC"

    async def _post_search(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        body: dict[str, Any],
        max_attempts: int,
    ) -> httpx.Response:
        for attempt in range(1, max_attempts + 1):
            response = await client.post(endpoint, json=body)
            if response.status_code != 429 or attempt == max_attempts:
                response.raise_for_status()
                return response
            retry_after = response.headers.get("Retry-After")
            try:
                delay = min(MAX_RETRY_DELAY_SECONDS, float(retry_after)) if retry_after else min(MAX_RETRY_DELAY_SECONDS, 1.5 * attempt)
            except ValueError:
                delay = min(MAX_RETRY_DELAY_SECONDS, 1.5 * attempt)
            await asyncio.sleep(max(0.5, delay))
        raise RuntimeError("La recherche TED n'a pas pu être exécutée")

    async def fetch(self, source: Source) -> ConnectorRunResult:
        settings = get_settings()
        endpoint = source.api_endpoint or settings.ted_api_base_url
        config = source.config or {}
        limit = min(MAX_RESULT_LIMIT, max(1, int(config.get("limit") or 300)))
        page_size = min(250, max(1, int(config.get("page_size") or 100)))
        groups = self._query_groups(config)
        if not groups:
            raise ValueError("TED nécessite au moins un mot-clé de recherche")

        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        request_delay = max(0.0, float(config.get("request_delay_seconds") or 0.5))
        max_attempts = min(8, max(1, int(config.get("rate_limit_retries") or 5)))
        logs: list[dict[str, Any]] = [{"event": "query_plan", "endpoint": endpoint, "query_count": len(groups), "limit": limit}]
        verify_ssl = bool(config.get("verify_ssl", True))
        async with httpx.AsyncClient(timeout=self.timeout, verify=verify_ssl) as client:
            for query_index, terms in enumerate(groups, start=1):
                page = 1
                query = self._query(config, terms)
                while len(records) < limit:
                    body = {
                        "query": query,
                        "fields": TED_FIELDS,
                        "page": page,
                        "limit": min(page_size, limit - len(records)),
                        "scope": str(config.get("scope") or "ACTIVE").upper(),
                        "checkQuerySyntax": False,
                        "paginationMode": "PAGE_NUMBER",
                        "onlyLatestVersions": True,
                    }
                    response = await self._post_search(client, endpoint, body, max_attempts=max_attempts)
                    payload = response.json()
                    if payload.get("timedOut"):
                        raise RuntimeError("La recherche TED a expiré")
                    page_records = payload.get("notices") or []
                    added = 0
                    for record in page_records:
                        reference = str(record.get("publication-number") or "")
                        if not reference or reference in seen:
                            continue
                        seen.add(reference)
                        records.append(record)
                        added += 1
                    logs.append({
                        "event": "page",
                        "query_index": query_index,
                        "page": page,
                        "returned": len(page_records),
                        "unique_added": added,
                        "total_count": payload.get("totalNoticeCount"),
                    })
                    if not page_records or len(page_records) < body["limit"]:
                        break
                    page += 1
                    if request_delay:
                        await asyncio.sleep(request_delay)
                if len(records) >= limit:
                    break
                if request_delay:
                    await asyncio.sleep(request_delay)

        notices = []
        for record in records:
            normalized = normalize_ted_record(record)
            notices.append(ConnectorNotice(
                source_reference=normalized["source_reference"],
                source_url=normalized["source_url"],
                payload=record,
                normalized=normalized,
                raw_text=normalized.get("document_context") or normalized["title"],
            ))
        logs.append({"event": "completed", "fetched": len(notices), "unique_references": len(seen)})
        return ConnectorRunResult(notices=notices, logs=logs)
