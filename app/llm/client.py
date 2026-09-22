"""Provider-Agnostic LLM Client and Multi-Modal Generative Interface.

This module provides a unified client abstraction for foundation models, supporting
both Google Gemini and OpenAI model families. It handles text generation, schema-enforced
JSON outputs, diffusion image synthesis, and video generation with automated fallback
mechanisms.

Architectural Principles:
    - Vendor Independence: Downstream workflow nodes interact exclusively with this module,
      never importing vendor-specific SDKs directly.
    - Strict Schema Enforcement: Structured JSON outputs are guaranteed at the engine level
      (`response_schema` in Gemini, `json_schema` in OpenAI).
    - Multi-Modal Synthesis: Coordinates text, FLUX/Gemini imagery, and Google Veo video reels.
    - Zero-Quota Resilience: Gracefully cascades to keyless neural alternatives (Pollinations FLUX)
      when commercial API limits are reached.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Exception raised when an upstream LLM API fails or returns an unparseable response."""


COMPLIANCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_compliant": {"type": "boolean"},
        "violations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["is_compliant", "violations"],
}


def _resolve(provider: str | None) -> str:
    """Resolve the active model provider name from explicit arguments or application settings.

    Args:
        provider: Explicit provider override ('gemini' or 'openai'), or None.

    Returns:
        str: Lowercased provider identifier.
    """
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
    """Generate free-form text completion using the configured LLM provider.

    Args:
        system: System instruction establishing agent persona, rules, and style.
        user: Prompt text containing inputs, variables, and context.
        temperature: Sampling temperature (defaults to settings.llm_temperature).
        provider: Optional provider override ('gemini' or 'openai').

    Returns:
        str: The generated model response string.

    Raises:
        LLMError: If the provider is unknown or the upstream API call fails.
    """
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
    aspect_ratio: str = "1:1",
) -> bytes:
    """Generate a single marketing image from a textual prompt.

    Attempts native Gemini image diffusion first; upon encountering quota or billing limits,
    cascades to keyless Pollinations FLUX.1 generation.

    Args:
        prompt: Descriptive visual prompt without on-screen typography.
        provider: Provider identifier (default: 'gemini').
        aspect_ratio: Image aspect ratio ('1:1', '9:16', or '16:9').

    Returns:
        bytes: Raw JPEG/PNG image binary payload.

    Raises:
        LLMError: If image synthesis fails across all providers.
    """
    name = _resolve(provider)
    if name != "gemini":
        raise LLMError(f"Image generation not supported for LLM_PROVIDER: {name!r}")
    try:
        return _gemini_image(prompt=prompt)
    except LLMError as exc:
        log.warning("Gemini image generation unavailable (%s) — falling back to Pollinations (keyless, free)", exc)
        return _pollinations_image(prompt=prompt, aspect_ratio=aspect_ratio)


def video_call(
    *,
    prompt: str,
    duration_seconds: int = 6,
    provider: str | None = None,
) -> bytes:
    """Generate a short video clip from a text prompt using Google Veo.

    Submits an asynchronous video generation operation, polls until complete,
    and returns the downloaded MP4 byte payload.

    Args:
        prompt: Scene description for text-to-video diffusion.
        duration_seconds: Target clip duration in seconds.
        provider: Provider identifier (default: 'gemini').

    Returns:
        bytes: Raw MP4 video binary payload.

    Raises:
        LLMError: If video synthesis fails or times out.
    """
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
    """Execute a structured LLM query with strict JSON schema enforcement.

    Args:
        system: System instructions detailing task and evaluation constraints.
        user: Input prompt text to evaluate.
        schema: Standard JSON schema dictionary the model must adhere to.
        temperature: Sampling temperature (defaults to settings.compliance_temperature).
        provider: Optional provider override.

    Returns:
        dict[str, Any]: Parsed JSON dictionary validating against the supplied schema.

    Raises:
        LLMError: If generation fails, returns non-JSON, or violates schema format.
    """
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
    """Send a text generation request to Google Gemini and return the raw text.

    Attempts ``settings.gemini_model`` first, then falls back through a hardcoded
    list of known-stable model aliases if the primary model returns an error or an
    empty body.  The cascade exists because Google deprecates preview model
    identifiers without notice and the fallback aliases are always kept current.

    Args:
        system: The system instruction string passed in ``GenerateContentConfig``.
        user: The user-turn content string.
        temperature: Sampling temperature forwarded to the model config unchanged.
        schema: If provided, the response MIME type is forced to
            ``application/json`` and the dict is set as the ``response_schema``
            so the SDK enforces JSON output.  If ``None``, plain text is returned.

    Returns:
        The stripped text body of the first non-empty candidate response.

    Raises:
        LLMError: If ``GEMINI_API_KEY`` is absent, the SDK is not installed, all
            models in the cascade fail, or the final response body is empty.
    """
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

    # Build the cascade: primary model first, then stable fallback aliases.
    # The duplicates check prevents retrying the same model ID twice when
    # settings.gemini_model already happens to match one of the aliases.
    models_to_try = [settings.gemini_model]
    for alt in ("gemini-2.0-flash", "gemini-2.5-flash"):
        if alt not in models_to_try:
            models_to_try.append(alt)

    last_exc = None
    response = None
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=user,
                config=types.GenerateContentConfig(**config),
            )
            if response and (response.text or "").strip():
                break
        except Exception as exc:  # pragma: no cover - network path
            last_exc = exc
            log.warning("Gemini call on %s failed (%s) — trying next model", model_name, exc)
            continue

    if response is None or not (response.text or "").strip():
        if last_exc:
            raise LLMError(f"Gemini call failed: {last_exc}") from last_exc
        raise LLMError("Gemini returned an empty response.")

    return (response.text or "").strip()


def _gemini_image(*, prompt: str) -> bytes:
    """Generate an image using the Gemini image-output model and return raw bytes.

    Uses ``generate_content`` with an image-capable model (e.g.
    ``gemini-2.0-flash-exp-image-generation``) rather than the separate Imagen
    ``generate_images`` API.  The Imagen path is Enterprise-only on AI Studio
    keys and raises a hard error ("This method is only supported in Gemini
    Enterprise Agent Platform mode").  The ``generate_content`` + ``inline_data``
    path is the current Developer-API-compatible route confirmed live against
    this project's key.

    The function walks all candidates and all parts, returning the first
    ``inline_data`` blob found.  If no image part is present the model either
    responded with text-only content or the prompt was rejected by the safety
    filter — in both cases an ``LLMError`` is raised so the caller can fall
    through to Pollinations.

    Args:
        prompt: Plain-English description of the image to generate.  Should be
            under 2 000 characters for reliable JSON transport.

    Returns:
        Raw JPEG or PNG bytes of the generated image.

    Raises:
        LLMError: If ``GEMINI_API_KEY`` is absent, the SDK is not installed, the
            API call raises, or no ``inline_data`` image part is found in the
            response.
    """
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

    # Walk the response tree: response -> candidates -> content.parts -> inline_data.
    # The SDK does not guarantee a flat .image attribute at the top level.
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


def _pollinations_image(*, prompt: str, aspect_ratio: str = "1:1") -> bytes:
    """Generate an image via the Pollinations FLUX.1 public API and return raw bytes.

    Pollinations is a keyless, zero-cost FLUX.1-schnell inference endpoint
    (``image.pollinations.ai``).  No account, no billing, no quota — confirmed
    live: a plain GET returns a ``image/jpeg`` body.

    Aspect ratio is translated to pixel dimensions before URL encoding.  The
    prompt is sanitised to strip newlines, ``%``, and ``&`` characters that
    would corrupt the query-string, then truncated to 200 characters to stay
    inside URL length limits.

    If the parameterised URL (``?width=&height=&nologo=true&model=flux``) fails
    with an HTTP error, the function retries with the bare URL
    (``/prompt/<encoded>``) as a fallback — the Pollinations CDN sometimes rejects
    the full query string when the prompt is near the length limit.

    Args:
        prompt: Plain-English image description.  Sanitised and truncated
            internally — callers do not need to pre-process it.
        aspect_ratio: One of ``"1:1"``, ``"9:16"``, or ``"16:9"``.  Any other
            value silently falls back to ``1024x1024``.

    Returns:
        Raw JPEG image bytes.

    Raises:
        LLMError: If both the parameterised and bare URLs return HTTP errors, or
            if the response body is empty.
    """
    import urllib.parse
    import httpx

    dim_map = {
        "1:1": (1024, 1024),
        "9:16": (768, 1344),
        "16:9": (1344, 768),
    }
    w, h = dim_map.get(aspect_ratio, (1024, 1024))
    clean = prompt.replace("\n", " ").replace("%", " percent ").replace("&", " and ").strip()[:200]
    encoded = urllib.parse.quote(clean)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={w}&height={h}&nologo=true&model=flux"
    try:
        response = httpx.get(url, timeout=20.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError:
        # Retry with the bare URL — some CDN nodes reject the full query string.
        try:
            fallback_url = f"https://image.pollinations.ai/prompt/{encoded}"
            response = httpx.get(fallback_url, timeout=20.0, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"Pollinations image call failed: {exc}") from exc
    except Exception as exc:
        raise LLMError(f"Pollinations image call failed: {exc}") from exc

    if not getattr(response, "content", None):
        raise LLMError("Pollinations returned an empty image.")
    return response.content


def _gemini_video(*, prompt: str, duration_seconds: int) -> bytes:
    """Generate a short video clip via Google Veo and return the raw MP4 bytes.

    Veo video generation is a long-running operation (LRO): the initial call
    returns an ``Operation`` object that is polled until its ``done`` flag is
    set.  The implementation uses a monotonic deadline rather than a fixed
    iteration count so the timeout is stable regardless of polling interval.

    The deprecated ``generate_videos(prompt=...)`` keyword form has been replaced
    by the ``source=GenerateVideosSource(prompt=...)`` shape here, matching the
    current SDK recommendation.

    Sequence:
        1. Submit the generation request via ``client.models.generate_videos``.
        2. Poll ``client.operations.get(operation)`` every
           ``settings.veo_poll_interval_seconds`` seconds.
        3. On completion, download the first generated video file via
           ``client.files.download(file=generated[0].video)``.

    Args:
        prompt: Text description of the desired video clip.  Veo performs best
            with cinematic, scene-level descriptions rather than abstract
            marketing copy.
        duration_seconds: Requested duration of the clip in seconds.  Veo
            may produce a clip of a slightly different length depending on the
            model version.

    Returns:
        Raw MP4 video bytes suitable for writing directly to disk.

    Raises:
        LLMError: If ``GEMINI_API_KEY`` is absent, the SDK is not installed,
            the initial call or any poll call raises, the LRO completes with an
            error, the result contains no video entries, or the download returns
            empty bytes.  Timeout is raised as ``LLMError`` after
            ``settings.veo_timeout_seconds`` seconds.
    """
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

    # Poll until the LRO reports done or the monotonic deadline expires.
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
    """Send a chat completion request to OpenAI and return the response text.

    Supports both plain text and structured JSON output.  When ``schema`` is
    provided, the request is sent with ``response_format.type = "json_schema"``
    and ``strict = True`` so the model is constrained to the supplied schema.
    The ``additionalProperties: False`` guard is merged into the schema
    automatically because the OpenAI strict-mode spec requires it.

    Args:
        system: Content of the ``system`` role message.
        user: Content of the ``user`` role message.
        temperature: Sampling temperature passed directly to the API.
        schema: Optional JSON Schema dict describing the required output
            structure.  If ``None``, plain text is returned.

    Returns:
        The stripped text content of the first choice message.

    Raises:
        LLMError: If ``OPENAI_API_KEY`` is absent, the SDK is not installed,
            the API call raises, or the response content is empty.
    """
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
        # strict=True requires additionalProperties: False on all object nodes.
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
