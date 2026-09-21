"""Graph assembly: wires the nodes and the compliance retry cycle together.

    START -> content -> localization -> compliance_gate -> route_after_compliance
                              ^                                  |         |
                              |__________ non-compliant __________|         |
                                       (retry_count <= max)                |
                                                                            v
                                                          manual_intervention -> END
                                                     (retry_count > max, circuit breaker)

Compliant drafts route straight to END; persisting the row to `content_queue`
is Phase 3's `persist_node`, added once the memory engine lands.
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes import (
    compliance_gate_node,
    content_node,
    localization_node,
    manual_intervention_node,
)
from app.graph.routing import COMPLIANT, CONTENT, MANUAL_INTERVENTION, route_after_compliance
from app.graph.state import MarketingState


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    graph = StateGraph(MarketingState)

    graph.add_node("content", content_node)
    graph.add_node("localization", localization_node)
    graph.add_node("compliance_gate", compliance_gate_node)
    graph.add_node("manual_intervention", manual_intervention_node)

    graph.add_edge(START, "content")
    graph.add_edge("content", "localization")
    graph.add_edge("localization", "compliance_gate")
    graph.add_conditional_edges(
        "compliance_gate",
        route_after_compliance,
        {
            COMPLIANT: END,
            CONTENT: "content",
            MANUAL_INTERVENTION: "manual_intervention",
        },
    )
    graph.add_edge("manual_intervention", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())
