"""Checkout request and response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from app.models.enums import CheckoutStatus

from .common import BaseSchema


class CheckoutCreate(BaseSchema):
    """Optional details supplied when a student creates a checkout."""

    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason", mode="after")
    @classmethod
    def empty_reason_is_none(cls, value: str | None) -> str | None:
        """Store an omitted and a whitespace-only reason consistently."""

        return value or None


class CheckoutResponse(BaseSchema):
    """Checkout data enriched with the public student fields used by Flutter."""

    id: int
    checkout_id: str
    student_id: str
    student_name: str
    room_number: str
    department: str | None = None
    year: str | None = None
    photo_url: str | None = None
    checkout_time: datetime
    checkin_time: datetime | None = None
    reason: str | None = None
    qr_token: str
    status: CheckoutStatus
    verified_by: int | None = None
    verified_at: datetime | None = None
    created_at: datetime


class CheckoutListResponse(BaseSchema):
    """Checkout collection payload with an explicit total."""

    checkouts: list[CheckoutResponse]
    total: int = Field(ge=0)


class CheckoutCheckin(BaseSchema):
    """Internal command used to record a student's return."""

    checkin_time: datetime | None = None


class QRTokenResponse(BaseSchema):
    """The non-image QR payload returned by the backend."""

    checkout_id: str
    qr_token: str


CheckoutDetailResponse = CheckoutResponse
