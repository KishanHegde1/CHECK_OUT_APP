"""Alembic runtime configuration for online and offline migrations."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Connection, make_url
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401  # Import all mapped tables into Base.metadata.
from app.core.config import get_settings
from app.core.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> URL:
    """Return the validated URL without placing credentials in Alembic config."""

    return make_url(get_settings().database_url)


def _context_options() -> dict[str, object]:
    """Return comparison settings shared by online and offline modes."""

    return {
        "target_metadata": target_metadata,
        "compare_type": True,
        "compare_server_default": True,
        "include_schemas": False,
        "transaction_per_migration": True,
    }


def run_migrations_offline() -> None:
    """Emit migration SQL without opening a database connection."""

    context.configure(
        url=_database_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_context_options(),
    )

    with context.begin_transaction():
        context.run_migrations()


def _run_migrations_on_connection(connection: Connection) -> None:
    """Run migrations with an already-open SQLAlchemy connection."""

    context.configure(connection=connection, **_context_options())

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against PostgreSQL with a non-persistent engine pool."""

    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        _run_migrations_on_connection(supplied_connection)
        return

    connectable = create_engine(
        _database_url(),
        connect_args={
            "connect_timeout": get_settings().database_connect_timeout_seconds,
        },
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        with connectable.connect() as connection:
            _run_migrations_on_connection(connection)
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
