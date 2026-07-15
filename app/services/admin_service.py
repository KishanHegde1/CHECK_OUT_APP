"""Administrator student-management, query, and dashboard services."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import APIError
from app.core.security import hash_password
from app.models.admin import Admin
from app.models.checkout import Checkout
from app.models.enums import CheckoutStatus, Gender, HostelStatus, UserRole
from app.models.security_staff import SecurityStaff
from app.models.student import Student
from app.models.user import User
from app.schemas.admin import (
    AdminProfileResponse,
    AdminStudentDetailResponse,
    DashboardResponse,
    OutsideStudentResponse,
)
from app.schemas.checkout import CheckoutResponse
from app.schemas.notification import NotificationResponse
from app.schemas.security import SecurityStaffListItem
from app.schemas.student import StudentCreate, StudentProfileResponse, StudentUpdate
from app.services.checkout_service import (
    list_all_checkouts as query_all_checkouts,
)
from app.services.checkout_service import list_student_checkouts
from app.services.notification_service import list_notifications
from app.services.student_service import to_student_profile

MAX_USERNAME_LENGTH = 50


def get_admin_for_user(db: Session, user: User) -> Admin:
    """Resolve the administrator profile for an authenticated account."""

    admin = db.scalar(
        select(Admin).options(joinedload(Admin.user)).where(Admin.user_id == user.id)
    )
    if admin is None:
        raise APIError(status_code=404, message="Admin profile not found")
    return admin


def get_profile(db: Session, user: User) -> AdminProfileResponse:
    """Return the authenticated administrator's profile."""

    admin = get_admin_for_user(db, user)
    return AdminProfileResponse(
        id=admin.id,
        user_id=admin.user_id,
        admin_id=admin.admin_id,
        full_name=admin.full_name,
        phone=admin.phone,
        email=admin.user.email if admin.user else None,
        created_at=admin.created_at,
    )


def _student_query(identifier: str):  # type: ignore[no-untyped-def]
    """Build a lookup accepting a numeric key or a case-insensitive USN."""

    conditions = [func.upper(Student.student_id) == identifier.upper()]
    if identifier.isdigit():
        conditions.append(Student.id == int(identifier))
    return select(Student).options(joinedload(Student.user)).where(or_(*conditions))


def _get_student_or_404(db: Session, identifier: str) -> Student:
    """Return a student and user relationship or a safe not-found response."""

    student = db.scalar(_student_query(identifier))
    if student is None:
        raise APIError(status_code=404, message="Student not found")
    if student.user is None:
        raise APIError(status_code=409, message="Student account is incomplete")
    return student


def _validate_username_length(full_name: str) -> None:
    """Keep the full-name login convention within users.username's limit."""

    if len(full_name) > MAX_USERNAME_LENGTH:
        raise APIError(
            status_code=422,
            message=(
                "Full name must not exceed 50 characters because it is used "
                "as the login username"
            ),
        )


def _raise_if_duplicate_student_values(
    db: Session,
    *,
    full_name: str,
    email: str,
    student_id: str,
    excluding_user_id: int | None = None,
    excluding_student_id: int | None = None,
) -> None:
    """Return clear conflict errors before attempting the atomic write."""

    username_query = select(User.id).where(
        func.lower(User.username) == full_name.lower()
    )
    email_query = select(User.id).where(func.lower(User.email) == email.lower())
    student_query = select(Student.id).where(Student.student_id == student_id)
    if excluding_user_id is not None:
        username_query = username_query.where(User.id != excluding_user_id)
        email_query = email_query.where(User.id != excluding_user_id)
    if excluding_student_id is not None:
        student_query = student_query.where(Student.id != excluding_student_id)

    if db.scalar(username_query) is not None:
        raise APIError(
            status_code=409, message="A student with this full name already exists"
        )
    if db.scalar(email_query) is not None:
        raise APIError(status_code=409, message="Email already exists")
    if db.scalar(student_query) is not None:
        raise APIError(status_code=409, message="Student ID already exists")


def _student_from_payload(payload: StudentCreate, user: User) -> Student:
    """Create a profile object without committing it separately from its user."""

    return Student(
        user=user,
        student_id=payload.student_id,
        full_name=payload.full_name,
        room_number=payload.room_number,
        department=payload.department,
        year=payload.year,
        phone=payload.phone,
        parent_phone=payload.parent_phone,
        hostel_status=payload.hostel_status,
        photo_url=payload.photo_url,
        gender=payload.gender,
        emergency_contact_name=payload.emergency_contact_name,
        hostel_block=payload.hostel_block,
    )


def create_student(
    db: Session,
    payload: StudentCreate,
    *,
    commit: bool = True,
) -> StudentProfileResponse:
    """Atomically create a student account and its profile.

    The initial password is the student ID, but only its bcrypt hash is ever
    persisted. ``commit=False`` is used by row-level import savepoints.
    """

    _validate_username_length(payload.full_name)
    _raise_if_duplicate_student_values(
        db,
        full_name=payload.full_name,
        email=payload.email,
        student_id=payload.student_id,
    )
    user = User(
        username=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.student_id),
        role=UserRole.STUDENT,
        is_active=True,
    )
    student = _student_from_payload(payload, user)
    db.add(student)
    try:
        db.flush()
        if commit:
            db.commit()
    except IntegrityError as exc:
        if commit:
            db.rollback()
        raise APIError(
            status_code=409,
            message="The student conflicts with existing account data",
        ) from exc
    except SQLAlchemyError as exc:
        if commit:
            db.rollback()
        raise APIError(
            status_code=503, message="Database service is unavailable"
        ) from exc

    if commit:
        db.refresh(student)
    return to_student_profile(student)


def update_student(
    db: Session,
    identifier: str,
    payload: StudentUpdate,
) -> StudentProfileResponse:
    """Update a student and matching login fields in one transaction."""

    student = _get_student_or_404(db, identifier)
    user = student.user
    values = payload.model_dump(exclude_unset=True)
    for required_field in (
        "student_id",
        "full_name",
        "email",
        "room_number",
        "department",
        "year",
        "phone",
        "parent_phone",
        "hostel_status",
    ):
        if required_field in values and values[required_field] is None:
            raise APIError(status_code=422, message=f"{required_field} cannot be null")

    next_student_id = values.get("student_id", student.student_id)
    next_full_name = values.get("full_name", student.full_name)
    next_email = values.get("email", user.email)
    _validate_username_length(next_full_name)
    _raise_if_duplicate_student_values(
        db,
        full_name=next_full_name,
        email=next_email,
        student_id=next_student_id,
        excluding_user_id=user.id,
        excluding_student_id=student.id,
    )

    if "full_name" in values:
        student.full_name = next_full_name
        user.username = next_full_name
    if "email" in values:
        user.email = next_email
    if "is_active" in values:
        user.is_active = values["is_active"]
    for field in (
        "student_id",
        "room_number",
        "department",
        "year",
        "phone",
        "parent_phone",
        "hostel_status",
        "photo_url",
        "gender",
        "emergency_contact_name",
        "hostel_block",
    ):
        if field in values:
            setattr(student, field, values[field])

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise APIError(
            status_code=409,
            message="The student conflicts with existing account data",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise APIError(
            status_code=503, message="Database service is unavailable"
        ) from exc
    db.refresh(student)
    return to_student_profile(student)


def set_student_active(
    db: Session,
    identifier: str,
    *,
    is_active: bool,
) -> StudentProfileResponse:
    """Activate or deactivate login access without deleting history."""

    student = _get_student_or_404(db, identifier)
    student.user.is_active = is_active
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise APIError(
            status_code=503, message="Database service is unavailable"
        ) from exc
    db.refresh(student)
    return to_student_profile(student)


def get_dashboard(db: Session) -> DashboardResponse:
    """Return active-student counts and each outside student's current checkout."""

    active_student = Student.user.has(User.is_active.is_(True))
    total_students = (
        db.scalar(select(func.count(Student.id)).where(active_student)) or 0
    )
    total_inside = (
        db.scalar(
            select(func.count(Student.id)).where(
                active_student, Student.hostel_status == HostelStatus.INSIDE
            )
        )
        or 0
    )
    total_outside = (
        db.scalar(
            select(func.count(Student.id)).where(
                active_student, Student.hostel_status == HostelStatus.OUTSIDE
            )
        )
        or 0
    )

    # The correlated lookup uses the existing (student_id, status) checkout
    # index and ensures a historical completed checkout is never selected.
    latest_active_checkout_id = (
        select(Checkout.id)
        .where(
            Checkout.student_id == Student.id,
            Checkout.status == CheckoutStatus.ACTIVE,
        )
        .order_by(Checkout.checkout_time.desc(), Checkout.id.desc())
        .limit(1)
        .correlate(Student)
        .scalar_subquery()
    )
    outside_rows = db.execute(
        select(Student, Checkout)
        .join(User, User.id == Student.user_id)
        .join(Checkout, Checkout.id == latest_active_checkout_id)
        .where(
            User.is_active.is_(True),
            Student.hostel_status == HostelStatus.OUTSIDE,
        )
        .order_by(Checkout.checkout_time.desc(), Checkout.id.desc())
    ).all()
    outside_students = [
        OutsideStudentResponse(
            id=student.id,
            student_id=student.student_id,
            full_name=student.full_name,
            room_number=student.room_number,
            department=student.department,
            year=student.year,
            checkout_id=checkout.checkout_id,
            checkout_time=checkout.checkout_time,
            reason=(checkout.reason or "Not provided").strip() or "Not provided",
            status=checkout.status,
        )
        for student, checkout in outside_rows
    ]
    active_checkouts = (
        db.scalar(
            select(func.count(Checkout.id)).where(
                Checkout.status == CheckoutStatus.ACTIVE
            )
        )
        or 0
    )
    pending_requests = (
        db.scalar(
            select(func.count(Checkout.id)).where(
                Checkout.status == CheckoutStatus.PENDING
            )
        )
        or 0
    )
    security_staff_count = db.scalar(select(func.count(SecurityStaff.id))) or 0
    return DashboardResponse(
        total_students=total_students,
        total_inside=total_inside,
        total_outside=total_outside,
        outside_students=outside_students,
        students_inside=total_inside,
        students_outside=total_outside,
        active_checkouts=active_checkouts,
        pending_requests=pending_requests,
        security_staff_count=security_staff_count,
    )


def list_students(
    db: Session,
    *,
    search: str | None = None,
    department: str | None = None,
    year: str | None = None,
    room_number: str | None = None,
    hostel_block: str | None = None,
    gender: Gender | None = None,
    hostel_status: HostelStatus | None = None,
    is_active: bool | None = None,
) -> list[StudentProfileResponse]:
    """Return student profiles using optional indexed admin filters."""

    statement = select(Student).options(joinedload(Student.user))
    if search:
        pattern = f"%{search.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Student.full_name).like(pattern),
                func.lower(Student.student_id).like(pattern),
            )
        )
    if department:
        statement = statement.where(Student.department == department)
    if year:
        statement = statement.where(Student.year == year)
    if room_number:
        statement = statement.where(Student.room_number == room_number)
    if hostel_block:
        statement = statement.where(Student.hostel_block == hostel_block)
    if gender is not None:
        statement = statement.where(Student.gender == gender)
    if hostel_status is not None:
        statement = statement.where(Student.hostel_status == hostel_status)
    if is_active is not None:
        statement = statement.where(Student.user.has(User.is_active == is_active))
    statement = statement.order_by(Student.student_id.asc())
    return [to_student_profile(student) for student in db.scalars(statement).all()]


def get_student(
    db: Session,
    identifier: str,
) -> AdminStudentDetailResponse:
    """Return a student by numeric ID or public student ID with history."""

    student = _get_student_or_404(db, identifier)
    return AdminStudentDetailResponse(
        student=to_student_profile(student),
        checkouts=list_student_checkouts(db, student.id),
    )


def list_checkouts(
    db: Session,
    status: CheckoutStatus | None = None,
) -> list[CheckoutResponse]:
    """Return checkout records for administrators."""

    return query_all_checkouts(db, status=status)


def list_security_staff(db: Session) -> list[SecurityStaffListItem]:
    """Return every security-staff profile."""

    statement = select(SecurityStaff).order_by(SecurityStaff.staff_id.asc())
    return [
        SecurityStaffListItem.model_validate(item)
        for item in db.scalars(statement).all()
    ]


def get_notifications(db: Session) -> list[NotificationResponse]:
    """Return global admin notifications."""

    return list_notifications(db)


__all__ = [
    "create_student",
    "get_admin_for_user",
    "get_dashboard",
    "get_notifications",
    "get_profile",
    "get_student",
    "list_checkouts",
    "list_security_staff",
    "list_students",
    "set_student_active",
    "update_student",
]
