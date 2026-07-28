from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = ROOT / "yolo" / "weights" / "yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt"


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(resolved)


def parse_bbox(text: str) -> tuple[int, int, int, int]:
    parts = [int(round(float(part.strip()))) for part in text.split(",")]
    if len(parts) != 4:
        raise ValueError("--manual-bbox must be x1,y1,x2,y2")
    x1, y1, x2, y2 = parts
    if x2 <= x1 or y2 <= y1:
        raise ValueError("--manual-bbox must have x2>x1 and y2>y1")
    return x1, y1, x2, y2


def clamp_bbox(bbox: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    return max(0, x1), max(0, y1), min(width, x2), min(height, y2)


def pad_bbox(bbox: tuple[int, int, int, int], width: int, height: int, pad_frac: float) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    pad = int(round(max(x2 - x1, y2 - y1) * pad_frac))
    return clamp_bbox((x1 - pad, y1 - pad, x2 + pad, y2 + pad), width, height)


def square_bbox(bbox: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    side = max(x2 - x1, y2 - y1)
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    half = side / 2.0
    return clamp_bbox((int(cx - half), int(cy - half), int(cx + half), int(cy + half)), width, height)


def bbox_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = float((ix2 - ix1) * (iy2 - iy1))
    area_a = float((ax2 - ax1) * (ay2 - ay1))
    area_b = float((bx2 - bx1) * (by2 - by1))
    return inter / (area_a + area_b - inter)


def draw_label(image, text: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.5
    thickness = 1
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    y0 = max(0, y - th - 6)
    cv2.rectangle(image, (x, y0), (min(image.shape[1] - 1, x + tw + 6), y0 + th + 6), color, -1)
    cv2.putText(image, text, (x + 3, y0 + th + 3), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)


def detections_from_result(result: Any, target_hints: set[str], manual_roi: tuple[int, int, int, int], width: int, height: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if result.boxes is None:
        return rows
    for box in result.boxes:
        cls_id = int(box.cls[0].item())
        conf = float(box.conf[0].item())
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
        bbox = clamp_bbox((int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))), width, height)
        name = str(result.names.get(cls_id, cls_id))
        iou = bbox_iou(bbox, manual_roi)
        rows.append(
            {
                "class_id": cls_id,
                "class_name": name,
                "confidence": conf,
                "xyxy": [x1, y1, x2, y2],
                "target_hint": name.lower() in target_hints,
                "manual_roi_iou": iou,
                "overlaps_manual_roi": iou >= 0.02,
            }
        )
    rows.sort(
        key=lambda item: (
            bool(item["overlaps_manual_roi"]),
            bool(item["target_hint"]),
            float(item["manual_roi_iou"]),
            float(item["confidence"]),
        ),
        reverse=True,
    )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run YOLO over a user-supplied object image and prepare an image-to-3D crop.")
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--semantic-label", required=True)
    parser.add_argument("--manual-bbox", required=True, help="x1,y1,x2,y2 ROI around the intended object.")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--target-hints", default="", help="Comma-separated detector class names that count as target hints.")
    parser.add_argument("--conf", type=float, default=0.05)
    parser.add_argument("--imgsz", type=int, default=1280)
    args = parser.parse_args()

    image_path = resolve_path(args.image)
    out_dir = resolve_path(args.out_dir)
    model_path = resolve_path(args.model) if args.model.exists() or (ROOT / args.model).exists() else args.model
    out_dir.mkdir(parents=True, exist_ok=True)

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"could not read image: {image_path}")
    height, width = image.shape[:2]
    manual_roi = clamp_bbox(parse_bbox(args.manual_bbox), width, height)
    target_hints = {item.strip().lower() for item in args.target_hints.split(",") if item.strip()}
    target_hints.add(args.semantic_label.lower())

    result = YOLO(str(model_path)).predict(source=image, conf=args.conf, imgsz=args.imgsz, verbose=False)[0]
    detections = detections_from_result(result, target_hints, manual_roi, width, height)

    annotated = image.copy()
    mx1, my1, mx2, my2 = manual_roi
    cv2.rectangle(annotated, (mx1, my1), (mx2, my2), (40, 220, 220), 2)
    draw_label(annotated, f"manual ROI: {args.semantic_label}", mx1, my1, (40, 180, 180))
    for det in detections:
        x1, y1, x2, y2 = [int(round(v)) for v in det["xyxy"]]
        color = (0, 180, 0) if det["overlaps_manual_roi"] else (0, 120, 255)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        draw_label(annotated, f"{det['class_name']} {det['confidence']:.2f}", x1, y1, color)
    if not detections:
        draw_label(annotated, "YOLO: no detections", 18, 28, (0, 0, 220))

    annotated_path = out_dir / f"{args.slug}_yolo_annotated.png"
    cv2.imwrite(str(annotated_path), annotated)

    usable = [det for det in detections if det["overlaps_manual_roi"] and det["target_hint"]]
    if usable:
        source_bbox = clamp_bbox(tuple(int(round(v)) for v in usable[0]["xyxy"]), width, height)
        crop_source = "yolo_detection"
        generated_tag = {
            "label": usable[0]["class_name"],
            "confidence": usable[0]["confidence"],
            "source": "yolo_detection",
            "manual_roi_iou": usable[0]["manual_roi_iou"],
        }
    else:
        source_bbox = manual_roi
        crop_source = "manual_roi_fallback"
        generated_tag = {
            "label": args.semantic_label,
            "confidence": None,
            "source": "user_expected_semantic_tag_not_detector_output",
        }

    crop_bbox = square_bbox(pad_bbox(source_bbox, width, height, 0.18), width, height)
    x1, y1, x2, y2 = crop_bbox
    crop = image[y1:y2, x1:x2]
    crop_path = out_dir / f"{args.slug}_image_to_3d_input.png"
    crop_512_path = out_dir / f"{args.slug}_image_to_3d_input_512.png"
    cv2.imwrite(str(crop_path), crop)
    cv2.imwrite(str(crop_512_path), cv2.resize(crop, (512, 512), interpolation=cv2.INTER_CUBIC))

    manifest = {
        "schema": "SPPA-USER-OBJECT-YOLO-PROBE-0.1",
        "semantic_label": args.semantic_label,
        "image": display_path(image_path),
        "model": display_path(model_path) if isinstance(model_path, Path) else str(model_path),
        "image_size": {"width": width, "height": height},
        "manual_roi_xyxy": list(manual_roi),
        "conf": args.conf,
        "imgsz": args.imgsz,
        "detections": detections,
        "generated_tag": generated_tag,
        "claim_boundary": "User-supplied image used as input evidence. It is not ground truth, not a segmentation mask, and not 3D reference geometry.",
        "outputs": {
            "annotated_image": display_path(annotated_path),
            "image_to_3d_input_crop": display_path(crop_path),
            "image_to_3d_input_crop_512": display_path(crop_512_path),
            "crop_bbox_xyxy": list(crop_bbox),
            "crop_source": crop_source,
        },
    }
    manifest_path = out_dir / f"{args.slug}_yolo_probe.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "detections": len(detections), "tag": generated_tag}, indent=2))


if __name__ == "__main__":
    main()
