from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any
import math

import cv2
import torch
from ultralytics import YOLO

from sppa_semantic_normalizer import normalize_detection_set

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(__file__).with_name("sppa_open_vocab_detector_config.json")
DEFAULT_OUT_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_yoloe26s_open_vocab"
DEFAULT_IMAGES = [
    ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_user_cyclist" / "cyclist_road_input.png",
    ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_user_tower" / "tower_mountain_raw_input.png",
    ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_user_tractor" / "tractor_mountain_raw_input.png",
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_detection_reference"
    / "20260703_user_tractor_trailer"
    / "tractor_trailer_mountain_raw_input.png",
]


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def rel(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(resolved)


def clean_slug(path: Path) -> str:
    return path.stem.lower().replace(" ", "_").replace("(", "").replace(")", "")

def polygon_area_px2(points: list[list[float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5

def simplify_polygon(points: Any, max_points: int = 96) -> list[list[float]]:
    if points is None:
        return []
    try:
        raw = points.tolist()
    except Exception:
        raw = points
    polygon: list[list[float]] = []
    for item in raw:
        try:
            x, y = item[:2]
        except Exception:
            continue
        polygon.append([round(float(x), 6), round(float(y), 6)])
    if len(polygon) > max_points:
        step = max(1, int(math.ceil(len(polygon) / float(max_points))))
        polygon = polygon[::step]
    return polygon


def load_config(path: Path) -> dict[str, Any]:
    data = json.loads(resolve(path).read_text(encoding="utf-8"))
    required = {"model", "classes", "imgsz", "conf", "max_det"}
    missing = sorted(required - set(data))
    if missing:
        raise SystemExit(f"Detector config missing required keys: {missing}")
    return data


def load_detector(config: dict[str, Any]) -> YOLO:
    model_ref = Path(str(config["model"]))
    model_path = resolve(model_ref) if resolve(model_ref).exists() else str(config["model"])
    model = YOLO(str(model_path))
    classes = list(config["classes"])
    if hasattr(model, "set_classes"):
        model.set_classes(classes)
    else:
        raise SystemExit("Selected model does not support set_classes(); use a YOLOE open-vocabulary checkpoint.")
    return model


def detection_rows(result: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if result.boxes is None:
        return rows
    names = result.names
    masks = result.masks
    mask_areas: list[int | None] = [None] * len(result.boxes)
    mask_polygons: list[list[list[float]]] = [[] for _ in range(len(result.boxes))]
    if masks is not None and masks.data is not None:
        mask_areas = [int(mask.sum().item()) for mask in masks.data]
    if masks is not None:
        for idx, polygon in enumerate(getattr(masks, "xy", []) or []):
            if idx < len(mask_polygons):
                mask_polygons[idx] = simplify_polygon(polygon)
    for idx, box in enumerate(result.boxes):
        cls_id = int(box.cls[0].item())
        polygon = mask_polygons[idx] if idx < len(mask_polygons) else []
        rows.append(
            {
                "class_id": cls_id,
                "class_name": str(names.get(cls_id, cls_id)),
                "confidence": float(box.conf[0].item()),
                "xyxy": [float(v) for v in box.xyxy[0].tolist()],
                "mask_area_px": mask_areas[idx] if idx < len(mask_areas) else None,
                "mask_polygon_px": polygon if len(polygon) >= 3 else None,
                "mask_polygon_point_count": len(polygon),
                "mask_polygon_area_px2": polygon_area_px2(polygon) if len(polygon) >= 3 else None,
                "mask_source": "ultralytics_result_masks_xy" if len(polygon) >= 3 else None,
            }
        )
    rows.sort(key=lambda item: float(item["confidence"]), reverse=True)
    return rows


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# SPPA open-vocabulary detector probe",
        "",
        f"- Profile: `{report['profile_id']}`",
        f"- Model: `{report['model']}`",
        f"- Ultralytics task: `{report['model_metadata'].get('task')}`",
        f"- Image size: `{report['imgsz']}`",
        f"- Confidence: `{report['conf']}`",
        f"- Device requested: `{report['device_requested']}`",
        f"- CUDA available: `{report['runtime']['cuda_available']}`",
        f"- CUDA device: `{report['runtime'].get('cuda_device_name')}`",
        "",
        "## Results",
        "",
        "| Image | Detections | Detector evidence | SPPA tag | Runtime archetype | Confidence | Elapsed ms | Model inference ms | Annotation |",
        "|---|---:|---|---|---|---:|---:|---:|---|",
    ]
    for item in report["images"]:
        tag = item.get("selected_tag") or {}
        speed = item.get("speed_ms") or {}
        annotation = item.get("annotated_image") or ""
        sppa_tag = tag.get("sppa_tag", "-")
        runtime_tag = tag.get("runtime_archetype_id", "-")
        lines.append(
            f"| `{item['image']}` | {item['num_detections']} | `{tag.get('detector_label', '-')}` | `{sppa_tag}` | `{runtime_tag}` | "
            f"{float(tag.get('confidence') or 0.0):.3f} | {float(item.get('elapsed_ms') or 0.0):.1f} | "
            f"{float(speed.get('inference') or 0.0):.1f} | `{annotation}` |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            report["paper_claim_boundary"],
            "",
            "## Prompt Classes",
            "",
            ", ".join(f"`{name}`" for name in report["classes"]),
        ]
    )
    return "\n".join(lines) + "\n"


def cuda_device_name() -> str | None:
    if not torch.cuda.is_available() or torch.cuda.device_count() < 1:
        return None
    try:
        return torch.cuda.get_device_name(0)
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the selected SPPA open-vocabulary detector profile.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--image", type=Path, action="append", default=None, help="Image path. Repeat for multiple images.")
    parser.add_argument("--device", default=None, help="Ultralytics device, e.g. 0 or cpu. Default uses config/auto.")
    parser.add_argument("--imgsz", type=int, default=None)
    parser.add_argument("--conf", type=float, default=None)
    parser.add_argument("--max-det", type=int, default=None)
    parser.add_argument("--warmup", type=int, default=1)
    args = parser.parse_args()

    config = load_config(args.config)
    out_dir = resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    image_paths = [resolve(path) for path in (args.image or DEFAULT_IMAGES)]
    missing_images = [str(path) for path in image_paths if not path.exists()]
    if missing_images:
        raise SystemExit(f"Missing images: {missing_images}")

    device_requested = args.device if args.device is not None else str(config.get("default_device", "auto"))
    predict_device = None if device_requested == "auto" else device_requested
    imgsz = int(args.imgsz or config["imgsz"])
    conf = float(args.conf or config["conf"])
    max_det = int(args.max_det or config["max_det"])

    model = load_detector(config)
    first_image = str(image_paths[0])
    for _ in range(max(0, args.warmup)):
        model.predict(first_image, imgsz=imgsz, conf=conf, max_det=max_det, device=predict_device, verbose=False)

    image_reports: list[dict[str, Any]] = []
    for image_path in image_paths:
        start = time.perf_counter()
        result = model.predict(
            str(image_path),
            imgsz=imgsz,
            conf=conf,
            max_det=max_det,
            device=predict_device,
            verbose=False,
        )[0]
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        rows = detection_rows(result)
        slug = clean_slug(image_path)
        annotated_path = out_dir / f"{slug}_yoloe26s_open_vocab.png"
        plotted = result.plot()
        cv2.imwrite(str(annotated_path), plotted)
        selected = normalize_detection_set(rows)
        image_reports.append(
            {
                "image": rel(image_path),
                "annotated_image": rel(annotated_path),
                "elapsed_ms": elapsed_ms,
                "speed_ms": result.speed,
                "num_detections": len(rows),
                "selected_tag": {
                    "detector_label": selected["detector_label"],
                    "sppa_tag": selected["sppa_tag"],
                    "runtime_archetype_id": selected["runtime_archetype_id"],
                    "sppa_runtime_archetypes": selected["runtime_archetypes"],
                    "sppa_match": selected["normalization_rule"],
                    "claim_status": selected["claim_status"],
                    "conservative": selected["conservative"],
                    "confidence": selected["confidence"],
                    "source": config["profile_id"],
                    "normalization_candidates": selected.get("normalization_candidates", []),
                }
                if selected
                else None,
                "detections": rows,
            }
        )

    yaml = getattr(getattr(model, "model", None), "yaml", None)
    report = {
        "schema": "SPPA-OPEN-VOCAB-DETECTOR-PROBE-0.1",
        "profile_id": config["profile_id"],
        "config": rel(resolve(args.config)),
        "model": str(config["model"]),
        "model_metadata": {
            "task": getattr(model, "task", None),
            "yaml_file": yaml.get("yaml_file") if isinstance(yaml, dict) else None,
            "scale": yaml.get("scale") if isinstance(yaml, dict) else None,
            "nc": yaml.get("nc") if isinstance(yaml, dict) else None,
        },
        "classes": list(config["classes"]),
        "imgsz": imgsz,
        "conf": conf,
        "max_det": max_det,
        "device_requested": device_requested,
        "runtime": {
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_device_name": cuda_device_name(),
        },
        "paper_claim_boundary": config["paper_claim_boundary"],
        "deployment_note": config.get("deployment_note"),
        "images": image_reports,
    }

    json_path = out_dir / "sppa_open_vocab_detector_probe.json"
    md_path = out_dir / "sppa_open_vocab_detector_probe.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"json": rel(json_path), "markdown": rel(md_path), "images": len(image_reports)}, indent=2))


if __name__ == "__main__":
    main()
