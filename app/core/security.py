"""Password hashing and JWT access-token primitives."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Any

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.core.config import get_settings
from app.core.exceptions import APIError

BCRYPT_MAX_PASSWORD_BYTES = 72
BCRYPT_ROUNDS = 12
AUTHENTICATION_HEADERS = {"WWW-Authenticate": "Bearer"}


def _password_bytes(password: str) -> bytes:
    """Encode and validate a password for bcrypt without silent truncation."""

    encoded = password.encode("utf-8")
    if not encoded:
        raise ValueError("Password must not be empty")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError("Password must not exceed 72 UTF-8 bytes")
    return encoded


def hash_password(password: str) -> str:
    """Return a bcrypt hash for a validated plaintext password."""

    password_bytes = _password_bytes(password)
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Safely compare a plaintext password with a stored bcrypt hash."""

    try:
        password_bytes = _password_bytes(plain_password)
        hash_bytes = password_hash.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except (TypeError, UnicodeError, ValueError):
        return False


def create_access_token(
    subject: str | int,
    *,
    expires_delta: timedelta | None = None,
    additional_claims: Mapping[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token for a user identifier."""

    settings = get_settings()
    issued_at = datetime.now(UTC)
    expires_at = issued_at + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )

    claims: dict[str, Any] = dict(additional_claims or {})
    claims.update(
        {
            "sub": str(subject),
            "iat": issued_at,
            "exp": expires_at,
            "jti": token_urlsafe(24),
            "type": "access",
        }
    )
    return jwt.encode(
        claims,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate and decode an access token or raise a safe API error."""

    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["sub", "iat", "exp", "type"]},
        )
    except InvalidTokenError as exc:
        raise APIError(
            401,
            "Could not validate credentials",
            headers=AUTHENTICATION_HEADERS,
        ) from exc

    if payload.get("type") != "access":
        raise APIError(
            401,
            "Could not validate credentials",
            headers=AUTHENTICATION_HEADERS,
        )
    return payload


def get_password_hash(password: str) -> str:
    """Compatibility alias for callers using conventional auth naming."""

    return hash_password(password)
