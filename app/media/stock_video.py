"""Free stock-footage fallback for video assembly: the Pexels Video API.

    script -> _extract_keyword() -> Pexels search -> download -> real .mp4

Used by app.media.assembly.assemble_video() as a middle tier between Veo
(real generative video, tried first) and the brand-tinted ColorClip (the
final, always-available safety net). Optional: without PEXELS_API_KEY set,
fetch_stock_video() raises ProviderError and the caller falls through to
the ColorClip, exactly like every other swappable provider in this repo
(app/agents/providers.py, worker/publisher.py) when its key is absent.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
import uuid

import httpx

from app.agents.providers import ProviderError
from app.config import settings

log = logging.getLogger(__name__)

SEARCH_URL = "https://api.pexels.com/videos/search"

_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "this",
    "that",
    "your",
    "you",
    "our",
    "we",
    "it",
    "not",
    "as",
    "by",
    "from",
    "its",
    "has",
    "have",
    "will",
    "can",
    "any",
    "into",
    "than",
    "their",
    "them",
    "just",
    "get",
    "now",
    "today",
    "more",
    "never",
    "every",
    "always",
    "terms",
    "apply",
}


def extract_keyword(script: str, *, fallback: str) -> str:
    """Pulls a 2-3 word visual search term out of a generated script — the
    first couple of distinct, meaningful (non-stopword) words, in the order
    they appear. Deterministic, no LLM call: this only needs to be good
    enough to point Pexels at a relevant category, not a perfect summary."""
    words = re.findall(r"[A-Za-z]{4,}", (script or "").lower())
    content_words = [w for w in words if w not in _STOPWORDS]
    seen: list[str] = []
    for w in content_words:
        if w not in seen:
            seen.append(w)
        if len(seen) == 3:
            break
    return " ".join(seen) if seen else fallback


def fetch_stock_video(keyword: str, *, output_dir: Path) -> Path:
    """Searches Pexels for `keyword` and downloads the first result to disk.
    Raises ProviderError (no key, no results, network failure) — callers
    decide what to fall back to, same contract as every other provider."""
    if not settings.pexels_api_key:
        raise ProviderError("PEXELS_API_KEY is not set.")

    try:
        response = httpx.get(
            SEARCH_URL,
            headers={"Authorization": settings.pexels_api_key},
            params={"query": keyword, "per_page": 1, "orientation": "portrait"},
            timeout=20.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ProviderError(f"Pexels search failed: {exc}") from exc

    videos = (response.json() or {}).get("videos") or []
    if not videos:
        raise ProviderError(f"Pexels returned no videos for {keyword!r}.")

    files = videos[0].get("video_files") or []
    if not files:
        raise ProviderError(f"Pexels result for {keyword!r} has no video files.")
    # Prefer a modest resolution — this is a background clip trimmed and
    # composited under captions, not the hero asset; keeps downloads fast.
    sized = [f for f in files if (f.get("width") or 0) >= 480]
    video_url = (sized or files)[0].get("link")
    if not video_url:
        raise ProviderError(f"Pexels result for {keyword!r} has no downloadable link.")

    try:
        video_response = httpx.get(video_url, timeout=45.0, follow_redirects=True)
        video_response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ProviderError(f"Pexels video download failed: {exc}") from exc
    if not video_response.content:
        raise ProviderError("Pexels returned an empty video file.")

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"stock_{uuid.uuid4().hex[:12]}.mp4"
    path.write_bytes(video_response.content)
    log.info("fetch_stock_video keyword=%r wrote %s (%d bytes)", keyword, path, len(video_response.content))
    return path
