"""Graph assembly: wires the nodes and the compliance retry cycle together.

    START -> memory_retrieval -> content -> localization -> compliance_gate -> route_after_compliance
                                      ^                                              |    |         |
                                      |______________ non-compliant _________________|    |         |
                                               (retry_count <= max)                        |         |
                                                                                            v         v
                                                                                        persist   manual_intervention
                                                                                          |               |
                                                                                          v               v
                                                                                         END             END
                                                                          (retry_count > max, circuit breaker)

memory_retrieval runs once, before the first draft — not on retry cycles, which
loop straight back to content_node (CLAUDE.md section 4).
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
    memory_retrieval_node,
    persist_node,
)
from app.graph.routing import COMPLIANT, CONTENT, MANUAL_INTERVENTION, route_after_compliance
from app.graph.state import MarketingState


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    graph = StateGraph(MarketingState)

    graph.add_node("memory_retrieval", memory_retrieval_node)
    graph.add_node("content", content_node)
    graph.add_node("localization", localization_node)
    graph.add_node("compliance_gate", compliance_gate_node)
    graph.add_node("persist", persist_node)
    graph.add_node("manual_intervention", manual_intervention_node)

    graph.add_edge(START, "memory_retrieval")
    graph.add_edge("memory_retrieval", "content")
    graph.add_edge("content", "localization")
    graph.add_edge("localization", "compliance_gate")
    graph.add_conditional_edges(
        "compliance_gate",
        route_after_compliance,
        {
            COMPLIANT: "persist",
            CONTENT: "content",
            MANUAL_INTERVENTION: "manual_intervention",
        },
    )
    graph.add_edge("persist", END)
    graph.add_edge("manual_intervention", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())
