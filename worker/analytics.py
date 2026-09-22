"""Project 2 analytics: engagement logging backed by publish_events table."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.models import PublishEvent

log = logging.getLogger(__name__)


def log_event(
    db: Session,
    *,
    content_id: int | None,
    event: str,
    provider: str = "mock",
    external_post_id: str | None = None,
    payload: dict | None = None,
) -> PublishEvent:
    row = PublishEvent(
        content_id=content_id,
        event=event,
        provider=provider,
        external_post_id=external_post_id,
        payload=payload or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def latest_engagement(db: Session, content_id: int) -> dict:
    from sqlalchemy import select

    row = db.execute(
        select(PublishEvent)
        .where(PublishEvent.content_id == content_id, PublishEvent.event == "engagement")
        .order_by(PublishEvent.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return dict(row.payload or {}) if row else {}
