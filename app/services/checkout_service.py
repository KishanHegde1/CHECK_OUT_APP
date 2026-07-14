"""Checkout lifecycle business logic."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import APIError
from app.models.checkout import Checkout
from app.models.enums import CheckoutStatus, HostelStatus, NotificationType
from app.models.notification import Notification
from app.models.student import Student
from app.schemas.checkout import CheckoutCreate, CheckoutResponse
from app.services.qr_service import generate_checkout_id, generate_qr_token


def to_checkout_response(checkout: Checkout) -> CheckoutResponse:
    """Convert a checkout and its student relation to the public schema."""

    student = checkout.student
    return CheckoutResponse(
        id=checkout.id,
        checkout_id=checkout.checkout_id,
        student_id=student.student_id,
        student_name=student.full_name,
        room_number=student.room_number,
        department=student.department,
        year=student.year,
        photo_url=student.photo_url,
        checkout_time=checkout.checkout_time,
        checkin_time=checkout.checkin_time,
        reason=checkout.reason,
        qr_token=checkout.qr_token,
        status=checkout.status,
        verified_by=checkout.verified_by,
        verified_at=checkout.verified_at,
        created_at=checkout.created_at,
    )


def create_checkout(
    db: Session,
    student: Student,
    payload: CheckoutCreate,
) -> CheckoutResponse:
    """Create one active checkout pass for a student, atomically."""

    locked_student = db.scalar(
        select(Student).where(Student.id == student.id).with_for_update()
    )
    if locked_student is None:
        raise APIError(status_code=404, message="Student profile not found")

    active_checkout = db.scalar(
        select(Checkout).where(
            Checkout.student_id == locked_student.id,
            Checkout.status.in_((CheckoutStatus.PENDING, CheckoutStatus.ACTIVE)),
        )
    )
    if active_checkout is not None:
        raise APIError(
            status_code=409,
            message="An active checkout already exists for this student",
        )

    checkout = Checkout(
        checkout_id=generate_checkout_id(),
        student=locked_student,
        reason=payload.reason,
        qr_token=generate_qr_token(),
        status=CheckoutStatus.ACTIVE,
    )
    locked_student.hostel_status = HostelStatus.OUTSIDE
    notification = Notification(
        title="Checkout generated",
        message=(
            f"{locked_student.full_name} generated checkout pass "
            f"{checkout.checkout_id}."
        ),
        notification_type=NotificationType.CHECKOUT,
    )
    db.add_all((checkout, notification))

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise APIError(
            status_code=409,
            message="Could not create a unique checkout pass",
        ) from exc

    db.refresh(checkout)
    checkout.student = locked_student
    return to_checkout_response(checkout)


def list_student_checkouts(
    db: Session,
    student_id: int,
) -> list[CheckoutResponse]:
    """Return a student's checkout history, newest first."""

    statement = (
        select(Checkout)
        .options(joinedload(Checkout.student))
        .where(Checkout.student_id == student_id)
        .order_by(Checkout.created_at.desc(), Checkout.id.desc())
    )
    return [to_checkout_response(item) for item in db.scalars(statement).all()]


def get_active_student_checkout(
    db: Session,
    student_id: int,
) -> CheckoutResponse:
    """Return the student's persisted active checkout without changing its token."""

    checkout = db.scalar(
        select(Checkout)
        .options(joinedload(Checkout.student))
        .where(
            Checkout.student_id == student_id,
            Checkout.status == CheckoutStatus.ACTIVE,
        )
    )
    if checkout is None:
        raise APIError(status_code=404, message="No active checkout found")
    return to_checkout_response(checkout)


def get_student_checkout(
    db: Session,
    student_id: int,
    checkout_identifier: str,
) -> CheckoutResponse:
    """Return a checkout owned by the given student.

    Both the stable public ``checkout_id`` and the numeric database identifier
    are accepted. Ownership remains part of the query to prevent IDOR access.
    """

    predicates = [Checkout.checkout_id == checkout_identifier]
    if checkout_identifier.isdigit():
        predicates.append(Checkout.id == int(checkout_identifier))

    statement = (
        select(Checkout)
        .options(joinedload(Checkout.student))
        .where(
            Checkout.student_id == student_id,
            or_(*predicates),
        )
    )
    checkout = db.scalar(statement)
    if checkout is None:
        raise APIError(status_code=404, message="Checkout not found")
    return to_checkout_response(checkout)


def list_all_checkouts(
    db: Session,
    *,
    status: CheckoutStatus | None = None,
) -> list[CheckoutResponse]:
    """Return all checkout records, optionally filtered by status."""

    statement = select(Checkout).options(joinedload(Checkout.student))
    if status is not None:
        statement = statement.where(Checkout.status == status)
    statement = statement.order_by(Checkout.created_at.desc(), Checkout.id.desc())
    return [to_checkout_response(item) for item in db.scalars(statement).all()]


__all__ = [
    "create_checkout",
    "get_active_student_checkout",
    "get_student_checkout",
    "list_all_checkouts",
    "list_student_checkouts",
    "to_checkout_response",
]
