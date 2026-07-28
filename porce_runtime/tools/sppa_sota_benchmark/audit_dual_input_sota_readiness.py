"""Audit the dual-input SPPA publication claim posture.

The intended ranking has two tracks:

1. YOLO-detected image input: a real detector crop with target class, confidence,
   bbox provenance, and the same image crop sent to image-to-3D methods.
2. Tag/text input: a semantic tag or prompt with no image, used by SPPA and
   text-conditioned baselines.

Manual ROIs are useful provenance, but they do not count as YOLO-detected image
inputs.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PAPER_RESULTS = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"
DEFAULT_JSON_OUT = PAPER_RESULTS / "sota_dual_input_readiness.json"
DEFAULT_MD_OUT = PAPER_RESULTS / "sota_dual_input_readiness.md"
ANNOTATIONS = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_detection_reference" / "20260703_real_input_annotations" / "real_input_2d_annotations.json"
REAL_YOLOE_DUAL_INPUT = PAPER_RESULTS / "real_yoloe_dual_input_benchmark.json"
METHOD_EXCLUSIONS = PAPER_RESULTS / "sota_method_exclusions.json"
IMAGE_ALIGNMENT_METRICS = PAPER_RESULTS / "sota_image_alignment_metrics.csv"
PREFERENCE_PROTOCOL = PAPER_RESULTS / "sota_preference_protocol.md"

TARGET_ALIASES = {
    "biker": {"biker", "bike", "bicycle", "cyclist"},
    "tower": {"tower", "pylon", "transmission tower", "power tower", "electric tower", "utility pole"},
    "tractor": {"tractor", "truck", "car", "vehicle"},
    "tractor_trailer": {"tractor", "truck", "car", "vehicle"},
}

RUNS = {
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

REQUIRED_IMAGE_METHODS = {
    "direct3d_s2",
    "triposr_warm",
    "hunyuan3d_2mini_turbo_shape",
    "hunyuan3d_2_1",
    "partcrafter",
    "pixal3d",
    "rodin_gen_2_5",
    "stable_fast_3d",
    "spar3d",
    "trellis2_4b",
    "tripo_sg_or_tripo_p1",
}
REQUIRED_TAG_METHODS = {
    "sppa",
    "shap_e_text_k16",
    "point_e_text_sdf32",
}


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def target_hits(probe: dict[str, Any], label: str) -> list[dict[str, Any]]:
    aliases = TARGET_ALIASES.get(label, {label})
    hits = []
    for det in probe.get("detections", []):
        class_name = str(det.get("class_name", "")).lower()
        if det.get("overlaps_manual_roi") is True and class_name in aliases:
            hits.append(det)
    return hits


def rows_for_run(run_dir: Path) -> list[dict[str, str]]:
    path = run_dir / "objects.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [row for row in csv.DictReader(f) if row.get("event") == "SPPA_BENCH_OBJECT" and row.get("status") == "ok"]


def case_status(item: dict[str, Any]) -> dict[str, Any]:
    label = str(item.get("label"))
    repo_probe_path = ROOT / str(item.get("probe_json", ""))
    repo_probe = load_json(repo_probe_path)
    coco_probe_path = repo_probe_path.parent / "coco_yolo11n" / repo_probe_path.name
    coco_probe = load_json(coco_probe_path)
    repo_hits = target_hits(repo_probe, label)
    coco_hits = target_hits(coco_probe, label)
    run_dir = RUNS.get(label)
    rows = rows_for_run(run_dir) if run_dir else []
    methods = sorted({row.get("model", "") for row in rows if row.get("model")})
    return {
        "label": label,
        "reviewed_tag": item.get("reviewed_semantic_tag"),
        "manual_bbox": item.get("manual_bbox_xyxy"),
        "repo_probe": rel(repo_probe_path),
        "coco_probe": rel(coco_probe_path),
        "repo_target_hits": len(repo_hits),
        "coco_target_hits": len(coco_hits),
        "has_yolo_detected_target_input": bool(repo_hits or coco_hits),
        "manual_roi_fallback": item.get("crop_source") == "manual_roi_fallback",
        "run_dir": rel(run_dir) if run_dir else None,
        "methods": methods,
        "image_methods_present": sorted(set(methods) & REQUIRED_IMAGE_METHODS),
        "tag_methods_present": sorted(set(methods) & REQUIRED_TAG_METHODS),
        "missing_image_methods": sorted(REQUIRED_IMAGE_METHODS - set(methods)),
        "missing_tag_methods": sorted(REQUIRED_TAG_METHODS - set(methods)),
    }


def build_report() -> dict[str, Any]:
    real_yoloe = load_json(REAL_YOLOE_DUAL_INPUT)
    if real_yoloe.get("bounded_dual_input_claim_ready") is True:
        cases = []
        for item in real_yoloe.get("cases", []):
            cases.append(
                {
                    "label": item.get("label"),
                    "raw_image": item.get("raw_image"),
                    "detector_label": item.get("selected_detector_label"),
                    "detector_confidence": item.get("selected_confidence"),
                    "detector_crop_512": item.get("detector_crop_512"),
                    "sppa_tag": item.get("selected_sppa_tag"),
                    "runtime_archetype": item.get("selected_runtime_archetype"),
                    "has_yolo_detected_target_input": item.get("image_input_track", {}).get(
                        "target_detection_available"
                    )
                    is True,
                    "image_methods_present": item.get("image_input_track", {}).get("methods_present", []),
                    "tag_methods_present": item.get("tag_text_input_track", {}).get("methods_present", []),
                    "missing_image_methods": item.get("image_input_track", {}).get("missing_required_methods", []),
                    "missing_tag_methods": item.get("tag_text_input_track", {}).get("missing_required_methods", []),
                    "not_ranked_modern_methods": item.get("image_input_track", {}).get(
                        "not_ranked_modern_methods", []
                    ),
                    "claim_boundary": item.get("claim_boundary"),
                }
            )

        requirements = [
            {
                "key": "yolo_detected_image_input_track",
                "status": "complete",
                "evidence": (
                    f"{real_yoloe.get('detector_ready_count')}/{real_yoloe.get('case_count')} real cases have "
                    "frozen YOLOE detector labels, confidence, bboxes, and detector crops."
                ),
                "missing": "None for the bounded SPPA systems claim.",
            },
            {
                "key": "image_to_3d_baseline_outputs",
                "status": "complete",
                "evidence": (
                    f"{real_yoloe.get('image_baseline_ready_count')}/{real_yoloe.get('case_count')} cases include "
                    "local TripoSR and Hunyuan3D-2mini image-track outputs."
                ),
                "missing": "Full visual leaderboard methods are documented separately as exclusions, not ranked rows.",
            },
            {
                "key": "contemporary_image_method_set",
                "status": "partial",
                "evidence": (
                    "Venue-complete contemporary visual methods are not all reproduced; exclusions are documented."
                    if METHOD_EXCLUSIONS.exists()
                    else "Venue-complete contemporary visual methods are not all reproduced."
                ),
                "missing": (
                    "Run or externally validate TRELLIS.2, Pixal3D, Hunyuan3D 2.1, Stable Fast 3D, SPAR3D, "
                    "TripoSG/Tripo P1, Direct3D-S2, PartCrafter, and Rodin Gen-2.5 before "
                    "claiming a full visual image-to-3D leaderboard."
                ),
            },
            {
                "key": "tag_text_input_track",
                "status": "complete",
                "evidence": (
                    f"{real_yoloe.get('tag_text_ready_count')}/{real_yoloe.get('case_count')} cases include "
                    "SPPA, Shap-E, and Point-E tag/text outputs on reviewed prompts."
                ),
                "missing": "None for the bounded tag/text track.",
            },
            {
                "key": "quality_metrics",
                "status": "partial",
                "evidence": (
                    "Detector alignment metrics and a human/task preference protocol exist, but no 3D reference "
                    "geometry exists for visual quality scoring."
                    if IMAGE_ALIGNMENT_METRICS.exists() and PREFERENCE_PROTOCOL.exists()
                    else "No complete visual quality metric package exists."
                ),
                "missing": "3D reference meshes, masks, or completed human scores for a full visual leaderboard.",
            },
        ]
        status_counts = {
            status: sum(1 for row in requirements if row["status"] == status)
            for status in ["complete", "partial", "missing"]
        }
        return {
            "schema": "SPPA-DUAL-INPUT-SOTA-READINESS-0.2",
            "annotations": rel(ANNOTATIONS),
            "real_yoloe_dual_input_benchmark": rel(REAL_YOLOE_DUAL_INPUT),
            "cases": cases,
            "requirements": requirements,
            "status_counts": status_counts,
            "claim_posture": "bounded_dual_input_systems_benchmark_ready_not_visual_leaderboard",
            "bounded_dual_input_claim_ready": True,
            "full_dual_input_leaderboard_ready": False,
            "supported_now": real_yoloe.get("supported_claim"),
            "ambitious_next_claim": (
                "Upgrade the same frozen dual-input protocol with 3D references, masks, completed human/task "
                "preference scores, and the full contemporary image-to-3D method set."
            ),
            "claim_boundary": real_yoloe.get("claim_boundary"),
        }

    annotations = load_json(ANNOTATIONS)
    items = list(annotations.get("items", []))
    cases = [case_status(item) for item in items]
    yolo_detected = [case for case in cases if case["has_yolo_detected_target_input"]]
    tag_ready = [case for case in cases if case["reviewed_tag"] and case["run_dir"] and case["tag_methods_present"]]
    all_have_image_baselines = bool(cases) and all(
        {"triposr_warm", "hunyuan3d_2mini_turbo_shape"}.issubset(set(case["methods"])) for case in cases
    )
    all_have_required_modern = bool(cases) and all(not case["missing_image_methods"] for case in cases)
    all_have_tag_methods = bool(cases) and all(not case["missing_tag_methods"] for case in cases)
    requirements = [
        {
            "key": "yolo_detected_image_input_track",
            "status": "complete" if yolo_detected else "missing",
            "evidence": f"{len(yolo_detected)}/{len(cases)} real cases have a target-compatible YOLO detection in the reviewed ROI.",
            "missing": "Provide at least one frozen real or simulated YOLO target crop per ranked class; manual ROI fallback does not count.",
        },
        {
            "key": "image_to_3d_baseline_outputs",
            "status": "partial" if all_have_image_baselines else "missing",
            "evidence": "TripoSR and Hunyuan3D-2mini outputs exist for the current real probes."
            if all_have_image_baselines
            else "One or more current probes lacks the reproduced image-to-3D baseline outputs.",
            "missing": "Run all image methods on the same YOLO-detected crops, then add TRELLIS.2, Pixal3D, Hunyuan3D-2.1, SF3D, SPAR3D, TripoSG/Tripo P1, Direct3D-S2, PartCrafter, and Rodin Gen-2.5 or documented exclusions.",
        },
        {
            "key": "contemporary_image_method_set",
            "status": "complete" if all_have_required_modern else "missing",
            "evidence": "Only local TripoSR and Hunyuan3D-2mini are reproduced on all four real probes.",
            "missing": "Missing contemporary required methods: TRELLIS.2, Pixal3D, Hunyuan3D-2.1, Stable Fast 3D, SPAR3D, TripoSG/Tripo P1, Direct3D-S2, PartCrafter, and Rodin Gen-2.5.",
        },
        {
            "key": "tag_text_input_track",
            "status": "complete" if all_have_tag_methods else "partial",
            "evidence": f"{len(tag_ready)}/{len(cases)} cases have reviewed tags and at least one tag-driven method output.",
            "missing": "Run Shap-E and Point-E text baselines on the same reviewed tags/prompts if they remain in the tag/text ranking.",
        },
        {
            "key": "quality_metrics",
            "status": "missing",
            "evidence": "No reference geometry, mask reprojection, image alignment, or human preference metric artifact is registered for these real probes.",
            "missing": "Add GT/reference metrics or a structured human preference/task-readability protocol before ranking visual quality.",
        },
    ]
    status_counts = {
        status: sum(1 for row in requirements if row["status"] == status)
        for status in ["complete", "partial", "missing"]
    }
    full_dual_input_leaderboard_ready = status_counts["partial"] == 0 and status_counts["missing"] == 0
    claim_posture = (
        "dual_input_benchmark_ready"
        if full_dual_input_leaderboard_ready
        else "ambitious_dual_input_protocol_not_leaderboard"
    )
    return {
        "schema": "SPPA-DUAL-INPUT-SOTA-READINESS-0.1",
        "annotations": rel(ANNOTATIONS),
        "cases": cases,
        "requirements": requirements,
        "status_counts": status_counts,
        "claim_posture": claim_posture,
        "bounded_dual_input_claim_ready": False,
        "full_dual_input_leaderboard_ready": full_dual_input_leaderboard_ready,
        "supported_now": (
            "Dual-input protocol audit: SPPA can be framed around two evidence paths "
            "(detector image evidence and tag/text evidence), but current real probes are not yet a leaderboard."
        ),
        "ambitious_next_claim": (
            "A dual-input benchmark where detector-produced crops/masks and tag/text inputs are frozen, "
            "then scored on task-fit, semantic readability, scale/orientation, cost, and optional GT geometry."
        ),
        "claim_boundary": (
            "A full dual-input leaderboard requires both a YOLO-detected image-input track "
            "and a tag/text-input track. Manual reviewed boxes are provenance, not detector outputs or 3D ground truth."
        ),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Dual-Input Claim Readiness",
        "",
        "Generated by `tools/sppa_sota_benchmark/audit_dual_input_sota_readiness.py`.",
        "",
        "## Verdict",
        "",
        f"- Claim posture: `{report['claim_posture']}`",
        f"- Bounded dual-input claim ready: {report.get('bounded_dual_input_claim_ready', False)}",
        f"- Full dual-input leaderboard ready: {report['full_dual_input_leaderboard_ready']}",
        f"- Requirement counts: complete={report['status_counts']['complete']}, partial={report['status_counts']['partial']}, missing={report['status_counts']['missing']}",
        f"- Supported now: {report['supported_now']}",
        f"- Ambitious next claim: {report['ambitious_next_claim']}",
        f"- Claim boundary: {report['claim_boundary']}",
        "",
        "## Requirements",
        "",
    ]
    for req in report["requirements"]:
        lines += [
            f"### `{req['key']}`",
            "",
            f"- Status: {req['status']}",
            f"- Evidence: {req['evidence']}",
            f"- Missing: {req['missing']}",
            "",
        ]
    lines += ["## Cases", ""]
    for case in report["cases"]:
        if "detector_label" in case:
            lines += [
                f"### `{case['label']}`",
                "",
                f"- Raw image: `{case['raw_image']}`",
                f"- YOLOE detector label: `{case['detector_label']}`",
                f"- YOLOE confidence: {case['detector_confidence']}",
                f"- Detector crop 512: `{case['detector_crop_512']}`",
                f"- SPPA normalized proxy: `{case['sppa_tag']}` -> `{case['runtime_archetype']}`",
                f"- Has YOLO-detected target input: {case['has_yolo_detected_target_input']}",
                f"- Image methods present: {', '.join(case['image_methods_present']) if case['image_methods_present'] else 'none'}",
                f"- Tag methods present: {', '.join(case['tag_methods_present']) if case['tag_methods_present'] else 'none'}",
                f"- Not-ranked modern image methods: {', '.join(case['not_ranked_modern_methods']) if case['not_ranked_modern_methods'] else 'none'}",
                f"- Claim boundary: {case['claim_boundary']}",
                "",
            ]
        else:
            lines += [
                f"### `{case['label']}`",
                "",
                f"- Reviewed tag: {case['reviewed_tag']}",
                f"- YOLO target hits repo/COCO: {case['repo_target_hits']} / {case['coco_target_hits']}",
                f"- Has YOLO-detected target input: {case['has_yolo_detected_target_input']}",
                f"- Manual ROI fallback: {case['manual_roi_fallback']}",
                f"- Methods present: {', '.join(case['methods']) if case['methods'] else 'none'}",
                f"- Missing image methods: {', '.join(case['missing_image_methods']) if case['missing_image_methods'] else 'none'}",
                f"- Missing tag methods: {', '.join(case['missing_tag_methods']) if case['missing_tag_methods'] else 'none'}",
                "",
            ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    json_out = args.json_out if args.json_out.is_absolute() else ROOT / args.json_out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    report = build_report()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(md_out, report)
    print(
        json.dumps(
            {
                "json": str(json_out),
                "markdown": str(md_out),
                "claim_posture": report["claim_posture"],
                "bounded_dual_input_claim_ready": report.get("bounded_dual_input_claim_ready", False),
                "full_dual_input_leaderboard_ready": report["full_dual_input_leaderboard_ready"],
                "status_counts": report["status_counts"],
            },
            indent=2,
        )
    )
    if args.strict and not report["full_dual_input_leaderboard_ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
