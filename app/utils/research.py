"""Shared, keyless research utility: DuckDuckGo search + Crawl4AI scraping.

Replaces the Tavily-based search path everywhere it was used (no API key,
no quota). DuckDuckGo's free backend is occasionally rate-limited and
returns zero results for a query that would normally succeed — retried a
few times, but callers must still tolerate an empty summary and degrade
gracefully (see app/agents/research.py's mock fallback).

Crawl4AI is imported lazily inside research_summary(), not at module level
(app/llm/client.py's convention): importing it eagerly has the side effect
of loading .env into the real process os.environ, which would leak secrets
into every test that merely imports this module.
"""

from __future__ import annotations

import asyncio
import logging

from duckduckgo_search import DDGS

log = logging.getLogger(__name__)

MAX_CHARS_PER_PAGE = 3000


def _search_urls(query: str, *, max_results: int, attempts: int) -> list[str]:
    for attempt in range(1, attempts + 1):
        try:
            results = DDGS().text(query, max_results=max_results)
        except Exception:
            log.exception("DuckDuckGo search failed for %r (attempt %s/%s)", query, attempt, attempts)
            continue
        urls = [r["href"] for r in results if r.get("href")]
        if urls:
            return urls
        log.warning("DuckDuckGo returned no results for %r (attempt %s/%s)", query, attempt, attempts)
    return []


async def research_summary(query: str, *, max_results: int = 2, attempts: int = 3) -> str:
    """Searches DuckDuckGo for `query`, scrapes the top `max_results` URLs
    with Crawl4AI, and returns a concatenated markdown summary. Returns ""
    if nothing could be found or scraped."""
    urls = await asyncio.to_thread(_search_urls, query, max_results=max_results, attempts=attempts)
    if not urls:
        return ""

    sections: list[str] = []
    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError:
        AsyncWebCrawler = None

    if AsyncWebCrawler is not None:
        async with AsyncWebCrawler() as crawler:
            for url in urls:
                try:
                    result = await crawler.arun(url=url)
                    markdown = str(result.markdown).strip()
                except Exception:
                    log.exception("Crawl4AI failed to scrape %s", url)
                    continue
                if markdown:
                    sections.append(f"### {url}\n{markdown[:MAX_CHARS_PER_PAGE]}")
    else:
        # Fallback to fast httpx + BeautifulSoup scraping
        import httpx
        from bs4 import BeautifulSoup
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for url in urls:
                try:
                    res = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                    if res.status_code == 200:
                        soup = BeautifulSoup(res.text, "html.parser")
                        for tag in soup(["script", "style", "nav", "footer"]):
                            tag.decompose()
                        text = soup.get_text(separator=" ", strip=True)
                        if text:
                            sections.append(f"### {url}\n{text[:MAX_CHARS_PER_PAGE]}")
                except Exception:
                    log.debug("HTTP fallback scrape skipped for %s", url)
                    continue

    return "\n\n".join(sections)
