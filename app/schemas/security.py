"""Security-staff profile and QR-verification schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from .checkout import CheckoutResponse
from .common import BaseSchema
from .student import StudentPublic


class SecurityStaffBase(BaseSchema):
    """Fields shared by security-staff profiles."""

    staff_id: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    gate_name: str = Field(min_length=1, max_length=255)
    shift: str = Field(min_length=1, max_length=64)
    is_active: bool


class SecurityProfileResponse(SecurityStaffBase):
    """Complete security-staff profile."""

    id: int
    user_id: int
    email: str | None = None
    created_at: datetime


class SecurityStaffListItem(SecurityStaffBase):
    """Security-staff entry returned to administrators."""

    id: int


class SecurityStaffListResponse(BaseSchema):
    """Security-staff collection with an explicit total."""

    security_staff: list[SecurityStaffListItem]
    total: int = Field(ge=0)


class VerificationAction(StrEnum):
    """Gate operation performed with a checkout QR token."""

    CHECKOUT = "CHECKOUT"
    CHECKIN = "CHECKIN"


class VerifyQRRequest(BaseSchema):
    """Secure token scanned from a student's QR code."""

    qr_token: str = Field(min_length=1, max_length=512)
    action: VerificationAction = VerificationAction.CHECKOUT


class VerifyQRResponse(BaseSchema):
    """Verified student and checkout information."""

    student: StudentPublic
    checkout: CheckoutResponse
    verification_successful: bool


SecurityStaffResponse = SecurityProfileResponse
QRVerificationRequest = VerifyQRRequest
QRVerificationResponse = VerifyQRResponse
