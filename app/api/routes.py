"""REST routes.

Phase 1 ships read-only views over the three tables plus a stats endpoint —
enough to prove the schema works and to back the review dashboard in Phase 6.
Approve / edit / reject write endpoints land with the dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import ContentQueueOut, FeedbackMemoryOut, LeadOut, QueueStats
from app.db.database import get_db
from app.db.models import ContentQueue, ContentStatus, FeedbackMemory, Lead

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
    rows = db.execute(
        select(ContentQueue.status, func.count(ContentQueue.id)).group_by(ContentQueue.status)
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
