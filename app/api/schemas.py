"""Pydantic contracts for the REST API."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class ContentQueueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    brand: str
    platform: str
    language: str
    content_type: str
    topic: str | None = None
    variant_label: str | None = None
    draft_content: str
    final_content: str | None = None
    media_path: str | None = None
    healed_content: str | None = None
    audit_transcript: str | None = None
    formats_json: str | None = None
    status: str
    compliance_errors: list[str] = Field(default_factory=list)
    retry_count: int
    feedback_reason: str | None = None
    external_post_id: str | None = None
    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None


class FeedbackMemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    brand: str
    platform: str
    error_tag: str
    human_note: str
    timestamp: dt.datetime | None = None
    content_id: int | None = None


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_name: str
    contact_name: str | None = None
    email: str | None = None
    website: str | None = None
    country: str | None = None
    segment: str | None = None
    target_brand: str | None = None
    fit_score: int | None = None
    score_rationale: str | None = None
    status: str


class QueueStats(BaseModel):
    """Headline numbers for the review dashboard and the live demo."""

    total: int
    by_status: dict[str, int]
    feedback_entries: int
    leads: int
    rejection_rate: float = Field(description="rejected / (rejected + approved), 0.0 when no decisions yet")
