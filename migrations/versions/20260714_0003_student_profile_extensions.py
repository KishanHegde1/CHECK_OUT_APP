"""Add student profile extensions and PostgreSQL updated-at trigger support.

Revision ID: 20260714_0003
Revises: 20260714_0002
Create Date: 2026-07-14 00:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

# Revision identifiers, used by Alembic.
revision: str = "20260714_0003"
down_revision: str | Sequence[str] | None = "20260714_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GENDER_CONSTRAINT = "ck_students_gender"
HOSTEL_BLOCK_INDEX = "ix_students_hostel_block"
TRIGGER_FUNCTION = "hostel_checkout_set_updated_at"


def _offline_upgrade() -> None:
    """Emit idempotent PostgreSQL SQL for a Neon migration preview."""

    op.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS gender VARCHAR(10)")
    op.execute(
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS "
        "emergency_contact_name VARCHAR(150)"
    )
    op.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS hostel_block VARCHAR(50)")
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
        f"WHERE conname = '{GENDER_CONSTRAINT}') THEN "
        "ALTER TABLE students ADD CONSTRAINT ck_students_gender "
        "CHECK (gender IS NULL OR gender IN ('MALE', 'FEMALE', 'OTHER')); "
        "END IF; END $$"
    )
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {HOSTEL_BLOCK_INDEX} " "ON students (hostel_block)"
    )
    _install_postgresql_updated_at_triggers()


def _install_postgresql_updated_at_triggers() -> None:
    """Add only missing PostgreSQL triggers; never duplicate existing ones."""

    op.execute(f"""
        CREATE OR REPLACE FUNCTION {TRIGGER_FUNCTION}()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """)
    op.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgrelid = 'users'::regclass
                  AND NOT tgisinternal
                  AND pg_get_triggerdef(oid) ILIKE '%updated_at%'
            ) THEN
                CREATE TRIGGER trg_users_set_updated_at
                BEFORE UPDATE ON users
                FOR EACH ROW EXECUTE FUNCTION {TRIGGER_FUNCTION}();
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgrelid = 'students'::regclass
                  AND NOT tgisinternal
                  AND pg_get_triggerdef(oid) ILIKE '%updated_at%'
            ) THEN
                CREATE TRIGGER trg_students_set_updated_at
                BEFORE UPDATE ON students
                FOR EACH ROW EXECUTE FUNCTION {TRIGGER_FUNCTION}();
            END IF;
        END $$
        """)


def upgrade() -> None:
    """Bring a fresh or manually extended schema to the current model shape."""

    if context.is_offline_mode():
        _offline_upgrade()
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("students")}
    additions = (
        ("gender", sa.String(length=10)),
        ("emergency_contact_name", sa.String(length=150)),
        ("hostel_block", sa.String(length=50)),
    )
    for name, column_type in additions:
        if name not in columns:
            op.add_column("students", sa.Column(name, column_type, nullable=True))

    if bind.dialect.name == "postgresql":
        constraints = inspector.get_check_constraints("students")
        if not any(
            "gender" in (item.get("sqltext") or "").lower() for item in constraints
        ):
            op.create_check_constraint(
                GENDER_CONSTRAINT,
                "students",
                "gender IS NULL OR gender IN ('MALE', 'FEMALE', 'OTHER')",
            )
        indexes = inspector.get_indexes("students")
        if not any(index.get("column_names") == ["hostel_block"] for index in indexes):
            op.create_index(HOSTEL_BLOCK_INDEX, "students", ["hostel_block"])
        _install_postgresql_updated_at_triggers()
    elif bind.dialect.name == "sqlite":
        indexes = inspector.get_indexes("students")
        if not any(index.get("column_names") == ["hostel_block"] for index in indexes):
            op.create_index(HOSTEL_BLOCK_INDEX, "students", ["hostel_block"])


def downgrade() -> None:
    """Remove extensions from a schema created by this migration chain."""

    if context.is_offline_mode():
        op.execute(f"DROP INDEX IF EXISTS {HOSTEL_BLOCK_INDEX}")
        op.execute(
            f"ALTER TABLE students DROP CONSTRAINT IF EXISTS {GENDER_CONSTRAINT}"
        )
        op.execute("ALTER TABLE students DROP COLUMN IF EXISTS hostel_block")
        op.execute("ALTER TABLE students DROP COLUMN IF EXISTS emergency_contact_name")
        op.execute("ALTER TABLE students DROP COLUMN IF EXISTS gender")
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("students")}
    if HOSTEL_BLOCK_INDEX in indexes:
        op.drop_index(HOSTEL_BLOCK_INDEX, table_name="students")
    if bind.dialect.name == "postgresql":
        constraints = {
            item["name"] for item in inspector.get_check_constraints("students")
        }
        if GENDER_CONSTRAINT in constraints:
            op.drop_constraint(GENDER_CONSTRAINT, "students", type_="check")
    columns = {column["name"] for column in inspector.get_columns("students")}
    for name in ("hostel_block", "emergency_contact_name", "gender"):
        if name in columns:
            op.drop_column("students", name)
