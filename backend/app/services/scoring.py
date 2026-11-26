from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any


PULSE_AXES = {
    "immobilier opere": ["immobilier", "site", "actif", "lieu", "occupation", "foncier"],
    "valorisation actif": ["valorisation", "revenus", "commercialisation", "rentabilité", "business plan"],
    "programmation evenementielle": [
        "programmation",
        "événementiel",
        "évènement",
        "événement",
        "spectacle",
        "culturel",
        "artistique",
        "mise en lumière",
        "médiation",
        "exposition",
        "scénographie",
    ],
    "hospitality mice": ["hospitality", "séminaire", "mice", "réceptif", "congrès"],
    "medias de lieu": ["publicité", "affichage", "régie", "média", "chalandise"],
    "exploitation prise bail": ["exploitation", "prise à bail", "concession", "dsp", "occupation"],
    "business plan evenementiel": ["business plan", "modèle économique", "compte d'exploitation"],
    "animation communautes": ["communauté", "animation", "public", "fréquentation"],
    "synergies": ["commerce", "f&b", "marketing", "property", "asset"],
    "lieux vivants": ["lieu vivant", "365", "activation", "usage", "destination", "équipement culturel", "tiers-lieu", "accueil public"],
}

LIVE_PREFILTER_MIN_SCORE = 25.0
HARD_REJECTION_REASONS = {
    "signal_live_absent",
    "mots_cles_trop_generiques",
    "bruit_hors_live",
}

LIVE_CORE_TERMS = [
    "événementiel",
    "évènement",
    "événement",
    "programmation événementielle",
    "programmation culturelle",
    "programmation artistique",
    "spectacle vivant",
    "mise en lumière",
    "médiation culturelle",
    "exposition",
    "scénographie",
    "exploitation événementielle",
    "gestion événementielle",
    "lieu culturel",
    "équipement culturel",
    "espace culturel",
    "espace d'exposition",
    "espaces d'exposition",
    "médiation",
    "lieu vivant",
    "activation de lieu",
    "valorisation de lieu",
    "valorisation patrimoniale",
    "transformation d'édifice",
    "reconversion de site",
    "destination culturelle",
    "accueil public",
    "tiers-lieu",
    "destination événementielle",
    "occupation temporaire",
    "commercialisation d'espaces",
    "régie publicitaire",
    "hospitality",
    "mice",
    "concession culturelle",
    "dsp culturelle",
    "appel à projets culturel",
    "appel à partenaires événementiels",
]

NOISE_TERMS = [
    "titre-restaurant",
    "gros oeuvre",
    "gros œuvre",
    "bioessais",
    "qualité de l'air",
    "qualité de l'eau",
    "bruit",
    "nuisance sonore",
    "acoustique",
    "étude acoustique",
    "déchetterie",
    "decheterie",
    "fourniture de matériels",
    "fourniture de materiels",
    "fourniture de consommables",
    "matériaux",
    "materiaux",
    "travaux et entretien",
    "audits énergétiques",
    "diagnostics de performances énergétiques",
    "maîtrise d'oeuvre technique",
    "maitrise d'oeuvre technique",
    "régisseur son et lumière",
    "regisseur son et lumiere",
    "maintenance",
    "nettoyage",
    "gardiennage",
]

GENERIC_ONLY_CATEGORIES = {
    "TERMES GENERIQUES MARCHES PUBLIQUES",
    "ETUDE ET CONSEIL",
}


@dataclass(frozen=True)
class KeywordConfig:
    id: int | None
    category: str
    term: str
    weight: float = 3.0
    synonyms: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)


@dataclass
class KeywordMatchResult:
    keyword_id: int | None
    category: str
    keyword: str
    matched_term: str
    excerpt: str
    weight: float
    match_type: str


@dataclass
class ScoreResult:
    global_score: float
    decision: str
    confidence_score: float
    human_review_required: bool
    score_by_family: dict[str, float]
    breakdown: dict[str, float]
    matched_keywords: list[KeywordMatchResult]
    maluses: list[dict[str, Any]]
    justifications: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["matched_keywords"] = [asdict(match) for match in self.matched_keywords]
        return payload


def prequalification_result(score: ScoreResult, minimum_score: float = LIVE_PREFILTER_MIN_SCORE) -> tuple[bool, str]:
    hard_reasons = [malus["reason"] for malus in score.maluses if malus.get("reason") in HARD_REJECTION_REASONS]
    if hard_reasons:
        return False, f"hors_enjeux_live:{', '.join(hard_reasons)}"
    if score.global_score < minimum_score:
        return False, f"score_insuffisant:{score.global_score}/{minimum_score}"
    return True, "prequalifie_live"


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = value.translate(str.maketrans({"’": "'", "‘": "'", "‛": "'", "`": "'", "´": "'", "‐": "-", "‑": "-", "–": "-", "—": "-"}))
    normalized = unicodedata.normalize("NFD", value)
    without_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_accents.casefold()).strip()


def compact_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def build_search_text(opportunity: dict[str, Any]) -> str:
    parts = [
        opportunity.get("title"),
        opportunity.get("object"),
        opportunity.get("description"),
        opportunity.get("document_context"),
        opportunity.get("buyer"),
        opportunity.get("location"),
        " ".join(opportunity.get("cpv") or []),
    ]
    for lot in opportunity.get("lots") or []:
        if isinstance(lot, dict):
            parts.extend(str(v) for v in lot.values() if v)
    return compact_text(" ".join(part for part in parts if part))


def make_excerpt(text: str, start: int, end: int, radius: int = 130) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    prefix = "..." if left else ""
    suffix = "..." if right < len(text) else ""
    return f"{prefix}{compact_text(text[left:right])}{suffix}"


def _normalized_index_map(original: str) -> tuple[str, list[int]]:
    normalized_chars: list[str] = []
    indexes: list[int] = []
    for idx, char in enumerate(original):
        decomposed = unicodedata.normalize("NFD", char)
        for out in decomposed:
            if unicodedata.category(out) == "Mn":
                continue
            normalized_chars.append(out.casefold())
            indexes.append(idx)
    return "".join(normalized_chars), indexes


def _find_exact(original: str, term: str) -> tuple[int, int] | None:
    normalized, index_map = _normalized_index_map(original)
    needle = normalize_text(term)
    if not needle:
        return None
    pattern = rf"(?<!\w){re.escape(needle)}s?(?!\w)"
    match = re.search(pattern, normalized)
    if not match:
        return None
    start = index_map[match.start()]
    end = index_map[min(match.end() - 1, len(index_map) - 1)] + 1
    return start, end


def _exclusions_hit(text: str, exclusions: list[str]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(exclusion) in normalized for exclusion in exclusions)


def _fuzzy_match(original: str, term: str) -> tuple[int, int] | None:
    normalized_text = normalize_text(original)
    normalized_term = normalize_text(term)
    if len(normalized_term) < 7 or len(normalized_text) < len(normalized_term):
        return None
    tokens = normalized_text.split()
    term_tokens = normalized_term.split()
    window_size = max(1, len(term_tokens))
    best_score = 0.0
    best_window: str | None = None
    for idx in range(0, max(1, len(tokens) - window_size + 1)):
        window = " ".join(tokens[idx : idx + window_size])
        ratio = SequenceMatcher(None, normalized_term, window).ratio()
        if ratio > best_score:
            best_score = ratio
            best_window = window
    if best_score < 0.9 or not best_window:
        return None
    return _find_exact(original, best_window)


def match_keywords(text: str, keywords: list[KeywordConfig]) -> list[KeywordMatchResult]:
    matches: list[KeywordMatchResult] = []
    seen: set[tuple[int | None, str]] = set()
    for keyword in keywords:
        if _exclusions_hit(text, keyword.exclusions):
            continue
        candidates = [keyword.term, *keyword.synonyms]
        for candidate in candidates:
            exact_span = _find_exact(text, candidate)
            match_type = "exact" if exact_span else "fuzzy"
            span = exact_span or _fuzzy_match(text, candidate)
            if not span:
                continue
            key = (keyword.id, normalize_text(candidate))
            if key in seen:
                continue
            seen.add(key)
            start, end = span
            matches.append(
                KeywordMatchResult(
                    keyword_id=keyword.id,
                    category=keyword.category,
                    keyword=keyword.term,
                    matched_term=candidate,
                    excerpt=make_excerpt(text, start, end),
                    weight=keyword.weight,
                    match_type=match_type,
                )
            )
    return matches


def semantic_heuristic_score(text: str) -> tuple[float, dict[str, float]]:
    axis_scores: dict[str, float] = {}
    normalized = normalize_text(text)
    for axis, terms in PULSE_AXES.items():
        hits = sum(1 for term in terms if normalize_text(term) in normalized)
        axis_scores[axis] = min(2.0, hits * 0.75)
    return min(20.0, sum(axis_scores.values())), axis_scores


def hit_terms(text: str, terms: list[str]) -> list[str]:
    normalized = normalize_text(text)
    return [term for term in terms if normalize_text(term) in normalized]


def _deadline_malus(deadline: datetime | None, now: datetime) -> list[dict[str, Any]]:
    if not deadline:
        return [{"reason": "deadline_non_disponible", "points": -2, "details": "Date limite non disponible"}]
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    remaining_days = (deadline - now).total_seconds() / 86400
    if remaining_days < 0:
        return [{"reason": "deadline_depassee", "points": -20, "details": "Date limite dépassée"}]
    if remaining_days < 3:
        return [{"reason": "deadline_tres_proche", "points": -8, "details": "Moins de 3 jours pour répondre"}]
    if remaining_days < 7:
        return [{"reason": "deadline_proche", "points": -4, "details": "Moins de 7 jours pour répondre"}]
    return []


def decision_from_score(score: float) -> str:
    if score >= 80:
        return "GO"
    if score >= 65:
        return "GO_HUMAN_REVIEW"
    if score >= 45:
        return "WATCH"
    return "NO_GO"


def label_from_score(score: float) -> str:
    if score >= 80:
        return "Très pertinent - GO recommandé"
    if score >= 65:
        return "Pertinent - analyse humaine requise"
    if score >= 45:
        return "À surveiller"
    return "Faible pertinence - NO-GO recommandé"


def score_opportunity(
    opportunity: dict[str, Any],
    keywords: list[KeywordConfig],
    now: datetime | None = None,
) -> ScoreResult:
    now = now or datetime.now(timezone.utc)
    text = build_search_text(opportunity)
    matches = match_keywords(text, keywords)
    unique_keyword_weight = {
        (match.keyword_id, normalize_text(match.keyword)): match.weight
        for match in matches
    }
    raw_keyword_weight = sum(unique_keyword_weight.values())
    keyword_points = min(35.0, raw_keyword_weight * 1.8)

    category_weights: dict[str, float] = {}
    for match in matches:
        category_weights[match.category] = category_weights.get(match.category, 0.0) + match.weight
    max_category_weight = max(category_weights.values(), default=1.0)
    score_by_family = {
        category: round(min(100.0, (weight / max_category_weight) * keyword_points), 2)
        for category, weight in category_weights.items()
    }

    semantic_points, axis_scores = semantic_heuristic_score(text)
    normalized = normalize_text(text)
    core_hits = hit_terms(text, LIVE_CORE_TERMS)
    noise_hits = hit_terms(text, NOISE_TERMS)
    live_core_points = min(20.0, len(core_hits) * 5.0)
    business_points = min(
        15.0,
        sum(
            3.0
            for term in [
                "revenus",
                "commercialisation",
                "business plan",
                "rentabilite",
                "concession",
                "mandat",
                "valorisation",
                "valorisation patrimoniale",
                "valorisation de lieu",
                "revenus additionnels",
            ]
            if normalize_text(term) in normalized
        ),
    )
    operational_points = min(
        10.0,
        sum(
            2.5
            for term in [
                "production",
                "programmation",
                "exploitation",
                "occupation",
                "operateur",
                "opérateur",
                "gestion de lieu",
                "accueil public",
                "médiation",
            ]
            if normalize_text(term) in normalized
        ),
    )
    feasibility_points = 10.0
    maluses = _deadline_malus(opportunity.get("deadline"), now)
    feasibility_points = max(0.0, feasibility_points + sum(malus["points"] for malus in maluses if malus["reason"].startswith("deadline")))
    quality_maluses: list[dict[str, Any]] = []
    matched_categories = {match.category for match in matches}
    generic_only = bool(matches) and matched_categories.issubset(GENERIC_ONLY_CATEGORIES) and not core_hits
    if matches and not core_hits:
        quality_maluses.append(
            {
                "reason": "signal_live_absent",
                "points": -12,
                "details": "Mots-clés détectés mais aucun signal fort événementiel, lieu vivant ou stratégie LIVE.",
            }
        )
    if generic_only:
        quality_maluses.append(
            {
                "reason": "mots_cles_trop_generiques",
                "points": -10,
                "details": "Détection portée uniquement par des catégories génériques.",
            }
        )
    if noise_hits:
        quality_maluses.append(
            {
                "reason": "bruit_hors_live",
                "points": -min(15, 5 * len(noise_hits)),
                "details": f"Signaux hors périmètre LIVE: {', '.join(noise_hits[:5])}",
            }
        )
    differentiation_points = min(
        5.0,
        sum(1.5 for term in ["singularite", "differenciation", "storytelling", "identite", "destination"] if term in normalized),
    )
    esg_points = min(5.0, sum(1.5 for term in ["utile", "public", "durable", "esg", "culture"] if term in normalized))

    breakdown = {
        "keyword_matching": round(keyword_points, 2),
        "semantic_relevance": round(semantic_points, 2),
        "live_core_signal": round(live_core_points, 2),
        "business_potential": round(business_points, 2),
        "operational_fit": round(operational_points, 2),
        "feasibility": round(feasibility_points, 2),
        "strategic_differentiation": round(differentiation_points, 2),
        "quality_esg_utility": round(esg_points, 2),
    }
    score = max(0.0, min(100.0, sum(breakdown.values()) + sum(malus["points"] for malus in quality_maluses)))
    if not core_hits and score > 42:
        score = 42
    if generic_only and score > 35:
        score = 35
    confidence = min(0.95, max(0.2, 0.35 + math.log1p(len(matches)) / 5 + semantic_points / 100 + len(core_hits) * 0.04 - len(noise_hits) * 0.03))
    human_review_required = confidence < 0.7 or not opportunity.get("deadline")
    justifications = [
        f"{len(matches)} mot(s)-clé(s) détecté(s)",
        f"Score sémantique heuristique Pulse LIVE: {semantic_points:.1f}/20",
        f"Signaux LIVE forts: {', '.join(core_hits[:5]) or 'aucun'}",
        label_from_score(score),
    ]

    return ScoreResult(
        global_score=round(score, 2),
        decision=decision_from_score(score),
        confidence_score=round(confidence, 2),
        human_review_required=human_review_required,
        score_by_family=score_by_family,
        breakdown=breakdown | {"semantic_axes": axis_scores, "live_core_hits": core_hits, "noise_hits": noise_hits},  # type: ignore[dict-item]
        matched_keywords=matches,
        maluses=maluses + quality_maluses,
        justifications=justifications,
    )
