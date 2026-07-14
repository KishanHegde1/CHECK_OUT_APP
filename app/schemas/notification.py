"""Notification request and response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.models.enums import NotificationType

from .common import BaseSchema


class NotificationBase(BaseSchema):
    """Fields shared by notification records."""

    title: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1)
    notification_type: NotificationType


class NotificationCreate(NotificationBase):
    """Fields used to create a notification."""


class NotificationResponse(NotificationBase):
    """Notification exposed through the API."""

    id: int
    is_read: bool
    created_at: datetime


class NotificationReadUpdate(BaseSchema):
    """Command used to change a notification's read state."""

    is_read: bool = True


class NotificationListResponse(BaseSchema):
    """Notification collection with unread and total counts."""

    notifications: list[NotificationResponse]
    unread_count: int = Field(ge=0)
    total: int = Field(ge=0)
