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
    database.SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
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
    "pexels_api_key",
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


@pytest.fixture(autouse=True)
def _no_live_pollinations(monkeypatch):
    """image_call falls back to Pollinations' keyless API when Gemini's
    billing gate blocks it; auto-mock it closed so a test with a blanked
    GEMINI_API_KEY doesn't make a real network call unless it explicitly
    re-patches this itself (see test_image_generation.py's fallback tests)."""
    import app.llm.client as client_module

    def _closed(**kwargs):
        raise client_module.LLMError("Pollinations mocked closed for tests")

    monkeypatch.setattr(client_module, "_pollinations_image", _closed)


@pytest.fixture(autouse=True)
def _no_live_pexels(monkeypatch):
    """assemble_video()'s moviepy fallback fetches real Pexels stock footage
    when PEXELS_API_KEY is set; auto-mock it closed so no test makes a real
    network call unless it explicitly re-patches this itself (the blanked
    key in _no_real_keys already gates this too — this is the same
    belt-and-suspenders pattern as _no_live_pollinations, for a service that
    happens to also be reachable without a key check ever running)."""
    import app.media.stock_video as stock_video_module

    def _closed(*args, **kwargs):
        raise stock_video_module.ProviderError("Pexels mocked closed for tests")

    monkeypatch.setattr(stock_video_module, "fetch_stock_video", _closed)
