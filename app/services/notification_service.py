"""Notification persistence and query services."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.schemas.notification import NotificationCreate, NotificationResponse


def create_notification(
    db: Session,
    payload: NotificationCreate,
    *,
    commit: bool = True,
) -> Notification:
    """Create a notification, optionally as part of an existing transaction."""

    notification = Notification(**payload.model_dump())
    db.add(notification)
    if commit:
        db.commit()
        db.refresh(notification)
    return notification


def list_notifications(db: Session) -> list[NotificationResponse]:
    """Return global admin notifications, newest first."""

    statement = select(Notification).order_by(
        Notification.created_at.desc(),
        Notification.id.desc(),
    )
    return [
        NotificationResponse.model_validate(item)
        for item in db.scalars(statement).all()
    ]


__all__ = ["create_notification", "list_notifications"]
