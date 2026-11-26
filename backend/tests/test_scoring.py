from datetime import datetime, timezone

from app.agents.source_discovery import _apply_prequalification_score
from app.models import Opportunity, OpportunityStatus
from app.services.normalization import parse_datetime
from app.services.opportunities import _status_after_analysis
from app.services.scoring import KeywordConfig, match_keywords, prequalification_result, score_opportunity


def test_keyword_matching_is_accent_case_and_plural_tolerant() -> None:
    text = "Programmations artistiques et etude de faisabilite EVENEMENTIELLE du site."
    keywords = [
        KeywordConfig(id=1, category="EVENEMENTIEL", term="programmation artistique", weight=5),
        KeywordConfig(id=2, category="ETUDE", term="étude de faisabilité événementielle", weight=5),
    ]

    matches = match_keywords(text, keywords)

    assert {match.keyword for match in matches} == {
        "programmation artistique",
        "étude de faisabilité événementielle",
    }
    assert all(match.excerpt for match in matches)


def test_scoring_returns_explainable_go_recommendation() -> None:
    opportunity = {
        "title": "AMO programmation événementielle",
        "description": (
            "Étude de potentiel événementiel, business plan événementiel, exploitation de lieu, "
            "commercialisation d'espaces, régie publicitaire, valorisation patrimoniale et revenus additionnels."
        ),
        "buyer": "Ville",
        "location": "Lille",
        "cpv": ["79952000"],
        "deadline": parse_datetime("2099-12-31T12:00:00+00:00"),
    }
    keywords = [
        KeywordConfig(id=1, category="ETUDE", term="AMO", weight=3),
        KeywordConfig(id=2, category="INGENIERIE", term="étude de potentiel événementiel", weight=5),
        KeywordConfig(id=3, category="BUSINESS", term="business plan événementiel", weight=5),
        KeywordConfig(id=4, category="EXPLOITATION", term="exploitation de lieu", weight=5),
        KeywordConfig(id=5, category="COMMERCIAL", term="régie publicitaire", weight=4),
    ]

    result = score_opportunity(opportunity, keywords, now=datetime(2026, 6, 28, tzinfo=timezone.utc))

    assert result.global_score >= 65
    assert result.decision in {"GO", "GO_HUMAN_REVIEW"}
    assert result.score_by_family
    assert result.matched_keywords
    assert "keyword_matching" in result.breakdown


def test_deadline_malus_blocks_expired_notice() -> None:
    opportunity = {
        "title": "Programmation culturelle",
        "description": "programmation culturelle et événementiel",
        "deadline": parse_datetime("2020-01-01T12:00:00+00:00"),
    }
    keywords = [KeywordConfig(id=1, category="EVENEMENTIEL", term="programmation culturelle", weight=5)]

    result = score_opportunity(opportunity, keywords, now=datetime(2026, 6, 28, tzinfo=timezone.utc))

    assert any(malus["reason"] == "deadline_depassee" for malus in result.maluses)
    assert result.breakdown["feasibility"] == 0


def test_technical_amo_air_noise_is_rejected_before_business_list() -> None:
    opportunity = {
        "title": "24N0568 - AMO d'étude technique et d'aide à la décision sur la qualité de l'air et le bruit",
        "description": "AMO d'étude technique sur la qualité de l'air et le bruit.",
        "deadline": parse_datetime("2099-12-31T12:00:00+00:00"),
    }
    keywords = [KeywordConfig(id=1, category="ETUDE ET CONSEIL", term="AMO", weight=3)]

    result = score_opportunity(opportunity, keywords, now=datetime(2026, 6, 28, tzinfo=timezone.utc))
    qualified, reason = prequalification_result(result)

    assert not qualified
    assert "hors_enjeux_live" in reason
    assert any(malus["reason"] == "bruit_hors_live" for malus in result.maluses)


def test_weak_unrelated_notice_is_rejected_under_default_prefilter() -> None:
    opportunity = {
        "title": "Fourniture de matériel administratif",
        "description": "Achat de fournitures de bureau et consommables standards.",
        "deadline": parse_datetime("2099-12-31T12:00:00+00:00"),
    }
    keywords = [KeywordConfig(id=1, category="ETUDE ET CONSEIL", term="AMO", weight=3)]

    result = score_opportunity(opportunity, keywords, now=datetime(2026, 6, 28, tzinfo=timezone.utc))
    qualified, reason = prequalification_result(result)

    assert result.global_score < 25
    assert not qualified
    assert reason.startswith("score_insuffisant")


def test_rejected_prequalification_is_stored_as_ai_discard() -> None:
    opportunity = Opportunity(
        source="BOAMP",
        source_reference="24N0568",
        title="24N0568 - AMO d'étude technique et d'aide à la décision sur la qualité de l'air et le bruit",
        description="AMO d'étude technique sur la qualité de l'air et le bruit.",
    )
    keywords = [KeywordConfig(id=1, category="ETUDE ET CONSEIL", term="AMO", weight=3)]
    result = score_opportunity(
        {
            "title": opportunity.title,
            "description": opportunity.description,
            "deadline": parse_datetime("2099-12-31T12:00:00+00:00"),
        },
        keywords,
        now=datetime(2026, 6, 28, tzinfo=timezone.utc),
    )
    qualified, reason = prequalification_result(result)

    assert not qualified

    _apply_prequalification_score(opportunity, result, rejected_reason=reason)

    assert opportunity.status == OpportunityStatus.NOT_RELEVANT
    assert opportunity.global_score == result.global_score
    assert opportunity.ai_summary and opportunity.ai_summary.startswith("Écarté par IA")
    assert opportunity.normalized_payload["live_prequalification"]["qualified"] is False


def test_relevant_status_is_downgraded_when_score_drops_under_threshold() -> None:
    next_status = _status_after_analysis(OpportunityStatus.RELEVANT, qualified=True, score=42.15)

    assert next_status == OpportunityStatus.ANALYZED
