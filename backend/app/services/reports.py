from __future__ import annotations

import json
from datetime import datetime
from html import escape
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings
from app.services.scoring import ScoreResult, label_from_score


class ReportSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    content: list[str]
    evidence: list[str]


class StructuredReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: ReportSection
    detection_reason: ReportSection
    pulse_relevance: ReportSection
    business_analysis: ReportSection
    local_event_trends: ReportSection
    market_positioning: ReportSection
    recommended_approach: ReportSection
    conclusion: ReportSection
    confidence_score: float
    human_review_required: bool
    llm_notice: str


def missing(value: Any) -> Any:
    return value if value not in (None, "", [], {}) else "Non disponible"


def build_heuristic_report(opportunity: dict[str, Any], score: ScoreResult) -> StructuredReport:
    matched = score.matched_keywords[:12]
    excerpts = [match.excerpt for match in matched if match.excerpt]
    title = missing(opportunity.get("title"))
    source = missing(opportunity.get("source"))
    buyer = missing(opportunity.get("buyer"))
    location = missing(opportunity.get("location"))
    deadline = opportunity.get("deadline")
    deadline_text = deadline.isoformat() if isinstance(deadline, datetime) else missing(deadline)

    executive = ReportSection(
        title="Synthèse exécutive",
        content=[
            f"Titre AO: {title}",
            f"Source: {source}",
            f"Acheteur: {buyer}",
            f"Date limite: {deadline_text}",
            f"Score global: {score.global_score}/100 - {label_from_score(score.global_score)}",
            "Analyse IA avancée indisponible : clé LLM manquante.",
        ],
        evidence=excerpts[:3],
    )
    detection = ReportSection(
        title="Pourquoi l'AO a été détecté",
        content=[
            f"Familles détectées: {', '.join(score.score_by_family.keys()) or 'Non disponible'}",
            f"Mots-clés détectés: {', '.join(sorted({m.keyword for m in matched})) or 'Non disponible'}",
        ],
        evidence=excerpts,
    )
    pulse = ReportSection(
        title="Analyse de pertinence Pulse LIVE",
        content=[
            "Pertinence estimée à partir des axes Pulse LIVE: immobilier opéré, valorisation d'actif, programmation, hospitality/MICE, médias de lieu, exploitation et revenus additionnels.",
            f"Score sémantique: {score.breakdown.get('semantic_relevance', 0)}/20.",
        ],
        evidence=excerpts[:5],
    )
    business = ReportSection(
        title="Analyse business",
        content=[
            f"Potentiel business: {score.breakdown.get('business_potential', 0)}/15.",
            f"Complexité/faisabilité: {score.breakdown.get('feasibility', 0)}/10.",
            "Budget estimé: Non disponible" if not opportunity.get("estimated_budget") else f"Budget estimé: {opportunity['estimated_budget']}",
            "Documents manquants à vérifier par un analyste.",
        ],
        evidence=excerpts[:4],
    )
    local_trends = ReportSection(
        title="Analyse locale événementielle",
        content=[
            f"Territoire à analyser: {location}.",
            "Tendances locales IA: information à enrichir avec les données publiques, agendas culturels, fréquentation des lieux et retours habitants.",
            "Lecture probable: privilégier une programmation hybride mêlant événements grand public, usages quotidiens du lieu, offres familiales, temps forts culturels et activation commerciale mesurable.",
            "Ce que l'équipe doit vérifier: événements déjà organisés localement, saisonnalité, publics dominants, attentes des commerçants, contraintes riverains et partenaires culturels mobilisables.",
        ],
        evidence=excerpts[:4],
    )
    market_positioning = ReportSection(
        title="Positionnement marché et AO comparables",
        content=[
            "AO comparables passés: Non disponible dans les preuves fournies.",
            "Attributaires ou confrères identifiés: Non disponible.",
            "Ordres de grandeur financiers publics: Non disponible.",
            "Critères de jugement ou note technique observés sur des dossiers similaires: Non disponible.",
            "À enrichir via BOAMP, avis d'attribution, données essentielles de marchés publics et profils acheteurs avant une étude réponse.",
        ],
        evidence=[],
    )
    approach = ReportSection(
        title="Approche recommandée",
        content=[
            "Angle LIVE: valoriser l'actif par l'usage, l'événementiel, la programmation et la création de revenus additionnels.",
            "Mobiliser selon besoin: direction LIVE, programmation, exploitation, marketing, property/asset management et partenaires spécialisés.",
            "Prochaines actions sous 48h: lire les pièces, confirmer l'éligibilité, identifier le décideur, cadrer GO/WATCH/NO-GO avec les preuves.",
        ],
        evidence=excerpts[:3],
    )
    conclusion = ReportSection(
        title="Conclusion",
        content=[
            f"Recommandation finale: {score.decision}.",
            f"Priorité: {'haute' if score.global_score >= 80 else 'moyenne' if score.global_score >= 45 else 'basse'}.",
            "Condition de GO: validation humaine des pièces, de la deadline et des contraintes contractuelles.",
        ],
        evidence=excerpts[:3],
    )
    return StructuredReport(
        executive_summary=executive,
        detection_reason=detection,
        pulse_relevance=pulse,
        business_analysis=business,
        local_event_trends=local_trends,
        market_positioning=market_positioning,
        recommended_approach=approach,
        conclusion=conclusion,
        confidence_score=score.confidence_score,
        human_review_required=score.human_review_required,
        llm_notice="Analyse IA avancée indisponible : clé LLM manquante.",
    )


def report_to_html(report: StructuredReport) -> str:
    sections = [
        report.executive_summary,
        report.detection_reason,
        report.pulse_relevance,
        report.business_analysis,
        report.local_event_trends,
        report.market_positioning,
        report.recommended_approach,
        report.conclusion,
    ]
    body = []
    for section in sections:
        items = "".join(f"<li>{escape(item)}</li>" for item in section.content)
        evidence = "".join(f"<blockquote>{escape(item)}</blockquote>" for item in section.evidence[:6])
        body.append(f"<section><h2>{escape(section.title)}</h2><ul>{items}</ul>{evidence}</section>")
    return (
        "<article class='live-report'>"
        "<h1>Rapport AO LIVE Pulse</h1>"
        f"{''.join(body)}"
        "</article>"
    )


def _response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        contents = item.get("content", []) if isinstance(item, dict) else getattr(item, "content", [])
        for content in contents or []:
            text = content.get("text") if isinstance(content, dict) else getattr(content, "text", None)
            if text:
                chunks.append(text)
    return "\n".join(chunks)


def extract_token_usage(payload: dict[str, Any] | None) -> dict[str, int]:
    usage = (payload or {}).get("usage") or {}
    input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
    output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or 0
    total_tokens = usage.get("total_tokens") or input_tokens + output_tokens
    return {
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "total_tokens": int(total_tokens or 0),
    }


async def build_report(opportunity: dict[str, Any], score: ScoreResult) -> tuple[StructuredReport, dict[str, Any], str]:
    settings = get_settings()
    if not settings.llm_enabled:
        report = build_heuristic_report(opportunity, score)
        return report, {"provider": "heuristic", "reason": "missing_openai_api_key"}, "heuristic"

    # The MVP keeps the LLM provider isolated. If parsing or the API fails, the
    # deterministic report remains the source of truth instead of inventing data.
    try:
        import httpx
        from openai import AsyncOpenAI

        http_client = httpx.AsyncClient(verify=settings.openai_verify_ssl)
        client = AsyncOpenAI(api_key=settings.openai_api_key, http_client=http_client)
        prompt_payload = {
            "opportunity": opportunity,
            "score": score.to_dict(),
            "success_criteria": [
                "Produire un rapport français directement exploitable par une équipe AO.",
                "S'appuyer uniquement sur les données et preuves fournies.",
                "Ne jamais inventer un budget, une deadline, un acheteur ou une contrainte absente.",
                "Mettre 'Non disponible' quand une information manque.",
                "Dans local_event_trends, produire une analyse locale événementielle: types d'événements observables ou probables, attentes de la population locale, tendances IA utiles à la réponse, et points à vérifier.",
                "Si les données ne prouvent pas les événements déjà tenus localement, le dire explicitement et formuler des hypothèses prudentes à valider.",
                "Dans market_positioning, exploiter uniquement les AO comparables, avis d'attribution, montants, attributaires, critères de jugement ou signaux concurrents présents dans le payload.",
                "Si aucun résultat public comparable n'est fourni, écrire 'Non disponible' et lister les recherches publiques à mener sans inventer de confrères, notes techniques ou montants.",
                "Renseigner confidence_score entre 0 et 1.",
            ],
        }
        try:
            response = await client.responses.create(
                model=settings.openai_model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "Tu es un analyste appels d'offres pour LIVE Pulse. "
                            "Tu qualifies la pertinence business, les risques et l'approche recommandée. "
                            "Tu refuses l'hallucination, tu cites uniquement les preuves du payload, "
                            "et tu distingues clairement preuves, tendances probables et points à vérifier."
                        ),
                    },
                    {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False, default=str)},
                ],
                reasoning={"effort": settings.openai_reasoning_effort},
                text={
                    "verbosity": settings.openai_text_verbosity,
                    "format": {
                        "type": "json_schema",
                        "name": "live_pulse_ao_report",
                        "strict": True,
                        "schema": StructuredReport.model_json_schema(),
                    },
                },
                store=False,
            )
        finally:
            await http_client.aclose()
        raw_text = _response_text(response)
        if raw_text:
            parsed = StructuredReport.model_validate_json(raw_text)
            return parsed, response.model_dump(mode="json"), settings.openai_model
    except Exception as exc:  # pragma: no cover - provider/network fallback
        report = build_heuristic_report(opportunity, score)
        raw = {"provider": "openai", "error": str(exc), "fallback": "heuristic"}
        return report, raw, "heuristic-fallback"

    report = build_heuristic_report(opportunity, score)
    return report, {"provider": "openai", "fallback": "empty_response"}, "heuristic-fallback"


def simple_pdf_bytes(title: str, lines: list[str]) -> bytes:
    safe_lines = [line.replace("(", "[").replace(")", "]")[:110] for line in [title, *lines]]
    stream_parts = ["BT", "/F1 12 Tf", "50 780 Td"]
    for index, line in enumerate(safe_lines[:45]):
        if index:
            stream_parts.append("0 -16 Td")
        stream_parts.append(f"({line}) Tj")
    stream_parts.append("ET")
    stream = "\n".join(stream_parts).encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream endobj\n",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer << /Root 1 0 R /Size {len(objects)+1} >>\nstartxref\n{xref_offset}\n%%EOF".encode())
    return bytes(pdf)
