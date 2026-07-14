"""Authentication business logic."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import APIError
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import CurrentUserResponse, LoginRequest, LoginResponse

DUMMY_PASSWORD_HASH = "$2b$12$18clmiDf9y2A9UMs2Vv6NO77vVkHS8vsxta7n.z7dvK3wZZzh3kUq"


def authenticate_user(db: Session, payload: LoginRequest) -> User:
    """Validate a username/email and password without leaking account state."""

    identifier = payload.username.strip().lower()
    user = db.scalar(
        select(User).where(
            or_(
                func.lower(User.username) == identifier,
                func.lower(User.email) == identifier,
            )
        )
    )
    candidate_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_is_valid = verify_password(payload.password, candidate_hash)
    if user is None or not password_is_valid:
        raise APIError(
            status_code=401,
            message="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise APIError(status_code=403, message="User account is inactive")
    return user


def login(db: Session, payload: LoginRequest) -> LoginResponse:
    """Authenticate a user and issue a signed access token."""

    user = authenticate_user(db, payload)
    token = create_access_token(
        subject=user.id,
        additional_claims={"role": user.role.value},
    )
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
    )


def current_user_response(user: User) -> CurrentUserResponse:
    """Return the public account representation for the authenticated user."""

    return CurrentUserResponse(
        user_id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


__all__ = ["authenticate_user", "current_user_response", "login"]
