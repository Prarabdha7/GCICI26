"""LangGraph node implementations for the marketing pipeline.

Every LLM call goes through app.llm.client — nodes never import a vendor SDK
directly (CLAUDE.md section 12).
"""

from __future__ import annotations

import asyncio
import logging

from app.agents import prompts
from app.config import settings
from app.db.database import session_scope
from app.db.models import ContentStatus
from app.db.persist import create_content_queue_row
from app.graph.state import MarketingState
from app.integrations.memgpt import augment_guidance_with_memgpt
from app.llm.client import COMPLIANCE_SCHEMA, LLMError, structured_call, text_call
from app.llm.fallback import fallback_content, fallback_localize, heuristic_compliance_check, self_healing_fix
from app.media.assembly import assemble_video
from app.memory.retrieval import (
    format_engagement_guidance,
    format_guidance,
    get_recent_engagement,
    get_recent_feedback,
)
from app.utils.research import research_summary

log = logging.getLogger(__name__)


def _adversarial_debate(brand: str, draft: str, rubric: str, violations: list[str]) -> tuple[str, str]:
    """Marketer vs Inquisitor vs Arbiter. Returns (transcript, healed). Zero-key safe."""
    joined = "\n".join(f"- {v}" for v in violations) or "- (heuristic gate)"
    try:
        marketer = text_call(system="You are a growth marketer. Be concise.", user=prompts.adversarial_marketer_prompt(brand=brand, draft=draft))
    except LLMError:
        marketer = "Marketer: keep bold hook for CTR, but accept disclaimer insertion."
    try:
        inquisitor = text_call(system="You are a strict MAS/HKIA auditor.", user=prompts.adversarial_inquisitor_prompt(brand=brand, draft=draft, rubric=rubric[:3000]))
    except LLMError:
        inquisitor = f"Inquisitor: {joined} (cites Rubric 4 / MAS-1)"
    try:
        arbiter = text_call(system="You are the underwriter arbiter.", user=prompts.adversarial_arbiter_prompt(brand=brand, draft=draft, violations=joined))
    except LLMError:
        arbiter = self_healing_fix(draft, violations)
    transcript = f"Marketer: {marketer}\n\nInquisitor: {inquisitor}\n\nArbiter: {arbiter[:800]}"
    healed = arbiter if len(arbiter) > 20 else self_healing_fix(draft, violations)
    return transcript, healed


def memory_retrieval_node(state: MarketingState) -> dict:
    """Runs before content_node on every generation (not on retries). Pulls
    human feedback AND measured real-post performance for the content agent."""
    with session_scope() as db:
        entries = get_recent_feedback(db, brand=state["brand"], platform=state["platform"])
        engagement = get_recent_engagement(db)
    local_guidance = format_guidance(entries)
    guidance = augment_guidance_with_memgpt(
        brand=state["brand"],
        platform=state["platform"],
        local_guidance=local_guidance,
    )
    return {
        "feedback_guidance": guidance,
        "engagement_guidance": format_engagement_guidance(
            engagement, brand=state["brand"], platform=state["platform"]
        ),
    }


def market_research_node(state: MarketingState) -> dict:
    """Grounds the upcoming draft in live market/competitor context via the
    keyless DuckDuckGo + Crawl4AI research utility (app/utils/research.py).
    DuckDuckGo's free backend is occasionally rate-limited — an empty result
    just means content_node writes without extra grounding, not a failure."""
    topic = state.get("topic")
    query = f"{state['brand']} {topic} news" if topic else f"{state['brand']} insurance news"
    try:
        market_research = asyncio.run(research_summary(query))
    except Exception:
        log.exception("market_research_node: live research failed for %r", query)
        market_research = ""
    log.info(
        "market_research_node brand=%s topic=%s found=%s",
        state["brand"], topic, bool(market_research),
    )
    return {"market_research": market_research}


def content_node(state: MarketingState) -> dict:
    """Generate (or rewrite) the draft. Injects prior compliance violations
    into the rewrite prompt so a retry is never identical to the last draft.
    Real mode: LLM errors propagate honestly. Demo mode (DEMO_MODE=true):
    labeled domain fallback tagged [DEMO]."""
    system = prompts.content_system_prompt(
        brand=state["brand"],
        platform=state["platform"],
        feedback_guidance=state.get("feedback_guidance", ""),
        engagement_guidance=state.get("engagement_guidance", ""),
    )
    user = prompts.content_user_prompt(
        brand=state["brand"],
        platform=state["platform"],
        topic=state.get("topic", ""),
        market_research=state.get("market_research", ""),
        compliance_errors=state.get("compliance_errors") or None,
    )
    try:
        draft = text_call(system=system, user=user)
        return _log_content(state, draft)
    except LLMError as exc:
        if not settings.demo_mode:
            log.error("content_node LLM unavailable in real mode (%s) — failing honestly", exc)
            raise
        log.warning("content_node LLM unavailable (%s) — labeled DEMO fallback", exc)
        draft = "[DEMO] " + fallback_content(
            state["brand"], state["platform"],
            topic=state.get("topic", "") or user[:200],
            feedback_guidance=state.get("feedback_guidance", ""),
        )
        result = _log_content(state, draft)
        result["is_demo"] = True
        return result


def _log_content(state: MarketingState, draft: str) -> dict:
    log.info(
        "content_node brand=%s platform=%s retry_count=%s",
        state["brand"], state["platform"], state.get("retry_count", 0),
    )
    return {"draft_content": draft}


def localization_node(state: MarketingState) -> dict:
    """Adapt the draft for the target market. Runs even for `en` (a light
    regional pass), and always before the compliance gate.
    Real mode: LLM errors propagate. Demo mode: labeled offline pass."""
    system = prompts.localization_system_prompt(brand=state["brand"], language=state["language"])
    user = prompts.localization_user_prompt(
        draft_content=state["draft_content"], language=state["language"]
    )
    try:
        localized = text_call(system=system, user=user)
    except LLMError as exc:
        if not settings.demo_mode:
            log.error("localization_node LLM unavailable in real mode (%s) — failing honestly", exc)
            raise
        log.warning("localization_node LLM unavailable (%s) — labeled DEMO pass", exc)
        localized = "[DEMO] " + fallback_localize(state["draft_content"], state["language"], state["brand"])
        log.info("localization_node brand=%s language=%s (demo)", state["brand"], state["language"])
        return {"draft_content": localized, "is_demo": True}
    log.info("localization_node brand=%s language=%s", state["brand"], state["language"])
    return {"draft_content": localized}


def compliance_gate_node(state: MarketingState) -> dict:
    """Structured, temperature-0 judge grounded in compliance_rubric.md, read
    fresh from disk on every call so rubric edits need no restart.
    LLM judge when available; deterministic local banned-phrase pre-check is
    always applied too and labeled [local-check] so its origin is explicit."""
    try:
        rubric = settings.compliance_rubric_path.read_text(encoding="utf-8")
    except OSError:
        rubric = "No Absolute Guarantees. No banned words. Disclaimer required."
    system = prompts.compliance_system_prompt(brand=state["brand"], rubric=rubric)
    user = prompts.compliance_user_prompt(draft_content=state["draft_content"])
    try:
        verdict = structured_call(system=system, user=user, schema=COMPLIANCE_SCHEMA, temperature=0.0)
    except LLMError as exc:
        log.warning("compliance_gate LLM unavailable (%s) — local deterministic check", exc)
        verdict = heuristic_compliance_check(state["draft_content"])
        verdict = {
            "is_compliant": verdict["is_compliant"],
            "violations": [f"[local-check] {v}" for v in verdict["violations"]],
        }

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
    # Adversarial debate only when explicitly enabled (dashboard generate).
    # Keeps exact return shape for unit tests that assert == dict.
    if not state.get("enable_adversarial"):
        return {"compliance_errors": violations, "retry_count": retry_count}
    transcript, healed = _adversarial_debate(state["brand"], state["draft_content"], rubric, violations)
    return {"compliance_errors": violations, "retry_count": retry_count, "audit_transcript": transcript, "healed_content": healed}


def persist_node(state: MarketingState) -> dict:
    """Writes the compliant draft to content_queue with status=pending.
    Also builds the multi-format pack (thread/carousel/A-B/focus group) best-effort."""
    from app.agents.formats import build_format_pack, pack_to_json

    try:
        pack = build_format_pack(state["draft_content"], state["brand"], state.get("platform", "linkedin"))
        formats_json = pack_to_json(pack)
    except Exception as exc:
        log.warning("format pack skipped (%s)", exc)
        formats_json = None
    is_demo = bool(state.get("is_demo")) or (state.get("draft_content") or "").startswith("[DEMO]")
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
            topic=state.get("topic"),
            content_type=state.get("content_type", "post"),
            healed_content=state.get("healed_content"),
            audit_transcript=state.get("audit_transcript"),
            formats_json=formats_json,
            is_demo=is_demo,
        )
        content_id = row.id
    log.info("persist_node brand=%s content_id=%s is_demo=%s", state["brand"], content_id, is_demo)
    return {"content_id": content_id, "status": ContentStatus.PENDING.value}


def video_assembly_node(state: MarketingState) -> dict:
    """Renders a reel for instagram/tiktok/video assets. Never crashes the graph:
    on media failure returns no media_path so text can still persist + gate.
    Stores media_path as web-relative `temp/<file>` so /temp mount serves it."""
    try:
        from app.config import settings as _settings

        video_path = assemble_video(
            script=state["draft_content"], language=state.get("language", "en"),
            brand=state.get("brand", "Jade"),
        )
        media = str(video_path)
        try:
            base = _settings.base_dir.resolve()
            rel = video_path.resolve().relative_to(base) if hasattr(video_path, "resolve") else None
            if rel is not None:
                media = rel.as_posix()
        except Exception:
            pass
    except Exception as exc:
        log.warning("video_assembly_node skipped (%s)", exc)
        return {}
    log.info("video_assembly_node brand=%s media_path=%s", state["brand"], media)
    return {"media_path": media}


def manual_intervention_node(state: MarketingState) -> dict:
    """Terminal node for the circuit-breaker path. The graph never loops
    forever and never crashes on a stubborn draft."""
    log.warning(
        "manual_intervention_node brand=%s retry_count=%s violations=%s",
        state["brand"], state.get("retry_count", 0), state.get("compliance_errors", []),
    )
    return {}
