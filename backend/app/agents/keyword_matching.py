from app.services.scoring import KeywordConfig, KeywordMatchResult, match_keywords


class KeywordMatchingAgent:
    def match(self, text: str, keywords: list[KeywordConfig]) -> list[KeywordMatchResult]:
        return match_keywords(text, keywords)

