"""REST routes.

Phase 1 ships read-only views over the three tables plus a stats endpoint —
enough to prove the schema works and to back the review dashboard in Phase 6.
Approve / edit / reject write endpoints land with the dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import ContentQueueOut, FeedbackMemoryOut, LeadOut, QueueStats
from app.db.database import get_db
from app.db.models import ContentQueue, ContentStatus, FeedbackMemory, Lead, PublishEvent

router = APIRouter(prefix="/api", tags=["queue"])


@router.get("/queue", response_model=list[ContentQueueOut])
def list_queue(
    db: Session = Depends(get_db),
    status: str | None = Query(default=None, description="filter by lifecycle status"),
    brand: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    language: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ContentQueue]:
    stmt = select(ContentQueue).order_by(ContentQueue.created_at.desc())
    if status:
        stmt = stmt.where(ContentQueue.status == status)
    if brand:
        stmt = stmt.where(ContentQueue.brand == brand)
    if platform:
        stmt = stmt.where(ContentQueue.platform == platform)
    if language:
        stmt = stmt.where(ContentQueue.language == language)
    return list(db.scalars(stmt.limit(limit).offset(offset)))


@router.get("/queue/{content_id}", response_model=ContentQueueOut)
def get_queue_item(content_id: int, db: Session = Depends(get_db)) -> ContentQueue:
    item = db.get(ContentQueue, content_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"content_queue row {content_id} not found")
    return item


@router.get("/feedback", response_model=list[FeedbackMemoryOut])
def list_feedback(
    db: Session = Depends(get_db),
    brand: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
) -> list[FeedbackMemory]:
    """The lessons-learned store. Phase 3 reads the top 5 of these before generating."""
    stmt = select(FeedbackMemory).order_by(FeedbackMemory.timestamp.desc())
    if brand:
        stmt = stmt.where(FeedbackMemory.brand == brand)
    if platform:
        stmt = stmt.where(FeedbackMemory.platform == platform)
    return list(db.scalars(stmt.limit(limit)))


@router.get("/leads", response_model=list[LeadOut])
def list_leads(
    db: Session = Depends(get_db),
    segment: str | None = Query(default=None),
    min_score: int | None = Query(default=None, ge=0, le=100),
    limit: int = Query(default=50, le=200),
) -> list[Lead]:
    stmt = select(Lead).order_by(Lead.fit_score.desc().nullslast())
    if segment:
        stmt = stmt.where(Lead.segment == segment)
    if min_score is not None:
        stmt = stmt.where(Lead.fit_score >= min_score)
    return list(db.scalars(stmt.limit(limit)))


@router.get("/stats", response_model=QueueStats)
def stats(db: Session = Depends(get_db)) -> QueueStats:
    # Real-only headline stats — demo rows excluded, never claimed as real.
    rows = db.execute(
        select(ContentQueue.status, func.count(ContentQueue.id))
        .where(ContentQueue.is_demo.is_(False))
        .group_by(ContentQueue.status)
    ).all()
    by_status = {status: count for status, count in rows}

    approved = by_status.get(ContentStatus.APPROVED.value, 0)
    rejected = by_status.get(ContentStatus.REJECTED.value, 0)
    decided = approved + rejected

    return QueueStats(
        total=sum(by_status.values()),
        by_status=by_status,
        feedback_entries=db.scalar(select(func.count(FeedbackMemory.id))) or 0,
        leads=db.scalar(select(func.count(Lead.id))) or 0,
        rejection_rate=round(rejected / decided, 4) if decided else 0.0,
    )


class WebhookPayload(BaseModel):
    content_id: int
    external_post_id: str | None = None
    status: str = "published"
    metrics: dict | None = None


@router.post("/publish/webhook")
def publish_webhook(payload: WebhookPayload, db: Session = Depends(get_db)) -> dict:
    """Real-provider confirmation: Buffer/Ayrshare calls back when a post goes live."""
    import datetime as dt

    item = db.get(ContentQueue, payload.content_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"content_queue row {payload.content_id} not found")
    if payload.external_post_id:
        item.external_post_id = payload.external_post_id
    if payload.status == "published":
        item.status = ContentStatus.PUBLISHED.value
        item.published_at = dt.datetime.now(dt.UTC)
    db.add(
        PublishEvent(
            content_id=item.id,
            event="webhook",
            provider="buffer",
            external_post_id=item.external_post_id,
            payload=payload.metrics or {},
        )
    )
    if payload.metrics:
        db.add(
            PublishEvent(
                content_id=item.id,
                event="engagement",
                provider="webhook",
                external_post_id=item.external_post_id,
                payload=payload.metrics,
            )
        )
    db.commit()
    return {"ok": True, "content_id": item.id, "status": item.status}


@router.get("/publish/events/{content_id}")
def publish_events(content_id: int, db: Session = Depends(get_db)) -> list[dict]:
    rows = list(
        db.scalars(select(PublishEvent).where(PublishEvent.content_id == content_id).order_by(PublishEvent.created_at))
    )
    return [
        {
            "event": r.event,
            "provider": r.provider,
            "external_post_id": r.external_post_id,
            "payload": r.payload or {},
            "at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def _lev(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


@router.get("/metrics/trend")
def metrics_trend(
    db: Session = Depends(get_db), days: int = Query(default=14, ge=1, le=90), include_demo: bool = Query(default=False)
) -> list[dict]:
    """Per-day learning curve over REAL rows (demo excluded unless include_demo=true)."""
    import datetime as dt

    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
    stmt = select(ContentQueue).where(ContentQueue.created_at >= since)
    if not include_demo:
        stmt = stmt.where(ContentQueue.is_demo.is_(False))
    rows = list(db.scalars(stmt.order_by(ContentQueue.created_at)))
    buckets: dict[str, list] = {}
    for r in rows:
        key = r.created_at.date().isoformat() if r.created_at else "undated"
        buckets.setdefault(key, []).append(r)
    out = []
    for day in sorted(buckets):
        items = buckets[day]
        approved = sum(1 for r in items if r.status == ContentStatus.APPROVED.value)
        rejected = sum(1 for r in items if r.status == ContentStatus.REJECTED.value)
        decided = approved + rejected
        dists = [_lev(r.draft_content or "", r.final_content or "") for r in items if r.final_content]
        retries = [r.retry_count or 0 for r in items]
        out.append(
            {
                "date": day,
                "created": len(items),
                "approved": approved,
                "rejected": rejected,
                "rejection_rate": round(rejected / decided, 4) if decided else 0.0,
                "avg_edit_distance": round(sum(dists) / len(dists), 1) if dists else 0.0,
                "avg_retries": round(sum(retries) / len(retries), 2) if retries else 0.0,
            }
        )
    return out
