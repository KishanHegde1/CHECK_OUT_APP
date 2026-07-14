"""Student request and response schemas."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import Field, field_validator

from app.models.enums import Gender, HostelStatus

from .common import BaseSchema


class StudentBase(BaseSchema):
    """Fields shared by student profile representations."""

    student_id: str = Field(min_length=1, max_length=50)
    full_name: str = Field(min_length=1, max_length=150)
    room_number: str = Field(min_length=1, max_length=30)
    department: str = Field(min_length=1, max_length=100)
    year: str = Field(min_length=1, max_length=30)
    phone: str = Field(min_length=1, max_length=30)
    parent_phone: str = Field(min_length=1, max_length=30)
    hostel_status: HostelStatus = HostelStatus.INSIDE
    photo_url: str | None = Field(default=None, max_length=2048)
    gender: Gender | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=150)
    hostel_block: str | None = Field(default=None, max_length=50)

    @field_validator("student_id", mode="after")
    @classmethod
    def normalize_student_id(cls, value: str) -> str:
        """Use a stable uppercase USN/student-ID convention."""

        normalized = value.upper()
        if not normalized:
            raise ValueError("student_id must not be blank")
        return normalized

    @field_validator("phone", "parent_phone", mode="after")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        """Accept readable local or international phone numbers only."""

        if not re.fullmatch(r"[+0-9][0-9 ()-]{4,29}", value):
            raise ValueError(
                "phone must contain only digits, spaces, parentheses, +, or -"
            )
        return value


class StudentCreate(StudentBase):
    """Fields used when provisioning a student profile."""

    email: str = Field(min_length=3, max_length=320)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Validate and normalize the login email without an extra dependency."""

        normalized = value.lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("email must be valid")
        return normalized


class StudentUpdate(BaseSchema):
    """Editable student profile fields."""

    student_id: str | None = Field(default=None, min_length=1, max_length=50)
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    email: str | None = Field(default=None, min_length=3, max_length=320)
    room_number: str | None = Field(default=None, min_length=1, max_length=30)
    department: str | None = Field(default=None, min_length=1, max_length=100)
    year: str | None = Field(default=None, min_length=1, max_length=30)
    phone: str | None = Field(default=None, min_length=1, max_length=30)
    parent_phone: str | None = Field(default=None, min_length=1, max_length=30)
    hostel_status: HostelStatus | None = None
    photo_url: str | None = Field(default=None, max_length=2048)
    gender: Gender | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=150)
    hostel_block: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None

    @field_validator("student_id", mode="after")
    @classmethod
    def normalize_optional_student_id(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None

    @field_validator("email", mode="after")
    @classmethod
    def normalize_optional_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("email must be valid")
        return normalized

    @field_validator("phone", "parent_phone", mode="after")
    @classmethod
    def validate_optional_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return StudentBase.validate_phone(value)


class StudentPublic(BaseSchema):
    """Public student identity embedded in verification responses."""

    id: int
    student_id: str
    full_name: str
    room_number: str
    department: str
    year: str
    hostel_status: HostelStatus
    photo_url: str | None = None
    gender: Gender | None = None
    hostel_block: str | None = None


class StudentListItem(StudentPublic):
    """Compact student representation used by the admin list."""


class StudentProfileResponse(StudentBase):
    """Complete student profile returned to the student and administrators."""

    id: int
    user_id: int
    email: str | None = None
    created_at: datetime
    updated_at: datetime


class StudentListResponse(BaseSchema):
    """Student list payload with an explicit total."""

    students: list[StudentListItem]
    total: int = Field(ge=0)


StudentResponse = StudentProfileResponse
StudentDetailResponse = StudentProfileResponse


class StudentImportRow(StudentCreate):
    """One validated student row from a CSV or XLSX import file."""


class StudentImportError(BaseSchema):
    """A safe row-level error returned after a partial import."""

    row: int = Field(ge=2)
    message: str = Field(min_length=1)


class StudentImportResult(BaseSchema):
    """Counts and row-level failures from an in-memory student import."""

    total_rows: int = Field(ge=0)
    imported: int = Field(ge=0)
    failed: int = Field(ge=0)
    errors: list[StudentImportError] = Field(default_factory=list)
