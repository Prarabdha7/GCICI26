"""Phase 7 tests: publisher providers and the auto-publisher worker.

All Buffer/Ayrshare HTTP calls are mocked — no live posts during pytest runs.

    pytest tests/test_phase7.py -v
"""

from __future__ import annotations

import httpx
import pytest

from app.config import settings
from app.db.database import session_scope
from app.db.models import ContentQueue, ContentStatus
from worker import publisher as publisher_module
from worker import scheduler as scheduler_module


def _fake_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=json_data, request=httpx.Request("POST", "https://example.test"))


def _seed_queue_row(db, **overrides) -> ContentQueue:
    fields = {
        "brand": "Jade", "platform": "linkedin", "language": "en",
        "draft_content": "draft copy", "status": ContentStatus.APPROVED.value,
    }
    fields.update(overrides)
    row = ContentQueue(**fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# --------------------------------------------------------------------------- #
# BufferPublisher
# --------------------------------------------------------------------------- #


def test_buffer_publisher_returns_post_id(monkeypatch) -> None:
    monkeypatch.setattr(
        publisher_module.httpx, "post",
        lambda *a, **kw: _fake_response({"data": {"createPost": {"id": "buf-1"}}}),
    )
    item = ContentQueue(brand="Jade", platform="linkedin", language="en", draft_content="hello")

    post_id = publisher_module.BufferPublisher(access_token="key").publish(item)

    assert post_id == "buf-1"


def test_buffer_publisher_requires_access_token() -> None:
    item = ContentQueue(brand="Jade", platform="linkedin", language="en", draft_content="hello")
    with pytest.raises(publisher_module.PublisherError):
        publisher_module.BufferPublisher(access_token="").publish(item)


def test_buffer_publisher_raises_on_graphql_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        publisher_module.httpx, "post",
        lambda *a, **kw: _fake_response({"errors": [{"message": "bad channel"}]}),
    )
    item = ContentQueue(brand="Jade", platform="linkedin", language="en", draft_content="hello")

    with pytest.raises(publisher_module.PublisherError):
        publisher_module.BufferPublisher(access_token="key").publish(item)


def test_buffer_publisher_translates_http_error_status_into_publisher_error(monkeypatch) -> None:
    """A real bug found via live testing: an expired/invalid token gets a 401
    from Buffer's actual API — raise_for_status() must not escape as a raw
    httpx.HTTPStatusError, or it crashes the whole scheduler job unhandled."""
    monkeypatch.setattr(
        publisher_module.httpx, "post",
        lambda *a, **kw: _fake_response({"error": "invalid token"}, status_code=401),
    )
    item = ContentQueue(brand="Jade", platform="linkedin", language="en", draft_content="hello")

    with pytest.raises(publisher_module.PublisherError):
        publisher_module.BufferPublisher(access_token="expired-key").publish(item)


def test_buffer_publisher_prefers_final_content_over_draft(monkeypatch) -> None:
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured["json"] = json
        return _fake_response({"data": {"createPost": {"id": "buf-1"}}})

    monkeypatch.setattr(publisher_module.httpx, "post", fake_post)
    item = ContentQueue(
        brand="Jade", platform="linkedin", language="en",
        draft_content="original", final_content="edited",
    )

    publisher_module.BufferPublisher(access_token="key").publish(item)

    assert captured["json"]["variables"]["input"]["text"] == "edited"


# --------------------------------------------------------------------------- #
# AyrsharePublisher
# --------------------------------------------------------------------------- #


def test_ayrshare_publisher_returns_post_id(monkeypatch) -> None:
    monkeypatch.setattr(
        publisher_module.httpx, "post",
        lambda *a, **kw: _fake_response({"postIds": [{"id": "ayr-1"}]}),
    )
    item = ContentQueue(brand="Jade", platform="instagram", language="en", draft_content="hello")

    post_id = publisher_module.AyrsharePublisher(api_key="key").publish(item)

    assert post_id == "ayr-1"


def test_ayrshare_publisher_requires_api_key() -> None:
    item = ContentQueue(brand="Jade", platform="instagram", language="en", draft_content="hello")
    with pytest.raises(publisher_module.PublisherError):
        publisher_module.AyrsharePublisher(api_key="").publish(item)


def test_ayrshare_publisher_raises_without_post_ids(monkeypatch) -> None:
    monkeypatch.setattr(publisher_module.httpx, "post", lambda *a, **kw: _fake_response({"postIds": []}))
    item = ContentQueue(brand="Jade", platform="instagram", language="en", draft_content="hello")

    with pytest.raises(publisher_module.PublisherError):
        publisher_module.AyrsharePublisher(api_key="key").publish(item)


def test_ayrshare_publisher_translates_http_error_status_into_publisher_error(monkeypatch) -> None:
    monkeypatch.setattr(
        publisher_module.httpx, "post",
        lambda *a, **kw: _fake_response({"error": "invalid token"}, status_code=401),
    )
    item = ContentQueue(brand="Jade", platform="instagram", language="en", draft_content="hello")

    with pytest.raises(publisher_module.PublisherError):
        publisher_module.AyrsharePublisher(api_key="expired-key").publish(item)


# --------------------------------------------------------------------------- #
# media URL helper
# --------------------------------------------------------------------------- #


def test_public_media_url_none_without_media_path() -> None:
    item = ContentQueue(brand="Jade", platform="linkedin", language="en", draft_content="x", media_path=None)
    assert publisher_module._public_media_url(item) is None


def test_public_media_url_none_without_base_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "public_media_base_url", "")
    item = ContentQueue(brand="Jade", platform="linkedin", language="en", draft_content="x", media_path="/tmp/reel.mp4")
    assert publisher_module._public_media_url(item) is None


def test_public_media_url_builds_from_base_and_filename(monkeypatch) -> None:
    """Files are served from the /static mount (app/main.py) — the URL must
    include that path segment, e.g. an ngrok base + /static/<filename>."""
    monkeypatch.setattr(settings, "public_media_base_url", "https://cdn.test")
    item = ContentQueue(brand="Jade", platform="linkedin", language="en", draft_content="x", media_path="/tmp/reel.mp4")
    assert publisher_module._public_media_url(item) == "https://cdn.test/static/reel.mp4"


# --------------------------------------------------------------------------- #
# get_publisher — swaps on available keys
# --------------------------------------------------------------------------- #


def test_get_publisher_prefers_buffer(monkeypatch) -> None:
    monkeypatch.setattr(settings, "buffer_access_token", "key")
    monkeypatch.setattr(settings, "ayrshare_api_key", "key")
    assert isinstance(publisher_module.get_publisher(), publisher_module.BufferPublisher)


def test_get_publisher_falls_back_to_ayrshare(monkeypatch) -> None:
    monkeypatch.setattr(settings, "buffer_access_token", "")
    monkeypatch.setattr(settings, "ayrshare_api_key", "key")
    assert isinstance(publisher_module.get_publisher(), publisher_module.AyrsharePublisher)


def test_get_publisher_raises_with_no_keys(monkeypatch) -> None:
    monkeypatch.setattr(settings, "buffer_access_token", "")
    monkeypatch.setattr(settings, "ayrshare_api_key", "")
    with pytest.raises(publisher_module.PublisherError):
        publisher_module.get_publisher()


# --------------------------------------------------------------------------- #
# publish_approved_content — the worker's poll cycle
# --------------------------------------------------------------------------- #


class _FakePublisher:
    def __init__(self, post_id: str = "post-1") -> None:
        self.post_id = post_id

    def publish(self, item: ContentQueue) -> str:
        return self.post_id


class _FailingPublisher:
    def publish(self, item: ContentQueue) -> str:
        raise publisher_module.PublisherError("boom")


def test_publish_approved_content_transitions_approved_to_scheduled(monkeypatch) -> None:
    """published is reserved for a future webhook confirmation the post went live."""
    with session_scope() as db:
        row = _seed_queue_row(db)
        content_id = row.id

    monkeypatch.setattr(scheduler_module, "get_publisher", lambda: _FakePublisher("post-abc"))

    count = scheduler_module.publish_approved_content()

    assert count == 1
    with session_scope() as db:
        item = db.get(ContentQueue, content_id)
        assert item.status == ContentStatus.SCHEDULED.value
        assert item.external_post_id == "post-abc"
        assert item.published_at is None


def test_publish_approved_content_ignores_non_approved_rows(monkeypatch) -> None:
    with session_scope() as db:
        pending = _seed_queue_row(db, status=ContentStatus.PENDING.value)
        rejected = _seed_queue_row(db, status=ContentStatus.REJECTED.value)
        pending_id, rejected_id = pending.id, rejected.id

    monkeypatch.setattr(scheduler_module, "get_publisher", lambda: _FakePublisher())

    scheduler_module.publish_approved_content()

    with session_scope() as db:
        assert db.get(ContentQueue, pending_id).status == ContentStatus.PENDING.value
        assert db.get(ContentQueue, rejected_id).status == ContentStatus.REJECTED.value


def test_publish_approved_content_skips_failures_without_crashing(monkeypatch) -> None:
    with session_scope() as db:
        row = _seed_queue_row(db)
        content_id = row.id

    monkeypatch.setattr(scheduler_module, "get_publisher", lambda: _FailingPublisher())

    count = scheduler_module.publish_approved_content()

    assert count == 0
    with session_scope() as db:
        assert db.get(ContentQueue, content_id).status == ContentStatus.APPROVED.value


def test_publish_approved_content_one_failure_does_not_block_others(monkeypatch) -> None:
    with session_scope() as db:
        good = _seed_queue_row(db, draft_content="unique-good-marker")
        bad = _seed_queue_row(db, draft_content="unique-bad-marker")
        good_id, bad_id = good.id, bad.id

    publishers = {good_id: _FakePublisher("ok-1"), bad_id: _FailingPublisher()}

    class RoutingPublisher:
        def publish(self, item):
            return publishers[item.id].publish(item)

    monkeypatch.setattr(scheduler_module, "get_publisher", lambda: RoutingPublisher())

    scheduler_module.publish_approved_content()

    with session_scope() as db:
        assert db.get(ContentQueue, good_id).status == ContentStatus.SCHEDULED.value
        assert db.get(ContentQueue, bad_id).status == ContentStatus.APPROVED.value


# --------------------------------------------------------------------------- #
# build_scheduler
# --------------------------------------------------------------------------- #


def test_build_scheduler_registers_the_poll_job() -> None:
    scheduler = scheduler_module.build_scheduler()
    job = scheduler.get_job(scheduler_module.JOB_ID)
    assert job is not None
    assert job.trigger.interval.total_seconds() == settings.publish_poll_interval
