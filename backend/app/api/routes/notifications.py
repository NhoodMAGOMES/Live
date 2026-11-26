from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession
from app.models import Notification
from app.schemas import NotificationRead


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
def list_notifications(db: DbSession) -> list[Notification]:
    return list(db.scalars(select(Notification).order_by(Notification.created_at.desc()).limit(100)).all())


@router.patch("/{notification_id}/read", response_model=NotificationRead)
def mark_read(notification_id: int, db: DbSession) -> Notification:
    notification = db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification

