"""Newsjacking intel sweep: periodic competitor research (no auto-publish).

Runs research_node per brand/niche and logs digests. Manual trigger lives at
POST /dashboard/newsjack which turns the digest into a campaign topic.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

SWEEP_TARGETS = [
    {"brand": "Jade", "niche": "jewellers block", "country": "Singapore"},
    {"brand": "Jaguar Transit", "niche": "high-value cargo transit", "country": "Malaysia"},
    {"brand": "DoctorShield", "niche": "medical indemnity", "country": "Hong Kong"},
]


def intel_sweep() -> list[dict]:
    from app.agents.research import research_node

    results = []
    for target in SWEEP_TARGETS:
        try:
            out = research_node({"brand": target["brand"], "niche": target["niche"], "country": target["country"]})
            digest = out.get("research_notes", "")[:500]
        except Exception as exc:
            digest = f"sweep failed: {exc}"
        log.info("intel sweep %s/%s: %s", target["brand"], target["country"], digest[:120])
        results.append({**target, "digest": digest})
    return results


def newsjack_topic(brand: str, niche: str, country: str) -> str:
    """Run research once and return a topic string for campaign generation."""
    from app.agents.research import research_node

    out = research_node({"brand": brand, "niche": niche, "country": country})
    digest = (out.get("research_notes") or "").strip().replace("\n", " ")
    return digest[:220] or f"{niche} update in {country}"
