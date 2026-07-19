"""Compose figures/fig_fitting_sequence_blender.png.

Four panels in a row for case test-csg_id-articulated_vehicle-013 (clean):
  (a) observed masks (top | side), from the sealed observation_masks.npy
  (b) actor at the mask-driven initial theta   (render_fit_init.png)
  (c) actor at the sealed fitted theta          (render_fit_fit.png)
  (d) GT mesh, 64^3 voxel grid -> marching cubes (render_fit_gt.png)

The voxel IoU annotation (0.571) is read from assets/blender_assets.json,
whose export asserted equality with the sealed raw_metrics.csv value.

Panels (b)-(d) are Blender renders produced by blender/render_fitting_sequence.py
with a shared camera fitted to the GT bounding box.

Run: python compose_fitting_sequence.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.font_manager as fm
from PIL import Image, ImageDraw, ImageFont

REPO = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d")
ASSETS = REPO / "tools" / "jgsa_figures" / "assets"
OUT = REPO / "figures" / "fig_fitting_sequence_blender.png"
TRUCK = "test-csg_id-articulated_vehicle-013"

PANEL_W, PANEL_H = 880, 660
LABEL_H = 54
GAP_X = 24
MARGIN = 40
BORDER = "#C9CDD2"


def get_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(fm.findfont("DejaVu Sans"), size)


def main() -> None:
    assets = json.loads((ASSETS / "blender_assets.json").read_text(encoding="utf-8"))
    iou = float(assets["cases"][TRUCK]["voxel_iou"])

    labels = [
        "(a) observed masks: top | side",
        "(b) initial \u03b8 (mask-driven)",
        f"(c) fitted \u03b8 \u2014 voxel IoU {iou:.3f}",
        "(d) ground truth (64\u00b3 mesh)",
    ]
    renders = [None, "render_fit_init.png", "render_fit_fit.png", "render_fit_gt.png"]

    canvas_w = 2 * MARGIN + 4 * PANEL_W + 3 * GAP_X
    canvas_h = MARGIN + LABEL_H + PANEL_H + MARGIN
    canvas = Image.new("RGB", (canvas_w, canvas_h), "#FFFFFF")
    draw = ImageDraw.Draw(canvas)
    label_font = get_font(36)

    for i, (label, render) in enumerate(zip(labels, renders)):
        x = MARGIN + i * (PANEL_W + GAP_X)
        y = MARGIN
        tw = draw.textlength(label, font=label_font)
        draw.text((x + (PANEL_W - tw) / 2, y + 4), label, fill="#1A1A1A", font=label_font)
        py = y + LABEL_H
        if render is None:
            # masks panel: black object on white, nearest-neighbor upscale
            sub = Image.new("RGB", (PANEL_W, PANEL_H), "#FFFFFF")
            masks = Image.open(ASSETS / "masks_truck.png").convert("RGB")
            scale = min((PANEL_W - 80) / masks.width, (PANEL_H - 80) / masks.height)
            scale = max(1, int(scale))
            masks = masks.resize((masks.width * scale, masks.height * scale),
                                 Image.NEAREST)
            sub.paste(masks, ((PANEL_W - masks.width) // 2,
                              (PANEL_H - masks.height) // 2))
        else:
            sub = Image.open(ASSETS / render).convert("RGB")
            sub = sub.resize((PANEL_W, PANEL_H), Image.LANCZOS)
        canvas.paste(sub, (x, py))
        draw.rectangle([x, py, x + PANEL_W - 1, py + PANEL_H - 1], outline=BORDER, width=2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT)
    print(f"saved {OUT} ({canvas_w}x{canvas_h})")


if __name__ == "__main__":
    main()
