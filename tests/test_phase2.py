"""Phase 2 tests: graph execution and the circuit breaker.

The LLM client is monkeypatched at the point of use (`app.graph.nodes`) so
these run without a network connection or an API key.

    pytest tests/test_phase2.py -v
"""

from __future__ import annotations

import uuid

import pytest

from app.graph import nodes as nodes_module
from app.graph.graph import build_graph
from app.graph.routing import COMPLIANT, CONTENT, MANUAL_INTERVENTION, route_after_compliance
from app.graph.state import MarketingState


def _initial_state(**overrides) -> MarketingState:
    state: MarketingState = {
        "draft_content": "",
        "brand": "Jade",
        "platform": "linkedin",
        "language": "en",
        "compliance_errors": [],
        "retry_count": 0,
    }
    state.update(overrides)
    return state


def _run_config() -> dict:
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


# --------------------------------------------------------------------------- #
# route_after_compliance — the circuit breaker
# --------------------------------------------------------------------------- #


def test_route_passes_compliant_draft_through() -> None:
    state = _initial_state(compliance_errors=[], retry_count=0)
    assert route_after_compliance(state) == COMPLIANT


@pytest.mark.parametrize("retry_count", [1, 2, 3])
def test_route_cycles_back_to_content_within_retry_budget(retry_count: int) -> None:
    state = _initial_state(compliance_errors=["bad"], retry_count=retry_count)
    assert route_after_compliance(state) == CONTENT


def test_route_trips_circuit_breaker_past_max_retries() -> None:
    state = _initial_state(compliance_errors=["bad"], retry_count=4)
    assert route_after_compliance(state) == MANUAL_INTERVENTION


# --------------------------------------------------------------------------- #
# Node-level behaviour
# --------------------------------------------------------------------------- #


def test_content_node_injects_prior_violations_into_the_rewrite_prompt(monkeypatch) -> None:
    captured = {}

    def fake_text_call(*, system, user, temperature=None, provider=None):
        captured["user"] = user
        return "new draft"

    monkeypatch.setattr(nodes_module, "text_call", fake_text_call)

    state = _initial_state(compliance_errors=["Uses 'guaranteed' (Rubric 1)"], retry_count=1)
    result = nodes_module.content_node(state)

    assert result == {"draft_content": "new draft"}
    assert "Uses 'guaranteed' (Rubric 1)" in captured["user"]


def test_compliance_gate_node_increments_retry_count_only_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        nodes_module,
        "structured_call",
        lambda **kwargs: {"is_compliant": False, "violations": ["v1"]},
    )
    state = _initial_state(retry_count=0)
    result = nodes_module.compliance_gate_node(state)
    assert result == {"compliance_errors": ["v1"], "retry_count": 1}


def test_compliance_gate_node_clears_violations_when_compliant(monkeypatch) -> None:
    monkeypatch.setattr(
        nodes_module,
        "structured_call",
        lambda **kwargs: {"is_compliant": True, "violations": []},
    )
    state = _initial_state(compliance_errors=["stale"], retry_count=2)
    result = nodes_module.compliance_gate_node(state)
    assert result == {"compliance_errors": []}
    assert "retry_count" not in result  # only the failure path bumps it


# --------------------------------------------------------------------------- #
# Full graph execution
# --------------------------------------------------------------------------- #


def _patch_llm(monkeypatch, *, compliant_after: int) -> list[int]:
    """Fake text_call/structured_call. Compliance fails until the Nth call."""
    calls = {"compliance": 0}
    history: list[int] = []

    def fake_text_call(*, system, user, temperature=None, provider=None):
        return f"draft #{calls['compliance']}"

    def fake_structured_call(*, system, user, schema, temperature=None, provider=None):
        calls["compliance"] += 1
        history.append(calls["compliance"])
        if calls["compliance"] >= compliant_after:
            return {"is_compliant": True, "violations": []}
        return {"is_compliant": False, "violations": [f"violation #{calls['compliance']}"]}

    monkeypatch.setattr(nodes_module, "text_call", fake_text_call)
    monkeypatch.setattr(nodes_module, "structured_call", fake_structured_call)
    return history


def test_graph_persists_after_a_compliant_retry_cycle(monkeypatch) -> None:
    """Non-compliant once, compliant on the second pass — proves the cycle runs."""
    history = _patch_llm(monkeypatch, compliant_after=2)
    graph = build_graph()

    final_state = graph.invoke(_initial_state(), config=_run_config())

    assert len(history) == 2, "compliance gate should run exactly twice"
    assert final_state["compliance_errors"] == []
    assert final_state["retry_count"] == 1


def test_graph_trips_circuit_breaker_and_reaches_manual_intervention(monkeypatch) -> None:
    """Always non-compliant — the graph must stop, not loop forever."""
    history = _patch_llm(monkeypatch, compliant_after=999)
    graph = build_graph()

    final_state = graph.invoke(_initial_state(), config=_run_config())

    # 4 compliance checks: retries 1, 2, 3 cycle back; the 4th (retry_count=4)
    # trips the breaker and routes to manual_intervention instead of a 5th.
    assert len(history) == 4
    assert final_state["retry_count"] == 4
    assert final_state["compliance_errors"] == ["violation #4"]


def test_graph_never_exceeds_max_retries_worth_of_compliance_checks(monkeypatch) -> None:
    """Regression guard: a stubborn draft must not loop past the configured budget."""
    from app.config import settings

    history = _patch_llm(monkeypatch, compliant_after=999)
    graph = build_graph()

    graph.invoke(_initial_state(), config=_run_config())

    assert len(history) == settings.max_compliance_retries + 1
