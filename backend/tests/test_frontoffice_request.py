import pytest
from pydantic import ValidationError

from app.schemas import FrontAnalysisRequest


def test_front_analysis_limit_accepts_broader_boamp_collection() -> None:
    request = FrontAnalysisRequest(limit=500)

    assert request.limit == 500


def test_front_analysis_default_prefilter_matches_business_rejection_floor() -> None:
    request = FrontAnalysisRequest()

    assert request.min_live_score == 25


def test_front_analysis_accepts_department_focus() -> None:
    request = FrontAnalysisRequest(departments=["59", "75"])

    assert request.departments == ["59", "75"]


def test_front_analysis_limit_rejects_unbounded_collection() -> None:
    with pytest.raises(ValidationError):
        FrontAnalysisRequest(limit=1001)
