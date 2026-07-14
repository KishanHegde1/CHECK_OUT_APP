"""Migration smoke tests that do not require a running PostgreSQL server."""

from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.unit


def test_initial_migration_upgrades_and_downgrades() -> None:
    """Exercise the checked-in revision through Alembic's real environment."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    config = Config("alembic.ini")
    application_tables = {
        "admins",
        "checkouts",
        "notifications",
        "security_staff",
        "students",
        "users",
    }

    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

        assert application_tables <= set(inspect(connection).get_table_names())
        assert MigrationContext.configure(connection).get_current_revision() == (
            "20260714_0003"
        )
        student_columns = {
            column["name"] for column in inspect(connection).get_columns("students")
        }
        assert {
            "gender",
            "emergency_contact_name",
            "hostel_block",
        } <= student_columns
        student_indexes = {
            index["name"] for index in inspect(connection).get_indexes("students")
        }
        assert "ix_students_hostel_block" in student_indexes
        user_indexes = set(
            connection.scalars(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'index' AND tbl_name = 'users'"
                )
            )
        )
        assert {
            "uq_users_username_lower",
            "uq_users_email_lower",
        } <= user_indexes
        checkout_index_sql = connection.scalar(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'index' "
                "AND name = 'uq_checkouts_one_active_per_student'"
            )
        )
        assert checkout_index_sql is not None
        assert "WHERE status = 'ACTIVE'" in checkout_index_sql

        connection.execute(
            text(
                "INSERT INTO users "
                "(username, email, password_hash, role, created_at, updated_at) "
                "VALUES "
                "('index-test', 'index-test@example.test', 'hash', 'STUDENT', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        user_id = connection.scalar(
            text("SELECT id FROM users WHERE username = 'index-test'")
        )
        assert user_id is not None
        connection.execute(
            text(
                "INSERT INTO students "
                "(user_id, student_id, full_name, room_number, department, year, "
                "phone, parent_phone, created_at, updated_at) "
                "VALUES (:user_id, 'INDEX-001', 'Index Test', 'A-1', 'CSE', '1', "
                "'1', '2', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"user_id": user_id},
        )
        student_id = connection.scalar(
            text("SELECT id FROM students WHERE student_id = 'INDEX-001'")
        )
        assert student_id is not None
        insert_checkout = text(
            "INSERT INTO checkouts "
            "(checkout_id, student_id, checkout_time, qr_token, status, "
            "created_at) "
            "VALUES (:checkout_id, :student_id, CURRENT_TIMESTAMP, :qr_token, "
            "'ACTIVE', CURRENT_TIMESTAMP)"
        )
        connection.execute(
            insert_checkout,
            {
                "checkout_id": "CHK-INDEX-001",
                "student_id": student_id,
                "qr_token": "index-token-001",
            },
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                insert_checkout,
                {
                    "checkout_id": "CHK-INDEX-002",
                    "student_id": student_id,
                    "qr_token": "index-token-002",
                },
            )
        connection.rollback()

        command.downgrade(config, "base")
        remaining = set(inspect(connection).get_table_names())
        assert not application_tables & remaining
        assert MigrationContext.configure(connection).get_current_revision() is None

    engine.dispose()


def test_active_checkout_migration_refuses_existing_duplicate_data() -> None:
    """Require operators to resolve duplicate ACTIVE rows before upgrading."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    config = Config("alembic.ini")

    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "20260712_0001")
        connection.execute(
            text(
                "INSERT INTO users "
                "(username, email, password_hash, role, created_at, updated_at) "
                "VALUES "
                "('duplicate-test', 'duplicate-test@example.test', 'hash', 'STUDENT', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        user_id = connection.scalar(
            text("SELECT id FROM users WHERE username = 'duplicate-test'")
        )
        assert user_id is not None
        connection.execute(
            text(
                "INSERT INTO students "
                "(user_id, student_id, full_name, room_number, department, year, "
                "phone, parent_phone, created_at, updated_at) "
                "VALUES (:user_id, 'DUPLICATE-001', 'Duplicate Test', 'A-1', "
                "'CSE', '1', '1', '2', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"user_id": user_id},
        )
        student_id = connection.scalar(
            text("SELECT id FROM students WHERE student_id = 'DUPLICATE-001'")
        )
        assert student_id is not None
        insert_checkout = text(
            "INSERT INTO checkouts "
            "(checkout_id, student_id, checkout_time, qr_token, status, "
            "created_at) "
            "VALUES (:checkout_id, :student_id, CURRENT_TIMESTAMP, :qr_token, "
            "'ACTIVE', CURRENT_TIMESTAMP)"
        )
        for suffix in ("001", "002"):
            connection.execute(
                insert_checkout,
                {
                    "checkout_id": f"CHK-DUPLICATE-{suffix}",
                    "student_id": student_id,
                    "qr_token": f"duplicate-token-{suffix}",
                },
            )
        connection.commit()

        with pytest.raises(RuntimeError, match="duplicate ACTIVE checkouts"):
            command.upgrade(config, "head")
        assert MigrationContext.configure(connection).get_current_revision() == (
            "20260712_0001"
        )

    engine.dispose()
