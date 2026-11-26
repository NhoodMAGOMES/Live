from app.services.scoring import ScoreResult


class PulseStrategyAgent:
    def recommend(self, score: ScoreResult) -> str:
        if score.global_score >= 80:
            return "GO"
        if score.global_score >= 45:
            return "WATCH"
        return "NO-GO"

