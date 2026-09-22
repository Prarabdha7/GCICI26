"""Optional MemGPT augmentation for memory guidance."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)


def _extract_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, list):
        for item in reversed(payload):
            text = _extract_text(item)
            if text:
                return text
        return ""
    if isinstance(payload, dict):
        for key in ("content", "text", "message", "response", "output"):
            text = _extract_text(payload.get(key))
            if text:
                return text
        for key in ("messages", "results", "choices"):
            text = _extract_text(payload.get(key))
            if text:
                return text
    return ""


def augment_guidance_with_memgpt(*, brand: str, platform: str, local_guidance: str) -> str:
    """Returns local guidance, optionally enriched by a MemGPT endpoint."""
    if not settings.memgpt_base_url or not settings.memgpt_agent_id:
        return local_guidance

    base = settings.memgpt_base_url.rstrip("/")
    url = f"{base}/v1/agents/{settings.memgpt_agent_id}/messages"
    prompt = (
        "Return concise memory guidance for this marketing generation. "
        "Only include concrete do/don't points relevant to brand/platform.\n\n"
        f"Brand: {brand}\nPlatform: {platform}\nLocal guidance: {local_guidance or '(none)'}"
    )
    body = {"messages": [{"role": "user", "content": prompt}]}

    try:
        response = httpx.post(url, json=body, timeout=settings.memgpt_timeout_seconds)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        log.warning("MemGPT guidance unavailable (%s)", exc)
        return local_guidance

    memgpt_guidance = _extract_text(data)
    if not memgpt_guidance:
        try:
            memgpt_guidance = json.dumps(data)[:400]
        except Exception:
            memgpt_guidance = ""
    memgpt_guidance = memgpt_guidance.strip()
    if not memgpt_guidance:
        return local_guidance

    block = f"ADDITIONAL GUIDANCE (MemGPT): {memgpt_guidance}"
    return f"{local_guidance}\n\n{block}" if local_guidance else block

