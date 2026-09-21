"""Lead-gen graph assembly: research and discovery run in parallel, converge
on scoring/outreach, then persist to the leads table.

    START -> research    -> \\
                              scoring_outreach -> persist_leads -> END
    START -> discovery -> enrichment -> /
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.leads import discovery_node, enrichment_node, persist_leads_node, scoring_outreach_node
from app.agents.research import research_node
from app.graph.state import LeadGenState


def build_lead_gen_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    graph = StateGraph(LeadGenState)

    graph.add_node("research", research_node)
    graph.add_node("discovery", discovery_node)
    graph.add_node("enrichment", enrichment_node)
    graph.add_node("scoring_outreach", scoring_outreach_node)
    graph.add_node("persist_leads", persist_leads_node)

    graph.add_edge(START, "research")
    graph.add_edge(START, "discovery")
    graph.add_edge("discovery", "enrichment")
    graph.add_edge("research", "scoring_outreach")
    graph.add_edge("enrichment", "scoring_outreach")
    graph.add_edge("scoring_outreach", "persist_leads")
    graph.add_edge("persist_leads", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())
