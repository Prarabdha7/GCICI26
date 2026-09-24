"""Discrete execution nodes for the LangGraph state machine.

Each function in this module acts as a pure or effectful transformation step over
`MarketingState`. Nodes are executed sequentially or conditionally by the compiled
LangGraph runtime (`app.graph.graph.build_graph`).

State Transition Semantics:
    1. Immutability & Threading: Node functions accept the current immutable state
       snapshot, perform their domain-specific step, and return a dictionary of partial
       state updates to be merged by LangGraph's reducer.
    2. Fail-Safe Cascading: External services (live search, LLM completions, media
       synthesis) are wrapped in fail-closed heuristic fallbacks (`app.llm.fallback`).
       Node execution will not raise fatal exceptions on network or API failures, ensuring
       deterministic completion through to the compliance evaluation gate.
    3. Statutory Gatekeeping: Compliance nodes evaluate drafted copy deterministically
       against regulatory rules (MAS Notice 318 / BNM / HKIA). On violation, the node
       initiates an adversarial 3-agent debate loop with a hard retry ceiling to prevent
       infinite token consumption.
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
from app.media.image_gen import generate_image
from app.memory.retrieval import format_guidance, get_recent_feedback
from app.utils.research import research_summary

log = logging.getLogger(__name__)


def _adversarial_debate(brand: str, draft: str, rubric: str, violations: list[str]) -> tuple[str, str]:
    """Conduct a 3-agent adversarial debate between Growth Marketer, Regulatory Inquisitor, and Arbiter.

    Args:
        brand: Target insurance brand name.
        draft: Generated promotional text copy under review.
        rubric: Full text of statutory compliance rubric.
        violations: List of flagged statutory violation statements.

    Returns:
        tuple[str, str]: A formatted debate transcript and a self-healed compliant text draft.
    """
    joined = "\n".join(f"- {v}" for v in violations) or "- (heuristic gate)"
    try:
        marketer = text_call(
            system="You are a growth marketer. Be concise.",
            user=prompts.adversarial_marketer_prompt(brand=brand, draft=draft),
        )
    except LLMError:
        marketer = "Marketer: keep bold hook for CTR, but accept disclaimer insertion."
    try:
        inquisitor = text_call(
            system="You are a strict MAS/HKIA auditor.",
            user=prompts.adversarial_inquisitor_prompt(brand=brand, draft=draft, rubric=rubric[:3000]),
        )
    except LLMError:
        inquisitor = f"Inquisitor: {joined} (cites Rubric 4 / MAS-1)"
    try:
        arbiter = text_call(
            system="You are the underwriter arbiter.",
            user=prompts.adversarial_arbiter_prompt(brand=brand, draft=draft, violations=joined),
        )
    except LLMError:
        arbiter = self_healing_fix(draft, violations)
    transcript = f"Marketer: {marketer}\n\nInquisitor: {inquisitor}\n\nArbiter: {arbiter[:800]}"
    healed = arbiter if len(arbiter) > 20 else self_healing_fix(draft, violations)
    return transcript, healed


def memory_retrieval_node(state: MarketingState) -> dict:
    """Retrieve historical human editorial corrections and augment with persistent agent memory.

    Args:
        state: Active LangGraph marketing workflow state.

    Returns:
        dict: State update dictionary with 'feedback_guidance' string.
    """
    with session_scope() as db:
        entries = get_recent_feedback(db, brand=state["brand"], platform=state["platform"])
    local_guidance = format_guidance(entries)
    guidance = augment_guidance_with_memgpt(
        brand=state["brand"],
        platform=state["platform"],
        local_guidance=local_guidance,
    )
    return {"feedback_guidance": guidance}


def market_research_node(state: MarketingState) -> dict:
    """Ground promotional copy in live market news and competitor activity.

    Args:
        state: Active LangGraph marketing workflow state.

    Returns:
        dict: State update dictionary with 'market_research' context string.
    """
    topic = state.get("topic")
    query = f"{state['brand']} {topic} news" if topic else f"{state['brand']} insurance news"
    try:
        market_research = asyncio.run(research_summary(query))
    except Exception:
        log.exception("market_research_node: live research failed for %r", query)
        market_research = ""
    log.info(
        "market_research_node brand=%s topic=%s found=%s",
        state["brand"],
        topic,
        bool(market_research),
    )
    return {"market_research": market_research}


def content_node(state: MarketingState) -> dict:
    """Synthesize primary marketing copy or rewrite based on regulatory feedback.

    Args:
        state: Active LangGraph marketing workflow state.

    Returns:
        dict: State update dictionary containing the newly drafted content.

    Raises:
        LLMError: If LLM generation fails while in production mode.
    """
    system = prompts.content_system_prompt(
        brand=state["brand"],
        platform=state["platform"],
        feedback_guidance=state.get("feedback_guidance", ""),
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
            state["brand"],
            state["platform"],
            topic=state.get("topic", "") or user[:200],
            feedback_guidance=state.get("feedback_guidance", ""),
        )
        result = _log_content(state, draft)
        result["is_demo"] = True
        return result


def _log_content(state: MarketingState, draft: str) -> dict:
    """Log telemetry details for content generation attempts.

    Args:
        state: Active LangGraph state.
        draft: Newly produced draft string.

    Returns:
        dict: State dictionary with 'draft_content'.
    """
    log.info(
        "content_node brand=%s platform=%s retry_count=%s",
        state["brand"],
        state["platform"],
        state.get("retry_count", 0),
    )
    return {"draft_content": draft}


def localization_node(state: MarketingState) -> dict:
    """Adapt the generated copy to the target jurisdiction's language and cultural tone.

    Args:
        state: Active LangGraph marketing state.

    Returns:
        dict: State update dictionary with localized draft content.

    Raises:
        LLMError: If remote LLM adaptation fails while operating in production mode.
    """
    system = prompts.localization_system_prompt(brand=state["brand"], language=state["language"])
    user = prompts.localization_user_prompt(draft_content=state["draft_content"], language=state["language"])
    try:
        localized = text_call(system=system, user=user)
    except LLMError as exc:
        if not settings.demo_mode:
            log.error("localization_node LLM unavailable in real mode (%s) — failing honestly", exc)
            raise
        base_draft = state["draft_content"] or ""
        while base_draft.startswith("[DEMO] "):
            base_draft = base_draft[7:]
        localized = "[DEMO] " + fallback_localize(base_draft, state["language"], state["brand"])
        log.info("localization_node brand=%s language=%s (demo)", state["brand"], state["language"])
        return {"draft_content": localized, "is_demo": True}
    log.info("localization_node brand=%s language=%s", state["brand"], state["language"])
    return {"draft_content": localized}


def compliance_gate_node(state: MarketingState) -> dict:
    """Evaluate content draft against statutory compliance rubrics with zero temperature.

    Loads the compliance rubric from disk dynamically on every run. Performs deterministic
    pattern matching alongside structured LLM evaluation against statutory regulations
    (e.g., MAS Notice 318 Clause 4.2 guarantee bans). If violations occur and adversarial
    mode is active, initiates a 3-agent debate to synthesize a self-healed draft.

    Args:
        state: Active LangGraph marketing state.

    Returns:
        dict: State update dictionary containing 'compliance_errors', 'retry_count',
              and optional 'audit_transcript' and 'healed_content'.
    """
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
        state["brand"],
        retry_count,
        violations,
    )
    if not state.get("enable_adversarial"):
        return {"compliance_errors": violations, "retry_count": retry_count}
    transcript, healed = _adversarial_debate(state["brand"], state["draft_content"], rubric, violations)
    return {
        "compliance_errors": violations,
        "retry_count": retry_count,
        "audit_transcript": transcript,
        "healed_content": healed,
    }


def _carousel_image_paths(slides: list[str]) -> list[str]:
    """Synthesize image assets for each slide of a multi-image carousel post.

    Args:
        slides: List of textual descriptions or body copy per slide.

    Returns:
        list[str]: Web-relative paths to the generated slide images.
    """
    paths: list[str] = []
    for slide in slides:
        try:
            image_path = generate_image(_image_prompt(slide))
            media = str(image_path)
            try:
                base = settings.base_dir.resolve()
                media = image_path.resolve().relative_to(base).as_posix()
            except Exception:
                pass
            paths.append(media)
        except Exception as exc:
            log.warning("carousel slide image skipped (%s)", exc)
    return paths


def persist_node(state: MarketingState) -> dict:
    """Commit the validated draft, media assets, and format packs into the database queue.

    Args:
        state: Active LangGraph marketing state.

    Returns:
        dict: State update dictionary containing 'content_id' and initial PENDING status.
    """
    from app.agents.formats import build_format_pack, pack_to_json

    try:
        pack = build_format_pack(state["draft_content"], state["brand"], state.get("platform", "linkedin"))
        formats_json = pack_to_json(pack)
    except Exception as exc:
        log.warning("format pack skipped (%s)", exc)
        pack = None
        formats_json = None

    image_paths = list(state.get("image_paths") or [])
    content_type = (state.get("content_type") or "post").lower()
    if content_type == "carousel" and pack and pack.get("carousel"):
        image_paths = _carousel_image_paths(pack["carousel"])

    is_demo = bool(state.get("is_demo")) or (state.get("draft_content") or "").startswith("[DEMO]")
    with session_scope() as db:
        row = create_content_queue_row(
            db,
            brand=state["brand"],
            platform=state["platform"],
            language=state["language"],
            draft_content=state["draft_content"],
            media_path=state.get("media_path"),
            image_paths=image_paths or None,
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
    """Assemble a 9:16 vertical video reel for short-form video formats.

    Args:
        state: Active LangGraph marketing state.

    Returns:
        dict: State dictionary containing 'media_path' pointing to the assembled MP4.
    """
    try:
        from app.config import settings as _settings

        video_path = assemble_video(
            script=state["draft_content"],
            language=state.get("language", "en"),
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


def _image_prompt(draft: str) -> str:
    """Derive a clean, content-driven visual diffusion prompt from marketing copy.

    Args:
        draft: Generated promotional text copy.

    Returns:
        str: Refined prompt for photorealistic or editorial illustration generation.
    """
    subject = (draft or "").strip()[:250]
    if not subject:
        return (
            "A professional marketing photo, no text overlay, no logos, photorealistic, suitable for an Instagram post."
        )
    return (
        f"{subject} "
        "No text overlay, no logos, photorealistic or tasteful editorial "
        "illustration suitable for an Instagram post."
    )


def image_generation_node(state: MarketingState) -> dict:
    """Generate a single hero marketing image for visual social posts.

    Args:
        state: Active LangGraph marketing state.

    Returns:
        dict: State update dictionary containing 'image_paths' with the generated file path.
    """
    try:
        image_path = generate_image(_image_prompt(state["draft_content"]))
        media = str(image_path)
        try:
            base = settings.base_dir.resolve()
            rel = image_path.resolve().relative_to(base)
            media = rel.as_posix()
        except Exception:
            pass
    except Exception as exc:
        log.warning("image_generation_node skipped (%s)", exc)
        return {}
    log.info("image_generation_node brand=%s image_path=%s", state["brand"], media)
    return {"image_paths": [media]}


def manual_intervention_node(state: MarketingState) -> dict:
    """Terminal circuit-breaker state executed when maximum retry limits are exceeded.

    Transitions non-converging assets to human review without blocking the pipeline.

    Args:
        state: Active LangGraph marketing state.

    Returns:
        dict: Empty state dictionary indicating pipeline termination.
    """
    log.warning(
        "manual_intervention_node brand=%s retry_count=%s violations=%s",
        state["brand"],
        state.get("retry_count", 0),
        state.get("compliance_errors", []),
    )
    return {}
