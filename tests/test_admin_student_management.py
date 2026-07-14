"""Administrator student-management and import contract tests."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from conftest import TEST_PASSWORD, SeedData
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import Student, User


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


def _headers(
    client: TestClient,
    username: str,
    password: str = TEST_PASSWORD,
) -> dict[str, str]:
    data = _success(
        client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
    )
    return {"Authorization": f"Bearer {data['access_token']}"}


def _student_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "full_name": "New Student",
        "email": "new.student@example.test",
        "student_id": "new001",
        "gender": "FEMALE",
        "department": "Computer Science",
        "year": "2",
        "hostel_block": "A",
        "room_number": "A-102",
        "phone": "+910000000101",
        "parent_phone": "+910000000201",
        "emergency_contact_name": "Parent Student",
        "hostel_status": "INSIDE",
        "photo_url": "https://example.test/new-student.jpg",
    }
    payload.update(changes)
    return payload


def test_admin_creates_student_with_hashed_usn_password_and_profile_fields(
    client: TestClient,
    db_session: Session,
    seeded_data: SeedData,
) -> None:
    created = _success(
        client.post(
            "/api/admin/students",
            headers=_headers(client, seeded_data.admin_user.username),
            json=_student_payload(),
        ),
        status_code=201,
    )

    assert created["student_id"] == "NEW001"
    assert created["gender"] == "FEMALE"
    assert created["emergency_contact_name"] == "Parent Student"
    assert created["hostel_block"] == "A"
    assert "password_hash" not in created

    user = db_session.scalar(select(User).where(User.email == created["email"]))
    assert user is not None
    assert user.username == "New Student"
    assert user.password_hash != "NEW001"
    assert verify_password("NEW001", user.password_hash)
    assert _headers(client, "new student", "NEW001")


def test_admin_updates_matching_login_fields_and_profile(
    client: TestClient,
    seeded_data: SeedData,
) -> None:
    admin_headers = _headers(client, seeded_data.admin_user.username)
    updated = _success(
        client.patch(
            "/api/admin/students/STU001",
            headers=admin_headers,
            json={
                "full_name": "Anita Renamed",
                "email": "ANITA.RENAMED@EXAMPLE.TEST",
                "student_id": "usn009",
                "gender": "OTHER",
                "hostel_block": "C",
                "emergency_contact_name": "Renamed Guardian",
            },
        )
    )

    assert updated["full_name"] == "Anita Renamed"
    assert updated["email"] == "anita.renamed@example.test"
    assert updated["student_id"] == "USN009"
    assert updated["gender"] == "OTHER"
    assert updated["hostel_block"] == "C"
    assert _headers(client, "anita renamed")


def test_deactivate_and_reactivate_student_control_login_without_deleting_profile(
    client: TestClient,
    seeded_data: SeedData,
) -> None:
    admin_headers = _headers(client, seeded_data.admin_user.username)
    deactivated = _success(
        client.post("/api/admin/students/STU001/deactivate", headers=admin_headers)
    )
    assert deactivated["email"] == seeded_data.student_one_user.email

    blocked = client.post(
        "/api/auth/login",
        json={
            "username": seeded_data.student_one_user.username,
            "password": TEST_PASSWORD,
        },
    )
    assert _error(blocked, 403)["message"] == "User account is inactive"

    reactivated = _success(
        client.post("/api/admin/students/STU001/activate", headers=admin_headers)
    )
    assert reactivated["email"] == seeded_data.student_one_user.email
    assert _headers(client, seeded_data.student_one_user.username)


def test_create_student_reports_clear_duplicate_conflicts(
    client: TestClient,
    seeded_data: SeedData,
) -> None:
    admin_headers = _headers(client, seeded_data.admin_user.username)
    _success(
        client.post(
            "/api/admin/students",
            headers=admin_headers,
            json=_student_payload(),
        ),
        status_code=201,
    )

    duplicate_name = client.post(
        "/api/admin/students",
        headers=admin_headers,
        json=_student_payload(email="different@example.test", student_id="NEW002"),
    )
    duplicate_email = client.post(
        "/api/admin/students",
        headers=admin_headers,
        json=_student_payload(
            full_name="Different Student",
            student_id="NEW003",
        ),
    )
    duplicate_id = client.post(
        "/api/admin/students",
        headers=admin_headers,
        json=_student_payload(
            full_name="Another Student",
            email="another@example.test",
        ),
    )

    assert "full name" in _error(duplicate_name, 409)["message"].lower()
    assert "email" in _error(duplicate_email, 409)["message"].lower()
    assert "student id" in _error(duplicate_id, 409)["message"].lower()


def test_admin_student_filters_include_new_profile_fields(
    client: TestClient,
    seeded_data: SeedData,
) -> None:
    admin_headers = _headers(client, seeded_data.admin_user.username)
    _success(
        client.post(
            "/api/admin/students",
            headers=admin_headers,
            json=_student_payload(),
        ),
        status_code=201,
    )

    students = _success(
        client.get(
            "/api/admin/students",
            headers=admin_headers,
            params={
                "search": "new",
                "hostel_block": "A",
                "gender": "FEMALE",
                "is_active": "true",
            },
        )
    )

    assert [student["student_id"] for student in students] == ["NEW001"]


def test_csv_import_keeps_valid_rows_and_reports_invalid_and_duplicate_rows(
    client: TestClient,
    db_session: Session,
    seeded_data: SeedData,
) -> None:
    headers = ",".join(
        [
            "full_name",
            "email",
            "student_id",
            "gender",
            "department",
            "year",
            "hostel_block",
            "room_number",
            "phone",
            "parent_phone",
            "emergency_contact_name",
            "hostel_status",
            "photo_url",
        ]
    )
    valid_row = ",".join(
        [
            "Imported Student",
            "imported@example.test",
            "imp001",
            "MALE",
            "CSE",
            "1",
            "A",
            "A-201",
            "+910000000301",
            "+910000000401",
            "Import Parent",
            "INSIDE",
            "",
        ]
    )
    invalid_gender_row = (
        valid_row.replace("MALE", "INVALID")
        .replace("imp001", "imp002")
        .replace("imported@example.test", "invalid@example.test")
    )
    duplicate_email_row = (
        valid_row.replace("Imported Student", "Duplicate Email")
        .replace("imp001", "imp003")
        .replace("MALE", "FEMALE")
    )
    csv_content = "\n".join(
        [headers, valid_row, invalid_gender_row, duplicate_email_row]
    )
    response = client.post(
        "/api/admin/students/import",
        headers=_headers(client, seeded_data.admin_user.username),
        files={"file": ("students.csv", csv_content, "text/csv")},
    )

    result = _success(response)
    assert result["total_rows"] == 3
    assert result["imported"] == 1
    assert result["failed"] == 2
    assert {error["row"] for error in result["errors"]} == {3, 4}
    imported_user = db_session.scalar(
        select(User).where(User.email == "imported@example.test")
    )
    assert imported_user is not None
    assert verify_password("IMP001", imported_user.password_hash)


def test_xlsx_import_accepts_valid_rows(
    client: TestClient,
    db_session: Session,
    seeded_data: SeedData,
) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(
        [
            "full_name",
            "email",
            "student_id",
            "gender",
            "department",
            "year",
            "hostel_block",
            "room_number",
            "phone",
            "parent_phone",
            "emergency_contact_name",
            "hostel_status",
        ]
    )
    worksheet.append(
        [
            "Spreadsheet Student",
            "spreadsheet@example.test",
            "xls001",
            "OTHER",
            "ECE",
            "3",
            "B",
            "B-301",
            "+910000000501",
            "+910000000601",
            "Spreadsheet Parent",
            "INSIDE",
        ]
    )
    content = BytesIO()
    workbook.save(content)
    workbook.close()

    response = client.post(
        "/api/admin/students/import",
        headers=_headers(client, seeded_data.admin_user.username),
        files={
            "file": (
                "students.xlsx",
                content.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    result = _success(response)
    assert result["imported"] == 1
    student = db_session.scalar(select(Student).where(Student.student_id == "XLS001"))
    assert student is not None
    assert student.gender.value == "OTHER"
    assert student.hostel_block == "B"
