"""Compose figures/fig_mission_twin_delta.png.

Conceptual mission illustration (no new quantitative data) for the
SPPA-MVFit reframe: when the image link is degraded or lost, SPPA
reconstructs the twin's delta from a lightweight semantic descriptor.

  (a) real world ......... real user-supplied flight photo of a lattice
                           tower (rea_flight_data/real_photos/tower.png),
                           red dashed box = measured YOLOE-26s detection
  (b) Cesium twin today .. UE/Cesium capture of matching terrain, tower-free
                           crop (the stale twin misses the object)
  (c) twin + SPPA proxy .. same crop with the lattice_tower family proxy
                           composited in (assets/render_fam_lattice_tower.png)

The annotated numbers are the sealed SPPA-MVFit values from
benchmarks/results/sppa_neural_flagship_wave.json
(descriptor_bytes mean 1449.7 B; inference_ms median 9.45 ms).

Sources (read-only, no new UE/Blender renders):
  rea_flight_data/real_photos/tower.png
  benchmarks/oblique_twin_wave/frames/t2_oblique45_az000.png
  tools/jgsa_figures/assets/render_fam_lattice_tower.png

Run: python fig_mission_twin_delta.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.font_manager as fm
import numpy as np
from matplotlib.colors import rgb_to_hsv
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]  # paper_semantic_proxy_3d/
SRC_REAL = Path(r"D:\Deep-AeroTwin-UE57-Test\rea_flight_data\real_photos\tower.png")
SRC_TWIN = ROOT / "benchmarks" / "oblique_twin_wave" / "frames" / "t2_oblique45_az000.png"
SRC_PROXY = ROOT / "tools" / "jgsa_figures" / "assets" / "render_fam_lattice_tower.png"
OUT = ROOT / "figures" / "fig_mission_twin_delta.png"

# Okabe-Ito (house palette, see jgsa_style.py)
OI_VERMILLION = "#D55E00"
INK = "#1A1A1A"
BORDER = "#C9CDD2"

# Layout: 2400 px wide, 3 equal panels 3:2, thin white gutters
PANEL_W, PANEL_H = 758, 505
GAP_X = 24
MARGIN_X = 39  # 3*758 + 2*24 + 2*39 = 2400
TOP_H, STRIP_H, BOTTOM_H = 36, 64, 30

# Source crops (left, top, right, bottom) in original pixels.
# (a) 2026-07-21: real user-supplied flight photo (640x480) instead of the
# Blender render; crop keeps the full tower (bbox y 86..395).
CROP_REAL = (0, 27, 640, 454)     # 640x427 (~3:2), full tower with margin
CROP_TWIN = (0, 20, 300, 220)     # 300x200 (3:2), tower-free: road + fields
# Tower bbox in the real photo = measured YOLOE-26s detection
# (experiments/sppa_detection_reference/20260721_real_flight_photos_yoloe26s_cpu)
BOX_REAL_SRC = (134.7, 86.0, 276.3, 394.9)

STRIPS = (
    "(a) real world now \u2014 flight photo",
    "(b) Cesium twin today \u2014 object missing",
    "(c) twin + SPPA proxy inserted",
)
CHIP_TEXT = "descriptor 1.45 kB \u00b7 fit 9.4 ms CPU"


def get_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(fm.findfont("DejaVu Sans"), size)


def dashed_rect(draw: ImageDraw.ImageDraw, box, color: str, width: int = 4,
                dash: int = 14, gap: int = 10) -> None:
    x0, y0, x1, y1 = box

    def hline(y, xa, xb):
        x = xa
        while x < xb:
            draw.line([(x, y), (min(x + dash, xb), y)], fill=color, width=width)
            x += dash + gap

    def vline(x, ya, yb):
        y = ya
        while y < yb:
            draw.line([(x, y), (x, min(y + dash, yb))], fill=color, width=width)
            y += dash + gap

    hline(y0, x0, x1)
    hline(y1, x0, x1)
    vline(x0, y0, y1)
    vline(x1, y0, y1)


def map_box(box, crop, out_size):
    sx = out_size[0] / (crop[2] - crop[0])
    sy = out_size[1] / (crop[3] - crop[1])
    return tuple(int(round(v)) for v in (
        (box[0] - crop[0]) * sx, (box[1] - crop[1]) * sy,
        (box[2] - crop[0]) * sx, (box[3] - crop[1]) * sy))


def load_crop(path: Path, crop, sharpen: bool = False) -> Image.Image:
    img = Image.open(path).convert("RGB").crop(crop)
    img = img.resize((PANEL_W, PANEL_H), Image.LANCZOS)
    if sharpen:
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=55, threshold=2))
    return img


def cutout_proxy(path: Path) -> Image.Image:
    """Segment the colored proxy from the light-gray studio background
    (background saturation ~ 0; proxy uses the saturated role palette)."""
    img = Image.open(path).convert("RGB")
    arr = np.asarray(img).astype(np.float32) / 255.0
    hsv = rgb_to_hsv(arr)
    mask = hsv[..., 1] > 0.20
    ys, xs = np.nonzero(mask)
    y0, y1 = np.percentile(ys, [0.2, 99.8]).astype(int)
    x0, x1 = np.percentile(xs, [0.2, 99.8]).astype(int)
    mask = mask[y0:y1 + 1, x0:x1 + 1]
    sub = img.crop((x0, y0, x1 + 1, y1 + 1))
    alpha = Image.fromarray((mask * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(1.2))
    sub.putalpha(alpha)
    return sub


def panel_real() -> Image.Image:
    img = load_crop(SRC_REAL, CROP_REAL)
    draw = ImageDraw.Draw(img)
    dashed_rect(draw, map_box(BOX_REAL_SRC, CROP_REAL, img.size), OI_VERMILLION)
    return img


def panel_twin() -> Image.Image:
    return load_crop(SRC_TWIN, CROP_TWIN, sharpen=True)


def panel_proxy() -> Image.Image:
    img = panel_twin()
    proxy = cutout_proxy(SRC_PROXY)
    target_h = int(PANEL_H * 0.60)
    scale = target_h / proxy.height
    proxy = proxy.resize((int(proxy.width * scale), target_h), Image.LANCZOS)
    base_x = int(PANEL_W * 0.52)          # ground contact point, x
    base_y = int(PANEL_H * 0.88)          # ground contact point, y
    px = base_x - proxy.width // 2
    py = base_y - proxy.height
    # soft contact shadow
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.ellipse([base_x - proxy.width // 2 - 14, base_y - 12,
                   base_x + proxy.width // 2 + 14, base_y + 12],
                  fill=(20, 15, 10, 95))
    shadow = shadow.filter(ImageFilter.GaussianBlur(9))
    img = Image.alpha_composite(img.convert("RGBA"), shadow)
    img.alpha_composite(proxy, (px, py))
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    pad = 10
    dashed_rect(draw, (px - pad, py - pad, px + proxy.width + pad,
                       py + proxy.height + pad), OI_VERMILLION)
    # annotation chip (bottom-left)
    font = get_font(23)
    tw = draw.textlength(CHIP_TEXT, font=font)
    ch, pad_x, pad_y = 40, 14, 12
    chip = Image.new("RGBA", (int(tw) + 2 * pad_x, ch), (26, 26, 26, 185))
    img_rgba = img.convert("RGBA")
    img_rgba.alpha_composite(chip, (pad_y, PANEL_H - ch - pad_y))
    draw = ImageDraw.Draw(img_rgba)
    draw.text((pad_y + pad_x, PANEL_H - ch - pad_y + ch // 2), CHIP_TEXT,
              fill="#FFFFFF", font=font, anchor="lm")
    return img_rgba.convert("RGB")


def main() -> None:
    canvas_w = 2 * MARGIN_X + 3 * PANEL_W + 2 * GAP_X
    canvas_h = TOP_H + PANEL_H + STRIP_H + BOTTOM_H
    canvas = Image.new("RGB", (canvas_w, canvas_h), "#FFFFFF")
    draw = ImageDraw.Draw(canvas)
    strip_font = get_font(30)

    panels = [panel_real(), panel_twin(), panel_proxy()]
    for i, (panel, strip) in enumerate(zip(panels, STRIPS)):
        x = MARGIN_X + i * (PANEL_W + GAP_X)
        y = TOP_H
        canvas.paste(panel, (x, y))
        draw.rectangle([x, y, x + PANEL_W - 1, y + PANEL_H - 1],
                       outline=BORDER, width=2)
        tw = draw.textlength(strip, font=strip_font)
        draw.text((x + (PANEL_W - tw) / 2, y + PANEL_H + STRIP_H / 2), strip,
                  fill=INK, font=strip_font, anchor="lm")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT, dpi=(300, 300))
    print(f"saved {OUT} ({canvas_w}x{canvas_h})")


if __name__ == "__main__":
    main()
