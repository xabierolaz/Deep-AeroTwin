from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IMAGE = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_user_cyclist" / "cyclist_road_input.png"
DEFAULT_MODEL = ROOT / "yolo" / "weights" / "yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt"
DEFAULT_OUT_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_user_cyclist"


TARGET_HINTS = {"biker", "bike", "bicycle", "cyclist", "person", "motorcycle", "motorbike"}


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def parse_bbox(text: str | None) -> tuple[int, int, int, int] | None:
    if not text:
        return None
    parts = [int(round(float(p.strip()))) for p in text.split(",")]
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
    bw = x2 - x1
    bh = y2 - y1
    pad = int(round(max(bw, bh) * pad_frac))
    return clamp_bbox((x1 - pad, y1 - pad, x2 + pad, y2 + pad), width, height)


def square_bbox(bbox: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    side = max(x2 - x1, y2 - y1)
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
    area_a = float(max(0, ax2 - ax1) * max(0, ay2 - ay1))
    area_b = float(max(0, bx2 - bx1) * max(0, by2 - by1))
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


def draw_label(image: np.ndarray, text: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.5
    thickness = 1
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    y0 = max(0, y - th - 6)
    cv2.rectangle(image, (x, y0), (min(image.shape[1] - 1, x + tw + 6), y0 + th + 6), color, -1)
    cv2.putText(image, text, (x + 3, y0 + th + 3), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)


def result_detections(result: Any) -> list[dict[str, Any]]:
    names = result.names
    detections: list[dict[str, Any]] = []
    if result.boxes is None:
        return detections
    for box in result.boxes:
        cls_id = int(box.cls[0].item())
        conf = float(box.conf[0].item())
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
        name = str(names.get(cls_id, cls_id))
        detections.append(
            {
                "class_id": cls_id,
                "class_name": name,
                "confidence": conf,
                "xyxy": [x1, y1, x2, y2],
                "target_hint": name.lower() in TARGET_HINTS,
            }
        )
    detections.sort(key=lambda item: (bool(item["target_hint"]), float(item["confidence"])), reverse=True)
    return detections


def choose_crop_bbox(
    detections: list[dict[str, Any]],
    manual_bbox: tuple[int, int, int, int] | None,
    width: int,
    height: int,
) -> tuple[tuple[int, int, int, int] | None, str]:
    usable_detections = [
        det
        for det in detections
        if manual_bbox is None or bool(det.get("overlaps_manual_roi"))
    ]
    if usable_detections:
        best = usable_detections[0]
        bbox = tuple(int(round(v)) for v in best["xyxy"])
        return square_bbox(pad_bbox(clamp_bbox(bbox, width, height), width, height, 0.35), width, height), "yolo_detection"
    if manual_bbox:
        return square_bbox(pad_bbox(clamp_bbox(manual_bbox, width, height), width, height, 0.15), width, height), "manual_roi_fallback"
    return None, "none"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a reproducible YOLO probe over the user-supplied cyclist image.")
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--conf", type=float, default=0.05)
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument(
        "--manual-bbox",
        default="320,255,520,440",
        help="x1,y1,x2,y2 ROI used only when YOLO produces no boxes.",
    )
    args = parser.parse_args()

    image_path = resolve_path(args.image)
    model_path = resolve_path(args.model) if args.model.exists() or (ROOT / args.model).exists() else args.model
    out_dir = resolve_path(args.out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"could not read image: {image_path}")
    height, width = image.shape[:2]

    model = YOLO(str(model_path))
    result = model.predict(source=image, conf=args.conf, imgsz=args.imgsz, verbose=False)[0]
    detections = result_detections(result)
    manual_bbox = parse_bbox(args.manual_bbox)
    manual_bbox = clamp_bbox(manual_bbox, width, height) if manual_bbox else None
    if manual_bbox:
        for det in detections:
            det_bbox = clamp_bbox(tuple(int(round(v)) for v in det["xyxy"]), width, height)
            iou = bbox_iou(det_bbox, manual_bbox)
            det["manual_roi_iou"] = iou
            det["overlaps_manual_roi"] = iou >= 0.02
        detections.sort(
            key=lambda item: (
                bool(item.get("overlaps_manual_roi")),
                bool(item["target_hint"]),
                float(item.get("manual_roi_iou", 0.0)),
                float(item["confidence"]),
            ),
            reverse=True,
        )

    annotated = image.copy()
    for det in detections:
        x1, y1, x2, y2 = [int(round(v)) for v in det["xyxy"]]
        color = (0, 180, 0) if det["target_hint"] else (0, 120, 255)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        draw_label(annotated, f"{det['class_name']} {det['confidence']:.2f}", x1, y1, color)

    if not detections:
        draw_label(annotated, "YOLO: no detections at configured threshold", 18, 28, (0, 0, 220))

    annotated_path = out_dir / "cyclist_road_yolo_annotated.png"
    cv2.imwrite(str(annotated_path), annotated)

    crop_bbox, crop_source = choose_crop_bbox(detections, manual_bbox, width, height)
    crop_path = None
    crop_512_path = None
    if crop_bbox is not None:
        x1, y1, x2, y2 = crop_bbox
        crop = image[y1:y2, x1:x2]
        crop_path = out_dir / "cyclist_image_to_3d_input.png"
        cv2.imwrite(str(crop_path), crop)
        crop_512 = cv2.resize(crop, (512, 512), interpolation=cv2.INTER_CUBIC)
        crop_512_path = out_dir / "cyclist_image_to_3d_input_512.png"
        cv2.imwrite(str(crop_512_path), crop_512)

    usable_detections = [
        det
        for det in detections
        if manual_bbox is None or bool(det.get("overlaps_manual_roi"))
    ]
    generated_tag = None
    if usable_detections:
        best = usable_detections[0]
        generated_tag = {
            "label": best["class_name"],
            "confidence": best["confidence"],
            "source": "yolo_detection",
            "target_hint": best["target_hint"],
            "manual_roi_iou": best.get("manual_roi_iou"),
        }
    else:
        generated_tag = {
            "label": "biker",
            "confidence": None,
            "source": "user_expected_semantic_tag_not_detector_output",
            "target_hint": True,
        }

    manifest = {
        "schema": "SPPA-USER-CYCLIST-YOLO-PROBE-0.1",
        "image": display_path(image_path),
        "model": display_path(model_path) if isinstance(model_path, Path) else str(model_path),
        "image_size": {"width": width, "height": height},
        "conf": args.conf,
        "imgsz": args.imgsz,
        "manual_roi_xyxy": list(manual_bbox) if manual_bbox else None,
        "detections": detections,
        "generated_tag": generated_tag,
        "claim_boundary": (
            "User-supplied road image used as detector/input evidence. It is not ground truth, "
            "not a segmentation mask, and not 3D reference geometry."
        ),
        "outputs": {
            "annotated_image": display_path(annotated_path),
            "image_to_3d_input_crop": display_path(crop_path) if crop_path else None,
            "image_to_3d_input_crop_512": display_path(crop_512_path) if crop_512_path else None,
            "crop_bbox_xyxy": list(crop_bbox) if crop_bbox else None,
            "crop_source": crop_source,
        },
    }

    manifest_path = out_dir / "cyclist_road_yolo_probe.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "detections": len(detections), "tag": generated_tag}, indent=2))


if __name__ == "__main__":
    main()
