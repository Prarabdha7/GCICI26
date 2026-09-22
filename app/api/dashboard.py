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
    # Real-only headline numbers — demo rows are counted separately below and
    # never mixed into real rates.
    rows = db.execute(
        select(ContentQueue.status, func.count(ContentQueue.id))
        .where(ContentQueue.is_demo.is_(False))
        .group_by(ContentQueue.status)
    ).all()
    by_status = {status: count for status, count in rows}
    approved = by_status.get(ContentStatus.APPROVED.value, 0)
    rejected = by_status.get(ContentStatus.REJECTED.value, 0)
    decided = approved + rejected

    feedback_rows = list(db.scalars(select(FeedbackMemory).order_by(FeedbackMemory.timestamp.desc()).limit(50)))
    # edit-distance telemetry from human-edited REAL rows (draft vs final)
    edited = list(
        db.scalars(
            select(ContentQueue).where(ContentQueue.final_content.is_not(None), ContentQueue.is_demo.is_(False)).limit(200)
        )
    )
    distances = [_edit_distance(r.draft_content or "", r.final_content or "") for r in edited if r.final_content]
    avg_edit = round(sum(distances) / len(distances), 1) if distances else 0.0
    demo_count = db.scalar(select(func.count(ContentQueue.id)).where(ContentQueue.is_demo.is_(True))) or 0

    return templates.TemplateResponse(
        request,
        "metrics.html",
        {
            "active_tab": "metrics",
            "by_status": by_status,
            "rejection_rate": round(rejected / decided, 4) if decided else 0.0,
            "avg_retries": round(db.scalar(select(func.avg(ContentQueue.retry_count)).where(ContentQueue.is_demo.is_(False))) or 0.0, 2),
            "feedback_entries": db.scalar(select(func.count(FeedbackMemory.id))) or 0,
            "leads": db.scalar(select(func.count(Lead.id))) or 0,
            "avg_edit_distance": avg_edit,
            "lessons": feedback_rows[:15],
            "demo_count": demo_count,
            "demo_mode": settings.demo_mode,
        },
    )


def _media_urls(media_path: str | None) -> dict:
    """Map stored media_path to web URLs. Reel-pipeline rows store
    `temp/reel_xxx.mp4` (served at /temp, with sibling .srt/.json captions);
    rows resolved to assets/generated/ (the /static mount, e.g.
    scripts/seed_demo.py's sample media — checked against the real filesystem,
    not string-matching) pass through with no caption siblings, since that
    pipeline doesn't generate any. Anything else unrecognized returns {},
    so the caller falls back to showing the raw path as text."""
    if not media_path:
        return {}
    import pathlib

    p = media_path.replace("\\", "/")
    name = pathlib.PurePath(p).name

    if p.startswith("/static/"):
        return {"video_url": p, "file": name}
    try:
        if pathlib.Path(media_path).resolve().is_relative_to(settings.generated_dir.resolve()):
            return {"video_url": f"/static/{name}", "file": name}
    except (OSError, ValueError):
        pass

    if p.startswith("temp/"):
        base = p
    elif "/temp/" in p:
        base = "temp/" + p.split("/temp/", 1)[1]
    elif not p.startswith("/"):
        base = f"temp/{name}"
    else:
        return {}
    stem = base[:-4] if base.endswith(".mp4") else base
    return {
        "video_url": f"/{base}",
        "srt_url": f"/{stem}.srt",
        "json_url": f"/{stem}.json",
        "file": name,
    }


def _image_urls(image_paths: list[str] | None) -> list[str]:
    """Same servable-path rule as _media_urls (video), applied per stored image."""
    if not image_paths:
        return []
    import pathlib

    urls = []
    for media_path in image_paths:
        p = media_path.replace("\\", "/")
        name = pathlib.PurePath(p).name
        if p.startswith("/static/"):
            urls.append(p)
            continue
        try:
            if pathlib.Path(media_path).resolve().is_relative_to(settings.generated_dir.resolve()):
                urls.append(f"/static/{name}")
                continue
        except (OSError, ValueError):
            pass
        if p.startswith("temp/"):
            urls.append(f"/{p}")
        elif "/temp/" in p:
            urls.append("/temp/" + p.split("/temp/", 1)[1])
        elif not p.startswith("/"):
            urls.append(f"/temp/{name}")
    return urls


@router.get("/dashboard/queue/{content_id}", response_class=HTMLResponse)
def queue_detail(content_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    import difflib
    import json as _json

    item = _get_item_or_404(content_id, db)
    media = _media_urls(item.media_path)
    image_urls = _image_urls(item.image_paths)
    # caption cards for the player (best-effort read of sibling .json)
    captions: list[dict] = []
    try:
        from pathlib import Path as _Path

        sibling = None
        if item.media_path:
            mp = (item.media_path or "").replace("\\", "/")
            fname = mp.split("/")[-1]
            stem = fname[:-4] if fname.endswith(".mp4") else fname
            sibling = _Path(settings.base_dir) / "temp" / f"{stem}.json"
        if sibling is not None and sibling.exists():
            captions = (_json.loads(sibling.read_text(encoding="utf-8")) or {}).get("captions", [])[:24]
    except Exception:
        captions = []
    # redline diff draft -> healed/final
    diff_rows: list[tuple[str, str]] = []
    target = item.healed_content or item.final_content
    if target and target != item.draft_content:
        for line in difflib.unified_diff(
            (item.draft_content or "").splitlines(),
            target.splitlines(),
            lineterm="",
        ):
            if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
                continue
            diff_rows.append(("del" if line.startswith("-") else "ins" if line.startswith("+") else "ctx", line[1:]))
    # multi-format pack
    pack: dict = {}
    try:
        pack = _json.loads(item.formats_json) if item.formats_json else {}
    except Exception:
        pack = {}
    return templates.TemplateResponse(
        request,
        "queue_detail.html",
        {"item": item, "error_tags": [tag.value for tag in ErrorTag], "media": media, "image_urls": image_urls, "captions": captions, "diff_rows": diff_rows, "pack": pack},
    )


@router.post("/dashboard/queue/{content_id}/approve")
def approve(content_id: int, request: Request, db: Session = Depends(get_db)) -> Response:
    item = _get_item_or_404(content_id, db)
    item.status = ContentStatus.APPROVED.value
    item.reviewed_at = dt.datetime.now(dt.UTC)
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
    item.reviewed_at = dt.datetime.now(dt.UTC)
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
    item.reviewed_at = dt.datetime.now(dt.UTC)
    db.commit()
    create_feedback_entry(
        db, brand=item.brand, platform=item.platform,
        error_tag=error_tag, human_note=human_note, content_id=item.id,
    )
    return _action_response(request)


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance (stdlib only) for closed-loop telemetry."""
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


@router.post("/dashboard/generate", response_class=HTMLResponse)
def generate_campaign(
    request: Request,
    brand: str = Form(...),
    platform: str = Form(default="linkedin"),
    language: str = Form(default="en"),
    topic: str = Form(default=""),
    content_type: str = Form(default="post"),
):
    """Mission-control trigger: runs the LangGraph pipeline synchronously.
    Real mode: requires a configured LLM or fails honestly. Demo mode
    (DEMO_MODE=true): produces rows explicitly labeled DEMO."""
    import uuid

    from app.db.database import session_scope as _scope
    from app.graph.graph import build_graph

    initial_state = {
        "draft_content": "",
        "brand": brand,
        "platform": platform,
        "language": language,
        "topic": topic,
        "content_type": content_type,
        "enable_adversarial": True,
        "compliance_errors": [],
        "retry_count": 0,
        "feedback_guidance": "",
        "media_path": None,
        "status": "",
        "content_id": None,
    }
    try:
        graph = build_graph()
        final_state = graph.invoke(initial_state, config={"configurable": {"thread_id": str(uuid.uuid4())}})
        is_demo_row = False
        try:
            with _scope() as _db:
                _row = _db.get(ContentQueue, final_state.get("content_id"))
                is_demo_row = bool(_row.is_demo) if _row is not None else False
        except Exception:
            pass
        tag = "[DEMO — simulated, not real] " if (settings.demo_mode or is_demo_row) else ""
        msg = f"{tag}Generated {brand}/{platform} (content_id={final_state.get('content_id')}, retries={final_state.get('retry_count', 0)})."
    except Exception as exc:
        msg = f"Generation failed honestly (real mode, no fabrication): {exc}"
    # re-render queue with a status banner
    from sqlalchemy.orm import Session as SASession

    db: SASession = next(get_db())
    try:
        items = list(
            db.scalars(
                select(ContentQueue)
                .where(ContentQueue.status == ContentStatus.PENDING.value)
                .order_by(ContentQueue.created_at.desc())
            )
        )
    finally:
        db.close()
    return templates.TemplateResponse(
        request, "dashboard.html", {"items": items, "active_tab": "queue", "banner": msg}
    )


@router.post("/dashboard/queue/{content_id}/accept-fix")
def accept_fix(content_id: int, request: Request, db: Session = Depends(get_db)) -> Response:
    """One-click self-healing: apply heuristic redline fix and approve."""
    from app.llm.fallback import heuristic_compliance_check, self_healing_fix

    item = _get_item_or_404(content_id, db)
    verdict = heuristic_compliance_check(item.draft_content or "")
    fixed = self_healing_fix(item.draft_content or "", verdict.get("violations", []))
    item.final_content = fixed
    item.healed_content = item.healed_content or fixed
    item.status = ContentStatus.APPROVED.value
    item.reviewed_at = dt.datetime.now(dt.UTC)
    db.commit()
    create_feedback_entry(
        db, brand=item.brand, platform=item.platform,
        error_tag="compliance_risk", human_note="Accepted self-healing fix.", content_id=item.id,
    )
    return _action_response(request)


@router.post("/dashboard/newsjack", response_class=HTMLResponse)
def newsjack(
    request: Request,
    brand: str = Form(...),
    niche: str = Form(default="jewellers block"),
    country: str = Form(default="Singapore"),
    platform: str = Form(default="linkedin"),
    language: str = Form(default="en"),
):
    """Competitor-intel trigger: research -> topic -> full campaign (zero-key safe)."""
    import uuid

    from app.graph.graph import build_graph
    from worker.intel import newsjack_topic

    try:
        topic = newsjack_topic(brand, niche, country)
        graph = build_graph()
        final_state = graph.invoke(
            {
                "draft_content": "", "brand": brand, "platform": platform,
                "language": language, "topic": topic, "content_type": "post",
                "enable_adversarial": True, "compliance_errors": [], "retry_count": 0,
                "feedback_guidance": "", "media_path": None, "status": "", "content_id": None,
            },
            config={"configurable": {"thread_id": str(uuid.uuid4())}},
        )
        tag = "[DEMO — simulated, not real] " if settings.demo_mode else ""
        msg = f"{tag}Newsjacked {brand}/{country} (content_id={final_state.get('content_id')}): {topic[:120]}"
    except Exception as exc:
        msg = f"Newsjack failed honestly (real mode, no fabrication): {exc}"
    db: Session = next(get_db())
    try:
        items = list(
            db.scalars(
                select(ContentQueue)
                .where(ContentQueue.status == ContentStatus.PENDING.value)
                .order_by(ContentQueue.created_at.desc())
            )
        )
    finally:
        db.close()
    return templates.TemplateResponse(
        request, "dashboard.html", {"items": items, "active_tab": "queue", "banner": msg}
    )
