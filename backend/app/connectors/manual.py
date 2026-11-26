from app.connectors.base import ConnectorRunResult
from app.models import Source


class ManualConnector:
    async def fetch(self, source: Source) -> ConnectorRunResult:
        return ConnectorRunResult(
            logs=[
                {
                    "event": "manual_source",
                    "details": "Cette source attend un import fichier, URL ou email d'alerte.",
                }
            ]
        )

