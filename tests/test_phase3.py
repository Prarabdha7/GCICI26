"""Phase 3 tests: closed-loop memory retrieval and prompt injection.

    pytest tests/test_phase3.py -v
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.agents import prompts
from app.db.models import Base, FeedbackMemory
from app.graph import nodes as nodes_module
from app.memory.retrieval import format_guidance, get_recent_feedback


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _seed(db: Session, **overrides) -> FeedbackMemory:
    fields = {"brand": "Jade", "platform": "linkedin", "error_tag": "too_salesy", "human_note": "note"}
    fields.update(overrides)
    row = FeedbackMemory(**fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# --------------------------------------------------------------------------- #
# get_recent_feedback
# --------------------------------------------------------------------------- #


def test_filters_by_brand_and_platform(db: Session) -> None:
    _seed(db, brand="Jade", platform="linkedin")
    _seed(db, brand="Jade", platform="instagram")
    _seed(db, brand="DoctorShield", platform="linkedin")

    results = get_recent_feedback(db, brand="Jade", platform="linkedin")

    assert len(results) == 1
    assert results[0].brand == "Jade"
    assert results[0].platform == "linkedin"


def test_orders_newest_first(db: Session) -> None:
    import datetime as dt

    older = _seed(db, human_note="older", timestamp=dt.datetime(2026, 1, 1))
    newer = _seed(db, human_note="newer", timestamp=dt.datetime(2026, 6, 1))

    results = get_recent_feedback(db, brand="Jade", platform="linkedin")

    assert [r.id for r in results] == [newer.id, older.id]


def test_default_limit_matches_settings(db: Session) -> None:
    from app.config import settings

    for i in range(settings.feedback_memory_limit + 3):
        _seed(db, human_note=f"note {i}")

    results = get_recent_feedback(db, brand="Jade", platform="linkedin")

    assert len(results) == settings.feedback_memory_limit


def test_explicit_limit_overrides_default(db: Session) -> None:
    for i in range(5):
        _seed(db, human_note=f"note {i}")

    results = get_recent_feedback(db, brand="Jade", platform="linkedin", limit=2)

    assert len(results) == 2


def test_returns_empty_when_no_rows_match(db: Session) -> None:
    _seed(db, brand="Jaguar Transit")

    assert get_recent_feedback(db, brand="Jade", platform="linkedin") == []


# --------------------------------------------------------------------------- #
# format_guidance — the exact injection contract
# --------------------------------------------------------------------------- #


def test_format_guidance_is_empty_with_no_feedback() -> None:
    assert format_guidance([]) == ""


def test_format_guidance_matches_exact_contract() -> None:
    entry = FeedbackMemory(brand="Jade", platform="linkedin", error_tag="too_salesy", human_note="Reads like a pitch.")

    result = format_guidance([entry])

    assert result == (
        "CRITICAL GUIDANCE: Previously, human reviewers rejected content for "
        "this brand due to: too_salesy: Reads like a pitch.. You MUST NOT "
        "repeat these mistakes."
    )


def test_format_guidance_joins_multiple_entries() -> None:
    entries = [
        FeedbackMemory(brand="Jade", platform="linkedin", error_tag="too_salesy", human_note="Too pushy."),
        FeedbackMemory(brand="Jade", platform="linkedin", error_tag="wrong_cta", human_note="CTA mismatched market."),
    ]

    result = format_guidance(entries)

    assert "too_salesy: Too pushy." in result
    assert "wrong_cta: CTA mismatched market." in result


# --------------------------------------------------------------------------- #
# memory_retrieval_node
# --------------------------------------------------------------------------- #


def test_memory_retrieval_node_writes_feedback_guidance(monkeypatch) -> None:
    canned = [FeedbackMemory(brand="Jade", platform="linkedin", error_tag="too_salesy", human_note="Too pushy.")]
    monkeypatch.setattr(nodes_module, "get_recent_feedback", lambda db, **kw: canned)

    result = nodes_module.memory_retrieval_node(
        {"brand": "Jade", "platform": "linkedin", "language": "en", "draft_content": "",
         "compliance_errors": [], "retry_count": 0, "feedback_guidance": ""}
    )

    assert result["feedback_guidance"] == format_guidance(canned)
    assert result["engagement_guidance"] == ""  # no real engagement measured yet


def test_memory_retrieval_node_returns_empty_guidance_with_no_history(monkeypatch) -> None:
    monkeypatch.setattr(nodes_module, "get_recent_feedback", lambda db, **kw: [])

    result = nodes_module.memory_retrieval_node(
        {"brand": "Jade", "platform": "linkedin", "language": "en", "draft_content": "",
         "compliance_errors": [], "retry_count": 0, "feedback_guidance": ""}
    )

    assert result["feedback_guidance"] == ""
    assert result["engagement_guidance"] == ""


def test_memory_retrieval_node_applies_memgpt_augmentation(monkeypatch) -> None:
    canned = [FeedbackMemory(brand="Jade", platform="linkedin", error_tag="too_salesy", human_note="Too pushy.")]
    monkeypatch.setattr(nodes_module, "get_recent_feedback", lambda db, **kw: canned)
    monkeypatch.setattr(
        nodes_module,
        "augment_guidance_with_memgpt",
        lambda **kw: f"{kw['local_guidance']}\n\nADDITIONAL GUIDANCE (MemGPT): keep tone educational",
    )

    result = nodes_module.memory_retrieval_node(
        {"brand": "Jade", "platform": "linkedin", "language": "en", "draft_content": "",
         "compliance_errors": [], "retry_count": 0, "feedback_guidance": ""}
    )

    assert "ADDITIONAL GUIDANCE (MemGPT)" in result["feedback_guidance"]


# --------------------------------------------------------------------------- #
# content_node — receiving and appending guidance to the system prompt
# --------------------------------------------------------------------------- #


def test_content_node_appends_feedback_guidance_to_system_prompt(monkeypatch) -> None:
    captured = {}

    def fake_text_call(*, system, user, temperature=None, provider=None):
        captured["system"] = system
        return "draft"

    monkeypatch.setattr(nodes_module, "text_call", fake_text_call)

    guidance = "CRITICAL GUIDANCE: Previously, human reviewers rejected content for this brand due to: too_salesy: Too pushy.. You MUST NOT repeat these mistakes."
    state = {
        "brand": "Jade", "platform": "linkedin", "language": "en", "draft_content": "",
        "compliance_errors": [], "retry_count": 0, "feedback_guidance": guidance,
    }

    nodes_module.content_node(state)

    assert guidance in captured["system"]


def test_content_node_injects_no_block_when_guidance_is_empty(monkeypatch) -> None:
    captured = {}

    def fake_text_call(*, system, user, temperature=None, provider=None):
        captured["system"] = system
        return "draft"

    monkeypatch.setattr(nodes_module, "text_call", fake_text_call)

    state = {
        "brand": "Jade", "platform": "linkedin", "language": "en", "draft_content": "",
        "compliance_errors": [], "retry_count": 0, "feedback_guidance": "",
    }

    nodes_module.content_node(state)

    assert "CRITICAL GUIDANCE" not in captured["system"]


def test_content_system_prompt_omits_block_by_default() -> None:
    prompt = prompts.content_system_prompt(brand="Jade", platform="linkedin")
    assert "CRITICAL GUIDANCE" not in prompt


# --------------------------------------------------------------------------- #
# Full graph — memory_retrieval runs before content, guidance flows through
# --------------------------------------------------------------------------- #


def test_graph_runs_memory_retrieval_before_content(monkeypatch) -> None:
    from app.graph.graph import build_graph

    canned = [FeedbackMemory(brand="Jade", platform="linkedin", error_tag="too_salesy", human_note="Too pushy.")]
    monkeypatch.setattr(nodes_module, "get_recent_feedback", lambda db, **kw: canned)

    captured = {}

    def fake_text_call(*, system, user, temperature=None, provider=None):
        captured.setdefault("systems", []).append(system)
        return "draft"

    def fake_structured_call(*, system, user, schema, temperature=None, provider=None):
        return {"is_compliant": True, "violations": []}

    monkeypatch.setattr(nodes_module, "text_call", fake_text_call)
    monkeypatch.setattr(nodes_module, "structured_call", fake_structured_call)

    graph = build_graph()
    initial_state = {
        "draft_content": "", "brand": "Jade", "platform": "linkedin", "language": "en",
        "compliance_errors": [], "retry_count": 0, "feedback_guidance": "",
    }
    final_state = graph.invoke(
        initial_state, config={"configurable": {"thread_id": str(uuid.uuid4())}}
    )

    assert final_state["feedback_guidance"] == format_guidance(canned)
    # content_node ran with the guidance already populated by memory_retrieval_node
    assert format_guidance(canned) in captured["systems"][0]


# --------------------------------------------------------------------------- #
# engagement guidance — the analytics loop feeding generation (real data only)
# --------------------------------------------------------------------------- #


def test_format_engagement_guidance_empty_without_measurements() -> None:
    from app.memory.retrieval import format_engagement_guidance

    assert format_engagement_guidance([], brand="Jade", platform="linkedin") == ""


def test_format_engagement_guidance_skips_demo_rows() -> None:
    from app.db.models import PublishEvent
    from app.memory.retrieval import format_engagement_guidance

    demo = PublishEvent(content_id=1, event="engagement", provider="mock-demo",
                        external_post_id="mock-x", payload={"impressions": 9999, "ctr": 0.9, "demo": True})
    assert format_engagement_guidance([demo], brand="Jade", platform="linkedin") == ""


def test_format_engagement_guidance_surfaces_real_numbers() -> None:
    from app.db.models import PublishEvent
    from app.memory.retrieval import format_engagement_guidance

    real = PublishEvent(content_id=7, event="engagement", provider="buffer",
                        external_post_id="buf-7", payload={"impressions": 1200, "ctr": 0.031})
    result = format_engagement_guidance([real], brand="Jade", platform="linkedin")
    assert "1200" in result and "content_id=7" in result


def test_memory_retrieval_node_injects_real_engagement(monkeypatch) -> None:
    from app.db.models import PublishEvent

    real = PublishEvent(content_id=7, event="engagement", provider="buffer",
                        external_post_id="buf-7", payload={"impressions": 1200, "ctr": 0.031})
    monkeypatch.setattr(nodes_module, "get_recent_feedback", lambda db, **kw: [])
    monkeypatch.setattr(nodes_module, "get_recent_engagement", lambda db, **kw: [real])

    result = nodes_module.memory_retrieval_node(
        {"brand": "Jade", "platform": "linkedin", "language": "en", "draft_content": "",
         "compliance_errors": [], "retry_count": 0, "feedback_guidance": ""}
    )

    assert "MEASURED PERFORMANCE" in result["engagement_guidance"]
