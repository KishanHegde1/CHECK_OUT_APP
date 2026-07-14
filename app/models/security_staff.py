"""Security staff profile model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.checkout import Checkout
    from app.models.user import User


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class SecurityStaff(Base):
    """Gate and shift details for a security user."""

    __tablename__ = "security_staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    staff_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(150), index=True)
    phone: Mapped[str] = mapped_column(String(30))
    gate_name: Mapped[str] = mapped_column(String(100), index=True)
    shift: Mapped[str] = mapped_column(String(50), index=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="security_staff")
    verified_checkouts: Mapped[list["Checkout"]] = relationship(
        back_populates="verifier",
        foreign_keys="Checkout.verified_by",
    )
