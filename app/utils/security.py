"""Compatibility exports for authentication primitives."""

from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    hash_password,
    verify_password,
)

__all__ = [
    "create_access_token",
    "decode_access_token",
    "get_password_hash",
    "hash_password",
    "verify_password",
]
