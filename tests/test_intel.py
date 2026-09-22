"""Intel digest persistence: the periodic sweep stores rows the UI can show."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.database import session_scope
from app.db.models import IntelDigest
from app.main import app


def test_intel_sweep_persists_one_row_per_target(monkeypatch) -> None:
    import app.agents.research as research_module

    def fake_research_node(state):
        return {"research_notes": f"notes for {state['brand']}"}

    monkeypatch.setattr(research_module, "research_node", fake_research_node)

    import worker.intel as intel_module

    results = intel_module.intel_sweep()

    assert len(results) == 3
    with session_scope() as db:
        from sqlalchemy import select

        rows = list(db.scalars(select(IntelDigest)))
        assert len(rows) == 3
        assert all(r.digest_text for r in rows)


def test_intel_sweep_records_failures_honestly(monkeypatch) -> None:
    import app.agents.research as research_module
    import worker.intel as intel_module

    def boom(state):
        raise RuntimeError("network down")

    monkeypatch.setattr(research_module, "research_node", boom)

    results = intel_module.intel_sweep()

    assert len(results) == 3
    with session_scope() as db:
        from sqlalchemy import select

        rows = list(db.scalars(select(IntelDigest)))
        assert all(r.digest_text == "" for r in rows)


def test_latest_digests_returns_newest_per_brand() -> None:
    from worker import intel as intel_module

    with session_scope() as db:
        db.add(IntelDigest(brand="Jade", niche="n", country="Singapore", digest_text="old"))
        db.add(IntelDigest(brand="Jade", niche="n", country="Singapore", digest_text="new"))
        db.commit()
        latest = intel_module.latest_digests(db)

    jade = [d for d in latest if d["brand"] == "Jade" and d["country"] == "Singapore"]
    assert len(jade) == 1
    assert jade[0]["digest_text"] == "new"


def test_intel_digests_endpoint_and_dashboard_render() -> None:
    with TestClient(app) as client:
        assert client.get("/api/intel/digests").status_code == 200
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "intel" in response.text.lower()
