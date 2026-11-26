from __future__ import annotations

from urllib import robotparser
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.connectors.base import ConnectorNotice, ConnectorRunResult
from app.models import Source
from app.services.normalization import normalize_manual_notice


class WebWatchConnector:
    async def fetch(self, source: Source) -> ConnectorRunResult:
        if not source.url:
            return ConnectorRunResult(logs=[{"event": "skipped", "reason": "missing_url"}])
        config = source.config or {}
        if not config.get("scraping_allowed", False):
            return ConnectorRunResult(
                logs=[
                    {
                        "event": "skipped",
                        "reason": "scraping_not_enabled",
                        "details": "Activer scraping_allowed seulement après vérification CGU/robots.txt.",
                    }
                ]
            )

        parsed = urlparse(source.url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        robots = robotparser.RobotFileParser()
        robots.set_url(robots_url)
        try:
            robots.read()
            allowed = robots.can_fetch("LIVEPulseBot", source.url)
        except Exception:
            allowed = False
        if not allowed:
            return ConnectorRunResult(logs=[{"event": "skipped", "reason": "robots_txt_disallow_or_unavailable"}])

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(source.url, headers={"User-Agent": "LIVEPulseBot/0.1"})
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        text = soup.get_text(" ", strip=True)
        payload = {
            "source": source.name,
            "source_url": source.url,
            "source_reference": source.url,
            "title": soup.title.text.strip() if soup.title else source.name,
            "description": text,
        }
        return ConnectorRunResult(
            notices=[
                ConnectorNotice(
                    source_reference=source.url,
                    source_url=source.url,
                    payload=payload,
                    normalized=normalize_manual_notice(payload),
                    raw_text=text,
                )
            ],
            logs=[{"event": "fetched", "url": source.url, "bytes": len(response.content)}],
        )

