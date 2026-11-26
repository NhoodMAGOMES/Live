from app.services.reports import StructuredReport, build_heuristic_report, extract_token_usage
from app.services.scoring import ScoreResult


def test_heuristic_report_matches_strict_structured_schema() -> None:
    score = ScoreResult(
        global_score=67.5,
        decision="WATCH",
        confidence_score=0.72,
        human_review_required=True,
        score_by_family={"programmation": 18.0},
        breakdown={"semantic_relevance": 12.0, "business_potential": 8.0, "feasibility": 6.0},
        matched_keywords=[],
        maluses=[],
        justifications=[],
    )

    report = build_heuristic_report({"title": "Programmation événementielle", "source": "BOAMP"}, score)
    schema = StructuredReport.model_json_schema()

    assert report.llm_notice
    assert report.local_event_trends.title == "Analyse locale événementielle"
    assert report.market_positioning.title == "Positionnement marché et AO comparables"
    assert "llm_notice" in schema["required"]
    assert "local_event_trends" in schema["required"]
    assert "market_positioning" in schema["required"]
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["ReportSection"]["required"] == ["title", "content", "evidence"]


def test_extract_token_usage_supports_responses_and_chat_payloads() -> None:
    responses_usage = extract_token_usage({"usage": {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20}})
    chat_usage = extract_token_usage({"usage": {"prompt_tokens": 5, "completion_tokens": 7}})

    assert responses_usage == {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20}
    assert chat_usage == {"input_tokens": 5, "output_tokens": 7, "total_tokens": 12}
