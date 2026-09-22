"""Graph assembly: wires the nodes and the compliance retry cycle together.

    START -> memory -> market_research -> content -> localization -+-> video -> compliance -> route
                                                          |         |                          |  |  |
                                                          +-> image-+                          |  |  |
                                                          ^__________ non-compliant ___________|  |  |
                                                                   (retry_count <= max)          v  v
                                                                                              persist manual
memory_retrieval and market_research_node each run once, before the first
draft — not on retry cycles, which loop straight back to content_node.
Video runs for tiktok, or any platform with content_type=="video". Image
runs for instagram posts (a single on-brand hero shot). Carousel slide
images are a special case: the format pack (and its slide texts) doesn't
exist until persist_node, so those are generated there, per slide, not by
this routed "image" node.
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes import (
    compliance_gate_node,
    content_node,
    image_generation_node,
    localization_node,
    manual_intervention_node,
    market_research_node,
    memory_retrieval_node,
    persist_node,
    video_assembly_node,
)
from app.graph.routing import COMPLIANT, CONTENT, MANUAL_INTERVENTION, route_after_compliance
from app.graph.state import MarketingState

VIDEO_PLATFORMS = {"tiktok"}
IMAGE_PLATFORMS = {"instagram"}


def route_after_localization(state: MarketingState) -> str:
    platform = (state.get("platform") or "").lower()
    raw_ct = state.get("content_type")
    ct = raw_ct.lower() if isinstance(raw_ct, str) else ""
    if ct == "video" or platform in VIDEO_PLATFORMS:
        return "video"
    if platform in IMAGE_PLATFORMS and ct != "carousel":
        return "image"
    return "compliance_gate"


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    graph = StateGraph(MarketingState)

    graph.add_node("memory_retrieval", memory_retrieval_node)
    graph.add_node("market_research", market_research_node)
    graph.add_node("content", content_node)
    graph.add_node("localization", localization_node)
    graph.add_node("video", video_assembly_node)
    graph.add_node("image", image_generation_node)
    graph.add_node("compliance_gate", compliance_gate_node)
    graph.add_node("persist", persist_node)
    graph.add_node("manual_intervention", manual_intervention_node)

    graph.add_edge(START, "memory_retrieval")
    graph.add_edge("memory_retrieval", "market_research")
    graph.add_edge("market_research", "content")
    graph.add_edge("content", "localization")
    graph.add_conditional_edges(
        "localization",
        route_after_localization,
        {"video": "video", "image": "image", "compliance_gate": "compliance_gate"},
    )
    graph.add_edge("video", "compliance_gate")
    graph.add_edge("image", "compliance_gate")
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
