"""Student profile model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import Gender, HostelStatus

if TYPE_CHECKING:
    from app.models.checkout import Checkout
    from app.models.user import User


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class Student(Base):
    """Hostel-specific profile for a student user."""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(150), index=True)
    room_number: Mapped[str] = mapped_column(String(30), index=True)
    department: Mapped[str] = mapped_column(String(100), index=True)
    year: Mapped[str] = mapped_column(String(30))
    phone: Mapped[str] = mapped_column(String(30))
    parent_phone: Mapped[str] = mapped_column(String(30))
    hostel_status: Mapped[HostelStatus] = mapped_column(
        SAEnum(
            HostelStatus,
            name="hostel_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=HostelStatus.INSIDE,
        server_default=HostelStatus.INSIDE.value,
        index=True,
    )
    photo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    gender: Mapped[Gender | None] = mapped_column(
        SAEnum(
            Gender,
            name="gender",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=True,
    )
    emergency_contact_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    hostel_block: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="student")
    checkouts: Mapped[list["Checkout"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
