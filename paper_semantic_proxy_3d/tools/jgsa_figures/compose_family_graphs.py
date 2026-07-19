"""Compose figures/fig_family_graphs_blender.png.

2x3 grid of the six default family graphs rendered in Blender
(assets/render_fam_*.png, produced by blender/render_family_graphs.py),
with a per-panel family label and a bottom legend mapping the six role
categories to the Okabe-Ito palette used in the renders.

Layout: row 1 = compact vehicle, articulated vehicle, quadruped;
        row 2 = branching vertical, lattice tower, rider cycle.

Run: python compose_family_graphs.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.font_manager as fm
from PIL import Image, ImageDraw, ImageFont

REPO = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d")
ASSETS = REPO / "tools" / "jgsa_figures" / "assets"
OUT = REPO / "figures" / "fig_family_graphs_blender.png"

ORDER = [
    ("compact_vehicle", "(a) compact vehicle"),
    ("articulated_vehicle", "(b) articulated vehicle"),
    ("quadruped", "(c) quadruped"),
    ("branching_vertical", "(d) branching vertical"),
    ("lattice_tower", "(e) lattice tower"),
    ("rider_cycle", "(f) rider cycle"),
]

PANEL_W, PANEL_H = 1000, 750
LABEL_H = 54
GAP_X, GAP_Y = 24, 30
MARGIN = 40
LEGEND_GAP_TOP = 30
LEGEND_H = 92
BORDER = "#C9CDD2"


def get_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(fm.findfont("DejaVu Sans"), size)


def main() -> None:
    assets = json.loads((ASSETS / "blender_assets.json").read_text(encoding="utf-8"))
    legend = list(assets["role_categories"].items())  # category -> color (frozen order)

    canvas_w = 2 * MARGIN + 3 * PANEL_W + 2 * GAP_X
    canvas_h = (MARGIN + 2 * (LABEL_H + PANEL_H) + GAP_Y
                + LEGEND_GAP_TOP + LEGEND_H + MARGIN)
    canvas = Image.new("RGB", (canvas_w, canvas_h), "#FFFFFF")
    draw = ImageDraw.Draw(canvas)
    label_font = get_font(40)
    legend_font = get_font(34)

    for i, (fam, label) in enumerate(ORDER):
        row, col = divmod(i, 3)
        x = MARGIN + col * (PANEL_W + GAP_X)
        y = MARGIN + row * (LABEL_H + PANEL_H + GAP_Y)
        # family label centered above the panel
        tw = draw.textlength(label, font=label_font)
        draw.text((x + (PANEL_W - tw) / 2, y + 2), label, fill="#1A1A1A", font=label_font)
        # panel
        panel = Image.open(ASSETS / f"render_fam_{fam}.png").convert("RGB")
        panel = panel.resize((PANEL_W, PANEL_H), Image.LANCZOS)
        py = y + LABEL_H
        canvas.paste(panel, (x, py))
        draw.rectangle([x, py, x + PANEL_W - 1, py + PANEL_H - 1], outline=BORDER, width=2)

    # legend strip: role category swatches
    ly = MARGIN + 2 * (LABEL_H + PANEL_H) + GAP_Y + LEGEND_GAP_TOP
    swatch = 34
    item_gap = 46
    widths = []
    for cat, _ in legend:
        widths.append(swatch + 12 + draw.textlength(cat, font=legend_font))
    total = sum(widths) + item_gap * (len(legend) - 1)
    lx = (canvas_w - total) / 2
    for (cat, color), w in zip(legend, widths):
        cy = ly + (LEGEND_H - swatch) / 2
        draw.rectangle([lx, cy, lx + swatch, cy + swatch], fill=color, outline="#666666")
        draw.text((lx + swatch + 12, ly + (LEGEND_H - 34) / 2 - 4), cat,
                  fill="#1A1A1A", font=legend_font)
        lx += w + item_gap

    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT)
    print(f"saved {OUT} ({canvas_w}x{canvas_h})")


if __name__ == "__main__":
    main()
