"""SQLAlchemy engine and session management.

Engine-agnostic by design: the same models run on SQLite (development) and
PostgreSQL (demo). Only DATABASE_URL changes.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

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
    """Create every table that does not yet exist, then additively backfill
    columns added after a database was first created (preserves existing rows —
    deleting the .db file is never required for additive schema changes)."""
    from sqlalchemy import inspect, text

    from app.db import models  # noqa: F401  (registers models on Base.metadata)
    from app.db.models import Base

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        inspector = inspect(conn)
        for table in Base.metadata.tables.values():
            try:
                present = {col["name"] for col in inspector.get_columns(table.name)}
            except Exception:
                continue
            for column in table.columns:
                if column.name not in present:
                    ddl = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type.compile(dialect=conn.dialect)}"
                    if column.default is not None and getattr(column.default, "arg", None) is not None:
                        ddl += f" DEFAULT {column.default.arg!r}" if isinstance(column.default.arg, str) else ""
                    try:
                        conn.execute(text(ddl))
                        log.info("Migrated %s: added column %s", table.name, column.name)
                        arg = getattr(column.default, "arg", None)
                        if isinstance(arg, bool):
                            conn.execute(
                                text(f"UPDATE {table.name} SET {column.name} = :v WHERE {column.name} IS NULL"),
                                {"v": int(arg)},
                            )
                    except Exception:
                        log.exception("Migration failed for %s.%s", table.name, column.name)
    tables = ", ".join(sorted(Base.metadata.tables))
    log.info("Database ready at %s — tables: %s", settings.database_url, tables)
