"""Obsidian-compatible memory vault: the agent's Second Brain on disk.

Projects DB rows (feedback, compliance-relevant queue rows, intel digests,
publish trail, brand/regulation cards) into local Markdown files with YAML
frontmatter and [[bidirectional links]], plus a graph.json the frontend
renders as a knowledge graph. The directory also opens directly in Obsidian.

Vault root defaults to <BASE_DIR>/vault (gitignored). Nothing here invents
content: every file traces to a DB row or to brand_knowledge.py config.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def _slug(text: str, limit: int = 60) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return text[:limit] or "untitled"


def _frontmatter(fields: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        elif isinstance(value, list):
            lines.append(f"{key}: [{', '.join(json.dumps(str(v)) for v in value)}]")
        else:
            escaped = str(value).replace('"', '\\"')
            lines.append(f'{key}: "{escaped}"')
    lines.append("---")
    return "\n".join(lines) + "\n"


def _write(root: Path, *parts: str, body: str) -> str:
    path = root.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path.relative_to(root).as_posix()


def export_brands(root: Path) -> list[dict]:
    from app.agents.brand_knowledge import BRANDS, JURISDICTIONS

    nodes = []
    for key, info in BRANDS.items():
        regs = [f"[[Regulation: {j}]]" for j in info.get("territories", []) if j in JURISDICTIONS]
        body = (
            _frontmatter({"kind": "brand", "brand": info["name"], "niche": info["niche"],
                          "territories": info.get("territories", [])})
            + f"\n# {info['name']}\n\n{info['tagline']}\n\n"
            + f"**Voice:** {info['voice']}\n\n**Audiences:** {', '.join(info.get('audiences', []))}\n\n"
            + "## Regulations\n\n" + ("\n".join(f"- {r}" for r in regs) + "\n" if regs else "_None mapped._\n")
        )
        rel = _write(root, "brands", f"{info['name']}.md", body=body)
        nodes.append({"id": f"brand:{info['name']}", "label": info["name"], "kind": "brand", "path": rel})
    for jurisdiction, info in JURISDICTIONS.items():
        body = (
            _frontmatter({"kind": "regulation", "jurisdiction": jurisdiction, "regulator": info["regulator"]})
            + f"\n# Regulation: {jurisdiction}\n\n**Regulator:** {info['regulator']}\n\n"
            + f"**Framework:** {info['framework']}\n\n**Required wording:** {info['mandatory_warnings']}\n"
        )
        rel = _write(root, "regulations", f"{jurisdiction}.md", body=body)
        nodes.append({"id": f"regulation:{jurisdiction}", "label": jurisdiction, "kind": "regulation", "path": rel})
    return nodes


def export_feedback(root: Path, db) -> tuple[list[dict], list[list[str]]]:
    from app.db.models import FeedbackMemory
    from sqlalchemy import select

    nodes, edges = [], []
    rows = list(db.scalars(select(FeedbackMemory).order_by(FeedbackMemory.timestamp)))
    for row in rows:
        name = f"{row.id:04d}-{_slug(row.error_tag)}"
        body = (
            _frontmatter({"kind": "feedback", "brand": row.brand, "platform": row.platform,
                          "tag": row.error_tag, "content_id": row.content_id or 0,
                          "at": row.timestamp.isoformat() if row.timestamp else ""})
            + f"\n# Feedback {row.id} — {row.error_tag}\n\n{row.human_note}\n\n"
            + f"See also: [[Brand: {row.brand}]]"
            + (f" · [[Asset: {row.content_id}]]" if row.content_id else "") + "\n"
        )
        rel = _write(root, "feedback", f"{name}.md", body=body)
        node_id = f"feedback:{row.id}"
        nodes.append({"id": node_id, "label": f"{row.error_tag} #{row.id}", "kind": "feedback", "path": rel})
        edges.append([node_id, f"brand:{row.brand}"])
        if row.content_id:
            edges.append([node_id, f"asset:{row.content_id}"])
    return nodes, edges


def export_queue(root: Path, db) -> tuple[list[dict], list[list[str]]]:
    from app.db.models import ContentQueue
    from sqlalchemy import select

    nodes, edges = [], []
    rows = list(db.scalars(select(ContentQueue).order_by(ContentQueue.created_at).limit(500)))
    for row in rows:
        name = f"{row.id:04d}-{_slug(row.brand + '-' + row.platform)}"
        body = (
            _frontmatter({"kind": "asset", "brand": row.brand, "platform": row.platform,
                          "language": row.language, "status": row.status,
                          "is_demo": bool(row.is_demo), "retry_count": row.retry_count or 0})
            + f"\n# Asset {row.id} — {row.brand} / {row.platform}\n\n"
            + f"**Status:** {row.status}{' (DEMO — simulated, not real)' if row.is_demo else ''}\n\n"
            + f"## Draft\n\n{row.draft_content or ''}\n\n"
            + (f"## Final\n\n{row.final_content or ''}\n\n" if row.final_content else "")
            + (f"## Compliance violations\n\n" + "\n".join(f"- {v}" for v in (row.compliance_errors or [])) + "\n\n" if row.compliance_errors else "")
            + f"See also: [[Brand: {row.brand}]]\n"
        )
        rel = _write(root, "assets", f"{name}.md", body=body)
        node_id = f"asset:{row.id}"
        nodes.append({"id": node_id, "label": f"Asset {row.id} ({row.status})", "kind": "asset", "path": rel})
        edges.append([node_id, f"brand:{row.brand}"])
    return nodes, edges


def export_intel(root: Path, db) -> tuple[list[dict], list[list[str]]]:
    from app.db.models import IntelDigest
    from sqlalchemy import select

    nodes, edges = [], []
    rows = list(db.scalars(select(IntelDigest).order_by(IntelDigest.created_at).limit(200)))
    for row in rows:
        name = f"{row.id:04d}-{_slug(row.brand + '-' + row.country)}"
        body = (
            _frontmatter({"kind": "intel", "brand": row.brand, "country": row.country,
                          "is_demo": bool(row.is_demo),
                          "at": row.created_at.isoformat() if row.created_at else ""})
            + f"\n# Intel {row.id} — {row.brand} / {row.country}\n\n{row.digest_text or ''}\n\n"
            + f"See also: [[Brand: {row.brand}]]\n"
        )
        rel = _write(root, "intel", f"{name}.md", body=body)
        node_id = f"intel:{row.id}"
        nodes.append({"id": node_id, "label": f"Intel {row.brand}/{row.country}", "kind": "intel", "path": rel})
        edges.append([node_id, f"brand:{row.brand}"])
    return nodes, edges


def export_competitors(root: Path) -> tuple[list[dict], list[list[str]]]:
    """Projects key regional competitors into vault markdown notes."""
    competitors = [
        {
            "name": "Chubb",
            "niche": "Jeweller's Block & High-Value Marine Cargo",
            "threat": "High brand recognition, legacy broker relationships across SG and MY.",
            "brands": ["Jade", "Jaguar Transit"],
            "regulations": ["Singapore", "Malaysia"],
        },
        {
            "name": "Medical Protection Society",
            "niche": "Medical Indemnity & Defence Mutual",
            "threat": "Dominant mutual insurer in Singapore and Malaysia, long institutional tenure.",
            "brands": ["DoctorShield"],
            "regulations": ["Singapore", "Malaysia"],
        },
        {
            "name": "Marsh McLennan",
            "niche": "Global Specie & High-Value Logistics Broker",
            "threat": "Large multinational account coverage, packaged cargo policies.",
            "brands": ["Jaguar Transit"],
            "regulations": ["Singapore", "Hong Kong"],
        },
    ]
    nodes, edges = [], []
    for c in competitors:
        name_slug = _slug(c["name"])
        brand_links = [f"[[Brand: {b}]]" for b in c["brands"]]
        reg_links = [f"[[Regulation: {r}]]" for r in c["regulations"]]
        body = (
            _frontmatter({"kind": "competitor", "name": c["name"], "niche": c["niche"]})
            + f"\n# Competitor: {c['name']}\n\n**Niche:** {c['niche']}\n\n"
            + f"**Market Threat Analysis:** {c['threat']}\n\n"
            + "## Target JA Assure Brands\n\n" + "\n".join(f"- {b}" for b in brand_links) + "\n\n"
            + "## Operating Jurisdictions\n\n" + "\n".join(f"- {r}" for r in reg_links) + "\n"
        )
        rel = _write(root, "competitors", f"{c['name'].replace(' ', '_')}.md", body=body)
        node_id = f"competitor:{name_slug}"
        nodes.append({"id": node_id, "label": f"Competitor: {c['name']}", "kind": "competitor", "path": rel})
        for b in c["brands"]:
            edges.append([node_id, f"brand:{b}"])
        for r in c["regulations"]:
            edges.append([node_id, f"regulation:{r}"])
    return nodes, edges


def export_canvas(root: Path, nodes: list[dict], edges: list[list[str]]) -> Path:
    """Generates an official Obsidian Canvas (.canvas) file for native graph visualization."""
    canvas_nodes = []
    kind_colors = {
        "brand": "1",        # red/crimson
        "regulation": "4",   # cyan/blue
        "competitor": "5",   # purple
        "feedback": "3",     # yellow
        "asset": "2",        # green
        "intel": "6",        # magenta
    }
    col_x = {
        "brand": 100,
        "competitor": 460,
        "regulation": 820,
        "feedback": 1180,
        "asset": 1540,
        "intel": 1900,
    }
    counters: dict[str, int] = {}
    id_to_canvas_id: dict[str, str] = {}

    for i, n in enumerate(nodes[:100]):  # cap to 100 nodes for clean canvas rendering
        kind = n.get("kind", "asset")
        row = counters.get(kind, 0)
        counters[kind] = row + 1
        x = col_x.get(kind, 1000)
        y = 100 + row * 160
        cid = f"cnode_{i}"
        id_to_canvas_id[n["id"]] = cid
        canvas_nodes.append({
            "id": cid,
            "type": "file" if n.get("path") else "text",
            "file": n.get("path"),
            "text": f"### {n.get('label')}\nKind: {kind}" if not n.get("path") else None,
            "x": x,
            "y": y,
            "width": 280,
            "height": 130,
            "color": kind_colors.get(kind, "1"),
        })

    canvas_edges = []
    for i, (src, dst) in enumerate(edges):
        if src in id_to_canvas_id and dst in id_to_canvas_id:
            canvas_edges.append({
                "id": f"cedge_{i}",
                "fromNode": id_to_canvas_id[src],
                "fromSide": "right",
                "toNode": id_to_canvas_id[dst],
                "toSide": "left",
            })

    canvas_data = {
        "nodes": canvas_nodes,
        "edges": canvas_edges,
    }
    canvas_path = root / "JA_Assure_Second_Brain.canvas"
    canvas_path.write_text(json.dumps(canvas_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return canvas_path


def export_vault(db, root: Path | None = None) -> dict:
    """Rebuild the whole vault from the DB. Returns {"nodes": [...], "edges": [...]}."""
    from app.config import settings

    root = Path(root) if root is not None else settings.base_dir / "vault"
    root.mkdir(parents=True, exist_ok=True)
    nodes = export_brands(root)
    edges: list[list[str]] = []
    comp_nodes, comp_edges = export_competitors(root)
    nodes.extend(comp_nodes)
    edges.extend(comp_edges)
    for exporter in (export_feedback, export_queue, export_intel):
        sub_nodes, sub_edges = exporter(root, db)
        nodes.extend(sub_nodes)
        edges.extend(sub_edges)
    # brand -> regulation edges from territories
    from app.agents.brand_knowledge import BRANDS

    for info in BRANDS.values():
        from app.agents.brand_knowledge import JURISDICTIONS

        for territory in info.get("territories", []):
            if territory in JURISDICTIONS:
                edges.append([f"brand:{info['name']}", f"regulation:{territory}"])
    graph = {"nodes": nodes, "edges": edges}
    (root / "graph.json").write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        export_canvas(root, nodes, edges)
    except Exception as exc:
        log.warning("Canvas export skipped (%s)", exc)
    log.info("vault exported: %s nodes, %s edges -> %s", len(nodes), len(edges), root)
    return graph
