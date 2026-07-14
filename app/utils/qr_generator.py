"""Generate opaque QR tokens and public checkout identifiers."""

from __future__ import annotations

import re
import secrets

DEFAULT_TOKEN_BYTES = 32
DEFAULT_ID_BYTES = 8
_VALID_PREFIX = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")


def generate_secure_token(byte_length: int = DEFAULT_TOKEN_BYTES) -> str:
    """Return a cryptographically secure URL-safe random token."""

    if byte_length < 16:
        raise ValueError("byte_length must be at least 16")
    return secrets.token_urlsafe(byte_length)


def generate_qr_token(byte_length: int = DEFAULT_TOKEN_BYTES) -> str:
    """Return the opaque value that Flutter encodes into a QR image."""

    return generate_secure_token(byte_length)


def generate_checkout_id(
    prefix: str = "CHK",
    random_bytes: int = DEFAULT_ID_BYTES,
) -> str:
    """Return a collision-resistant human-readable checkout identifier."""

    normalized_prefix = prefix.strip().upper()
    if not _VALID_PREFIX.fullmatch(normalized_prefix):
        raise ValueError("prefix must contain only letters, digits, and hyphens")
    if random_bytes < 6:
        raise ValueError("random_bytes must be at least 6")

    random_part = secrets.token_hex(random_bytes).upper()
    return f"{normalized_prefix}-{random_part}"


__all__ = [
    "generate_checkout_id",
    "generate_qr_token",
    "generate_secure_token",
]
