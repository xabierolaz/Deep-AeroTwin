from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ultralytics import YOLO, YOLOWorld

ROOT = Path(__file__).resolve().parents[2]
OUT_JSON = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "yolo_detector_candidate_comparison.json"
OUT_MD = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "yolo_detector_candidate_comparison.md"

PROMPTS = [
    "tractor",
    "farm tractor",
    "tractor with trailer",
    "trailer",
    "utility trailer",
    "agricultural vehicle",
    "vehicle",
    "truck",
    "power transmission tower",
    "electric pylon",
    "bicycle",
    "cyclist",
]


@dataclass(frozen=True)
class Case:
    case_id: str
    image: Path
    manual_roi_xyxy: tuple[int, int, int, int]
    strict_keywords: tuple[str, ...]
    weak_vehicle_keywords: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    path: Path
    loader: str
    open_vocab: bool
    notes: str


CASES = [
    Case(
        case_id="tractor_real_mountain",
        image=ROOT.parent
        / "papers"
        / "semantic_proxy_3d"
        / "experiments_root"
        / "sppa_detection_reference"
        / "20260703_user_tractor"
        / "tractor_mountain_raw_input.png",
        manual_roi_xyxy=(382, 323, 437, 383),
        strict_keywords=("tractor",),
        weak_vehicle_keywords=("truck", "vehicle", "car", "train"),
    ),
    Case(
        case_id="tractor_trailer_real_mountain",
        image=ROOT.parent
        / "papers"
        / "semantic_proxy_3d"
        / "experiments_root"
        / "sppa_detection_reference"
        / "20260703_user_tractor_trailer"
        / "tractor_trailer_mountain_raw_input.png",
        manual_roi_xyxy=(380, 255, 505, 500),
        strict_keywords=("tractor", "trailer"),
        weak_vehicle_keywords=("truck", "vehicle", "car", "train"),
    ),
]

CUSTOM_MODEL = ROOT / "yolo" / "weights" / "yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt"

CANDIDATES = [
    Candidate(
        candidate_id="installed_custom_yolo11n_3class",
        path=CUSTOM_MODEL,
        loader="YOLO",
        open_vocab=False,
        notes="Installed project model; fixed classes are biker/cow/tower.",
    ),
    Candidate(
        candidate_id="yolo11x_coco_closed_set",
        path=ROOT / "yolo11x.pt",
        loader="YOLO",
        open_vocab=False,
        notes="Large closed-set YOLO11 COCO detector; COCO has 80 classes and no tractor class.",
    ),
    Candidate(
        candidate_id="yolov8x_worldv2_open_vocab",
        path=ROOT / "yolov8x-worldv2.pt",
        loader="YOLOWorld",
        open_vocab=True,
        notes="YOLO-World open-vocabulary detector with SPPA target prompts.",
    ),
    Candidate(
        candidate_id="yoloe_11s_seg_open_vocab",
        path=ROOT / "yoloe-11s-seg.pt",
        loader="YOLO",
        open_vocab=True,
        notes="YOLOE open-vocabulary segmentation/detection checkpoint with SPPA target prompts.",
    ),
    Candidate(
        candidate_id="yoloe_26s_seg_open_vocab",
        path=ROOT / "yoloe-26s-seg.pt",
        loader="YOLO",
        open_vocab=True,
        notes="YOLOE-26s open-vocabulary segmentation/detection checkpoint selected as the edge-oriented SPPA profile.",
    ),
    Candidate(
        candidate_id="yoloe_11l_seg_open_vocab",
        path=ROOT / "yoloe-11l-seg.pt",
        loader="YOLO",
        open_vocab=True,
        notes="Larger YOLOE open-vocabulary segmentation/detection checkpoint with SPPA target prompts.",
    ),
]


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def bbox_iou(a: tuple[float, float, float, float], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    denom = area_a + area_b - inter
    return float(inter / denom) if denom else 0.0


def center_in_roi(box: tuple[float, float, float, float], roi: tuple[int, int, int, int]) -> bool:
    x1, y1, x2, y2 = box
    rx1, ry1, rx2, ry2 = roi
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    return rx1 <= cx <= rx2 and ry1 <= cy <= ry2


def load_model(candidate: Candidate) -> Any:
    if candidate.loader == "YOLOWorld":
        model = YOLOWorld(str(candidate.path))
    else:
        model = YOLO(str(candidate.path))
    if candidate.open_vocab:
        model.set_classes(PROMPTS)
    return model


def model_metadata(model: Any) -> dict[str, Any]:
    names = getattr(model, "names", None)
    if isinstance(names, dict):
        clean_names = {str(k): v for k, v in names.items()}
    else:
        clean_names = names
    yaml = getattr(getattr(model, "model", None), "yaml", None)
    return {
        "task": getattr(model, "task", None),
        "names": clean_names,
        "yaml_file": yaml.get("yaml_file") if isinstance(yaml, dict) else None,
        "scale": yaml.get("scale") if isinstance(yaml, dict) else None,
        "nc": yaml.get("nc") if isinstance(yaml, dict) else None,
    }


def detections_for_case(model: Any, case: Case) -> list[dict[str, Any]]:
    result = model.predict(str(case.image), conf=0.01, imgsz=1280, verbose=False)[0]
    detections: list[dict[str, Any]] = []
    if result.boxes is None:
        return detections
    for box in result.boxes:
        cls_id = int(box.cls[0].item())
        name = str(result.names.get(cls_id, cls_id))
        label = name.lower()
        xyxy = tuple(float(v) for v in box.xyxy[0].tolist())
        iou = bbox_iou(xyxy, case.manual_roi_xyxy)
        strict = any(keyword in label for keyword in case.strict_keywords)
        weak = any(keyword in label for keyword in case.weak_vehicle_keywords)
        detections.append(
            {
                "class_id": cls_id,
                "class_name": name,
                "confidence": float(box.conf[0].item()),
                "xyxy": list(xyxy),
                "manual_roi_iou": iou,
                "center_in_manual_roi": center_in_roi(xyxy, case.manual_roi_xyxy),
                "overlaps_manual_roi": iou >= 0.02,
                "strict_semantic_hit": strict,
                "weak_vehicle_hit": weak,
            }
        )
    detections.sort(
        key=lambda row: (
            bool(row["overlaps_manual_roi"] or row["center_in_manual_roi"]),
            bool(row["strict_semantic_hit"]),
            bool(row["weak_vehicle_hit"]),
            float(row["manual_roi_iou"]),
            float(row["confidence"]),
        ),
        reverse=True,
    )
    return detections


def summarize_case(rows: list[dict[str, Any]]) -> dict[str, Any]:
    roi_rows = [row for row in rows if row["overlaps_manual_roi"] or row["center_in_manual_roi"]]
    strict_rows = [row for row in roi_rows if row["strict_semantic_hit"]]
    weak_rows = [row for row in roi_rows if row["weak_vehicle_hit"]]
    return {
        "detections": len(rows),
        "roi_detections": len(roi_rows),
        "strict_target_hit": bool(strict_rows),
        "weak_vehicle_hit": bool(weak_rows),
        "best_roi_detection": roi_rows[0] if roi_rows else None,
        "best_strict_detection": strict_rows[0] if strict_rows else None,
        "top_detections": rows[:8],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# YOLO detector candidate comparison",
        "",
        "This is a local probe over the user-supplied tractor images. It is not a COCO/LVIS benchmark; it checks whether each detector can produce a usable image-side tag/box for the SPPA dual-input path.",
        "",
        "## Installed model",
        "",
        f"- Path: `{report['installed_model']['path']}`",
        f"- Task: `{report['installed_model']['metadata'].get('task')}`",
        f"- YAML: `{report['installed_model']['metadata'].get('yaml_file')}`",
        f"- Classes: `{report['installed_model']['metadata'].get('names')}`",
        "",
        "## Results",
        "",
        "| Candidate | Case | Detections | ROI detections | Strict tractor/trailer hit | Weak vehicle hit | Best ROI label | Best ROI conf | Notes |",
        "|---|---:|---:|---:|---:|---:|---|---:|---|",
    ]
    for candidate in report["candidates"]:
        if "error" in candidate:
            lines.append(
                f"| `{candidate['candidate_id']}` | all | 0 | 0 | no | no | error | 0.00 | {candidate['error']} |"
            )
            continue
        for case_id, summary in candidate["cases"].items():
            best = summary.get("best_roi_detection")
            label = best["class_name"] if best else "-"
            conf = best["confidence"] if best else 0.0
            lines.append(
                f"| `{candidate['candidate_id']}` | `{case_id}` | {summary['detections']} | {summary['roi_detections']} | "
                f"{'yes' if summary['strict_target_hit'] else 'no'} | {'yes' if summary['weak_vehicle_hit'] else 'no'} | "
                f"`{label}` | {conf:.3f} | {candidate['notes']} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- A strict hit means the detector output label contains `tractor` or `trailer` on a box overlapping the manual ROI.",
            "- A weak vehicle hit means the detector produced a nearby generic vehicle-like label such as `truck`, `vehicle`, `car`, or `train`.",
            "- For the paper claim, weak vehicle hits are not enough: they can help cropping, but they cannot support a truthful tractor-class detector claim.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema": "SPPA-YOLO-DETECTOR-CANDIDATE-COMPARISON-0.1",
        "prompts": PROMPTS,
        "cases": [
            {
                "case_id": case.case_id,
                "image": rel(case.image),
                "manual_roi_xyxy": list(case.manual_roi_xyxy),
                "strict_keywords": list(case.strict_keywords),
                "weak_vehicle_keywords": list(case.weak_vehicle_keywords),
            }
            for case in CASES
        ],
        "installed_model": {"path": rel(CUSTOM_MODEL), "metadata": {}},
        "candidates": [],
    }

    for candidate in CANDIDATES:
        entry: dict[str, Any] = {
            "candidate_id": candidate.candidate_id,
            "path": rel(candidate.path),
            "loader": candidate.loader,
            "open_vocab": candidate.open_vocab,
            "notes": candidate.notes,
        }
        if not candidate.path.exists():
            entry["error"] = f"missing weights: {candidate.path}"
            report["candidates"].append(entry)
            continue
        try:
            model = load_model(candidate)
            entry["metadata"] = model_metadata(model)
            if candidate.path == CUSTOM_MODEL:
                report["installed_model"]["metadata"] = entry["metadata"]
            entry["cases"] = {}
            for case in CASES:
                rows = detections_for_case(model, case)
                entry["cases"][case.case_id] = summarize_case(rows)
        except Exception as exc:  # noqa: BLE001 - benchmark report must capture candidate failures.
            entry["error"] = f"{type(exc).__name__}: {exc}"
        report["candidates"].append(entry)

    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    OUT_MD.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"json": rel(OUT_JSON), "markdown": rel(OUT_MD)}, indent=2))


if __name__ == "__main__":
    main()
