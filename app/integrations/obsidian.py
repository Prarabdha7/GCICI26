"""Optional Obsidian + Excalidraw execution export."""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from uuid import uuid4

from app.config import settings

log = logging.getLogger(__name__)


def _safe_slug(value: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value.lower())
    return "-".join(part for part in clean.split("-") if part)[:80] or "run"


def _build_excalidraw_json(*, include_video: bool, manual: bool) -> str:
    steps = ["memory_retrieval", "market_research", "content", "localization"]
    if include_video:
        steps.append("video")
    steps.append("compliance_gate")
    steps.append("manual_intervention" if manual else "persist")

    elements = []
    x0, y0, w, h = 40, 120, 170, 70
    prev_id = None
    for i, name in enumerate(steps):
        node_id = f"node-{i}-{uuid4().hex[:8]}"
        x = x0 + i * 220
        elements.append(
            {
                "id": node_id,
                "type": "rectangle",
                "x": x,
                "y": y0,
                "width": w,
                "height": h,
                "angle": 0,
                "strokeColor": "#1e1e1e",
                "backgroundColor": "#fff9db" if i == len(steps) - 1 else "#ffffff",
                "fillStyle": "solid",
                "strokeWidth": 1,
                "strokeStyle": "solid",
                "roughness": 0,
                "opacity": 100,
                "groupIds": [],
                "frameId": None,
                "roundness": {"type": 2},
                "seed": i + 1,
                "version": 1,
                "versionNonce": i + 10,
                "isDeleted": False,
                "boundElements": [],
                "updated": 1,
                "link": None,
                "locked": False,
            }
        )
        elements.append(
            {
                "id": f"text-{i}-{uuid4().hex[:8]}",
                "type": "text",
                "x": x + 16,
                "y": y0 + 24,
                "width": 138,
                "height": 22,
                "angle": 0,
                "strokeColor": "#1e1e1e",
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": 1,
                "strokeStyle": "solid",
                "roughness": 0,
                "opacity": 100,
                "groupIds": [],
                "frameId": None,
                "roundness": None,
                "seed": i + 100,
                "version": 1,
                "versionNonce": i + 110,
                "isDeleted": False,
                "boundElements": [],
                "updated": 1,
                "link": None,
                "locked": False,
                "text": name,
                "fontSize": 18,
                "fontFamily": 1,
                "textAlign": "left",
                "verticalAlign": "middle",
                "containerId": None,
                "originalText": name,
                "lineHeight": 1.25,
            }
        )

        if prev_id is not None:
            elements.append(
                {
                    "id": f"arrow-{i}-{uuid4().hex[:8]}",
                    "type": "arrow",
                    "x": x - 40,
                    "y": y0 + 35,
                    "width": 40,
                    "height": 0,
                    "angle": 0,
                    "strokeColor": "#1e1e1e",
                    "backgroundColor": "transparent",
                    "fillStyle": "solid",
                    "strokeWidth": 2,
                    "strokeStyle": "solid",
                    "roughness": 0,
                    "opacity": 100,
                    "groupIds": [],
                    "frameId": None,
                    "roundness": None,
                    "seed": i + 200,
                    "version": 1,
                    "versionNonce": i + 210,
                    "isDeleted": False,
                    "boundElements": [],
                    "updated": 1,
                    "link": None,
                    "locked": False,
                    "points": [[0, 0], [40, 0]],
                    "lastCommittedPoint": None,
                    "startBinding": None,
                    "endBinding": None,
                    "startArrowhead": None,
                    "endArrowhead": "arrow",
                }
            )
        prev_id = node_id

    return json.dumps(
        {
            "type": "excalidraw",
            "version": 2,
            "source": "https://ja-assure.local/execution-export",
            "elements": elements,
            "appState": {"viewBackgroundColor": "#ffffff"},
            "files": {},
        },
        ensure_ascii=False,
        indent=2,
    )


def export_execution_to_obsidian(*, state: dict, thread_id: str) -> None:
    if not settings.obsidian_export_enabled or not settings.obsidian_vault_dir:
        return

    vault = Path(settings.obsidian_vault_dir).expanduser()
    if not vault.exists() or not vault.is_dir():
        log.warning("Obsidian export skipped: OBSIDIAN_VAULT_DIR is invalid (%s)", vault)
        return

    folder = vault / "JA-Assure-Runs"
    folder.mkdir(parents=True, exist_ok=True)

    brand = str(state.get("brand") or "unknown")
    platform = str(state.get("platform") or "unknown")
    content_id = str(state.get("content_id") or "pending")
    status = str(state.get("status") or "unknown")
    retry_count = int(state.get("retry_count") or 0)
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = _safe_slug(f"{brand}-{platform}-{content_id}-{thread_id}")

    note_name = f"{timestamp}-{slug}"
    note_path = folder / f"{note_name}.md"
    excalidraw_path = folder / f"{note_name}.excalidraw"

    brand_tag = _safe_slug(brand)
    platform_tag = _safe_slug(platform)
    status_tag = _safe_slug(status)

    brand_link = "Jaguar-Transit" if "jaguar" in brand.lower() else ("DoctorShield" if "doctor" in brand.lower() else "Jade")
    platform_map = {
        "linkedin": "LinkedIn",
        "instagram": "Instagram",
        "tiktok": "TikTok",
        "facebook": "Facebook",
    }
    platform_link = platform_map.get(platform.lower(), platform.capitalize())

    content_type_val = state.get("content_type") or "post"
    topic_val = state.get("topic") or "General Brand Marketing"

    note = [
        "---",
        f"title: JA Assure Run {content_id} ({brand} - {platform_link})",
        f"tags: [run, brand/{brand_tag}, channel/{platform_tag}, status/{status_tag}]",
        f'brand: "[[{brand_link}]]"',
        f'channel: "[[{platform_link}]]"',
        'hub: "[[JA-Assure-Second-Brain]]"',
        'orchestrator: "[[LangGraph-Engine]]"',
        'gate: "[[Compliance-Gate]]"',
        f"created: {timestamp}",
        "---",
        "",
        f"# JA Assure Run {content_id} — {brand} on {platform_link}",
        "",
        "> Part of the [[JA-Assure-Second-Brain]] active multi-agent pipeline telemetry.",
        "",
        "## Linked Entities",
        f"- **Brand**: [[{brand_link}]]",
        f"- **Target Channel**: [[{platform_link}]]",
        "- **Orchestration**: [[LangGraph-Engine]]",
        "- **Compliance Gatekeeper**: [[Compliance-Gate]]",
        "- **Memory Context**: [[Tier-2-Mem0-Buffer]]",
        "",
        "## Execution Telemetry",
        f"- **Thread ID**: `{thread_id}`",
        f"- **Brand**: `{brand}`",
        f"- **Platform**: `{platform}`",
        f"- **Status**: `{status}`",
        f"- **Retry count**: `{retry_count}`",
        f"- **Content type**: `{content_type_val}`",
        f"- **Topic**: `{topic_val}`",
        f"- **Generated at (UTC)**: `{timestamp}`",
    ]
    if state.get("compliance_errors"):
        note.append(f"- **Compliance errors**: `{state.get('compliance_errors')}`")

    if settings.excalidraw_export_enabled:
        note.extend(
            [
                "",
                "## Execution Flowchart",
                f"![[{excalidraw_path.name}]]",
            ]
        )

    note.extend(
        [
            "",
            "## Graph Context",
            f"Connects [[{brand_link}]] with [[{platform_link}]] governed by [[Universal-Rubric]] and evaluated at [[Compliance-Gate]].",
        ]
    )
    note_path.write_text("\n".join(note) + "\n", encoding="utf-8")

    if settings.excalidraw_export_enabled:
        include_video = ((state.get("platform") or "").lower() in {"instagram", "tiktok"}) or (
            (state.get("content_type") or "").lower() == "video"
        )
        manual = status == "manual_intervention"
        excalidraw_path.write_text(
            _build_excalidraw_json(include_video=include_video, manual=manual),
            encoding="utf-8",
        )

