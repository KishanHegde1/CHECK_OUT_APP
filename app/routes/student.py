"""Student-only endpoints."""

from fastapi import APIRouter, status

from app.core.dependencies import DatabaseSession, StudentUser
from app.schemas.checkout import CheckoutCreate, CheckoutResponse
from app.schemas.common import APIResponse
from app.schemas.student import StudentProfileResponse
from app.services import student_service
from app.utils.response import success_response

router = APIRouter(prefix="/student", tags=["Student"])


@router.get("/profile", response_model=APIResponse[StudentProfileResponse])
def profile(
    db: DatabaseSession,
    current_user: StudentUser,
) -> dict[str, object]:
    """Return the authenticated student's hostel profile."""

    result = student_service.get_profile(db, current_user)
    return success_response(result, "Student profile retrieved")


@router.get("/checkouts", response_model=APIResponse[list[CheckoutResponse]])
def checkouts(
    db: DatabaseSession,
    current_user: StudentUser,
) -> dict[str, object]:
    """Return the authenticated student's checkout history."""

    result = student_service.list_checkouts(db, current_user)
    return success_response(result, "Student checkouts retrieved")


@router.post(
    "/checkouts",
    response_model=APIResponse[CheckoutResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_checkout(
    payload: CheckoutCreate,
    db: DatabaseSession,
    current_user: StudentUser,
) -> dict[str, object]:
    """Generate an active checkout and its opaque QR token."""

    result = student_service.create_checkout(db, current_user, payload)
    return success_response(result, "Checkout created successfully")


@router.get(
    "/checkouts/active",
    response_model=APIResponse[CheckoutResponse],
)
def active_checkout(
    db: DatabaseSession,
    current_user: StudentUser,
) -> dict[str, object]:
    """Return the current active checkout without generating a new QR token."""

    result = student_service.get_active_checkout(db, current_user)
    return success_response(result, "Active checkout retrieved")


@router.get(
    "/checkouts/{checkout_id}",
    response_model=APIResponse[CheckoutResponse],
)
def checkout_detail(
    checkout_id: str,
    db: DatabaseSession,
    current_user: StudentUser,
) -> dict[str, object]:
    """Return one checkout owned by the authenticated student."""

    result = student_service.get_checkout(db, current_user, checkout_id)
    return success_response(result, "Checkout retrieved")
