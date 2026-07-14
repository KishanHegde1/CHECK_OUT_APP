"""Compatibility exports for FastAPI dependencies."""

from app.core.dependencies import (
    AdminUser,
    CurrentUser,
    DatabaseSession,
    SecurityUser,
    StudentUser,
    get_current_user,
    oauth2_scheme,
    require_roles,
)

__all__ = [
    "AdminUser",
    "CurrentUser",
    "DatabaseSession",
    "SecurityUser",
    "StudentUser",
    "get_current_user",
    "oauth2_scheme",
    "require_roles",
]
