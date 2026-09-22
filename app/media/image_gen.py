"""Zero-new-key image generation: Gemini/Imagen via app.llm.client.

    prompt (brand-aware) -> image_call() -> PNG bytes -> temp/img_*.png

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


def generate_image(prompt: str, *, output_dir: Path = TEMP_DIR) -> Path:
    """Calls the configured image provider and writes a real PNG to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    image_bytes = image_call(prompt=prompt)
    path = output_dir / f"img_{uuid.uuid4().hex[:12]}.png"
    path.write_bytes(image_bytes)
    log.info("generate_image wrote %s (%d bytes)", path, len(image_bytes))
    return path
