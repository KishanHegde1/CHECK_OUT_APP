"""Authentication request and response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, ConfigDict, Field, field_validator

from app.models.enums import UserRole

from .common import BaseSchema


class LoginRequest(BaseSchema):
    """Credentials accepted by the login endpoint.

    The Flutter interface labels the identifier as ``user_id`` while the
    database calls it ``username``. Both JSON spellings are accepted, with
    ``username`` retained as the canonical Python/API field.
    """

    model_config = ConfigDict(str_strip_whitespace=False)

    username: str = Field(
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("username", "user_id", "userId", "email"),
    )
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("username", mode="after")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        """Trim the identifier without mutating the submitted password."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("username must not be blank")
        return normalized


class LoginResponse(BaseSchema):
    """JWT credentials and principal information returned after login."""

    access_token: str = Field(min_length=1)
    token_type: str = "bearer"
    role: UserRole
    user_id: int


class TokenData(BaseSchema):
    """Validated claims extracted from a JWT access token."""

    user_id: int | None = Field(
        default=None,
        validation_alias=AliasChoices("user_id", "sub"),
    )
    role: UserRole | None = None


class CurrentUserResponse(BaseSchema):
    """Public account fields returned by ``GET /api/auth/me``."""

    user_id: int = Field(validation_alias=AliasChoices("user_id", "id"))
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


UserResponse = CurrentUserResponse
TokenResponse = LoginResponse
