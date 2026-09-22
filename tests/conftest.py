"""Per-test isolated database: no test writes to the real ja_assure.db, and no
test can see rows a previous test committed (e.g. dashboard actions leaving
rows in `approved` status, which the Phase 7 worker would otherwise pick up)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base


@pytest.fixture(autouse=True)
def _isolated_database():
    import app.db.database as database

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    database.engine = engine
    database.SessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    yield
    engine.dispose()
