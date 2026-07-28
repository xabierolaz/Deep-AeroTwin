from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from geo_projector import GeoProjector  # noqa: E402

DEFAULT_RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"
REAL_REPLAY_PATH = DEFAULT_RESULTS_DIR / "real_image_assumed_flight_replay.json"
VISUAL_AUDIT_PATH = DEFAULT_RESULTS_DIR / "sppa_visual_part_evidence_audit.json"
IMAGE_CUES_PATH = DEFAULT_RESULTS_DIR / "sppa_agnostic_image_space_parts_probe.json"
DEFAULT_RUN_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260704_real_all_sppa_unified"
ANNOTATIONS_PATH = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_detection_reference"
    / "20260703_real_input_annotations"
    / "real_input_2d_annotations.json"
)
MAX_DESCRIPTOR_BYTES = 32768


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def axial_delta_deg(a: float, b: float) -> float:
    diff = abs((a - b) % 180.0)
    return min(diff, 180.0 - diff)


def tex_escape(value: Any) -> str:
    return str(value).replace("\\", "\\textbackslash{}").replace("_", "\\_")


def tex_case_label(value: Any) -> str:
    return tex_escape({"tractor_trailer": "tractor+trailer"}.get(str(value), str(value)))


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def visual_rows_by_case(path: Path) -> dict[str, dict[str, Any]]:
    data = load_json(path)
    rows: dict[str, dict[str, Any]] = {}
    for row in data.get("rows", []):
        case = str(row.get("case") or "")
        if case:
            rows[case] = row
    return rows


def replay_rows(path: Path) -> list[dict[str, Any]]:
    data = load_json(path)
    rows = data.get("rows", [])
    return rows if isinstance(rows, list) else []


def descriptor_visual_metric_by_case(run_dir: Path) -> dict[str, dict[str, Any]]:
    objects_csv = run_dir / "objects.csv"
    if not objects_csv.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    with objects_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("event") != "SPPA_OBJECT" or row.get("model") != "sppa":
                continue
            path = Path(str(row.get("descriptor_path") or ""))
            if not path.is_absolute():
                path = ROOT / path
            if not path.exists():
                continue
            descriptor = json.loads(path.read_text(encoding="utf-8"))
            visual_metric = (descriptor.get("evidence") or {}).get("visual_metric_yaw_consistency") or {}
            out[str(row.get("label") or "")] = {
                "descriptor_path": str(path),
                "descriptor_bytes": descriptor.get("cost", {}).get("descriptor_bytes"),
                "evidence_sources": (descriptor.get("evidence") or {}).get("evidence_sources") or [],
                "visual_metric": visual_metric,
                "pose": descriptor.get("pose") or {},
            }
    return out


def rows_by_case(path: Path) -> dict[str, dict[str, Any]]:
    data = load_json(path)
    rows: dict[str, dict[str, Any]] = {}
    for row in data.get("rows", data.get("items", [])):
        case = str(row.get("case_id") or row.get("label") or "")
        if case:
            rows[case] = row
    return rows


def agreement_class(delta: float | None) -> str:
    if delta is None:
        return "missing"
    if delta <= 25.0:
        return "aligned"
    if delta <= 45.0:
        return "weakly_aligned"
    return "divergent_declared"


def raw_visual_yaw_from_audit(row: dict[str, Any]) -> tuple[float | None, str | None]:
    round_axis = as_float(row.get("round_pair_axis_angle_deg"))
    if round_axis is not None:
        return round_axis % 180.0, "raw_round_pair_axis_image_space"
    line_axis = as_float(row.get("line_dominant_angle_deg"))
    if line_axis is not None:
        return line_axis % 180.0, "raw_line_axis_image_space"
    return None, None


def image_size_for(case: str, annotations_by_case: dict[str, dict[str, Any]]) -> tuple[int | None, int | None]:
    ann = annotations_by_case.get(case) or {}
    size = ann.get("image_size") if isinstance(ann.get("image_size"), dict) else {}
    width = as_float(size.get("width"))
    height = as_float(size.get("height"))
    return (None if width is None else int(width), None if height is None else int(height))


def visual_axis_points_from_cues(cue_row: dict[str, Any]) -> tuple[str | None, list[tuple[float, float]]]:
    cues = cue_row.get("image_space_cues") if isinstance(cue_row.get("image_space_cues"), dict) else {}
    pairs = cues.get("validated_round_part_pairs") if isinstance(cues.get("validated_round_part_pairs"), list) else []
    if pairs:
        strongest = sorted(
            (pair for pair in pairs if isinstance(pair, dict)),
            key=lambda pair: float(pair.get("score") or 0.0),
            reverse=True,
        )
        centers = strongest[0].get("centers_xy") if strongest else None
        if isinstance(centers, list) and len(centers) >= 2:
            return "round_pair_centers_projected_to_ground", [
                (float(centers[0][0]), float(centers[0][1])),
                (float(centers[1][0]), float(centers[1][1])),
            ]
    lines = cues.get("line_primitive_candidates") if isinstance(cues.get("line_primitive_candidates"), list) else []
    if lines:
        longest = sorted(
            (line for line in lines if isinstance(line, dict)),
            key=lambda line: float(line.get("length_px") or 0.0),
            reverse=True,
        )
        xyxy = longest[0].get("xyxy") if longest else None
        if isinstance(xyxy, list) and len(xyxy) >= 4:
            return "longest_line_projected_to_ground", [
                (float(xyxy[0]), float(xyxy[1])),
                (float(xyxy[2]), float(xyxy[3])),
            ]
    return None, []


def projected_visual_axis(
    case: str,
    cue_row: dict[str, Any],
    real_row: dict[str, Any],
    annotations_by_case: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    crop = cue_row.get("crop_xyxy")
    if not (isinstance(crop, list) and len(crop) >= 4):
        return {"available": False, "failure": "missing_crop_xyxy"}
    width, height = image_size_for(case, annotations_by_case)
    if width is None or height is None:
        return {"available": False, "failure": "missing_image_size"}
    flight = real_row.get("flight_replay") if isinstance(real_row.get("flight_replay"), dict) else {}
    source, local_points = visual_axis_points_from_cues(cue_row)
    if not source or len(local_points) < 2:
        return {"available": False, "failure": "missing_visual_axis_points"}
    params = {
        "image_height": int(height),
        "image_width": int(width),
        "drone_yaw_deg": flight.get("drone_yaw_deg"),
        "drone_pitch_deg": flight.get("drone_pitch_deg"),
        "drone_roll_deg": flight.get("drone_roll_deg"),
        "alt_agl_m": flight.get("alt_agl_m"),
        "camera_vfov_deg": flight.get("camera_vfov_deg"),
        "mount_roll_deg": flight.get("mount_roll_deg"),
        "mount_pitch_deg": flight.get("mount_pitch_deg"),
        "mount_yaw_deg": flight.get("mount_yaw_deg"),
        "max_range_m": flight.get("max_range_m"),
    }
    if any(value is None for value in params.values()):
        return {"available": False, "failure": "missing_flight_parameter"}
    projected = []
    global_points = []
    for x_local, y_local in local_points[:2]:
        x_full = float(crop[0]) + float(x_local)
        y_full = float(crop[1]) + float(y_local)
        point = GeoProjector.pixel_to_ground_offset_m(y_full, x_full, **params)
        if point is None:
            return {"available": False, "failure": "visual_axis_point_does_not_intersect_ground"}
        global_points.append([round(x_full, 3), round(y_full, 3)])
        projected.append(point)
    dn = float(projected[1]["north_m"]) - float(projected[0]["north_m"])
    de = float(projected[1]["east_m"]) - float(projected[0]["east_m"])
    length_m = math.hypot(dn, de)
    if length_m <= 1e-6:
        return {"available": False, "failure": "projected_visual_axis_degenerate"}
    yaw = math.degrees(math.atan2(de, dn)) % 180.0
    return {
        "available": True,
        "source": source,
        "yaw_deg": round(yaw, 3),
        "length_m": round(length_m, 3),
        "global_image_points_xy": global_points,
        "claim_boundary": (
            "Visual axis endpoints are projected through the declared UAV replay camera model. "
            "This is scenario-relative geometry, not measured telemetry or ground truth."
        ),
    }


def build_report(
    real_replay_path: Path,
    visual_audit_path: Path,
    image_cues_path: Path,
    annotations_path: Path,
    run_dir: Path,
) -> dict[str, Any]:
    failures: list[str] = []
    audit_warnings: list[str] = []
    visual_by_case = visual_rows_by_case(visual_audit_path)
    real_rows = replay_rows(real_replay_path)
    cues_by_case = rows_by_case(image_cues_path)
    annotations_by_case = rows_by_case(annotations_path)
    descriptor_by_case = descriptor_visual_metric_by_case(run_dir)
    if not real_replay_path.exists():
        failures.append(f"missing_real_replay:{real_replay_path}")
    if not visual_audit_path.exists():
        failures.append(f"missing_visual_audit:{visual_audit_path}")
    if not image_cues_path.exists():
        failures.append(f"missing_image_cues:{image_cues_path}")
    if not annotations_path.exists():
        failures.append(f"missing_annotations:{annotations_path}")
    if not descriptor_by_case:
        failures.append(f"missing_descriptor_visual_metric_run:{run_dir}")
    if not real_rows:
        failures.append("real_replay_has_no_rows")
    if not visual_by_case:
        failures.append("visual_audit_has_no_rows")

    rows: list[dict[str, Any]] = []
    for real_row in real_rows:
        case = str(real_row.get("case_id") or "")
        visual = visual_by_case.get(case, {})
        metric_yaw = as_float(real_row.get("yaw_deg"))
        visual_yaw, visual_yaw_source = raw_visual_yaw_from_audit(visual)
        delta = None if metric_yaw is None or visual_yaw is None else axial_delta_deg(metric_yaw, visual_yaw)
        klass = agreement_class(delta)
        projected_axis = projected_visual_axis(case, cues_by_case.get(case, {}), real_row, annotations_by_case)
        projected_yaw = as_float(projected_axis.get("yaw_deg"))
        projected_delta = (
            None if metric_yaw is None or projected_yaw is None else axial_delta_deg(metric_yaw, projected_yaw)
        )
        projected_klass = agreement_class(projected_delta)
        descriptor_metric = descriptor_by_case.get(case, {})
        descriptor_visual_metric = descriptor_metric.get("visual_metric") or {}
        descriptor_pose = descriptor_metric.get("pose") or {}
        footprint = real_row.get("sppa_footprint_m") or {}
        telemetry_measured = real_row.get("telemetry_is_measured")
        metric_gt = real_row.get("metric_ground_truth")
        metric_source = real_row.get("sppa_observation_metric_evidence_source")
        descriptor_policy = (
            "world footprint yaw is accepted only from the UAV projection branch; visual yaw remains an "
            "image-space ambiguous cue and is used as support/gating evidence, not as metric ground truth"
        )
        if visual_yaw is None:
            failures.append(f"{case}:missing_visual_yaw")
        if metric_yaw is None:
            failures.append(f"{case}:missing_projected_metric_yaw")
        if real_row.get("yaw_ambiguous") is not True:
            failures.append(f"{case}:metric_footprint_yaw_not_ambiguous")
        if telemetry_measured is not False:
            failures.append(f"{case}:telemetry_must_be_declared_replay_not_measured")
        if metric_gt is not False:
            failures.append(f"{case}:metric_ground_truth_must_be_false")
        if not footprint:
            failures.append(f"{case}:missing_sppa_footprint")
        if not projected_axis.get("available"):
            failures.append(f"{case}:projected_visual_axis_missing:{projected_axis.get('failure')}")
        if not descriptor_visual_metric.get("applied"):
            failures.append(f"{case}:descriptor_visual_metric_yaw_consistency_missing")
        if "visual_metric_yaw_consistency" not in (descriptor_metric.get("evidence_sources") or []):
            failures.append(f"{case}:descriptor_evidence_sources_missing_visual_metric_yaw_consistency")
        descriptor_delta = as_float(descriptor_visual_metric.get("axial_delta_deg"))
        descriptor_agreement = descriptor_visual_metric.get("agreement")
        if projected_delta is not None and descriptor_delta is not None and abs(projected_delta - descriptor_delta) > 0.01:
            failures.append(f"{case}:descriptor_visual_metric_delta_mismatch")
        if descriptor_agreement and descriptor_agreement != projected_klass:
            failures.append(f"{case}:descriptor_visual_metric_agreement_mismatch")
        if (
            as_float(descriptor_metric.get("descriptor_bytes"))
            and float(descriptor_metric["descriptor_bytes"]) > MAX_DESCRIPTOR_BYTES
        ):
            failures.append(f"{case}:descriptor_bytes_over_{MAX_DESCRIPTOR_BYTES}:{descriptor_metric['descriptor_bytes']}")
        if projected_klass in {"aligned", "weakly_aligned"}:
            if descriptor_pose.get("yaw_source") != "projected_footprint_yaw_gate":
                failures.append(f"{case}:descriptor_pose_yaw_not_projected_gate:{descriptor_pose.get('yaw_source')}")
            if descriptor_pose.get("yaw_coordinate_frame") != "declared_assumed_flight_replay_local_ned":
                failures.append(
                    f"{case}:descriptor_pose_yaw_frame_not_declared_replay:{descriptor_pose.get('yaw_coordinate_frame')}"
                )
            pose_yaw = as_float(descriptor_pose.get("yaw_deg"))
            if metric_yaw is not None and pose_yaw is not None and axial_delta_deg(metric_yaw, pose_yaw) > 0.01:
                failures.append(f"{case}:descriptor_pose_yaw_does_not_match_projected_footprint")
            if descriptor_pose.get("yaw_ambiguous") is not True:
                failures.append(f"{case}:descriptor_pose_projected_yaw_not_marked_ambiguous")
        if klass == "divergent_declared":
            audit_warnings.append(f"{case}:visual_metric_yaw_divergent:{delta:.2f}_deg")
        if projected_klass == "divergent_declared":
            audit_warnings.append(f"{case}:projected_visual_metric_yaw_divergent:{projected_delta:.2f}_deg")

        rows.append(
            {
                "case": case,
                "visual_yaw_deg": None if visual_yaw is None else round(visual_yaw, 3),
                "visual_yaw_source": visual_yaw_source,
                "visual_yaw_frame": "image_space_profile",
                "projected_metric_yaw_deg": None if metric_yaw is None else round(metric_yaw, 3),
                "projected_metric_source": metric_source,
                "axial_delta_deg": None if delta is None else round(delta, 3),
                "agreement": klass,
                "projected_visual_axis": projected_axis,
                "projected_visual_axis_yaw_deg": None if projected_yaw is None else round(projected_yaw, 3),
                "projected_visual_metric_delta_deg": None if projected_delta is None else round(projected_delta, 3),
                "projected_visual_metric_agreement": projected_klass,
                "descriptor_visual_metric_recorded": bool(descriptor_visual_metric.get("applied")),
                "descriptor_visual_metric_agreement": descriptor_agreement,
                "descriptor_pose_yaw_source": descriptor_pose.get("yaw_source"),
                "descriptor_pose_yaw_deg": descriptor_pose.get("yaw_deg"),
                "descriptor_pose_yaw_frame": descriptor_pose.get("yaw_coordinate_frame"),
                "descriptor_bytes": descriptor_metric.get("descriptor_bytes"),
                "descriptor_path": descriptor_metric.get("descriptor_path"),
                "telemetry_measured": telemetry_measured,
                "metric_ground_truth": metric_gt,
                "footprint_length_m": as_float(footprint.get("length_m")),
                "footprint_width_m": as_float(footprint.get("width_m")),
                "policy": descriptor_policy,
            }
        )

    return {
        "status": "passed" if not failures else "failed",
        "claim_boundary": (
            "This audit compares two independent orientation cues on real image probes: image-space visual "
            "orientation inferred from generic SPPA part/line evidence, and axial ground-footprint orientation "
            "from UAV camera projection using declared replay telemetry. It does not claim measured flight "
            "ground truth or absolute world yaw. Divergence is allowed only when explicitly declared and routed "
            "through the conservative policy."
        ),
        "real_replay_path": str(real_replay_path),
        "visual_audit_path": str(visual_audit_path),
        "image_cues_path": str(image_cues_path),
        "annotations_path": str(annotations_path),
        "run_dir": str(run_dir),
        "rows": rows,
        "aligned_count": sum(1 for row in rows if row["agreement"] == "aligned"),
        "weakly_aligned_count": sum(1 for row in rows if row["agreement"] == "weakly_aligned"),
        "divergent_declared_count": sum(1 for row in rows if row["agreement"] == "divergent_declared"),
        "projected_aligned_count": sum(1 for row in rows if row["projected_visual_metric_agreement"] == "aligned"),
        "projected_weakly_aligned_count": sum(
            1 for row in rows if row["projected_visual_metric_agreement"] == "weakly_aligned"
        ),
        "projected_divergent_declared_count": sum(
            1 for row in rows if row["projected_visual_metric_agreement"] == "divergent_declared"
        ),
        "descriptor_recorded_count": sum(1 for row in rows if row["descriptor_visual_metric_recorded"]),
        "max_descriptor_bytes": max((int(row.get("descriptor_bytes") or 0) for row in rows), default=0),
        "failures": failures,
        "audit_warnings": audit_warnings,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# SPPA Visual-Metric Yaw Consistency Audit",
        "",
        report["claim_boundary"],
        "",
        f"- Status: {report['status']}",
        f"- Aligned: {report['aligned_count']}",
        f"- Weakly aligned: {report['weakly_aligned_count']}",
        f"- Divergent but declared: {report['divergent_declared_count']}",
        f"- Projected-axis aligned: {report['projected_aligned_count']}",
        f"- Projected-axis weakly aligned: {report['projected_weakly_aligned_count']}",
        f"- Projected-axis divergent but declared: {report['projected_divergent_declared_count']}",
        f"- Descriptor-recorded rows: {report['descriptor_recorded_count']}",
        f"- Max descriptor bytes: {report['max_descriptor_bytes']}",
        f"- Failures: {report.get('failures') or 'none'}",
        f"- Audit warnings: {report.get('audit_warnings') or 'none'}",
        "",
        "| Case | Projected visual-axis yaw | Footprint yaw | Delta | Agreement | Descriptor | Policy |",
        "|---|---:|---:|---:|---|---:|---|",
    ]
    for row in report["rows"]:
        lines.append(
            f"| {row['case']} | {row['projected_visual_axis_yaw_deg']} | "
            f"{row['projected_metric_yaw_deg']} | {row['projected_visual_metric_delta_deg']} | "
            f"{row['projected_visual_metric_agreement']} | {str(row['descriptor_visual_metric_recorded']).lower()} | "
            f"{row['descriptor_pose_yaw_source']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_tex(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "\\begin{table}[H]",
        "\\centering",
        "\\footnotesize",
        "\\setlength{\\tabcolsep}{3pt}",
        "\\renewcommand{\\arraystretch}{1.08}",
        "\\caption{SPPA visual--metric yaw gate on real image probes. Pixel-space visual axes are projected through the declared UAV replay camera model before comparison with the projected ground footprint. When the gate is non-divergent, SPPA selects the axial projected-footprint yaw; both projected quantities remain scenario-relative, not measured telemetry or ground truth.}",
        "\\label{tab:sppa-visual-metric-yaw}",
        "\\begin{tabularx}{\\linewidth}{@{}L{0.15\\linewidth}r r r L{0.19\\linewidth}Y@{}}",
        "\\toprule",
        "Case & Visual axis & Footprint yaw & $\\Delta$ & Agreement & Use in SPPA \\\\",
        "\\midrule",
    ]
    visible = {
        "aligned": "aligned",
        "weakly_aligned": "weakly aligned",
        "divergent_declared": "divergent declared",
        "missing": "missing",
    }
    for row in report["rows"]:
        delta_value = row["projected_visual_metric_delta_deg"]
        visual_axis_value = row["projected_visual_axis_yaw_deg"]
        delta = "-" if delta_value is None else f"{delta_value:.1f}$^\\circ$"
        vyaw = "-" if visual_axis_value is None else f"{visual_axis_value:.1f}$^\\circ$"
        myaw = "-" if row["projected_metric_yaw_deg"] is None else f"{row['projected_metric_yaw_deg']:.1f}$^\\circ$"
        use = "selected axial footprint yaw"
        lines.append(
            f"{tex_case_label(row['case'])} & {vyaw} & {myaw} & {delta} & "
            f"{tex_escape(visible.get(row['projected_visual_metric_agreement'], row['projected_visual_metric_agreement']))} & {tex_escape(use)} \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabularx}", "\\end{table}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify SPPA visual and UAV-projected metric yaw consistency.")
    parser.add_argument("--real-replay", type=Path, default=REAL_REPLAY_PATH)
    parser.add_argument("--visual-audit", type=Path, default=VISUAL_AUDIT_PATH)
    parser.add_argument("--image-cues", type=Path, default=IMAGE_CUES_PATH)
    parser.add_argument("--annotations", type=Path, default=ANNOTATIONS_PATH)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_visual_metric_yaw_consistency.json")
    parser.add_argument("--md-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_visual_metric_yaw_consistency.md")
    parser.add_argument("--tex-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_visual_metric_yaw_consistency.tex")
    args = parser.parse_args()

    real_replay = args.real_replay if args.real_replay.is_absolute() else ROOT / args.real_replay
    visual_audit = args.visual_audit if args.visual_audit.is_absolute() else ROOT / args.visual_audit
    image_cues = args.image_cues if args.image_cues.is_absolute() else ROOT / args.image_cues
    annotations = args.annotations if args.annotations.is_absolute() else ROOT / args.annotations
    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    report = build_report(real_replay, visual_audit, image_cues, annotations, run_dir)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(args.md_out, report)
    write_tex(args.tex_out, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "aligned": report["aligned_count"],
                "weakly_aligned": report["weakly_aligned_count"],
                "divergent_declared": report["divergent_declared_count"],
                "projected_aligned": report["projected_aligned_count"],
                "projected_weakly_aligned": report["projected_weakly_aligned_count"],
                "projected_divergent_declared": report["projected_divergent_declared_count"],
                "descriptor_recorded": report["descriptor_recorded_count"],
                "max_descriptor_bytes": report["max_descriptor_bytes"],
                "failures": report["failures"],
                "json": str(args.json_out),
            },
            indent=2,
        )
    )
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
