"""Newsjacking intel sweep: periodic competitor research (no auto-publish).

Runs research_node per brand/niche and persists each digest to the
intel_digests table (brief item 1: periodic digest). Manual trigger lives at
POST /dashboard/newsjack which turns the latest digest into a campaign topic.
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
    from app.config import settings
    from app.db.database import session_scope
    from app.db.models import IntelDigest

    results = []
    with session_scope() as db:
        for target in SWEEP_TARGETS:
            try:
                out = research_node({"brand": target["brand"], "niche": target["niche"], "country": target["country"]})
                digest = out.get("research_notes", "")
            except Exception as exc:
                digest = ""
                log.warning("intel sweep failed for %s/%s: %s", target["brand"], target["country"], exc)
            row = IntelDigest(
                brand=target["brand"], niche=target["niche"], country=target["country"],
                digest_text=(digest or "")[:2000], is_demo=settings.demo_mode,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            log.info("intel sweep %s/%s: row=%s chars=%s", target["brand"], target["country"], row.id, len(row.digest_text))
            results.append({**target, "digest": row.digest_text, "digest_id": row.id})
    return results


def latest_digests(db, *, limit_per_brand: int = 1) -> list[dict]:
    """Newest digest per (brand, country), real rows first, demo-labeled."""
    from sqlalchemy import select

    from app.db.models import IntelDigest

    rows = list(db.scalars(select(IntelDigest).order_by(IntelDigest.created_at.desc(), IntelDigest.id.desc()).limit(200)))
    seen: set[tuple[str, str]] = set()
    out = []
    for row in rows:
        key = (row.brand, row.country)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "id": row.id, "brand": row.brand, "niche": row.niche, "country": row.country,
            "digest_text": row.digest_text, "is_demo": row.is_demo,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })
        if len(out) >= limit_per_brand * len(SWEEP_TARGETS):
            break
    return out


def newsjack_topic(brand: str, niche: str, country: str) -> str:
    """Run research once and return a topic string for campaign generation."""
    from app.agents.research import research_node

    out = research_node({"brand": brand, "niche": niche, "country": country})
    digest = (out.get("research_notes") or "").strip().replace("\n", " ")
    return digest[:220] or f"{niche} update in {country}"
