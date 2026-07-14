"""Persisted domain enumeration values."""

from enum import StrEnum


class UserRole(StrEnum):
    """Authorization role assigned to a user account."""

    STUDENT = "STUDENT"
    ADMIN = "ADMIN"
    SECURITY = "SECURITY"


class HostelStatus(StrEnum):
    """Whether a student is currently inside or outside the hostel."""

    INSIDE = "INSIDE"
    OUTSIDE = "OUTSIDE"


class Gender(StrEnum):
    """Optional gender recorded on a student's hostel profile."""

    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class CheckoutStatus(StrEnum):
    """Lifecycle state of a checkout request."""

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class NotificationType(StrEnum):
    """Category used to present an administrative notification."""

    CHECKOUT = "CHECKOUT"
    SECURITY = "SECURITY"
    SYSTEM = "SYSTEM"
    NOTICE = "NOTICE"
