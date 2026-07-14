"""Create the initial Hostel Checkout schema.

Revision ID: 20260712_0001
Revises:
Create Date: 2026-07-12 00:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "20260712_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


USER_ROLE = sa.Enum(
    "STUDENT",
    "ADMIN",
    "SECURITY",
    name="user_role",
    native_enum=False,
    create_constraint=False,
    validate_strings=True,
)
HOSTEL_STATUS = sa.Enum(
    "INSIDE",
    "OUTSIDE",
    name="hostel_status",
    native_enum=False,
    create_constraint=False,
    validate_strings=True,
)
CHECKOUT_STATUS = sa.Enum(
    "PENDING",
    "ACTIVE",
    "COMPLETED",
    "CANCELLED",
    name="checkout_status",
    native_enum=False,
    create_constraint=False,
    validate_strings=True,
)
NOTIFICATION_TYPE = sa.Enum(
    "CHECKOUT",
    "SECURITY",
    "SYSTEM",
    "NOTICE",
    name="notification_type",
    native_enum=False,
    create_constraint=False,
    validate_strings=True,
)


def upgrade() -> None:
    """Create all application tables, constraints, and indexes."""

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", USER_ROLE, nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('STUDENT', 'ADMIN', 'SECURITY')",
            name=op.f("ck_users_user_role"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(
        op.f("ix_users_email"),
        "users",
        ["email"],
        unique=True,
    )
    op.create_index(
        op.f("ix_users_is_active"),
        "users",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_users_role"),
        "users",
        ["role"],
        unique=False,
    )
    op.create_index(
        op.f("ix_users_username"),
        "users",
        ["username"],
        unique=True,
    )
    op.create_index(
        "uq_users_username_lower",
        "users",
        [sa.text("lower(username)")],
        unique=True,
    )
    op.create_index(
        "uq_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "notification_type",
            NOTIFICATION_TYPE,
            server_default=sa.text("'SYSTEM'"),
            nullable=False,
        ),
        sa.Column(
            "is_read",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "notification_type IN ('CHECKOUT', 'SECURITY', 'SYSTEM', 'NOTICE')",
            name=op.f("ck_notifications_notification_type"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(
        op.f("ix_notifications_created_at"),
        "notifications",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_is_read"),
        "notifications",
        ["is_read"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_read_created",
        "notifications",
        ["is_read", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_notification_type"),
        "notifications",
        ["notification_type"],
        unique=False,
    )

    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.String(length=50), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("room_number", sa.String(length=30), nullable=False),
        sa.Column("department", sa.String(length=100), nullable=False),
        sa.Column("year", sa.String(length=30), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("parent_phone", sa.String(length=30), nullable=False),
        sa.Column(
            "hostel_status",
            HOSTEL_STATUS,
            server_default=sa.text("'INSIDE'"),
            nullable=False,
        ),
        sa.Column("photo_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "hostel_status IN ('INSIDE', 'OUTSIDE')",
            name=op.f("ck_students_hostel_status"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_students_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_students")),
    )
    op.create_index(
        op.f("ix_students_department"),
        "students",
        ["department"],
        unique=False,
    )
    op.create_index(
        op.f("ix_students_full_name"),
        "students",
        ["full_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_students_hostel_status"),
        "students",
        ["hostel_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_students_room_number"),
        "students",
        ["room_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_students_student_id"),
        "students",
        ["student_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_students_user_id"),
        "students",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("admin_id", sa.String(length=50), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_admins_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admins")),
    )
    op.create_index(
        op.f("ix_admins_admin_id"),
        "admins",
        ["admin_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_admins_full_name"),
        "admins",
        ["full_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admins_user_id"),
        "admins",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "security_staff",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.String(length=50), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("gate_name", sa.String(length=100), nullable=False),
        sa.Column("shift", sa.String(length=50), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_security_staff_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_staff")),
    )
    op.create_index(
        op.f("ix_security_staff_full_name"),
        "security_staff",
        ["full_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_security_staff_gate_name"),
        "security_staff",
        ["gate_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_security_staff_is_active"),
        "security_staff",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_security_staff_shift"),
        "security_staff",
        ["shift"],
        unique=False,
    )
    op.create_index(
        op.f("ix_security_staff_staff_id"),
        "security_staff",
        ["staff_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_security_staff_user_id"),
        "security_staff",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "checkouts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("checkout_id", sa.String(length=64), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("checkout_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checkin_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=250), nullable=True),
        sa.Column("qr_token", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            CHECKOUT_STATUS,
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column("verified_by", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "checkin_time IS NULL OR checkin_time >= checkout_time",
            name=op.f("ck_checkouts_checkin_not_before_checkout"),
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACTIVE', 'COMPLETED', 'CANCELLED')",
            name=op.f("ck_checkouts_checkout_status"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name=op.f("fk_checkouts_student_id_students"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["verified_by"],
            ["security_staff.id"],
            name=op.f("fk_checkouts_verified_by_security_staff"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_checkouts")),
    )
    op.create_index(
        op.f("ix_checkouts_checkout_id"),
        "checkouts",
        ["checkout_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_checkouts_checkout_time"),
        "checkouts",
        ["checkout_time"],
        unique=False,
    )
    op.create_index(
        op.f("ix_checkouts_qr_token"),
        "checkouts",
        ["qr_token"],
        unique=True,
    )
    op.create_index(
        op.f("ix_checkouts_status"),
        "checkouts",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_checkouts_student_status",
        "checkouts",
        ["student_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_checkouts_student_id"),
        "checkouts",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_checkouts_verified_by"),
        "checkouts",
        ["verified_by"],
        unique=False,
    )


def downgrade() -> None:
    """Drop application tables in reverse foreign-key dependency order."""

    op.drop_table("checkouts")
    op.drop_table("security_staff")
    op.drop_table("admins")
    op.drop_table("students")
    op.drop_table("notifications")
    op.drop_table("users")
