"""Authentication, database, and role-based FastAPI dependencies."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import APIError
from app.core.security import AUTHENTICATION_HEADERS, decode_access_token
from app.models.enums import UserRole
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{get_settings().api_prefix}/auth/login",
    description=(
        "JWT bearer authentication. Login accepts JSON and returns the "
        "standard API envelope."
    ),
)

DatabaseSession = Annotated[Session, Depends(get_db)]
AccessToken = Annotated[str, Depends(oauth2_scheme)]


def get_current_user(token: AccessToken, db: DatabaseSession) -> User:
    """Decode a bearer token and reload its active user from the database."""

    payload = decode_access_token(token)
    subject = payload.get("sub")
    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise APIError(
            401,
            "Could not validate credentials",
            headers=AUTHENTICATION_HEADERS,
        ) from exc

    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise APIError(
            401,
            "Could not validate credentials",
            headers=AUTHENTICATION_HEADERS,
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(
    *allowed_roles: UserRole,
) -> Callable[[CurrentUser], User]:
    """Build a dependency that rejects authenticated users of other roles."""

    allowed = frozenset(allowed_roles)
    if not allowed:
        raise ValueError("At least one role is required")

    def role_dependency(current_user: CurrentUser) -> User:
        if current_user.role not in allowed:
            raise APIError(403, "You do not have permission to access this resource")
        return current_user

    return role_dependency


require_student = require_roles(UserRole.STUDENT)
require_admin = require_roles(UserRole.ADMIN)
require_security = require_roles(UserRole.SECURITY)

StudentUser = Annotated[User, Depends(require_student)]
AdminUser = Annotated[User, Depends(require_admin)]
SecurityUser = Annotated[User, Depends(require_security)]
