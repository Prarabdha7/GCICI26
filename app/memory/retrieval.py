"""Closed-loop feedback retrieval — runs before every generation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import FeedbackMemory


def get_recent_feedback(
    db: Session, *, brand: str, platform: str, limit: int | None = None
) -> list[FeedbackMemory]:
    """Most recent feedback_memory rows for a brand/platform pair, newest first."""
    stmt = (
        select(FeedbackMemory)
        .where(FeedbackMemory.brand == brand, FeedbackMemory.platform == platform)
        .order_by(FeedbackMemory.timestamp.desc())
        .limit(limit or settings.feedback_memory_limit)
    )
    return list(db.execute(stmt).scalars())


def format_guidance(entries: list[FeedbackMemory]) -> str:
    """Exact injection contract (CLAUDE.md section 5). Empty when there is no
    feedback yet — never inject a placeholder block."""
    if not entries:
        return ""
    notes = "; ".join(f"{entry.error_tag}: {entry.human_note}" for entry in entries)
    return (
        "CRITICAL GUIDANCE: Previously, human reviewers rejected content for "
        f"this brand due to: {notes}. You MUST NOT repeat these mistakes."
    )


def get_recent_engagement(db: Session, *, limit: int = 20) -> list:
    """Latest REAL engagement events (demo/mock rows excluded — fabricated
    metrics must never steer generation). Newest first."""
    from app.db.models import PublishEvent

    stmt = (
        select(PublishEvent)
        .where(PublishEvent.event == "engagement", PublishEvent.provider != "mock-demo")
        .order_by(PublishEvent.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


def format_engagement_guidance(entries: list, *, brand: str, platform: str) -> str:
    """Honest performance signal for the content agent. Empty when nothing
    real has been measured yet — never invent performance claims."""
    relevant = []
    for entry in entries:
        payload = entry.payload or {}
        if not isinstance(payload, dict) or payload.get("demo"):
            continue
        relevant.append(entry)
        if len(relevant) >= 5:
            break
    if not relevant:
        return ""
    parts = []
    for entry in relevant:
        payload = entry.payload or {}
        impressions = payload.get("impressions", "?")
        ctr = payload.get("ctr", "?")
        parts.append(f"content_id={entry.content_id} provider={entry.provider} impressions={impressions} ctr={ctr}")
    return (
        "MEASURED PERFORMANCE (real published posts, learn what resonated; "
        "do not invent similar numbers): " + "; ".join(parts)
    )
