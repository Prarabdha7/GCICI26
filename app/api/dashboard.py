"""Human review dashboard: Jinja2 + HTMX, server-rendered, no build step."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.db.models import ContentQueue, ContentStatus, ErrorTag, FeedbackMemory, Lead
from app.memory.store import create_feedback_entry

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory=str(settings.base_dir / "app" / "templates"))

# htmx sets this to the id of the resolved hx-target. Detail-page forms target
# #detail-actions; list-page row buttons target their own <tr id="row-...">.
DETAIL_TARGET_ID = "detail-actions"


def _action_response(request: Request) -> Response:
    if request.headers.get("HX-Target") == DETAIL_TARGET_ID:
        response = Response(status_code=200)
        response.headers["HX-Redirect"] = "/dashboard"
        return response
    return HTMLResponse("")


def _get_item_or_404(content_id: int, db: Session) -> ContentQueue:
    item = db.get(ContentQueue, content_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"content_queue row {content_id} not found")
    return item


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_home(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    items = list(
        db.scalars(
            select(ContentQueue)
            .where(ContentQueue.status == ContentStatus.PENDING.value)
            .order_by(ContentQueue.created_at.desc())
        )
    )
    return templates.TemplateResponse(
        request, "dashboard.html", {"items": items, "active_tab": "queue"}
    )


@router.get("/dashboard/manual-intervention", response_class=HTMLResponse)
def manual_intervention_view(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    items = list(
        db.scalars(
            select(ContentQueue)
            .where(ContentQueue.status == ContentStatus.MANUAL_INTERVENTION.value)
            .order_by(ContentQueue.created_at.desc())
        )
    )
    return templates.TemplateResponse(
        request,
        "manual_intervention.html",
        {
            "items": items,
            "active_tab": "manual",
            "max_retries": settings.max_compliance_retries,
        },
    )


@router.get("/dashboard/metrics", response_class=HTMLResponse)
def metrics_view(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    rows = db.execute(
        select(ContentQueue.status, func.count(ContentQueue.id)).group_by(ContentQueue.status)
    ).all()
    by_status = {status: count for status, count in rows}
    approved = by_status.get(ContentStatus.APPROVED.value, 0)
    rejected = by_status.get(ContentStatus.REJECTED.value, 0)
    decided = approved + rejected

    return templates.TemplateResponse(
        request,
        "metrics.html",
        {
            "active_tab": "metrics",
            "by_status": by_status,
            "rejection_rate": round(rejected / decided, 4) if decided else 0.0,
            "avg_retries": round(db.scalar(select(func.avg(ContentQueue.retry_count))) or 0.0, 2),
            "feedback_entries": db.scalar(select(func.count(FeedbackMemory.id))) or 0,
            "leads": db.scalar(select(func.count(Lead.id))) or 0,
        },
    )


@router.get("/dashboard/queue/{content_id}", response_class=HTMLResponse)
def queue_detail(content_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    item = _get_item_or_404(content_id, db)
    return templates.TemplateResponse(
        request,
        "queue_detail.html",
        {"item": item, "error_tags": [tag.value for tag in ErrorTag]},
    )


@router.post("/dashboard/queue/{content_id}/approve")
def approve(content_id: int, request: Request, db: Session = Depends(get_db)) -> Response:
    item = _get_item_or_404(content_id, db)
    item.status = ContentStatus.APPROVED.value
    item.reviewed_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    return _action_response(request)


@router.post("/dashboard/queue/{content_id}/reject")
def reject(
    content_id: int,
    request: Request,
    error_tag: str = Form(...),
    human_note: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    """Rejecting closes the loop: the human's reason becomes a feedback_memory
    row the content agent is shown before its next attempt for this brand."""
    item = _get_item_or_404(content_id, db)
    item.status = ContentStatus.REJECTED.value
    item.feedback_reason = human_note
    item.reviewed_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    create_feedback_entry(
        db, brand=item.brand, platform=item.platform,
        error_tag=error_tag, human_note=human_note, content_id=item.id,
    )
    return _action_response(request)


@router.post("/dashboard/queue/{content_id}/edit")
def edit(
    content_id: int,
    request: Request,
    final_content: str = Form(...),
    error_tag: str = Form(...),
    human_note: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    item = _get_item_or_404(content_id, db)
    item.final_content = final_content
    item.status = ContentStatus.APPROVED.value
    item.feedback_reason = human_note
    item.reviewed_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    create_feedback_entry(
        db, brand=item.brand, platform=item.platform,
        error_tag=error_tag, human_note=human_note, content_id=item.id,
    )
    return _action_response(request)
