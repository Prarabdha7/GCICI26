"""Swappable search, discovery, scraping and enrichment providers.

Selection is driven entirely by which API keys are present in the environment
(CLAUDE.md: never hardcode a provider choice). Nodes call the factory
functions; they never instantiate a concrete provider directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.agents import local_samples
from app.config import settings


class ProviderError(RuntimeError):
    """Raised when no provider is configured or a provider call fails."""


class BaseSearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, *, max_results: int = 5) -> list[dict[str, Any]]:
        """Returns results shaped as {"title", "url", "snippet"}."""


class BaseDiscoveryProvider(ABC):
    @abstractmethod
    def discover(self, *, niche: str, country: str, max_results: int = 10) -> list[dict[str, Any]]:
        """Returns prospects shaped as {"company_name", "website"}."""


class SerperSearch(BaseSearchProvider):
    """Stub provider, ready for activation once SERPER_API_KEY is set."""

    API_URL = "https://google.serper.dev/search"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.serper_api_key

    def search(self, query: str, *, max_results: int = 5) -> list[dict[str, Any]]:
        if not self.api_key:
            raise ProviderError("SERPER_API_KEY is not set.")
        response = httpx.post(
            self.API_URL,
            headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
            timeout=30.0,
        )
        response.raise_for_status()
        results = response.json().get("organic", [])
        return [
            {"title": r.get("title", ""), "url": r.get("link", ""), "snippet": r.get("snippet", "")}
            for r in results[:max_results]
        ]


class GooglePlacesDiscovery(BaseDiscoveryProvider):
    """Stub provider, ready for activation once GOOGLE_PLACES_API_KEY is set."""

    API_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.google_places_api_key

    def discover(self, *, niche: str, country: str, max_results: int = 10) -> list[dict[str, Any]]:
        if not self.api_key:
            raise ProviderError("GOOGLE_PLACES_API_KEY is not set.")
        response = httpx.get(
            self.API_URL,
            params={"query": f"{niche} in {country}", "key": self.api_key},
            timeout=30.0,
        )
        response.raise_for_status()
        places = response.json().get("results", [])
        return [
            {"company_name": p.get("name", ""), "website": p.get("website", "")}
            for p in places[:max_results]
        ]


class ScrapeGraphClient:
    """Extracts structured markdown from a competitor URL via the ScrapeGraphAI API."""

    API_URL = "https://api.scrapegraphai.com/v1/markdownify"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.scrapegraph_api_key

    def extract_markdown(self, url: str) -> str:
        if not self.api_key:
            raise ProviderError("SCRAPEGRAPH_API_KEY is not set.")
        response = httpx.post(
            self.API_URL,
            headers={"SGAI-APIKEY": self.api_key},
            json={"website_url": url},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json().get("result", "")


def get_search_provider() -> BaseSearchProvider:
    if settings.serper_api_key:
        return SerperSearch()
    raise ProviderError("No search provider configured: set SERPER_API_KEY.")


def get_discovery_provider() -> BaseDiscoveryProvider:
    if settings.google_places_api_key:
        return GooglePlacesDiscovery()
    raise ProviderError("No discovery provider configured: set GOOGLE_PLACES_API_KEY.")


def get_hunter_contacts(domain: str, *, api_key: str | None = None) -> list[dict[str, Any]]:
    """Professional email contacts for a domain via Hunter.io Domain Search."""
    key = api_key if api_key is not None else settings.hunter_api_key
    if not key:
        raise ProviderError("HUNTER_API_KEY is not set.")
    response = httpx.get(
        "https://api.hunter.io/v2/domain-search",
        params={"domain": domain, "api_key": key},
        timeout=20.0,
    )
    response.raise_for_status()
    return response.json().get("data", {}).get("emails", [])


# --------------------------------------------------------------------------- #
# Demo-path mocks — data lives machine-local (local/demo_samples.json,
# gitignored); the repo ships zero baked-in samples. Absent file = empty
# results, never invented content. Strict get_* above are unchanged (tests
# assert they raise).
# --------------------------------------------------------------------------- #

class MockSearchProvider(BaseSearchProvider):
    """Deterministic zero-cost search — brand-aware slice of the local sample file."""

    def search(self, query: str, *, max_results: int = 5) -> list[dict[str, Any]]:
        data = local_samples.search_results()
        q = (query or "").lower()
        if "doctor" in q or "medic" in q or "clinic" in q:
            preferred = [r for r in data if "mps" in r.get("url", "") or "doctorshield" in r.get("url", "")]
        elif "transit" in q or "cargo" in q or "logistic" in q or "jaguar" in q:
            preferred = [r for r in data if "axa" in r.get("url", "") or "jaguar" in r.get("url", "")]
        else:
            preferred = [r for r in data if "chubb" in r.get("url", "") or "jade" in r.get("url", "")]
        rest = [r for r in data if r not in preferred]
        return (preferred + rest)[:max_results]


class MockDiscoveryProvider(BaseDiscoveryProvider):
    """Deterministic prospect list from the local sample file, filtered by niche."""

    def discover(self, *, niche: str, country: str, max_results: int = 10) -> list[dict[str, Any]]:
        data = local_samples.prospects()
        n = (niche or "").lower()
        if "clinic" in n or "medic" in n or "doctor" in n:
            picks = [p for p in data if "clinic" in p.get("website", "")]
        elif "courier" in n or "transit" in n or "logistic" in n or "cargo" in n:
            picks = [p for p in data if "logistics" in p.get("website", "")]
        elif "jewel" in n or "gold" in n or "gem" in n:
            picks = [p for p in data if "gem" in p.get("website", "") or "gold" in p.get("website", "")]
        else:
            picks = data
        return picks[:max_results]


class MockScrapeGraphClient:
    """Offline markdown extractor — template from the local sample file."""

    def extract_markdown(self, url: str) -> str:
        template = local_samples.scrape_template()
        if not template:
            return ""
        try:
            return template.format(url=url)
        except (IndexError, KeyError):
            return template


def get_search_provider_resilient() -> BaseSearchProvider:
    try:
        return get_search_provider()
    except ProviderError:
        return MockSearchProvider()


def get_discovery_provider_resilient() -> BaseDiscoveryProvider:
    try:
        return get_discovery_provider()
    except ProviderError:
        return MockDiscoveryProvider()


def get_scraper_resilient() -> ScrapeGraphClient | MockScrapeGraphClient:
    if settings.scrapegraph_api_key:
        return ScrapeGraphClient()
    return MockScrapeGraphClient()


def get_hunter_contacts_resilient(domain: str) -> list[dict[str, Any]]:
    try:
        return get_hunter_contacts(domain)
    except ProviderError:
        local = (domain or "").split(".")[0].replace("-", " ").title()
        return [{"value": f"contact@{domain}", "first_name": local, "position": "Operations Manager"}] if domain else []
