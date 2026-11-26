from __future__ import annotations

from app.models import Notification, NotificationType


class AlertAgent:
    def build_notification(self, title: str, message: str, opportunity_id: int | None = None) -> Notification:
        return Notification(
            type=NotificationType.NEW_OPPORTUNITY,
            title=title,
            message=message,
            opportunity_id=opportunity_id,
            payload={},
        )
