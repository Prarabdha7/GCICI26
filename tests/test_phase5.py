"""Phase 5 tests: swappable providers, research/lead-gen agents, persist_node.

Every external HTTP call (Serper, ScrapeGraph, Hunter.io, Google Places) is
mocked — zero real API usage.

    pytest tests/test_phase5.py -v
"""

from __future__ import annotations

import uuid

import httpx
import pytest

from app.agents import leads as leads_module
from app.agents import providers
from app.agents import research as research_module
from app.config import settings
from app.db.database import session_scope
from app.db.models import ContentQueue, Lead
from app.graph import nodes as nodes_module


def _fake_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=json_data, request=httpx.Request("GET", "https://example.test"))


# --------------------------------------------------------------------------- #
# providers.py — search
# --------------------------------------------------------------------------- #


def test_serper_search_maps_organic_results(monkeypatch) -> None:
    monkeypatch.setattr(
        providers.httpx,
        "post",
        lambda *a, **kw: _fake_response({"organic": [{"title": "T", "link": "https://a.test", "snippet": "s"}]}),
    )

    results = providers.SerperSearch(api_key="key").search("query")

    assert results == [{"title": "T", "url": "https://a.test", "snippet": "s"}]


# --------------------------------------------------------------------------- #
# providers.py — discovery
# --------------------------------------------------------------------------- #


def test_google_places_discovery_maps_places(monkeypatch) -> None:
    monkeypatch.setattr(
        providers.httpx,
        "get",
        lambda *a, **kw: _fake_response({"results": [{"name": "Acme", "website": "https://acme.test"}]}),
    )

    prospects = providers.GooglePlacesDiscovery(api_key="key").discover(niche="jewellers", country="SG")

    assert prospects == [{"company_name": "Acme", "website": "https://acme.test"}]


def test_google_places_discovery_requires_api_key() -> None:
    with pytest.raises(providers.ProviderError):
        providers.GooglePlacesDiscovery(api_key="").discover(niche="jewellers", country="SG")


# --------------------------------------------------------------------------- #
# providers.py — scraping and enrichment
# --------------------------------------------------------------------------- #


def test_scrapegraph_client_returns_markdown(monkeypatch) -> None:
    monkeypatch.setattr(providers.httpx, "post", lambda *a, **kw: _fake_response({"result": "# Markdown"}))
    assert providers.ScrapeGraphClient(api_key="key").extract_markdown("https://a.test") == "# Markdown"


def test_get_hunter_contacts_returns_emails(monkeypatch) -> None:
    monkeypatch.setattr(
        providers.httpx,
        "get",
        lambda *a, **kw: _fake_response({"data": {"emails": [{"value": "a@acme.test"}]}}),
    )
    assert providers.get_hunter_contacts("acme.test", api_key="key") == [{"value": "a@acme.test"}]


def test_get_hunter_contacts_requires_api_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "hunter_api_key", "")
    with pytest.raises(providers.ProviderError):
        providers.get_hunter_contacts("acme.test", api_key="")


# --------------------------------------------------------------------------- #
# provider selection — swaps on available keys
# --------------------------------------------------------------------------- #


def test_get_search_provider_uses_serper(monkeypatch) -> None:
    monkeypatch.setattr(settings, "serper_api_key", "key")
    assert isinstance(providers.get_search_provider(), providers.SerperSearch)


def test_get_search_provider_raises_with_no_keys(monkeypatch) -> None:
    monkeypatch.setattr(settings, "serper_api_key", "")
    with pytest.raises(providers.ProviderError):
        providers.get_search_provider()


def test_get_discovery_provider_uses_google_places(monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_places_api_key", "key")
    assert isinstance(providers.get_discovery_provider(), providers.GooglePlacesDiscovery)


def test_get_discovery_provider_raises_with_no_keys(monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_places_api_key", "")
    with pytest.raises(providers.ProviderError):
        providers.get_discovery_provider()


# --------------------------------------------------------------------------- #
# research_node
# --------------------------------------------------------------------------- #


def test_research_node_builds_digest_from_live_research(monkeypatch) -> None:
    captured = {}

    async def fake_research_summary(query, **kw):
        captured["query"] = query
        return "live crawled markdown"

    def fake_text_call(*, system, user, temperature=None, provider=None):
        captured["user"] = user
        return "digest"

    monkeypatch.setattr(research_module, "research_summary", fake_research_summary)
    monkeypatch.setattr(research_module, "text_call", fake_text_call)

    result = research_module.research_node({"brand": "Jade", "niche": "jewellers", "country": "SG"})

    assert result == {"research_notes": "digest"}
    assert "live crawled markdown" in captured["user"]
    assert "jewellers" in captured["query"]


def test_research_node_falls_back_to_mock_digest_when_live_research_is_empty(monkeypatch) -> None:
    captured = {}

    async def fake_research_summary(query, **kw):
        return ""

    def fake_text_call(*, system, user, temperature=None, provider=None):
        captured["user"] = user
        return "digest"

    monkeypatch.setattr(research_module, "research_summary", fake_research_summary)
    monkeypatch.setattr(research_module, "text_call", fake_text_call)

    research_module.research_node({"brand": "Jade", "niche": "jewellers", "country": "SG"})

    # MockSearchProvider's canned results should ground the fallback digest.
    assert "chubb" in captured["user"].lower() or "jade" in captured["user"].lower()


# --------------------------------------------------------------------------- #
# leads.py nodes
# --------------------------------------------------------------------------- #


def test_discovery_node_returns_provider_results(monkeypatch) -> None:
    class FakeDiscovery(providers.BaseDiscoveryProvider):
        def discover(self, *, niche, country, max_results=10):
            return [{"company_name": "Acme", "website": "https://acme.test"}]

    monkeypatch.setattr(leads_module, "get_discovery_provider", lambda: FakeDiscovery())

    result = leads_module.discovery_node({"niche": "jewellers", "country": "SG"})

    assert result == {"discovered": [{"company_name": "Acme", "website": "https://acme.test"}]}


def test_enrichment_node_attaches_contacts_by_domain(monkeypatch) -> None:
    captured = {}

    def fake_get_hunter_contacts(domain):
        captured["domain"] = domain
        return [{"value": "a@acme.test"}]

    monkeypatch.setattr(leads_module, "get_hunter_contacts", fake_get_hunter_contacts)

    state = {"discovered": [{"company_name": "Acme", "website": "https://acme.test/about"}]}
    result = leads_module.enrichment_node(state)

    assert captured["domain"] == "acme.test"
    assert result["enriched"][0]["contacts"] == [{"value": "a@acme.test"}]


def test_enrichment_node_degrades_gracefully_without_hunter_key(monkeypatch) -> None:
    def fake_get_hunter_contacts(domain):
        raise providers.ProviderError("no key")

    monkeypatch.setattr(leads_module, "get_hunter_contacts", fake_get_hunter_contacts)

    state = {"discovered": [{"company_name": "Acme", "website": "https://acme.test"}]}
    result = leads_module.enrichment_node(state)

    assert result["enriched"][0]["contacts"] == []


def test_scoring_outreach_node_merges_verdict_into_prospect(monkeypatch) -> None:
    monkeypatch.setattr(
        leads_module,
        "structured_call",
        lambda **kw: {"fit_score": 80, "score_rationale": "good fit", "outreach_draft": "hello"},
    )

    state = {
        "brand": "Jade",
        "research_notes": "",
        "enriched": [{"company_name": "Acme", "website": "https://acme.test", "contacts": []}],
    }
    result = leads_module.scoring_outreach_node(state)

    assert result["leads"] == [
        {
            "company_name": "Acme",
            "website": "https://acme.test",
            "contacts": [],
            "fit_score": 80,
            "score_rationale": "good fit",
            "outreach_draft": "hello",
        }
    ]


def test_lead_score_schema_is_exact() -> None:
    props = leads_module.LEAD_SCORE_SCHEMA["properties"]
    assert set(props) == {"fit_score", "score_rationale", "outreach_draft"}
    assert set(leads_module.LEAD_SCORE_SCHEMA["required"]) == {"fit_score", "score_rationale", "outreach_draft"}


def test_persist_leads_node_writes_rows(monkeypatch) -> None:
    state = {
        "brand": "Jade",
        "niche": "jewellers",
        "country": "SG",
        "leads": [
            {
                "company_name": "Acme",
                "website": "https://acme.test",
                "contacts": [{"value": "a@acme.test"}],
                "fit_score": 80,
                "score_rationale": "good fit",
                "outreach_draft": "hello",
            }
        ],
    }

    result = leads_module.persist_leads_node(state)

    assert len(result["lead_ids"]) == 1
    with session_scope() as db:
        row = db.get(Lead, result["lead_ids"][0])
        assert row.company_name == "Acme"
        assert row.email == "a@acme.test"
        assert row.fit_score == 80
        assert row.target_brand == "Jade"


# --------------------------------------------------------------------------- #
# Full lead-gen graph — parallel research + discovery converge on scoring
# --------------------------------------------------------------------------- #


def test_lead_gen_graph_runs_research_and_discovery_in_parallel(monkeypatch) -> None:
    from app.graph.lead_gen_graph import build_lead_gen_graph

    class FakeDiscovery(providers.BaseDiscoveryProvider):
        def discover(self, *, niche, country, max_results=10):
            return [{"company_name": "Acme", "website": "https://acme.test"}]

    async def fake_research_summary(query, **kw):
        return "live crawled markdown"

    monkeypatch.setattr(research_module, "text_call", lambda **kw: "digest")
    monkeypatch.setattr(research_module, "research_summary", fake_research_summary)
    monkeypatch.setattr(leads_module, "get_discovery_provider", lambda: FakeDiscovery())
    monkeypatch.setattr(leads_module, "get_hunter_contacts", lambda domain: [{"value": "a@acme.test"}])
    monkeypatch.setattr(
        leads_module,
        "structured_call",
        lambda **kw: {"fit_score": 90, "score_rationale": "great", "outreach_draft": "hi"},
    )

    graph = build_lead_gen_graph()
    final_state = graph.invoke(
        {
            "brand": "Jade",
            "niche": "jewellers",
            "country": "SG",
            "research_notes": "",
            "discovered": [],
            "enriched": [],
            "leads": [],
            "lead_ids": [],
        },
        config={"configurable": {"thread_id": str(uuid.uuid4())}},
    )

    assert final_state["research_notes"] == "digest"
    assert len(final_state["lead_ids"]) == 1
    with session_scope() as db:
        row = db.get(Lead, final_state["lead_ids"][0])
        assert row.company_name == "Acme"
        assert row.fit_score == 90


# --------------------------------------------------------------------------- #
# persist_node — the compliant-marketing-draft path
# --------------------------------------------------------------------------- #


def test_persist_node_writes_content_queue_row() -> None:
    state = {
        "brand": "Jade",
        "platform": "linkedin",
        "language": "en",
        "draft_content": "final approved copy",
        "compliance_errors": [],
        "retry_count": 0,
        "feedback_guidance": "",
        "media_path": None,
    }

    result = nodes_module.persist_node(state)

    assert result["status"] == "pending"
    with session_scope() as db:
        row = db.get(ContentQueue, result["content_id"])
        assert row.brand == "Jade"
        assert row.draft_content == "final approved copy"
        assert row.status == "pending"


def test_persist_node_carries_media_path_and_retry_count() -> None:
    state = {
        "brand": "Jade",
        "platform": "instagram",
        "language": "en",
        "draft_content": "copy",
        "compliance_errors": [],
        "retry_count": 2,
        "feedback_guidance": "",
        "media_path": "/tmp/reel.mp4",
    }

    result = nodes_module.persist_node(state)

    with session_scope() as db:
        row = db.get(ContentQueue, result["content_id"])
        assert row.media_path == "/tmp/reel.mp4"
        assert row.retry_count == 2


def test_full_marketing_graph_persists_on_compliance(monkeypatch) -> None:
    from app.graph.graph import build_graph

    monkeypatch.setattr(nodes_module, "text_call", lambda **kw: "draft")
    monkeypatch.setattr(nodes_module, "structured_call", lambda **kw: {"is_compliant": True, "violations": []})
    monkeypatch.setattr(nodes_module, "get_recent_feedback", lambda db, **kw: [])

    graph = build_graph()
    initial_state = {
        "draft_content": "",
        "brand": "Jade",
        "platform": "linkedin",
        "language": "en",
        "compliance_errors": [],
        "retry_count": 0,
        "feedback_guidance": "",
        "media_path": None,
        "status": "",
        "content_id": None,
    }
    final_state = graph.invoke(initial_state, config={"configurable": {"thread_id": str(uuid.uuid4())}})

    assert final_state["status"] == "pending"
    assert final_state["content_id"] is not None
    with session_scope() as db:
        row = db.get(ContentQueue, final_state["content_id"])
        assert row.draft_content == "draft"
