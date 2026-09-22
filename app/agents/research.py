"""Research agent: competitor intelligence, digested by the LLM."""

from __future__ import annotations

import logging

from app.agents.prompts import research_system_prompt, research_user_prompt
from app.agents.providers import MockSearchProvider, ProviderError, ScrapeGraphClient, get_search_provider
from app.graph.state import LeadGenState
from app.llm.client import LLMError, text_call

log = logging.getLogger(__name__)


def research_node(state: LeadGenState) -> dict:
    """Searches for competitor activity, scrapes the top hits, and asks the
    LLM for a structured digest. Runs in parallel with discovery_node.
    Zero-key safe: falls back to MockSearchProvider + domain digest."""
    try:
        provider = get_search_provider()
    except ProviderError:
        provider = MockSearchProvider()
    try:
        results = provider.search(f"{state['niche']} insurance competitors {state['country']}")
    except ProviderError:
        results = MockSearchProvider().search(f"{state['niche']} {state['country']}")

    excerpts = []
    scraper = ScrapeGraphClient()
    for result in results[:3]:
        url = result.get("url")
        if not url:
            continue
        try:
            excerpts.append(scraper.extract_markdown(url))
        except Exception:
            excerpts.append(result.get("snippet", ""))

    context = "\n\n---\n\n".join(excerpts) or "\n".join(r.get("snippet", "") for r in results)
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
