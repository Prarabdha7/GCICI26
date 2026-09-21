"""Conditional routing after the compliance gate.

This is the only place retry policy lives (CLAUDE.md section 4).
`retry_count` is incremented exclusively by `compliance_gate_node`.
"""

from __future__ import annotations

from app.config import settings
from app.graph.state import MarketingState

CONTENT = "content"
MANUAL_INTERVENTION = "manual_intervention"
COMPLIANT = "compliant"


def route_after_compliance(state: MarketingState) -> str:
    if not state["compliance_errors"]:
        return COMPLIANT
    if state["retry_count"] > settings.max_compliance_retries:
        return MANUAL_INTERVENTION  # circuit breaker
    return CONTENT  # cycle back and rewrite
