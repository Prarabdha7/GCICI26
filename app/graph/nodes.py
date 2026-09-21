"""LangGraph node implementations for the marketing pipeline.

Every LLM call goes through app.llm.client — nodes never import a vendor SDK
directly (CLAUDE.md section 12).
"""

from __future__ import annotations

import logging

from app.agents import prompts
from app.config import settings
from app.db.database import session_scope
from app.db.models import ContentStatus
from app.db.persist import create_content_queue_row
from app.graph.state import MarketingState
from app.llm.client import COMPLIANCE_SCHEMA, structured_call, text_call
from app.media.assembly import assemble_video
from app.memory.retrieval import format_guidance, get_recent_feedback

log = logging.getLogger(__name__)


def memory_retrieval_node(state: MarketingState) -> dict:
    """Runs before content_node on every generation (not on retries)."""
    with session_scope() as db:
        entries = get_recent_feedback(db, brand=state["brand"], platform=state["platform"])
    return {"feedback_guidance": format_guidance(entries)}


def content_node(state: MarketingState) -> dict:
    """Generate (or rewrite) the draft. Injects prior compliance violations
    into the rewrite prompt so a retry is never identical to the last draft."""
    system = prompts.content_system_prompt(
        brand=state["brand"],
        platform=state["platform"],
        feedback_guidance=state.get("feedback_guidance", ""),
    )
    user = prompts.content_user_prompt(
        brand=state["brand"],
        platform=state["platform"],
        compliance_errors=state.get("compliance_errors") or None,
    )
    draft = text_call(system=system, user=user)
    log.info(
        "content_node brand=%s platform=%s retry_count=%s",
        state["brand"], state["platform"], state.get("retry_count", 0),
    )
    return {"draft_content": draft}


def localization_node(state: MarketingState) -> dict:
    """Adapt the draft for the target market. Runs even for `en` (a light
    regional pass), and always before the compliance gate."""
    system = prompts.localization_system_prompt(brand=state["brand"], language=state["language"])
    user = prompts.localization_user_prompt(
        draft_content=state["draft_content"], language=state["language"]
    )
    localized = text_call(system=system, user=user)
    log.info("localization_node brand=%s language=%s", state["brand"], state["language"])
    return {"draft_content": localized}


def compliance_gate_node(state: MarketingState) -> dict:
    """Structured, temperature-0 judge grounded in compliance_rubric.md, read
    fresh from disk on every call so rubric edits need no restart."""
    rubric = settings.compliance_rubric_path.read_text(encoding="utf-8")
    system = prompts.compliance_system_prompt(brand=state["brand"], rubric=rubric)
    user = prompts.compliance_user_prompt(draft_content=state["draft_content"])
    verdict = structured_call(system=system, user=user, schema=COMPLIANCE_SCHEMA, temperature=0.0)

    is_compliant = bool(verdict.get("is_compliant"))
    violations = list(verdict.get("violations") or [])

    if is_compliant:
        log.info("compliance_gate_node brand=%s PASS", state["brand"])
        return {"compliance_errors": []}

    retry_count = state.get("retry_count", 0) + 1
    log.info(
        "compliance_gate_node brand=%s FAIL retry_count=%s violations=%s",
        state["brand"], retry_count, violations,
    )
    return {"compliance_errors": violations, "retry_count": retry_count}


def persist_node(state: MarketingState) -> dict:
    """Writes the compliant draft to content_queue with status=pending."""
    with session_scope() as db:
        row = create_content_queue_row(
            db,
            brand=state["brand"],
            platform=state["platform"],
            language=state["language"],
            draft_content=state["draft_content"],
            media_path=state.get("media_path"),
            compliance_errors=state.get("compliance_errors", []),
            retry_count=state.get("retry_count", 0),
        )
        content_id = row.id
    log.info("persist_node brand=%s content_id=%s", state["brand"], content_id)
    return {"content_id": content_id, "status": ContentStatus.PENDING.value}


def video_assembly_node(state: MarketingState) -> dict:
    """For video assets (Reels, TikTok). Not wired into build_graph()'s default
    topology yet — nothing gates "this needs a video" (CLAUDE.md section 8)."""
    video_path = assemble_video(script=state["draft_content"], language=state["language"])
    log.info("video_assembly_node brand=%s media_path=%s", state["brand"], video_path)
    return {"media_path": str(video_path)}


def manual_intervention_node(state: MarketingState) -> dict:
    """Terminal node for the circuit-breaker path. The graph never loops
    forever and never crashes on a stubborn draft."""
    log.warning(
        "manual_intervention_node brand=%s retry_count=%s violations=%s",
        state["brand"], state.get("retry_count", 0), state.get("compliance_errors", []),
    )
    return {}
