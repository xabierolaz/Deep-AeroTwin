#!/usr/bin/env python
"""Build a compact visual grid for the SPPA input-alignment audit.

The grid uses already-rendered orthographic ISO PNGs. It is a paper figure
builder, not a benchmark runner.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


LABELS = ["car", "truck", "tractor", "biker", "cow", "tree"]
INPUT_DIR = Path("experiments/sppa_sota_benchmark/inputs")
MESH_METHODS = [
    (
        "SPPA",
        Path("experiments/sppa_sota_benchmark/runs/20260705_sppa_current_label_only/views/models/sppa"),
        "mesh",
    ),
    (
        "TripoSR",
        Path("experiments/sppa_sota_benchmark/runs/20260701_195624/views/models/triposr_warm_r128_6gb"),
        "mesh",
    ),
    (
        "Hunyuan3D",
        Path("experiments/sppa_sota_benchmark/runs/20260701_195624/views/models/hunyuan3d_2mini_turbo_rgba_6gb"),
        "mesh",
    ),
    (
        "Shap-E",
        Path("experiments/sppa_sota_benchmark/runs/20260701_text3d_prompt_baselines/views/models/shap_e_text_k16_6gb"),
        "mesh",
    ),
    (
        "Point-E",
        Path("experiments/sppa_sota_benchmark/runs/20260701_text3d_prompt_baselines/views/models/point_e_text_sdf32_4096_6gb"),
        "mesh",
    ),
]


def input_row_metadata(path: Path) -> tuple[str, str]:
    if path.exists():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        items = list(manifest.get("items", []))
        any_detector = any(item.get("source_type") == "detector_crop" for item in items)
        if any_detector:
            return (
                "Text/tag\ninput",
                "First row shows the label-only text/tag input. Image crop/proxy inputs are omitted from this visual grid because they can resemble SPPA outputs; this is a qualitative audit, not a SOTA ranking.",
            )
    return (
        "Text/tag\ninput",
        "Text/tag row is label-only; RGBA crop inputs are omitted here to avoid proxy-input bias.",
    )


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def crop_nonwhite(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    bg = Image.new("RGBA", image.size, (255, 255, 255, 255))
    diff = Image.new("L", image.size, 0)
    pixels = image.load()
    out = diff.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if a > 20 and min(abs(r - 255), abs(g - 255), abs(b - 255)) > 12:
                out[x, y] = 255
    bbox = diff.getbbox()
    if bbox is None:
        return bg
    pad = 10
    left = max(0, bbox[0] - pad)
    top = max(0, bbox[1] - pad)
    right = min(image.width, bbox[2] + pad)
    bottom = min(image.height, bbox[3] + pad)
    return image.crop((left, top, right, bottom))


def paste_fit(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    max_w = x1 - x0
    max_h = y1 - y0
    image = crop_nonwhite(image)
    image.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    x = x0 + (max_w - image.width) // 2
    y = y0 + (max_h - image.height) // 2
    canvas.alpha_composite(image, (x, y))


def draw_center(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, font: ImageFont.ImageFont) -> None:
    x0, y0, x1, y1 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x0 + (x1 - x0 - tw) / 2, y0 + (y1 - y0 - th) / 2), text, fill=(20, 20, 20), font=font)

def draw_multiline_center(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, font: ImageFont.ImageFont) -> None:
    lines = text.splitlines()
    metrics = [draw.textbbox((0, 0), line, font=font) for line in lines]
    widths = [bbox[2] - bbox[0] for bbox in metrics]
    heights = [bbox[3] - bbox[1] for bbox in metrics]
    line_gap = 4
    total_h = sum(heights) + line_gap * max(0, len(lines) - 1)
    x0, y0, x1, y1 = box
    y = y0 + (y1 - y0 - total_h) / 2
    for line, width, height in zip(lines, widths, heights):
        draw.text((x0 + (x1 - x0 - width) / 2, y), line, fill=(20, 20, 20), font=font)
        y += height + line_gap


def draw_text_input_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str, font: ImageFont.ImageFont) -> None:
    x0, y0, x1, y1 = box
    pad = 10
    draw.rounded_rectangle(
        (x0 + pad, y0 + pad, x1 - pad, y1 - pad),
        radius=8,
        fill=(248, 249, 252),
        outline=(95, 110, 130),
        width=2,
    )
    draw.text(
        (x0 + pad + 12, y0 + pad + 10),
        "text:",
        fill=(95, 95, 95),
        font=load_font(18),
    )
    draw_multiline_center(draw, (x0 + pad, y0 + pad + 18, x1 - pad, y1 - pad), f'"{label}"', font)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--input-provenance",
        type=Path,
        default=Path("experiments/sppa_sota_benchmark/inputs/input_provenance.json"),
    )
    args = parser.parse_args()

    input_label, note = input_row_metadata(args.repo_root / args.input_provenance)
    methods = [(input_label, INPUT_DIR, "input")] + MESH_METHODS

    label_font = load_font(24)
    method_font = load_font(23)
    note_font = load_font(18)

    cell_w = 180
    cell_h = 145
    left_w = 135
    top_h = 58
    note_h = 38
    width = left_w + cell_w * len(LABELS)
    height = top_h + cell_h * len(methods) + note_h

    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    for col, label in enumerate(LABELS):
        x0 = left_w + col * cell_w
        draw_center(draw, (x0, 8, x0 + cell_w, top_h - 6), label, label_font)

    for row, (method, base, row_kind) in enumerate(methods):
        y0 = top_h + row * cell_h
        draw_multiline_center(draw, (0, y0, left_w - 8, y0 + cell_h), method, method_font)
        for col, label in enumerate(LABELS):
            x0 = left_w + col * cell_w
            cell = (x0 + 10, y0 + 8, x0 + cell_w - 10, y0 + cell_h - 8)
            if row_kind == "input":
                draw_text_input_card(draw, cell, label, label_font)
            else:
                path = args.repo_root / base / label / "iso.png"
                if path.exists():
                    paste_fit(canvas, Image.open(path), cell)
                else:
                    draw_center(draw, cell, "missing", note_font)
            draw.rectangle((x0, y0, x0 + cell_w, y0 + cell_h), outline=(220, 220, 220), width=1)

    draw.line((left_w, top_h, width, top_h), fill=(120, 120, 120), width=2)
    draw.line((left_w, 0, left_w, top_h + cell_h * len(methods)), fill=(120, 120, 120), width=2)
    draw.text((left_w, top_h + cell_h * len(methods) + 8), note, fill=(45, 45, 45), font=note_font)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(args.output, quality=95)


if __name__ == "__main__":
    main()
