from app.services.market_intelligence import market_search_terms
from app.services.scoring import KeywordMatchResult, ScoreResult


def test_market_search_terms_prioritize_matched_keywords_before_title() -> None:
    score = ScoreResult(
        global_score=62,
        decision="WATCH",
        confidence_score=0.7,
        human_review_required=True,
        score_by_family={},
        breakdown={},
        matched_keywords=[
            KeywordMatchResult(
                keyword_id=1,
                category="EVENEMENTIEL",
                keyword="programmation culturelle",
                matched_term="programmation culturelle",
                excerpt="programmation culturelle du site",
                weight=5,
                match_type="exact",
            )
        ],
        maluses=[],
        justifications=[],
    )

    terms = market_search_terms({"title": "Concession événementielle pour un équipement culturel"}, score)

    assert terms[0] == "programmation culturelle"
    assert len(terms) <= 4
