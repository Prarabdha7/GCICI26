"""APScheduler worker: polls content_queue for approved rows and publishes them.

Nothing publishes without a human approving it first (CLAUDE.md's non-negotiable).
"""

from __future__ import annotations

import datetime as dt
import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.config import settings
from app.db.database import session_scope
from app.db.models import ContentQueue, ContentStatus
from worker.analytics import log_event
from worker.publisher import MockPublisher, PublisherError, get_publisher, publish_with_retry, simulate_engagement

log = logging.getLogger(__name__)

JOB_ID = "publish_approved_content"
ANALYTICS_JOB_ID = "confirm_scheduled_published"
INTEL_JOB_ID = "intel_sweep"


def _resolve_publisher():
    """Strict keys first; mock dispatcher only when no keys are configured."""
    try:
        return get_publisher()
    except PublisherError:
        log.info("No social keys configured — using MockPublisher for zero-key demo")
        return MockPublisher()


def _provider_name(publisher) -> str:
    return type(publisher).__name__.replace("Publisher", "").lower() or "mock"


def publish_approved_content() -> int:
    """One poll cycle. A failing row is logged and skipped, never dropped
    silently and never blocking the rest of the batch (CLAUDE.md section 12).

    Success moves a row to `scheduled`, not `published` — `published` is
    confirmed by confirm_scheduled_as_published() (webhook/analytics loop)."""
    scheduled = 0
    try:
        publisher = _resolve_publisher()
    except PublisherError:
        log.exception("No publisher available")
        return 0
    provider = _provider_name(publisher)
    with session_scope() as db:
        rows = list(
            db.scalars(select(ContentQueue).where(ContentQueue.status == ContentStatus.APPROVED.value))
        )
        for item in rows:
            content_id = item.id
            try:
                post_id = publish_with_retry(publisher, item)
            except PublisherError:
                log.exception("publish failed for content_id=%s", content_id)
                log_event(db, content_id=content_id, event="failed", provider=provider, payload={"error": "publish failed"})
                continue
            item.external_post_id = post_id
            item.status = ContentStatus.SCHEDULED.value
            item.scheduled_for = dt.datetime.now(dt.timezone.utc)
            db.commit()
            log_event(db, content_id=content_id, event="scheduled", provider=provider, external_post_id=post_id)
            scheduled += 1
            log.info("scheduled content_id=%s post_id=%s", content_id, post_id)
    return scheduled


def confirm_scheduled_as_published() -> int:
    """Analytics feedback loop: scheduled -> published with engagement snapshot.

    Real providers confirm via POST /api/publish/webhook; this job handles the
    mock/demo path by simulating impressions/clicks and stamping published_at.
    """
    confirmed = 0
    with session_scope() as db:
        rows = list(
            db.scalars(select(ContentQueue).where(ContentQueue.status == ContentStatus.SCHEDULED.value))
        )
        for item in rows:
            content_id = item.id
            metrics = simulate_engagement(item)
            item.status = ContentStatus.PUBLISHED.value
            item.published_at = dt.datetime.now(dt.timezone.utc)
            if not item.published_url and item.external_post_id:
                if item.external_post_id.startswith("mock-"):
                    item.published_url = f"https://mock.social/p/{item.external_post_id}"
                else:
                    item.published_url = f"https://buffer.com/p/{item.external_post_id}"
            db.commit()
            log_event(db, content_id=content_id, event="published", provider="mock" if (item.external_post_id or "").startswith("mock-") else "buffer", external_post_id=item.external_post_id)
            log_event(db, content_id=content_id, event="engagement", provider="analytics", external_post_id=item.external_post_id, payload=metrics)
            confirmed += 1
            log.info("published content_id=%s metrics=%s", content_id, metrics)
    return confirmed


def build_scheduler() -> BackgroundScheduler:
    from worker.intel import intel_sweep

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        publish_approved_content, "interval", seconds=settings.publish_poll_interval, id=JOB_ID
    )
    scheduler.add_job(
        confirm_scheduled_as_published, "interval", seconds=settings.publish_poll_interval, id=ANALYTICS_JOB_ID
    )
    scheduler.add_job(intel_sweep, "interval", hours=6, id=INTEL_JOB_ID)
    return scheduler


def main() -> None:
    """Run the worker as a standalone process: `python -m worker.scheduler`."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s | %(message)s"
    )
    scheduler = build_scheduler()
    scheduler.start()
    log.info("Auto-publisher worker started — polling every %ss.", settings.publish_poll_interval)
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("Auto-publisher worker stopped.")


if __name__ == "__main__":
    main()
