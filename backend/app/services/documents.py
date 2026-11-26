from __future__ import annotations

import io
import json
from pathlib import Path

from bs4 import BeautifulSoup


def extract_text_from_bytes(filename: str, content: bytes, content_type: str | None = None) -> str:
    suffix = Path(filename).suffix.casefold()
    if suffix == ".pdf" or content_type == "application/pdf":
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    if suffix == ".docx":
        import docx

        document = docx.Document(io.BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    if suffix in {".html", ".htm", ".xml"} or (content_type or "").endswith("html"):
        soup = BeautifulSoup(content, "lxml")
        return soup.get_text(" ", strip=True)
    if suffix == ".json":
        parsed = json.loads(content.decode("utf-8"))
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    return content.decode("utf-8", errors="replace")


def chunk_text(text: str, chunk_size: int = 1600, overlap: int = 180) -> list[str]:
    clean = " ".join((text or "").split())
    if not clean:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + chunk_size)
        chunks.append(clean[start:end])
        if end == len(clean):
            break
        start = max(0, end - overlap)
    return chunks

