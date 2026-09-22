"""Feedback memory read path — retrieves recent rejections and formats the CRITICAL GUIDANCE block.

This module is the read side of the closed-loop learning system.  It is called
by ``app.graph.nodes.content_node`` at the start of every content generation
pass, before the LLM system prompt is assembled.

Injection contract (referenced in CLAUDE.md section 5):
    - The formatted string starts with ``"CRITICAL GUIDANCE: Previously, human
      reviewers rejected content for this brand due to: "``.
    - If no feedback rows exist for the brand/platform pair, an empty string is
      returned and nothing is prepended to the system prompt.  A placeholder
      block is never emitted because injecting boilerplate into an empty state
      wastes tokens and misleads the model.
    - The depth of the lookup window is controlled by
      ``settings.feedback_memory_limit`` (default: 5 rows).

The complementary write side lives in ``app.memory.store``.
"""


from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import FeedbackMemory


def get_recent_feedback(
    db: Session, *, brand: str, platform: str, limit: int | None = None
) -> list[FeedbackMemory]:
    """Retrieve the most recent feedback rows for a brand/platform pair, newest first.

    Executes a filtered, ordered, and limited SELECT against the
    ``feedback_memory`` table.  The query is intentionally narrow — only brand
    and platform are filtered — because human reviewers do not always tag the
    exact topic, and broader context (e.g. repeated tone violations) applies
    across all topics for a given channel.

    Args:
        db: An active SQLAlchemy ``Session``.
        brand: Brand display name to filter by (exact string match).
        platform: Social channel identifier to filter by (exact string match).
        limit: Maximum number of rows to return.  Defaults to
            ``settings.feedback_memory_limit`` (configured in ``.env``,
            typically 5) so the system prompt injection stays within token
            budget.

    Returns:
        A list of ``FeedbackMemory`` ORM instances ordered by ``timestamp``
        descending (newest first).  Returns an empty list if no matching rows
        exist.
    """
    stmt = (
        select(FeedbackMemory)
        .where(FeedbackMemory.brand == brand, FeedbackMemory.platform == platform)
        .order_by(FeedbackMemory.timestamp.desc())
        .limit(limit or settings.feedback_memory_limit)
    )
    return list(db.execute(stmt).scalars())


def format_guidance(entries: list[FeedbackMemory]) -> str:
    """Format a list of feedback rows into the CRITICAL GUIDANCE injection block.

    The injection contract is defined in CLAUDE.md section 5.  The key rules
    are:
        - If ``entries`` is empty, return ``""`` — never inject a placeholder.
        - The prefix ``"CRITICAL GUIDANCE: Previously, human reviewers rejected
          content for this brand due to: "`` must begin the string exactly as
          written so downstream code can detect guidance presence with
          ``"CRITICAL GUIDANCE" in system``.
        - Individual entries are joined with ``"; "`` to keep the injection on
          one logical sentence without list-style line breaks that consume
          token budget.

    Args:
        entries: Ordered list of ``FeedbackMemory`` rows, typically from
            ``get_recent_feedback``.  May be empty.

    Returns:
        A formatted guidance string ready to prepend to a system prompt, or
        an empty string when ``entries`` is empty.
    """
    if not entries:
        return ""
    notes = "; ".join(f"{entry.error_tag}: {entry.human_note}" for entry in entries)
    return (
        "CRITICAL GUIDANCE: Previously, human reviewers rejected content for "
        f"this brand due to: {notes}. You MUST NOT repeat these mistakes."
    )

