"""LangGraph state for the marketing content pipeline.

A single TypedDict threaded through every node. See CLAUDE.md section 4 for
the full topology; this is the core slice Phase 2 operates on.
"""

from __future__ import annotations

from typing import TypedDict


class MarketingState(TypedDict):
    draft_content: str
    brand: str
    platform: str
    language: str
    compliance_errors: list[str]
    retry_count: int
