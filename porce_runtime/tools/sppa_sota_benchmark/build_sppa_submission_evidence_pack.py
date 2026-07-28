from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PAPER_RESULTS = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"
DUAL_INPUT_JSON = PAPER_RESULTS / "real_yoloe_dual_input_benchmark.json"
UNREAL_PROFILE_SUMMARY_CSV = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_packaged_render"
    / "20260703T031115Z_packaged_render"
    / "unreal_csv_profile_summary.csv"
)
SCHEDULER_REPLAY_CSV = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_descriptor_update"
    / "20260702_observed_material_v04_large"
    / "replay_update_rows.csv"
)

METHOD_EXCLUSIONS = [
    {
        "method": "hunyuan3d_2_1",
        "family": "image_to_3d",
        "status": "not_ranked",
        "reason": "Not rerun under the frozen four-real-image local protocol before this submission precheck.",
        "claim_effect": "Listed as required future work for any full visual image-to-3D leaderboard.",
    },
    {
        "method": "stable_fast_3d",
        "family": "image_to_3d",
        "status": "not_ranked",
        "reason": "Installed in a Python 3.10 environment but produced no benchmark event before the 20 minute local timeout in the previous pass.",
        "claim_effect": "Not counted as an output-quality failure; excluded from the bounded systems ranking.",
    },
    {
        "method": "spar3d",
        "family": "image_to_3d",
        "status": "not_ranked",
        "reason": "Local install completed, but the required model weights were gated before inference.",
        "claim_effect": "Reproducibility blocker for visual leaderboard; not a measured output-quality result.",
    },
    {
        "method": "trellis2_4b",
        "family": "image_to_3d",
        "status": "not_ranked",
        "reason": "Not installed and not executed under the local constrained protocol.",
        "claim_effect": "A contemporary visual leaderboard should include it or explain a venue-approved exclusion.",
    },
    {
        "method": "pixal3d",
        "family": "image_to_3d",
        "status": "not_ranked",
        "reason": "SIGGRAPH 2026 method identified after the local four-image pass; not installed or executed under the frozen protocol.",
        "claim_effect": "Required for a July 2026 high-fidelity visual leaderboard; excluded from the bounded SPPA systems claim.",
    },
    {
        "method": "tripo_sg_or_tripo_p1",
        "family": "image_to_3d",
        "status": "not_ranked",
        "reason": "Contemporary Tripo foundation/API variants were not run locally under the frozen crop protocol; only local TripoSR is reproduced.",
        "claim_effect": "Do not imply TripoSR represents the current Tripo family in a full visual leaderboard.",
    },
    {
        "method": "direct3d_s2",
        "family": "image_to_3d",
        "status": "not_ranked",
        "reason": "High-resolution sparse-volume method identified as contemporary related work but not installed or executed locally.",
        "claim_effect": "Needed as a high-fidelity baseline or explicit exclusion in any venue-grade visual SOTA comparison.",
    },
    {
        "method": "partcrafter",
        "family": "structured_image_to_3d",
        "status": "not_ranked",
        "reason": "Part-aware structured 3D method is relevant to SPPA's part/proxy argument but was not installed or run.",
        "claim_effect": "Should be discussed as related work; not a measured baseline in the bounded systems table.",
    },
    {
        "method": "rodin_gen_2_5",
        "family": "commercial_image_text_to_3d",
        "status": "not_ranked",
        "reason": "Commercial/API system reported as fast and production-oriented; not locally reproducible in the frozen offline artifact.",
        "claim_effect": "Useful for market/context discussion, but not ranked without API-run provenance, common inputs, and cost/runtime records.",
    },
]

PREFERENCE_CRITERIA = [
    ("semantic_readability", "Can a reviewer identify the intended family without seeing the tag?"),
    ("task_fit", "Would the output be useful as a UAV obstacle/display proxy for a live track?"),
    ("scale_orientation_plausibility", "Are dimensions and dominant orientation plausible for the available evidence?"),
    ("control_cost", "Is the output lightweight enough for repeated updates in the target runtime?"),
    ("failure_transparency", "Does the method expose uncertainty/fallback instead of pretending to know unsupported detail?"),
]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


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


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_method_exclusions() -> dict[str, Any]:
    report = {
        "schema": "SPPA-SOTA-METHOD-EXCLUSIONS-0.1",
        "created_utc": utc_stamp(),
        "exclusion_scope": (
            "These methods are not ranked in the bounded SPPA systems claim. They remain required future work "
            "for a venue-grade full visual image-to-3D leaderboard."
        ),
        "bounded_claim_effect": "The runtime/task-fit SPPA claim compares local reproduced outputs and explicitly excludes full visual SOTA ranking.",
        "items": METHOD_EXCLUSIONS,
    }
    write_json(PAPER_RESULTS / "sota_method_exclusions.json", report)
    lines = [
        "# SOTA Method Exclusions",
        "",
        "Generated by `tools/sppa_sota_benchmark/build_sppa_submission_evidence_pack.py`.",
        "",
        f"- Scope: {report['exclusion_scope']}",
        f"- Bounded claim effect: {report['bounded_claim_effect']}",
        "",
    ]
    for item in METHOD_EXCLUSIONS:
        lines += [
            f"## `{item['method']}`",
            "",
            f"- Family: {item['family']}",
            f"- Status: {item['status']}",
            f"- Reason: {item['reason']}",
            f"- Claim effect: {item['claim_effect']}",
            "",
        ]
    (PAPER_RESULTS / "sota_method_exclusions.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def write_preference_protocol() -> dict[str, Any]:
    report = {
        "schema": "SPPA-PREFERENCE-PROTOCOL-0.1",
        "created_utc": utc_stamp(),
        "status": "protocol_only_no_human_scores_yet",
        "minimum_reviewers": 5,
        "score_range": "1-5 Likert per criterion plus forced-choice task-fit preference",
        "blind_fields": ["method_name", "runtime_cost", "input_mode"],
        "criteria": [{"key": key, "question": question} for key, question in PREFERENCE_CRITERIA],
        "claim_boundary": (
            "This protocol enables a future human/task preference study. It is not itself a completed human evaluation."
        ),
    }
    write_json(PAPER_RESULTS / "sota_preference_protocol.json", report)
    lines = [
        "# SPPA Human/Task Preference Protocol",
        "",
        "Generated by `tools/sppa_sota_benchmark/build_sppa_submission_evidence_pack.py`.",
        "",
        f"- Status: `{report['status']}`",
        f"- Minimum reviewers: {report['minimum_reviewers']}",
        f"- Score range: {report['score_range']}",
        f"- Claim boundary: {report['claim_boundary']}",
        "",
        "## Criteria",
        "",
    ]
    for item in report["criteria"]:
        lines += [f"- `{item['key']}`: {item['question']}"]
    lines += [
        "",
        "## Procedure",
        "",
        "1. Freeze input evidence for each case: detector crop for image-conditioned methods and tag/text prompt for text-conditioned methods.",
        "2. Render every output from the same camera and scale frame where possible.",
        "3. Hide method names and runtime costs during visual scoring.",
        "4. Score each criterion from 1 to 5 and add one forced-choice question: which output would you trust as a UAV obstacle/display proxy?",
        "5. Report median and interquartile range per method and case; keep runtime/task-fit ranking separate from visual quality ranking.",
        "",
    ]
    (PAPER_RESULTS / "sota_preference_protocol.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def write_image_alignment_metrics() -> dict[str, Any]:
    dual = load_json(DUAL_INPUT_JSON)
    rows = []
    for case in dual.get("cases", []):
        crop_meta = case.get("detector_crop_meta") or {}
        source_size = crop_meta.get("source_image_size") or {}
        rows.append(
            {
                "label": case.get("label"),
                "raw_image": case.get("raw_image"),
                "image_width": source_size.get("width"),
                "image_height": source_size.get("height"),
                "detector_label": case.get("selected_detector_label"),
                "detector_confidence": case.get("selected_confidence"),
                "sppa_tag": case.get("selected_sppa_tag"),
                "sppa_proxy": case.get("selected_runtime_archetype"),
                "bbox_xyxy": json.dumps(case.get("detector_bbox_xyxy")),
                "bbox_area_fraction": case.get("detector_bbox_area_fraction"),
                "mask_area_px": case.get("detector_mask_area_px"),
                "crop_512": case.get("detector_crop_512"),
                "metric_scope": "detector_provenance_and_semantic_alignment_only_no_3d_gt",
            }
        )
    out_csv = PAPER_RESULTS / "sota_image_alignment_metrics.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["label"])
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "schema": "SPPA-IMAGE-ALIGNMENT-METRICS-0.1",
        "created_utc": utc_stamp(),
        "csv": rel(out_csv),
        "case_count": len(rows),
        "scope": "Detector bbox/confidence and semantic normalization metrics only; no 3D ground-truth quality is claimed.",
        "all_cases_have_detector_crop": bool(rows) and all(row.get("crop_512") for row in rows),
    }
    write_json(PAPER_RESULTS / "sota_image_alignment_metrics.json", report)
    lines = [
        "# Image Alignment Metrics",
        "",
        "Generated by `tools/sppa_sota_benchmark/build_sppa_submission_evidence_pack.py`.",
        "",
        f"- CSV: `{report['csv']}`",
        f"- Case count: {report['case_count']}",
        f"- All cases have detector crop: {report['all_cases_have_detector_crop']}",
        f"- Scope: {report['scope']}",
        "",
        "| Case | Detector | Conf. | SPPA proxy | BBox area |",
        "|---|---|---:|---|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['label']} | `{row['detector_label']}` | {safe_float(row['detector_confidence']):.3f} | "
            f"`{row['sppa_proxy']}` | {safe_float(row['bbox_area_fraction']):.4f} |"
        )
    lines.append("")
    (PAPER_RESULTS / "sota_image_alignment_metrics.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def profile_phase(metric: str) -> tuple[str, str]:
    if metric in {"FrameTime"}:
        return "frame", "end_to_end_render_frame_timing"
    if "GameThread" in metric or metric.startswith("Ticks/"):
        return "game_thread", "unreal_game_thread_actor_or_runner_cost"
    if "RenderThread" in metric:
        return "render_thread", "unreal_render_thread_scene_update_cost"
    if "GPU" in metric or metric.startswith("GPUMem"):
        return "gpu", "gpu_timing_or_memory_budget"
    if metric.startswith("RHI/") or "RHIThread" in metric:
        return "rhi", "draw_submission_and_rhi_budget"
    if metric.startswith("Exclusive/"):
        return "render_micro_event", "render_thread_micro_counter"
    return "other", "supporting_counter"


def write_phase_aligned_unreal_profile() -> dict[str, Any]:
    rows_in = read_csv(UNREAL_PROFILE_SUMMARY_CSV)
    selected_metrics = {
        "FrameTime",
        "GameThreadTime",
        "RenderThreadTime",
        "RenderThreadTime_CriticalPath",
        "RHIThreadTime",
        "GPUTime",
        "RHI/DrawCalls",
        "RHI/PrimitivesDrawn",
        "GPUSceneInstanceCount",
        "GPUMem/LocalUsedMB",
        "Exclusive/RenderThread/AddPrimitiveSceneInfos",
        "Exclusive/RenderThread/RemovePrimitiveSceneInfos",
        "Exclusive/RenderThread/UpdatePrimitiveInstances",
        "Exclusive/RenderThread/UpdatePrimitiveTransform",
        "Exclusive/RenderThread/UpdateGPUScene",
    }
    rows = []
    for row in rows_in:
        metric = row.get("metric") or ""
        if metric not in selected_metrics:
            continue
        phase, claim_role = profile_phase(metric)
        rows.append(
            {
                "phase": phase,
                "metric": metric,
                "source_profile": row.get("file"),
                "n": row.get("n"),
                "p50": row.get("p50"),
                "p95": row.get("p95"),
                "p99": row.get("p99"),
                "max": row.get("max"),
                "mean": row.get("mean"),
                "claim_role": claim_role,
            }
        )
    out_csv = PAPER_RESULTS / "sppa_phase_aligned_unreal_profile.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "phase",
                "metric",
                "source_profile",
                "n",
                "p50",
                "p95",
                "p99",
                "max",
                "mean",
                "claim_role",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    phases = sorted({row["phase"] for row in rows})
    phase_counts = Counter(row["phase"] for row in rows)
    report = {
        "schema": "SPPA-PHASE-ALIGNED-UNREAL-PROFILE-0.1",
        "created_utc": utc_stamp(),
        "source": rel(UNREAL_PROFILE_SUMMARY_CSV),
        "csv": rel(out_csv),
        "row_count": len(rows),
        "phases": phases,
        "phase_counts": dict(phase_counts),
        "claim_boundary": (
            "Profiled packaged Unreal CSV counters are separated by engine phase. They are not live UAV telemetry, "
            "but they support phase-aware packaged-render feasibility evidence."
        ),
    }
    write_json(PAPER_RESULTS / "sppa_phase_aligned_unreal_profile.json", report)
    lines = [
        "# Phase-Aligned Unreal Profile",
        "",
        "Generated by `tools/sppa_sota_benchmark/build_sppa_submission_evidence_pack.py`.",
        "",
        f"- Source: `{report['source']}`",
        f"- CSV: `{report['csv']}`",
        f"- Rows: {report['row_count']}",
        f"- Phases: {', '.join(report['phases'])}",
        f"- Boundary: {report['claim_boundary']}",
        "",
        "| Phase | Metrics |",
        "|---|---:|",
    ]
    for phase in phases:
        lines.append(f"| `{phase}` | {phase_counts[phase]} |")
    lines.append("")
    (PAPER_RESULTS / "sppa_phase_aligned_unreal_profile.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return ordered[idx]


def parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def write_scheduler_active_track_replay() -> dict[str, Any]:
    rows_in = read_csv(SCHEDULER_REPLAY_CSV)
    timestamps = [ts for ts in (parse_timestamp(row.get("timestamp", "")) for row in rows_in) if ts]
    duration_s = 0.0
    if len(timestamps) >= 2:
        duration_s = max(0.0, (max(timestamps) - min(timestamps)).total_seconds())
    action_counts = Counter(row.get("action") or "unknown" for row in rows_in)
    tracks = {row.get("track_id") for row in rows_in if row.get("track_id")}
    frames = {row.get("frame_id") for row in rows_in if row.get("frame_id")}
    timing_columns = [
        "descriptor_build_us",
        "descriptor_build_with_parts_us",
        "schedule_us",
        "scheduler_decision_us",
        "update_packet_build_us",
        "effective_create_us",
        "pose_update_no_mesh_us",
    ]
    timings: dict[str, list[float]] = defaultdict(list)
    for row in rows_in:
        for key in timing_columns:
            value = row.get(key)
            if value not in (None, ""):
                timings[key].append(safe_float(value))
    out_csv = PAPER_RESULTS / "sppa_scheduler_active_track_replay.csv"
    summary_row = {
        "source": rel(SCHEDULER_REPLAY_CSV),
        "rows": len(rows_in),
        "unique_tracks": len(tracks),
        "unique_frames": len(frames),
        "duration_s": round(duration_s, 6),
        "row_rate_hz": round(len(rows_in) / duration_s, 3) if duration_s > 0 else "",
        "create_count": action_counts.get("create", 0),
        "shape_param_update_count": action_counts.get("shape_param_update", 0),
        "pose_update_count": action_counts.get("pose_update", 0),
        "no_op_count": action_counts.get("no_op", 0),
        "descriptor_build_us_p50": round(median(timings["descriptor_build_us"]), 3) if timings["descriptor_build_us"] else "",
        "descriptor_build_us_p95": round(percentile(timings["descriptor_build_us"], 0.95), 3)
        if timings["descriptor_build_us"]
        else "",
        "scheduler_decision_us_p50": round(median(timings["scheduler_decision_us"]), 3)
        if timings["scheduler_decision_us"]
        else "",
        "scheduler_decision_us_p95": round(percentile(timings["scheduler_decision_us"], 0.95), 3)
        if timings["scheduler_decision_us"]
        else "",
        "packet_build_us_p50": round(median(timings["update_packet_build_us"]), 3)
        if timings["update_packet_build_us"]
        else "",
        "packet_build_us_p95": round(percentile(timings["update_packet_build_us"], 0.95), 3)
        if timings["update_packet_build_us"]
        else "",
        "claim_scope": "recorded_descriptor_scheduler_replay_not_live_flight_radio_link",
    }
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_row.keys()))
        writer.writeheader()
        writer.writerow(summary_row)
    report = {
        "schema": "SPPA-SCHEDULER-ACTIVE-TRACK-REPLAY-0.1",
        "created_utc": utc_stamp(),
        "source": rel(SCHEDULER_REPLAY_CSV),
        "csv": rel(out_csv),
        "rows": len(rows_in),
        "unique_tracks": len(tracks),
        "unique_frames": len(frames),
        "duration_s": summary_row["duration_s"],
        "action_counts": dict(action_counts),
        "claim_boundary": (
            "This is an active-track descriptor scheduler replay from recorded logs. It is not a live flight test, "
            "but it establishes create/update/no-op scheduling rates and packet-building costs."
        ),
    }
    write_json(PAPER_RESULTS / "sppa_scheduler_active_track_replay.json", report)
    lines = [
        "# Scheduler Active-Track Replay",
        "",
        "Generated by `tools/sppa_sota_benchmark/build_sppa_submission_evidence_pack.py`.",
        "",
        f"- Source: `{report['source']}`",
        f"- CSV: `{report['csv']}`",
        f"- Rows: {report['rows']}",
        f"- Unique tracks: {report['unique_tracks']}",
        f"- Unique frames: {report['unique_frames']}",
        f"- Duration (s): {report['duration_s']}",
        f"- Action counts: {report['action_counts']}",
        f"- Boundary: {report['claim_boundary']}",
        "",
    ]
    (PAPER_RESULTS / "sppa_scheduler_active_track_replay.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SPPA submission evidence artifacts around the bounded claim.")
    parser.parse_args()
    PAPER_RESULTS.mkdir(parents=True, exist_ok=True)
    outputs = {
        "method_exclusions": write_method_exclusions(),
        "preference_protocol": write_preference_protocol(),
        "image_alignment_metrics": write_image_alignment_metrics(),
        "phase_aligned_unreal_profile": write_phase_aligned_unreal_profile(),
        "scheduler_active_track_replay": write_scheduler_active_track_replay(),
    }
    summary = {
        "schema": "SPPA-SUBMISSION-EVIDENCE-PACK-0.1",
        "created_utc": utc_stamp(),
        "outputs": {
            key: {
                "schema": value.get("schema"),
                "csv": value.get("csv"),
                "status": value.get("status"),
                "row_count": value.get("row_count") or value.get("case_count") or value.get("rows"),
            }
            for key, value in outputs.items()
        },
        "claim_boundary": (
            "This pack upgrades the bounded SPPA systems claim. It does not create 3D ground truth or a full visual "
            "image-to-3D SOTA leaderboard."
        ),
    }
    write_json(PAPER_RESULTS / "sppa_submission_evidence_pack.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
