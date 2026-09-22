"""Conditional Edge Routing and Circuit Breaker Policies.

This module defines state-based conditional routing rules for the LangGraph state
machine following compliance verification. It encapsulates retry thresholds and
prevents infinite self-healing loops through an automated circuit breaker.

Routing Outlets:
    - COMPLIANT: Draft passes all statutory criteria and proceeds to media assembly.
    - CONTENT: Draft failed validation but has remaining retry attempts; cycles
      back to content generation with injected violation critique.
    - MANUAL_INTERVENTION: Draft exceeded maximum compliance retry limits; routes
      directly to human intervention queue.
"""

from __future__ import annotations

from app.config import settings
from app.graph.state import MarketingState

CONTENT = "content"
MANUAL_INTERVENTION = "manual_intervention"
COMPLIANT = "compliant"


def route_after_compliance(state: MarketingState) -> str:
    """Determine the next workflow node destination based on compliance evaluation results.

    Args:
        state: Active LangGraph state containing compliance errors and retry counter.

    Returns:
        str: Next node identifier ('compliant', 'content', or 'manual_intervention').
    """
    if not state["compliance_errors"]:
        return COMPLIANT
    if state["retry_count"] > settings.max_compliance_retries:
        return MANUAL_INTERVENTION
    return CONTENT
