from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sppa_semantic_normalizer import refine_normalized_with_observation

try:
    from PIL import Image
except Exception:  # pragma: no cover - reported in output if missing
    Image = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[2]
PAPER_RESULTS = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"
DEFAULT_RUN_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "dual_input" / "20260704_real_yoloe_dual_input_benchmark"
YOLOE_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_detection_reference"
    / "20260703_yoloe26s_universal_open_vocab_cpu"
    / "sppa_open_vocab_detector_probe.json"
)
ANNOTATIONS_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_detection_reference"
    / "20260703_real_input_annotations"
    / "real_input_2d_annotations.json"
)
TEXT_BASELINE_CSV = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_sota_benchmark"
    / "runs"
    / "20260703_real_text3d_prompt_baselines"
    / "objects.csv"
)
SPPA_UNIFIED_CSV = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_sota_benchmark"
    / "runs"
    / "20260704_real_all_sppa_unified"
    / "objects.csv"
)
REAL_REPLAY_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "benchmarks"
    / "results"
    / "real_image_assumed_flight_replay.json"
)

IMAGE_RUNS = {
    "biker": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260703_real_cyclist_sppa_triposr_hunyuan",
    "tower": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260703_real_tower_sppa_triposr_hunyuan",
    "tractor": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260703_real_tractor_sppa_triposr_hunyuan",
    "tractor_trailer": ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_sota_benchmark"
    / "runs"
    / "20260703_real_tractor_trailer_sppa_triposr_hunyuan",
}

REQUIRED_IMAGE_METHODS = {"triposr_warm", "hunyuan3d_2mini_turbo_shape"}
REQUIRED_TAG_METHODS = {"sppa", "shap_e_text_k16", "point_e_text_sdf32"}
MODERN_IMAGE_METHODS_NOT_RANKED = {
    "direct3d_s2",
    "hunyuan3d_2_1",
    "partcrafter",
    "pixal3d",
    "rodin_gen_2_5",
    "stable_fast_3d",
    "spar3d",
    "trellis2_4b",
    "tripo_sg_or_tripo_p1",
}
METHOD_DISPLAY = {
    "sppa": "SPPA",
    "triposr_warm": "TripoSR",
    "hunyuan3d_2mini_turbo_shape": "Hunyuan2-mini",
    "shap_e_text_k16": "Shap-E",
    "point_e_text_sdf32": "Point-E",
}


def rel(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def image_label_from_path(path: str) -> str | None:
    lower = path.lower().replace("\\", "/")
    if "user_cyclist" in lower or "cyclist" in lower or "biker" in lower:
        return "biker"
    if "user_tower" in lower or "tower" in lower:
        return "tower"
    if "tractor_trailer" in lower:
        return "tractor_trailer"
    if "user_tractor" in lower or "tractor" in lower:
        return "tractor"
    return None


def rows_for_objects_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [
            row
            for row in csv.DictReader(f)
            if row.get("event") in {"SPPA_BENCH_OBJECT", "SPPA_OBJECT"} and row.get("status") == "ok"
        ]


def summarize_method_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "model": row.get("model"),
        "input_mode": row.get("input_mode"),
        "status": row.get("status"),
        "wall_ms": round(safe_float(row.get("wall_sec")) * 1000.0, 1),
        "triangles": safe_int(row.get("triangles") or row.get("faces")),
        "vertices": safe_int(row.get("vertices")),
        "vram_mb": round(safe_float(row.get("torch_peak_reserved_mb")), 1),
        "mesh_path": row.get("mesh_path") or None,
    }


def image_methods(label: str) -> list[dict[str, Any]]:
    run_dir = IMAGE_RUNS.get(label)
    rows = rows_for_objects_csv(run_dir / "objects.csv") if run_dir else []
    return [summarize_method_row(row) for row in rows]


def text_methods_by_label() -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows_for_objects_csv(TEXT_BASELINE_CSV):
        label = row.get("label") or ""
        grouped.setdefault(label, []).append(summarize_method_row(row))
    for row in rows_for_objects_csv(SPPA_UNIFIED_CSV):
        if row.get("model") != "sppa":
            continue
        label = row.get("label") or ""
        grouped.setdefault(label, []).append(summarize_method_row(row))
    return grouped


def annotation_by_label() -> dict[str, dict[str, Any]]:
    data = load_json(ANNOTATIONS_JSON)
    return {str(item.get("label")): item for item in data.get("items", [])}


def replay_by_label() -> dict[str, dict[str, Any]]:
    data = load_json(REAL_REPLAY_JSON)
    rows = data.get("rows") or data.get("cases") or []
    return {str(item.get("label") or item.get("case_id") or item.get("case")): item for item in rows}


def detector_normalized_from_replay(selected_tag: dict[str, Any], replay: dict[str, Any]) -> dict[str, Any]:
    return {
        "detector_label": selected_tag.get("detector_label") or replay.get("detector_label"),
        "confidence": safe_float(selected_tag.get("confidence"), safe_float(replay.get("detector_confidence"))),
        "sppa_tag": selected_tag.get("sppa_tag") or replay.get("sppa_tag"),
        "runtime_archetype_id": selected_tag.get("runtime_archetype_id")
        or replay.get("detector_runtime_archetype_id")
        or replay.get("sppa_tag"),
        "runtime_archetypes": selected_tag.get("runtime_archetypes") or [],
        "normalization_rule": selected_tag.get("sppa_match")
        or replay.get("normalization_rule")
        or (selected_tag.get("normalization_candidates") or [{}])[0].get("normalization_rule"),
        "claim_status": selected_tag.get("claim_status") or replay.get("claim_status"),
        "conservative": bool(selected_tag.get("conservative", replay.get("conservative", False))),
        "score": safe_float(selected_tag.get("score"), 0.0),
    }


def labels_in_detector_label(detector_label: str) -> list[str]:
    normalized = detector_label.replace("+", ",")
    return [part.strip().lower() for part in normalized.split(",") if part.strip()]


def select_detection_boxes(image_entry: dict[str, Any], selected_tag: dict[str, Any]) -> list[dict[str, Any]]:
    detections = list(image_entry.get("detections", []))
    detector_label = str(selected_tag.get("detector_label") or "").lower()
    parts = labels_in_detector_label(detector_label)
    selected: list[dict[str, Any]] = []
    if parts:
        for part in parts:
            matches = [det for det in detections if str(det.get("class_name", "")).lower() == part]
            if matches:
                selected.append(max(matches, key=lambda det: safe_float(det.get("confidence"))))
    if selected:
        return selected
    matches = [det for det in detections if str(det.get("class_name", "")).lower() == detector_label]
    if matches:
        return [max(matches, key=lambda det: safe_float(det.get("confidence")))]
    return [max(detections, key=lambda det: safe_float(det.get("confidence")))] if detections else []


def union_bbox(detections: list[dict[str, Any]]) -> list[float] | None:
    boxes = [det.get("xyxy") for det in detections if isinstance(det.get("xyxy"), list) and len(det["xyxy"]) == 4]
    if not boxes:
        return None
    return [
        min(float(box[0]) for box in boxes),
        min(float(box[1]) for box in boxes),
        max(float(box[2]) for box in boxes),
        max(float(box[3]) for box in boxes),
    ]


def expand_and_clamp_bbox(bbox: list[float], width: int, height: int, margin_ratio: float = 0.18) -> list[int]:
    x1, y1, x2, y2 = bbox
    bw = max(1.0, x2 - x1)
    bh = max(1.0, y2 - y1)
    margin = max(bw, bh) * margin_ratio
    return [
        max(0, int(round(x1 - margin))),
        max(0, int(round(y1 - margin))),
        min(width, int(round(x2 + margin))),
        min(height, int(round(y2 + margin))),
    ]


def write_detector_crop(
    label: str,
    image_path: Path,
    bbox_xyxy: list[float] | None,
    crop_dir: Path,
) -> tuple[Path | None, Path | None, dict[str, Any]]:
    if Image is None or bbox_xyxy is None or not image_path.exists():
        return None, None, {"crop_written": False, "reason": "Pillow missing, bbox missing, or image missing"}
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        width, height = image.size
        crop_bbox = expand_and_clamp_bbox(bbox_xyxy, width, height)
        crop = image.crop(tuple(crop_bbox))
        crop_path = crop_dir / f"{label}_yoloe_detector_crop.png"
        crop_512_path = crop_dir / f"{label}_yoloe_detector_crop_512.png"
        crop_dir.mkdir(parents=True, exist_ok=True)
        crop.save(crop_path)
        crop.resize((512, 512), Image.Resampling.BICUBIC).save(crop_512_path)
        return (
            crop_path,
            crop_512_path,
            {
                "crop_written": True,
                "source_image_size": {"width": width, "height": height},
                "crop_bbox_xyxy": crop_bbox,
                "crop_width": crop_bbox[2] - crop_bbox[0],
                "crop_height": crop_bbox[3] - crop_bbox[1],
            },
        )


def build_case(
    image_entry: dict[str, Any],
    annotations: dict[str, dict[str, Any]],
    text_methods: dict[str, list[dict[str, Any]]],
    replay_rows: dict[str, dict[str, Any]],
    crop_dir: Path,
) -> dict[str, Any]:
    label = image_label_from_path(str(image_entry.get("image", ""))) or "unknown"
    selected_tag = dict(image_entry.get("selected_tag") or {})
    selected_detections = select_detection_boxes(image_entry, selected_tag)
    bbox = union_bbox(selected_detections)
    image_path = ROOT / str(image_entry.get("image", ""))
    crop_path, crop_512_path, crop_meta = write_detector_crop(label, image_path, bbox, crop_dir)
    image_size = crop_meta.get("source_image_size") or annotations.get(label, {}).get("image_size") or {}
    width = safe_float(image_size.get("width"))
    height = safe_float(image_size.get("height"))
    bbox_area_fraction = None
    if bbox and width > 0 and height > 0:
        bbox_area_fraction = round(max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1]) / (width * height), 6)

    image_method_rows = image_methods(label)
    text_method_rows = list(text_methods.get(label, []))
    tag_track_methods = sorted(
        text_method_rows,
        key=lambda row: str(row.get("model")),
    )
    image_method_names = {str(row.get("model")) for row in image_method_rows}
    tag_method_names = {str(row.get("model")) for row in tag_track_methods}

    replay = replay_rows.get(label, {})
    reviewed_tag = annotations.get(label, {}).get("reviewed_semantic_tag")
    reviewed_runtime = replay.get("runtime_archetype_id") or reviewed_tag
    confidence = safe_float(selected_tag.get("confidence"), default=0.0)
    detector_normalized = detector_normalized_from_replay(selected_tag, replay)
    detector_refined = refine_normalized_with_observation(
        detector_normalized,
        replay.get("sppa_metric_dims_m"),
        replay.get("sppa_uncertainty") if isinstance(replay.get("sppa_uncertainty"), dict) else None,
    ) or detector_normalized
    detector_refinement = detector_refined.get("observation_refinement") or {}
    return {
        "label": label,
        "raw_image": rel(image_path),
        "annotated_image": rel(ROOT / str(image_entry.get("annotated_image", ""))) if image_entry.get("annotated_image") else None,
        "real_image_input": image_path.exists(),
        "yoloe_model": "yoloe-26s-seg.pt",
        "yoloe_elapsed_ms_cpu": round(safe_float(image_entry.get("elapsed_ms")), 3),
        "yoloe_inference_ms_cpu": round(safe_float((image_entry.get("speed_ms") or {}).get("inference")), 3),
        "num_detections": safe_int(image_entry.get("num_detections")),
        "selected_detector_label": selected_tag.get("detector_label"),
        "selected_confidence": confidence,
        "selected_sppa_tag": selected_tag.get("sppa_tag"),
        "selected_runtime_archetype": selected_tag.get("runtime_archetype_id"),
        "detector_observation_refined_sppa_tag": detector_refined.get("sppa_tag"),
        "detector_observation_refined_runtime_archetype": detector_refined.get("runtime_archetype_id"),
        "detector_observation_refined_rule": detector_refined.get("normalization_rule"),
        "detector_observation_refinement_applied": bool(detector_refinement.get("applied")),
        "detector_observation_refinement": detector_refinement,
        "selected_claim_status": selected_tag.get("claim_status"),
        "selected_conservative": selected_tag.get("conservative"),
        "selected_normalization_rule": selected_tag.get("sppa_match")
        or (selected_tag.get("normalization_candidates") or [{}])[0].get("normalization_rule"),
        "detector_bbox_xyxy": [round(float(v), 3) for v in bbox] if bbox else None,
        "detector_bbox_area_fraction": bbox_area_fraction,
        "detector_mask_area_px": sum(safe_int(det.get("mask_area_px")) for det in selected_detections),
        "detector_crop": rel(crop_path),
        "detector_crop_512": rel(crop_512_path),
        "detector_crop_meta": crop_meta,
        "manual_bbox_xyxy": annotations.get(label, {}).get("manual_bbox_xyxy"),
        "reviewed_semantic_tag": reviewed_tag,
        "reviewed_runtime_archetype": reviewed_runtime,
        "image_input_track": {
            "input": "real_image_yoloe_detector_bbox_crop",
            "target_detection_available": bool(selected_tag and bbox and confidence > 0.0),
            "detector_label": selected_tag.get("detector_label"),
            "sppa_normalized_proxy": selected_tag.get("runtime_archetype_id"),
            "sppa_observation_refined_proxy": detector_refined.get("runtime_archetype_id"),
            "sppa_observation_refined_tag": detector_refined.get("sppa_tag"),
            "sppa_observation_refinement_applied": bool(detector_refinement.get("applied")),
            "methods_present": sorted(image_method_names),
            "required_methods_present": sorted(REQUIRED_IMAGE_METHODS & image_method_names),
            "missing_required_methods": sorted(REQUIRED_IMAGE_METHODS - image_method_names),
            "not_ranked_modern_methods": sorted(MODERN_IMAGE_METHODS_NOT_RANKED),
            "method_rows": image_method_rows,
        },
        "tag_text_input_track": {
            "input": "reviewed_tag_text_only_no_image",
            "tag": annotations.get(label, {}).get("reviewed_semantic_tag"),
            "sppa_normalized_proxy": reviewed_runtime,
            "methods_present": sorted(tag_method_names),
            "required_methods_present": sorted(REQUIRED_TAG_METHODS & tag_method_names),
            "missing_required_methods": sorted(REQUIRED_TAG_METHODS - tag_method_names),
            "method_rows": tag_track_methods,
        },
        "metric_replay": {
            "available": bool(replay),
            "telemetry_measured": False if replay else None,
            "metric_ground_truth": False if replay else None,
            "dimensions_m": replay.get("dimensions_m") or replay.get("scenario_dimensions_m"),
            "local_pose_m": replay.get("local_pose_m") or replay.get("position_m"),
        },
        "claim_boundary": (
            "The raw image and YOLOE detector evidence are real local inputs. The detector crop is a reproducible "
            "image-input artifact, but it is not a 3D ground-truth mesh or visual-quality reference."
        ),
    }


def build_report(run_dir: Path) -> dict[str, Any]:
    yoloe = load_json(YOLOE_JSON)
    annotations = annotation_by_label()
    text_methods = text_methods_by_label()
    replay_rows = replay_by_label()
    crop_dir = run_dir / "detector_crops"
    cases = [
        build_case(image_entry, annotations, text_methods, replay_rows, crop_dir)
        for image_entry in yoloe.get("images", [])
    ]
    case_count = len(cases)
    detector_ready = sum(1 for case in cases if case["image_input_track"]["target_detection_available"])
    image_baseline_ready = sum(1 for case in cases if not case["image_input_track"]["missing_required_methods"])
    tag_ready = sum(1 for case in cases if not case["tag_text_input_track"]["missing_required_methods"])
    metric_replay_ready = sum(1 for case in cases if case["metric_replay"]["available"])
    bounded_ready = bool(cases) and detector_ready == case_count and image_baseline_ready == case_count and tag_ready == case_count
    return {
        "schema": "SPPA-REAL-YOLOE-DUAL-INPUT-BENCHMARK-0.1",
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "yoloe_probe": rel(YOLOE_JSON),
        "annotations": rel(ANNOTATIONS_JSON),
        "text_baselines": rel(TEXT_BASELINE_CSV),
        "real_image_assumed_flight_replay": rel(REAL_REPLAY_JSON),
        "case_count": case_count,
        "detector_ready_count": detector_ready,
        "image_baseline_ready_count": image_baseline_ready,
        "tag_text_ready_count": tag_ready,
        "metric_replay_ready_count": metric_replay_ready,
        "image_is_real": True,
        "detector_is_real": True,
        "tag_text_input_has_no_image": True,
        "metric_ground_truth_available": False,
        "bounded_dual_input_claim_ready": bounded_ready,
        "full_visual_image_to_3d_leaderboard_ready": False,
        "claim_posture": (
            "bounded_dual_input_systems_benchmark_ready"
            if bounded_ready
            else "dual_input_protocol_has_missing_local_artifacts"
        ),
        "supported_claim": (
            "SPPA is evaluated as a bounded dual-input proxy system: the real-image path provides YOLOE detector "
            "evidence, crops, and an observation-refined SPPA family audit, while the tag/text path evaluates the "
            "reviewed semantic phrase used by SPPA and text-conditioned baselines."
        ),
        "claim_boundary": (
            "This artifact supports a bounded systems/task-fit comparison, not a full visual image-to-3D SOTA "
            "leaderboard. The real images, YOLOE labels, bboxes, crops, and local method timings are evidence; "
            "3D ground-truth geometry, measured flight telemetry, and venue-complete contemporary visual baselines "
            "are explicitly not claimed."
        ),
        "cases": cases,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Real YOLOE Dual-Input Benchmark",
        "",
        "Generated by `tools/sppa_sota_benchmark/build_real_yoloe_dual_input_benchmark.py`.",
        "",
        "## Verdict",
        "",
        f"- Claim posture: `{report['claim_posture']}`",
        f"- Bounded dual-input claim ready: {report['bounded_dual_input_claim_ready']}",
        f"- Full visual image-to-3D leaderboard ready: {report['full_visual_image_to_3d_leaderboard_ready']}",
        f"- Detector-ready cases: {report['detector_ready_count']} / {report['case_count']}",
        f"- Image-baseline-ready cases: {report['image_baseline_ready_count']} / {report['case_count']}",
        f"- Tag/text-ready cases: {report['tag_text_ready_count']} / {report['case_count']}",
        f"- Metric replay-ready cases: {report['metric_replay_ready_count']} / {report['case_count']}",
        f"- Supported claim: {report['supported_claim']}",
        f"- Claim boundary: {report['claim_boundary']}",
        "",
        "## Cases",
        "",
    ]
    for case in report["cases"]:
        image_methods_text = ", ".join(case["image_input_track"]["methods_present"]) or "none"
        tag_methods_text = ", ".join(case["tag_text_input_track"]["methods_present"]) or "none"
        lines += [
            f"### `{case['label']}`",
            "",
            f"- Raw image: `{case['raw_image']}`",
            f"- YOLOE evidence: `{case['selected_detector_label']}` at confidence {case['selected_confidence']:.3f}",
            f"- Detector-only SPPA family: `{case['selected_sppa_tag']}` -> `{case['selected_runtime_archetype']}`",
            f"- Detector+observation SPPA family: `{case['detector_observation_refined_sppa_tag']}` -> `{case['detector_observation_refined_runtime_archetype']}` (applied: {case['detector_observation_refinement_applied']})",
            f"- Reviewed SPPA text: `{case['reviewed_semantic_tag']}` -> `{case['reviewed_runtime_archetype']}`",
            f"- Detector crop 512: `{case['detector_crop_512']}`",
            f"- Detector bbox area fraction: {case['detector_bbox_area_fraction']}",
            f"- Image-track methods: {image_methods_text}",
            f"- Tag/text-track methods: {tag_methods_text}",
            f"- Metric replay available: {case['metric_replay']['available']}",
            f"- Boundary: {case['claim_boundary']}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def latex_escape(text: Any) -> str:
    value = str(text)
    return (
        value.replace("\\", r"\textbackslash{}")
        .replace("_", r"\_")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("#", r"\#")
    )


def latex_case_label(label: Any) -> str:
    labels = {
        "tractor_trailer": "tractor+trailer",
    }
    return latex_escape(labels.get(str(label), str(label)))


def compact_method_list(methods: list[str]) -> str:
    return ", ".join(METHOD_DISPLAY.get(method, method) for method in methods)


def write_tex(path: Path, report: dict[str, Any]) -> None:
    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\footnotesize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\renewcommand{\arraystretch}{1.08}",
        r"\caption{Frozen real-image and tag/text dual-input benchmark for the bounded SPPA systems claim. The image track uses YOLOE detector evidence and crops for image-to-3D baselines; SPPA additionally reports an observation-refined detector family when geometry supports a safer proxy. The tag/text track uses the reviewed word or phrase for SPPA and text-conditioned baselines. This is not a full visual image-to-3D leaderboard.}",
        r"\label{tab:real-yoloe-dual-input-benchmark}",
        r"\begin{tabularx}{\linewidth}{@{}L{0.13\linewidth}L{0.19\linewidth}L{0.31\linewidth}L{0.18\linewidth}Y@{}}",
        r"\toprule",
        r"Case & YOLOE image input & SPPA family path & Image-track methods & Tag/text methods \\",
        r"\midrule",
    ]
    for case in report["cases"]:
        image_methods_text = compact_method_list(case["image_input_track"]["required_methods_present"])
        tag_methods_text = compact_method_list(case["tag_text_input_track"]["required_methods_present"])
        lines.append(
            f"{latex_case_label(case['label'])} & "
            f"\\texttt{{{latex_escape(case['selected_detector_label'])}}} "
            f"({safe_float(case['selected_confidence']):.2f}) & "
            f"detector: \\texttt{{{latex_escape(case['selected_sppa_tag'])}}} $\\rightarrow$ "
            f"\\texttt{{{latex_escape(case['selected_runtime_archetype'])}}}; "
            f"obs: \\texttt{{{latex_escape(case['detector_observation_refined_sppa_tag'])}}} $\\rightarrow$ "
            f"\\texttt{{{latex_escape(case['detector_observation_refined_runtime_archetype'])}}}; "
            f"text: \\texttt{{{latex_escape(case.get('reviewed_semantic_tag'))}}} $\\rightarrow$ "
            f"\\texttt{{{latex_escape(case.get('reviewed_runtime_archetype'))}}} & "
            f"{latex_escape(image_methods_text)} & "
            f"{latex_escape(tag_methods_text)} \\\\"
        )
    lines += [
        r"\bottomrule",
        r"\end{tabularx}",
        r"\end{table}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def mirror_to_paper_results(run_dir: Path, report: dict[str, Any]) -> None:
    PAPER_RESULTS.mkdir(parents=True, exist_ok=True)
    for suffix in ["json", "md", "tex"]:
        src = run_dir / f"real_yoloe_dual_input_benchmark.{suffix}"
        dst = PAPER_RESULTS / f"real_yoloe_dual_input_benchmark.{suffix}"
        if src.exists():
            shutil.copyfile(src, dst)
    crops_src = run_dir / "detector_crops"
    crops_dst = PAPER_RESULTS / "real_yoloe_detector_crops"
    if crops_src.exists():
        crops_dst.mkdir(parents=True, exist_ok=True)
        for file in crops_src.glob("*.png"):
            shutil.copyfile(file, crops_dst / file.name)
    for case in report["cases"]:
        for key in ["detector_crop", "detector_crop_512"]:
            crop = case.get(key)
            if crop:
                src = ROOT / crop
                mirrored = crops_dst / src.name
                if mirrored.exists():
                    case[key] = rel(mirrored)
    (PAPER_RESULTS / "real_yoloe_dual_input_benchmark.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the real YOLOE dual-input benchmark manifest for SPPA.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    report = build_report(run_dir)
    json_path = run_dir / "real_yoloe_dual_input_benchmark.json"
    md_path = run_dir / "real_yoloe_dual_input_benchmark.md"
    tex_path = run_dir / "real_yoloe_dual_input_benchmark.tex"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(md_path, report)
    write_tex(tex_path, report)
    mirror_to_paper_results(run_dir, report)
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(md_path),
                "tex": str(tex_path),
                "paper_json": str(PAPER_RESULTS / "real_yoloe_dual_input_benchmark.json"),
                "claim_posture": report["claim_posture"],
                "bounded_dual_input_claim_ready": report["bounded_dual_input_claim_ready"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
