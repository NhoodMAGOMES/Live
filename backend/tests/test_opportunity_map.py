from datetime import datetime, timedelta, timezone

from app.models import Opportunity, OpportunityStatus
from app.services.opportunity_map import build_map_points, department_codes_from_location


def test_department_codes_from_location_handles_single_digit_and_aliases() -> None:
    assert department_codes_from_location("1, 38, Paris") == ["01", "38", "75"]
    assert department_codes_from_location("Bordeaux / Landes / Biarritz") == ["33", "40", "64"]


def test_build_map_points_groups_metropolitan_and_overseas_locations() -> None:
    soon_deadline = datetime.now(timezone.utc) + timedelta(days=2)
    opportunities = [
        Opportunity(
            id=1,
            source="BOAMP",
            source_reference="A",
            title="AO Paris",
            location="75",
            status=OpportunityStatus.NEW,
            global_score=55,
            deadline=soon_deadline,
            created_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
        ),
        Opportunity(
            id=2,
            source="BOAMP",
            source_reference="B",
            title="AO Antilles",
            location="971",
            status=OpportunityStatus.WATCH,
            global_score=45,
            created_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
        ),
    ]

    points = {point["key"]: point for point in build_map_points(opportunities)}

    assert points["75"]["department_name"] == "Paris"
    assert points["75"]["x"] is not None
    assert points["75"]["count"] == 1
    assert points["75"]["deadline_counts"]["soon"] == 1
    assert "paris" in points["75"]["search_text"]
    assert points["971"]["department_name"] == "Guadeloupe"
    assert points["971"]["is_overseas"] is True
    assert points["971"]["x"] is None
