"""Memory vault: DB rows project to Obsidian-compatible markdown + graph."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.db.database import session_scope
from app.db.models import ContentQueue, ContentStatus, FeedbackMemory
from app.main import app
from app.memory.vault import export_vault


def _seed(db) -> None:
    row = ContentQueue(brand="Jade", platform="linkedin", language="en",
                       draft_content="draft", status=ContentStatus.PENDING.value)
    db.add(row)
    db.commit()
    db.refresh(row)
    db.add(FeedbackMemory(brand="Jade", platform="linkedin", error_tag="too_salesy",
                          human_note="Too pushy.", content_id=row.id))
    db.commit()


def test_export_vault_writes_markdown_and_graph(tmp_path: Path) -> None:
    with session_scope() as db:
        _seed(db)
        graph = export_vault(db, root=tmp_path / "vault")

    assert (tmp_path / "vault" / "brands" / "Jade.md").exists()
    assert (tmp_path / "vault" / "regulations" / "Singapore.md").exists()
    assert list((tmp_path / "vault" / "feedback").glob("*.md"))
    assert list((tmp_path / "vault" / "assets").glob("*.md"))
    assert "[[Regulation: Singapore]]" in (tmp_path / "vault" / "brands" / "Jade.md").read_text(encoding="utf-8")
    assert "[[Brand: Jade]]" in next((tmp_path / "vault" / "feedback").glob("*.md")).read_text(encoding="utf-8")

    kinds = {n["kind"] for n in graph["nodes"]}
    assert {"brand", "regulation", "feedback", "asset"} <= kinds
    assert any(e[0].startswith("feedback:") and e[1].startswith("brand:") for e in graph["edges"])


def test_vault_endpoint_returns_graph(tmp_path: Path, monkeypatch) -> None:
    import app.memory.vault as vault_module
    from app.memory.vault import export_vault as real_export

    def _to_tmp(db):
        return real_export(db, root=tmp_path / "vault")

    monkeypatch.setattr(vault_module, "export_vault", _to_tmp)
    with session_scope() as db:
        _seed(db)
    with TestClient(app) as client:
        graph = client.get("/api/memory/vault").json()
        assert any(n["kind"] == "feedback" for n in graph["nodes"])
        assert any(n["kind"] == "brand" for n in graph["nodes"])
