"""Provider-agnostic LLM client.

Every LLM call in this project goes through here — nodes never import a vendor
SDK directly.  That keeps the graph readable and lets the provider be swapped
with one environment variable.

Two entry points:

    text_call(...)        -> str    free-form generation
    structured_call(...)  -> dict   schema-enforced JSON, used by the compliance gate

Structured output is enforced at the API level (Gemini `response_schema`,
OpenAI `json_schema`), never by asking the model politely for JSON.

SDKs are imported lazily so the app boots without every provider installed.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when a provider call fails or returns an unusable payload."""


# The contract the compliance gate must satisfy. Any other shape is a hard
# failure — never salvage a malformed verdict with a regex.
COMPLIANCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_compliant": {"type": "boolean"},
        "violations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["is_compliant", "violations"],
}


def _resolve(provider: str | None) -> str:
    return (provider or settings.llm_provider).lower()


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def text_call(
    *,
    system: str,
    user: str,
    temperature: float | None = None,
    provider: str | None = None,
) -> str:
    """Free-form generation. Used by the content, research and localisation nodes."""
    temp = settings.llm_temperature if temperature is None else temperature
    name = _resolve(provider)
    if name == "gemini":
        return _gemini(system=system, user=user, temperature=temp, schema=None)
    if name == "openai":
        return _openai(system=system, user=user, temperature=temp, schema=None)
    raise LLMError(f"Unknown LLM_PROVIDER: {name!r}")


def image_call(
    *,
    prompt: str,
    provider: str | None = None,
) -> bytes:
    """Generates a single image from a text prompt. Returns raw image bytes.
    Used by app.media.image_gen for Instagram-visual posts/carousels.

    Gemini's native image-output models are billing-gated on the free tier
    (confirmed live: 429 RESOURCE_EXHAUSTED, limit=0, on every image model
    this key can see). Rather than fail the whole pipeline over that, this
    falls back to Pollinations' keyless image API — a real, live, free
    generation call, not a fabricated placeholder — the same pattern this
    project already uses for research (DuckDuckGo + Crawl4AI instead of a
    paid search key)."""
    name = _resolve(provider)
    if name != "gemini":
        raise LLMError(f"Image generation not supported for LLM_PROVIDER: {name!r}")
    try:
        return _gemini_image(prompt=prompt)
    except LLMError as exc:
        log.warning("Gemini image generation unavailable (%s) — falling back to Pollinations (keyless, free)", exc)
        return _pollinations_image(prompt=prompt)


def video_call(
    *,
    prompt: str,
    duration_seconds: int = 6,
    provider: str | None = None,
) -> bytes:
    """Generates a short video from a text prompt. Returns raw MP4 bytes.
    Used by app.media.assembly as the primary (Veo) path; a failure here is
    expected to fall back to the zero-cost edge-tts + moviepy assembly, not
    to crash the pipeline."""
    name = _resolve(provider)
    if name == "gemini":
        return _gemini_video(prompt=prompt, duration_seconds=duration_seconds)
    raise LLMError(f"Video generation not supported for LLM_PROVIDER: {name!r}")


def structured_call(
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    temperature: float | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """Schema-enforced JSON generation. Used by the compliance gate."""
    temp = settings.compliance_temperature if temperature is None else temperature
    name = _resolve(provider)
    if name == "gemini":
        raw = _gemini(system=system, user=user, temperature=temp, schema=schema)
    elif name == "openai":
        raw = _openai(system=system, user=user, temperature=temp, schema=schema)
    else:
        raise LLMError(f"Unknown LLM_PROVIDER: {name!r}")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Provider returned non-JSON despite schema enforcement: {raw[:400]!r}") from exc

    if not isinstance(parsed, dict):
        raise LLMError(f"Expected a JSON object, got {type(parsed).__name__}")
    return parsed


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #


def _gemini(*, system: str, user: str, temperature: float, schema: dict[str, Any] | None) -> str:
    if not settings.gemini_api_key:
        raise LLMError("GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover
        raise LLMError("google-genai is not installed. pip install -r requirements.txt") from exc

    client = genai.Client(api_key=settings.gemini_api_key)
    config: dict[str, Any] = {"system_instruction": system, "temperature": temperature}
    if schema is not None:
        config["response_mime_type"] = "application/json"
        config["response_schema"] = schema

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=user,
            config=types.GenerateContentConfig(**config),
        )
    except Exception as exc:  # pragma: no cover - network path
        raise LLMError(f"Gemini call failed: {exc}") from exc

    text = (response.text or "").strip()
    if not text:
        raise LLMError("Gemini returned an empty response.")
    return text


def _gemini_image(*, prompt: str) -> bytes:
    """Uses generate_content with an image-output model (gemini-*-image), not
    the separate Imagen generate_images API: that method is Enterprise-only
    ("This method is only supported in Gemini Enterprise Agent Platform mode,
    not in Gemini Developer API mode") on an AI-Studio key, confirmed live
    against this project's key. generate_content + inline_data is the current
    Developer-API-compatible path Google's own SDK deprecation notice points
    to (see the ExperimentalWarning on generate_images)."""
    if not settings.gemini_api_key:
        raise LLMError("GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in.")
    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover
        raise LLMError("google-genai is not installed. pip install -r requirements.txt") from exc

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        response = client.models.generate_content(model=settings.gemini_image_model, contents=prompt)
    except Exception as exc:  # pragma: no cover - network path
        raise LLMError(f"Gemini image call failed: {exc}") from exc

    candidates = getattr(response, "candidates", None) or []
    image_bytes = None
    for candidate in candidates:
        for part in getattr(candidate.content, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            if inline is not None and inline.data:
                image_bytes = inline.data
                break
        if image_bytes:
            break
    if not image_bytes:
        raise LLMError("Gemini returned no image data.")
    return image_bytes


def _pollinations_image(*, prompt: str) -> bytes:
    """Keyless, free image generation — no account, no billing. Confirmed
    live: GET returns a real image/jpeg body."""
    import urllib.parse

    import httpx

    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
    try:
        response = httpx.get(url, timeout=45.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMError(f"Pollinations image call failed: {exc}") from exc
    if not response.content:
        raise LLMError("Pollinations returned an empty image.")
    return response.content


def _gemini_video(*, prompt: str, duration_seconds: int) -> bytes:
    """Veo is a long-running operation: submit, poll client.operations.get()
    until done, then download the result's bytes via client.files.download().
    generate_videos(prompt=...) is deprecated in favor of source=; using the
    non-deprecated shape here."""
    if not settings.gemini_api_key:
        raise LLMError("GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover
        raise LLMError("google-genai is not installed. pip install -r requirements.txt") from exc

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        operation = client.models.generate_videos(
            model=settings.gemini_video_model,
            source=types.GenerateVideosSource(prompt=prompt),
            config=types.GenerateVideosConfig(number_of_videos=1, duration_seconds=duration_seconds),
        )
    except Exception as exc:  # pragma: no cover - network path
        raise LLMError(f"Veo call failed: {exc}") from exc

    deadline = time.monotonic() + settings.veo_timeout_seconds
    while not operation.done:
        if time.monotonic() > deadline:
            raise LLMError(f"Veo generation timed out after {settings.veo_timeout_seconds}s.")
        time.sleep(settings.veo_poll_interval_seconds)
        try:
            operation = client.operations.get(operation)
        except Exception as exc:  # pragma: no cover - network path
            raise LLMError(f"Veo polling failed: {exc}") from exc

    if operation.error:
        raise LLMError(f"Veo generation failed: {operation.error}")

    generated = getattr(operation.result, "generated_videos", None) or []
    if not generated:
        raise LLMError("Veo returned no video data.")

    try:
        video_bytes = client.files.download(file=generated[0].video)
    except Exception as exc:  # pragma: no cover - network path
        raise LLMError(f"Veo video download failed: {exc}") from exc
    if not video_bytes:
        raise LLMError("Veo returned an empty video.")
    return video_bytes


def _openai(*, system: str, user: str, temperature: float, schema: dict[str, Any] | None) -> str:
    if not settings.openai_api_key:
        raise LLMError("OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in.")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise LLMError("openai is not installed. pip install -r requirements.txt") from exc

    client = OpenAI(api_key=settings.openai_api_key)
    kwargs: dict[str, Any] = {
        "model": settings.openai_model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "structured_output",
                "strict": True,
                "schema": {**schema, "additionalProperties": False},
            },
        }

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:  # pragma: no cover - network path
        raise LLMError(f"OpenAI call failed: {exc}") from exc

    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise LLMError("OpenAI returned an empty response.")
    return text
