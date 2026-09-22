"""Multi-format pack: one idea -> linkedin + thread + carousel + video script + A/B.

LLM JSON when available; otherwise a deterministic offline builder that only
reformats the ACTUAL draft (sentence splits) — never invents new claims.
The synthetic focus-group panel is demo-only (DEMO_MODE=true) and labeled.
"""

from __future__ import annotations

import json
import logging

log = logging.getLogger(__name__)

PACK_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "linkedin": {"type": "string"},
        "thread": {"type": "array", "items": {"type": "string"}},
        "carousel": {"type": "array", "items": {"type": "string"}},
        "video_script": {"type": "string"},
        "variant_a": {"type": "string"},
        "variant_b": {"type": "string"},
    },
    "required": ["linkedin", "thread", "carousel", "video_script", "variant_a", "variant_b"],
}


def _offline_pack(draft: str, brand: str) -> dict:
    from app.config import settings as _settings

    base = (draft or "").strip() or f"{brand} protection update. Terms apply."
    sentences = [s.strip() for s in base.replace("\n", " ").split(". ") if s.strip()][:6]
    while len(sentences) < 5:
        sentences.append(f"{brand} cover detail {len(sentences) + 1}. Terms apply.")
    thread = [f"{i + 1}/ {s[:240]}" for i, s in enumerate(sentences[:5])]
    carousel = [
        f"Slide {i + 1}: {s[:120]}" for i, s in enumerate(sentences[:5])
    ]
    return {
        "linkedin": base[:900],
        "thread": thread,
        "carousel": carousel,
        "video_script": f"Hook: {sentences[0][:120]} Body: {' '.join(sentences[1:3])[:300]} CTA: Talk to JA Assure. Terms apply.",
        "variant_a": f"{base[:500]} [A: heritage angle]",
        "variant_b": f"{base[:500]} [B: risk-control angle]",
        "focus_group": focus_group_notes(base, brand) if _settings.demo_mode else [],
    }


def focus_group_notes(draft: str, brand: str) -> list[str]:
    """Synthetic pre-publication panel — DEMO ONLY, personas load machine-local
    (local/demo_samples.json) and every note is labeled. Absent file = no
    personas, never invented opinions."""
    from app.agents import local_samples

    panels = local_samples.personas()
    b = (brand or "").lower()
    notes: list[str] = []
    for key in ("doctor", "goldsmith", "freight"):
        panel = panels.get(key, {})
        matches = panel.get("match", []) if isinstance(panel, dict) else []
        specific = panel.get("specific") if isinstance(panel, dict) else None
        fallback = panel.get("na") if isinstance(panel, dict) else None
        if specific and any(m in b for m in matches):
            notes.append(specific)
        elif fallback:
            notes.append(fallback)
    flag = panels.get("guarantee_flag") if isinstance(panels, dict) else None
    if flag and "guarantee" in (draft or "").lower():
        notes.append(flag)
    return notes


def build_format_pack(draft: str, brand: str, platform: str = "linkedin") -> dict:
    """Try LLM JSON pack, fall back offline. Always returns full schema."""
    try:
        from app.llm.client import LLMError, structured_call

        system = (
            f"You are the repurposing agent for {brand}. Turn one draft into a multi-format pack. "
            "Return only JSON matching the schema: linkedin (post), thread (5 x posts), "
            "carousel (5 slide texts), video_script (60s), variant_a, variant_b."
        )
        user = f"Platform: {platform}\nDraft:\n{draft[:2000]}"
        verdict = structured_call(system=system, user=user, schema=PACK_SCHEMA)
        # normalize
        pack = _offline_pack(draft, brand)
        for k in pack:
            if verdict.get(k):
                pack[k] = verdict[k]
        return pack
    except Exception as exc:
        log.warning("format pack LLM unavailable (%s) — offline builder", exc)
        return _offline_pack(draft, brand)


def pack_to_json(pack: dict) -> str:
    return json.dumps(pack, ensure_ascii=False)


def pack_from_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}
