"""Tests for the shared DuckDuckGo + Crawl4AI research utility
(app/utils/research.py) and its wiring into market_research_node and the
lead-gen research_node.

CRITICAL: never let the real `crawl4ai` package get imported here — importing
it has the side effect of loading .env into the real process os.environ
(discovered while building this), which would leak secrets into other tests.
A fake module is injected into sys.modules before calling research_summary()
with a non-empty URL list, so the lazy `from crawl4ai import AsyncWebCrawler`
inside it resolves to the fake instead of ever importing the real package.

    pytest tests/test_research_utils.py -v
"""

from __future__ import annotations

import sys
import types

import pytest

from app.utils import research as research_utils


def _install_fake_crawl4ai(
    monkeypatch, markdown_by_url: dict[str, str] | None = None, *, raise_for: set[str] | None = None
):
    markdown_by_url = markdown_by_url or {}
    raise_for = raise_for or set()

    class FakeCrawlResult:
        def __init__(self, markdown: str) -> None:
            self.markdown = markdown

    class FakeCrawler:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url: str):
            if url in raise_for:
                raise RuntimeError("scrape failed")
            return FakeCrawlResult(markdown_by_url.get(url, f"# {url}\ncontent"))

    fake_module = types.ModuleType("crawl4ai")
    fake_module.AsyncWebCrawler = FakeCrawler
    monkeypatch.setitem(sys.modules, "crawl4ai", fake_module)


# --------------------------------------------------------------------------- #
# _search_urls
# --------------------------------------------------------------------------- #


def test_search_urls_returns_hrefs_on_first_success(monkeypatch) -> None:
    monkeypatch.setattr(
        research_utils,
        "DDGS",
        lambda: type(
            "D",
            (),
            {
                "text": lambda self, q, max_results=None: [
                    {"href": "https://a.test"},
                    {"href": "https://b.test"},
                ]
            },
        )(),
    )
    urls = research_utils._search_urls("query", max_results=2, attempts=3)
    assert urls == ["https://a.test", "https://b.test"]


def test_search_urls_retries_then_succeeds(monkeypatch) -> None:
    calls = {"n": 0}

    class FlakyDDGS:
        def text(self, q, max_results=None):
            calls["n"] += 1
            if calls["n"] < 3:
                return []
            return [{"href": "https://a.test"}]

    monkeypatch.setattr(research_utils, "DDGS", FlakyDDGS)
    urls = research_utils._search_urls("query", max_results=2, attempts=3)
    assert urls == ["https://a.test"]
    assert calls["n"] == 3


def test_search_urls_gives_up_after_all_attempts_empty(monkeypatch) -> None:
    monkeypatch.setattr(research_utils, "DDGS", lambda: type("D", (), {"text": lambda self, q, max_results=None: []})())
    assert research_utils._search_urls("query", max_results=2, attempts=2) == []


def test_search_urls_survives_ddgs_raising(monkeypatch) -> None:
    class RaisingDDGS:
        def text(self, q, max_results=None):
            raise RuntimeError("blocked")

    monkeypatch.setattr(research_utils, "DDGS", RaisingDDGS)
    assert research_utils._search_urls("query", max_results=2, attempts=2) == []


# --------------------------------------------------------------------------- #
# research_summary
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_research_summary_empty_when_no_urls_found(monkeypatch) -> None:
    monkeypatch.setattr(research_utils, "_search_urls", lambda *a, **kw: [])
    assert await research_utils.research_summary("query") == ""


@pytest.mark.asyncio
async def test_research_summary_never_imports_crawl4ai_when_no_urls(monkeypatch) -> None:
    sys.modules.pop("crawl4ai", None)
    monkeypatch.setattr(research_utils, "_search_urls", lambda *a, **kw: [])
    await research_utils.research_summary("query")
    assert "crawl4ai" not in sys.modules


@pytest.mark.asyncio
async def test_research_summary_concatenates_scraped_markdown(monkeypatch) -> None:
    monkeypatch.setattr(research_utils, "_search_urls", lambda *a, **kw: ["https://a.test", "https://b.test"])
    _install_fake_crawl4ai(monkeypatch, {"https://a.test": "Alpha content", "https://b.test": "Beta content"})

    summary = await research_utils.research_summary("query")

    assert "https://a.test" in summary
    assert "Alpha content" in summary
    assert "https://b.test" in summary
    assert "Beta content" in summary


@pytest.mark.asyncio
async def test_research_summary_skips_a_url_that_fails_to_scrape(monkeypatch) -> None:
    monkeypatch.setattr(research_utils, "_search_urls", lambda *a, **kw: ["https://a.test", "https://b.test"])
    _install_fake_crawl4ai(monkeypatch, {"https://b.test": "Beta content"}, raise_for={"https://a.test"})

    summary = await research_utils.research_summary("query")

    assert "https://a.test" not in summary
    assert "Beta content" in summary


@pytest.mark.asyncio
async def test_research_summary_truncates_long_pages(monkeypatch) -> None:
    monkeypatch.setattr(research_utils, "_search_urls", lambda *a, **kw: ["https://a.test"])
    _install_fake_crawl4ai(monkeypatch, {"https://a.test": "x" * 10_000})

    summary = await research_utils.research_summary("query")

    assert len(summary) < 10_000


# --------------------------------------------------------------------------- #
# market_research_node (app/graph/nodes.py) — the main content graph's hook
# --------------------------------------------------------------------------- #


def test_market_research_node_writes_market_research(monkeypatch) -> None:
    from app.graph import nodes as nodes_module

    async def fake_summary(query, **kw):
        return f"digest for: {query}"

    monkeypatch.setattr(nodes_module, "research_summary", fake_summary)

    result = nodes_module.market_research_node({"brand": "Jade", "platform": "instagram", "topic": "SIJE memo cover"})

    assert result == {"market_research": "digest for: Jade SIJE memo cover news"}


def test_market_research_node_falls_back_to_brand_when_no_topic(monkeypatch) -> None:
    from app.graph import nodes as nodes_module

    captured = {}

    async def fake_summary(query, **kw):
        captured["query"] = query
        return "digest"

    monkeypatch.setattr(nodes_module, "research_summary", fake_summary)

    nodes_module.market_research_node({"brand": "DoctorShield", "platform": "linkedin"})

    assert captured["query"] == "DoctorShield insurance news"


def test_market_research_node_degrades_gracefully_on_failure(monkeypatch) -> None:
    from app.graph import nodes as nodes_module

    async def failing_summary(query, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(nodes_module, "research_summary", failing_summary)

    result = nodes_module.market_research_node({"brand": "Jade", "platform": "instagram"})

    assert result == {"market_research": ""}


def test_content_node_grounds_prompt_in_market_research(monkeypatch) -> None:
    from app.graph import nodes as nodes_module

    captured = {}

    def fake_text_call(*, system, user, temperature=None, provider=None):
        captured["user"] = user
        return "draft"

    monkeypatch.setattr(nodes_module, "text_call", fake_text_call)

    state = {
        "brand": "Jade",
        "platform": "instagram",
        "language": "en",
        "draft_content": "",
        "compliance_errors": [],
        "retry_count": 0,
        "feedback_guidance": "",
        "market_research": "### https://a.test\nCompetitor X raised premiums 10%.",
    }
    nodes_module.content_node(state)

    assert "Competitor X raised premiums 10%" in captured["user"]


def test_content_node_omits_research_block_when_absent(monkeypatch) -> None:
    from app.graph import nodes as nodes_module

    captured = {}

    def fake_text_call(*, system, user, temperature=None, provider=None):
        captured["user"] = user
        return "draft"

    monkeypatch.setattr(nodes_module, "text_call", fake_text_call)

    state = {
        "brand": "Jade",
        "platform": "instagram",
        "language": "en",
        "draft_content": "",
        "compliance_errors": [],
        "retry_count": 0,
        "feedback_guidance": "",
    }
    nodes_module.content_node(state)

    assert "live market research" not in captured["user"].lower()
