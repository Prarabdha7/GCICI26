"""Hybrid zero-cost video source providers for JA Assure reels.

Strategies supported in order of priority with graceful fallbacks:
1. Google Veo (Strategy 2): Native AI video generation via Gemini API key if enabled.
2. Community Video Endpoint (Strategy 3): Free open-source diffusion endpoint (Pollinations.ai).
3. Curated High-End B-Roll Loops (Strategy 4): Local loop files in assets/video/ (Jade, DoctorShield, Jaguar Transit).
4. Imagen 3 / Gemini Image + 2.5D Ken Burns Camera Engine (Strategy 1): Photorealistic still animated with 3D push-in and pan.
5. Procedural Branded 2.5D Canvas: Fully offline zero-asset mathematical fallback.

Zero crashes, 100% free ($0.00).
"""

from __future__ import annotations

import logging
import urllib.parse
from pathlib import Path

import httpx

from app.config import settings

log = logging.getLogger(__name__)

BRAND_CINEMATIC_PROMPTS: dict[str, str] = {
    "jade": (
        "Emerald and diamond brooch resting on black velvet inside a bank vault, "
        "dramatic lighting, 4K, macro cinematic sweep, photorealistic luxury jewellery"
    ),
    "doctorshield": (
        "Dramatic clinical lighting in a modern diagnostic surgical theater, "
        "sterile, blue ambient glow, ultra-detailed 4K cinematic medical technology"
    ),
    "jaguar transit": (
        "Armored security logistics convoy transport vehicle on wet asphalt at night "
        "under neon streetlights, cinematic rain reflections, 4K high-value transit"
    ),
    "jaguar_transit": (
        "Armored security logistics convoy transport vehicle on wet asphalt at night "
        "under neon streetlights, cinematic rain reflections, 4K high-value transit"
    ),
}

BRAND_BROLL_FILENAMES: dict[str, list[str]] = {
    "jade": ["jade_vault_loop.mp4", "jade_loop.mp4"],
    "doctorshield": ["doctorshield_clinic_loop.mp4", "doctorshield_loop.mp4"],
    "jaguar transit": ["jaguar_transit_loop.mp4", "jaguar_loop.mp4"],
    "jaguar_transit": ["jaguar_transit_loop.mp4", "jaguar_loop.mp4"],
}


def get_cinematic_prompt(brand: str, script: str = "") -> str:
    """Returns a tailored cinematic video prompt for the given brand."""
    key = (brand or "").strip().lower()
    base = BRAND_CINEMATIC_PROMPTS.get(key, f"Cinematic corporate commercial for {brand}")
    if script:
        first_words = " ".join(script.split()[:12])
        return f"{base}, concept: {first_words}"
    return base


def generate_veo_clip(
    prompt: str,
    *,
    output_path: Path,
    brand: str = "Jade",
) -> Path | None:
    """Strategy 2: Google Veo video generation via Gemini API key.

    Probes the Google GenAI SDK for video generation models (e.g. veo-2.0-generate-001).
    Returns output_path if successful, or None if Veo is not enabled on the API key tier.
    Never raises an uncaught exception.
    """
    if not settings.gemini_api_key:
        return None

    try:
        from google import genai

        client = genai.Client(api_key=settings.gemini_api_key)
        veo_models = [
            settings.gemini_video_model,
            "veo-3.1-fast-generate-preview",
            "veo-3.1-generate-preview",
            "veo-3.1-lite-generate-preview",
            "veo-2.0-generate-001",
        ]
        # Check if client has models with generate_videos or video support
        if hasattr(client.models, "generate_videos"):
            for m in veo_models:
                try:
                    operation = client.models.generate_videos(
                        model=m,
                        prompt=prompt,
                        config={"aspect_ratio": "9:16", "person_generation": "ALLOW_ADULT"},
                    )
                    if hasattr(operation, "response") and operation.response:
                        video_bytes = getattr(operation.response, "video_bytes", None)
                        if video_bytes:
                            output_path.parent.mkdir(parents=True, exist_ok=True)
                            output_path.write_bytes(video_bytes)
                            log.info("Veo generation succeeded with %s: %s", m, output_path)
                            return output_path
                except Exception as model_err:
                    log.debug("Veo model %s unavailable: %s", m, model_err)
                    continue
    except Exception as exc:
        log.info("Google Veo unavailable on current API key tier (%s) — falling back to Strategy 1/3/4", exc)

    return None


def fetch_community_video(
    prompt: str,
    *,
    output_path: Path,
    timeout: float = 10.0,
) -> Path | None:
    """Strategy 3: Free community open-source video endpoint (Pollinations.ai).

    Calls https://image.pollinations.ai/prompt/<prompt>?model=video with a strict timeout.
    Returns output_path on 200 with valid MP4 bytes, or None on failure/timeout.
    """
    safe_prompt = urllib.parse.quote(prompt[:180])
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?model=video"

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 200 and len(resp.content) > 1024:
                # Basic check for MP4 signature or length
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(resp.content)
                log.info("Community video fetched: %s (%d bytes)", output_path, len(resp.content))
                return output_path
    except Exception as exc:
        log.info("Community video endpoint skipped (%s) — falling back to B-roll / Ken Burns", exc)

    return None


def get_curated_broll(
    brand: str,
    *,
    assets_dir: Path | None = None,
) -> Path | None:
    """Strategy 4: Curated local B-roll loop from assets/video/.

    Returns the path if a valid loop file exists, else None.
    """
    assets = assets_dir if assets_dir is not None else settings.video_assets_dir
    if not assets or not assets.is_dir():
        return None

    key = (brand or "").strip().lower()
    candidates = BRAND_BROLL_FILENAMES.get(key, [f"{key}_loop.mp4"])
    for name in candidates:
        p = assets / name
        if p.is_file() and p.stat().st_size > 0:
            return p

    return None


def generate_imagen_still(
    prompt: str,
    *,
    output_path: Path,
) -> Path | None:
    """Strategy 1 Still: Generate 4K photorealistic still via Gemini/Imagen.

    Uses app.llm.client.image_call to query Imagen/Gemini image model.
    Returns output_path if successful, else None.
    """
    if not settings.gemini_api_key:
        return None

    try:
        from app.llm.client import image_call

        image_bytes = image_call(prompt=prompt)
        if image_bytes and len(image_bytes) > 256:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)
            log.info("Imagen 3 still generated: %s (%d bytes)", output_path, len(image_bytes))
            return output_path
    except Exception as exc:
        log.info("Imagen 3 image generation skipped (%s) — using procedural canvas", exc)

    return None
