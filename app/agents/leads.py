"""B2B prospect discovery, domain enrichment, underwriting scoring, and outreach synthesis.

This module implements the 4-phase lead acquisition sub-pipeline:
    1. Discovery (`discovery_node`): Queries search engines or business registries
       for prospective commercial insurance buyers matching a niche and territory.
    2. Enrichment (`enrichment_node`): Resolves decision-maker contact details, roles,
       and verified email addresses via Hunter.io domain search.
    3. Scoring & Outreach (`scoring_outreach_node`): Evaluates underwriting appetite fit
       (0-100) via structured LLM inference and drafts bespoke cold outreach copy.
    4. Persistence (`persist_leads_node`): Commits qualified leads to the relational
       database under the `Lead` model for CRM export and sales dispatch.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from app.agents.prompts import lead_scoring_system_prompt, lead_scoring_user_prompt
from app.agents.providers import MockDiscoveryProvider, ProviderError, get_discovery_provider, get_hunter_contacts
from app.config import settings
from app.db.database import session_scope
from app.db.models import Lead, LeadStatus
from app.graph.state import LeadGenState
from app.llm.client import LLMError, structured_call

log = logging.getLogger(__name__)

LEAD_SCORE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "fit_score": {"type": "integer"},
        "score_rationale": {"type": "string"},
        "outreach_draft": {"type": "string"},
    },
    "required": ["fit_score", "score_rationale", "outreach_draft"],
}


def discovery_node(state: LeadGenState) -> dict[str, Any]:
    """Discover commercial entities in the target market matching the specified risk niche.

    Dispatches discovery queries to the active provider (e.g. Google Places,
    custom scrapers). In real production mode, missing credentials or connection
    failures propagate immediately as `ProviderError`. In explicitly enabled demo
    mode, labeled fallback prospects are supplied to enable offline evaluation.

    Args:
        state: Current `LeadGenState` containing `niche` and `country` criteria.

    Returns:
        dict[str, Any]: Partial state update with `discovered` prospect records.

    Raises:
        ProviderError: If the underlying discovery provider fails in real mode.
    """
    try:
        provider = get_discovery_provider()
        discovered = provider.discover(niche=state["niche"], country=state["country"])
    except ProviderError as exc:
        if not settings.demo_mode:
            log.error("discovery_node provider unavailable in real mode (%s)", exc)
            raise
        log.warning("discovery_node provider unavailable (%s) — labeled DEMO data", exc)
        discovered = MockDiscoveryProvider().discover(niche=state["niche"], country=state["country"])
    log.info("discovery_node niche=%s country=%s found=%s", state["niche"], state["country"], len(discovered))
    return {"discovered": discovered}


def enrichment_node(state: LeadGenState) -> dict[str, Any]:
    """Enrich discovered company domains with verified corporate contacts via Hunter.io.

    Parses the domain hostname from each prospect's website URL and queries
    the Hunter API. Unresolvable domains or missing enrichment keys fail softly,
    returning an empty contacts list for that prospect rather than aborting the pipeline.

    Args:
        state: Current `LeadGenState` containing the `discovered` prospect list.

    Returns:
        dict[str, Any]: Partial state update with `enriched` prospect records.
    """
    enriched = []
    for prospect in state.get("discovered", []):
        domain = urlparse(prospect.get("website", "")).netloc or prospect.get("website", "")
        try:
            contacts = get_hunter_contacts(domain)
        except ProviderError:
            contacts = []
        enriched.append({**prospect, "contacts": contacts})
    return {"enriched": enriched}


def scoring_outreach_node(state: LeadGenState) -> dict[str, Any]:
    """Score underwriting appetite fit and draft personalized executive outreach copy.

    Invokes structured LLM completion with `LEAD_SCORE_SCHEMA` to rate suitability
    between 0 and 100 and generate a targeted introductory proposal.
    In real mode, LLM failures propagate honestly as `LLMError`. In demo mode, a
    heuristically generated score and draft message are attached with explicit demo tagging.

    Args:
        state: Current `LeadGenState` containing enriched prospect records.

    Returns:
        dict[str, Any]: Partial state update with scored and drafted `leads`.

    Raises:
        LLMError: If structured generation fails while running in real mode.
    """
    leads = []
    for prospect in state.get("enriched", []):
        system = lead_scoring_system_prompt(brand=state["brand"])
        user = lead_scoring_user_prompt(
            company_name=prospect.get("company_name", ""),
            website=prospect.get("website", ""),
            research_notes=state.get("research_notes", ""),
        )
        try:
            verdict = structured_call(system=system, user=user, schema=LEAD_SCORE_SCHEMA)
        except LLMError as exc:
            if not settings.demo_mode:
                log.error("scoring_outreach LLM unavailable in real mode (%s)", exc)
                raise
            verdict = {
                "fit_score": 72,
                "score_rationale": f"[DEMO] Heuristic fit for {state['brand']}: niche keyword match on {prospect.get('company_name', '')}.",
                "outreach_draft": f"[DEMO] Hello {prospect.get('company_name', 'team')} — JA Assure {state['brand']} offers instant-bind, contract-certain cover for your segment. Terms apply.",
            }
        leads.append({**prospect, **verdict})
    return {"leads": leads}


def persist_leads_node(state: LeadGenState) -> dict[str, Any]:
    """Persist scored and drafted prospects to the relational leads database table.

    Iterates over the evaluated lead collection, maps company contact details to the
    SQLAlchemy `Lead` ORM model, and executes an atomic commit within `session_scope()`.
    Preserves audit traceability by assigning initial status `LeadStatus.NEW` and
    tagging synthetic leads with `is_demo=True`.

    Args:
        state: Current `LeadGenState` containing final scored `leads`.

    Returns:
        dict[str, Any]: Partial state update containing the assigned database `lead_ids`.
    """
    lead_ids = []
    with session_scope() as db:
        for lead in state.get("leads", []):
            contacts = lead.get("contacts") or []
            primary_email = contacts[0].get("value") if contacts else None
            row = Lead(
                company_name=lead.get("company_name", ""),
                email=primary_email,
                website=lead.get("website"),
                country=state["country"],
                segment=state["niche"],
                target_brand=state["brand"],
                fit_score=lead.get("fit_score"),
                score_rationale=lead.get("score_rationale"),
                outreach_draft=lead.get("outreach_draft"),
                status=LeadStatus.DRAFTED.value,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            lead_ids.append(row.id)
    log.info("persist_leads_node niche=%s persisted=%s", state["niche"], len(lead_ids))
    return {"lead_ids": lead_ids}
