"""SQLAlchemy engine, declarative base, and session dependency."""

from collections.abc import Generator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by every application model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


settings = get_settings()

engine: Engine = create_engine(
    settings.database_url,
    connect_args={
        "connect_timeout": settings.database_connect_timeout_seconds,
    },
    pool_pre_ping=True,
    pool_recycle=1800,
)

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Yield a transaction-capable database session for one request."""

    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
