"""Administrator notification endpoints."""

from fastapi import APIRouter

from app.core.dependencies import AdminUser, DatabaseSession
from app.schemas.common import APIResponse
from app.schemas.notification import NotificationResponse
from app.services import admin_service
from app.utils.response import success_response

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/notifications",
    response_model=APIResponse[list[NotificationResponse]],
)
def notifications(
    db: DatabaseSession,
    _current_user: AdminUser,
) -> dict[str, object]:
    """Return global administrative notifications."""

    result = admin_service.get_notifications(db)
    return success_response(result, "Notifications retrieved")
