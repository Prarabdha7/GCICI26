"""Swappable search, discovery, scraping and enrichment providers.

Selection is driven entirely by which API keys are present in the environment
(CLAUDE.md: never hardcode a provider choice). Nodes call the factory
functions; they never instantiate a concrete provider directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

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


class TavilySearch(BaseSearchProvider):
    """Active default search provider."""

    API_URL = "https://api.tavily.com/search"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.tavily_api_key

    def search(self, query: str, *, max_results: int = 5) -> list[dict[str, Any]]:
        if not self.api_key:
            raise ProviderError("TAVILY_API_KEY is not set.")
        response = httpx.post(
            self.API_URL,
            json={"api_key": self.api_key, "query": query, "max_results": max_results},
            timeout=30.0,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")}
            for r in results
        ]


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


class TavilyDiscovery(BaseDiscoveryProvider):
    """Active default: finds niche prospects via the search provider."""

    def __init__(self, search_provider: BaseSearchProvider | None = None) -> None:
        self.search_provider = search_provider or TavilySearch()

    def discover(self, *, niche: str, country: str, max_results: int = 10) -> list[dict[str, Any]]:
        results = self.search_provider.search(f"{niche} companies in {country}", max_results=max_results)
        return [{"company_name": r["title"], "website": r["url"]} for r in results if r.get("url")]


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
    if settings.tavily_api_key:
        return TavilySearch()
    if settings.serper_api_key:
        return SerperSearch()
    raise ProviderError("No search provider configured: set TAVILY_API_KEY or SERPER_API_KEY.")


def get_discovery_provider() -> BaseDiscoveryProvider:
    if settings.tavily_api_key:
        return TavilyDiscovery()
    if settings.google_places_api_key:
        return GooglePlacesDiscovery()
    raise ProviderError("No discovery provider configured: set TAVILY_API_KEY or GOOGLE_PLACES_API_KEY.")


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
# Zero-key mocks — never change the strict get_* above (tests assert they raise).
# Callers try strict first, then fall back to these so demos never crash.
# --------------------------------------------------------------------------- #

MOCK_SEARCH_RESULTS: list[dict[str, Any]] = [
    {"title": "Chubb Jewellers Block — HK exhibition limits tightened", "url": "https://example.test/chubb-jade", "snippet": "Chubb/Lloyds syndicates now require 7-day pre-approval for off-premises memo goods; exhibition transit sub-limits cut 20%."},
    {"title": "MPS raises discretionary defence subscriptions 14%", "url": "https://example.test/mps-doctorshield", "snippet": "Medical Protection Society hikes aesthetic/ortho subscriptions; cover remains discretionary not contractual — doctors seek binding policies."},
    {"title": "AXA XL marine cargo excludes unattended-vehicle theft", "url": "https://example.test/axa-jaguar", "snippet": "Regional cargo insurers impose 48h reporting deadlines and unattended-vehicle exclusions; SME couriers struggle with manual claims."},
]

MOCK_PROSPECTS: list[dict[str, Any]] = [
    {"company_name": "Orchard Gem House", "website": "https://orchard-gem.test"},
    {"company_name": "KL Goldsmith Collective", "website": "https://kl-gold.test"},
    {"company_name": "Causeway Secure Logistics", "website": "https://causeway-logistics.test"},
    {"company_name": "Novena Specialist Clinic", "website": "https://novena-clinic.test"},
]


class MockSearchProvider(BaseSearchProvider):
    """Deterministic zero-cost search — brand-aware slice of MOCK_SEARCH_RESULTS."""

    def search(self, query: str, *, max_results: int = 5) -> list[dict[str, Any]]:
        q = (query or "").lower()
        if "doctor" in q or "medic" in q or "clinic" in q:
            preferred = [r for r in MOCK_SEARCH_RESULTS if "mps" in r["url"] or "doctorshield" in r["url"]]
        elif "transit" in q or "cargo" in q or "logistic" in q or "jaguar" in q:
            preferred = [r for r in MOCK_SEARCH_RESULTS if "axa" in r["url"] or "jaguar" in r["url"]]
        else:
            preferred = [r for r in MOCK_SEARCH_RESULTS if "chubb" in r["url"] or "jade" in r["url"]]
        rest = [r for r in MOCK_SEARCH_RESULTS if r not in preferred]
        return (preferred + rest)[:max_results]


class MockDiscoveryProvider(BaseDiscoveryProvider):
    """Deterministic prospect list filtered by niche keywords."""

    def discover(self, *, niche: str, country: str, max_results: int = 10) -> list[dict[str, Any]]:
        n = (niche or "").lower()
        if "clinic" in n or "medic" in n or "doctor" in n:
            picks = [p for p in MOCK_PROSPECTS if "clinic" in p["website"]]
        elif "courier" in n or "transit" in n or "logistic" in n or "cargo" in n:
            picks = [p for p in MOCK_PROSPECTS if "logistics" in p["website"]]
        elif "jewel" in n or "gold" in n or "gem" in n:
            picks = [p for p in MOCK_PROSPECTS if "gem" in p["website"] or "gold" in p["website"]]
        else:
            picks = MOCK_PROSPECTS
        return picks[:max_results]


class MockScrapeGraphClient:
    """Offline markdown extractor — returns canned competitor excerpts."""

    def extract_markdown(self, url: str) -> str:
        return f"# Competitor brief ({url})\n\nKey shift: tighter warranties, slower onboarding. Gap for JA Assure: instant memo / per-consignment bind + contractual wording. Source: cached zero-key digest."


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
