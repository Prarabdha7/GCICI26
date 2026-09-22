"""SQLAlchemy engine and session management.

Engine-agnostic by design: the same models run on SQLite (development) and
PostgreSQL (demo). Only DATABASE_URL changes.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

log = logging.getLogger(__name__)

_connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Iterator[Session]:
    """FastAPI dependency. All database access goes through this."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Session access for code outside a FastAPI request (graph nodes, workers)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create every table that does not yet exist."""
    from app.db import models  # noqa: F401  (registers models on Base.metadata)
    from app.db.models import Base

    Base.metadata.create_all(bind=engine)
    tables = ", ".join(sorted(Base.metadata.tables))
    log.info("Database ready at %s — tables: %s", settings.database_url, tables)
