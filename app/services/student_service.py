"""Student profile and checkout orchestration."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import APIError
from app.models.student import Student
from app.models.user import User
from app.schemas.checkout import CheckoutCreate, CheckoutResponse
from app.schemas.student import StudentProfileResponse
from app.services import checkout_service


def get_student_for_user(db: Session, user: User) -> Student:
    """Resolve the student profile belonging to an authenticated user."""

    student = db.scalar(
        select(Student)
        .options(joinedload(Student.user))
        .where(Student.user_id == user.id)
    )
    if student is None:
        raise APIError(status_code=404, message="Student profile not found")
    return student


def to_student_profile(student: Student) -> StudentProfileResponse:
    """Convert a student and account relationship to a response schema."""

    return StudentProfileResponse(
        id=student.id,
        user_id=student.user_id,
        student_id=student.student_id,
        full_name=student.full_name,
        room_number=student.room_number,
        department=student.department,
        year=student.year,
        phone=student.phone,
        parent_phone=student.parent_phone,
        hostel_status=student.hostel_status,
        photo_url=student.photo_url,
        gender=student.gender,
        emergency_contact_name=student.emergency_contact_name,
        hostel_block=student.hostel_block,
        email=student.user.email if student.user else None,
        created_at=student.created_at,
        updated_at=student.updated_at,
    )


def get_profile(db: Session, user: User) -> StudentProfileResponse:
    """Return the authenticated student's profile."""

    return to_student_profile(get_student_for_user(db, user))


def create_checkout(
    db: Session,
    user: User,
    payload: CheckoutCreate,
) -> CheckoutResponse:
    """Create a checkout for the authenticated student."""

    student = get_student_for_user(db, user)
    return checkout_service.create_checkout(db, student, payload)


def list_checkouts(db: Session, user: User) -> list[CheckoutResponse]:
    """Return the authenticated student's checkout history."""

    student = get_student_for_user(db, user)
    return checkout_service.list_student_checkouts(db, student.id)


def get_active_checkout(db: Session, user: User) -> CheckoutResponse:
    """Return the current active checkout and its original stored QR token."""

    student = get_student_for_user(db, user)
    return checkout_service.get_active_student_checkout(db, student.id)


def get_checkout(
    db: Session,
    user: User,
    checkout_identifier: str,
) -> CheckoutResponse:
    """Return one checkout owned by the authenticated student."""

    student = get_student_for_user(db, user)
    return checkout_service.get_student_checkout(
        db,
        student.id,
        checkout_identifier,
    )


__all__ = [
    "create_checkout",
    "get_active_checkout",
    "get_checkout",
    "get_profile",
    "get_student_for_user",
    "list_checkouts",
    "to_student_profile",
]
