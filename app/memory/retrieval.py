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
