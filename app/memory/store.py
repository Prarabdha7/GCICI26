"""Feedback memory write path — records every human rejection or edit into the database.

This module is the write side of the closed-loop learning system.  It is
called by the API action endpoints (``app.api.actions``) whenever a reviewer
rejects a content queue row or submits a free-text edit note.

The complementary read side lives in ``app.memory.retrieval``, which queries
the most recent rows here and formats them into a ``CRITICAL GUIDANCE:``
injection block that the content generation node prepends to its system prompt.

The pair of modules constitutes the Tier-2 episodic memory layer described in
the architecture: short-term human feedback is durable across server restarts
and gradually shapes generated content toward brand-compliant output.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import FeedbackMemory


def create_feedback_entry(
    db: Session,
    *,
    brand: str,
    platform: str,
    error_tag: str,
    human_note: str,
    content_id: int | None = None,
) -> FeedbackMemory:
    """Persist a single feedback rejection or edit note to the database.

    Constructs a ``FeedbackMemory`` ORM row, adds it to the session, commits,
    and refreshes the instance so that server-generated fields (``id``,
    ``timestamp``) are populated on the returned object.

    The ``is_demo`` field is intentionally left at its default (``False``).
    Demo seed rows are written directly by ``scripts.seed_demo`` with
    ``is_demo=True`` so that production analytics queries can exclude them
    with a ``WHERE is_demo = 0`` filter.

    Args:
        db: An active SQLAlchemy ``Session`` obtained from
            ``app.db.database.get_db`` or equivalent.
        brand: Brand display name (e.g. ``"Jade"``, ``"Jaguar Transit"``).
            Stored as-is; lookup in ``retrieval.get_recent_feedback`` must use
            the same casing.
        platform: Social channel identifier (e.g. ``"linkedin"``, ``"instagram"``).
        error_tag: Controlled rejection category from ``ErrorTag`` enum values
            (e.g. ``"too_salesy"``, ``"compliance_risk"``).
        human_note: Free-text reviewer note describing the specific problem.
            This string is injected verbatim into the next generation's system
            prompt via ``format_guidance``.
        content_id: Optional foreign key referencing the ``ContentQueue`` row
            that was rejected.  Enables rejection-rate analytics linking a
            feedback note back to the original generated asset.

    Returns:
        The committed and refreshed ``FeedbackMemory`` instance with its
        database-assigned ``id`` and ``timestamp`` populated.
    """
    row = FeedbackMemory(
        brand=brand,
        platform=platform,
        error_tag=error_tag,
        human_note=human_note,
        content_id=content_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
