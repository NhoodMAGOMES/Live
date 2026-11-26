from app.connectors.boamp import BOAMPConnector
from app.connectors.manual import ManualConnector
from app.connectors.ted import TEDConnector
from app.connectors.web_watch import WebWatchConnector
from app.models import SourceConnectorType


def connector_for(connector_type: SourceConnectorType):
    if connector_type == SourceConnectorType.BOAMP_API:
        return BOAMPConnector()
    if connector_type == SourceConnectorType.TED_API:
        return TEDConnector()
    if connector_type in {SourceConnectorType.WEB_WATCH, SourceConnectorType.RSS}:
        return WebWatchConnector()
    return ManualConnector()
