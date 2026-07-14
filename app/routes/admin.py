"""Administrator endpoints."""

from fastapi import APIRouter, File, UploadFile, status

from app.core.dependencies import AdminUser, DatabaseSession
from app.models.enums import CheckoutStatus, Gender, HostelStatus
from app.schemas.admin import AdminStudentDetailResponse, DashboardResponse
from app.schemas.checkout import CheckoutResponse
from app.schemas.common import APIResponse
from app.schemas.security import SecurityStaffListItem
from app.schemas.student import (
    StudentCreate,
    StudentImportResult,
    StudentProfileResponse,
    StudentUpdate,
)
from app.services import admin_service, student_import_service
from app.utils.response import success_response

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard", response_model=APIResponse[DashboardResponse])
def dashboard(
    db: DatabaseSession,
    _current_user: AdminUser,
) -> dict[str, object]:
    """Return database-derived dashboard metrics."""

    return success_response(admin_service.get_dashboard(db), "Dashboard retrieved")


@router.get(
    "/students",
    response_model=APIResponse[list[StudentProfileResponse]],
)
def students(
    db: DatabaseSession,
    _current_user: AdminUser,
    search: str | None = None,
    department: str | None = None,
    year: str | None = None,
    room_number: str | None = None,
    hostel_block: str | None = None,
    gender: Gender | None = None,
    hostel_status: HostelStatus | None = None,
    is_active: bool | None = None,
) -> dict[str, object]:
    """Return student profiles with optional compatibility-preserving filters."""

    result = admin_service.list_students(
        db,
        search=search,
        department=department,
        year=year,
        room_number=room_number,
        hostel_block=hostel_block,
        gender=gender,
        hostel_status=hostel_status,
        is_active=is_active,
    )
    return success_response(result, "Students retrieved")


@router.post(
    "/students",
    response_model=APIResponse[StudentProfileResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_student(
    payload: StudentCreate,
    db: DatabaseSession,
    _current_user: AdminUser,
) -> dict[str, object]:
    """Provision a student user and linked profile in one transaction."""

    result = admin_service.create_student(db, payload)
    return success_response(result, "Student created successfully")


@router.post(
    "/students/import",
    response_model=APIResponse[StudentImportResult],
)
async def import_students(
    db: DatabaseSession,
    _current_user: AdminUser,
    file: UploadFile = File(...),
) -> dict[str, object]:
    """Import CSV/XLSX students in memory without retaining upload files."""

    result = await student_import_service.import_students(db, file)
    return success_response(result, "Student import completed")


@router.post(
    "/students/{student_id}/deactivate",
    response_model=APIResponse[StudentProfileResponse],
)
def deactivate_student(
    student_id: str,
    db: DatabaseSession,
    _current_user: AdminUser,
) -> dict[str, object]:
    """Disable a student account while preserving profile and checkout history."""

    result = admin_service.set_student_active(db, student_id, is_active=False)
    return success_response(result, "Student deactivated")


@router.post(
    "/students/{student_id}/activate",
    response_model=APIResponse[StudentProfileResponse],
)
def activate_student(
    student_id: str,
    db: DatabaseSession,
    _current_user: AdminUser,
) -> dict[str, object]:
    """Restore a previously deactivated student account."""

    result = admin_service.set_student_active(db, student_id, is_active=True)
    return success_response(result, "Student activated")


@router.patch(
    "/students/{student_id}",
    response_model=APIResponse[StudentProfileResponse],
)
def update_student(
    student_id: str,
    payload: StudentUpdate,
    db: DatabaseSession,
    _current_user: AdminUser,
) -> dict[str, object]:
    """Update a student profile and matching login fields atomically."""

    result = admin_service.update_student(db, student_id, payload)
    return success_response(result, "Student updated successfully")


@router.get(
    "/students/{student_id}",
    response_model=APIResponse[AdminStudentDetailResponse],
)
def student_detail(
    student_id: str,
    db: DatabaseSession,
    _current_user: AdminUser,
) -> dict[str, object]:
    """Return a student and their checkout history."""

    return success_response(
        admin_service.get_student(db, student_id), "Student retrieved"
    )


@router.get("/checkouts", response_model=APIResponse[list[CheckoutResponse]])
def checkouts(
    db: DatabaseSession,
    _current_user: AdminUser,
    status: CheckoutStatus | None = None,
) -> dict[str, object]:
    """Return all checkouts, optionally filtered by status."""

    result = admin_service.list_checkouts(db, status=status)
    return success_response(result, "Checkouts retrieved")


@router.get(
    "/checkouts/active",
    response_model=APIResponse[list[CheckoutResponse]],
)
def active_checkouts(
    db: DatabaseSession,
    _current_user: AdminUser,
) -> dict[str, object]:
    """Return active checkout passes."""

    result = admin_service.list_checkouts(db, status=CheckoutStatus.ACTIVE)
    return success_response(result, "Active checkouts retrieved")


@router.get(
    "/security-staff",
    response_model=APIResponse[list[SecurityStaffListItem]],
)
def security_staff(
    db: DatabaseSession,
    _current_user: AdminUser,
) -> dict[str, object]:
    """Return configured security-staff profiles."""

    result = admin_service.list_security_staff(db)
    return success_response(result, "Security staff retrieved")
