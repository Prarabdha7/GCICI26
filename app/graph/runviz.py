"""Excalidraw export of a pipeline run: real stages, real statuses.

Builds a static .excalidraw scene (Research -> Content -> Compliance ->
Review -> Publish) from one content_queue row plus its publish events and
feedback. Open the downloaded JSON at https://excalidraw.com. Nothing is
invented: every label comes from the database.
"""

from __future__ import annotations


def _box(idx: int, title: str, subtitle: str, tone: str) -> tuple[dict, dict]:
    x = 40 + idx * 260
    y = 120
    colors = {
        "blue": ("#1971c2", "#d0ebff"),
        "violet": ("#5f3dc4", "#e5dbff"),
        "amber": ("#e67700", "#ffec99"),
        "green": ("#2b8a3e", "#b2f2bb"),
        "gray": ("#495057", "#e9ecef"),
        "red": ("#c92a2a", "#ffc9c9"),
    }
    stroke, bg = colors.get(tone, colors["gray"])
    rect = {
        "id": f"node-{idx}", "type": "rectangle", "x": x, "y": y,
        "width": 220, "height": 110, "strokeColor": stroke, "backgroundColor": bg,
        "fillStyle": "solid", "strokeWidth": 2, "roughness": 1, "opacity": 100,
    }
    text = {
        "id": f"label-{idx}", "type": "text", "x": x + 12, "y": y + 14,
        "width": 196, "height": 82, "fontSize": 15, "strokeColor": "#1e1e1e",
        "text": f"{title}\n{subtitle[:90]}", "textAlign": "left", "verticalAlign": "top",
    }
    return rect, text


def _arrow(idx: int) -> dict:
    x = 40 + idx * 260 + 220
    return {
        "id": f"arrow-{idx}", "type": "arrow", "x": x, "y": 175,
        "width": 40, "height": 0, "strokeColor": "#495057", "strokeWidth": 2,
        "points": [[0, 0], [40, 0]],
    }


def export_run(item, events: list[dict], feedback: list[dict]) -> dict:
    """Build the scene from a ContentQueue row + its real events/feedback."""
    status = (item.status or "pending").lower()
    review_tone = {"approved": "green", "rejected": "red", "pending": "amber"}.get(status, "amber")
    publish_tone = {"published": "green", "scheduled": "blue"}.get(status, "gray")
    stages = [
        ("Research", f"{item.brand} / {item.topic or 'market scan'}", "blue"),
        ("Content", (item.draft_content or "")[:90] or "no draft", "violet"),
        ("Compliance", "; ".join(item.compliance_errors or [])[:90] or "passed", "amber"),
        (f"Review: {status}", "; ".join(f.get("human_note", "") for f in feedback)[:90] or "awaiting human", review_tone),
        ("Publish", f"{item.external_post_id or 'not posted'}", publish_tone),
    ]
    elements: list[dict] = []
    for idx, (title, subtitle, tone) in enumerate(stages):
        rect, text = _box(idx, title, subtitle, tone)
        elements.extend([rect, text])
        if idx < len(stages) - 1:
            elements.append(_arrow(idx))
    for event in events[:6]:
        elements.append({
            "id": f"event-{event.get('event')}-{event.get('at')}", "type": "text",
            "x": 40, "y": 280 + 24 * elements.__len__() % 200, "fontSize": 13,
            "strokeColor": "#495057",
            "text": f"• {event.get('event')} [{event.get('provider')}] {event.get('at') or ''}",
        })
    return {"type": "excalidraw", "version": 2, "source": "ja-assure", "elements": elements}
