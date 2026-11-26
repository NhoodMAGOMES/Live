from __future__ import annotations

from app.services.documents import chunk_text, extract_text_from_bytes


class NoticeExtractionAgent:
    def extract(self, filename: str, content: bytes, content_type: str | None = None) -> tuple[str, list[str]]:
        text = extract_text_from_bytes(filename, content, content_type)
        return text, chunk_text(text)
