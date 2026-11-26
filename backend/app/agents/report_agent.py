from typing import Any

from app.services.reports import build_report
from app.services.scoring import ScoreResult


class ReportAgent:
    async def generate(self, opportunity: dict[str, Any], score: ScoreResult):
        return await build_report(opportunity, score)

