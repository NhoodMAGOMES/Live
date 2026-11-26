from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any


def content_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                return None
    return None


def _loads_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _deep_get(payload: dict[str, Any], path: list[str]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _compact_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _structured_context(*values: Any) -> str | None:
    parts: list[str] = []
    for value in values:
        if isinstance(value, dict):
            encoded = json.dumps(value, ensure_ascii=False, default=str)
            if encoded and encoded != "{}":
                parts.append(encoded)
            continue
        if isinstance(value, list):
            parts.extend(_string_list(value))
            continue
        text = str(value).strip() if value is not None else ""
        if text:
            parts.append(text)
    compacted = _compact_text(" ".join(parts))
    return compacted or None


def _cpv_from_donnees(donnees: dict[str, Any]) -> list[str]:
    cpv = _deep_get(donnees, ["OBJET", "CPV"])
    if isinstance(cpv, list):
        return [str(item.get("PRINCIPAL")) for item in cpv if isinstance(item, dict) and item.get("PRINCIPAL")]
    if isinstance(cpv, dict) and cpv.get("PRINCIPAL"):
        return [str(cpv["PRINCIPAL"])]
    return []


def normalize_boamp_record(record: dict[str, Any]) -> dict[str, Any]:
    donnees = _loads_json(record.get("donnees"))
    objet = _deep_get(donnees, ["OBJET", "OBJET_COMPLET"]) or record.get("objet")
    title = _deep_get(donnees, ["OBJET", "TITRE_MARCHE"]) or record.get("objet") or "Avis BOAMP sans titre"
    location = (
        _deep_get(donnees, ["OBJET", "LIEU_EXEC_LIVR", "ADRESSE"])
        or record.get("code_departement_prestation")
        or ", ".join(record.get("code_departement") or [])
    )
    market_type = record.get("type_marche")
    if isinstance(market_type, list):
        market_type = ", ".join(market_type)
    descriptors = _string_list(record.get("descripteur_libelle"))
    department_codes = _string_list(record.get("code_departement")) or _string_list(record.get("code_departement_prestation"))
    market_facets = _string_list(record.get("type_marche_facette"))
    document_context = _structured_context(
        record.get("objet"),
        _deep_get(donnees, ["OBJET", "OBJET_COMPLET"]),
        "Descripteurs BOAMP:",
        descriptors,
        "Nature:",
        record.get("nature_libelle"),
        "Famille:",
        record.get("famille_libelle"),
        "Procedure:",
        record.get("procedure_libelle") or record.get("type_procedure"),
        "Type de marche:",
        market_type,
        market_facets,
        "Departements:",
        department_codes,
        "Criteres:",
        record.get("criteres"),
    )
    return {
        "source": "BOAMP",
        "source_reference": record.get("idweb") or record.get("id"),
        "source_url": record.get("url_avis"),
        "title": title,
        "buyer": record.get("nomacheteur") or _deep_get(donnees, ["IDENTITE", "DENOMINATION"]),
        "buyer_type": record.get("famille_libelle"),
        "object": record.get("objet"),
        "description": objet,
        "lots": [],
        "cpv": _cpv_from_donnees(donnees),
        "procedure": record.get("procedure_libelle") or record.get("type_procedure"),
        "market_type": market_type,
        "location": location,
        "publication_date": parse_datetime(record.get("dateparution")),
        "deadline": parse_datetime(record.get("datelimitereponse")),
        "estimated_budget": None,
        "document_context": document_context,
        "normalized_payload": {
            "boamp": record,
            "donnees": donnees,
            "boamp_structured_context": {
                "descriptors": descriptors,
                "nature": record.get("nature_libelle"),
                "procedure": record.get("procedure_libelle") or record.get("type_procedure"),
                "market_type": market_type,
                "market_facets": market_facets,
                "departments": department_codes,
            },
            "document_context": document_context,
        },
    }


def normalize_manual_notice(payload: dict[str, Any]) -> dict[str, Any]:
    description = payload.get("description") or payload.get("text") or payload.get("content") or ""
    return {
        "source": payload.get("source") or "manual",
        "source_reference": payload.get("source_reference") or payload.get("reference"),
        "source_url": payload.get("source_url") or payload.get("url"),
        "title": payload.get("title") or payload.get("objet") or "AO importé manuellement",
        "buyer": payload.get("buyer") or payload.get("acheteur"),
        "buyer_type": payload.get("buyer_type"),
        "object": payload.get("object") or payload.get("objet"),
        "description": description,
        "lots": payload.get("lots") or [],
        "cpv": payload.get("cpv") or [],
        "procedure": payload.get("procedure"),
        "market_type": payload.get("market_type") or payload.get("type_marche"),
        "location": payload.get("location") or payload.get("localisation"),
        "publication_date": parse_datetime(payload.get("publication_date")),
        "deadline": parse_datetime(payload.get("deadline")),
        "estimated_budget": payload.get("estimated_budget"),
        "normalized_payload": payload,
    }


def _ted_localized(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        values = [str(item).strip() for item in value if str(item).strip()]
        return " / ".join(values) or None
    if not isinstance(value, dict):
        return None
    for language in ("fra", "fre", "eng"):
        localized = _ted_localized(value.get(language))
        if localized:
            return localized
    for localized_value in value.values():
        localized = _ted_localized(localized_value)
        if localized:
            return localized
    return None


def _ted_values(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


def _ted_link(record: dict[str, Any], kind: str = "html") -> str | None:
    links = (record.get("links") or {}).get(kind) or {}
    if isinstance(links, str):
        return links
    if not isinstance(links, dict):
        return None
    for language in ("FRA", "ENG", "MUL"):
        if links.get(language):
            return str(links[language])
    return str(next(iter(links.values()))) if links else None


def _ted_limited(value: str | None, maximum: int = 512) -> str | None:
    if not value or len(value) <= maximum:
        return value
    return f"{value[: maximum - 3].rstrip()}..."


def normalize_ted_record(record: dict[str, Any]) -> dict[str, Any]:
    reference = str(record.get("publication-number") or "").strip()
    title = _ted_localized(record.get("notice-title")) or f"Avis TED {reference}"
    buyer = _ted_localized(record.get("buyer-name"))
    cpv = _ted_values(record.get("classification-cpv"))
    locations = _ted_values(record.get("place-of-performance"))
    market_types = _ted_values(record.get("contract-nature"))
    deadlines = _ted_values(record.get("deadline-receipt-tender-date-lot"))
    deadline = min((parsed for value in deadlines if (parsed := parse_datetime(value))), default=None)
    source_url = _ted_link(record) or (f"https://ted.europa.eu/fr/notice/-/detail/{reference}" if reference else None)
    document_context = _structured_context(
        title,
        "Acheteur:",
        buyer,
        "CPV:",
        cpv,
        "Nature du marché:",
        market_types,
        "Lieux d'exécution:",
        locations,
    )
    return {
        "source": "TED",
        "source_reference": reference or None,
        "source_url": source_url,
        "title": title,
        "buyer": _ted_limited(buyer),
        "buyer_type": None,
        "object": title,
        "description": document_context,
        "lots": [],
        "cpv": cpv,
        "procedure": _ted_localized(record.get("procedure-type")),
        "market_type": ", ".join(market_types) or None,
        "location": _ted_limited(", ".join(locations) or None),
        "publication_date": parse_datetime(record.get("publication-date")),
        "deadline": deadline,
        "estimated_budget": None,
        "document_context": document_context,
        "normalized_payload": {
            "ted": record,
            "document_context": document_context,
            "document_links": {
                "html": source_url,
                "pdf": _ted_link(record, "pdf"),
                "xml": _ted_link(record, "xml"),
            },
        },
    }
