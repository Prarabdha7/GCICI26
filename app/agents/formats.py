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
    """Synthetic pre-publication panel — DEMO ONLY, always labeled as personas."""
    b = (brand or "").lower()
    notes = []
    if "doctor" in b or "shield" in b:
        notes.append("[DEMO persona] Dr. Kevin Lim (surgeon): avoid 'malpractice', say 'inquiry/defence'; keep peer tone.")
    else:
        notes.append("[DEMO persona] Dr. Kevin Lim: n/a for non-medical brand.")
    if "jade" in b:
        notes.append("[DEMO persona] Madam Chen (goldsmith): demand memo-goods + discretion wording; no safe-grade details.")
    else:
        notes.append("[DEMO persona] Madam Chen: discretion angle added.")
    if "jaguar" in b or "transit" in b:
        notes.append("[DEMO persona] Marcus Tan (freight): demand chain-of-custody + telematics terms.")
    else:
        notes.append("[DEMO persona] Marcus Tan: transit terms n/a.")
    if "guarantee" in (draft or "").lower():
        notes.append("[DEMO persona] Panel flag: absolute guarantee language — must soften before human review.")
    return notes


def build_format_pack(draft: str, brand: str, platform: str = "linkedin") -> dict:
    """Try LLM JSON pack, fall back offline. Always returns full schema."""
    try:
        from app.llm.client import structured_call

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
