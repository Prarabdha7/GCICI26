"""Seed LABELED demo data so the review dashboard looks live for a pitch.

    python -m scripts.seed_demo

DEMO-ONLY: refuses to run unless DEMO_MODE=true. Every seeded row is tagged
is_demo=True (content, feedback, leads) so demo output is never mistaken for
real content and never enters real metrics. Safe to re-run: each table is
seeded only if it is currently empty, so this never duplicates rows.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.db.database import init_db, session_scope  # noqa: E402
from app.db.models import ContentQueue, ContentStatus, FeedbackMemory, Lead, LeadStatus  # noqa: E402

log = logging.getLogger("seed_demo")

SAMPLE_MEDIA_URL = "/static/sample.mp4"


def _load_seed_table(name: str) -> list[dict]:
    """Seed rows load machine-local (local/demo_samples.json, gitignored).
    Absent file or empty table = seed nothing for that table, honestly."""
    from app.agents import local_samples

    tables = local_samples.seed_rows()
    rows = tables.get(name, [])
    cleaned = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row = dict(row)
        row.setdefault("is_demo", True)
        cleaned.append(row)
    return cleaned



def _ensure_sample_media() -> None:
    """Generates a real sample reel via the Phase 4 pipeline so /static/sample.mp4
    is an actual playable file, not a broken link, for the SAMPLE_MEDIA_URL
    referenced by the approved rows above."""
    sample_path = settings.generated_dir / "sample.mp4"
    if sample_path.exists():
        log.info("Sample media already exists at %s — skipping generation.", sample_path)
        return
    try:
        from app.media.assembly import assemble_video

        generated = assemble_video(
            script="JA Assure. Coverage that understands your business.",
            language="en", output_dir=settings.generated_dir,
        )
        generated.rename(sample_path)
        log.info("Generated sample media at %s", sample_path)
    except Exception:
        log.warning(
            "Could not generate sample media (edge-tts needs network access) — "
            "%s will 404 until you run this again with network access.",
            SAMPLE_MEDIA_URL,
        )


def _seed_content_queue(db) -> int:
    if db.query(ContentQueue).count() > 0:
        log.info("content_queue already has rows — skipping.")
        return 0
    rows = _load_seed_table("content")
    if not rows:
        log.info("No local content samples (local/demo_samples.json) — seeding nothing.")
        return 0
    for fields in rows:
        db.add(ContentQueue(**fields))
    db.commit()
    log.info("Seeded %d content_queue rows.", len(rows))
    return len(rows)


def _seed_feedback_memory(db) -> int:
    if db.query(FeedbackMemory).count() > 0:
        log.info("feedback_memory already has rows — skipping.")
        return 0
    rows = _load_seed_table("feedback")
    if not rows:
        log.info("No local feedback samples (local/demo_samples.json) — seeding nothing.")
        return 0
    for fields in rows:
        db.add(FeedbackMemory(**fields))
    db.commit()
    log.info("Seeded %d feedback_memory rows.", len(rows))
    return len(rows)


def _seed_leads(db) -> int:
    if db.query(Lead).count() > 0:
        log.info("leads already has rows — skipping.")
        return 0
    rows = _load_seed_table("leads")
    if not rows:
        log.info("No local lead samples (local/demo_samples.json) — seeding nothing.")
        return 0
    for fields in rows:
        db.add(Lead(**fields))
    db.commit()
    log.info("Seeded %d leads rows.", len(rows))
    return len(rows)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    if not settings.demo_mode:
        log.error("Refusing: set DEMO_MODE=true to seed labeled demo rows. Real DBs stay clean.")
        return 2
    init_db()
    _ensure_sample_media()
    with session_scope() as db:
        _seed_content_queue(db)
        _seed_feedback_memory(db)
        _seed_leads(db)
    log.info("Demo data ready. Run `uvicorn app.main:app --reload` and open /dashboard.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
