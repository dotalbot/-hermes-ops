#!/usr/bin/env python3
"""Validate the Skills Manager draw.io source and render deterministic SVG previews."""

from __future__ import annotations

import argparse
import html
import math
import re
import textwrap
import xml.etree.ElementTree as ET
from itertools import combinations
from pathlib import Path

REQUIRED_PAGES = {
    "Operating Map": [
        "Hermes Skills Manager", "Git authority", "managerctl", "Hermes Kanban",
        "Implementation profile", "Reviewer profile", "Operator hash gate",
        "Independent verdict", "Acceptance / promotion",
    ],
    "Project Setup": [
        "Project Setup", "Setup request", "Immutable action plan", "Exact approval?",
        "project apply", "project doctor", "reconcile plan", "Explicit rollback",
    ],
    "Skill Lifecycle": [
        "Shared Skill Lifecycle", "Inventory", "Candidate apply", "Fleet impact",
        "Compatibility evidence", "Canary apply", "Promotion plan",
        "Controlled promote", "Rollback retained",
    ],
}

REQUIRED_EDGES = {
    "Project Setup": {
        ("p2-adapter", "p2-evidence"),
        ("p2-journal", "p2-rollback"),
    },
    "Skill Lifecycle": {
        ("p3-impact", "p3-block"),
        ("p3-block", "p3-compat"),
        ("p3-block", "p3-cplan"),
        ("p3-promoteact", "p3-rollback"),
    },
}

REQUIRED_DASHED_EDGES = {
    "Project Setup": {
        ("p2-adapter", "p2-evidence"),
        ("p2-journal", "p2-rollback"),
    },
    "Skill Lifecycle": {
        ("p3-block", "p3-cplan"),
        ("p3-promoteact", "p3-rollback"),
    },
}

FORBIDDEN_EDGES = {
    "Skill Lifecycle": {("p3-impact", "p3-compat")},
}

REQUIRED_CONNECTED_NODES = {
    "Project Setup": {"p2-evidence", "p2-rollback"},
    "Skill Lifecycle": {"p3-block", "p3-rollback"},
}


def style_map(style: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in style.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            result[key] = value
        elif part:
            result[part] = "1"
    return result


def plain_text(value: str) -> str:
    value = re.sub(r"(?i)<br\s*/?>", "\n", value)
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


def geometry(cell: ET.Element) -> tuple[float, float, float, float]:
    geo = cell.find("mxGeometry")
    if geo is None:
        return 0.0, 0.0, 0.0, 0.0
    x = float(geo.get("x", "0"))
    y = float(geo.get("y", "0"))
    width = float(geo.get("width", "0"))
    height = float(geo.get("height", "0"))
    return x, y, width, height


def absolute_geometry(cell_id: str, cells: dict[str, ET.Element], cache: dict[str, tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    if cell_id in cache:
        return cache[cell_id]
    cell = cells[cell_id]
    x, y, width, height = geometry(cell)
    parent = cell.get("parent")
    if parent in cells and cells[parent].get("vertex") == "1":
        px, py, _, _ = absolute_geometry(parent, cells, cache)
        x += px
        y += py
    cache[cell_id] = (x, y, width, height)
    return cache[cell_id]


def svg_text(lines: list[str], x: float, y: float, size: int, anchor: str = "middle", weight: str = "normal", fill: str = "#1f2937") -> str:
    escaped = [html.escape(line) for line in lines]
    spans = []
    for index, line in enumerate(escaped):
        dy = "0" if index == 0 else str(size + 3)
        spans.append(f'<tspan x="{x:.1f}" dy="{dy}">{line}</tspan>')
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-family="Arial,Helvetica,sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}">' + "".join(spans) + "</text>"


def wrapped_lines(text: str, width: float, size: int) -> list[str]:
    result: list[str] = []
    max_chars = max(10, int(width / max(size * 0.55, 1)))
    for raw in text.splitlines() or [""]:
        result.extend(textwrap.wrap(raw, width=max_chars, break_long_words=False, break_on_hyphens=False) or [""])
    return result


def render_page(model: ET.Element, page_name: str, output: Path) -> None:
    root = model.find("root")
    if root is None:
        raise ValueError(f"{page_name}: missing root")
    cells = {cell.get("id", ""): cell for cell in root.findall("mxCell")}
    cache: dict[str, tuple[float, float, float, float]] = {}
    width = int(float(model.get("pageWidth", "1480")))
    height = int(float(model.get("pageHeight", "820")))

    containers: list[str] = []
    vertices: list[str] = []
    edges: list[str] = []
    for cid, cell in cells.items():
        if cell.get("edge") == "1":
            edges.append(cid)
        elif cell.get("vertex") == "1":
            if "swimlane" in style_map(cell.get("style", "")):
                containers.append(cid)
            else:
                vertices.append(cid)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="#52606d"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]

    for cid in containers:
        cell = cells[cid]
        x, y, w, h = absolute_geometry(cid, cells, cache)
        st = style_map(cell.get("style", ""))
        fill = st.get("fillColor", "#f5f5f5")
        stroke = st.get("strokeColor", "#9e9e9e")
        parts.append(f'<rect id="{cid}" x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        parts.append(f'<line x1="{x}" y1="{y+34}" x2="{x+w}" y2="{y+34}" stroke="{stroke}" stroke-width="1.5"/>')
        parts.append(svg_text([plain_text(cell.get("value", ""))], x + 12, y + 23, int(float(st.get("fontSize", "17"))), anchor="start", weight="bold"))

    for cid in edges:
        cell = cells[cid]
        source = cell.get("source", "")
        target = cell.get("target", "")
        sx, sy, sw, sh = absolute_geometry(source, cells, cache)
        tx, ty, tw, th = absolute_geometry(target, cells, cache)
        scx, scy = sx + sw / 2, sy + sh / 2
        tcx, tcy = tx + tw / 2, ty + th / 2
        source_points = []
        edge_geo = cell.find("mxGeometry")
        if edge_geo is not None:
            point_array = edge_geo.find("Array[@as='points']")
            if point_array is not None:
                source_points = [(float(point.get("x", "0")), float(point.get("y", "0"))) for point in point_array.findall("mxPoint")]
        if source_points:
            first_x, first_y = source_points[0]
            last_x, last_y = source_points[-1]
            if first_y < sy:
                start = (scx, sy)
            elif first_y > sy + sh:
                start = (scx, sy + sh)
            elif first_x < sx:
                start = (sx, scy)
            else:
                start = (sx + sw, scy)
            if last_y < ty:
                end = (tcx, ty)
            elif last_y > ty + th:
                end = (tcx, ty + th)
            elif last_x < tx:
                end = (tx, tcy)
            else:
                end = (tx + tw, tcy)
            points = [start, *source_points, end]
        else:
            vertical_separated = (sy + sh + 30 <= ty) or (ty + th + 30 <= sy)
            if vertical_separated:
                if scy <= tcy:
                    start, end = (scx, sy + sh), (tcx, ty)
                else:
                    start, end = (scx, sy), (tcx, ty + th)
                mid = (start[1] + end[1]) / 2
                points = [start, (start[0], mid), (end[0], mid), end]
            else:
                long_horizontal = abs(scx - tcx) > max(sw, tw) * 2.2
                if long_horizontal:
                    corridor_y = min(sy, ty) - 25
                    start, end = (scx, sy), (tcx, ty)
                    points = [start, (start[0], corridor_y), (end[0], corridor_y), end]
                else:
                    if scx <= tcx:
                        start, end = (sx + sw, scy), (tx, tcy)
                    else:
                        start, end = (sx, scy), (tx + tw, tcy)
                    mid = (start[0] + end[0]) / 2
                    points = [start, (mid, start[1]), (mid, end[1]), end]
        d = "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in points)
        st = style_map(cell.get("style", ""))
        dash = ' stroke-dasharray="7 5"' if st.get("dashed") == "1" else ""
        stroke = st.get("strokeColor", "#52606d")
        parts.append(f'<path id="{cid}" d="{d}" fill="none" stroke="{stroke}" stroke-width="2"{dash} marker-end="url(#arrow)"/>')
        label = plain_text(cell.get("value", ""))
        if label:
            longest = max(
                zip(points, points[1:]),
                key=lambda pair: abs(pair[1][0] - pair[0][0]) + abs(pair[1][1] - pair[0][1]),
            )
            lx = (longest[0][0] + longest[1][0]) / 2
            ly = (longest[0][1] + longest[1][1]) / 2 - 6
            label_width = max(58, len(label) * 7.2 + 12)
            parts.append(f'<rect x="{lx-label_width/2:.1f}" y="{ly-14:.1f}" width="{label_width:.1f}" height="20" rx="4" fill="#ffffff" fill-opacity="0.94"/>')
            parts.append(svg_text([label], lx, ly, 14))

    for cid in vertices:
        cell = cells[cid]
        x, y, w, h = absolute_geometry(cid, cells, cache)
        st = style_map(cell.get("style", ""))
        text = plain_text(cell.get("value", ""))
        size = int(float(st.get("fontSize", "16")))
        if "text" in st:
            lines = wrapped_lines(text, w, size)
            parts.append(svg_text(lines, x + w / 2, y + size, size, weight="bold" if st.get("fontStyle") == "1" else "normal"))
            continue
        fill = st.get("fillColor", "#ffffff")
        stroke = st.get("strokeColor", "#52606d")
        if "rhombus" in st:
            pts = f"{x+w/2},{y} {x+w},{y+h/2} {x+w/2},{y+h} {x},{y+h/2}"
            parts.append(f'<polygon id="{cid}" points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        elif st.get("shape") == "cylinder3":
            ry = min(10, h / 7)
            parts.append(f'<path id="{cid}" d="M{x},{y+ry} A{w/2},{ry} 0 0 1 {x+w},{y+ry} L{x+w},{y+h-ry} A{w/2},{ry} 0 0 1 {x},{y+h-ry} Z" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
            parts.append(f'<ellipse cx="{x+w/2}" cy="{y+ry}" rx="{w/2}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        else:
            parts.append(f'<rect id="{cid}" x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        lines = wrapped_lines(text, w - 12, size)
        line_height = size + 3
        start_y = y + h / 2 - (len(lines) - 1) * line_height / 2 + size * 0.35
        parts.append(svg_text(lines, x + w / 2, start_y, size, weight="bold" if "<b>" in cell.get("value", "") and len(lines) == 1 else "normal"))

    parts.append("</svg>")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts), encoding="utf-8")
    svg_root = ET.parse(output).getroot()
    svg_visible_text = " ".join(part.strip() for part in svg_root.itertext() if part.strip())
    svg_visible_text = re.sub(r"\s+", " ", svg_visible_text)
    svg_ids = {element.get("id") for element in svg_root.iter() if element.get("id")}
    missing_edges = sorted(set(edges) - svg_ids)
    if missing_edges:
        raise ValueError(f"{page_name}: preview missing edge IDs {missing_edges!r}")
    for required in REQUIRED_PAGES[page_name]:
        if required not in svg_visible_text:
            raise ValueError(f"{page_name}: preview missing required label {required!r}")


def waypoint_segments(cell: ET.Element) -> list[tuple[str, float, float, float]]:
    """Return axis, fixed coordinate, interval start, interval end for source-owned routes."""
    points = [
        (float(point.get("x", "nan")), float(point.get("y", "nan")))
        for point in cell.findall("mxGeometry/Array[@as='points']/mxPoint")
    ]
    segments: list[tuple[str, float, float, float]] = []
    for first, second in zip(points, points[1:]):
        if math.isclose(first[1], second[1], abs_tol=0.01):
            segments.append(("h", first[1], min(first[0], second[0]), max(first[0], second[0])))
        elif math.isclose(first[0], second[0], abs_tol=0.01):
            segments.append(("v", first[0], min(first[1], second[1]), max(first[1], second[1])))
    return segments


def validate_operating_contracts(name: str, cells: list[ET.Element]) -> None:
    edges = [cell for cell in cells if cell.get("edge") == "1"]
    pairs = {(cell.get("source", ""), cell.get("target", "")) for cell in edges}

    missing = REQUIRED_EDGES.get(name, set()) - pairs
    if missing:
        raise ValueError(f"{name}: missing required edges {sorted(missing)!r}")
    forbidden = FORBIDDEN_EDGES.get(name, set()) & pairs
    if forbidden:
        raise ValueError(f"{name}: forbidden bypass edges present {sorted(forbidden)!r}")

    dashed_pairs = {
        (cell.get("source", ""), cell.get("target", ""))
        for cell in edges
        if style_map(cell.get("style", "")).get("dashed") == "1"
    }
    missing_dashed = REQUIRED_DASHED_EDGES.get(name, set()) - dashed_pairs
    if missing_dashed:
        raise ValueError(f"{name}: required recovery/blocking edges are not dashed {sorted(missing_dashed)!r}")

    degree: dict[str, int] = {}
    for source, target in pairs:
        degree[source] = degree.get(source, 0) + 1
        degree[target] = degree.get(target, 0) + 1
    disconnected = sorted(node for node in REQUIRED_CONNECTED_NODES.get(name, set()) if degree.get(node, 0) == 0)
    if disconnected:
        raise ValueError(f"{name}: required nodes are disconnected {disconnected!r}")

    if name == "Skill Lifecycle":
        decision = next(cell for cell in cells if cell.get("id") == "p3-block")
        if "rhombus" not in style_map(decision.get("style", "")):
            raise ValueError("Skill Lifecycle: impact completeness gate must be a decision")
        labels = {
            (cell.get("source", ""), cell.get("target", "")): plain_text(cell.get("value", ""))
            for cell in edges
        }
        if labels.get(("p3-block", "p3-compat")) != "YES":
            raise ValueError("Skill Lifecycle: success output from impact gate must be labelled YES")
        if "NO" not in labels.get(("p3-block", "p3-cplan"), ""):
            raise ValueError("Skill Lifecycle: blocked output from impact gate must be labelled NO")

    for left, right in combinations(edges, 2):
        if left.get("source") == right.get("source") or left.get("target") == right.get("target"):
            continue
        for lseg in waypoint_segments(left):
            for rseg in waypoint_segments(right):
                if lseg[0] != rseg[0] or not math.isclose(lseg[1], rseg[1], abs_tol=0.01):
                    continue
                overlap = min(lseg[3], rseg[3]) - max(lseg[2], rseg[2])
                if overlap > 8:
                    raise ValueError(
                        f"{name}: edges {left.get('id')} and {right.get('id')} overlap "
                        f"the same {lseg[0]} corridor by {overlap:.1f}px"
                    )


def validate_and_render(source: Path, preview_dir: Path) -> list[Path]:
    tree = ET.parse(source)
    mxfile = tree.getroot()
    if mxfile.tag != "mxfile":
        raise ValueError("source root must be mxfile")
    pages = mxfile.findall("diagram")
    names = [page.get("name", "") for page in pages]
    if names != list(REQUIRED_PAGES):
        raise ValueError(f"page order/names mismatch: {names!r}")

    previews: list[Path] = []
    for page in pages:
        name = page.get("name", "")
        model = page.find("mxGraphModel")
        if model is None:
            raise ValueError(f"{name}: missing mxGraphModel")
        root = model.find("root")
        if root is None:
            raise ValueError(f"{name}: missing root")
        cells = root.findall("mxCell")
        cell_map = {cell.get("id", ""): cell for cell in cells}
        geometry_cache: dict[str, tuple[float, float, float, float]] = {}
        ids = [cell.get("id", "") for cell in cells]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{name}: duplicate mxCell IDs")
        id_set = set(ids)
        if not {"0", "1"}.issubset(id_set):
            raise ValueError(f"{name}: root cells 0 and 1 are required")
        labels = "\n".join(plain_text(cell.get("value", "")) for cell in cells)
        for required in REQUIRED_PAGES[name]:
            if required not in labels:
                raise ValueError(f"{name}: missing required label {required!r}")
        validate_operating_contracts(name, cells)
        for cell in cells:
            for attr in ("parent", "source", "target"):
                ref = cell.get(attr)
                if ref and ref not in id_set:
                    raise ValueError(f"{name}: {cell.get('id')} has unresolved {attr}={ref}")
            if cell.get("edge") == "1":
                geo = cell.find("mxGeometry")
                if geo is None or geo.get("relative") != "1":
                    raise ValueError(f"{name}: edge {cell.get('id')} lacks relative geometry")
                source_id = cell.get("source", "")
                target_id = cell.get("target", "")
                sx, sy, sw, sh = absolute_geometry(source_id, cell_map, geometry_cache)
                tx, ty, tw, th = absolute_geometry(target_id, cell_map, geometry_cache)
                scx, tcx = sx + sw / 2, tx + tw / 2
                vertical_separated = (sy + sh + 30 <= ty) or (ty + th + 30 <= sy)
                long_horizontal = abs(scx - tcx) > max(sw, tw) * 2.2
                point_array = geo.find("Array[@as='points']")
                points = [] if point_array is None else point_array.findall("mxPoint")
                if (vertical_separated or long_horizontal) and len(points) < 2:
                    raise ValueError(f"{name}: non-trivial edge {cell.get('id')} lacks source-owned waypoints")
                for point in points:
                    x = float(point.get("x", "nan"))
                    y = float(point.get("y", "nan"))
                    if not math.isfinite(x) or not math.isfinite(y):
                        raise ValueError(f"{name}: edge {cell.get('id')} has non-finite waypoint")
            if cell.get("vertex") == "1" and plain_text(cell.get("value", "")):
                size = float(style_map(cell.get("style", "")).get("fontSize", "0"))
                if size < 14:
                    raise ValueError(f"{name}: {cell.get('id')} fontSize {size} is below 14")
        slug = name.lower().replace(" ", "-")
        output = preview_dir / f"skills-manager-operating-overview-{slug}.svg"
        render_page(model, name, output)
        previews.append(output)
    return previews


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("preview_dir", type=Path)
    args = parser.parse_args()
    previews = validate_and_render(args.source, args.preview_dir)
    print(f"DRAWIO_VALIDATION=PASS pages={len(previews)}")
    for preview in previews:
        print(preview)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
