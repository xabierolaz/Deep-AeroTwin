from __future__ import annotations

import argparse
import csv
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260705_sppa_input_mode_comparison"
DEFAULT_OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_input_mode_comparison_grid.png"

CASES = [
    (
        "biker",
        ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "inputs" / "biker_real_road_crop_512.png",
    ),
    (
        "tower",
        ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "inputs" / "tower_real_mountain_crop_512.png",
    ),
    (
        "tractor",
        ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "inputs" / "tractor_real_mountain_crop_512.png",
    ),
    (
        "tractor_trailer",
        ROOT.parent
        / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
        / "sppa_sota_benchmark"
        / "inputs"
        / "tractor_trailer_real_mountain_crop_512.png",
    ),
]

MODES = [
    ("tag_only", "Text/tag only", "reviewed phrase"),
    ("detector_metric", "YOLOE + metric", "real detector + replay"),
    ("detector_metric_visual", "YOLOE + metric + visual", "adds agnostic cues"),
]


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = [
        "arialbd.ttf" if bold else "arial.ttf",
        "calibrib.ttf" if bold else "calibri.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
    ]
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def rows_by_case_mode(run_dir: Path) -> dict[tuple[str, str], dict[str, str]]:
    rows: dict[tuple[str, str], dict[str, str]] = {}
    path = run_dir / "objects.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rows[(str(row.get("label") or ""), str(row.get("model") or ""))] = row
    return rows


def crop_nonwhite(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    mask = Image.new("L", rgba.size, 0)
    pix = rgba.load()
    out = mask.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pix[x, y]
            if a > 20 and (abs(r - 255) > 8 or abs(g - 255) > 8 or abs(b - 255) > 8):
                out[x, y] = 255
    bbox = mask.getbbox()
    if bbox is None:
        return rgba
    pad = 8
    return rgba.crop(
        (
            max(0, bbox[0] - pad),
            max(0, bbox[1] - pad),
            min(rgba.width, bbox[2] + pad),
            min(rgba.height, bbox[3] + pad),
        )
    )


def paste_fit(canvas: Image.Image, path: Path, box: tuple[int, int, int, int], crop_white: bool) -> None:
    if not path.exists():
        return
    image = Image.open(path).convert("RGBA")
    if crop_white:
        image = crop_nonwhite(image)
    x0, y0, x1, y1 = box
    image.thumbnail((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
    canvas.alpha_composite(image, (x0 + (x1 - x0 - image.width) // 2, y0 + (y1 - y0 - image.height) // 2))


def centered(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], font: ImageFont.ImageFont, fill: tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((x0 + (x1 - x0 - (bbox[2] - bbox[0])) / 2, y0 + (y1 - y0 - (bbox[3] - bbox[1])) / 2), text, font=font, fill=fill)


def multiline(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    line_gap: int = 3,
) -> None:
    x0, y0, x1, y1 = box
    lines: list[str] = []
    for raw in text.splitlines():
        lines.extend(wrap(raw, width=28) or [""])
    metrics = [draw.textbbox((0, 0), line, font=font) for line in lines]
    heights = [bbox[3] - bbox[1] for bbox in metrics]
    total_h = sum(heights) + line_gap * max(0, len(lines) - 1)
    y = y0 + max(0, (y1 - y0 - total_h) / 2)
    for line, bbox, h in zip(lines, metrics, heights):
        w = bbox[2] - bbox[0]
        draw.text((x0 + (x1 - x0 - w) / 2, y), line, font=font, fill=fill)
        y += h + line_gap


def model_view(run_dir: Path, mode: str, case: str) -> Path:
    return run_dir / "views" / "models" / mode / case / "iso.png"


def metric_text(row: dict[str, str] | None) -> str:
    if not row:
        return "missing"
    try:
        tris = int(float(row.get("triangles") or 0.0))
        wall_ms = float(row.get("wall_sec") or 0.0) * 1000.0
    except ValueError:
        tris = 0
        wall_ms = 0.0
    lines = [
        str(row.get("semantic_label") or ""),
        str(row.get("effective_dims_text") or ""),
        f"{tris:,} tris | {wall_ms:.1f} ms",
    ]
    if str(row.get("visual_shape_conditioning_applied") or "").lower() in {"true", "1", "yes"}:
        added = row.get("visual_shape_conditioning_added_triangles") or "0"
        lines.append(f"visual +{added} tris")
    return "\n".join(line for line in lines if line)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render SPPA input-mode comparison grid.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    output = args.output if args.output.is_absolute() else ROOT / args.output
    rows = rows_by_case_mode(run_dir)
    title_font = load_font(19, bold=True)
    subtitle_font = load_font(14)
    label_font = load_font(20, bold=True)
    metric_font = load_font(12)
    note_font = load_font(14)

    left_w = 156
    cell_w = 250
    input_w = 220
    header_h = 62
    image_h = 160
    metric_h = 70
    row_h = image_h + metric_h + 12
    note_h = 44
    pad = 16
    width = left_w + input_w + cell_w * len(MODES) + pad * 2
    height = pad + header_h + row_h * len(CASES) + note_h + pad
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    centered(draw, "Input crop", (left_w, pad, left_w + input_w, pad + 30), title_font, (25, 25, 25))
    centered(draw, "real image, not GT", (left_w, pad + 30, left_w + input_w, pad + header_h), subtitle_font, (85, 85, 85))
    for col, (_, title, subtitle) in enumerate(MODES):
        x0 = left_w + input_w + col * cell_w
        centered(draw, title, (x0, pad, x0 + cell_w, pad + 30), title_font, (25, 25, 25))
        centered(draw, subtitle, (x0, pad + 30, x0 + cell_w, pad + header_h), subtitle_font, (85, 85, 85))

    for row_index, (case, input_path) in enumerate(CASES):
        y0 = pad + header_h + row_index * row_h
        display_case = "tractor+trailer" if case == "tractor_trailer" else case
        centered(draw, display_case, (0, y0, left_w, y0 + image_h + metric_h), label_font, (25, 25, 25))
        input_box = (left_w + 10, y0 + 8, left_w + input_w - 10, y0 + image_h)
        paste_fit(canvas, input_path, input_box, crop_white=False)
        multiline(draw, "real crop\nno 3D reference", (left_w + 6, y0 + image_h, left_w + input_w - 6, y0 + image_h + metric_h), metric_font, (60, 60, 60))
        draw.rectangle((left_w, y0, left_w + input_w, y0 + image_h + metric_h), outline=(222, 222, 222), width=1)
        for col, (mode, _, _) in enumerate(MODES):
            x0 = left_w + input_w + col * cell_w
            image_box = (x0 + 10, y0 + 8, x0 + cell_w - 10, y0 + image_h)
            paste_fit(canvas, model_view(run_dir, mode, case), image_box, crop_white=True)
            row = rows.get((case, mode))
            multiline(draw, metric_text(row), (x0 + 6, y0 + image_h, x0 + cell_w - 6, y0 + image_h + metric_h), metric_font, (55, 55, 55))
            draw.rectangle((x0, y0, x0 + cell_w, y0 + image_h + metric_h), outline=(222, 222, 222), width=1)

    note = (
        "Same SPPA generator under three input contracts. Visual cues condition only existing semantic roles; "
        "they do not create new classes, ground-truth masks, or dense reconstructions."
    )
    note_lines = wrap(note, width=150)
    y = height - pad - note_h + 8
    for line in note_lines[:2]:
        draw.text((pad, y), line, font=note_font, fill=(45, 45, 45))
        y += 18
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, quality=95)
    print(output)


if __name__ == "__main__":
    main()
