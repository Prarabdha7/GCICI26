"""Writes compliant drafts to `content_queue`."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import ContentQueue, ContentStatus


def create_content_queue_row(
    db: Session,
    *,
    brand: str,
    platform: str,
    language: str,
    draft_content: str,
    media_path: str | None = None,
    compliance_errors: list[str] | None = None,
    retry_count: int = 0,
) -> ContentQueue:
    row = ContentQueue(
        brand=brand,
        platform=platform,
        language=language,
        draft_content=draft_content,
        media_path=media_path,
        status=ContentStatus.PENDING.value,
        compliance_errors=compliance_errors or [],
        retry_count=retry_count,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
