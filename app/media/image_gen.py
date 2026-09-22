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


def generate_image(prompt: str, *, output_dir: Path = TEMP_DIR) -> Path:
    """Calls the configured image provider and writes the real image to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    image_bytes = image_call(prompt=prompt)
    path = output_dir / f"img_{uuid.uuid4().hex[:12]}{_guess_extension(image_bytes)}"
    path.write_bytes(image_bytes)
    log.info("generate_image wrote %s (%d bytes)", path, len(image_bytes))
    return path
