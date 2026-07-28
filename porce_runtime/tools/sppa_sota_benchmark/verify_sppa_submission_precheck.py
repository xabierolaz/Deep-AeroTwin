from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PAPER_DIR = ROOT.parent / "papers" / "semantic_proxy_3d"
TARGET_LABEL_ALIASES = {
    "biker": {"biker", "bike", "bicycle", "cyclist"},
    "tower": {"tower", "pylon", "transmission tower", "power tower", "electric tower", "utility pole"},
    "tractor": {"tractor", "truck", "car", "vehicle"},
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def pdf_pages(path: Path) -> int | None:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception:
        log = read_text(path.with_suffix(".log"))
        match = re.search(r"Output written on .* \((\d+) pages?,", log)
        return int(match.group(1)) if match else None


def count_log_issues(path: Path) -> dict[str, int]:
    text = read_text(path)
    patterns = {
        "latex_errors": r"! LaTeX Error",
        "undefined_citations": r"LaTeX Warning: Citation .* undefined",
        "undefined_references": r"There were undefined references|undefined references",
        "overfull": r"Overfull \\hbox",
        "underfull": r"Underfull \\hbox",
        "float_changed": r"float specifier changed",
    }
    return {name: len(re.findall(pattern, text)) for name, pattern in patterns.items()}


def input_provenance_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "items": 0,
            "candidate_real_inputs": 0,
            "candidate_real_input_labels": [],
            "ground_truth_items": 0,
            "detector_crop_items": 0,
            "synthetic_proxy_items": 0,
            "bbox_items": 0,
            "mask_items": 0,
            "reference_mesh_items": 0,
            "candidate_real_bbox_items": 0,
            "candidate_real_mask_items": 0,
            "candidate_real_reference_mesh_items": 0,
            "can_label_first_row_as_ground_truth": False,
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    items = list(data.get("items", []))
    candidate_real_inputs = list(data.get("candidate_real_inputs", []))
    return {
        "exists": True,
        "items": len(items),
        "candidate_real_inputs": len(candidate_real_inputs),
        "candidate_real_input_labels": [str(item.get("label")) for item in candidate_real_inputs],
        "ground_truth_items": sum(1 for item in items if item.get("is_ground_truth") is True),
        "detector_crop_items": sum(1 for item in items if item.get("source_type") == "detector_crop"),
        "synthetic_proxy_items": sum(1 for item in items if item.get("source_type") == "synthetic_proxy_crop"),
        "bbox_items": sum(1 for item in items if item.get("has_bbox") is True),
        "mask_items": sum(1 for item in items if item.get("has_mask") is True),
        "reference_mesh_items": sum(1 for item in items if item.get("has_reference_mesh") is True),
        "candidate_real_bbox_items": sum(1 for item in candidate_real_inputs if item.get("has_bbox") is True),
        "candidate_real_mask_items": sum(1 for item in candidate_real_inputs if item.get("has_mask") is True),
        "candidate_real_reference_mesh_items": sum(1 for item in candidate_real_inputs if item.get("has_reference_mesh") is True),
        "can_label_first_row_as_ground_truth": bool(items) and all(item.get("is_ground_truth") is True for item in items),
    }


def detection_reference_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "items": 0,
            "ground_truth_items": 0,
            "readable_image_items": 0,
            "detector_crop_items": 0,
            "labels": [],
            "claim": None,
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    items = list(data.get("items", []))
    return {
        "exists": True,
        "items": len(items),
        "ground_truth_items": sum(1 for item in items if item.get("is_ground_truth") is True),
        "readable_image_items": sum(1 for item in items if item.get("image_readable") is True),
        "detector_crop_items": sum(1 for item in items if item.get("source_type") == "detector_crop"),
        "labels": [str(item.get("label")) for item in items],
        "claim": data.get("claim"),
    }


def real_input_2d_annotation_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "items": 0,
            "bbox_gt_2d_items": 0,
            "gt_3d_items": 0,
            "mask_items": 0,
            "reference_mesh_items": 0,
            "labels": [],
            "claim_boundary": None,
            "can_support_3d_sota_gt": False,
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    items = list(data.get("items", []))
    return {
        "exists": True,
        "items": len(items),
        "bbox_gt_2d_items": sum(1 for item in items if item.get("is_ground_truth_2d_bbox") is True),
        "gt_3d_items": sum(1 for item in items if item.get("is_ground_truth_3d") is True),
        "mask_items": sum(1 for item in items if item.get("has_mask") is True),
        "reference_mesh_items": sum(1 for item in items if item.get("has_reference_mesh") is True),
        "labels": [str(item.get("label")) for item in items],
        "claim_boundary": data.get("global_claim"),
        "can_support_3d_sota_gt": False,
    }


def real_image_assumed_flight_replay_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "case_count": 0,
            "passed_count": 0,
            "failed_count": 0,
            "image_is_real": False,
            "detector_is_real": False,
            "telemetry_is_measured": None,
            "metric_ground_truth": None,
            "claim_posture": None,
            "claim_boundary": None,
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "exists": True,
        "case_count": int(data.get("case_count", 0) or 0),
        "passed_count": int(data.get("passed_count", 0) or 0),
        "failed_count": int(data.get("failed_count", 0) or 0),
        "image_is_real": data.get("image_is_real") is True,
        "detector_is_real": data.get("detector_is_real") is True,
        "telemetry_is_measured": data.get("telemetry_is_measured"),
        "metric_ground_truth": data.get("metric_ground_truth"),
        "claim_posture": data.get("claim_posture"),
        "claim_boundary": data.get("claim_boundary"),
    }


def real_yoloe_dual_input_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "case_count": 0,
            "detector_ready_count": 0,
            "image_baseline_ready_count": 0,
            "tag_text_ready_count": 0,
            "metric_replay_ready_count": 0,
            "bounded_dual_input_claim_ready": False,
            "full_visual_image_to_3d_leaderboard_ready": False,
            "claim_posture": None,
            "claim_boundary": None,
        }
    data = load_json(path)
    return {
        "exists": True,
        "case_count": int(data.get("case_count", 0) or 0),
        "detector_ready_count": int(data.get("detector_ready_count", 0) or 0),
        "image_baseline_ready_count": int(data.get("image_baseline_ready_count", 0) or 0),
        "tag_text_ready_count": int(data.get("tag_text_ready_count", 0) or 0),
        "metric_replay_ready_count": int(data.get("metric_replay_ready_count", 0) or 0),
        "bounded_dual_input_claim_ready": data.get("bounded_dual_input_claim_ready") is True,
        "full_visual_image_to_3d_leaderboard_ready": data.get("full_visual_image_to_3d_leaderboard_ready") is True,
        "claim_posture": data.get("claim_posture"),
        "claim_boundary": data.get("claim_boundary"),
    }


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def evidence_channel_coverage_status(path: Path, tex_path: Path, figure_path: Path) -> dict[str, Any]:
    data = load_json(path)
    if not data:
        return {
            "exists": False,
            "tex_exists": tex_path.exists(),
            "figure_exists": figure_path.exists(),
            "row_count": 0,
            "case_count": 0,
            "summary": {},
            "budget_failures": 0,
            "visual_improvement_cases": 0,
            "claim_boundary": None,
        }
    rows = list(data.get("rows", []))
    by_case: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_case.setdefault(str(row.get("case")), {})[str(row.get("mode"))] = row
    visual_improvement_cases = 0
    for modes in by_case.values():
        metric = modes.get("detector_metric")
        visual = modes.get("detector_metric_visual")
        if metric and visual and int(visual.get("active_evidence_channels") or 0) > int(
            metric.get("active_evidence_channels") or 0
        ):
            visual_improvement_cases += 1
    return {
        "exists": path.exists(),
        "tex_exists": tex_path.exists(),
        "figure_exists": figure_path.exists(),
        "row_count": len(rows),
        "case_count": len(by_case),
        "summary": data.get("summary", {}),
        "budget_failures": sum(1 for row in rows if row.get("budget_pass") is not True),
        "visual_improvement_cases": visual_improvement_cases,
        "claim_boundary": data.get("claim_boundary"),
    }


def tag_summary(data: dict[str, Any]) -> dict[str, Any]:
    tag = data.get("generated_tag") or {}
    return {
        "label": tag.get("label"),
        "confidence": tag.get("confidence"),
        "source": tag.get("source"),
        "manual_roi_iou": tag.get("manual_roi_iou"),
    }

def format_tag(tag: dict[str, Any]) -> str:
    if not tag.get("label"):
        return "none"
    confidence = tag.get("confidence")
    try:
        confidence_text = f"{float(confidence):.3f}"
    except (TypeError, ValueError):
        confidence_text = "n/a"
    iou = tag.get("manual_roi_iou")
    try:
        iou_text = f"{float(iou):.3f}"
    except (TypeError, ValueError):
        iou_text = "n/a"
    return f"{tag.get('label')} (conf={confidence_text}, source={tag.get('source')}, roi_iou={iou_text})"

def expected_probe_label(data: dict[str, Any]) -> str | None:
    label = data.get("semantic_label") or data.get("expected_label")
    if label:
        return str(label).lower()
    image = str(data.get("image", "")).lower()
    if "cyclist" in image or "biker" in image:
        return "biker"
    if "tower" in image:
        return "tower"
    if "tractor" in image:
        return "tractor"
    return None

def valid_detector_hits(data: dict[str, Any]) -> int:
    expected = expected_probe_label(data)
    aliases = TARGET_LABEL_ALIASES.get(expected or "", {expected} if expected else set())
    hits = 0
    for item in data.get("detections", []):
        class_name = str(item.get("class_name", "")).lower()
        if item.get("overlaps_manual_roi") is True and class_name in aliases:
            hits += 1
    return hits

def run_method_summary(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "objects.csv"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("event") != "SPPA_BENCH_OBJECT":
                continue
            rows.append(
                {
                    "model": row.get("model"),
                    "status": row.get("status"),
                    "wall_ms": round(float(row.get("wall_sec") or 0.0) * 1000.0, 1),
                    "triangles": int(float(row.get("triangles") or 0.0)),
                    "vram_mb": round(float(row.get("torch_peak_reserved_mb") or 0.0), 1)
                    if row.get("torch_peak_reserved_mb")
                    else 0.0,
                }
            )
    return rows

def real_input_probe_status() -> dict[str, Any]:
    cyclist_dir = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_user_cyclist"
    tower_dir = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_user_tower"
    tractor_dir = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_user_tractor"
    tractor_trailer_dir = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_user_tractor_trailer"
    cyclist_run_dir = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260703_real_cyclist_sppa_triposr_hunyuan"
    tower_run_dir = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260703_real_tower_sppa_triposr_hunyuan"
    tractor_run_dir = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260703_real_tractor_sppa_triposr_hunyuan"
    tractor_trailer_run_dir = (
        ROOT.parent
        / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
        / "sppa_sota_benchmark"
        / "runs"
        / "20260703_real_tractor_trailer_sppa_triposr_hunyuan"
    )
    real_input_probe_figure = PAPER_DIR / "figures" / "sppa_real_input_probe_grid.png"

    probe_specs = [
        {
            "label": "biker",
            "image": cyclist_dir / "cyclist_road_input.png",
            "crop_512": cyclist_dir / "cyclist_image_to_3d_input_512.png",
            "repo_probe": cyclist_dir / "cyclist_road_yolo_probe.json",
            "repo_lowconf_probe": cyclist_dir / "repo_yolo_lowconf" / "cyclist_road_yolo_probe.json",
            "coco_probe": cyclist_dir / "coco_yolo11n" / "cyclist_road_yolo_probe.json",
            "run_dir": cyclist_run_dir,
            "summary": cyclist_run_dir / "REAL_CYCLIST_PROBE.md",
        },
        {
            "label": "tower",
            "image": tower_dir / "tower_mountain_raw_input.png",
            "crop_512": tower_dir / "tower_mountain_image_to_3d_input_512.png",
            "repo_probe": tower_dir / "tower_mountain_yolo_probe.json",
            "repo_lowconf_probe": None,
            "coco_probe": tower_dir / "coco_yolo11n" / "tower_mountain_yolo_probe.json",
            "run_dir": tower_run_dir,
            "summary": tower_run_dir / "REAL_TOWER_PROBE.md",
        },
        {
            "label": "tractor",
            "image": tractor_dir / "tractor_mountain_raw_input.png",
            "crop_512": tractor_dir / "tractor_mountain_image_to_3d_input_512.png",
            "repo_probe": tractor_dir / "tractor_mountain_yolo_probe.json",
            "repo_lowconf_probe": None,
            "coco_probe": tractor_dir / "coco_yolo11n" / "tractor_mountain_yolo_probe.json",
            "run_dir": tractor_run_dir,
            "summary": tractor_run_dir / "REAL_TRACTOR_PROBE.md",
        },
        {
            "label": "tractor_trailer",
            "image": tractor_trailer_dir / "tractor_trailer_mountain_raw_input.png",
            "crop_512": tractor_trailer_dir / "tractor_trailer_mountain_image_to_3d_input_512.png",
            "repo_probe": tractor_trailer_dir / "tractor_trailer_mountain_yolo_probe.json",
            "repo_lowconf_probe": None,
            "coco_probe": tractor_trailer_dir / "coco_yolo11n" / "tractor_trailer_mountain_yolo_probe.json",
            "run_dir": tractor_trailer_run_dir,
            "summary": tractor_trailer_run_dir / "REAL_TRACTOR_TRAILER_PROBE.md",
        },
    ]

    probes: list[dict[str, Any]] = []
    for spec in probe_specs:
        repo = load_json(spec["repo_probe"])
        lowconf = load_json(spec["repo_lowconf_probe"]) if spec["repo_lowconf_probe"] else {}
        coco = load_json(spec["coco_probe"])
        probes.append(
            {
                "label": spec["label"],
                "exists": spec["image"].exists(),
                "readable_input_image": spec["image"].exists(),
                "image_to_3d_crop_512_exists": spec["crop_512"].exists(),
                "is_ground_truth": False,
                "has_mask": False,
                "has_reference_mesh": False,
                "repo_yolo_detections": len(repo.get("detections", [])),
                "repo_yolo_valid_target_hits": valid_detector_hits(repo),
                "repo_yolo_tag": tag_summary(repo),
                "repo_yolo_lowconf_detections": len(lowconf.get("detections", [])),
                "repo_yolo_lowconf_valid_target_hits": valid_detector_hits(lowconf),
                "repo_yolo_lowconf_tag": tag_summary(lowconf),
                "coco_yolo_detections": len(coco.get("detections", [])),
                "coco_yolo_valid_target_hits": valid_detector_hits(coco),
                "coco_yolo_tag": tag_summary(coco),
                "run_exists": spec["run_dir"].exists(),
                "objects_csv_exists": (spec["run_dir"] / "objects.csv").exists(),
                "summary_exists": spec["summary"].exists(),
                "methods": run_method_summary(spec["run_dir"]),
            }
        )

    return {
        "exists": any(probe["exists"] for probe in probes),
        "count": len(probes),
        "labels": [probe["label"] for probe in probes],
        "probes": probes,
        "readable_input_images": sum(1 for probe in probes if probe["readable_input_image"]),
        "image_to_3d_crop_512_count": sum(1 for probe in probes if probe["image_to_3d_crop_512_exists"]),
        "runs_ready": sum(1 for probe in probes if probe["run_exists"] and probe["objects_csv_exists"]),
        "is_ground_truth": False,
        "has_mask": False,
        "has_reference_mesh": False,
        "real_input_probe_figure": real_input_probe_figure.exists(),
    }


def phrase_status(main_tex: str) -> dict[str, bool]:
    lower = re.sub(r"\s+", " ", main_tex.lower())
    return {
        "states_not_sota_ranking": bool(re.search(r"not (?:a )?(?:visual )?sota ranking", lower)),
        "states_circular_ranking_excluded": "circular" in lower and "excluded" in lower,
        "states_not_real_detection_gt": "not real detection ground truth" in lower,
        "mentions_input_provenance_manifest": "input-provenance manifest" in lower,
        "states_operator_unproven": "operator" in lower and ("unproven" in lower or "not yet" in lower),
    }


def evidence_file_status() -> dict[str, bool]:
    checks = {
        "task_fit_ranking_csv": PAPER_DIR / "benchmarks" / "results" / "sppa_task_fit_ranking.csv",
        "task_fit_ranking_tex": PAPER_DIR / "benchmarks" / "results" / "sppa_task_fit_ranking.tex",
        "visual_grid": PAPER_DIR / "figures" / "sppa_input_alignment_six_case_visual_grid.png",
        "sota_protocol_manifest": ROOT.parent
        / "papers"
        / "semantic_proxy_3d"
        / "experiments_root"
        / "sppa_sota_benchmark"
        / "protocols"
        / "sppa_sota_protocol_v01.json",
        "sota_protocol_readiness": PAPER_DIR / "benchmarks" / "results" / "sota_protocol_readiness.json",
        "dual_input_sota_readiness": PAPER_DIR / "benchmarks" / "results" / "sota_dual_input_readiness.json",
        "real_yoloe_dual_input_benchmark": PAPER_DIR / "benchmarks" / "results" / "real_yoloe_dual_input_benchmark.json",
        "sota_method_exclusions": PAPER_DIR / "benchmarks" / "results" / "sota_method_exclusions.json",
        "sota_preference_protocol": PAPER_DIR / "benchmarks" / "results" / "sota_preference_protocol.md",
        "sota_image_alignment_metrics": PAPER_DIR / "benchmarks" / "results" / "sota_image_alignment_metrics.csv",
        "phase_aligned_unreal_profile_csv": PAPER_DIR / "benchmarks" / "results" / "sppa_phase_aligned_unreal_profile.csv",
        "phase_aligned_unreal_profile_md": PAPER_DIR / "benchmarks" / "results" / "sppa_phase_aligned_unreal_profile.md",
        "scheduler_active_track_replay_csv": PAPER_DIR / "benchmarks" / "results" / "sppa_scheduler_active_track_replay.csv",
        "scheduler_active_track_replay_md": PAPER_DIR / "benchmarks" / "results" / "sppa_scheduler_active_track_replay.md",
        "submission_evidence_pack": PAPER_DIR / "benchmarks" / "results" / "sppa_submission_evidence_pack.json",
        "supplement_triage": PAPER_DIR / "SUPPLEMENT_TRIAGE.json",
        "sppa_visual_material_audit": PAPER_DIR / "benchmarks" / "results" / "sppa_visual_material_audit.json",
        "sppa_runtime_budget": PAPER_DIR / "benchmarks" / "results" / "sppa_runtime_budget.json",
        "sppa_visual_part_evidence_audit": PAPER_DIR
        / "benchmarks"
        / "results"
        / "sppa_visual_part_evidence_audit.json",
        "sppa_visual_part_evidence_grid": PAPER_DIR
        / "benchmarks"
        / "results"
        / "sppa_visual_part_evidence_grid.json",
        "sppa_visual_part_evidence_grid_figure": PAPER_DIR / "figures" / "sppa_visual_part_evidence_grid.png",
        "agnostic_image_space_parts_probe": PAPER_DIR
        / "benchmarks"
        / "results"
        / "sppa_agnostic_image_space_parts_probe.json",
        "agnostic_image_space_parts_verify": PAPER_DIR
        / "benchmarks"
        / "results"
        / "sppa_agnostic_image_space_parts_verify.json",
        "agnostic_label_invariance": PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_label_invariance.json",
        "agnostic_identity_invariance": PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_identity_invariance.json",
        "agnostic_path_invariance": PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_path_invariance.json",
        "agnostic_detection_representation_invariance": PAPER_DIR
        / "benchmarks"
        / "results"
        / "sppa_agnostic_detection_representation_invariance.json",
        "agnostic_side_channel_invariance": PAPER_DIR
        / "benchmarks"
        / "results"
        / "sppa_agnostic_side_channel_invariance.json",
        "agnostic_mirror_equivariance": PAPER_DIR
        / "benchmarks"
        / "results"
        / "sppa_agnostic_mirror_equivariance.json",
        "agnostic_photometric_stability": PAPER_DIR
        / "benchmarks"
        / "results"
        / "sppa_agnostic_photometric_stability.json",
        "agnostic_synthetic_part_controls": PAPER_DIR
        / "benchmarks"
        / "results"
        / "sppa_agnostic_synthetic_part_controls.json",
        "agnostic_synthetic_controls_figure": PAPER_DIR / "figures" / "sppa_agnostic_synthetic_controls_grid.png",
        "agnostic_synthetic_sweep": PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_synthetic_sweep.json",
        "agnostic_synthetic_sweep_figure": PAPER_DIR / "figures" / "sppa_agnostic_synthetic_sweep_examples.png",
        "agnostic_synthetic_fuzz": PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_synthetic_fuzz.json",
        "agnostic_synthetic_fuzz_figure": PAPER_DIR / "figures" / "sppa_agnostic_synthetic_fuzz_examples.png",
        "agnostic_image_space_parts_figure": PAPER_DIR / "figures" / "sppa_agnostic_mask_vs_image_cues_grid.png",
        "truck_figure_decision": PAPER_DIR / "TRUCK_FIGURE_DECISION.json",
        "first_row_gt_decision": PAPER_DIR / "FIRST_ROW_GT_DECISION.md",
        "real_input_output_quality_audit": PAPER_DIR / "REAL_INPUT_OUTPUT_QUALITY_AUDIT.md",
        "real_input_2d_annotations": ROOT.parent
        / "papers"
        / "semantic_proxy_3d"
        / "experiments_root"
        / "sppa_detection_reference"
        / "20260703_real_input_annotations"
        / "real_input_2d_annotations.json",
        "input_provenance": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "inputs" / "input_provenance.json",
        "synthetic_detection_reference_manifest": ROOT.parent
        / "papers"
        / "semantic_proxy_3d"
        / "experiments_root"
        / "sppa_detection_reference"
        / "20260703_synthetic_yolo"
        / "synthetic_detection_reference_manifest.json",
        "restructure_plan": PAPER_DIR / "SPPA_PAPER_RESTRUCTURE_PLAN.md",
        "main_pdf": PAPER_DIR / "semantic_proxy_3d_paper.pdf",
        "submission_supplement_pdf": PAPER_DIR / "semantic_proxy_3d_submission_supplement.pdf",
        "supplement_pdf": PAPER_DIR / "semantic_proxy_3d_technical_supplement.pdf",
        "lightweight_baselines": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_lightweight_baselines" / "20260702_open_label" / "lightweight_baseline_metrics.csv",
        "scheduler_policy_contract": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_descriptor_update" / "20260703_scheduler_policy_contract" / "scheduler_policy_contract.json",
        "calibrated_mask_shape": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_calibrated_mask_shape" / "20260703_synthetic" / "calibrated_mask_shape_summary.json",
        "bandwidth_model": ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_bandwidth" / "20260703_link_budget_model" / "bandwidth_link_model_summary.json",
        "mvfit_protocol_amendment": PAPER_DIR / "SPPA_PROTOCOL_AMENDMENT_02_20260715.md",
        "mvfit_pretest_freeze": PAPER_DIR / "reproducibility" / "sppa_mvfit" / "pretest_freeze.json",
        "mvfit_clean_clone_gate": PAPER_DIR / "reproducibility" / "sppa_mvfit" / "clean_clone_gate.json",
        "mvfit_development_metrics": PAPER_DIR
        / "reproducibility"
        / "sppa_mvfit"
        / "results"
        / "development"
        / "raw_metrics.csv",
        "mvfit_confirmatory_metrics": PAPER_DIR
        / "reproducibility"
        / "sppa_mvfit"
        / "results"
        / "confirmatory"
        / "raw_metrics.csv",
        "mvfit_protocol_audit_pass": PAPER_DIR
        / "editorial_audits"
        / "20260715"
        / "PROTOCOL_AUDIT_PASS.json",
        "mvfit_resolution_sensitivity": PAPER_DIR
        / "reproducibility"
        / "sppa_mvfit"
        / "results"
        / "test"
        / "resolution_sensitivity.json",
    }
    return {name: path.exists() for name, path in checks.items()}


def gate_status(
    files: dict[str, bool],
    provenance: dict[str, Any],
    detection_reference: dict[str, Any],
    real_inputs: dict[str, Any],
    real_input_2d_annotations: dict[str, Any],
    real_yoloe_dual_input: dict[str, Any],
) -> list[dict[str, str]]:
    gates: list[dict[str, str]] = []
    real_probe_summaries = ", ".join(
        (
            f"{probe['label']}:input={probe['readable_input_image']},"
            f"crop512={probe['image_to_3d_crop_512_exists']},"
            f"repo_hits={probe['repo_yolo_valid_target_hits']},"
            f"coco_hits={probe['coco_yolo_valid_target_hits']},"
            f"run={probe['run_exists'] and probe['objects_csv_exists']}"
        )
        for probe in real_inputs.get("probes", [])
    ) or "none"
    bounded_common_ready = files["mvfit_protocol_audit_pass"] and files["mvfit_confirmatory_metrics"]
    bounded_common_development = (
        files["mvfit_protocol_amendment"]
        and files["mvfit_pretest_freeze"]
        and files["mvfit_development_metrics"]
    )
    detector_ready = (
        real_yoloe_dual_input["exists"]
        and real_yoloe_dual_input["case_count"] > 0
        and real_yoloe_dual_input["detector_ready_count"] == real_yoloe_dual_input["case_count"]
        and files["sota_image_alignment_metrics"]
    )
    gates.append(
        {
            "gate": "common_representation_benchmark",
            "status": "complete" if bounded_common_ready else "partial" if bounded_common_development else "missing",
            "evidence": (
                "The amended family-conditioned multiview-fitting protocol has a valid external protocol-audit pass "
                "and held-out confirmatory raw metrics."
                if bounded_common_ready
                else "The amended protocol, executable freeze, and development-only metrics exist, but the mandatory "
                "external protocol audit and held-out confirmatory run are absent. The historical task-fit ranking is excluded."
            ),
        }
    )
    gates.append(
        {
            "gate": "detection_derived_evidence",
            "status": "complete" if detector_ready else "partial"
            if (
                detection_reference["ground_truth_items"] > 0
                or provenance["detector_crop_items"] > 0
                or provenance["ground_truth_items"] > 0
                or real_input_2d_annotations["bbox_gt_2d_items"] > 0
                or real_inputs["readable_input_images"] > 0
            )
            else "missing",
            "evidence": (
                f"Real YOLOE dual-input detector-ready cases={real_yoloe_dual_input['detector_ready_count']}/"
                f"{real_yoloe_dual_input['case_count']}, alignment_metrics={files['sota_image_alignment_metrics']}. "
                f"Visual-grid provenance has {provenance['detector_crop_items']} detector crops and "
                f"{provenance['ground_truth_items']} ground-truth items. Separate detection-reference manifest has "
                f"{detection_reference['ground_truth_items']} synthetic GT bbox items, "
                f"{detection_reference['readable_image_items']} readable image crops, labels={detection_reference['labels']}. "
                f"Real-input 2D annotation manifest has bbox_gt_2d_items={real_input_2d_annotations['bbox_gt_2d_items']}, "
                f"gt_3d_items={real_input_2d_annotations['gt_3d_items']}, labels={real_input_2d_annotations['labels']}. "
                f"Real input probes ({real_inputs['count']}) have readable_images={real_inputs['readable_input_images']}, "
                f"crop512={real_inputs['image_to_3d_crop_512_count']}, runs_ready={real_inputs['runs_ready']}, "
                f"figure={real_inputs['real_input_probe_figure']}; {real_probe_summaries}."
            ),
        }
    )
    gates.append(
        {
            "gate": "phase_aligned_unreal_profiling",
            "status": "complete"
            if files["phase_aligned_unreal_profile_csv"] and files["phase_aligned_unreal_profile_md"]
            else "partial",
            "evidence": (
                "Phase-separated packaged Unreal counters are registered for frame, GameThread, RenderThread, RHI, GPU, memory, and render micro-events."
                if files["phase_aligned_unreal_profile_csv"] and files["phase_aligned_unreal_profile_md"]
                else "Selected Unreal evidence exists in the paper, but the phase-aligned profile artifact is incomplete."
            ),
        }
    )
    gates.append(
        {
            "gate": "flight_or_sim_scheduler_rates",
            "status": "complete"
            if files["scheduler_policy_contract"]
            and files["scheduler_active_track_replay_csv"]
            and files["scheduler_active_track_replay_md"]
            else "partial"
            if files["scheduler_policy_contract"]
            else "missing",
            "evidence": (
                "Scheduler policy contract and active-track replay artifacts are registered with create/update/no-op rates."
                if files["scheduler_policy_contract"]
                and files["scheduler_active_track_replay_csv"]
                and files["scheduler_active_track_replay_md"]
                else "Scheduler policy rows exist, but final active-track replay evidence is not established as a submission gate."
            ),
        }
    )
    return gates


def sota_ranking_readiness_status(
    files: dict[str, bool],
    provenance: dict[str, Any],
    detection_reference: dict[str, Any],
    real_inputs: dict[str, Any],
    real_input_2d_annotations: dict[str, Any],
    real_yoloe_dual_input: dict[str, Any],
) -> dict[str, Any]:
    requirements: list[dict[str, str]] = []

    def add(key: str, status: str, evidence: str, missing: str) -> None:
        requirements.append({"key": key, "status": status, "evidence": evidence, "missing": missing})

    local_methods = ["SPPA", "TripoSR", "Hunyuan3D", "Shap-E", "Point-E"]
    expected_modern_methods = [
        "TRELLIS.2",
        "Pixal3D",
        "Hunyuan3D 2.1",
        "Stable Fast 3D",
        "SPAR3D",
        "TripoSG/Tripo P1",
        "Direct3D-S2",
        "PartCrafter",
        "Rodin Gen-2.5",
        "TripoSR",
    ]

    add(
        "common_inputs",
        "complete"
        if real_yoloe_dual_input["bounded_dual_input_claim_ready"]
        else "partial"
        if provenance["items"] >= 6 and real_inputs["count"] >= 2
        else "missing",
        (
            f"{provenance['items']} synthetic proxy crops, {real_inputs['count']} real-input probes, and "
            f"{real_yoloe_dual_input['case_count']} frozen real YOLOE dual-input cases exist. "
            "The six-case visual grid remains a qualitative input-alignment audit."
        ),
        "Use one frozen public or recorded detection dataset for every compared method, with per-item provenance.",
    )
    add(
        "ground_truth_references",
        "missing"
        if provenance["reference_mesh_items"] == 0 and real_inputs["has_reference_mesh"] is False
        else "partial",
        (
            f"visual_grid_gt={provenance['ground_truth_items']}, visual_grid_masks={provenance['mask_items']}, "
            f"visual_grid_reference_meshes={provenance['reference_mesh_items']}, "
            f"real_input_gt={real_inputs['is_ground_truth']}, real_input_reference_mesh={real_inputs['has_reference_mesh']}; "
            f"synthetic_bbox_only_items={detection_reference['ground_truth_items']}, "
            f"real_input_bbox_gt_2d_items={real_input_2d_annotations['bbox_gt_2d_items']}, "
            f"real_input_gt_3d_items={real_input_2d_annotations['gt_3d_items']}."
        ),
        "Add annotated masks/footprints, 3D reference meshes, or a documented human-preference protocol.",
    )
    add(
        "detector_evidence_separated_from_gt",
        "complete"
        if real_yoloe_dual_input["detector_ready_count"] == real_yoloe_dual_input["case_count"]
        and real_yoloe_dual_input["case_count"] > 0
        else "partial"
        if real_inputs["readable_input_images"]
        else "missing",
        (
            f"real_input_images={real_inputs['readable_input_images']}, "
            f"manual_bbox_gt_2d_items={real_input_2d_annotations['bbox_gt_2d_items']}, "
            f"legacy_detector_valid_target_hits={sum(probe['repo_yolo_valid_target_hits'] + probe['coco_yolo_valid_target_hits'] for probe in real_inputs['probes'])}, "
            f"real_yoloe_detector_ready={real_yoloe_dual_input['detector_ready_count']}/{real_yoloe_dual_input['case_count']}; "
            "reviewed tags are recorded separately from detector outputs."
        ),
        "Record detector crops with bbox/mask/class confidence and keep them distinct from reviewed semantic tags and GT.",
    )
    add(
        "quality_metrics",
        "partial"
        if files["sota_image_alignment_metrics"] and files["sota_preference_protocol"]
        else "missing",
        (
            "Detector image-alignment metrics and a human/task preference protocol are registered. "
            "Chamfer/F-score/normal-consistency and completed human scores remain unavailable because no 3D references exist."
            if files["sota_image_alignment_metrics"] and files["sota_preference_protocol"]
            else "No Chamfer/F-score/normal-consistency, 2D reprojection, image-alignment, or human-preference metric artifact is registered in this precheck."
        ),
        "Implement at least one reference-based metric for GT cases and one declared perceptual/preference metric for non-GT visual quality.",
    )
    add(
        "contemporary_method_set",
        "partial",
        (
            f"Local reproduced methods: {', '.join(local_methods)}. Expected modern comparison set includes "
            f"{', '.join(expected_modern_methods)}; not all are reproduced here. Exclusions documented={files['sota_method_exclusions']}."
        ),
        "Run or explicitly exclude the venue-expected 2025/2026 image-to-3D methods under the same protocol.",
    )
    add(
        "visual_leaderboard_claim",
        "missing",
        "The historical task-fit ranking is circular and excluded; the comparative figure is only an input-alignment audit.",
        "Only publish a full visual image-to-3D leaderboard after all ranked rows are backed by common inputs, metrics, and reproducible method outputs.",
    )

    status_counts = {status: sum(1 for row in requirements if row["status"] == status) for status in ["complete", "partial", "missing"]}
    full_visual_leaderboard_ready = status_counts["missing"] == 0 and status_counts["partial"] == 0
    claim_posture = (
        "full_visual_image_to_3d_leaderboard_ready"
        if full_visual_leaderboard_ready
        else "ambitious_bounded_systems_claim"
    )
    return {
        "claim_posture": claim_posture,
        "full_visual_image_to_3d_leaderboard_ready": full_visual_leaderboard_ready,
        "supported_publication_claim": (
            "No comparative publication claim is currently supported. The multiview fitting result is development-only, "
            "and the current visual comparison remains an input-alignment audit."
        ),
        "recommended_comparative_figure_role": "qualitative input-alignment audit" if not full_visual_leaderboard_ready else "full visual image-to-3D leaderboard",
        "should_use_first_row_as_ground_truth": provenance["can_label_first_row_as_ground_truth"] and real_inputs["is_ground_truth"],
        "requirements": requirements,
        "status_counts": status_counts,
    }


def build_report() -> dict[str, Any]:
    main_tex_path = PAPER_DIR / "semantic_proxy_3d_paper.tex"
    submission_supplement_tex_path = PAPER_DIR / "semantic_proxy_3d_submission_supplement.tex"
    supplement_tex_path = PAPER_DIR / "semantic_proxy_3d_technical_supplement.tex"
    main_pdf = PAPER_DIR / "semantic_proxy_3d_paper.pdf"
    submission_supplement_pdf = PAPER_DIR / "semantic_proxy_3d_submission_supplement.pdf"
    supplement_pdf = PAPER_DIR / "semantic_proxy_3d_technical_supplement.pdf"
    provenance_path = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "inputs" / "input_provenance.json"
    detection_reference_path = (
        ROOT.parent
        / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
        / "sppa_detection_reference"
        / "20260703_synthetic_yolo"
        / "synthetic_detection_reference_manifest.json"
    )
    real_input_2d_annotations_path = (
        ROOT.parent
        / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
        / "sppa_detection_reference"
        / "20260703_real_input_annotations"
        / "real_input_2d_annotations.json"
    )
    sota_protocol_readiness_path = PAPER_DIR / "benchmarks" / "results" / "sota_protocol_readiness.json"
    dual_input_sota_readiness_path = PAPER_DIR / "benchmarks" / "results" / "sota_dual_input_readiness.json"
    real_yoloe_dual_input_benchmark_path = (
        PAPER_DIR / "benchmarks" / "results" / "real_yoloe_dual_input_benchmark.json"
    )
    real_image_assumed_flight_replay_path = PAPER_DIR / "benchmarks" / "results" / "real_image_assumed_flight_replay.json"
    supplement_triage_path = PAPER_DIR / "SUPPLEMENT_TRIAGE.json"
    visual_material_audit_path = PAPER_DIR / "benchmarks" / "results" / "sppa_visual_material_audit.json"
    sppa_runtime_budget_path = PAPER_DIR / "benchmarks" / "results" / "sppa_runtime_budget.json"
    sppa_evidence_channel_coverage_path = (
        PAPER_DIR / "benchmarks" / "results" / "sppa_evidence_channel_coverage.json"
    )
    sppa_evidence_channel_coverage_tex_path = (
        PAPER_DIR / "benchmarks" / "results" / "sppa_evidence_channel_coverage.tex"
    )
    sppa_evidence_channel_coverage_figure_path = PAPER_DIR / "figures" / "sppa_evidence_channel_coverage.png"
    sppa_visual_part_evidence_audit_path = (
        PAPER_DIR / "benchmarks" / "results" / "sppa_visual_part_evidence_audit.json"
    )
    sppa_visual_part_evidence_grid_path = (
        PAPER_DIR / "benchmarks" / "results" / "sppa_visual_part_evidence_grid.json"
    )
    sppa_visual_part_evidence_grid_figure_path = PAPER_DIR / "figures" / "sppa_visual_part_evidence_grid.png"
    sppa_visual_metric_yaw_consistency_path = (
        PAPER_DIR / "benchmarks" / "results" / "sppa_visual_metric_yaw_consistency.json"
    )
    sppa_descriptor_contract_audit_path = (
        PAPER_DIR / "benchmarks" / "results" / "sppa_descriptor_contract_audit.json"
    )
    sppa_connector_constraints_path = PAPER_DIR / "benchmarks" / "results" / "sppa_connector_constraints.json"
    sppa_connector_constraints_tex_path = PAPER_DIR / "benchmarks" / "results" / "sppa_connector_constraints.tex"
    agnostic_image_space_parts_probe_path = (
        PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_image_space_parts_probe.json"
    )
    agnostic_image_space_parts_verify_path = (
        PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_image_space_parts_verify.json"
    )
    agnostic_label_invariance_path = PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_label_invariance.json"
    agnostic_identity_invariance_path = PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_identity_invariance.json"
    agnostic_path_invariance_path = PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_path_invariance.json"
    agnostic_detection_representation_invariance_path = (
        PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_detection_representation_invariance.json"
    )
    agnostic_side_channel_invariance_path = (
        PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_side_channel_invariance.json"
    )
    agnostic_mirror_equivariance_path = (
        PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_mirror_equivariance.json"
    )
    agnostic_photometric_stability_path = (
        PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_photometric_stability.json"
    )
    agnostic_synthetic_part_controls_path = (
        PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_synthetic_part_controls.json"
    )
    agnostic_synthetic_controls_figure_path = PAPER_DIR / "figures" / "sppa_agnostic_synthetic_controls_grid.png"
    agnostic_synthetic_sweep_path = PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_synthetic_sweep.json"
    agnostic_synthetic_sweep_figure_path = PAPER_DIR / "figures" / "sppa_agnostic_synthetic_sweep_examples.png"
    agnostic_synthetic_fuzz_path = PAPER_DIR / "benchmarks" / "results" / "sppa_agnostic_synthetic_fuzz.json"
    agnostic_synthetic_fuzz_figure_path = PAPER_DIR / "figures" / "sppa_agnostic_synthetic_fuzz_examples.png"
    visual_bridge_robustness_table_path = (
        PAPER_DIR / "benchmarks" / "results" / "sppa_visual_bridge_robustness_table.json"
    )
    visual_bridge_robustness_table_tex_path = (
        PAPER_DIR / "benchmarks" / "results" / "sppa_visual_bridge_robustness_table.tex"
    )
    agnostic_image_space_parts_figure_path = PAPER_DIR / "figures" / "sppa_agnostic_mask_vs_image_cues_grid.png"
    truck_figure_decision_path = PAPER_DIR / "TRUCK_FIGURE_DECISION.json"
    main_tex = read_text(main_tex_path)
    provenance = input_provenance_status(provenance_path)
    detection_reference = detection_reference_status(detection_reference_path)
    real_input_2d_annotations = real_input_2d_annotation_status(real_input_2d_annotations_path)
    real_image_assumed_flight_replay = real_image_assumed_flight_replay_status(real_image_assumed_flight_replay_path)
    real_yoloe_dual_input = real_yoloe_dual_input_status(real_yoloe_dual_input_benchmark_path)
    real_inputs = real_input_probe_status()
    files = evidence_file_status()
    phrases = phrase_status(main_tex)
    main_log = count_log_issues(main_pdf.with_suffix(".log"))
    submission_supplement_log = count_log_issues(submission_supplement_pdf.with_suffix(".log"))
    supplement_log = count_log_issues(supplement_pdf.with_suffix(".log"))
    gates = gate_status(
        files,
        provenance,
        detection_reference,
        real_inputs,
        real_input_2d_annotations,
        real_yoloe_dual_input,
    )
    sota_readiness = sota_ranking_readiness_status(
        files,
        provenance,
        detection_reference,
        real_inputs,
        real_input_2d_annotations,
        real_yoloe_dual_input,
    )
    sota_protocol_report = load_json(sota_protocol_readiness_path)
    dual_input_sota_report = load_json(dual_input_sota_readiness_path)
    supplement_triage = load_json(supplement_triage_path)
    visual_material_audit = load_json(visual_material_audit_path)
    sppa_runtime_budget = load_json(sppa_runtime_budget_path)
    sppa_evidence_channel_coverage = evidence_channel_coverage_status(
        sppa_evidence_channel_coverage_path,
        sppa_evidence_channel_coverage_tex_path,
        sppa_evidence_channel_coverage_figure_path,
    )
    sppa_visual_part_evidence_audit = load_json(sppa_visual_part_evidence_audit_path)
    sppa_visual_part_evidence_grid = load_json(sppa_visual_part_evidence_grid_path)
    sppa_visual_metric_yaw_consistency = load_json(sppa_visual_metric_yaw_consistency_path)
    sppa_descriptor_contract_audit = load_json(sppa_descriptor_contract_audit_path)
    sppa_connector_constraints = load_json(sppa_connector_constraints_path)
    agnostic_image_space_parts_probe = load_json(agnostic_image_space_parts_probe_path)
    agnostic_image_space_parts_verify = load_json(agnostic_image_space_parts_verify_path)
    agnostic_label_invariance = load_json(agnostic_label_invariance_path)
    agnostic_identity_invariance = load_json(agnostic_identity_invariance_path)
    agnostic_path_invariance = load_json(agnostic_path_invariance_path)
    agnostic_detection_representation_invariance = load_json(agnostic_detection_representation_invariance_path)
    agnostic_side_channel_invariance = load_json(agnostic_side_channel_invariance_path)
    agnostic_mirror_equivariance = load_json(agnostic_mirror_equivariance_path)
    agnostic_photometric_stability = load_json(agnostic_photometric_stability_path)
    agnostic_synthetic_part_controls = load_json(agnostic_synthetic_part_controls_path)
    agnostic_synthetic_sweep = load_json(agnostic_synthetic_sweep_path)
    agnostic_synthetic_fuzz = load_json(agnostic_synthetic_fuzz_path)
    visual_bridge_robustness_table = load_json(visual_bridge_robustness_table_path)
    agnostic_probe_row_count = len(agnostic_image_space_parts_probe.get("rows", []))
    truck_figure_decision = load_json(truck_figure_decision_path)

    blockers: list[str] = []
    warnings: list[str] = []

    if not all(phrases.values()):
        missing = [name for name, ok in phrases.items() if not ok]
        blockers.append("main manuscript is missing claim-boundary phrases: " + ", ".join(missing))
    if not files["mvfit_protocol_audit_pass"]:
        blockers.append(
            "amended SPPA-MVFit protocol lacks the mandatory valid three-reviewer external audit pass; "
            "held-out seed derivation and test execution remain prohibited"
        )
    if not files["mvfit_confirmatory_metrics"]:
        blockers.append(
            "held-out confirmatory SPPA-MVFit raw metrics are absent; development-only metrics cannot support a submission claim"
        )
    if provenance["can_label_first_row_as_ground_truth"]:
        warnings.append("first row can be labeled as ground truth according to manifest; verify caption is updated intentionally")
    else:
        if "ground truth" in main_tex.lower() and not phrases["states_not_real_detection_gt"]:
            blockers.append("main manuscript mentions ground truth without the required not-real-detection-ground-truth boundary")
    if main_log["latex_errors"] or main_log["undefined_citations"] or main_log["undefined_references"]:
        blockers.append("main PDF log has LaTeX errors or unresolved citations/references")
    if (
        submission_supplement_pdf.exists()
        and (
            submission_supplement_log["latex_errors"]
            or submission_supplement_log["undefined_citations"]
            or submission_supplement_log["undefined_references"]
            or submission_supplement_log["overfull"]
        )
    ):
        blockers.append("submission supplement PDF log has LaTeX errors, unresolved references, or overfull boxes")
    if supplement_log["latex_errors"] or supplement_log["undefined_citations"] or supplement_log["undefined_references"]:
        blockers.append("supplement PDF log has LaTeX errors or unresolved citations/references")

    submission_supplement_pages = pdf_pages(submission_supplement_pdf)
    supplement_pages = pdf_pages(supplement_pdf)
    formal_supplement_ready = bool(
        submission_supplement_pdf.exists()
        and submission_supplement_tex_path.exists()
        and submission_supplement_pages
        and submission_supplement_pages <= 6
        and not (
            submission_supplement_log["latex_errors"]
            or submission_supplement_log["undefined_citations"]
            or submission_supplement_log["undefined_references"]
            or submission_supplement_log["overfull"]
        )
    )
    if not formal_supplement_ready:
        warnings.append("formal short submission supplement is missing or not clean/page-bounded")
    if supplement_pages and supplement_pages > 12 and not formal_supplement_ready:
        warnings.append(f"supplement is {supplement_pages} pages; treat as artifact log, not formal submission supplement")
    if not supplement_triage_path.exists():
        warnings.append("supplement triage report is missing")
    elif (
        supplement_triage.get("recommendation", {}).get("formal_supplement") == "do_not_submit_current_38_page_file"
        and not formal_supplement_ready
    ):
        warnings.append("supplement triage recommends not submitting the current long supplement as a formal supplement")
    if any(gate["status"] != "complete" for gate in gates):
        blockers.append("full experimental-paper claim is not supported because one or more four-priority gates are partial or missing")
    if not sota_readiness["full_visual_image_to_3d_leaderboard_ready"]:
        warnings.append(
            "full visual image-to-3D leaderboard is not claimed; the historical task-fit ranking is circular and excluded"
        )
    if dual_input_sota_readiness_path.exists() and dual_input_sota_report.get("full_dual_input_leaderboard_ready") is not True:
        if dual_input_sota_report.get("bounded_dual_input_claim_ready") is True:
            warnings.append("bounded dual-input claim is ready, but a full visual dual-input leaderboard remains unclaimed")
        else:
            blockers.append("bounded dual-input claim is not supported because the YOLO-detected image-input track or tag/text track is incomplete")
    if detection_reference["exists"] and detection_reference["readable_image_items"] == 0:
        warnings.append("synthetic detection-reference manifest is bbox-only; no readable crops are available for the visual comparison row")
    if real_inputs["exists"] and not real_inputs["is_ground_truth"]:
        warnings.append("real input probes are image-to-3D crop material and detector stress tests, but not ground truth or reference meshes")
    if real_image_assumed_flight_replay["exists"]:
        if real_image_assumed_flight_replay["telemetry_is_measured"] is not False:
            blockers.append("real-image assumed-flight replay must mark telemetry_is_measured=false")
        if real_image_assumed_flight_replay["failed_count"] > 0:
            blockers.append("real-image assumed-flight replay has failed cases")
        warnings.append("real-image metric replay uses real images and real YOLOE evidence, but telemetry is declared replay input rather than measured flight data")
    if visual_material_audit_path.exists() and visual_material_audit.get("pass") is not True:
        blockers.append("SPPA visual/material audit has failures")
    if not visual_material_audit_path.exists():
        warnings.append("SPPA visual/material audit is missing")
    if sppa_runtime_budget_path.exists() and sppa_runtime_budget.get("status") != "passed":
        blockers.append("SPPA runtime budget regression has failures")
    if not sppa_runtime_budget_path.exists():
        warnings.append("SPPA runtime budget report is missing")
    if not sppa_evidence_channel_coverage["exists"]:
        blockers.append("SPPA evidence-channel coverage report is missing")
    if not sppa_evidence_channel_coverage["tex_exists"]:
        blockers.append("SPPA evidence-channel coverage LaTeX table is missing")
    if not sppa_evidence_channel_coverage["figure_exists"]:
        blockers.append("SPPA evidence-channel coverage figure is missing")
    if sppa_evidence_channel_coverage["exists"]:
        if int(sppa_evidence_channel_coverage["row_count"] or 0) != 12:
            blockers.append("SPPA evidence-channel coverage must cover 12 input-mode rows")
        if int(sppa_evidence_channel_coverage["budget_failures"] or 0) != 0:
            blockers.append("SPPA evidence-channel coverage includes rows outside the lightweight budget")
        if int(sppa_evidence_channel_coverage["visual_improvement_cases"] or 0) != int(
            sppa_evidence_channel_coverage["case_count"] or 0
        ):
            blockers.append("SPPA visual evidence channel does not improve over detector+metric for every real probe")
        summary = sppa_evidence_channel_coverage.get("summary", {})
        text_mean = float(summary.get("tag_only", {}).get("mean_active_evidence_channels", 0) or 0)
        metric_mean = float(summary.get("detector_metric", {}).get("mean_active_evidence_channels", 0) or 0)
        visual_mean = float(summary.get("detector_metric_visual", {}).get("mean_active_evidence_channels", 0) or 0)
        if not (text_mean <= metric_mean < visual_mean):
            blockers.append("SPPA evidence-channel coverage means are not monotonic across text, metric, and visual modes")
    if sppa_visual_part_evidence_audit_path.exists() and sppa_visual_part_evidence_audit.get("status") != "passed":
        blockers.append("SPPA visual part evidence audit has failures")
    if not sppa_visual_part_evidence_audit_path.exists():
        blockers.append("SPPA visual part evidence audit is missing")
    if not sppa_visual_part_evidence_grid_path.exists():
        blockers.append("SPPA visual part evidence grid report is missing")
    if not sppa_visual_part_evidence_grid_figure_path.exists():
        blockers.append("SPPA visual part evidence grid figure is missing")
    if sppa_visual_metric_yaw_consistency_path.exists() and sppa_visual_metric_yaw_consistency.get("status") != "passed":
        blockers.append("SPPA visual-metric yaw consistency audit has failures")
    if not sppa_visual_metric_yaw_consistency_path.exists():
        blockers.append("SPPA visual-metric yaw consistency audit is missing")
    if sppa_descriptor_contract_audit_path.exists() and sppa_descriptor_contract_audit.get("status") != "passed":
        blockers.append("SPPA descriptor contract audit has failures")
    if not sppa_descriptor_contract_audit_path.exists():
        blockers.append("SPPA descriptor contract audit is missing")
    if sppa_connector_constraints_path.exists() and int(sppa_connector_constraints.get("failed", 0) or 0) > 0:
        blockers.append("SPPA connector constraint regression has failures")
    if not sppa_connector_constraints_path.exists():
        blockers.append("SPPA connector constraint regression is missing")
    if not sppa_connector_constraints_tex_path.exists():
        blockers.append("SPPA connector constraint LaTeX table is missing")
    if agnostic_image_space_parts_verify_path.exists() and agnostic_image_space_parts_verify.get("status") != "pass":
        blockers.append("agnostic image-space parts probe verification has failures")
    if agnostic_image_space_parts_probe_path.exists() and not agnostic_image_space_parts_verify_path.exists():
        warnings.append("agnostic image-space parts probe exists but verification report is missing")
    if not agnostic_image_space_parts_probe_path.exists():
        warnings.append("agnostic image-space parts probe is missing; image-to-primitive bridge remains untested")
    if agnostic_label_invariance_path.exists() and agnostic_label_invariance.get("status") != "pass":
        blockers.append("agnostic label-invariance verification has failures")
    if agnostic_image_space_parts_probe_path.exists() and not agnostic_label_invariance_path.exists():
        warnings.append("agnostic image-space parts probe exists but label-invariance verification is missing")
    if agnostic_identity_invariance_path.exists() and agnostic_identity_invariance.get("status") != "pass":
        blockers.append("agnostic identity-invariance verification has failures")
    if agnostic_image_space_parts_probe_path.exists() and not agnostic_identity_invariance_path.exists():
        warnings.append("agnostic image-space parts probe exists but case-identity invariance verification is missing")
    if agnostic_path_invariance_path.exists() and agnostic_path_invariance.get("status") != "pass":
        blockers.append("agnostic path-invariance verification has failures")
    if agnostic_image_space_parts_probe_path.exists() and not agnostic_path_invariance_path.exists():
        warnings.append("agnostic image-space parts probe exists but image-path/name invariance verification is missing")
    if (
        agnostic_detection_representation_invariance_path.exists()
        and agnostic_detection_representation_invariance.get("status") != "pass"
    ):
        blockers.append("agnostic detection-representation invariance verification has failures")
    if agnostic_image_space_parts_probe_path.exists() and not agnostic_detection_representation_invariance_path.exists():
        warnings.append(
            "agnostic image-space parts probe exists but detection-order/duplicate-mask invariance verification is missing"
        )
    if agnostic_side_channel_invariance_path.exists() and agnostic_side_channel_invariance.get("status") != "pass":
        blockers.append("agnostic combined side-channel invariance verification has failures")
    if agnostic_image_space_parts_probe_path.exists() and not agnostic_side_channel_invariance_path.exists():
        warnings.append("agnostic image-space parts probe exists but combined side-channel invariance verification is missing")
    if agnostic_mirror_equivariance_path.exists() and agnostic_mirror_equivariance.get("status") != "pass":
        blockers.append("agnostic mirror-equivariance verification has primary failures")
    if agnostic_image_space_parts_probe_path.exists() and not agnostic_mirror_equivariance_path.exists():
        warnings.append("agnostic image-space parts probe exists but mirror-equivariance verification is missing")
    if agnostic_mirror_equivariance.get("audit_warnings"):
        warnings.append(
            "agnostic mirror-equivariance has secondary audit warnings: "
            + str(len(agnostic_mirror_equivariance.get("audit_warnings") or []))
        )
    if agnostic_photometric_stability_path.exists() and agnostic_photometric_stability.get("status") != "pass":
        blockers.append("agnostic photometric-stability verification has primary failures")
    if agnostic_image_space_parts_probe_path.exists() and not agnostic_photometric_stability_path.exists():
        warnings.append("agnostic image-space parts probe exists but photometric-stability verification is missing")
    if agnostic_photometric_stability.get("audit_warnings"):
        warnings.append(
            "agnostic photometric-stability has secondary audit warnings: "
            + str(len(agnostic_photometric_stability.get("audit_warnings") or []))
        )
    if agnostic_probe_row_count:
        coverage_checks = [
            ("label-invariance", agnostic_label_invariance_path, agnostic_label_invariance),
            ("case-identity invariance", agnostic_identity_invariance_path, agnostic_identity_invariance),
            ("image-path/name invariance", agnostic_path_invariance_path, agnostic_path_invariance),
            (
                "detection-order/duplicate-mask invariance",
                agnostic_detection_representation_invariance_path,
                agnostic_detection_representation_invariance,
            ),
            ("combined side-channel invariance", agnostic_side_channel_invariance_path, agnostic_side_channel_invariance),
            ("mirror equivariance", agnostic_mirror_equivariance_path, agnostic_mirror_equivariance),
            ("photometric stability", agnostic_photometric_stability_path, agnostic_photometric_stability),
        ]
        for name, path, payload in coverage_checks:
            if path.exists() and int(payload.get("rows_checked") or 0) != agnostic_probe_row_count:
                blockers.append(
                    f"agnostic {name} verification covers "
                    f"{int(payload.get('rows_checked') or 0)} / {agnostic_probe_row_count} real probe rows"
                )
    if agnostic_synthetic_part_controls_path.exists() and agnostic_synthetic_part_controls.get("status") != "pass":
        blockers.append("agnostic synthetic part controls have failures")
    if agnostic_image_space_parts_probe_path.exists() and not agnostic_synthetic_part_controls_path.exists():
        warnings.append("agnostic image-space parts probe exists but synthetic primitive controls are missing")
    if agnostic_synthetic_sweep_path.exists() and agnostic_synthetic_sweep.get("status") != "pass":
        blockers.append("agnostic synthetic sweep has failures")
    if agnostic_image_space_parts_probe_path.exists() and not agnostic_synthetic_sweep_path.exists():
        warnings.append("agnostic image-space parts probe exists but synthetic sweep metrics are missing")
    if agnostic_synthetic_fuzz_path.exists() and agnostic_synthetic_fuzz.get("status") != "pass":
        blockers.append("agnostic synthetic fuzz has failures")
    if agnostic_image_space_parts_probe_path.exists() and not agnostic_synthetic_fuzz_path.exists():
        warnings.append("agnostic image-space parts probe exists but multi-seed synthetic fuzz is missing")
    if visual_bridge_robustness_table_path.exists() and visual_bridge_robustness_table.get("status") != "passed":
        blockers.append("SPPA visual bridge robustness table has failures")
    if not visual_bridge_robustness_table_path.exists():
        blockers.append("SPPA visual bridge robustness table JSON is missing")
    if not visual_bridge_robustness_table_tex_path.exists():
        blockers.append("SPPA visual bridge robustness LaTeX table is missing")
    if truck_figure_decision_path.exists() and truck_figure_decision.get("pass") is not True:
        blockers.append("truck figure decision audit has failures")
    if not truck_figure_decision_path.exists():
        warnings.append("truck figure decision audit is missing")

    return {
        "main_tex": str(main_tex_path),
        "submission_supplement_tex": str(submission_supplement_tex_path) if submission_supplement_tex_path.exists() else None,
        "supplement_tex": str(supplement_tex_path) if supplement_tex_path.exists() else None,
        "main_pdf_pages": pdf_pages(main_pdf),
        "submission_supplement_pdf_pages": submission_supplement_pages,
        "submission_supplement_ready": formal_supplement_ready,
        "supplement_pdf_pages": supplement_pages,
        "input_provenance": provenance,
        "detection_reference": detection_reference,
        "real_input_2d_annotations": real_input_2d_annotations,
        "real_image_assumed_flight_replay": {
            "path": str(real_image_assumed_flight_replay_path),
            **real_image_assumed_flight_replay,
        },
        "real_yoloe_dual_input_benchmark": {
            "path": str(real_yoloe_dual_input_benchmark_path),
            **real_yoloe_dual_input,
        },
        "real_input_probes": real_inputs,
        "claim_phrases": phrases,
        "files": files,
        "main_log": main_log,
        "submission_supplement_log": submission_supplement_log,
        "supplement_log": supplement_log,
        "four_priority_gates": gates,
        "sota_ranking_readiness": sota_readiness,
        "sota_protocol_readiness_report": {
            "path": str(sota_protocol_readiness_path),
            "exists": sota_protocol_readiness_path.exists(),
            "claim_posture": (sota_protocol_report.get("claim_posture") or {}).get("headline"),
            "full_visual_image_to_3d_leaderboard_ready": sota_protocol_report.get("can_claim_image_to_3d_sota_leaderboard"),
            "runtime_semantic_proxy_task_fit_ready": sota_protocol_report.get("can_claim_runtime_task_fit_ranking"),
            "status_counts": sota_protocol_report.get("status_counts", {}),
        },
        "dual_input_sota_readiness_report": {
            "path": str(dual_input_sota_readiness_path),
            "exists": dual_input_sota_readiness_path.exists(),
            "claim_posture": dual_input_sota_report.get("claim_posture"),
            "bounded_dual_input_claim_ready": dual_input_sota_report.get("bounded_dual_input_claim_ready"),
            "full_dual_input_leaderboard_ready": dual_input_sota_report.get("full_dual_input_leaderboard_ready"),
            "status_counts": dual_input_sota_report.get("status_counts", {}),
        },
        "supplement_triage": {
            "path": str(supplement_triage_path),
            "exists": supplement_triage_path.exists(),
            "formal_supplement": supplement_triage.get("recommendation", {}).get("formal_supplement"),
            "preferred_shape": supplement_triage.get("recommendation", {}).get("preferred_shape"),
            "pdf_pages": supplement_triage.get("pdf_pages"),
            "line_count": supplement_triage.get("line_count"),
            "decision_counts": supplement_triage.get("decision_counts", {}),
        },
        "sppa_visual_material_audit": {
            "path": str(visual_material_audit_path),
            "exists": visual_material_audit_path.exists(),
            "pass": visual_material_audit.get("pass"),
            "failures": visual_material_audit.get("failures", []),
            "claim_boundary": visual_material_audit.get("claim_boundary"),
        },
        "sppa_runtime_budget": {
            "path": str(sppa_runtime_budget_path),
            "exists": sppa_runtime_budget_path.exists(),
            "status": sppa_runtime_budget.get("status"),
            "summary": sppa_runtime_budget.get("summary", {}),
            "budgets": sppa_runtime_budget.get("budgets", {}),
            "failures": sppa_runtime_budget.get("failures", []),
            "claim_boundary": sppa_runtime_budget.get("claim_boundary"),
        },
        "sppa_evidence_channel_coverage": {
            "path": str(sppa_evidence_channel_coverage_path),
            "exists": sppa_evidence_channel_coverage["exists"],
            "tex_path": str(sppa_evidence_channel_coverage_tex_path),
            "tex_exists": sppa_evidence_channel_coverage["tex_exists"],
            "figure": str(sppa_evidence_channel_coverage_figure_path),
            "figure_exists": sppa_evidence_channel_coverage["figure_exists"],
            "row_count": sppa_evidence_channel_coverage["row_count"],
            "case_count": sppa_evidence_channel_coverage["case_count"],
            "summary": sppa_evidence_channel_coverage["summary"],
            "budget_failures": sppa_evidence_channel_coverage["budget_failures"],
            "visual_improvement_cases": sppa_evidence_channel_coverage["visual_improvement_cases"],
            "claim_boundary": sppa_evidence_channel_coverage["claim_boundary"],
        },
        "sppa_visual_part_evidence": {
            "path": str(sppa_visual_part_evidence_audit_path),
            "exists": sppa_visual_part_evidence_audit_path.exists(),
            "status": sppa_visual_part_evidence_audit.get("status"),
            "failures": sppa_visual_part_evidence_audit.get("failures", []),
            "rows_checked": len(sppa_visual_part_evidence_audit.get("rows", [])),
            "grid_path": str(sppa_visual_part_evidence_grid_path),
            "grid_exists": sppa_visual_part_evidence_grid_path.exists(),
            "figure": str(sppa_visual_part_evidence_grid_figure_path),
            "figure_exists": sppa_visual_part_evidence_grid_figure_path.exists(),
            "grid_rows": len(sppa_visual_part_evidence_grid.get("rows", [])),
            "claim_boundary": sppa_visual_part_evidence_audit.get("claim_boundary"),
        },
        "sppa_visual_metric_yaw_consistency": {
            "path": str(sppa_visual_metric_yaw_consistency_path),
            "exists": sppa_visual_metric_yaw_consistency_path.exists(),
            "status": sppa_visual_metric_yaw_consistency.get("status"),
            "rows_checked": len(sppa_visual_metric_yaw_consistency.get("rows", [])),
            "aligned_count": sppa_visual_metric_yaw_consistency.get("aligned_count"),
            "weakly_aligned_count": sppa_visual_metric_yaw_consistency.get("weakly_aligned_count"),
            "divergent_declared_count": sppa_visual_metric_yaw_consistency.get("divergent_declared_count"),
            "projected_aligned_count": sppa_visual_metric_yaw_consistency.get("projected_aligned_count"),
            "projected_weakly_aligned_count": sppa_visual_metric_yaw_consistency.get(
                "projected_weakly_aligned_count"
            ),
            "projected_divergent_declared_count": sppa_visual_metric_yaw_consistency.get(
                "projected_divergent_declared_count"
            ),
            "descriptor_recorded_count": sppa_visual_metric_yaw_consistency.get("descriptor_recorded_count"),
            "max_descriptor_bytes": sppa_visual_metric_yaw_consistency.get("max_descriptor_bytes"),
            "failures": sppa_visual_metric_yaw_consistency.get("failures", []),
            "audit_warnings": sppa_visual_metric_yaw_consistency.get("audit_warnings", []),
            "claim_boundary": sppa_visual_metric_yaw_consistency.get("claim_boundary"),
        },
        "sppa_descriptor_contract_audit": {
            "path": str(sppa_descriptor_contract_audit_path),
            "exists": sppa_descriptor_contract_audit_path.exists(),
            "status": sppa_descriptor_contract_audit.get("status"),
            "rows_checked": sppa_descriptor_contract_audit.get("row_count"),
            "failed_rows": sppa_descriptor_contract_audit.get("failed_count"),
            "visual_metric_contract_rows": sppa_descriptor_contract_audit.get("visual_metric_contract_count"),
            "max_descriptor_bytes": sppa_descriptor_contract_audit.get("max_descriptor_bytes"),
            "failures": sppa_descriptor_contract_audit.get("failures", []),
            "claim_boundary": sppa_descriptor_contract_audit.get("claim_boundary"),
        },
        "sppa_connector_constraints": {
            "path": str(sppa_connector_constraints_path),
            "exists": sppa_connector_constraints_path.exists(),
            "tex_path": str(sppa_connector_constraints_tex_path),
            "tex_exists": sppa_connector_constraints_tex_path.exists(),
            "status": sppa_connector_constraints.get("status")
            or ("passed" if sppa_connector_constraints_path.exists() and int(sppa_connector_constraints.get("failed", 0) or 0) == 0 else "failed"),
            "rows_checked": len(sppa_connector_constraints.get("rows", [])),
            "failed": int(sppa_connector_constraints.get("failed", 0) or 0),
            "rows": sppa_connector_constraints.get("rows", []),
            "claim_boundary": sppa_connector_constraints.get("claim_boundary"),
        },
        "agnostic_image_space_parts": {
            "path": str(agnostic_image_space_parts_probe_path),
            "exists": agnostic_image_space_parts_probe_path.exists(),
            "figure": str(agnostic_image_space_parts_figure_path),
            "figure_exists": agnostic_image_space_parts_figure_path.exists(),
            "verify_path": str(agnostic_image_space_parts_verify_path),
            "verify_exists": agnostic_image_space_parts_verify_path.exists(),
            "verify_status": agnostic_image_space_parts_verify.get("status"),
            "label_invariance_path": str(agnostic_label_invariance_path),
            "label_invariance_exists": agnostic_label_invariance_path.exists(),
            "label_invariance_status": agnostic_label_invariance.get("status"),
            "label_invariance_rows_checked": agnostic_label_invariance.get("rows_checked"),
            "identity_invariance_path": str(agnostic_identity_invariance_path),
            "identity_invariance_exists": agnostic_identity_invariance_path.exists(),
            "identity_invariance_status": agnostic_identity_invariance.get("status"),
            "identity_invariance_rows_checked": agnostic_identity_invariance.get("rows_checked"),
            "path_invariance_path": str(agnostic_path_invariance_path),
            "path_invariance_exists": agnostic_path_invariance_path.exists(),
            "path_invariance_status": agnostic_path_invariance.get("status"),
            "path_invariance_rows_checked": agnostic_path_invariance.get("rows_checked"),
            "detection_representation_invariance_path": str(agnostic_detection_representation_invariance_path),
            "detection_representation_invariance_exists": agnostic_detection_representation_invariance_path.exists(),
            "detection_representation_invariance_status": agnostic_detection_representation_invariance.get("status"),
            "detection_representation_invariance_rows_checked": agnostic_detection_representation_invariance.get(
                "rows_checked"
            ),
            "detection_representation_invariance_variants_checked": agnostic_detection_representation_invariance.get(
                "variants_checked"
            ),
            "side_channel_invariance_path": str(agnostic_side_channel_invariance_path),
            "side_channel_invariance_exists": agnostic_side_channel_invariance_path.exists(),
            "side_channel_invariance_status": agnostic_side_channel_invariance.get("status"),
            "side_channel_invariance_rows_checked": agnostic_side_channel_invariance.get("rows_checked"),
            "mirror_equivariance_path": str(agnostic_mirror_equivariance_path),
            "mirror_equivariance_exists": agnostic_mirror_equivariance_path.exists(),
            "mirror_equivariance_status": agnostic_mirror_equivariance.get("status"),
            "mirror_equivariance_rows_checked": agnostic_mirror_equivariance.get("rows_checked"),
            "mirror_equivariance_audit_warning_count": len(agnostic_mirror_equivariance.get("audit_warnings") or []),
            "mirror_equivariance_diagnostic_note_count": len(
                agnostic_mirror_equivariance.get("diagnostic_notes") or []
            ),
            "photometric_stability_path": str(agnostic_photometric_stability_path),
            "photometric_stability_exists": agnostic_photometric_stability_path.exists(),
            "photometric_stability_status": agnostic_photometric_stability.get("status"),
            "photometric_stability_rows_checked": agnostic_photometric_stability.get("rows_checked"),
            "photometric_stability_variants_checked": agnostic_photometric_stability.get("variants_checked"),
            "photometric_stability_audit_warning_count": len(
                agnostic_photometric_stability.get("audit_warnings") or []
            ),
            "photometric_stability_diagnostic_note_count": len(
                agnostic_photometric_stability.get("diagnostic_notes") or []
            ),
            "synthetic_controls_path": str(agnostic_synthetic_part_controls_path),
            "synthetic_controls_exists": agnostic_synthetic_part_controls_path.exists(),
            "synthetic_controls_status": agnostic_synthetic_part_controls.get("status"),
            "synthetic_controls_count": agnostic_synthetic_part_controls.get("control_count"),
            "synthetic_controls_failures": agnostic_synthetic_part_controls.get("failures", []),
            "synthetic_controls_figure": str(agnostic_synthetic_controls_figure_path),
            "synthetic_controls_figure_exists": agnostic_synthetic_controls_figure_path.exists(),
            "synthetic_sweep_path": str(agnostic_synthetic_sweep_path),
            "synthetic_sweep_exists": agnostic_synthetic_sweep_path.exists(),
            "synthetic_sweep_status": agnostic_synthetic_sweep.get("status"),
            "synthetic_sweep_figure": str(agnostic_synthetic_sweep_figure_path),
            "synthetic_sweep_figure_exists": agnostic_synthetic_sweep_figure_path.exists(),
            "synthetic_sweep_summary": agnostic_synthetic_sweep.get("summary", {}),
            "synthetic_fuzz_path": str(agnostic_synthetic_fuzz_path),
            "synthetic_fuzz_exists": agnostic_synthetic_fuzz_path.exists(),
            "synthetic_fuzz_status": agnostic_synthetic_fuzz.get("status"),
            "synthetic_fuzz_figure": str(agnostic_synthetic_fuzz_figure_path),
            "synthetic_fuzz_figure_exists": agnostic_synthetic_fuzz_figure_path.exists(),
            "synthetic_fuzz_seeds": agnostic_synthetic_fuzz.get("seeds", []),
            "synthetic_fuzz_summary": agnostic_synthetic_fuzz.get("summary", {}),
            "visual_bridge_robustness_table_path": str(visual_bridge_robustness_table_path),
            "visual_bridge_robustness_table_exists": visual_bridge_robustness_table_path.exists(),
            "visual_bridge_robustness_table_tex": str(visual_bridge_robustness_table_tex_path),
            "visual_bridge_robustness_table_tex_exists": visual_bridge_robustness_table_tex_path.exists(),
            "visual_bridge_robustness_table_status": visual_bridge_robustness_table.get("status"),
            "visual_bridge_robustness_table_rows": len(visual_bridge_robustness_table.get("rows", [])),
            "visual_bridge_robustness_table_failures": visual_bridge_robustness_table.get("failures", []),
            "expected_rows_checked": agnostic_probe_row_count,
            "rows_checked": agnostic_image_space_parts_verify.get("rows_checked"),
            "row_scopes": [
                {
                    "case_id": row.get("case_id"),
                    "scope": (row.get("image_space_cues") or {}).get("scope"),
                    "grade": (row.get("image_space_cues") or {}).get("grade"),
                    "round_pairs": (row.get("image_space_cues") or {}).get("validated_round_part_pair_count"),
                    "coherent_lines": ((row.get("image_space_cues") or {}).get("line_coherence") or {}).get("coherent"),
                }
                for row in agnostic_image_space_parts_probe.get("rows", [])
            ],
            "label_invariance_rows": [
                {
                    "case_id": row.get("case_id"),
                    "geometry_changed_after_label_mutation": row.get("geometry_changed_after_label_mutation"),
                    "baseline_hash": str(row.get("baseline_hash") or "")[:12],
                    "mutated_hash": str(row.get("mutated_hash") or "")[:12],
                    "status": row.get("status"),
                }
                for row in agnostic_label_invariance.get("rows", [])
            ],
            "identity_invariance_rows": [
                {
                    "original_case_id": row.get("original_case_id"),
                    "mutated_case_id": row.get("mutated_case_id"),
                    "geometry_changed_after_identity_mutation": row.get("geometry_changed_after_identity_mutation"),
                    "baseline_hash": str(row.get("baseline_hash") or "")[:12],
                    "mutated_hash": str(row.get("mutated_hash") or "")[:12],
                    "status": row.get("status"),
                }
                for row in agnostic_identity_invariance.get("rows", [])
            ],
            "path_invariance_rows": [
                {
                    "case_id": row.get("case_id"),
                    "mutated_image": row.get("mutated_image"),
                    "geometry_changed_after_path_mutation": row.get("geometry_changed_after_path_mutation"),
                    "baseline_hash": str(row.get("baseline_hash") or "")[:12],
                    "mutated_hash": str(row.get("mutated_hash") or "")[:12],
                    "status": row.get("status"),
                }
                for row in agnostic_path_invariance.get("rows", [])
            ],
            "detection_representation_invariance_rows": [
                {
                    "case_id": row.get("case_id"),
                    "variants": [
                        {
                            "mutation": variant.get("mutation"),
                            "geometry_changed": variant.get("geometry_changed"),
                            "baseline_hash": str(variant.get("baseline_hash") or "")[:12],
                            "mutated_hash": str(variant.get("mutated_hash") or "")[:12],
                            "status": variant.get("status"),
                        }
                        for variant in row.get("variants", [])
                    ],
                    "status": row.get("status"),
                }
                for row in agnostic_detection_representation_invariance.get("rows", [])
            ],
            "side_channel_invariance_rows": [
                {
                    "original_case_id": row.get("original_case_id"),
                    "mutated_case_id": row.get("mutated_case_id"),
                    "mutated_image": row.get("mutated_image"),
                    "geometry_changed_after_side_channel_mutation": row.get(
                        "geometry_changed_after_side_channel_mutation"
                    ),
                    "baseline_hash": str(row.get("baseline_hash") or "")[:12],
                    "mutated_hash": str(row.get("mutated_hash") or "")[:12],
                    "status": row.get("status"),
                }
                for row in agnostic_side_channel_invariance.get("rows", [])
            ],
            "mirror_equivariance_rows": [
                {
                    "case_id": row.get("case_id"),
                    "status": row.get("status"),
                    "baseline_scope": row.get("baseline_scope"),
                    "mirrored_scope": row.get("mirrored_scope"),
                    "baseline_strong_round_pairs": row.get("baseline_strong_round_pairs"),
                    "mirrored_strong_round_pairs": row.get("mirrored_strong_round_pairs"),
                    "baseline_round_pairs": row.get("baseline_round_pairs"),
                    "mirrored_round_pairs": row.get("mirrored_round_pairs"),
                    "baseline_lines": row.get("baseline_lines"),
                    "mirrored_lines": row.get("mirrored_lines"),
                    "pca_angle_delta_deg": row.get("pca_angle_delta_deg"),
                    "audit_warning_count": len(row.get("audit_warnings") or []),
                }
                for row in agnostic_mirror_equivariance.get("rows", [])
            ],
            "photometric_stability_rows": [
                {
                    "case_id": row.get("case_id"),
                    "variants": [
                        {
                            "variant": variant.get("variant"),
                            "status": variant.get("status"),
                            "baseline_family": variant.get("baseline_family"),
                            "variant_family": variant.get("variant_family"),
                            "baseline_scope": variant.get("baseline_scope"),
                            "variant_scope": variant.get("variant_scope"),
                            "baseline_strong_round_pairs": variant.get("baseline_strong_round_pairs"),
                            "variant_strong_round_pairs": variant.get("variant_strong_round_pairs"),
                            "baseline_lines": variant.get("baseline_lines"),
                            "variant_lines": variant.get("variant_lines"),
                            "audit_warning_count": len(variant.get("audit_warnings") or []),
                        }
                        for variant in row.get("variants", [])
                    ],
                }
                for row in agnostic_photometric_stability.get("rows", [])
            ],
            "synthetic_control_rows": [
                {
                    "case_id": row.get("case_id"),
                    "expected": row.get("expected_summary"),
                    "scope": row.get("scope"),
                    "strong_round_pairs": row.get("strong_round_pairs"),
                    "line_structure": row.get("line_structure"),
                    "status": row.get("status"),
                }
                for row in agnostic_synthetic_part_controls.get("rows", [])
            ],
            "claim_boundary": agnostic_image_space_parts_probe.get("claim_boundary"),
        },
        "truck_figure_decision": {
            "path": str(truck_figure_decision_path),
            "exists": truck_figure_decision_path.exists(),
            "pass": truck_figure_decision.get("pass"),
            "selected_main_figure": truck_figure_decision.get("decision", {}).get("selected_main_figure"),
            "supporting_artifact_figure": truck_figure_decision.get("decision", {}).get("supporting_artifact_figure"),
            "should_fuse_figures": truck_figure_decision.get("decision", {}).get("should_fuse_figures"),
            "recommendation": truck_figure_decision.get("decision", {}).get("recommendation"),
            "claim_boundary": truck_figure_decision.get("decision", {}).get("claim_boundary"),
        },
        "submission_shape": (
            "main paper plus short submission supplement; long technical supplement retained as artifact log"
            if formal_supplement_ready
            else supplement_triage.get("recommendation", {}).get(
                "preferred_shape",
                "main paper plus archived artifacts; do not submit the 38-page supplement as a formal supplement",
            )
        ),
        "main_runtime_contract_submission_ready": len(blockers) == 0,
        "full_experimental_paper_ready": len(blockers) == 0 and all(gate["status"] == "complete" for gate in gates),
        "blockers": blockers,
        "warnings": warnings,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    real_inputs = report["real_input_probes"]
    lines = [
        "# SPPA Submission Precheck",
        "",
        "This report is generated by `tools/sppa_sota_benchmark/verify_sppa_submission_precheck.py`.",
        "",
        "## Verdict",
        "",
        f"- Main PDF pages: {report['main_pdf_pages']}",
        f"- Short submission supplement pages: {report['submission_supplement_pdf_pages']}",
        f"- Short submission supplement ready: {report['submission_supplement_ready']}",
        f"- Supplement PDF pages: {report['supplement_pdf_pages']}",
        f"- Recommended submission shape: {report['submission_shape']}",
        f"- Main runtime-contract submission ready: {report['main_runtime_contract_submission_ready']}",
        f"- Full experimental paper ready: {report['full_experimental_paper_ready']}",
        "",
        "## Supplement Triage",
        "",
        f"- Triage report exists: {report['supplement_triage']['exists']}",
        f"- Current supplement pages: {report['supplement_triage']['pdf_pages']}",
        f"- Current supplement lines: {report['supplement_triage']['line_count']}",
        f"- Formal supplement decision: {report['supplement_triage']['formal_supplement']}",
        f"- Preferred shape: {report['supplement_triage']['preferred_shape']}",
        f"- Section decision counts: {report['supplement_triage']['decision_counts']}",
        f"- Short supplement log: {report['submission_supplement_log']}",
        "",
        "## SPPA Visual Material Audit",
        "",
        f"- Audit exists: {report['sppa_visual_material_audit']['exists']}",
        f"- Audit pass: {report['sppa_visual_material_audit']['pass']}",
        f"- Failures: {report['sppa_visual_material_audit']['failures'] or 'none'}",
        f"- Claim boundary: {report['sppa_visual_material_audit']['claim_boundary']}",
        "",
        "## SPPA Runtime Budget",
        "",
        f"- Budget report exists: {report['sppa_runtime_budget']['exists']}",
        f"- Budget status: {report['sppa_runtime_budget']['status']}",
        f"- Total wall time: {report['sppa_runtime_budget']['summary'].get('total_wall_ms')} ms",
        f"- Max wall time: {report['sppa_runtime_budget']['summary'].get('max_wall_ms')} ms",
        f"- Max triangles: {report['sppa_runtime_budget']['summary'].get('max_triangles')}",
        f"- Max OBJ bytes: {report['sppa_runtime_budget']['summary'].get('max_mesh_bytes')}",
        f"- Max descriptor bytes: {report['sppa_runtime_budget']['summary'].get('max_descriptor_bytes')}",
        f"- Failures: {report['sppa_runtime_budget']['failures'] or 'none'}",
        f"- Claim boundary: {report['sppa_runtime_budget']['claim_boundary']}",
        "",
        "## SPPA Evidence-Channel Coverage",
        "",
        f"- Report exists: {report['sppa_evidence_channel_coverage']['exists']}",
        f"- LaTeX table exists: {report['sppa_evidence_channel_coverage']['tex_exists']}",
        f"- Figure exists: {report['sppa_evidence_channel_coverage']['figure_exists']}",
        f"- Rows: {report['sppa_evidence_channel_coverage']['row_count']}",
        f"- Cases: {report['sppa_evidence_channel_coverage']['case_count']}",
        f"- Visual improvement cases: {report['sppa_evidence_channel_coverage']['visual_improvement_cases']}",
        f"- Budget failures: {report['sppa_evidence_channel_coverage']['budget_failures']}",
        f"- Summary: {report['sppa_evidence_channel_coverage']['summary']}",
        f"- Claim boundary: {report['sppa_evidence_channel_coverage']['claim_boundary']}",
        "",
        "## SPPA Visual Part Evidence",
        "",
        f"- Audit exists: {report['sppa_visual_part_evidence']['exists']}",
        f"- Audit status: {report['sppa_visual_part_evidence']['status']}",
        f"- Rows checked: {report['sppa_visual_part_evidence']['rows_checked']}",
        f"- Grid report exists: {report['sppa_visual_part_evidence']['grid_exists']}",
        f"- Grid rows: {report['sppa_visual_part_evidence']['grid_rows']}",
        f"- Grid figure exists: {report['sppa_visual_part_evidence']['figure_exists']}",
        f"- Failures: {report['sppa_visual_part_evidence']['failures'] or 'none'}",
        f"- Claim boundary: {report['sppa_visual_part_evidence']['claim_boundary']}",
        "",
        "## SPPA Visual-Metric Yaw Consistency",
        "",
        f"- Audit exists: {report['sppa_visual_metric_yaw_consistency']['exists']}",
        f"- Audit status: {report['sppa_visual_metric_yaw_consistency']['status']}",
        f"- Rows checked: {report['sppa_visual_metric_yaw_consistency']['rows_checked']}",
        f"- Aligned: {report['sppa_visual_metric_yaw_consistency']['aligned_count']}",
        f"- Weakly aligned: {report['sppa_visual_metric_yaw_consistency']['weakly_aligned_count']}",
        f"- Divergent but declared: {report['sppa_visual_metric_yaw_consistency']['divergent_declared_count']}",
        f"- Projected-axis aligned: {report['sppa_visual_metric_yaw_consistency']['projected_aligned_count']}",
        f"- Projected-axis weakly aligned: "
        f"{report['sppa_visual_metric_yaw_consistency']['projected_weakly_aligned_count']}",
        f"- Projected-axis divergent but declared: "
        f"{report['sppa_visual_metric_yaw_consistency']['projected_divergent_declared_count']}",
        f"- Descriptor-recorded rows: {report['sppa_visual_metric_yaw_consistency']['descriptor_recorded_count']}",
        f"- Max descriptor bytes: {report['sppa_visual_metric_yaw_consistency']['max_descriptor_bytes']}",
        f"- Failures: {report['sppa_visual_metric_yaw_consistency']['failures'] or 'none'}",
        f"- Audit warnings: {report['sppa_visual_metric_yaw_consistency']['audit_warnings'] or 'none'}",
        f"- Claim boundary: {report['sppa_visual_metric_yaw_consistency']['claim_boundary']}",
        "",
        "## SPPA Descriptor Contract",
        "",
        f"- Audit exists: {report['sppa_descriptor_contract_audit']['exists']}",
        f"- Audit status: {report['sppa_descriptor_contract_audit']['status']}",
        f"- Rows checked: {report['sppa_descriptor_contract_audit']['rows_checked']}",
        f"- Failed rows: {report['sppa_descriptor_contract_audit']['failed_rows']}",
        f"- Visual-metric contract rows: {report['sppa_descriptor_contract_audit']['visual_metric_contract_rows']}",
        f"- Max descriptor bytes: {report['sppa_descriptor_contract_audit']['max_descriptor_bytes']}",
        f"- Failures: {report['sppa_descriptor_contract_audit']['failures'] or 'none'}",
        f"- Claim boundary: {report['sppa_descriptor_contract_audit']['claim_boundary']}",
        "",
        "## SPPA Connector Constraints",
        "",
        f"- Audit exists: {report['sppa_connector_constraints']['exists']}",
        f"- Audit status: {report['sppa_connector_constraints']['status']}",
        f"- LaTeX table exists: {report['sppa_connector_constraints']['tex_exists']}",
        f"- Rows checked: {report['sppa_connector_constraints']['rows_checked']}",
        f"- Failed rows: {report['sppa_connector_constraints']['failed']}",
        f"- Claim boundary: {report['sppa_connector_constraints']['claim_boundary']}",
        "",
        "| Case | Connectors | Roles | Length range | Status |",
        "|---|---:|---|---:|---|",
        *[
            f"| {row['case_id']} | {row.get('connector_count', 0)} | "
            f"{', '.join(row.get('connector_roles', []))} | "
            f"{row.get('connector_length_min', 0.0)}-{row.get('connector_length_max', 0.0)} m | "
            f"{row.get('status')} |"
            for row in report["sppa_connector_constraints"]["rows"]
        ],
        "",
        "## Agnostic Image-Space Parts Probe",
        "",
        f"- Probe exists: {report['agnostic_image_space_parts']['exists']}",
        f"- Figure exists: {report['agnostic_image_space_parts']['figure_exists']}",
        f"- Verification exists: {report['agnostic_image_space_parts']['verify_exists']}",
        f"- Verification status: {report['agnostic_image_space_parts']['verify_status']}",
        f"- Expected real rows checked by invariance verifiers: "
        f"{report['agnostic_image_space_parts']['expected_rows_checked']}",
        f"- Rows checked: {report['agnostic_image_space_parts']['rows_checked']}",
        f"- Label-invariance exists: {report['agnostic_image_space_parts']['label_invariance_exists']}",
        f"- Label-invariance status: {report['agnostic_image_space_parts']['label_invariance_status']}",
        f"- Label-invariance rows checked: {report['agnostic_image_space_parts']['label_invariance_rows_checked']}",
        f"- Identity-invariance exists: {report['agnostic_image_space_parts']['identity_invariance_exists']}",
        f"- Identity-invariance status: {report['agnostic_image_space_parts']['identity_invariance_status']}",
        f"- Identity-invariance rows checked: {report['agnostic_image_space_parts']['identity_invariance_rows_checked']}",
        f"- Path-invariance exists: {report['agnostic_image_space_parts']['path_invariance_exists']}",
        f"- Path-invariance status: {report['agnostic_image_space_parts']['path_invariance_status']}",
        f"- Path-invariance rows checked: {report['agnostic_image_space_parts']['path_invariance_rows_checked']}",
        f"- Detection-representation invariance exists: "
        f"{report['agnostic_image_space_parts']['detection_representation_invariance_exists']}",
        f"- Detection-representation invariance status: "
        f"{report['agnostic_image_space_parts']['detection_representation_invariance_status']}",
        f"- Detection-representation invariance rows checked: "
        f"{report['agnostic_image_space_parts']['detection_representation_invariance_rows_checked']}",
        f"- Detection-representation invariance variants checked: "
        f"{report['agnostic_image_space_parts']['detection_representation_invariance_variants_checked']}",
        f"- Combined side-channel invariance exists: {report['agnostic_image_space_parts']['side_channel_invariance_exists']}",
        f"- Combined side-channel invariance status: {report['agnostic_image_space_parts']['side_channel_invariance_status']}",
        f"- Combined side-channel invariance rows checked: "
        f"{report['agnostic_image_space_parts']['side_channel_invariance_rows_checked']}",
        f"- Mirror-equivariance exists: {report['agnostic_image_space_parts']['mirror_equivariance_exists']}",
        f"- Mirror-equivariance primary status: {report['agnostic_image_space_parts']['mirror_equivariance_status']}",
        f"- Mirror-equivariance rows checked: {report['agnostic_image_space_parts']['mirror_equivariance_rows_checked']}",
        f"- Mirror-equivariance audit warnings: "
        f"{report['agnostic_image_space_parts']['mirror_equivariance_audit_warning_count']}",
        f"- Mirror-equivariance diagnostic notes: "
        f"{report['agnostic_image_space_parts']['mirror_equivariance_diagnostic_note_count']}",
        f"- Photometric stability exists: {report['agnostic_image_space_parts']['photometric_stability_exists']}",
        f"- Photometric stability status: {report['agnostic_image_space_parts']['photometric_stability_status']}",
        f"- Photometric stability rows checked: "
        f"{report['agnostic_image_space_parts']['photometric_stability_rows_checked']}",
        f"- Photometric stability variants checked: "
        f"{report['agnostic_image_space_parts']['photometric_stability_variants_checked']}",
        f"- Photometric stability audit warnings: "
        f"{report['agnostic_image_space_parts']['photometric_stability_audit_warning_count']}",
        f"- Photometric stability diagnostic notes: "
        f"{report['agnostic_image_space_parts']['photometric_stability_diagnostic_note_count']}",
        f"- Synthetic controls exist: {report['agnostic_image_space_parts']['synthetic_controls_exists']}",
        f"- Synthetic controls status: {report['agnostic_image_space_parts']['synthetic_controls_status']}",
        f"- Synthetic controls count: {report['agnostic_image_space_parts']['synthetic_controls_count']}",
        f"- Synthetic controls figure exists: {report['agnostic_image_space_parts']['synthetic_controls_figure_exists']}",
        f"- Synthetic sweep exists: {report['agnostic_image_space_parts']['synthetic_sweep_exists']}",
        f"- Synthetic sweep status: {report['agnostic_image_space_parts']['synthetic_sweep_status']}",
        f"- Synthetic sweep cases: {report['agnostic_image_space_parts']['synthetic_sweep_summary'].get('case_count')}",
        f"- Synthetic sweep primary accuracy: {report['agnostic_image_space_parts']['synthetic_sweep_summary'].get('primary_scope_accuracy')}",
        f"- Synthetic sweep round-pair P/R/F1: "
        f"{(report['agnostic_image_space_parts']['synthetic_sweep_summary'].get('round_pair') or {}).get('precision')} / "
        f"{(report['agnostic_image_space_parts']['synthetic_sweep_summary'].get('round_pair') or {}).get('recall')} / "
        f"{(report['agnostic_image_space_parts']['synthetic_sweep_summary'].get('round_pair') or {}).get('f1')}",
        f"- Synthetic sweep line-structure P/R/F1: "
        f"{(report['agnostic_image_space_parts']['synthetic_sweep_summary'].get('line_structure') or {}).get('precision')} / "
        f"{(report['agnostic_image_space_parts']['synthetic_sweep_summary'].get('line_structure') or {}).get('recall')} / "
        f"{(report['agnostic_image_space_parts']['synthetic_sweep_summary'].get('line_structure') or {}).get('f1')}",
        f"- Synthetic sweep figure exists: {report['agnostic_image_space_parts']['synthetic_sweep_figure_exists']}",
        f"- Synthetic fuzz exists: {report['agnostic_image_space_parts']['synthetic_fuzz_exists']}",
        f"- Synthetic fuzz status: {report['agnostic_image_space_parts']['synthetic_fuzz_status']}",
        f"- Synthetic fuzz seeds: {', '.join(str(seed) for seed in report['agnostic_image_space_parts']['synthetic_fuzz_seeds']) or 'none'}",
        f"- Synthetic fuzz cases: {report['agnostic_image_space_parts']['synthetic_fuzz_summary'].get('case_count')}",
        f"- Synthetic fuzz primary accuracy: {report['agnostic_image_space_parts']['synthetic_fuzz_summary'].get('primary_scope_accuracy')}",
        f"- Synthetic fuzz round-pair P/R/F1: "
        f"{(report['agnostic_image_space_parts']['synthetic_fuzz_summary'].get('round_pair') or {}).get('precision')} / "
        f"{(report['agnostic_image_space_parts']['synthetic_fuzz_summary'].get('round_pair') or {}).get('recall')} / "
        f"{(report['agnostic_image_space_parts']['synthetic_fuzz_summary'].get('round_pair') or {}).get('f1')}",
        f"- Synthetic fuzz line-structure P/R/F1: "
        f"{(report['agnostic_image_space_parts']['synthetic_fuzz_summary'].get('line_structure') or {}).get('precision')} / "
        f"{(report['agnostic_image_space_parts']['synthetic_fuzz_summary'].get('line_structure') or {}).get('recall')} / "
        f"{(report['agnostic_image_space_parts']['synthetic_fuzz_summary'].get('line_structure') or {}).get('f1')}",
        f"- Synthetic fuzz figure exists: {report['agnostic_image_space_parts']['synthetic_fuzz_figure_exists']}",
        f"- Robustness table exists: {report['agnostic_image_space_parts']['visual_bridge_robustness_table_exists']}",
        f"- Robustness table status: {report['agnostic_image_space_parts']['visual_bridge_robustness_table_status']}",
        f"- Robustness LaTeX table exists: {report['agnostic_image_space_parts']['visual_bridge_robustness_table_tex_exists']}",
        f"- Robustness table rows: {report['agnostic_image_space_parts']['visual_bridge_robustness_table_rows']}",
        f"- Robustness table failures: {report['agnostic_image_space_parts']['visual_bridge_robustness_table_failures'] or 'none'}",
        f"- Claim boundary: {report['agnostic_image_space_parts']['claim_boundary']}",
        "",
        "| Case | Scope | Grade | Round pairs | Coherent lines |",
        "|---|---|---|---:|---:|",
        *[
            f"| {row['case_id']} | {row['scope']} | {row['grade']} | "
            f"{row['round_pairs']} | {str(row['coherent_lines']).lower()} |"
            for row in report["agnostic_image_space_parts"]["row_scopes"]
        ],
        "",
        "| Case | Geometry changed after label mutation | Baseline hash | Mutated hash | Status |",
        "|---|---:|---|---|---|",
        *[
            f"| {row['case_id']} | {str(row['geometry_changed_after_label_mutation']).lower()} | "
            f"`{row['baseline_hash']}` | `{row['mutated_hash']}` | {row['status']} |"
            for row in report["agnostic_image_space_parts"]["label_invariance_rows"]
        ],
        "",
        "| Original case | Mutated case | Geometry changed after identity mutation | Baseline hash | Mutated hash | Status |",
        "|---|---|---:|---|---|---|",
        *[
            f"| {row['original_case_id']} | {row['mutated_case_id']} | "
            f"{str(row['geometry_changed_after_identity_mutation']).lower()} | "
            f"`{row['baseline_hash']}` | `{row['mutated_hash']}` | {row['status']} |"
            for row in report["agnostic_image_space_parts"]["identity_invariance_rows"]
        ],
        "",
        "| Case | Mutated image | Geometry changed after path mutation | Baseline hash | Mutated hash | Status |",
        "|---|---|---:|---|---|---|",
        *[
            f"| {row['case_id']} | `{row['mutated_image']}` | "
            f"{str(row['geometry_changed_after_path_mutation']).lower()} | "
            f"`{row['baseline_hash']}` | `{row['mutated_hash']}` | {row['status']} |"
            for row in report["agnostic_image_space_parts"]["path_invariance_rows"]
        ],
        "",
        "| Case | Detection representation mutation | Geometry changed | Baseline hash | Mutated hash | Status |",
        "|---|---|---:|---|---|---|",
        *[
            f"| {row['case_id']} | {variant['mutation']} | {str(variant['geometry_changed']).lower()} | "
            f"`{variant['baseline_hash']}` | `{variant['mutated_hash']}` | {variant['status']} |"
            for row in report["agnostic_image_space_parts"]["detection_representation_invariance_rows"]
            for variant in row["variants"]
        ],
        "",
        "| Original case | Mutated case | Mutated image | Geometry changed after combined side-channel mutation | Baseline hash | Mutated hash | Status |",
        "|---|---|---|---:|---|---|---|",
        *[
            f"| {row['original_case_id']} | {row['mutated_case_id']} | `{row['mutated_image']}` | "
            f"{str(row['geometry_changed_after_side_channel_mutation']).lower()} | "
            f"`{row['baseline_hash']}` | `{row['mutated_hash']}` | {row['status']} |"
            for row in report["agnostic_image_space_parts"]["side_channel_invariance_rows"]
        ],
        "",
        "| Case | Mirror status | Scope -> mirror | Strong pairs -> mirror | All pairs -> mirror | Lines -> mirror | PCA mirror delta deg | Audit warnings |",
        "|---|---|---|---:|---:|---:|---:|---:|",
        *[
            f"| {row['case_id']} | {row['status']} | {row['baseline_scope']} -> {row['mirrored_scope']} | "
            f"{row['baseline_strong_round_pairs']} -> {row['mirrored_strong_round_pairs']} | "
            f"{row['baseline_round_pairs']} -> {row['mirrored_round_pairs']} | "
            f"{row['baseline_lines']} -> {row['mirrored_lines']} | {row['pca_angle_delta_deg']} | "
            f"{row['audit_warning_count']} |"
            for row in report["agnostic_image_space_parts"]["mirror_equivariance_rows"]
        ],
        "",
        "| Case | Photometric variant | Status | Family -> variant | Scope -> variant | Strong pairs -> variant | Lines -> variant | Audit warnings |",
        "|---|---|---|---|---|---:|---:|---:|",
        *[
            f"| {row['case_id']} | {variant['variant']} | {variant['status']} | "
            f"{variant['baseline_family']} -> {variant['variant_family']} | "
            f"{variant['baseline_scope']} -> {variant['variant_scope']} | "
            f"{variant['baseline_strong_round_pairs']} -> {variant['variant_strong_round_pairs']} | "
            f"{variant['baseline_lines']} -> {variant['variant_lines']} | {variant['audit_warning_count']} |"
            for row in report["agnostic_image_space_parts"]["photometric_stability_rows"]
            for variant in row["variants"]
        ],
        "",
        "| Synthetic control | Expected | Scope | Strong round pairs | Line structure | Status |",
        "|---|---|---|---:|---:|---|",
        *[
            f"| {row['case_id']} | {row['expected']} | {row['scope']} | "
            f"{row['strong_round_pairs']} | {str(row['line_structure']).lower()} | {row['status']} |"
            for row in report["agnostic_image_space_parts"]["synthetic_control_rows"]
        ],
        "",
        "## Truck Figure Decision",
        "",
        f"- Decision audit exists: {report['truck_figure_decision']['exists']}",
        f"- Decision audit pass: {report['truck_figure_decision']['pass']}",
        f"- Selected main figure: {report['truck_figure_decision']['selected_main_figure']}",
        f"- Supporting artifact figure: {report['truck_figure_decision']['supporting_artifact_figure']}",
        f"- Fuse figures: {report['truck_figure_decision']['should_fuse_figures']}",
        f"- Recommendation: {report['truck_figure_decision']['recommendation']}",
        f"- Claim boundary: {report['truck_figure_decision']['claim_boundary']}",
        "",
        "## Input Provenance",
        "",
        f"- Items: {report['input_provenance']['items']}",
        f"- Ground-truth items: {report['input_provenance']['ground_truth_items']}",
        f"- Detector crops: {report['input_provenance']['detector_crop_items']}",
        f"- Synthetic proxy crops: {report['input_provenance']['synthetic_proxy_items']}",
        f"- Candidate real inputs: {report['input_provenance'].get('candidate_real_inputs', 0)}",
        f"- Candidate real input labels: {', '.join(report['input_provenance'].get('candidate_real_input_labels', [])) or 'none'}",
        f"- First row can be called ground truth: {report['input_provenance']['can_label_first_row_as_ground_truth']}",
        f"- First-row GT decision exists: {report['files']['first_row_gt_decision']}",
        "",
        "## Detection Reference Artifact",
        "",
        f"- Exists: {report['detection_reference']['exists']}",
        f"- Items: {report['detection_reference']['items']}",
        f"- Synthetic/annotated GT bbox items: {report['detection_reference']['ground_truth_items']}",
        f"- Readable image/crop items: {report['detection_reference']['readable_image_items']}",
        f"- Labels: {', '.join(report['detection_reference']['labels']) if report['detection_reference']['labels'] else 'none'}",
        "",
        "## Real Input 2D Annotations",
        "",
        f"- Exists: {report['real_input_2d_annotations']['exists']}",
        f"- Items: {report['real_input_2d_annotations']['items']}",
        f"- 2D bbox GT items: {report['real_input_2d_annotations']['bbox_gt_2d_items']}",
        f"- 3D GT items: {report['real_input_2d_annotations']['gt_3d_items']}",
        f"- Masks: {report['real_input_2d_annotations']['mask_items']}",
        f"- Reference meshes: {report['real_input_2d_annotations']['reference_mesh_items']}",
        f"- Labels: {', '.join(report['real_input_2d_annotations']['labels']) if report['real_input_2d_annotations']['labels'] else 'none'}",
        f"- Can support 3D SOTA GT: {report['real_input_2d_annotations']['can_support_3d_sota_gt']}",
        f"- Claim boundary: {report['real_input_2d_annotations']['claim_boundary']}",
        "",
        "## Real-Image Assumed-Flight Replay",
        "",
        f"- Exists: {report['real_image_assumed_flight_replay']['exists']}",
        f"- Cases passed/total: {report['real_image_assumed_flight_replay']['passed_count']} / {report['real_image_assumed_flight_replay']['case_count']}",
        f"- Images real: {report['real_image_assumed_flight_replay']['image_is_real']}",
        f"- Detector evidence real: {report['real_image_assumed_flight_replay']['detector_is_real']}",
        f"- Telemetry measured: {report['real_image_assumed_flight_replay']['telemetry_is_measured']}",
        f"- Metric ground truth: {report['real_image_assumed_flight_replay']['metric_ground_truth']}",
        f"- Claim posture: {report['real_image_assumed_flight_replay']['claim_posture']}",
        f"- Claim boundary: {report['real_image_assumed_flight_replay']['claim_boundary']}",
        "",
        "## Real YOLOE Dual-Input Benchmark",
        "",
        f"- Exists: {report['real_yoloe_dual_input_benchmark']['exists']}",
        f"- Cases: {report['real_yoloe_dual_input_benchmark']['case_count']}",
        f"- Detector-ready cases: {report['real_yoloe_dual_input_benchmark']['detector_ready_count']}",
        f"- Image-baseline-ready cases: {report['real_yoloe_dual_input_benchmark']['image_baseline_ready_count']}",
        f"- Tag/text-ready cases: {report['real_yoloe_dual_input_benchmark']['tag_text_ready_count']}",
        f"- Metric replay-ready cases: {report['real_yoloe_dual_input_benchmark']['metric_replay_ready_count']}",
        f"- Bounded dual-input claim ready: {report['real_yoloe_dual_input_benchmark']['bounded_dual_input_claim_ready']}",
        f"- Full visual image-to-3D leaderboard ready: {report['real_yoloe_dual_input_benchmark']['full_visual_image_to_3d_leaderboard_ready']}",
        f"- Claim posture: {report['real_yoloe_dual_input_benchmark']['claim_posture']}",
        f"- Claim boundary: {report['real_yoloe_dual_input_benchmark']['claim_boundary']}",
        "",
        "## Real Input Probes",
        "",
        f"- Exists: {real_inputs['exists']}",
        f"- Count: {real_inputs['count']}",
        f"- Labels: {', '.join(real_inputs['labels']) if real_inputs['labels'] else 'none'}",
        f"- Readable input images: {real_inputs['readable_input_images']}",
        f"- Image-to-3D 512 crops: {real_inputs['image_to_3d_crop_512_count']}",
        f"- Runs ready: {real_inputs['runs_ready']}",
        f"- Real input probe figure exists: {real_inputs['real_input_probe_figure']}",
        f"- Real input output quality audit exists: {report['files']['real_input_output_quality_audit']}",
        f"- Ground truth: {real_inputs['is_ground_truth']}",
        "",
        "## Four Priority Gates",
        "",
    ]
    for probe in real_inputs["probes"]:
        methods = ", ".join(
            (
                f"{method['model']}={method['status']} "
                f"{method['wall_ms']}ms {method['triangles']} tris {method['vram_mb']}MB"
            )
            for method in probe["methods"]
        ) or "none"
        lines[-3:-3] = [
            f"### Probe: `{probe['label']}`",
            "",
            f"- Raw input exists: {probe['readable_input_image']}",
            f"- Image-to-3D crop 512 exists: {probe['image_to_3d_crop_512_exists']}",
            f"- Repo YOLO detections / valid target hits: {probe['repo_yolo_detections']} / {probe['repo_yolo_valid_target_hits']}",
            f"- Repo YOLO tag: {format_tag(probe['repo_yolo_tag'])}",
            f"- Repo YOLO low-conf detections / valid target hits: {probe['repo_yolo_lowconf_detections']} / {probe['repo_yolo_lowconf_valid_target_hits']}",
            f"- Repo YOLO low-conf tag: {format_tag(probe['repo_yolo_lowconf_tag'])}",
            f"- COCO YOLO detections / valid target hits: {probe['coco_yolo_detections']} / {probe['coco_yolo_valid_target_hits']}",
            f"- COCO YOLO tag: {format_tag(probe['coco_yolo_tag'])}",
            f"- Run exists / objects.csv / summary: {probe['run_exists']} / {probe['objects_csv_exists']} / {probe['summary_exists']}",
            f"- Method summary: {methods}",
            f"- Ground truth / mask / reference mesh: {probe['is_ground_truth']} / {probe['has_mask']} / {probe['has_reference_mesh']}",
            "",
        ]
    readiness = report["sota_ranking_readiness"]
    lines[-3:-3] = [
        "## Claim Posture Readiness",
        "",
        f"- Claim posture: `{readiness['claim_posture']}`",
        f"- Supported publication claim: {readiness['supported_publication_claim']}",
        f"- Full visual image-to-3D leaderboard ready: {readiness['full_visual_image_to_3d_leaderboard_ready']}",
        f"- Recommended comparative figure role: {readiness['recommended_comparative_figure_role']}",
        f"- First row should be called ground truth: {readiness['should_use_first_row_as_ground_truth']}",
        f"- Requirement counts: complete={readiness['status_counts']['complete']}, partial={readiness['status_counts']['partial']}, missing={readiness['status_counts']['missing']}",
        f"- Protocol manifest exists: {report['files']['sota_protocol_manifest']}",
        f"- Protocol readiness report exists: {report['sota_protocol_readiness_report']['exists']}",
        f"- Protocol claim posture: `{report['sota_protocol_readiness_report']['claim_posture']}`",
        f"- Protocol full visual leaderboard ready: {report['sota_protocol_readiness_report']['full_visual_image_to_3d_leaderboard_ready']}",
        f"- Protocol runtime task-fit ready: {report['sota_protocol_readiness_report']['runtime_semantic_proxy_task_fit_ready']}",
        f"- Protocol readiness counts: {report['sota_protocol_readiness_report']['status_counts']}",
        f"- Dual-input readiness report exists: {report['dual_input_sota_readiness_report']['exists']}",
        f"- Dual-input claim posture: `{report['dual_input_sota_readiness_report']['claim_posture']}`",
        f"- Bounded dual-input claim ready: {report['dual_input_sota_readiness_report']['bounded_dual_input_claim_ready']}",
        f"- Dual-input leaderboard ready: {report['dual_input_sota_readiness_report']['full_dual_input_leaderboard_ready']}",
        f"- Dual-input readiness counts: {report['dual_input_sota_readiness_report']['status_counts']}",
        f"- Method exclusions exist: {report['files']['sota_method_exclusions']}",
        f"- Preference protocol exists: {report['files']['sota_preference_protocol']}",
        f"- Image alignment metrics exist: {report['files']['sota_image_alignment_metrics']}",
        f"- Phase-aligned Unreal profile exists: {report['files']['phase_aligned_unreal_profile_csv'] and report['files']['phase_aligned_unreal_profile_md']}",
        f"- Scheduler active-track replay exists: {report['files']['scheduler_active_track_replay_csv'] and report['files']['scheduler_active_track_replay_md']}",
        "",
    ]
    for row in readiness["requirements"]:
        lines[-3:-3] = [
            f"### Claim requirement: `{row['key']}`",
            "",
            f"- Status: {row['status']}",
            f"- Evidence: {row['evidence']}",
            f"- Missing: {row['missing']}",
            "",
        ]
    for gate in report["four_priority_gates"]:
        lines.append(f"- `{gate['gate']}`: {gate['status']} - {gate['evidence']}")
    lines += ["", "## Blockers", ""]
    lines.extend([f"- {item}" for item in report["blockers"]] or ["- None"])
    lines += ["", "## Warnings", ""]
    lines.extend([f"- {item}" for item in report["warnings"]] or ["- None"])
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify SPPA paper claim boundaries before submission.")
    parser.add_argument("--json-out", type=Path, default=PAPER_DIR / "SUBMISSION_PRECHECK.json")
    parser.add_argument("--md-out", type=Path, default=PAPER_DIR / "SUBMISSION_PRECHECK.md")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when any blocker remains.")
    args = parser.parse_args()

    report = build_report()
    args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(args.md_out, report)
    print(json.dumps({"json": str(args.json_out), "markdown": str(args.md_out), "blockers": len(report["blockers"])}, indent=2))
    if args.strict and report["blockers"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
