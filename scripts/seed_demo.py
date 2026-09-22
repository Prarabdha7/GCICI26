"""Seed LABELED demo rows for walkthroughs only.

    python -m scripts.seed_demo

Refuses to run unless DEMO_MODE=true. Every row is tagged is_demo=True and
prefixed [DEMO] so demo output is never mistaken for real content. Seeds
only pending / manual_intervention / rejected states — never approved, so
nothing auto-publishes unexpectedly. Safe to re-run (skips when demo rows
already exist).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.db.database import init_db, session_scope  # noqa: E402
from app.db.models import ContentQueue, ContentStatus, FeedbackMemory  # noqa: E402
from app.memory.store import create_feedback_entry  # noqa: E402

log = logging.getLogger("seed_demo")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    if not settings.demo_mode:
        log.error("Refusing: set DEMO_MODE=true to seed labeled demo rows. Real DBs stay clean.")
        return 2
    init_db()
    with session_scope() as db:
        from sqlalchemy import select

        existing = db.scalar(select(ContentQueue.id).where(ContentQueue.is_demo.is_(True)).limit(1))
        if existing is not None:
            log.info("Demo rows already present — nothing to do.")
            return 0
        pending = ContentQueue(
            brand="Jade", platform="linkedin", language="en", content_type="post",
            topic="SIJE memo cover (demo)", status=ContentStatus.PENDING.value,
            draft_content="[DEMO] Jade Jewellers Block covers stock, memo goods and exhibition transit. Terms apply.",
            compliance_errors=[], retry_count=0, is_demo=True,
        )
        stuck = ContentQueue(
            brand="Jaguar Transit", platform="tiktok", language="en", content_type="post",
            topic="absolute guarantee (demo)", status=ContentStatus.MANUAL_INTERVENTION.value,
            draft_content="[DEMO] Nothing you ship will ever go missing — 100% guaranteed.",
            compliance_errors=["[local-check] Uses banned phrase 'guaranteed'"],
            retry_count=4, is_demo=True,
        )
        rejected = ContentQueue(
            brand="DoctorShield", platform="instagram", language="en", content_type="post",
            topic="tone (demo)", status=ContentStatus.REJECTED.value,
            draft_content="[DEMO] Cheap cover for every clinic!",
            feedback_reason="Too salesy for clinicians.",
            compliance_errors=[], retry_count=0, is_demo=True,
        )
        db.add_all([pending, stuck, rejected])
        db.commit()
        db.refresh(rejected)
        create_feedback_entry(
            db, brand="DoctorShield", platform="instagram",
            error_tag="too_salesy", human_note="[DEMO] Too salesy for clinicians.",
            content_id=rejected.id,
        )
    log.info("Seeded 3 labeled DEMO rows (pending / manual_intervention / rejected).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
