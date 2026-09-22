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
    topic: str | None = None,
    content_type: str = "post",
    variant_label: str | None = None,
    healed_content: str | None = None,
    audit_transcript: str | None = None,
    formats_json: str | None = None,
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
        topic=topic,
        content_type=content_type,
        variant_label=variant_label,
        healed_content=healed_content,
        audit_transcript=audit_transcript,
        formats_json=formats_json,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
