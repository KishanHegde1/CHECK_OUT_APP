"""Small, side-effect-free helpers shared by services."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Normalize an aware timestamp to UTC.

    Naive timestamps are treated as UTC because database timestamps in this
    project are defined in UTC.
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def normalize_optional_text(value: str | None) -> str | None:
    """Trim optional text and convert an empty result to ``None``."""

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def calculate_offset(page: int, page_size: int) -> int:
    """Return a SQL offset for a one-indexed page."""

    if page < 1:
        raise ValueError("page must be at least 1")
    if page_size < 1:
        raise ValueError("page_size must be at least 1")
    return (page - 1) * page_size


def enum_value(value: Any) -> Any:
    """Return an enum's wire value and pass other values through unchanged."""

    return value.value if isinstance(value, Enum) else value


__all__ = [
    "calculate_offset",
    "ensure_utc",
    "enum_value",
    "normalize_optional_text",
    "utc_now",
]
