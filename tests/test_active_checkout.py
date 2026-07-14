"""Active checkout persistence and QR-token lifecycle tests."""

from __future__ import annotations

from typing import Any

from conftest import TEST_PASSWORD, SeedData
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Checkout, CheckoutStatus


def _success(response: Any, status_code: int = 200) -> dict[str, Any]:
    assert response.status_code == status_code, response.text
    body = response.json()
    assert body["success"] is True
    return body["data"]


def _error(response: Any, status_code: int) -> dict[str, Any]:
    assert response.status_code == status_code, response.text
    body = response.json()
    assert body["success"] is False
    return body


def _headers(client: TestClient, username: str) -> dict[str, str]:
    data = _success(
        client.post(
            "/api/auth/login",
            json={"username": username, "password": TEST_PASSWORD},
        )
    )
    return {"Authorization": f"Bearer {data['access_token']}"}


def _create_checkout(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    return _success(
        client.post(
            "/api/student/checkouts",
            headers=headers,
            json={"reason": "Study leave"},
        ),
        status_code=201,
    )


def test_no_active_checkout_returns_safe_404(
    client: TestClient,
    seeded_data: SeedData,
) -> None:
    response = client.get(
        "/api/student/checkouts/active",
        headers=_headers(client, seeded_data.student_one_user.username),
    )

    body = _error(response, 404)
    assert body["message"] == "No active checkout found"


def test_active_checkout_returns_the_original_stored_qr_token(
    client: TestClient,
    seeded_data: SeedData,
) -> None:
    student_headers = _headers(client, seeded_data.student_one_user.username)
    created = _create_checkout(client, student_headers)

    first = _success(
        client.get("/api/student/checkouts/active", headers=student_headers)
    )
    second = _success(
        client.get("/api/student/checkouts/active", headers=student_headers)
    )

    assert first["checkout_id"] == created["checkout_id"]
    assert first["qr_token"] == created["qr_token"]
    assert second["checkout_id"] == created["checkout_id"]
    assert second["qr_token"] == created["qr_token"]
    assert first["status"] == "ACTIVE"
    assert first["reason"] == "Study leave"
    assert first["checkin_time"] is None


def test_active_checkout_is_private_and_blocks_a_second_checkout(
    client: TestClient,
    seeded_data: SeedData,
) -> None:
    first_headers = _headers(client, seeded_data.student_one_user.username)
    second_headers = _headers(client, seeded_data.student_two_user.username)
    _create_checkout(client, first_headers)

    other_student = client.get(
        "/api/student/checkouts/active",
        headers=second_headers,
    )
    duplicate = client.post(
        "/api/student/checkouts",
        headers=first_headers,
        json={"reason": "A second checkout"},
    )

    _error(other_student, 404)
    duplicate_body = _error(duplicate, 409)
    assert "active checkout" in duplicate_body["message"].lower()


def test_checkin_completes_qr_and_preserves_the_original_timestamp_on_rescan(
    client: TestClient,
    db_session: Session,
    seeded_data: SeedData,
) -> None:
    student_headers = _headers(client, seeded_data.student_one_user.username)
    security_headers = _headers(client, seeded_data.security_user.username)
    created = _create_checkout(client, student_headers)

    completed = _success(
        client.post(
            "/api/security/verify-qr",
            headers=security_headers,
            json={"qr_token": created["qr_token"], "action": "CHECKIN"},
        )
    )
    reused = _success(
        client.post(
            "/api/security/verify-qr",
            headers=security_headers,
            json={"qr_token": created["qr_token"], "action": "CHECKIN"},
        )
    )

    assert completed["checkout"]["status"] == "COMPLETED"
    assert completed["checkout"]["checkin_time"]
    assert completed["checkout"]["verified_by"] == seeded_data.security_staff.id
    assert completed["checkout"]["verified_at"]
    assert completed["student"]["hostel_status"] == "INSIDE"
    assert reused["checkout"]["status"] == "COMPLETED"
    assert reused["checkout"]["checkin_time"] == completed["checkout"]["checkin_time"]
    assert reused["checkout"]["reason"] == "Study leave"

    db_session.refresh(seeded_data.student_one)
    assert seeded_data.student_one.hostel_status.value == "INSIDE"


def test_cancelled_qr_is_rejected(
    client: TestClient,
    db_session: Session,
    seeded_data: SeedData,
) -> None:
    cancelled = Checkout(
        checkout_id="CHK-CANCELLED-001",
        student_id=seeded_data.student_one.id,
        qr_token="cancelled-checkout-token-with-more-than-sixteen-bytes",
        status=CheckoutStatus.CANCELLED,
    )
    db_session.add(cancelled)
    db_session.commit()

    response = client.post(
        "/api/security/verify-qr",
        headers=_headers(client, seeded_data.security_user.username),
        json={"qr_token": cancelled.qr_token},
    )

    assert _error(response, 409)["message"] == "Checkout was cancelled"
