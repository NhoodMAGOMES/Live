from app.services.scoring import semantic_heuristic_score


class SemanticRelevanceAgent:
    def score(self, text: str) -> tuple[float, dict[str, float]]:
        return semantic_heuristic_score(text)

