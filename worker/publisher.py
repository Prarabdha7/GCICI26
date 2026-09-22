"""Publishing providers, swapped on whichever key is configured.

Mirrors the provider pattern in app/agents/providers.py (Phase 5): the worker
never hardcodes Buffer or Ayrshare — it asks get_publisher() for whichever one
is active.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.db.models import ContentQueue


class PublisherError(RuntimeError):
    """Raised when no publisher is configured or a publish call fails."""


class BasePublisher(ABC):
    @abstractmethod
    def publish(self, item: ContentQueue) -> str:
        """Publishes one approved row and returns the provider's post id."""


def _public_media_url(item: ContentQueue) -> str | None:
    """media_path is a local filesystem path; the posting API needs a URL it
    can fetch. Without PUBLIC_MEDIA_BASE_URL configured, media is skipped."""
    if not item.media_path or not settings.public_media_base_url:
        return None
    return f"{settings.public_media_base_url.rstrip('/')}/{Path(item.media_path).name}"


class BufferPublisher(BasePublisher):
    """Buffer's GraphQL createPost mutation."""

    API_URL = "https://graph.buffer.com"

    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token if access_token is not None else settings.buffer_access_token

    def publish(self, item: ContentQueue) -> str:
        if not self.access_token:
            raise PublisherError("BUFFER_ACCESS_TOKEN is not set.")

        variables: dict[str, Any] = {
            "input": {"text": item.final_content or item.draft_content, "channelId": item.platform}
        }
        media_url = _public_media_url(item)
        if media_url:
            variables["input"]["media"] = [{"url": media_url}]

        response = httpx.post(
            self.API_URL,
            headers={"Authorization": f"Bearer {self.access_token}"},
            json={
                "query": "mutation CreatePost($input: CreatePostInput!) { createPost(input: $input) { id } }",
                "variables": variables,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("errors"):
            raise PublisherError(f"Buffer publish failed: {data['errors']}")
        return data["data"]["createPost"]["id"]


class AyrsharePublisher(BasePublisher):
    """Ayrshare's /api/post endpoint."""

    API_URL = "https://app.ayrshare.com/api/post"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.ayrshare_api_key

    def publish(self, item: ContentQueue) -> str:
        if not self.api_key:
            raise PublisherError("AYRSHARE_API_KEY is not set.")

        payload: dict[str, Any] = {
            "post": item.final_content or item.draft_content, "platforms": [item.platform]
        }
        media_url = _public_media_url(item)
        if media_url:
            payload["mediaUrls"] = [media_url]

        response = httpx.post(
            self.API_URL, headers={"Authorization": f"Bearer {self.api_key}"}, json=payload, timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        post_ids = data.get("postIds") or []
        if not post_ids:
            raise PublisherError(f"Ayrshare publish failed: {data}")
        return post_ids[0]["id"]


def get_publisher() -> BasePublisher:
    if settings.buffer_access_token:
        return BufferPublisher()
    if settings.ayrshare_api_key:
        return AyrsharePublisher()
    raise PublisherError("No publisher configured: set BUFFER_ACCESS_TOKEN or AYRSHARE_API_KEY.")
