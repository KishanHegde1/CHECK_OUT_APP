"""Student checkout model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import CheckoutStatus

if TYPE_CHECKING:
    from app.models.security_staff import SecurityStaff
    from app.models.student import Student


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class Checkout(Base):
    """A student's request and resulting period outside the hostel."""

    __tablename__ = "checkouts"
    __table_args__ = (
        CheckConstraint(
            "checkin_time IS NULL OR checkin_time >= checkout_time",
            name="checkin_not_before_checkout",
        ),
        Index("ix_checkouts_student_status", "student_id", "status"),
        Index(
            "uq_checkouts_one_active_per_student",
            "student_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    checkout_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        index=True,
    )
    checkout_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        index=True,
    )
    checkin_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    qr_token: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
    )
    status: Mapped[CheckoutStatus] = mapped_column(
        SAEnum(
            CheckoutStatus,
            name="checkout_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=CheckoutStatus.ACTIVE,
        server_default=CheckoutStatus.ACTIVE.value,
        index=True,
    )
    verified_by: Mapped[int | None] = mapped_column(
        ForeignKey("security_staff.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )

    student: Mapped["Student"] = relationship(back_populates="checkouts")
    verifier: Mapped["SecurityStaff | None"] = relationship(
        back_populates="verified_checkouts",
        foreign_keys=[verified_by],
    )
