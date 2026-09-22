"""Demo/real segregation: simulations are labeled and demo-gated, real mode is honest.

Real mode (default): unconfigured LLM/providers/publisher raise instead of
fabricating. Demo mode (DEMO_MODE=true): fallbacks engage and every output is
tagged [DEMO]/mock/is_demo, excluded from real metrics.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.db.database import session_scope
from app.db.models import ContentQueue, ContentStatus
from app.graph import nodes as nodes_module
from app.llm.client import LLMError
from app.agents import providers


def _marketing_state(**overrides):
    state = {
        "draft_content": "", "brand": "Jade", "platform": "linkedin", "language": "en",
        "compliance_errors": [], "retry_count": 0, "feedback_guidance": "",
        "media_path": None, "status": "", "content_id": None,
    }
    state.update(overrides)
    return state


def test_real_mode_content_fails_honestly_without_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(nodes_module, "text_call", lambda **kw: (_ for _ in ()).throw(LLMError("no key")))
    with pytest.raises(LLMError):
        nodes_module.content_node(_marketing_state())


def test_demo_mode_content_is_labeled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(nodes_module, "text_call", lambda **kw: (_ for _ in ()).throw(LLMError("no key")))
    result = nodes_module.content_node(_marketing_state())
    assert result["draft_content"].startswith("[DEMO]")
    assert result["is_demo"] is True


def test_demo_rows_excluded_from_real_stats(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    with session_scope() as db:
        db.add(ContentQueue(brand="Jade", platform="linkedin", language="en", draft_content="[DEMO] x", status=ContentStatus.APPROVED.value, is_demo=True))
        db.add(ContentQueue(brand="Jade", platform="linkedin", language="en", draft_content="real", status=ContentStatus.REJECTED.value, is_demo=False))
        db.commit()
    with TestClient(app) as client:
        stats = client.get("/api/stats").json()
    assert stats["by_status"].get("approved", 0) == 0
    assert stats["by_status"].get("rejected", 0) == 1


def test_real_mode_publisher_resolve_fails_honestly(monkeypatch) -> None:
    from worker import scheduler as scheduler_module
    from worker.publisher import PublisherError

    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "buffer_access_token", "")
    monkeypatch.setattr(settings, "ayrshare_api_key", "")
    with pytest.raises(PublisherError):
        scheduler_module._resolve_publisher()


def test_demo_mode_publisher_resolves_mock(monkeypatch) -> None:
    from worker import scheduler as scheduler_module
    from worker.publisher import MockPublisher

    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "buffer_access_token", "")
    monkeypatch.setattr(settings, "ayrshare_api_key", "")
    assert isinstance(scheduler_module._resolve_publisher(), MockPublisher)


def test_confirm_leaves_real_scheduled_untouched(monkeypatch) -> None:
    from worker import scheduler as scheduler_module

    monkeypatch.setattr(settings, "demo_mode", True)
    with session_scope() as db:
        row = ContentQueue(brand="Jade", platform="linkedin", language="en", draft_content="real",
                           status=ContentStatus.SCHEDULED.value, external_post_id="buf-real-1", is_demo=False)
        db.add(row)
        db.commit()
        content_id = row.id
    assert scheduler_module.confirm_scheduled_as_published() == 0
    with session_scope() as db:
        assert db.get(ContentQueue, content_id).status == ContentStatus.SCHEDULED.value


def test_heuristic_violations_labeled_local(monkeypatch) -> None:
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(nodes_module, "structured_call", lambda **kw: (_ for _ in ()).throw(LLMError("down")))
    result = nodes_module.compliance_gate_node(_marketing_state(draft_content="100% guaranteed payout"))
    assert result["compliance_errors"]
    assert all(v.startswith("[local-check]") for v in result["compliance_errors"])


def test_seed_script_refuses_real_mode(monkeypatch) -> None:
    from scripts import seed_demo

    monkeypatch.setattr(settings, "demo_mode", False)
    assert seed_demo.main() == 2


def test_local_samples_missing_file_is_honest_empty(monkeypatch, tmp_path) -> None:
    from app.agents import local_samples

    monkeypatch.setattr(settings, "local_samples_path", str(tmp_path / "absent.json"))
    assert local_samples.search_results() == []
    assert local_samples.prospects() == []
    assert local_samples.personas() == {}
    assert local_samples.seed_rows() == {}


def test_local_samples_personas_drive_focus_group(monkeypatch, tmp_path) -> None:
    import json

    from app.agents import local_samples
    from app.agents.formats import focus_group_notes

    samples = tmp_path / "samples.json"
    samples.write_text(json.dumps({"personas": {
        "doctor": {"match": ["doctor"], "specific": "SPECIFIC-DOC", "na": "NA-DOC"},
        "goldsmith": {"match": ["jade"], "specific": "SPECIFIC-JADE", "na": "NA-JADE"},
        "freight": {"match": ["jaguar"], "specific": "SPECIFIC-JAG", "na": "NA-JAG"},
        "guarantee_flag": "FLAG",
    }}), encoding="utf-8")
    monkeypatch.setattr(settings, "local_samples_path", str(samples))
    notes = focus_group_notes("guaranteed cover", "Jade")
    assert "SPECIFIC-JADE" in notes and "NA-DOC" in notes and "FLAG" in notes
    assert local_samples.personas()["doctor"]["specific"] == "SPECIFIC-DOC"


def test_seed_demo_loads_rows_from_local_file(monkeypatch, tmp_path) -> None:
    import json

    from scripts import seed_demo

    samples = tmp_path / "samples.json"
    samples.write_text(json.dumps({"seed_rows": {
        "content": [{"brand": "Jade", "platform": "linkedin", "language": "en",
                     "draft_content": "tmp demo", "status": "pending"}],
        "feedback": [], "leads": [],
    }}), encoding="utf-8")
    monkeypatch.setattr(settings, "local_samples_path", str(samples))
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(seed_demo, "_ensure_sample_media", lambda: None)
    assert seed_demo.main() == 0
    with session_scope() as db:
        from sqlalchemy import select

        row = db.scalars(select(ContentQueue).where(ContentQueue.is_demo.is_(True))).one()
        assert row.draft_content == "tmp demo"


def test_seed_demo_seeds_nothing_without_local_file(monkeypatch, tmp_path) -> None:
    from scripts import seed_demo

    monkeypatch.setattr(settings, "local_samples_path", str(tmp_path / "absent.json"))
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(seed_demo, "_ensure_sample_media", lambda: None)
    assert seed_demo.main() == 0
    with session_scope() as db:
        from sqlalchemy import select

        assert db.scalar(select(ContentQueue.id).limit(1)) is None
