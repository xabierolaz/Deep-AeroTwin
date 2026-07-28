from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260703_real_cyclist_sppa_triposr_hunyuan"
SPPA_RUN = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260704_real_all_sppa_unified"
DEFAULT_OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_real_cyclist_probe_grid.png"


PANELS = [
    {
        "title": "Road input",
        "subtitle": "real crop, not GT",
        "image": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "inputs" / "biker_real_road_crop_512.png",
    },
    {
        "title": "Detector evidence",
        "subtitle": "COCO: person 0.56",
        "image": ROOT.parent
        / "papers"
        / "semantic_proxy_3d"
        / "experiments_root"
        / "sppa_detection_reference"
        / "20260703_user_cyclist"
        / "coco_yolo11n"
        / "cyclist_road_yolo_annotated.png",
    },
    {
        "title": "SPPA",
        "subtitle": "reviewed tag: biker",
        "image": SPPA_RUN / "views" / "models" / "sppa" / "biker" / "iso.png",
        "model": "sppa",
    },
    {
        "title": "TripoSR",
        "subtitle": "image-to-3D crop",
        "image": DEFAULT_RUN / "views" / "models" / "triposr_warm_r128_6gb" / "biker" / "iso.png",
        "model": "triposr_warm",
    },
    {
        "title": "Hunyuan3D",
        "subtitle": "image-to-3D crop",
        "image": DEFAULT_RUN / "views" / "models" / "hunyuan3d_2mini_turbo_rgba_6gb" / "biker" / "iso.png",
        "model": "hunyuan3d_2mini_turbo_shape",
    },
]


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def read_object_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return {row.get("model", ""): row for row in rows}


def metric_text(row: dict[str, str] | None) -> str:
    if not row:
        return ""
    try:
        wall_ms = float(row.get("wall_sec") or 0.0) * 1000.0
        tris = int(float(row.get("triangles") or 0.0))
        vram = row.get("torch_peak_reserved_mb")
        if vram:
            return f"{wall_ms:.1f} ms | {tris:,} tris | {float(vram):.0f} MB"
        return f"{wall_ms:.1f} ms | {tris:,} tris"
    except ValueError:
        return ""


def crop_nonwhite(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    diff = Image.new("L", rgba.size, 0)
    pixels = rgba.load()
    out = diff.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            if a > 20 and (abs(r - 255) > 10 or abs(g - 255) > 10 or abs(b - 255) > 10):
                out[x, y] = 255
    bbox = diff.getbbox()
    if bbox is None:
        return bg
    pad = 8
    return rgba.crop(
        (
            max(0, bbox[0] - pad),
            max(0, bbox[1] - pad),
            min(rgba.width, bbox[2] + pad),
            min(rgba.height, bbox[3] + pad),
        )
    )


def paste_panel_image(canvas: Image.Image, path: Path, box: tuple[int, int, int, int], crop_white: bool = True) -> None:
    image = Image.open(path).convert("RGBA")
    if crop_white:
        image = crop_nonwhite(image)
    x0, y0, x1, y1 = box
    image.thumbnail((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
    x = x0 + (x1 - x0 - image.width) // 2
    y = y0 + (y1 - y0 - image.height) // 2
    canvas.alpha_composite(image, (x, y))


def draw_centered_text(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], font: ImageFont.ImageFont, fill: tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((x0 + (x1 - x0 - w) / 2, y0 + (y1 - y0 - h) / 2), text, font=font, fill=fill)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the real cyclist SPPA/image-to-3D probe grid.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    output = args.output if args.output.is_absolute() else ROOT / args.output
    rows = read_object_rows(run_dir / "objects.csv")

    title_font = load_font(24, bold=True)
    subtitle_font = load_font(17)
    metric_font = load_font(14)
    note_font = load_font(16)

    cell_w = 245
    image_h = 220
    header_h = 72
    metric_h = 36
    note_h = 44
    pad = 16
    width = pad * 2 + cell_w * len(PANELS)
    height = pad + header_h + image_h + metric_h + note_h + pad
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    for index, panel in enumerate(PANELS):
        x0 = pad + index * cell_w
        x1 = x0 + cell_w
        draw_centered_text(draw, panel["title"], (x0, pad, x1, pad + 32), title_font, (20, 20, 20))
        draw_centered_text(draw, panel["subtitle"], (x0, pad + 34, x1, pad + header_h), subtitle_font, (90, 90, 90))
        image_box = (x0 + 14, pad + header_h, x1 - 14, pad + header_h + image_h)
        if panel["image"].exists():
            paste_panel_image(canvas, panel["image"], image_box, crop_white=index > 1)
        else:
            draw_centered_text(draw, "missing", image_box, subtitle_font, (160, 30, 30))
        metric = metric_text(rows.get(str(panel.get("model", "")))) if panel.get("model") else ""
        draw_centered_text(
            draw,
            metric,
            (x0, pad + header_h + image_h, x1, pad + header_h + image_h + metric_h),
            metric_font,
            (60, 60, 60),
        )
        draw.rectangle((x0, pad + header_h, x1, pad + header_h + image_h + metric_h), outline=(220, 220, 220), width=1)

    note = "Real cyclist probe: input evidence, not ground truth. SPPA uses a reviewed semantic tag; image-to-3D methods use the same low-quality crop."
    draw.text((pad, height - pad - note_h + 12), note, font=note_font, fill=(45, 45, 45))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, quality=95)
    print(output)


if __name__ == "__main__":
    main()
