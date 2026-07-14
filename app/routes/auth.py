"""Authentication endpoints."""

from fastapi import APIRouter, status

from app.core.dependencies import CurrentUser, DatabaseSession
from app.schemas.auth import CurrentUserResponse, LoginRequest, LoginResponse
from app.schemas.common import APIResponse
from app.services import auth_service
from app.utils.response import success_response

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=APIResponse[LoginResponse],
    status_code=status.HTTP_200_OK,
)
def login(payload: LoginRequest, db: DatabaseSession) -> dict[str, object]:
    """Authenticate credentials and issue a JWT bearer token."""

    result = auth_service.login(db, payload)
    return success_response(result, "Login successful")


@router.get("/me", response_model=APIResponse[CurrentUserResponse])
def me(current_user: CurrentUser) -> dict[str, object]:
    """Return the currently authenticated account."""

    result = auth_service.current_user_response(current_user)
    return success_response(result, "Current user retrieved")


@router.post("/logout", response_model=APIResponse[dict[str, str]])
def logout(current_user: CurrentUser) -> dict[str, object]:
    """Confirm logout so the client can discard its access token."""

    return success_response(
        {"user_id": str(current_user.id)},
        "Logout successful; discard the access token",
    )
