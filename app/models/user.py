"""User account model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.admin import Admin
    from app.models.security_staff import SecurityStaff
    from app.models.student import Student


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class User(Base):
    """Credentials and authorization state shared by every actor."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        SAEnum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        index=True,
    )
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    student: Mapped["Student | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )
    admin: Mapped["Admin | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )
    security_staff: Mapped["SecurityStaff | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )


# Authentication normalizes both identifiers to lowercase. These expression
# indexes enforce that invariant for writes made outside the application too.
Index("uq_users_username_lower", func.lower(User.username), unique=True)
Index("uq_users_email_lower", func.lower(User.email), unique=True)
