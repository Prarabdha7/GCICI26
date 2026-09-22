"""LangGraph state for the marketing content pipeline.

A single TypedDict threaded through every node. See CLAUDE.md section 4 for
the full topology; this is the core slice Phase 2 operates on.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class MarketingState(TypedDict):
    draft_content: str
    brand: str
    platform: str
    language: str
    topic: NotRequired[str]
    content_type: NotRequired[str]
    market_research: NotRequired[str]
    enable_adversarial: NotRequired[bool]
    audit_transcript: NotRequired[str]
    healed_content: NotRequired[str]
    compliance_errors: list[str]
    retry_count: int
    feedback_guidance: str
    media_path: str | None
    status: str
    content_id: int | None


class LeadGenState(TypedDict):
    """Threaded through the lead-gen graph. research and discovery run in
    parallel and converge on scoring_outreach (app/graph/lead_gen_graph.py)."""

    brand: str
    niche: str
    country: str
    research_notes: str
    discovered: list[dict]
    enriched: list[dict]
    leads: list[dict]
    lead_ids: list[int]
