"""Security-staff profile and QR verification business logic."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.exceptions import APIError
from app.models.checkout import Checkout
from app.models.enums import CheckoutStatus, HostelStatus, NotificationType
from app.models.notification import Notification
from app.models.security_staff import SecurityStaff
from app.models.user import User
from app.schemas.security import (
    SecurityProfileResponse,
    VerificationAction,
    VerifyQRRequest,
    VerifyQRResponse,
)
from app.schemas.student import StudentPublic
from app.services.checkout_service import to_checkout_response
from app.utils.helpers import utc_now


def get_security_for_user(db: Session, user: User) -> SecurityStaff:
    """Resolve and validate an authenticated security-staff profile."""

    staff = db.scalar(
        select(SecurityStaff)
        .options(joinedload(SecurityStaff.user))
        .where(SecurityStaff.user_id == user.id)
    )
    if staff is None:
        raise APIError(status_code=404, message="Security profile not found")
    if not staff.is_active:
        raise APIError(status_code=403, message="Security profile is inactive")
    return staff


def get_profile(db: Session, user: User) -> SecurityProfileResponse:
    """Return the authenticated security staff member's profile."""

    staff = get_security_for_user(db, user)
    return SecurityProfileResponse(
        id=staff.id,
        user_id=staff.user_id,
        staff_id=staff.staff_id,
        full_name=staff.full_name,
        phone=staff.phone,
        gate_name=staff.gate_name,
        shift=staff.shift,
        is_active=staff.is_active,
        email=staff.user.email if staff.user else None,
        created_at=staff.created_at,
    )


def verify_qr(
    db: Session,
    user: User,
    payload: VerifyQRRequest,
) -> VerifyQRResponse:
    """Validate a QR token and apply a checkout or check-in gate action.

    A checkout scan records exit verification. A check-in scan atomically
    completes an active checkout and returns the student to ``INSIDE``.
    """

    staff = get_security_for_user(db, user)
    checkout = db.scalar(
        select(Checkout)
        .options(selectinload(Checkout.student))
        .where(Checkout.qr_token == payload.qr_token)
        .with_for_update()
    )
    if checkout is None:
        raise APIError(status_code=404, message="Invalid QR token")

    if checkout.status == CheckoutStatus.COMPLETED:
        raise APIError(status_code=409, message="Checkout already completed")
    if checkout.status == CheckoutStatus.CANCELLED:
        raise APIError(status_code=409, message="Checkout was cancelled")
    if checkout.status == CheckoutStatus.PENDING:
        raise APIError(status_code=409, message="Checkout is pending approval")
    if checkout.status != CheckoutStatus.ACTIVE:
        raise APIError(status_code=409, message="Checkout is no longer active")

    if payload.action == VerificationAction.CHECKIN:
        verified_at = utc_now()
        checkout.checkin_time = verified_at
        checkout.status = CheckoutStatus.COMPLETED
        checkout.verified_by = staff.id
        checkout.verified_at = verified_at
        checkout.student.hostel_status = HostelStatus.INSIDE
        db.add(
            Notification(
                title="Student checked in",
                message=(
                    f"{staff.full_name} checked in "
                    f"{checkout.student.full_name} for {checkout.checkout_id}."
                ),
                notification_type=NotificationType.SECURITY,
            )
        )
        try:
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise APIError(503, "Database service is unavailable") from exc
        db.refresh(checkout)
    elif checkout.verified_at is None:
        checkout.verified_by = staff.id
        checkout.verified_at = utc_now()
        db.add(
            Notification(
                title="Checkout verified",
                message=f"{staff.full_name} verified checkout {checkout.checkout_id}.",
                notification_type=NotificationType.SECURITY,
            )
        )
        try:
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise APIError(503, "Database service is unavailable") from exc
        db.refresh(checkout)

    student = checkout.student
    return VerifyQRResponse(
        student=StudentPublic.model_validate(student),
        checkout=to_checkout_response(checkout),
        verification_successful=True,
    )


__all__ = ["get_profile", "get_security_for_user", "verify_qr"]
