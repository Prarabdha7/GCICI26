"""JSON action API for the static frontend (`/app`).

Thin wrappers over the same pipeline the HTML dashboard uses — generate,
newsjack, review actions, and media/caption resolution. Errors are honest
HTTP 4xx/5xx with plain messages; demo output is always tagged is_demo.
Nothing here invents data: every response comes from the DB or the graph.
"""

from __future__ import annotations

import datetime as dt
import difflib
import json as _json
import uuid
from pathlib import Path, PurePath
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.db.models import ContentQueue, ContentStatus, FeedbackMemory
from app.memory.store import create_feedback_entry

router = APIRouter(prefix="/api", tags=["actions"])


# --------------------------------------------------------------------------- #
# schemas
# --------------------------------------------------------------------------- #


class GenerateIn(BaseModel):
    brand: str
    platform: str = "linkedin"
    language: str = "en"
    topic: str = ""
    content_type: str = "post"


class NewsjackIn(BaseModel):
    brand: str
    niche: str = "jewellers block"
    country: str = "Singapore"
    platform: str = "linkedin"
    language: str = "en"


class RejectIn(BaseModel):
    error_tag: str
    human_note: str


class EditIn(BaseModel):
    final_content: str
    error_tag: str
    human_note: str


class ActionOut(BaseModel):
    ok: bool = True
    content_id: int
    status: str
    is_demo: bool = False
    message: str = ""


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _get_item_or_404(content_id: int, db: Session) -> ContentQueue:
    item = db.get(ContentQueue, content_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"content_queue row {content_id} not found")
    return item


def _media_urls(media_path: str | None) -> dict[str, Any]:
    """Same rule as the HTML dashboard: map stored path to servable URLs."""
    if not media_path:
        return {}
    p = media_path.replace("\\", "/")
    name = PurePath(p).name
    if p.startswith("temp/"):
        base = p
    elif "/temp/" in p:
        base = "temp/" + p.split("/temp/", 1)[1]
    else:
        base = f"temp/{name}"
    stem = base[:-4] if base.endswith(".mp4") else base
    return {"video_url": f"/{base}", "srt_url": f"/{stem}.srt", "json_url": f"/{stem}.json", "file": name}


def _read_captions(media_path: str | None, limit: int = 24) -> list[dict]:
    try:
        if not media_path:
            return []
        fname = media_path.replace("\\", "/").split("/")[-1]
        stem = fname[:-4] if fname.endswith(".mp4") else fname
        sibling = Path(settings.base_dir) / "temp" / f"{stem}.json"
        if not sibling.exists():
            return []
        return (_json.loads(sibling.read_text(encoding="utf-8")) or {}).get("captions", [])[:limit]
    except Exception:
        return []


def _diff_rows(before: str, after: str) -> list[dict]:
    rows = []
    for line in difflib.unified_diff((before or "").splitlines(), (after or "").splitlines(), lineterm=""):
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            continue
        kind = "del" if line.startswith("-") else "ins" if line.startswith("+") else "ctx"
        rows.append({"kind": kind, "text": line[1:]})
    return rows


def _run_pipeline(*, brand: str, platform: str, language: str, topic: str, content_type: str) -> dict:
    from app.graph.graph import build_graph

    graph = build_graph()
    try:
        return graph.invoke(
            {
                "draft_content": "", "brand": brand, "platform": platform,
                "language": language, "topic": topic, "content_type": content_type,
                "enable_adversarial": True, "compliance_errors": [], "retry_count": 0,
                "feedback_guidance": "", "media_path": None, "status": "", "content_id": None,
            },
            config={"configurable": {"thread_id": str(uuid.uuid4())}},
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Generation unavailable honestly: {exc}") from exc


# --------------------------------------------------------------------------- #
# endpoints
# --------------------------------------------------------------------------- #


@router.get("/demo/status")
def demo_status() -> dict:
    """Tells the frontend whether labeled demo output is enabled. No secrets."""
    return {"demo_mode": settings.demo_mode, "llm_configured": bool(settings.gemini_api_key or settings.openai_api_key)}


@router.post("/generate", response_model=ActionOut)
def generate(body: GenerateIn, db: Session = Depends(get_db)) -> ActionOut:
    final_state = _run_pipeline(brand=body.brand, platform=body.platform, language=body.language, topic=body.topic, content_type=body.content_type)
    item = _get_item_or_404(final_state["content_id"], db)
    tag = "[DEMO — simulated, not real] " if item.is_demo else ""
    return ActionOut(content_id=item.id, status=item.status, is_demo=item.is_demo,
                     message=f"{tag}Generated {item.brand}/{item.platform} (retries={item.retry_count}).")


@router.post("/newsjack", response_model=ActionOut)
def newsjack(body: NewsjackIn, db: Session = Depends(get_db)) -> ActionOut:
    from worker.intel import newsjack_topic

    try:
        topic = newsjack_topic(body.brand, body.niche, body.country)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Research unavailable honestly: {exc}") from exc
    final_state = _run_pipeline(brand=body.brand, platform=body.platform, language=body.language, topic=topic, content_type="post")
    item = _get_item_or_404(final_state["content_id"], db)
    tag = "[DEMO — simulated, not real] " if item.is_demo else ""
    return ActionOut(content_id=item.id, status=item.status, is_demo=item.is_demo,
                     message=f"{tag}Newsjacked {item.brand}/{body.country}: {topic[:120]}")


@router.post("/queue/{content_id}/approve", response_model=ActionOut)
def approve(content_id: int, db: Session = Depends(get_db)) -> ActionOut:
    item = _get_item_or_404(content_id, db)
    item.status = ContentStatus.APPROVED.value
    item.reviewed_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    return ActionOut(content_id=item.id, status=item.status, is_demo=item.is_demo, message="Approved — worker may publish.")


@router.post("/queue/{content_id}/reject", response_model=ActionOut)
def reject(content_id: int, body: RejectIn, db: Session = Depends(get_db)) -> ActionOut:
    item = _get_item_or_404(content_id, db)
    item.status = ContentStatus.REJECTED.value
    item.feedback_reason = body.human_note
    item.reviewed_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    create_feedback_entry(db, brand=item.brand, platform=item.platform,
                          error_tag=body.error_tag, human_note=body.human_note, content_id=item.id)
    return ActionOut(content_id=item.id, status=item.status, is_demo=item.is_demo, message="Rejected — feedback saved to memory.")


@router.post("/queue/{content_id}/edit", response_model=ActionOut)
def edit(content_id: int, body: EditIn, db: Session = Depends(get_db)) -> ActionOut:
    item = _get_item_or_404(content_id, db)
    item.final_content = body.final_content
    item.status = ContentStatus.APPROVED.value
    item.feedback_reason = body.human_note
    item.reviewed_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    create_feedback_entry(db, brand=item.brand, platform=item.platform,
                          error_tag=body.error_tag, human_note=body.human_note, content_id=item.id)
    return ActionOut(content_id=item.id, status=item.status, is_demo=item.is_demo, message="Edited, approved, feedback saved.")


@router.post("/queue/{content_id}/accept-fix", response_model=ActionOut)
def accept_fix(content_id: int, db: Session = Depends(get_db)) -> ActionOut:
    from app.llm.fallback import heuristic_compliance_check, self_healing_fix

    item = _get_item_or_404(content_id, db)
    verdict = heuristic_compliance_check(item.draft_content or "")
    fixed = self_healing_fix(item.draft_content or "", verdict.get("violations", []))
    item.final_content = fixed
    item.healed_content = item.healed_content or fixed
    item.status = ContentStatus.APPROVED.value
    item.reviewed_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    create_feedback_entry(db, brand=item.brand, platform=item.platform,
                          error_tag="compliance_risk", human_note="Accepted self-healing fix.", content_id=item.id)
    return ActionOut(content_id=item.id, status=item.status, is_demo=item.is_demo, message="Self-healing fix applied and approved.")


@router.get("/queue/{content_id}/media")
def queue_media(content_id: int, db: Session = Depends(get_db)) -> dict:
    """Servable media URLs + captions + redline diff for one row. 404 when absent."""
    item = _get_item_or_404(content_id, db)
    media = _media_urls(item.media_path)
    target = item.healed_content or item.final_content
    return {
        "content_id": item.id,
        "is_demo": item.is_demo,
        "media": media,
        "captions": _read_captions(item.media_path),
        "diff": _diff_rows(item.draft_content or "", target or "") if target and target != item.draft_content else [],
        "audit_transcript": item.audit_transcript,
        "healed_content": item.healed_content,
        "formats": _json.loads(item.formats_json) if item.formats_json else {},
    }


@router.get("/queue/{content_id}/feedback")
def queue_feedback(content_id: int, db: Session = Depends(get_db)) -> list[dict]:
    _get_item_or_404(content_id, db)
    from sqlalchemy import select

    from app.db.models import FeedbackMemory as _FM

    rows = list(db.scalars(select(_FM).where(_FM.content_id == content_id).order_by(_FM.timestamp)))
    return [{"error_tag": r.error_tag, "human_note": r.human_note,
             "at": r.timestamp.isoformat() if r.timestamp else None} for r in rows]


@router.get("/memory/vault")
def memory_vault(db: Session = Depends(get_db)) -> dict:
    """Rebuild the Obsidian-compatible memory vault from live DB rows and
    return its knowledge graph. Markdown files land under vault/ (gitignored)
    and are servable at /vault/*.md for reading or opening in Obsidian."""
    from app.memory.vault import export_vault

    return export_vault(db)
