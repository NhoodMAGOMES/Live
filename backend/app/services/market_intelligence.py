from __future__ import annotations

import re
from typing import Any

import httpx

from app.services.scoring import ScoreResult


BOAMP_RECORDS_URL = "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records"
DECP_RECORDS_URL = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/decp_augmente/records"
MAX_TERMS = 4


def _compact(value: Any, limit: int = 280) -> str | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value if item not in (None, ""))
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:limit] if text else None


def _clean_term(value: Any) -> str | None:
    text = _compact(value, 90)
    if not text:
        return None
    text = text.replace('"', "").strip()
    if len(text) < 4:
        return None
    return text


def _fallback_title_terms(opportunity: dict[str, Any]) -> list[str]:
    text = _compact(opportunity.get("title") or opportunity.get("object"), 180) or ""
    chunks = re.split(r"[-–—:;,()/]", text)
    return [chunk.strip() for chunk in chunks if len(chunk.strip()) >= 12][:2]


def market_search_terms(opportunity: dict[str, Any], score: ScoreResult) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for match in score.matched_keywords:
        for value in (match.keyword, match.matched_term):
            term = _clean_term(value)
            key = term.casefold() if term else ""
            if term and key not in seen:
                seen.add(key)
                terms.append(term)
    for term in _fallback_title_terms(opportunity):
        clean = _clean_term(term)
        key = clean.casefold() if clean else ""
        if clean and key not in seen:
            seen.add(key)
            terms.append(clean)
    return terms[:MAX_TERMS]


def _search_clause(terms: list[str]) -> str:
    return "(" + " OR ".join(f'search("{term}")' for term in terms) + ")"


def _boamp_item(record: dict[str, Any], query: str) -> dict[str, Any]:
    return {
        "query": query,
        "source": "BOAMP",
        "title": _compact(record.get("objet")),
        "buyer": _compact(record.get("nomacheteur")),
        "published_at": _compact(record.get("dateparution")),
        "notice_type": _compact(record.get("nature_libelle")),
        "procedure": _compact(record.get("procedure_libelle")),
        "holders": _compact(record.get("titulaire")),
        "criteria": _compact(record.get("criteres"), 500),
        "url": _compact(record.get("url_avis"), 500),
    }


def _decp_item(record: dict[str, Any], query: str) -> dict[str, Any]:
    holders = [
        record.get("denominationsocialeetablissement"),
        record.get("denominationunitelegale"),
        record.get("denominationsociale_cotitulaire1"),
        record.get("denominationsociale_cotitulaire2"),
        record.get("denominationsociale_cotitulaire3"),
    ]
    return {
        "query": query,
        "source": "Données essentielles de la commande publique",
        "title": _compact(record.get("objetmarche")),
        "buyer": _compact(record.get("nomacheteur")),
        "notified_at": _compact(record.get("datenotification")),
        "amount": record.get("montant"),
        "duration_months": record.get("dureemois"),
        "procedure": _compact(record.get("procedure")),
        "cpv": _compact(record.get("codecpv") or record.get("referencecpv")),
        "holders": _compact([holder for holder in holders if holder]),
    }


def _error_text(exc: Exception) -> str:
    return str(exc) or exc.__class__.__name__


async def collect_market_intelligence(opportunity: dict[str, Any], score: ScoreResult, *, timeout: float = 15.0) -> dict[str, Any]:
    terms = market_search_terms(opportunity, score)
    context: dict[str, Any] = {
        "queries": terms,
        "boamp_results": [],
        "public_awards": [],
        "limitations": [],
    }
    if not terms:
        context["limitations"].append("Aucun mot-clé assez discriminant pour chercher des AO comparables publics.")
        return context

    query_label = ", ".join(terms)
    search_clause = _search_clause(terms)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(
                BOAMP_RECORDS_URL,
                params={
                    "select": "idweb,url_avis,dateparution,nature_libelle,procedure_libelle,titulaire,criteres,objet,nomacheteur",
                    "where": f"{search_clause} AND titulaire is not null",
                    "order_by": "-dateparution",
                    "limit": 8,
                },
            )
            response.raise_for_status()
            for record in response.json().get("results", []):
                context["boamp_results"].append(_boamp_item(record, query_label))
        except Exception as exc:  # pragma: no cover - public data availability varies
            context["limitations"].append(f"Recherche BOAMP indisponible: {_error_text(exc)}")

        try:
            response = await client.get(
                DECP_RECORDS_URL,
                params={
                    "select": "id,objetmarche,nomacheteur,datenotification,montant,dureemois,procedure,codecpv,referencecpv,denominationsocialeetablissement,denominationunitelegale,denominationsociale_cotitulaire1,denominationsociale_cotitulaire2,denominationsociale_cotitulaire3",
                    "where": f"{search_clause} AND montant is not null",
                    "order_by": "-datenotification",
                    "limit": 8,
                },
            )
            response.raise_for_status()
            for record in response.json().get("results", []):
                context["public_awards"].append(_decp_item(record, query_label))
        except Exception as exc:  # pragma: no cover - public data availability varies
            context["limitations"].append(f"Recherche données essentielles indisponible: {_error_text(exc)}")

    context["boamp_results"] = context["boamp_results"][:8]
    context["public_awards"] = context["public_awards"][:8]
    if not context["boamp_results"] and not context["public_awards"]:
        context["limitations"].append("Aucun résultat public comparable trouvé automatiquement.")
    return context
