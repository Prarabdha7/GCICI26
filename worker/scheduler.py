"""APScheduler worker: polls content_queue for approved rows and publishes them.

Nothing publishes without a human approving it first (CLAUDE.md's non-negotiable).
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.config import settings
from app.db.database import session_scope
from app.db.models import ContentQueue, ContentStatus
from worker.publisher import PublisherError, get_publisher

log = logging.getLogger(__name__)

JOB_ID = "publish_approved_content"


def publish_approved_content() -> int:
    """One poll cycle. A failing row is logged and skipped, never dropped
    silently and never blocking the rest of the batch (CLAUDE.md section 12).

    Success moves a row to `scheduled`, not `published` — `published` is
    reserved for a future webhook confirmation that the post actually went live."""
    scheduled = 0
    with session_scope() as db:
        rows = list(
            db.scalars(select(ContentQueue).where(ContentQueue.status == ContentStatus.APPROVED.value))
        )
        for item in rows:
            try:
                post_id = get_publisher().publish(item)
            except PublisherError:
                log.exception("publish failed for content_id=%s", item.id)
                continue
            item.external_post_id = post_id
            item.status = ContentStatus.SCHEDULED.value
            db.commit()
            scheduled += 1
            log.info("scheduled content_id=%s post_id=%s", item.id, post_id)
    return scheduled


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        publish_approved_content, "interval", seconds=settings.publish_poll_interval, id=JOB_ID
    )
    return scheduler
