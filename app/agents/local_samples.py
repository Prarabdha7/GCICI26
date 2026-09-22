"""Machine-local sample content for the demo path (gitignored, never committed).

The repo ships zero baked-in samples: mock search/discovery data, focus-group
personas and seed rows all load from `local/demo_samples.json`
(`settings.local_samples_path`, resolved against BASE_DIR). When the file is
absent or invalid, loaders return empty collections and callers stay honest
(empty results / refusal) instead of inventing content. See
`local/samples.example.json` for the shape. Tests point the setting at tmp
files they create themselves.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def samples_path() -> Path:
    from app.config import settings

    raw = Path(settings.local_samples_path)
    return raw if raw.is_absolute() else settings.base_dir / raw


def load_samples() -> dict[str, Any]:
    try:
        raw = samples_path().read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        log.warning("Local samples file is not valid JSON — ignoring.")
        return {}
    if not isinstance(data, dict):
        log.warning("Local samples file must hold a JSON object — ignoring.")
        return {}
    return data


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def search_results() -> list[dict[str, Any]]:
    items = _as_list(load_samples().get("search_results"))
    return [r for r in items if isinstance(r, dict)]


def prospects() -> list[dict[str, Any]]:
    items = _as_list(load_samples().get("prospects"))
    return [p for p in items if isinstance(p, dict)]


def personas() -> dict[str, Any]:
    data = load_samples().get("personas")
    return data if isinstance(data, dict) else {}


def scrape_template() -> str:
    template = load_samples().get("scrape_template")
    return template if isinstance(template, str) else ""


def seed_rows() -> dict[str, list]:
    data = load_samples().get("seed_rows")
    if not isinstance(data, dict):
        return {}
    return {k: _as_list(v) for k, v in data.items()}
