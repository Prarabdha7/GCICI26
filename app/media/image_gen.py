"""High-resolution image generator for JA Assure.

Uses Gemini image generation (gemini-3.1-flash-image with fallbacks) via
app.llm.client.image_call, with a graceful high-definition procedural visual
still fallback if quota is exhausted or keys are absent.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

from app.llm.client import image_call
from app.media.assembly import TEMP_DIR, _brand_color

log = logging.getLogger(__name__)


def generate_procedural_image(
    prompt: str,
    *,
    brand: str = "Jade",
    size: tuple[int, int] = (1080, 1080),
    output_path: Path | None = None,
) -> Path:
    """Generates a high-definition branded visual card when API keys are unconfigured or rate-limited."""
    W, H = size
    bg = _brand_color(brand)
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # Gradient/glow effect in center
    gold = (212, 175, 55)
    cream = (250, 248, 242)
    accent = (45, 212, 191) if "jade" in brand.lower() else ((245, 158, 11) if "jaguar" in brand.lower() else (6, 182, 212))

    # Outer luxury double border
    draw.rectangle([24, 24, W - 24, H - 24], outline=gold, width=3)
    draw.rectangle([34, 34, W - 34, H - 34], outline=(gold[0]//2, gold[1]//2, gold[2]//2), width=1)

    # Top brand bar
    draw.rectangle([35, 35, W - 35, 140], fill=(10, 10, 15))
    draw.text((60, 68), f"JA ASSURE  •  {brand.upper()}", fill=gold)

    # Center card area
    draw.rectangle([80, 220, W - 80, H - 220], fill=(bg[0] + 10, bg[1] + 15, bg[2] + 20), outline=accent, width=2)
    draw.text((120, 270), "SPECIALTY RISK INTELLIGENCE", fill=accent)

    # Prompt words wrapped
    words = (prompt or "Bespoke protection and risk transfer").split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > 28:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)

    y = 360
    for line in lines[:8]:
        draw.text((120, y), line, fill=cream)
        y += 50

    # Bottom legal tag
    draw.rectangle([35, H - 120, W - 35, H - 35], fill=(10, 10, 15))
    draw.text((60, H - 85), "CONFIDENTIAL & PROPRIETARY  •  MAS / BNM COMPLIANT DISCLOSURE", fill=(140, 140, 140))

    target = output_path or (TEMP_DIR / f"procedural_{uuid.uuid4().hex[:8]}.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    img.save(target)
    return target


def generate_image(
    prompt: str,
    *,
    brand: str = "Jade",
    model: str | None = None,
    output_dir: Path = TEMP_DIR,
) -> Path:
    """Attempts Gemini image generation (gemini-3.1-flash-image) and falls back safely to procedural card."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"img_{uuid.uuid4().hex[:10]}.png"
    target = output_dir / filename

    try:
        raw_bytes = image_call(prompt=prompt, model=model)
        if raw_bytes and len(raw_bytes) > 256:
            target.write_bytes(raw_bytes)
            log.info("generate_image wrote live Gemini image %s (%d bytes)", target, len(raw_bytes))
            return target
    except Exception as exc:
        log.warning("Live image generation failed (%s) — using procedural card fallback", exc)

    return generate_procedural_image(prompt, brand=brand, output_path=target)
