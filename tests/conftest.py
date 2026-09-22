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


# Keys must never leak into tests from a developer's local .env: the suite
# asserts fail-closed behavior with no keys, so every secret-bearing setting
# is blanked (and demo_mode forced off) for each test. Tests that need a key
# set it explicitly via monkeypatch.
_SECRET_ATTRS = (
    "gemini_api_key",
    "openai_api_key",
    "serper_api_key",
    "scrapegraph_api_key",
    "google_places_api_key",
    "hunter_api_key",
    "buffer_access_token",
    "ayrshare_api_key",
)


@pytest.fixture(autouse=True)
def _no_real_keys(monkeypatch):
    from app.config import settings

    for attr in _SECRET_ATTRS:
        monkeypatch.setattr(settings, attr, "")
    monkeypatch.setattr(settings, "demo_mode", False)


@pytest.fixture(autouse=True)
def _no_live_research(monkeypatch):
    """market_research_node / research_node hit a real DuckDuckGo + Crawl4AI
    search by default; auto-mock both modules' bound name so no test makes a
    live network call unless it explicitly re-patches this itself."""

    async def _empty_research(*args, **kwargs) -> str:
        return ""

    import app.agents.research as research_module
    import app.graph.nodes as nodes_module

    monkeypatch.setattr(nodes_module, "research_summary", _empty_research)
    monkeypatch.setattr(research_module, "research_summary", _empty_research)
