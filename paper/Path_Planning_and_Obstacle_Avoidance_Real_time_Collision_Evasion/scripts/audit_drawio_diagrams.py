from __future__ import annotations

import math
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rect:
    id: str
    x: float
    y: float
    w: float
    h: float
    audit_ignore: bool = False

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.h

    def expanded(self, margin: float) -> "Rect":
        return Rect(self.id, self.x - margin, self.y - margin, self.w + 2 * margin, self.h + 2 * margin, self.audit_ignore)


def get_style_map(style: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in style.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def point_in_rect(px: float, py: float, rect: Rect, *, strict: bool = False) -> bool:
    if strict:
        return rect.left < px < rect.right and rect.top < py < rect.bottom
    return rect.left <= px <= rect.right and rect.top <= py <= rect.bottom


def segment_intersects_rect(p1: tuple[float, float], p2: tuple[float, float], rect: Rect) -> bool:
    x1, y1 = p1
    x2, y2 = p2
    if point_in_rect(x1, y1, rect, strict=True) or point_in_rect(x2, y2, rect, strict=True):
        return True
    if math.isclose(x1, x2):
        x = x1
        if rect.left < x < rect.right:
            ymin, ymax = sorted((y1, y2))
            return ymax > rect.top and ymin < rect.bottom
        return False
    if math.isclose(y1, y2):
        y = y1
        if rect.top < y < rect.bottom:
            xmin, xmax = sorted((x1, x2))
            return xmax > rect.left and xmin < rect.right
        return False
    return False


def load_diagram(path: Path) -> tuple[dict[str, Rect], list[dict]]:
    root = ET.parse(path).getroot()
    diagram_root = root.find(".//root")
    if diagram_root is None:
        raise RuntimeError(f"No mxGraph root found in {path}")

    rects: dict[str, Rect] = {}
    edges: list[dict] = []

    for cell in diagram_root.findall("mxCell"):
        if cell.get("vertex") == "1":
            style = cell.get("style", "")
            if "text;" in style:
                continue
            geom = cell.find("mxGeometry")
            if geom is None:
                continue
            x = float(geom.get("x", "0"))
            y = float(geom.get("y", "0"))
            w = float(geom.get("width", "0"))
            h = float(geom.get("height", "0"))
            style_map = get_style_map(style)
            rects[cell.attrib["id"]] = Rect(
                cell.attrib["id"],
                x,
                y,
                w,
                h,
                audit_ignore=style_map.get("auditIgnore") == "1",
            )
        elif cell.get("edge") == "1":
            style_map = get_style_map(cell.get("style", ""))
            edges.append(
                {
                    "id": cell.attrib["id"],
                    "source": cell.get("source"),
                    "target": cell.get("target"),
                    "style": style_map,
                    "audit_ignore": style_map.get("auditIgnore") == "1",
                    "points": [
                        (float(pt.get("x", "0")), float(pt.get("y", "0")))
                        for pt in cell.findall("./mxGeometry/Array[@as='points']/mxPoint")
                    ],
                    "label": cell.get("value", ""),
                }
            )

    return rects, edges


def anchor(rect: Rect, style: dict[str, str], prefix: str) -> tuple[float, float]:
    px = float(style.get(f"{prefix}X", "0.5"))
    py = float(style.get(f"{prefix}Y", "0.5"))
    return rect.x + px * rect.w, rect.y + py * rect.h


def audit_file(path: Path, clearance_margin: float = 8.0) -> tuple[list[str], list[str]]:
    rects, edges = load_diagram(path)
    errors: list[str] = []
    warnings: list[str] = []

    for edge in edges:
        if edge["audit_ignore"]:
            continue
        source_id = edge["source"]
        target_id = edge["target"]
        if source_id not in rects or target_id not in rects:
            errors.append(f"{edge['id']}: missing source or target vertex")
            continue

        source = rects[source_id]
        target = rects[target_id]
        poly = [anchor(source, edge["style"], "exit")]
        poly.extend(edge["points"])
        poly.append(anchor(target, edge["style"], "entry"))

        for p1, p2 in zip(poly, poly[1:]):
            for rect_id, rect in rects.items():
                if rect_id in {source_id, target_id}:
                    continue
                if rect.audit_ignore:
                    continue
                if segment_intersects_rect(p1, p2, rect):
                    errors.append(
                        f"{edge['id']}: segment {p1} -> {p2} crosses {rect_id}"
                    )
                elif segment_intersects_rect(p1, p2, rect.expanded(clearance_margin)):
                    warnings.append(
                        f"{edge['id']}: segment {p1} -> {p2} comes within {clearance_margin:g}px of {rect_id}"
                    )

    rect_items = list(rects.values())
    for idx, rect_a in enumerate(rect_items):
        if rect_a.audit_ignore:
            continue
        for rect_b in rect_items[idx + 1 :]:
            if rect_b.audit_ignore:
                continue
            overlap_x = min(rect_a.right, rect_b.right) - max(rect_a.left, rect_b.left)
            overlap_y = min(rect_a.bottom, rect_b.bottom) - max(rect_a.top, rect_b.top)
            if overlap_x > 0 and overlap_y > 0:
                errors.append(f"vertex overlap: {rect_a.id} overlaps {rect_b.id}")

    return errors, warnings


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: python audit_drawio_diagrams.py <diagram.drawio> [<diagram.drawio> ...]")
        return 2

    had_error = False
    for arg in argv[1:]:
        path = Path(arg)
        errors, warnings = audit_file(path)
        print(f"\n[{path.name}]")
        if not errors and not warnings:
            print("PASS: no crossings or near-box route warnings")
            continue
        if errors:
            had_error = True
            print("Errors:")
            for msg in errors:
                print(f"  - {msg}")
        if warnings:
            print("Warnings:")
            for msg in warnings:
                print(f"  - {msg}")
    return 1 if had_error else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
