"""Shared API fixtures backed by an isolated in-memory SQLite database."""

from __future__ import annotations

import os
from collections.abc import Generator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Settings are evaluated while application modules are imported. Keep the
# production engine pointed at a non-connecting psycopg URL, then override the
# request-scoped database dependency with SQLite below.
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://test_user:test_password@localhost/test_database"
)
os.environ["SECRET_KEY"] = "test-secret-key-with-at-least-thirty-two-characters"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["CORS_ORIGINS"] = "[]"

from app.core.database import Base, get_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Admin,
    HostelStatus,
    SecurityStaff,
    Student,
    User,
    UserRole,
)

TEST_PASSWORD = "Correct-Horse-Battery-Staple-42"
TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)

test_engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    bind=test_engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


@event.listens_for(test_engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection: object, _record: object) -> None:
    """Make SQLite enforce the foreign keys used in production."""

    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@dataclass(frozen=True, slots=True)
class SeedData:
    """References to the accounts and profiles created for each test."""

    admin_user: User
    admin: Admin
    security_user: User
    security_staff: SecurityStaff
    student_one_user: User
    student_one: Student
    student_two_user: User
    student_two: Student


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Create a clean schema and session for one test."""

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def seeded_data(db_session: Session) -> SeedData:
    """Seed one account per privileged role and two student accounts."""

    admin_user = User(
        username="admin.user",
        email="admin@example.test",
        password_hash=TEST_PASSWORD_HASH,
        role=UserRole.ADMIN,
        is_active=True,
    )
    admin = Admin(
        user=admin_user,
        admin_id="ADM001",
        full_name="Asha Administrator",
        phone="+910000000001",
    )

    security_user = User(
        username="security.user",
        email="security@example.test",
        password_hash=TEST_PASSWORD_HASH,
        role=UserRole.SECURITY,
        is_active=True,
    )
    security_staff = SecurityStaff(
        user=security_user,
        staff_id="SEC001",
        full_name="Sam Security",
        phone="+910000000002",
        gate_name="Main Gate",
        shift="Night",
        is_active=True,
    )

    student_one_user = User(
        username="student.one",
        email="student.one@example.test",
        password_hash=TEST_PASSWORD_HASH,
        role=UserRole.STUDENT,
        is_active=True,
    )
    student_one = Student(
        user=student_one_user,
        student_id="STU001",
        full_name="Anita Student",
        room_number="A-101",
        department="Computer Science",
        year="4th Year",
        phone="+910000000003",
        parent_phone="+910000000013",
        hostel_status=HostelStatus.INSIDE,
        photo_url="https://example.test/student-one.jpg",
    )

    student_two_user = User(
        username="student.two",
        email="student.two@example.test",
        password_hash=TEST_PASSWORD_HASH,
        role=UserRole.STUDENT,
        is_active=True,
    )
    student_two = Student(
        user=student_two_user,
        student_id="STU002",
        full_name="Bina Student",
        room_number="B-202",
        department="Electrical Engineering",
        year="2nd Year",
        phone="+910000000004",
        parent_phone="+910000000014",
        hostel_status=HostelStatus.INSIDE,
        photo_url=None,
    )

    db_session.add_all(
        (
            admin,
            security_staff,
            student_one,
            student_two,
        )
    )
    db_session.commit()

    return SeedData(
        admin_user=admin_user,
        admin=admin,
        security_user=security_user,
        security_staff=security_staff,
        student_one_user=student_one_user,
        student_one=student_one,
        student_two_user=student_two_user,
        student_two=student_two,
    )


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Return a client whose database dependency uses the test session."""

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
