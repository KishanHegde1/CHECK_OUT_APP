"""Focused end-to-end tests for the public Hostel Checkout API contract."""

from __future__ import annotations

import re
from typing import Any

import pytest
from conftest import TEST_PASSWORD, SeedData
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Checkout,
    CheckoutStatus,
    Notification,
    NotificationType,
    User,
    UserRole,
)

pytestmark = pytest.mark.unit


def assert_success(response: Any, status_code: int = 200) -> dict[str, Any]:
    """Assert and return a standard success envelope."""

    assert response.status_code == status_code, response.text
    body = response.json()
    assert set(body) == {"success", "message", "data"}
    assert body["success"] is True
    assert isinstance(body["message"], str) and body["message"]
    return body


def assert_error(response: Any, status_code: int) -> dict[str, Any]:
    """Assert and return a standard error envelope."""

    assert response.status_code == status_code, response.text
    body = response.json()
    assert set(body) == {"success", "message", "errors"}
    assert body["success"] is False
    assert isinstance(body["message"], str) and body["message"]
    assert isinstance(body["errors"], list)
    return body


def auth_headers(
    client: TestClient,
    identifier: str,
    *,
    alias: str = "username",
) -> dict[str, str]:
    """Log in an account and return its bearer authorization header."""

    response = client.post(
        "/api/auth/login",
        json={alias: identifier, "password": TEST_PASSWORD},
    )
    data = assert_success(response)["data"]
    return {"Authorization": f"Bearer {data['access_token']}"}


def create_checkout(
    client: TestClient,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create and return a checkout response payload."""

    response = client.post(
        "/api/student/checkouts",
        headers=headers,
        json={"reason": "Campus appointment"} if payload is None else payload,
    )
    return assert_success(response, 201)["data"]


def test_health_uses_success_envelope(client: TestClient) -> None:
    response = client.get("/health")

    body = assert_success(response)
    assert body == {
        "success": True,
        "message": "Service is healthy",
        "data": {"status": "healthy"},
    }
    assert response.headers["X-Request-ID"]

    ready = assert_success(client.get("/ready"))
    assert ready["data"] == {"status": "ready", "database": "reachable"}


def test_request_validation_uses_422_error_envelope(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={})

    body = assert_error(response, 422)
    assert body["message"] == "Request validation failed"
    assert {error["field"] for error in body["errors"]} == {
        "username",
        "password",
    }


def test_router_errors_and_openapi_use_error_envelope(client: TestClient) -> None:
    """Keep 404/405 runtime and documented validation errors consistent."""

    assert_error(client.get("/api/not-a-route"), 404)
    assert_error(client.put("/health"), 405)

    document = client.get("/openapi.json").json()
    schemas = document["components"]["schemas"]
    assert schemas["ErrorResponse"]["required"] == [
        "success",
        "message",
        "errors",
    ]
    validation_schema = document["paths"]["/api/auth/login"]["post"]["responses"][
        "422"
    ]["content"]["application/json"]["schema"]
    assert validation_schema == {"$ref": "#/components/schemas/ErrorResponse"}


def test_login_accepts_username_and_user_id_alias(
    client: TestClient,
    seeded_data: SeedData,
) -> None:
    canonical = client.post(
        "/api/auth/login",
        json={
            "username": seeded_data.student_one_user.username,
            "password": TEST_PASSWORD,
        },
    )
    canonical_data = assert_success(canonical)["data"]
    assert canonical_data["access_token"]
    assert canonical_data["token_type"] == "bearer"
    assert canonical_data["role"] == "STUDENT"
    assert canonical_data["user_id"] == seeded_data.student_one_user.id

    alias = client.post(
        "/api/auth/login",
        json={
            "user_id": seeded_data.student_one_user.username,
            "password": TEST_PASSWORD,
        },
    )
    alias_data = assert_success(alias)["data"]
    assert alias_data["user_id"] == seeded_data.student_one_user.id
    assert alias_data["access_token"] != canonical_data["access_token"]


@pytest.mark.parametrize(
    ("identifier", "password"),
    (("unknown.user", TEST_PASSWORD), ("student.one", "wrong-password")),
)
def test_invalid_login_is_generic(
    client: TestClient,
    seeded_data: SeedData,
    identifier: str,
    password: str,
) -> None:
    del seeded_data
    response = client.post(
        "/api/auth/login",
        json={"username": identifier, "password": password},
    )

    body = assert_error(response, 401)
    assert body["message"] == "Invalid username or password"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_user_identifiers_are_case_insensitively_unique(
    db_session: Session,
    seeded_data: SeedData,
) -> None:
    """Keep database uniqueness aligned with normalized authentication."""

    duplicate = User(
        username=seeded_data.student_one_user.username.upper(),
        email="different@example.test",
        password_hash=seeded_data.student_one_user.password_hash,
        role=UserRole.STUDENT,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_me_logout_and_missing_token_contract(
    client: TestClient,
    seeded_data: SeedData,
) -> None:
    missing = client.get("/api/auth/me")
    missing_body = assert_error(missing, 401)
    assert missing_body["message"] == "Not authenticated"
    assert missing.headers["WWW-Authenticate"] == "Bearer"

    headers = auth_headers(client, seeded_data.student_one_user.email)
    me_body = assert_success(client.get("/api/auth/me", headers=headers))
    assert me_body["data"]["user_id"] == seeded_data.student_one_user.id
    assert me_body["data"]["username"] == seeded_data.student_one_user.username
    assert me_body["data"]["role"] == "STUDENT"
    assert me_body["data"]["is_active"] is True

    logout_body = assert_success(client.post("/api/auth/logout", headers=headers))
    assert logout_body["data"] == {"user_id": str(seeded_data.student_one_user.id)}


def test_role_dependency_rejects_wrong_role(
    client: TestClient,
    seeded_data: SeedData,
) -> None:
    student_headers = auth_headers(client, seeded_data.student_one_user.username)

    response = client.get("/api/admin/dashboard", headers=student_headers)

    body = assert_error(response, 403)
    assert "permission" in body["message"].lower()


def test_student_profile(
    client: TestClient,
    seeded_data: SeedData,
) -> None:
    headers = auth_headers(client, seeded_data.student_one_user.username)

    body = assert_success(client.get("/api/student/profile", headers=headers))

    profile = body["data"]
    assert profile["id"] == seeded_data.student_one.id
    assert profile["student_id"] == "STU001"
    assert profile["room_number"] == "A-101"
    assert profile["year"] == "4th Year"
    assert profile["hostel_status"] == "INSIDE"
    assert profile["email"] == seeded_data.student_one_user.email


def test_checkout_create_requires_and_persists_a_reason_with_secure_qr(
    client: TestClient,
    db_session: Session,
    seeded_data: SeedData,
) -> None:
    first_headers = auth_headers(client, seeded_data.student_one_user.username)
    first = create_checkout(
        client,
        first_headers,
        {"reason": "  Campus appointment  "},
    )

    assert first["reason"] == "Campus appointment"
    assert first["checkin_time"] is None
    assert first["status"] == "ACTIVE"
    assert first["student_id"] == seeded_data.student_one.student_id
    assert first["checkout_id"].startswith("CHK-")
    assert len(first["qr_token"]) >= 32
    assert re.fullmatch(r"[A-Za-z0-9_-]+", first["qr_token"])
    assert first["qr_token"] != first["checkout_id"]

    checkout = db_session.scalar(
        select(Checkout).where(Checkout.checkout_id == first["checkout_id"])
    )
    assert checkout is not None
    assert checkout.reason == "Campus appointment"

    db_session.refresh(seeded_data.student_one)
    assert seeded_data.student_one.hostel_status.value == "OUTSIDE"

    second_headers = auth_headers(client, seeded_data.student_two_user.username)
    second = create_checkout(client, second_headers, {"reason": "Weekend visit"})
    assert second["qr_token"] != first["qr_token"]
    assert second["checkout_id"] != first["checkout_id"]


@pytest.mark.parametrize(
    "payload",
    (
        {},
        {"reason": ""},
        {"reason": "   "},
        {"reason": "x" * 251},
    ),
)
def test_checkout_reason_is_required_meaningful_and_at_most_250_characters(
    client: TestClient,
    seeded_data: SeedData,
    payload: dict[str, str],
) -> None:
    response = client.post(
        "/api/student/checkouts",
        headers=auth_headers(client, seeded_data.student_one_user.username),
        json=payload,
    )

    assert_error(response, 422)


def test_duplicate_active_checkout_returns_409(
    client: TestClient,
    seeded_data: SeedData,
) -> None:
    headers = auth_headers(client, seeded_data.student_one_user.username)
    create_checkout(client, headers)

    duplicate = client.post(
        "/api/student/checkouts",
        headers=headers,
        json={"reason": "A second pass"},
    )

    body = assert_error(duplicate, 409)
    assert "active checkout already exists" in body["message"].lower()


def test_checkout_list_detail_and_idor_protection(
    client: TestClient,
    seeded_data: SeedData,
) -> None:
    owner_headers = auth_headers(client, seeded_data.student_one_user.username)
    other_headers = auth_headers(client, seeded_data.student_two_user.username)
    created = create_checkout(client, owner_headers, {"reason": "Medical visit"})

    list_body = assert_success(
        client.get("/api/student/checkouts", headers=owner_headers)
    )
    assert [item["checkout_id"] for item in list_body["data"]] == [
        created["checkout_id"]
    ]
    assert list_body["data"][0]["reason"] == "Medical visit"
    assert list_body["data"][0]["checkin_time"] is None

    public_detail = assert_success(
        client.get(
            f"/api/student/checkouts/{created['checkout_id']}",
            headers=owner_headers,
        )
    )
    assert public_detail["data"]["id"] == created["id"]

    numeric_detail = assert_success(
        client.get(
            f"/api/student/checkouts/{created['id']}",
            headers=owner_headers,
        )
    )
    assert numeric_detail["data"]["checkout_id"] == created["checkout_id"]

    idor = client.get(
        f"/api/student/checkouts/{created['checkout_id']}",
        headers=other_headers,
    )
    body = assert_error(idor, 404)
    assert body["message"] == "Checkout not found"


def test_security_verify_is_validated_audited_and_idempotent(
    client: TestClient,
    db_session: Session,
    seeded_data: SeedData,
) -> None:
    student_headers = auth_headers(client, seeded_data.student_one_user.username)
    security_headers = auth_headers(client, seeded_data.security_user.username)
    created = create_checkout(client, student_headers)

    profile = assert_success(
        client.get("/api/security/profile", headers=security_headers)
    )["data"]
    assert profile["staff_id"] == seeded_data.security_staff.staff_id

    invalid = client.post(
        "/api/security/verify-qr",
        headers=security_headers,
        json={"qr_token": "not-a-valid-token"},
    )
    invalid_body = assert_error(invalid, 404)
    assert invalid_body["message"] == "Invalid QR token"

    first = assert_success(
        client.post(
            "/api/security/verify-qr",
            headers=security_headers,
            json={"qr_token": created["qr_token"]},
        )
    )["data"]
    assert first["verification_successful"] is True
    assert first["student"]["student_id"] == seeded_data.student_one.student_id
    assert first["checkout"]["verified_by"] == seeded_data.security_staff.id
    assert first["checkout"]["verified_at"]
    assert first["checkout"]["reason"] == "Campus appointment"
    assert first["checkout"]["checkin_time"] is None

    second = assert_success(
        client.post(
            "/api/security/verify-qr",
            headers=security_headers,
            json={"qr_token": created["qr_token"]},
        )
    )["data"]
    assert second["checkout"]["verified_by"] == first["checkout"]["verified_by"]
    assert second["checkout"]["verified_at"] == first["checkout"]["verified_at"]

    db_session.expire_all()
    checkout = db_session.scalar(
        select(Checkout).where(Checkout.checkout_id == created["checkout_id"])
    )
    assert checkout is not None
    assert checkout.verified_by == seeded_data.security_staff.id
    assert checkout.verified_at is not None

    audit_notifications = db_session.scalar(
        select(func.count(Notification.id)).where(
            Notification.notification_type == NotificationType.SECURITY
        )
    )
    assert audit_notifications == 1


def test_security_checkin_completes_checkout_and_allows_a_new_pass(
    client: TestClient,
    db_session: Session,
    seeded_data: SeedData,
) -> None:
    student_headers = auth_headers(client, seeded_data.student_one_user.username)
    security_headers = auth_headers(client, seeded_data.security_user.username)
    created = create_checkout(client, student_headers)
    verify_url = "/api/security/verify-qr"

    assert_success(
        client.post(
            verify_url,
            headers=security_headers,
            json={"qr_token": created["qr_token"]},
        )
    )
    completed = assert_success(
        client.post(
            verify_url,
            headers=security_headers,
            json={"qr_token": created["qr_token"], "action": "CHECKIN"},
        )
    )["data"]
    assert completed["checkout"]["status"] == "COMPLETED"
    assert completed["checkout"]["checkin_time"]
    assert completed["checkout"]["reason"] == "Campus appointment"
    assert completed["student"]["hostel_status"] == "INSIDE"

    retry = assert_success(
        client.post(
            verify_url,
            headers=security_headers,
            json={"qr_token": created["qr_token"], "action": "CHECKIN"},
        )
    )["data"]
    assert retry["checkout"]["checkin_time"] == completed["checkout"]["checkin_time"]
    assert retry["checkout"]["reason"] == "Campus appointment"

    history = assert_success(
        client.get("/api/student/checkouts", headers=student_headers)
    )["data"]
    assert history[0]["reason"] == "Campus appointment"
    assert history[0]["checkin_time"] == completed["checkout"]["checkin_time"]

    admin_checkouts = assert_success(
        client.get(
            "/api/admin/checkouts",
            headers=auth_headers(client, seeded_data.admin_user.username),
        )
    )["data"]
    assert admin_checkouts[0]["reason"] == "Campus appointment"
    assert admin_checkouts[0]["checkin_time"] == completed["checkout"]["checkin_time"]

    replacement = create_checkout(client, student_headers)
    assert replacement["checkout_id"] != created["checkout_id"]
    db_session.refresh(seeded_data.student_one)
    assert seeded_data.student_one.hostel_status.value == "OUTSIDE"


def test_admin_dashboard_returns_exact_database_counts(
    client: TestClient,
    db_session: Session,
    seeded_data: SeedData,
) -> None:
    student_headers = auth_headers(client, seeded_data.student_one_user.username)
    create_checkout(client, student_headers)
    db_session.add(
        Checkout(
            checkout_id="CHK-PENDING-001",
            student_id=seeded_data.student_two.id,
            reason="Awaiting approval",
            qr_token="pending-token-with-more-than-sixteen-bytes-001",
            status=CheckoutStatus.PENDING,
        )
    )
    db_session.commit()

    admin_headers = auth_headers(client, seeded_data.admin_user.username)
    dashboard = assert_success(
        client.get("/api/admin/dashboard", headers=admin_headers)
    )["data"]

    assert dashboard == {
        "total_students": 2,
        "students_inside": 1,
        "students_outside": 1,
        "active_checkouts": 1,
        "pending_requests": 1,
        "security_staff_count": 1,
    }


def test_admin_collections_active_notifications_and_student_detail(
    client: TestClient,
    seeded_data: SeedData,
) -> None:
    student_headers = auth_headers(client, seeded_data.student_one_user.username)
    created = create_checkout(client, student_headers, {"reason": "Family visit"})
    admin_headers = auth_headers(client, seeded_data.admin_user.username)

    students = assert_success(client.get("/api/admin/students", headers=admin_headers))[
        "data"
    ]
    assert [student["student_id"] for student in students] == ["STU001", "STU002"]

    detail = assert_success(
        client.get(
            f"/api/admin/students/{seeded_data.student_one.student_id}",
            headers=admin_headers,
        )
    )["data"]
    assert detail["student"]["id"] == seeded_data.student_one.id
    assert [item["checkout_id"] for item in detail["checkouts"]] == [
        created["checkout_id"]
    ]

    all_checkouts = assert_success(
        client.get("/api/admin/checkouts", headers=admin_headers)
    )["data"]
    active_checkouts = assert_success(
        client.get("/api/admin/checkouts/active", headers=admin_headers)
    )["data"]
    assert [item["checkout_id"] for item in all_checkouts] == [created["checkout_id"]]
    assert [item["checkout_id"] for item in active_checkouts] == [
        created["checkout_id"]
    ]
    assert all_checkouts[0]["reason"] == "Family visit"
    assert all_checkouts[0]["checkin_time"] is None

    staff = assert_success(
        client.get("/api/admin/security-staff", headers=admin_headers)
    )["data"]
    assert len(staff) == 1
    assert staff[0]["staff_id"] == seeded_data.security_staff.staff_id

    notifications = assert_success(
        client.get("/api/admin/notifications", headers=admin_headers)
    )["data"]
    assert len(notifications) == 1
    assert notifications[0]["notification_type"] == "CHECKOUT"
    assert created["checkout_id"] in notifications[0]["message"]
