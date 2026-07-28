from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "3d_to_dataset_xabi" / "dataset"
DEFAULT_ASSETS = ROOT / "3d_to_dataset_xabi" / "assets"
DEFAULT_OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_synthetic_yolo"
CLASS_TO_ID = {"biker": 0, "cow": 1, "tower": 2}
DEFAULT_IMAGE_SIZE = 640


def repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_font(size: int) -> ImageFont.ImageFont:
    for candidate in [Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/segoeui.ttf")]:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def read_label(path: Path) -> tuple[int, float, float, float, float]:
    line = path.read_text(encoding="utf-8").strip().splitlines()[0]
    cls, xc, yc, w, h = line.split()[:5]
    return int(cls), float(xc), float(yc), float(w), float(h)


def bbox_norm_to_px(box: tuple[float, float, float, float], width: int, height: int) -> dict[str, int | float]:
    xc, yc, bw, bh = box
    x1 = max(0, int(round((xc - bw / 2.0) * width)))
    y1 = max(0, int(round((yc - bh / 2.0) * height)))
    x2 = min(width, int(round((xc + bw / 2.0) * width)))
    y2 = min(height, int(round((yc + bh / 2.0) * height)))
    return {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "w": max(0, x2 - x1),
        "h": max(0, y2 - y1),
        "aspect": (max(0, x2 - x1) / max(1, y2 - y1)),
    }


def find_sample(dataset: Path, label: str) -> tuple[str, Path, Path]:
    for split in ["test", "val", "train"]:
        label_dir = dataset / "labels" / split
        image_dir = dataset / "images" / split
        for label_path in sorted(label_dir.glob(f"{label}_*.txt")):
            image_path = image_dir / (label_path.stem + ".jpg")
            if image_path.exists():
                return split, image_path, label_path
    raise FileNotFoundError(f"no sample found for {label}")


def crop_item(image: Image.Image, bbox_px: dict[str, int | float], pad_ratio: float = 0.12) -> Image.Image:
    x1 = int(bbox_px["x1"])
    y1 = int(bbox_px["y1"])
    x2 = int(bbox_px["x2"])
    y2 = int(bbox_px["y2"])
    pad_x = int(round((x2 - x1) * pad_ratio))
    pad_y = int(round((y2 - y1) * pad_ratio))
    left = max(0, x1 - pad_x)
    top = max(0, y1 - pad_y)
    right = min(image.width, x2 + pad_x)
    bottom = min(image.height, y2 + pad_y)
    return image.crop((left, top, right, bottom))


def draw_contact_sheet(items: list[dict[str, Any]], out_path: Path) -> None:
    cell_w, cell_h = 260, 210
    top_h = 44
    sheet = Image.new("RGB", (cell_w * len(items), top_h + cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(22)
    for idx, item in enumerate(items):
        x0 = idx * cell_w
        draw.text((x0 + 12, 10), item["label"], fill=(20, 20, 20), font=title_font)
        if item.get("crop_image"):
            crop = Image.open(ROOT / item["crop_image"]).convert("RGB")
            crop.thumbnail((cell_w - 24, cell_h - 24), Image.Resampling.LANCZOS)
            sheet.paste(crop, (x0 + (cell_w - crop.width) // 2, top_h + (cell_h - crop.height) // 2))
        else:
            draw.text((x0 + 18, top_h + 64), "bbox-only\n(no image)", fill=(80, 80, 80), font=title_font)
        draw.rectangle((x0, 0, x0 + cell_w - 1, top_h + cell_h - 1), outline=(210, 210, 210))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=95)


def build_manifest(dataset: Path, assets_dir: Path, out_dir: Path, labels: list[str], fallback_image_size: int) -> dict[str, Any]:
    crops_dir = out_dir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for label in labels:
        split, image_path, label_path = find_sample(dataset, label)
        class_id, xc, yc, bw, bh = read_label(label_path)
        image: Image.Image | None
        try:
            image = Image.open(image_path).convert("RGB")
            image_width, image_height = image.width, image.height
        except Exception:
            image = None
            image_width = fallback_image_size
            image_height = fallback_image_size
        bbox_px = bbox_norm_to_px((xc, yc, bw, bh), image_width, image_height)
        crop_path: Path | None = None
        if image is not None:
            crop = crop_item(image, bbox_px)
            crop_path = crops_dir / f"{label}_{image_path.stem}_crop.jpg"
            crop.save(crop_path, quality=95)
        asset_path = assets_dir / f"{label}.obj"
        items.append(
            {
                "label": label,
                "class_id": class_id,
                "split": split,
                "source_image": repo_rel(image_path),
                "source_label": repo_rel(label_path),
                "crop_image": repo_rel(crop_path) if crop_path else None,
                "source_type": "synthetic_yolo_reference_crop",
                "is_ground_truth": True,
                "ground_truth_scope": "synthetic 2D class label and bounding box only",
                "detector": None,
                "has_bbox": True,
                "has_mask": False,
                "has_reference_mesh": asset_path.exists(),
                "reference_mesh": repo_rel(asset_path) if asset_path.exists() else None,
                "reference_mesh_scope": "class asset used by synthetic renderer, not per-instance 3D pose ground truth",
                "image_readable": image is not None,
                "image_size_px": {"width": image_width, "height": image_height},
                "bbox_yolo_norm": {"xc": xc, "yc": yc, "w": bw, "h": bh},
                "bbox_px": bbox_px,
            }
        )
    contact_sheet = out_dir / "synthetic_detection_reference_contact_sheet.jpg"
    draw_contact_sheet(items, contact_sheet)
    return {
        "schema": "SPPA-DETECTION-REFERENCE-0.1",
        "created_utc": "2026-07-03T00:00:00Z",
        "dataset": repo_rel(dataset),
        "claim": "Synthetic YOLO reference labels with ground-truth 2D class/bbox annotations. Not real detector output, not flight imagery, and not 3D ground truth. Some legacy files use image extensions for non-image numeric dumps, so entries may be bbox-only.",
        "contact_sheet": repo_rel(contact_sheet),
        "items": items,
    }


def write_markdown(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Synthetic Detection Reference Manifest",
        "",
        manifest["claim"],
        "",
        f"- Dataset: `{manifest['dataset']}`",
        f"- Items: {len(manifest['items'])}",
        f"- Contact sheet: `{manifest['contact_sheet']}`",
        f"- Readable images: {sum(1 for item in manifest['items'] if item.get('image_readable'))}",
        "",
        "| Label | Split | GT Scope | BBox px | Crop |",
        "|---|---|---|---|---|",
    ]
    for item in manifest["items"]:
        bbox = item["bbox_px"]
        bbox_text = f"{bbox['x1']},{bbox['y1']} - {bbox['x2']},{bbox['y2']}"
        crop = item["crop_image"] if item.get("crop_image") else "bbox-only/no-readable-image"
        lines.append(f"| {item['label']} | {item['split']} | {item['ground_truth_scope']} | {bbox_text} | `{crop}` |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create SPPA synthetic detection/reference crop manifest from the YOLO synthetic dataset.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--assets-dir", type=Path, default=DEFAULT_ASSETS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--labels", nargs="+", default=["biker", "cow", "tower"])
    parser.add_argument("--fallback-image-size", type=int, default=DEFAULT_IMAGE_SIZE)
    args = parser.parse_args()

    manifest = build_manifest(args.dataset, args.assets_dir, args.out_dir, args.labels, args.fallback_image_size)
    manifest_path = args.out_dir / "synthetic_detection_reference_manifest.json"
    md_path = args.out_dir / "synthetic_detection_reference_manifest.md"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_markdown(md_path, manifest)
    print(manifest_path)
    print(md_path)


if __name__ == "__main__":
    main()
