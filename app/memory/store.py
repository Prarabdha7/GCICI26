"""Writes a feedback_memory row on every human reject or edit."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import FeedbackMemory


def create_feedback_entry(
    db: Session,
    *,
    brand: str,
    platform: str,
    error_tag: str,
    human_note: str,
    content_id: int | None = None,
) -> FeedbackMemory:
    row = FeedbackMemory(
        brand=brand,
        platform=platform,
        error_tag=error_tag,
        human_note=human_note,
        content_id=content_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
