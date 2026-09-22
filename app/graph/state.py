"""Workflow State Schemas and Type Definitions.

This module defines strongly-typed state containers (`TypedDict`) exchanged across
nodes in the LangGraph execution runtime. It establishes explicit contracts for
creative drafting, compliance validation, and multi-channel lead generation pipelines.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class MarketingState(TypedDict):
    """Execution state container for the autonomous marketing pipeline.

    Attributes:
        draft_content: Working marketing copy text.
        brand: Target insurance brand persona ('Jade', 'Jaguar Transit', 'DoctorShield').
        platform: Target publishing channel ('linkedin', 'instagram', 'tiktok').
        language: Regional language code ('en', 'ms', 'zh', 'th', 'id').
        topic: Campaign theme or user-supplied creative concept.
        content_type: Form factor ('post', 'carousel', or 'reel').
        market_research: Live competitor context gathered from web scrapers.
        enable_adversarial: Toggles 3-agent adversarial debate on compliance failure.
        audit_transcript: Adversarial debate transcript.
        healed_content: Statutorily corrected version of draft copy.
        is_demo: Indicates synthetic or simulated operational status.
        compliance_errors: Specific regulatory clauses violated.
        retry_count: Number of automated self-healing iterations executed.
        feedback_guidance: Historical human critiques injected from memory.
        media_path: Relative filesystem path to generated video reels.
        image_paths: List of relative filesystem paths to generated images.
        status: Content queue processing status.
        content_id: Primary key of persisted database record.
    """

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
    is_demo: NotRequired[bool]
    compliance_errors: list[str]
    retry_count: int
    feedback_guidance: str
    media_path: str | None
    image_paths: NotRequired[list[str]]
    status: str
    content_id: int | None


class LeadGenState(TypedDict):
    """Execution state container for the autonomous B2B lead generation workflow.

    Attributes:
        brand: Target insurance brand persona.
        niche: Commercial business vertical.
        country: Target geographical jurisdiction.
        research_notes: Web intelligence synthesized from business directories.
        discovered: Raw prospect accounts parsed from scraping.
        enriched: Prospect records enriched with contact information.
        leads: Fully qualified lead entries scored for underwriting fit.
        lead_ids: Primary keys of persisted Lead database rows.
    """

    brand: str
    niche: str
    country: str
    research_notes: str
    discovered: list[dict]
    enriched: list[dict]
    leads: list[dict]
    lead_ids: list[int]
