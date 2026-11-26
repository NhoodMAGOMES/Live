from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from app.connectors.base import ConnectorNotice, ConnectorRunResult
from app.core.config import get_settings
from app.models import Source
from app.services.normalization import normalize_boamp_record


BOAMP_PAGE_LIMIT = 100
DEFAULT_RESULT_LIMIT = 300
MAX_RESULT_LIMIT = 1000
MAX_TERMS_PER_QUERY = 8

LIVE_QUERY_GROUPS: list[list[str]] = [
    [
        "AMO",
        "assistance à maîtrise d'ouvrage",
        "prestation intellectuelle",
        "marché de prestation intellectuelle",
        "mission de conseil",
        "mission d'étude",
        "étude de faisabilité",
        "étude de potentiel",
    ],
    [
        "programmation culturelle",
        "programmation artistique",
        "équipement culturel",
        "lieu culturel",
        "espaces d'exposition",
        "médiation culturelle",
        "spectacle vivant",
        "scénographie",
    ],
    [
        "valorisation patrimoniale",
        "valorisation de lieu",
        "transformation d'édifice",
        "reconversion de site",
        "activation de lieu",
        "destination culturelle",
        "tiers-lieu",
        "occupation temporaire",
    ],
    [
        "exploitation de site",
        "gestion de lieu",
        "opérateur de lieu",
        "concession culturelle",
        "DSP culturelle",
        "appel à projets culturel",
        "délégation de service public",
        "convention d'occupation",
    ],
    [
        "commercialisation d'espaces",
        "régie publicitaire",
        "affichage",
        "naming",
        "sponsoring",
        "mécénat",
        "partenariat événementiel",
        "revenus additionnels",
    ],
    [
        "accueil public",
        "séminaire",
        "congrès",
        "réceptif",
        "tourisme d'affaires",
        "hospitality",
        "MICE",
        "restauration événementielle",
    ],
]


def _clean_term(value: Any) -> str:
    return str(value).replace('"', "").strip()


def _clean_terms(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    terms: list[str] = []
    seen: set[str] = set()
    for value in values:
        term = _clean_term(value)
        key = term.casefold()
        if term and key not in seen:
            seen.add(key)
            terms.append(term)
    return terms


class BOAMPConnector:
    """BOAMP via DILA/Opendatasoft Explore API.

    The endpoint is configurable because Opendatasoft versions can evolve.
    Official public base used by default:
    https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records
    """

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def _search_clause(self, terms: list[str]) -> str | None:
        clean_terms = _clean_terms(terms)
        if not clean_terms:
            return None
        search_terms = " OR ".join(f'search("{term}")' for term in clean_terms[:MAX_TERMS_PER_QUERY])
        return f"({search_terms})"

    def _base_filters(self, config: dict[str, Any]) -> list[str]:
        clauses: list[str] = []
        analysis_date = config.get("analysis_date")
        if analysis_date:
            safe_date = str(analysis_date)[:10]
            days_back = max(1, int(config.get("days_back") or 1))
            end_date = date.fromisoformat(safe_date)
            if days_back > 1:
                start_date = end_date - timedelta(days=days_back - 1)
                clauses.append(f"dateparution >= date'{start_date.isoformat()}'")
                clauses.append(f"dateparution <= date'{end_date.isoformat()}'")
            else:
                clauses.append(f"dateparution = date'{safe_date}'")
        days_back = config.get("days_back")
        if days_back and not analysis_date:
            since = (datetime.now(timezone.utc) - timedelta(days=int(days_back))).date().isoformat()
            clauses.append(f"dateparution >= date'{since}'")
        buyers = _clean_terms(config.get("buyers"))
        if buyers:
            buyer_terms = " OR ".join(f'search(nomacheteur,"{buyer}")' for buyer in buyers[:5])
            clauses.append(f"({buyer_terms})")
        departments = _clean_terms(config.get("departments"))
        if departments:
            dept_terms = ", ".join(f'"{dept}"' for dept in departments)
            clauses.append(f"(code_departement_prestation in ({dept_terms}) OR code_departement in ({dept_terms}))")
        return clauses

    def _query_groups(self, config: dict[str, Any]) -> list[list[str]]:
        groups: list[list[str]] = []
        configured_groups = config.get("query_groups") or config.get("keyword_groups")
        if isinstance(configured_groups, list):
            for group in configured_groups:
                terms = group.get("terms") or group.get("keywords") if isinstance(group, dict) else group
                clean_group = _clean_terms(terms)
                if clean_group:
                    groups.append(clean_group)

        configured_keywords = _clean_terms(config.get("keywords"))
        if configured_keywords:
            groups.insert(0, configured_keywords)

        if config.get("use_live_query_expansion", True) is not False:
            groups.extend(LIVE_QUERY_GROUPS)

        unique_groups: list[list[str]] = []
        seen_clauses: set[str] = set()
        for group in groups:
            clause = self._search_clause(group)
            if clause and clause not in seen_clauses:
                seen_clauses.add(clause)
                unique_groups.append(group)
        return unique_groups

    def _where_clauses(self, config: dict[str, Any]) -> list[str | None]:
        base_filters = self._base_filters(config)
        search_clauses = [self._search_clause(group) for group in self._query_groups(config)]
        search_clauses = [clause for clause in search_clauses if clause]
        if not search_clauses:
            return [" AND ".join(base_filters) if base_filters else None]
        clauses = []
        for search_clause in search_clauses:
            combined = [search_clause, *base_filters]
            clauses.append(" AND ".join(combined))
        return clauses

    def _where(self, config: dict[str, Any]) -> str | None:
        return self._where_clauses(config)[0]

    async def fetch(self, source: Source) -> ConnectorRunResult:
        settings = get_settings()
        endpoint = source.api_endpoint or settings.boamp_api_base_url
        config = source.config or {}
        limit = min(MAX_RESULT_LIMIT, max(1, int(config.get("limit", DEFAULT_RESULT_LIMIT))))
        if config.get("use_live_query_expansion", True) is not False and not config.get("strict_limit"):
            limit = min(MAX_RESULT_LIMIT, max(limit, DEFAULT_RESULT_LIMIT))
        page_size = min(BOAMP_PAGE_LIMIT, max(1, int(config.get("page_size", BOAMP_PAGE_LIMIT))))
        where_clauses = self._where_clauses(config)
        if config.get("per_query_limit"):
            per_query_limit = min(limit, max(1, int(config["per_query_limit"])))
        else:
            per_query_limit = min(limit, max(1, (limit + len(where_clauses) - 1) // len(where_clauses)))

        logs = [
            {
                "event": "query_plan",
                "endpoint": endpoint,
                "query_count": len(where_clauses),
                "limit": limit,
                "per_query_limit": per_query_limit,
            }
        ]
        verify_ssl = bool(config.get("verify_ssl", True))
        records: list[dict[str, Any]] = []
        seen_references: set[str] = set()
        async with httpx.AsyncClient(timeout=self.timeout, verify=verify_ssl) as client:
            for query_index, where in enumerate(where_clauses, start=1):
                params: dict[str, Any] = {"limit": min(page_size, per_query_limit), "order_by": "-dateparution"}
                if where:
                    params["where"] = where
                logs.append({"event": "request", "query_index": query_index, "params": params})
                query_seen = 0
                total_count: int | None = None
                while query_seen < per_query_limit and len(records) < limit:
                    page_params = {
                        **params,
                        "limit": min(page_size, per_query_limit - query_seen, limit - len(records)),
                    }
                    if query_seen:
                        page_params["offset"] = query_seen
                    response = await client.get(endpoint, params=page_params)
                    response.raise_for_status()
                    payload = response.json()
                    if total_count is None:
                        total_count = int(payload.get("total_count") or 0)
                    page_records = payload.get("results", [])
                    query_seen += len(page_records)
                    unique_added = 0
                    for record in page_records:
                        reference = str(record.get("idweb") or record.get("id") or record.get("url_avis") or "")
                        if not reference:
                            reference = f"{record.get('dateparution')}::{record.get('objet')}"
                        if reference in seen_references:
                            continue
                        seen_references.add(reference)
                        records.append(record)
                        unique_added += 1
                    logs.append(
                        {
                            "event": "page",
                            "query_index": query_index,
                            "offset": page_params.get("offset", 0),
                            "returned": len(page_records),
                            "unique_added": unique_added,
                            "total_count": total_count,
                        }
                    )
                    if not page_records or query_seen >= total_count:
                        break
                logs.append(
                    {
                        "event": "query_complete",
                        "query_index": query_index,
                        "seen": query_seen,
                        "unique_total": len(records),
                    }
                )
                if len(records) >= limit:
                    break
        notices = [
            ConnectorNotice(
                source_reference=record.get("idweb") or record.get("id"),
                source_url=record.get("url_avis"),
                payload=record,
                normalized=normalize_boamp_record(record),
                raw_text=str(record.get("donnees") or record.get("objet") or ""),
            )
            for record in records
        ]
        logs.append({"event": "response", "returned": len(notices), "limit": limit, "query_count": len(where_clauses)})
        return ConnectorRunResult(notices=notices, logs=logs)
