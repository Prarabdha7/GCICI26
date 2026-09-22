"""Zero-new-key image generation: Gemini native image models via
app.llm.client, falling back to Pollinations' keyless API when Gemini's
free-tier billing gate blocks it.

    prompt (brand-aware) -> image_call() -> bytes -> temp/img_*.<ext>

Real mode: an LLMError propagates to the caller — no fabricated image.
Callers (app.graph.nodes) decide whether that's fatal; today they treat a
missing image the same way video_assembly_node treats a missing clip: best
effort, never blocks the text pipeline.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from app.llm.client import image_call
from app.media.assembly import TEMP_DIR

log = logging.getLogger(__name__)

_MAGIC_BYTES: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8\xff", ".jpg"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
]


def _guess_extension(image_bytes: bytes) -> str:
    """Different providers return different formats (Gemini: PNG, Pollinations:
    JPEG) — sniff the real one so /temp serves the correct Content-Type."""
    for magic, ext in _MAGIC_BYTES:
        if image_bytes.startswith(magic):
            return ext
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return ".webp"
    return ".png"


def generate_image(prompt: str, *, aspect_ratio: str = "1:1", output_dir: Path = TEMP_DIR) -> Path:
    """Calls the configured image provider and writes the real image to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    image_bytes = image_call(prompt=prompt, aspect_ratio=aspect_ratio)
    path = output_dir / f"img_{uuid.uuid4().hex[:12]}{_guess_extension(image_bytes)}"
    path.write_bytes(image_bytes)
    log.info("generate_image wrote %s (%d bytes)", path, len(image_bytes))
    return path


def render_brand_visual(
    *,
    brand: str = "Jade",
    title: str,
    subtitle: str = "",
    aspect_ratio: str = "1:1",
    output_dir: Path = TEMP_DIR,
) -> Path:
    """Zero-cost procedural brand visual card in Apple Cupertino aesthetic."""
    from PIL import Image, ImageDraw

    output_dir.mkdir(parents=True, exist_ok=True)
    dim_map = {
        "1:1": (1080, 1080),
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
    }
    W, H = dim_map.get(aspect_ratio, (1080, 1080))
    b = (brand or "Jade").strip().lower()
    if "doctor" in b:
        bg_top, bg_bot = (4, 30, 48), (2, 84, 120)
        accent = (6, 182, 212)
        niche = "MEDICAL INDEMNITY"
    elif "jaguar" in b:
        bg_top, bg_bot = (11, 17, 32), (30, 58, 138)
        accent = (59, 130, 246)
        niche = "HIGH-VALUE TRANSIT"
    else:
        bg_top, bg_bot = (4, 26, 20), (6, 78, 59)
        accent = (16, 185, 129)
        niche = "JEWELLERS BLOCK"

    img = Image.new("RGB", (W, H), bg_top)
    draw = ImageDraw.Draw(img)

    # Vertical subtle gradient
    for y in range(H):
        ratio = y / H
        r = int(bg_top[0] * (1 - ratio) + bg_bot[0] * ratio)
        g = int(bg_top[1] * (1 - ratio) + bg_bot[1] * ratio)
        b_c = int(bg_top[2] * (1 - ratio) + bg_bot[2] * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b_c))

    # Glass container
    pad_x = int(W * 0.08)
    pad_y = int(H * 0.12)
    draw.rounded_rectangle(
        [pad_x, pad_y, W - pad_x, H - pad_y],
        radius=32,
        fill=(15, 23, 42),
        outline=accent,
        width=3,
    )

    # Header
    draw.text((pad_x + 50, pad_y + 60), f"JA ASSURE  |  {brand.upper()}", fill=accent)
    draw.text((pad_x + 50, pad_y + 100), niche, fill=(148, 163, 184))

    # Title wrapping
    words = (title or "").split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > 28:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)

    y_cur = pad_y + 200
    for line in lines[:8]:
        draw.text((pad_x + 50, y_cur), line, fill=(255, 255, 255))
        y_cur += 54

    # Subtitle
    if subtitle:
        y_cur += 20
        draw.text((pad_x + 50, y_cur), subtitle[:120], fill=(203, 213, 225))

    # Footer
    draw.text((pad_x + 50, H - pad_y - 70), "MAS Notice 318 Compliant  |  Direct InsurTech Specialist", fill=(148, 163, 184))

    path = output_dir / f"brand_{uuid.uuid4().hex[:12]}.png"
    img.save(path)
    return path
