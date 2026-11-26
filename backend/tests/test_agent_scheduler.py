from datetime import datetime, timezone

from app.models import Agent
from app.services.agent_orchestrator import compute_next_run_at


def test_daily_schedule_uses_paris_time() -> None:
    agent = Agent(
        slug="verification_cycle",
        name="Cycle",
        description="",
        task="",
        is_active=True,
        schedule_enabled=True,
        schedule_frequency="daily",
        schedule_interval=1,
        schedule_time="08:00",
        schedule_weekday=0,
    )

    next_run = compute_next_run_at(agent, from_time=datetime(2026, 6, 28, 5, 0, tzinfo=timezone.utc))

    assert next_run == datetime(2026, 6, 28, 6, 0, tzinfo=timezone.utc)


def test_weekly_schedule_moves_to_next_matching_day() -> None:
    agent = Agent(
        slug="weekly",
        name="Weekly",
        description="",
        task="",
        is_active=True,
        schedule_enabled=True,
        schedule_frequency="weekly",
        schedule_interval=1,
        schedule_time="09:30",
        schedule_weekday=0,
    )

    next_run = compute_next_run_at(agent, from_time=datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc))

    assert next_run == datetime(2026, 6, 29, 7, 30, tzinfo=timezone.utc)
