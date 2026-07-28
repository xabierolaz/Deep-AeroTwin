from __future__ import annotations

import argparse
import ast
import csv
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPLAY_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "benchmarks"
    / "results"
    / "real_image_assumed_flight_replay.json"
)
DEFAULT_OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_real_detection_zoom_audit.png"
SPPA_RUN = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260704_real_all_sppa_unified"


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


def root_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else ROOT / path

def load_sppa_rows() -> dict[str, dict[str, str]]:
    path = SPPA_RUN / "objects.csv"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return {str(row.get("label") or ""): row for row in csv.DictReader(f)}


def fit_image(image: Image.Image, box: tuple[int, int], fill=(250, 250, 250)) -> Image.Image:
    target_w, target_h = box
    canvas = Image.new("RGB", (target_w, target_h), fill)
    im = image.convert("RGB")
    im.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
    canvas.paste(im, ((target_w - im.width) // 2, (target_h - im.height) // 2))
    return canvas


def crop_zoom_box(image: Image.Image, bbox: list[float], pad_ratio: float = 1.15) -> tuple[int, int, int, int]:
    w, h = image.size
    x1, y1, x2, y2 = [float(v) for v in bbox]
    bw = max(1.0, x2 - x1)
    bh = max(1.0, y2 - y1)
    pad = max(bw, bh) * pad_ratio
    cx = (x1 + x2) * 0.5
    cy = (y1 + y2) * 0.5
    left = max(0, int(round(cx - bw * 0.5 - pad)))
    top = max(0, int(round(cy - bh * 0.5 - pad)))
    right = min(w, int(round(cx + bw * 0.5 + pad)))
    bottom = min(h, int(round(cy + bh * 0.5 + pad)))
    return left, top, right, bottom


def draw_bbox(draw: ImageDraw.ImageDraw, bbox: tuple[float, float, float, float], color=(230, 55, 55), width: int = 4) -> None:
    x1, y1, x2, y2 = bbox
    for offset in range(width):
        draw.rectangle((x1 - offset, y1 - offset, x2 + offset, y2 + offset), outline=color)


def draw_polygon(
    base: Image.Image,
    polygon: list[list[float]],
    *,
    offset: tuple[float, float],
    scale: float,
    fill=(65, 190, 75, 88),
    outline=(30, 145, 45),
) -> None:
    if len(polygon) < 3:
        return
    pts = [((float(x) - offset[0]) * scale, (float(y) - offset[1]) * scale) for x, y in polygon]
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.polygon(pts, fill=fill)
    od.line(pts + [pts[0]], fill=outline + (255,), width=4)
    base.alpha_composite(overlay)


def full_tile(row: dict[str, Any], size: tuple[int, int]) -> Image.Image:
    path = root_path(row.get("image"))
    if path is None or not path.exists():
        return Image.new("RGB", size, (245, 245, 245))
    image = Image.open(path).convert("RGBA")
    original_w, original_h = image.size
    target_w, target_h = size
    scale = min(target_w / original_w, target_h / original_h)
    new_w = int(round(original_w * scale))
    new_h = int(round(original_h * scale))
    resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (250, 250, 250, 255))
    ox = (target_w - new_w) // 2
    oy = (target_h - new_h) // 2
    canvas.alpha_composite(resized, (ox, oy))
    bbox = row.get("bbox_xyxy") or []
    if len(bbox) == 4:
        scaled = tuple(ox + float(v) * scale if i % 2 == 0 else oy + float(v) * scale for i, v in enumerate(bbox))
        draw_bbox(ImageDraw.Draw(canvas), scaled, width=3)
    return canvas.convert("RGB")


def zoom_tile(row: dict[str, Any], size: tuple[int, int]) -> Image.Image:
    path = root_path(row.get("image"))
    bbox = row.get("bbox_xyxy") or []
    if path is None or not path.exists() or len(bbox) != 4:
        return Image.new("RGB", size, (245, 245, 245))
    image = Image.open(path).convert("RGBA")
    crop_box = crop_zoom_box(image, bbox)
    crop = image.crop(crop_box)
    target_w, target_h = size
    scale = min(target_w / crop.width, target_h / crop.height)
    new_w = int(round(crop.width * scale))
    new_h = int(round(crop.height * scale))
    resized = crop.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (250, 250, 250, 255))
    ox = (target_w - new_w) // 2
    oy = (target_h - new_h) // 2
    canvas.alpha_composite(resized, (ox, oy))
    offset = (float(crop_box[0]) - ox / scale, float(crop_box[1]) - oy / scale)

    native = row.get("native_detector_mask") or {}
    polygon = native.get("polygon") or []
    draw_polygon(canvas, polygon, offset=offset, scale=scale)
    x1, y1, x2, y2 = [float(v) for v in bbox]
    scaled_bbox = (
        (x1 - offset[0]) * scale,
        (y1 - offset[1]) * scale,
        (x2 - offset[0]) * scale,
        (y2 - offset[1]) * scale,
    )
    draw_bbox(ImageDraw.Draw(canvas), scaled_bbox, width=4)
    return canvas.convert("RGB")


def proxy_tile(case_id: str, model: str, size: tuple[int, int]) -> Image.Image:
    path = SPPA_RUN / "views" / "models" / model / case_id / "iso.png"
    if not path.exists():
        return Image.new("RGB", size, (245, 245, 245))
    image = Image.open(path).convert("RGBA")
    return fit_image(image, size)


def parse_dictish(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    text = str(value).strip()
    if not text:
        return {}
    try:
        loaded = json.loads(text)
        return loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        pass
    try:
        loaded = ast.literal_eval(text)
        return loaded if isinstance(loaded, dict) else {}
    except (SyntaxError, ValueError, TypeError):
        return {}


def dims_text(dims: dict[str, Any]) -> str:
    if not dims:
        return "-"
    return f"L {float(dims.get('length', 0.0)):.1f} W {float(dims.get('width', 0.0)):.1f} H {float(dims.get('height', 0.0)):.1f} m"


def metric_lines(row: dict[str, Any], sppa_row: dict[str, str] | None = None) -> list[str]:
    raw_dims = row.get("sppa_metric_dims_m") or {}
    fused_dims = parse_dictish((sppa_row or {}).get("fused_metric_dims_m"))
    unc = row.get("sppa_uncertainty") or {}
    bbox = row.get("bbox_xyxy") or []
    area = "-"
    path = root_path(row.get("image"))
    if len(bbox) == 4 and path and path.exists():
        with Image.open(path) as im:
            iw, ih = im.size
        area = f"{100.0 * max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1]) / float(iw * ih):.2f}%"
    low = bool(unc.get("shape_low_confidence"))
    gate = str((sppa_row or {}).get("observation_gate") or "-")
    gate_label = {
        "shape_low_confidence": "low-conf reject",
        "vehicle_metric_aspect_implausible": "vehicle aspect reject",
        "vertical_height_only_low_confidence_shape": "height-only obs",
        "vehicle_soft_low_confidence_fusion": "soft scale fusion",
        "vehicle_soft_aspect_fusion": "aspect fusion",
        "vehicle_soft_constraint_fusion": "constraint fusion",
        "accepted_dims_low_mask_quality": "dims only",
        "accepted": "obs accepted",
    }.get(gate, gate.replace("_", " "))
    applied = str((sppa_row or {}).get("observation_applied") or "").strip().lower() in {"true", "1", "yes"}
    image_geometry = str((sppa_row or {}).get("observation_image_geometry_applied") or "").strip().lower() in {"true", "1", "yes"}
    gate_state = "fused" if applied and "fusion" in gate else ("applied" if applied else "rejected")
    return [
        f"YOLOE: {row.get('detector_label')}",
        f"confidence: {float(row.get('detector_confidence') or 0.0):.2f}",
        f"mask pts: {row.get('native_detector_mask_point_count')}  bbox area: {area}",
        f"raw dims: {dims_text(raw_dims)}",
        f"SPPA dims: {dims_text(fused_dims)}",
        f"yaw: {float(row.get('yaw_deg') or 0.0):.1f} deg",
        f"low-confidence shape: {'yes' if low else 'no'}",
        f"SPPA gate: {gate_state}",
        f"image pose used: {'yes' if image_geometry else 'no'}",
        f"gate reason: {gate_label}",
    ]


def metrics_tile(row: dict[str, Any], size: tuple[int, int], sppa_row: dict[str, str] | None = None) -> Image.Image:
    canvas = Image.new("RGB", size, (252, 252, 252))
    draw = ImageDraw.Draw(canvas)
    title = load_font(18, bold=True)
    small = load_font(12)
    draw.text((14, 14), str(row.get("case_id")), font=title, fill=(25, 25, 25))
    y = 48
    for line in metric_lines(row, sppa_row):
        fill = (185, 35, 35) if line.endswith("yes") or "rejected" in line else (55, 55, 55)
        draw.text((14, y), line, font=small, fill=fill)
        y += 22
    draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline=(218, 218, 218), width=1)
    return canvas


def labeled(tile: Image.Image, title: str, subtitle: str, width: int, height: int) -> Image.Image:
    out = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(out)
    draw.text((8, 6), title, font=load_font(17, bold=True), fill=(20, 20, 20))
    draw.text((8, 28), subtitle, font=load_font(12), fill=(85, 85, 85))
    out.paste(tile, (0, 48))
    draw.rectangle((0, 48, width - 1, height - 1), outline=(225, 225, 225), width=1)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build zoomed real-input detector/mask audit for SPPA.")
    parser.add_argument("--replay-json", type=Path, default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    replay_json = args.replay_json if args.replay_json.is_absolute() else ROOT / args.replay_json
    out = args.out if args.out.is_absolute() else ROOT / args.out
    report = json.loads(replay_json.read_text(encoding="utf-8"))
    rows = list(report.get("rows") or [])
    sppa_rows = load_sppa_rows()

    cell_w = 260
    body_h = 300
    cell_h = body_h + 48
    headers = [
        ("Full image", "bbox context"),
        ("Detector zoom", "bbox + YOLOE mask"),
        ("Evidence", "quality summary"),
        ("SPPA", "final proxy"),
    ]
    width = cell_w * len(headers)
    header_h = 58
    height = header_h + cell_h * len(rows) + 34
    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    for idx, (title, subtitle) in enumerate(headers):
        x = idx * cell_w
        draw.text((x + 8, 8), title, font=load_font(18, bold=True), fill=(20, 20, 20))
        draw.text((x + 8, 32), subtitle, font=load_font(12), fill=(85, 85, 85))

    for row_idx, row in enumerate(rows):
        y = header_h + cell_h * row_idx
        case_id = str(row.get("case_id"))
        tiles = [
            labeled(full_tile(row, (cell_w, body_h)), case_id, "source frame", cell_w, cell_h),
            labeled(zoom_tile(row, (cell_w, body_h)), case_id, "zoomed evidence", cell_w, cell_h),
            labeled(metrics_tile(row, (cell_w, body_h), sppa_rows.get(case_id)), case_id, "quality summary", cell_w, cell_h),
            labeled(proxy_tile(case_id, "sppa", (cell_w, body_h)), case_id, "selected output", cell_w, cell_h),
        ]
        for col_idx, tile in enumerate(tiles):
            canvas.paste(tile, (col_idx * cell_w, y))

    note = (
        "Zoom audit: YOLOE masks/bboxes are detector evidence, not GT. "
        "SPPA fuses scale when plausible and rejects unsafe image pose."
    )
    draw.text((8, height - 26), note, font=load_font(13), fill=(50, 50, 50))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=95)
    print(json.dumps({"out": str(out), "rows": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
