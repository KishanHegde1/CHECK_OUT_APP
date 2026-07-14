"""Administrative notification model."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import NotificationType


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class Notification(Base):
    """A global administrative event or notice."""

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_read_created", "is_read", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    notification_type: Mapped[NotificationType] = mapped_column(
        SAEnum(
            NotificationType,
            name="notification_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=NotificationType.SYSTEM,
        server_default=NotificationType.SYSTEM.value,
        index=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        index=True,
    )
