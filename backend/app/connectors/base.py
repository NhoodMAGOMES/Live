from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.models import Source


@dataclass
class ConnectorNotice:
    source_reference: str | None
    source_url: str | None
    payload: dict[str, Any]
    normalized: dict[str, Any]
    raw_text: str | None = None


@dataclass
class ConnectorRunResult:
    notices: list[ConnectorNotice] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)


class SourceConnector(Protocol):
    async def fetch(self, source: Source) -> ConnectorRunResult:
        ...
