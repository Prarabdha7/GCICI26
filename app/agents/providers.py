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
        self.api_key = api_key or settings.tavily_api_key

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
        self.api_key = api_key or settings.serper_api_key

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
        self.api_key = api_key or settings.google_places_api_key

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
        self.api_key = api_key or settings.scrapegraph_api_key

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
    key = api_key or settings.hunter_api_key
    if not key:
        raise ProviderError("HUNTER_API_KEY is not set.")
    response = httpx.get(
        "https://api.hunter.io/v2/domain-search",
        params={"domain": domain, "api_key": key},
        timeout=20.0,
    )
    response.raise_for_status()
    return response.json().get("data", {}).get("emails", [])
