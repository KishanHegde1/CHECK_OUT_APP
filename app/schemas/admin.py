"""Administrator-facing response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.models.enums import CheckoutStatus

from .checkout import CheckoutResponse
from .common import BaseSchema
from .student import StudentProfileResponse


class AdminProfileResponse(BaseSchema):
    """Public administrator profile."""

    id: int
    user_id: int
    admin_id: str
    full_name: str
    phone: str | None = None
    email: str | None = None
    created_at: datetime


class OutsideStudentResponse(BaseSchema):
    """An active student's current checkout shown on the dashboard."""

    id: int
    student_id: str
    full_name: str
    room_number: str
    department: str
    year: str
    checkout_id: str
    checkout_time: datetime
    reason: str
    status: CheckoutStatus


class DashboardResponse(BaseSchema):
    """Database-derived counts displayed by the admin dashboard."""

    total_students: int = Field(ge=0)
    total_inside: int = Field(ge=0)
    total_outside: int = Field(ge=0)
    outside_students: list[OutsideStudentResponse] = Field(default_factory=list)

    # Retained for existing dashboard clients that use the original field names.
    students_inside: int = Field(ge=0)
    students_outside: int = Field(ge=0)
    active_checkouts: int = Field(ge=0)
    pending_requests: int = Field(ge=0)
    security_staff_count: int = Field(ge=0)


class AdminStudentDetailResponse(BaseSchema):
    """Full student profile and the checkout records shown by administrators."""

    student: StudentProfileResponse
    checkouts: list[CheckoutResponse] = Field(default_factory=list)


AdminResponse = AdminProfileResponse
