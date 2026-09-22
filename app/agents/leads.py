"""Lead generation agent: discovery, enrichment, scoring and outreach drafting."""

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


def discovery_node(state: LeadGenState) -> dict:
    """Finds prospects in the target niche/market. Runs in parallel with research_node.
    Real mode: provider failures propagate honestly. Demo mode: labeled mock data."""
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


def enrichment_node(state: LeadGenState) -> dict:
    """Pulls professional contacts for each discovered domain via Hunter.io."""
    enriched = []
    for prospect in state.get("discovered", []):
        domain = urlparse(prospect.get("website", "")).netloc or prospect.get("website", "")
        try:
            contacts = get_hunter_contacts(domain)
        except ProviderError:
            contacts = []
        enriched.append({**prospect, "contacts": contacts})
    return {"enriched": enriched}


def scoring_outreach_node(state: LeadGenState) -> dict:
    """Scores each enriched prospect's fit and drafts a personalised outreach message.
    Real mode: LLM failures propagate honestly. Demo mode: labeled heuristic score."""
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


def persist_leads_node(state: LeadGenState) -> dict:
    """Writes scored, drafted prospects to the leads table."""
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
