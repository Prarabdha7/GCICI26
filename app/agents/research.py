"""Research agent: competitor intelligence, digested by the LLM."""

from __future__ import annotations

import asyncio
import logging

from app.agents.prompts import research_system_prompt, research_user_prompt
from app.agents.providers import MockSearchProvider
from app.graph.state import LeadGenState
from app.llm.client import LLMError, text_call
from app.utils.research import research_summary

log = logging.getLogger(__name__)


def research_node(state: LeadGenState) -> dict:
    """Searches DuckDuckGo and scrapes the top hits with Crawl4AI for live
    competitor/market context, then asks the LLM for a structured digest.
    Runs in parallel with discovery_node. Zero-key safe: falls back to a
    deterministic mock digest if the live search returns nothing."""
    query = f"{state['niche']} insurance competitors {state['country']}"
    context = asyncio.run(research_summary(query))
    if not context:
        log.warning("research_node: no live results for %r — using mock digest", query)
        context = "\n".join(r.get("snippet", "") for r in MockSearchProvider().search(query))

    system = research_system_prompt(brand=state["brand"])
    user = research_user_prompt(niche=state["niche"], country=state["country"], context=context)
    try:
        digest = text_call(system=system, user=user)
    except LLMError:
        digest = (
            f"Market digest for {state['brand']} ({state['niche']} / {state['country']}): "
            f"{context[:600]} Recommended angle: position JA Assure as the instant-bind, "
            f"contract-certain alternative. Terms apply."
        )

    log.info("research_node brand=%s niche=%s country=%s", state["brand"], state["niche"], state["country"])
    return {"research_notes": digest}
