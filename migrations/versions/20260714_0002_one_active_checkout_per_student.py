"""Enforce one active checkout per student.

Revision ID: 20260714_0002
Revises: 20260712_0001
Create Date: 2026-07-14 00:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

# Revision identifiers, used by Alembic.
revision: str = "20260714_0002"
down_revision: str | Sequence[str] | None = "20260712_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_checkouts_one_active_per_student"
ACTIVE_CHECKOUT_PREDICATE = sa.text("status = 'ACTIVE'")


def upgrade() -> None:
    """Create the partial unique index after refusing duplicate active data."""

    if not context.is_offline_mode():
        duplicate = (
            op.get_bind()
            .execute(
                sa.text(
                    "SELECT student_id "
                    "FROM checkouts "
                    "WHERE status = 'ACTIVE' "
                    "GROUP BY student_id "
                    "HAVING COUNT(*) > 1 "
                    "LIMIT 1"
                )
            )
            .first()
        )
        if duplicate is not None:
            raise RuntimeError(
                "Cannot create the one-active-checkout index because duplicate "
                "ACTIVE checkouts exist. Resolve duplicate data manually first."
            )

    op.create_index(
        INDEX_NAME,
        "checkouts",
        ["student_id"],
        unique=True,
        postgresql_where=ACTIVE_CHECKOUT_PREDICATE,
        sqlite_where=ACTIVE_CHECKOUT_PREDICATE,
    )


def downgrade() -> None:
    """Remove the active-checkout uniqueness guard."""

    op.drop_index(INDEX_NAME, table_name="checkouts")
