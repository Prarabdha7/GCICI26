"""Seed realistic demo data so the review dashboard looks live for a pitch.

    python -m scripts.seed_demo

Safe to re-run: each table is seeded only if it is currently empty, so this
never duplicates rows into a database that already has real content.
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

# -- approved: localized posts across SG / MY / TH, ready for the auto-publisher --
APPROVED_ROWS = [
    dict(
        brand="Jade", platform="instagram", language="en", content_type="post",
        status=ContentStatus.APPROVED.value, media_path=SAMPLE_MEDIA_URL,
        draft_content=(
            "Discretion is not a discount. Jade covers what your collection is "
            "actually worth — appraised value, not a guess. Terms, conditions, "
            "and exclusions apply."
        ),
    ),
    dict(
        brand="Jaguar Transit", platform="linkedin", language="ms", content_type="post",
        status=ContentStatus.APPROVED.value, media_path=SAMPLE_MEDIA_URL,
        draft_content=(
            "Satu kelewatan serah boleh menelan kos lebih daripada nilai barang "
            "itu sendiri. Jaguar Transit melindungi kargo bernilai tinggi dari "
            "pintu ke pintu. Tertakluk kepada terma polisi rasmi dan kelulusan "
            "penajaminan."
        ),
    ),
    dict(
        brand="DoctorShield", platform="linkedin", language="th", content_type="post",
        status=ContentStatus.APPROVED.value, media_path=SAMPLE_MEDIA_URL,
        draft_content=(
            "การตัดสินใจทางคลินิกเป็นของคุณ ความเสี่ยงทางการเงินจากการเรียกร้องค่าสินไหม "
            "ไม่จำเป็นต้องเป็นของคุณ DoctorShield — ความคุ้มครองสำหรับแพทย์ผู้ปฏิบัติงาน "
            "ข้อมูลนี้เป็นข้อมูลทั่วไปเท่านั้น ไม่ถือเป็นคำแนะนำทางการเงิน"
        ),
    ),
]

# -- manual_intervention: circuit-breaker casualties for that dashboard tab --
MANUAL_INTERVENTION_ROWS = [
    dict(
        brand="Jaguar Transit", platform="tiktok", language="en", content_type="post",
        status=ContentStatus.MANUAL_INTERVENTION.value, retry_count=4,
        draft_content=(
            "Nothing you ship will ever go missing with Jaguar Transit — 100% "
            "guaranteed, always approved."
        ),
        compliance_errors=[
            "Uses '100% guaranteed' and 'always approved', both banned words (Rubric 4).",
            "Implies zero loss is possible, violating the Jaguar Transit brand "
            "constraint against guaranteeing zero loss (Rubric 2).",
        ],
    ),
    dict(
        brand="DoctorShield", platform="instagram", language="th", content_type="post",
        status=ContentStatus.MANUAL_INTERVENTION.value, retry_count=5,
        draft_content=(
            "แพทย์ทุกคนที่ถือ DoctorShield จะไม่มีวันถูกฟ้องร้องเรื่องการรักษาที่ผิดพลาดอีกต่อไป"
        ),
        compliance_errors=[
            "Promises immunity from malpractice lawsuits, violating the "
            "DoctorShield brand constraint (Rubric 2).",
            "No mandatory disclaimer present (Rubric 3).",
        ],
    ),
]

CONTENT_QUEUE_ROWS = APPROVED_ROWS + MANUAL_INTERVENTION_ROWS

# -- feedback history: aligned to the approved rows' brand/platform above, so
# get_recent_feedback() has something to surface for exactly what's on screen --
FEEDBACK_MEMORY_ROWS = [
    dict(
        brand="Jade", platform="instagram", error_tag="too_salesy",
        human_note="Read like a discount ad — Jade never discounts. Reframe "
        "around craftsmanship and discretion, not price.",
    ),
    dict(
        brand="Jaguar Transit", platform="linkedin", error_tag="wrong_cta",
        human_note="CTA said 'Buy now' — B2B logistics buyers don't respond to "
        "that register. Use 'Request a risk assessment' instead.",
    ),
]

LEAD_ROWS = [
    dict(
        company_name="Marina Bay Fine Jewellers", contact_name="Priya Nair",
        email="priya@marinabayjewellers.sg", website="https://marinabayjewellers.sg",
        country="Singapore", segment="jeweller", target_brand="Jade",
        fit_score=88,
        score_rationale="High-value retail jeweller in the CBD with no visible "
        "block cover mentioned publicly; prior press coverage of a nearby break-in.",
        outreach_draft="Hi Priya — after the recent spate of CBD jewellery store "
        "incidents, wanted to check whether your current cover reflects your "
        "showcase value today. Happy to send a same-day quote.",
        status=LeadStatus.DRAFTED.value,
    ),
    dict(
        company_name="KL Express Logistics", contact_name="Aiman Rahman",
        email="aiman@klexpress.my", website="https://klexpress.my",
        country="Malaysia", segment="courier", target_brand="Jaguar Transit",
        fit_score=76,
        score_rationale="Mid-size courier fleet expanding into cross-border "
        "high-value freight; no transit insurer named on their site.",
        outreach_draft="Hi Aiman — congrats on the KL-Singapore lane expansion. "
        "Cross-border high-value freight usually needs different cover than "
        "domestic parcels. Worth a 15-minute call?",
        status=LeadStatus.DRAFTED.value,
    ),
    dict(
        company_name="Dr. Tan Family Clinic", contact_name="Dr. Michelle Tan",
        email="clinic@drtanfamily.sg", website="https://drtanfamily.sg",
        country="Singapore", segment="clinic", target_brand="DoctorShield",
        fit_score=82,
        score_rationale="Solo GP practice, no indemnity provider named publicly; "
        "renewal season for most SG clinics is Q1.",
        outreach_draft="Hi Dr. Tan — with renewal season coming up, happy to "
        "benchmark your current indemnity terms against DoctorShield's "
        "clinician-first policy at no obligation.",
        status=LeadStatus.DRAFTED.value,
    ),
]


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
    for fields in CONTENT_QUEUE_ROWS:
        db.add(ContentQueue(**fields))
    db.commit()
    log.info("Seeded %d content_queue rows.", len(CONTENT_QUEUE_ROWS))
    return len(CONTENT_QUEUE_ROWS)


def _seed_feedback_memory(db) -> int:
    if db.query(FeedbackMemory).count() > 0:
        log.info("feedback_memory already has rows — skipping.")
        return 0
    for fields in FEEDBACK_MEMORY_ROWS:
        db.add(FeedbackMemory(**fields))
    db.commit()
    log.info("Seeded %d feedback_memory rows.", len(FEEDBACK_MEMORY_ROWS))
    return len(FEEDBACK_MEMORY_ROWS)


def _seed_leads(db) -> int:
    if db.query(Lead).count() > 0:
        log.info("leads already has rows — skipping.")
        return 0
    for fields in LEAD_ROWS:
        db.add(Lead(**fields))
    db.commit()
    log.info("Seeded %d leads rows.", len(LEAD_ROWS))
    return len(LEAD_ROWS)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
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
