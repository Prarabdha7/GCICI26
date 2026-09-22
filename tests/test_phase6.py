"""Phase 6 tests: the review dashboard and closed-loop memory storage.

    pytest tests/test_phase6.py -v
"""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.db.database import session_scope
from app.db.models import ContentQueue, ContentStatus, FeedbackMemory
from app.main import app
from app.memory.store import create_feedback_entry


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _seed_queue_row(db: Session, **overrides) -> ContentQueue:
    fields = {
        "brand": "Jade", "platform": "linkedin", "language": "en",
        "draft_content": "draft copy", "status": ContentStatus.PENDING.value,
    }
    fields.update(overrides)
    row = ContentQueue(**fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# --------------------------------------------------------------------------- #
# app/memory/store.py
# --------------------------------------------------------------------------- #


def test_create_feedback_entry_writes_a_row() -> None:
    with session_scope() as db:
        entry = create_feedback_entry(
            db, brand="Jade", platform="linkedin", error_tag="too_salesy",
            human_note="Reads like a pitch.", content_id=None,
        )
        assert entry.id is not None

    with session_scope() as db:
        row = db.get(FeedbackMemory, entry.id)
        assert row.brand == "Jade"
        assert row.error_tag == "too_salesy"
        assert row.human_note == "Reads like a pitch."


def test_create_feedback_entry_links_content_id() -> None:
    with session_scope() as db:
        queue_row = _seed_queue_row(db)
        entry = create_feedback_entry(
            db, brand=queue_row.brand, platform=queue_row.platform,
            error_tag="wrong_cta", human_note="CTA mismatched.", content_id=queue_row.id,
        )
        assert entry.content_id == queue_row.id


# --------------------------------------------------------------------------- #
# dashboard routes — GET
# --------------------------------------------------------------------------- #


def test_dashboard_home_lists_pending_items(client) -> None:
    with session_scope() as db:
        _seed_queue_row(db, draft_content="unique-pending-marker-1")

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "unique-pending-marker-1" in response.text


def test_dashboard_home_excludes_non_pending_items(client) -> None:
    with session_scope() as db:
        _seed_queue_row(db, draft_content="unique-approved-marker", status=ContentStatus.APPROVED.value)

    response = client.get("/dashboard")

    assert "unique-approved-marker" not in response.text


def test_manual_intervention_view_lists_only_breaker_trips(client) -> None:
    with session_scope() as db:
        _seed_queue_row(db, draft_content="unique-manual-marker", status=ContentStatus.MANUAL_INTERVENTION.value, retry_count=4)
        _seed_queue_row(db, draft_content="unique-pending-marker-2", status=ContentStatus.PENDING.value)

    response = client.get("/dashboard/manual-intervention")

    assert response.status_code == 200
    assert "unique-manual-marker" in response.text
    assert "unique-pending-marker-2" not in response.text


def test_metrics_view_renders(client) -> None:
    response = client.get("/dashboard/metrics")
    assert response.status_code == 200
    assert "Rejection rate" in response.text


def test_queue_detail_renders_existing_item(client) -> None:
    with session_scope() as db:
        row = _seed_queue_row(db, draft_content="unique-detail-marker")
        content_id = row.id

    response = client.get(f"/dashboard/queue/{content_id}")

    assert response.status_code == 200
    assert "unique-detail-marker" in response.text


def test_queue_detail_404_for_missing_item(client) -> None:
    response = client.get("/dashboard/queue/999999999")
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# dashboard routes — actions
# --------------------------------------------------------------------------- #


def test_approve_updates_status(client) -> None:
    with session_scope() as db:
        row = _seed_queue_row(db)
        content_id = row.id

    response = client.post(f"/dashboard/queue/{content_id}/approve")

    assert response.status_code == 200
    with session_scope() as db:
        assert db.get(ContentQueue, content_id).status == ContentStatus.APPROVED.value


def test_approve_from_list_context_returns_empty_body_for_htmx_swap(client) -> None:
    with session_scope() as db:
        row = _seed_queue_row(db)
        content_id = row.id

    response = client.post(f"/dashboard/queue/{content_id}/approve")

    assert response.text == ""
    assert "hx-redirect" not in {k.lower() for k in response.headers}


def test_approve_from_detail_context_sends_hx_redirect(client) -> None:
    with session_scope() as db:
        row = _seed_queue_row(db)
        content_id = row.id

    response = client.post(
        f"/dashboard/queue/{content_id}/approve", headers={"HX-Target": "detail-actions"}
    )

    assert response.headers.get("HX-Redirect") == "/dashboard"


def test_reject_updates_status_and_writes_feedback(client) -> None:
    with session_scope() as db:
        row = _seed_queue_row(db, brand="DoctorShield", platform="instagram")
        content_id = row.id

    response = client.post(
        f"/dashboard/queue/{content_id}/reject",
        data={"error_tag": "off_brand_tone", "human_note": "Too casual for clinicians."},
    )

    assert response.status_code == 200
    with session_scope() as db:
        item = db.get(ContentQueue, content_id)
        assert item.status == ContentStatus.REJECTED.value
        assert item.feedback_reason == "Too casual for clinicians."

        feedback = db.query(FeedbackMemory).filter_by(content_id=content_id).one()
        assert feedback.brand == "DoctorShield"
        assert feedback.platform == "instagram"
        assert feedback.error_tag == "off_brand_tone"
        assert feedback.human_note == "Too casual for clinicians."


def test_reject_requires_error_tag_and_human_note(client) -> None:
    with session_scope() as db:
        row = _seed_queue_row(db)
        content_id = row.id

    response = client.post(f"/dashboard/queue/{content_id}/reject", data={})

    assert response.status_code == 422


def test_edit_saves_final_content_approves_and_writes_feedback(client) -> None:
    with session_scope() as db:
        row = _seed_queue_row(db, brand="Jaguar Transit", platform="x", draft_content="original copy")
        content_id = row.id

    response = client.post(
        f"/dashboard/queue/{content_id}/edit",
        data={
            "final_content": "corrected copy",
            "error_tag": "wrong_cta",
            "human_note": "Swapped the CTA for the SG market.",
        },
    )

    assert response.status_code == 200
    with session_scope() as db:
        item = db.get(ContentQueue, content_id)
        assert item.final_content == "corrected copy"
        assert item.status == ContentStatus.APPROVED.value

        feedback = db.query(FeedbackMemory).filter_by(content_id=content_id).one()
        assert feedback.error_tag == "wrong_cta"
        assert feedback.human_note == "Swapped the CTA for the SG market."


def test_reject_on_missing_item_returns_404(client) -> None:
    response = client.post(
        "/dashboard/queue/999999999/reject",
        data={"error_tag": "other", "human_note": "n/a"},
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# The closed loop: a rejection here is retrievable by Phase 3's memory engine
# --------------------------------------------------------------------------- #


def test_rejection_is_retrievable_by_memory_engine(client) -> None:
    from app.memory.retrieval import get_recent_feedback

    with session_scope() as db:
        row = _seed_queue_row(db, brand="Jade", platform="tiktok")
        content_id = row.id

    client.post(
        f"/dashboard/queue/{content_id}/reject",
        data={"error_tag": "too_salesy", "human_note": "Reads like an ad, not a story."},
    )

    with session_scope() as db:
        entries = get_recent_feedback(db, brand="Jade", platform="tiktok")

    assert any(e.human_note == "Reads like an ad, not a story." for e in entries)


# --------------------------------------------------------------------------- #
# Static media serving (Phase 8): /static mount and detail-page embedding
# --------------------------------------------------------------------------- #


def test_media_urls_empty_without_media_path() -> None:
    from app.api.dashboard import _media_urls

    assert _media_urls(None) == {}


def test_media_urls_passthrough_for_already_static_path() -> None:
    from app.api.dashboard import _media_urls

    assert _media_urls("/static/sample.mp4") == {"video_url": "/static/sample.mp4", "file": "sample.mp4"}


def test_media_urls_resolves_local_file_under_generated_dir() -> None:
    from app.api.dashboard import _media_urls
    from app.config import settings

    local_path = settings.generated_dir / "reel_abc123.mp4"
    assert _media_urls(str(local_path)) == {"video_url": "/static/reel_abc123.mp4", "file": "reel_abc123.mp4"}


def test_media_urls_empty_for_an_unrecognized_absolute_path() -> None:
    from app.api.dashboard import _media_urls

    assert _media_urls("/some/other/machine/reel.mp4") == {}


def test_media_urls_assumes_temp_for_bare_relative_filenames() -> None:
    from app.api.dashboard import _media_urls

    assert _media_urls("reel_xyz.mp4") == {
        "video_url": "/temp/reel_xyz.mp4",
        "srt_url": "/temp/reel_xyz.srt",
        "json_url": "/temp/reel_xyz.json",
        "file": "reel_xyz.mp4",
    }


def test_queue_detail_embeds_video_when_media_is_servable(client) -> None:
    with session_scope() as db:
        row = _seed_queue_row(db, media_path="/static/sample.mp4")
        content_id = row.id

    response = client.get(f"/dashboard/queue/{content_id}")

    assert '<video controls' in response.text
    assert "/static/sample.mp4" in response.text


def test_static_mount_serves_a_real_file(client) -> None:
    from app.config import settings

    probe = settings.generated_dir / "test_probe.txt"
    probe.write_text("ok")
    try:
        response = client.get("/static/test_probe.txt")
        assert response.status_code == 200
        assert response.text == "ok"
    finally:
        probe.unlink()


def test_api_draft_script_retail_device(client) -> None:
    res = client.post("/api/media/draft-script", json={"topic": "iPhone 18 Pro 5% offer", "brand": "Jade"})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "voiceover_script" in data
    assert "visual_prompt" in data
    assert "social_copy" in data
    assert len(data["voiceover_script"]) > 10


def test_api_draft_script_medical(client) -> None:
    res = client.post("/api/media/draft-script", json={"topic": "telemedicine liabilities", "brand": "DoctorShield"})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "DoctorShield" in data["voiceover_script"] or "clinical" in data["voiceover_script"].lower() or "practice" in data["voiceover_script"].lower()


def test_api_draft_script_cargo(client) -> None:
    res = client.post("/api/media/draft-script", json={"topic": "Red Sea detour cold-chain", "brand": "Jaguar Transit"})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "Jaguar Transit" in data["voiceover_script"] or "cargo" in data["voiceover_script"].lower() or "freight" in data["voiceover_script"].lower()


def test_api_synthesize_speech(client) -> None:
    res = client.post("/api/media/synthesize-speech", json={"script": "Test neural voiceover.", "language": "en"})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["audio_url"].startswith("/temp/")
    assert data["filename"].endswith(".mp3")


def test_api_perception_scrape_live_search(client) -> None:
    res = client.post("/api/perception/scrape", json={"competitor": "Chubb", "brand": "Jade"})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert len(data["extracted_claims"]) > 0
    assert len(data["competitor_gaps"]) > 0
    assert "Jade" in data["counter_positioning_hook"]
    assert "crawl_telemetry" in data
    assert data["crawl_telemetry"]["tokens_consumed"] == 0

