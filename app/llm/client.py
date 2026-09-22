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


def image_call(
    *,
    prompt: str,
    provider: str | None = None,
    model: str | None = None,
) -> bytes:
    """Generates a single image from a text prompt. Returns raw image bytes (PNG)."""
    name = _resolve(provider)
    if name == "gemini":
        return _gemini_image(prompt=prompt, model=model)
    raise LLMError(f"Image generation not supported for LLM_PROVIDER: {name!r}")


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #


def _gemini_image(*, prompt: str, model: str | None = None) -> bytes:
    if not settings.gemini_api_key:
        raise LLMError("GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in.")
    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover
        raise LLMError("google-genai is not installed. pip install -r requirements.txt") from exc

    client = genai.Client(api_key=settings.gemini_api_key)
    target_models = [model] if model else [
        settings.gemini_image_model,
        "gemini-3.1-flash-image",
        "gemini-3.1-flash-lite-image",
        "gemini-2.5-flash-image",
        "gemini-3-pro-image",
    ]
    last_exc = None
    for m in [m for m in target_models if m]:
        try:
            response = client.models.generate_content(model=m, contents=prompt)
            candidates = getattr(response, "candidates", None) or []
            for candidate in candidates:
                for part in getattr(candidate.content, "parts", None) or []:
                    inline = getattr(part, "inline_data", None)
                    if inline and inline.data:
                        return inline.data
        except Exception as exc:
            last_exc = exc
            continue

    raise LLMError(f"Gemini image call failed: {last_exc}")


def _gemini(*, system: str, user: str, temperature: float, schema: dict[str, Any] | None) -> str:
    if not settings.gemini_api_key:
        raise LLMError("GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover
        raise LLMError("google-genai is not installed. pip install -r requirements.txt") from exc

    import time

    client = genai.Client(api_key=settings.gemini_api_key)
    config: dict[str, Any] = {"system_instruction": system, "temperature": temperature}
    if schema is not None:
        config["response_mime_type"] = "application/json"
        config["response_schema"] = schema

    target_models = [
        settings.gemini_model,
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-flash-latest",
    ]
    target_models = list(dict.fromkeys(m for m in target_models if m))

    last_exc = None
    for attempt in range(2):
        for m in target_models:
            try:
                response = client.models.generate_content(
                    model=m,
                    contents=user,
                    config=types.GenerateContentConfig(**config),
                )
                text = (response.text or "").strip()
                if text:
                    return text
            except Exception as exc:  # pragma: no cover - network path
                last_exc = exc
                err_str = str(exc).lower()
                if (
                    "429" in err_str
                    or "resource_exhausted" in err_str
                    or "quota" in err_str
                    or "unavailable" in err_str
                    or "503" in err_str
                    or "not_found" in err_str
                    or "404" in err_str
                ):
                    log.warning(
                        "Gemini model %s encountered rate/quota/availability error (%s) — rotating to next model in pool",
                        m,
                        exc,
                    )
                    continue
                # For non-transient errors (e.g. invalid key or bad parameter), raise immediately
                raise LLMError(f"Gemini call failed: {exc}") from exc

        if attempt == 0:
            log.warning("All pool models throttled in round 1; brief pause before final attempt...")
            time.sleep(1.5)

    raise LLMError(f"Gemini call failed across all pool models: {last_exc}") from last_exc


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
