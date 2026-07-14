"""Security-staff endpoints."""

from fastapi import APIRouter

from app.core.dependencies import DatabaseSession, SecurityUser
from app.schemas.common import APIResponse
from app.schemas.security import (
    SecurityProfileResponse,
    VerifyQRRequest,
    VerifyQRResponse,
)
from app.services import security_service
from app.utils.response import success_response

router = APIRouter(prefix="/security", tags=["Security"])


@router.get("/profile", response_model=APIResponse[SecurityProfileResponse])
def profile(
    db: DatabaseSession,
    current_user: SecurityUser,
) -> dict[str, object]:
    """Return the authenticated security-staff profile."""

    result = security_service.get_profile(db, current_user)
    return success_response(result, "Security profile retrieved")


@router.post("/verify-qr", response_model=APIResponse[VerifyQRResponse])
def verify_qr(
    payload: VerifyQRRequest,
    db: DatabaseSession,
    current_user: SecurityUser,
) -> dict[str, object]:
    """Validate a checkout token and persist verification audit fields."""

    result = security_service.verify_qr(db, current_user, payload)
    return success_response(result, "QR verification successful")
