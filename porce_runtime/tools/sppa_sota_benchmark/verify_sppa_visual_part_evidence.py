from __future__ import annotations

import argparse
import ast
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260704_real_all_sppa_unified"
DEFAULT_RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"

EXPECTED_ROLE_SUPPORT = {
    "biker": {"vehicle_tire", "bike_frame"},
    "tower": {"vertical_structure_metal"},
    "tractor": {"vehicle_tire", "vehicle_attachment"},
    "tractor_trailer": {"container_detail"},
}

EXPECTED_GEOMETRY_FEATURES = {
    "biker": {"round_pair"},
    "tower": {"line_structure"},
    "tractor": {"round_pair"},
    "tractor_trailer": {"line_structure"},
}


def parse_dictish(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    text = str(value).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    try:
        parsed = ast.literal_eval(text)
        return parsed if isinstance(parsed, dict) else {}
    except (SyntaxError, ValueError, TypeError):
        return {}


def parse_listish(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except (SyntaxError, ValueError, TypeError):
        pass
    return [part.strip() for part in text.split(",") if part.strip()]


def as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def read_rows(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("event") != "SPPA_OBJECT" or row.get("model") != "sppa":
                continue
            rows[str(row.get("label") or "")] = row
    return rows


def descriptor_path_from_row(row: dict[str, Any]) -> Path:
    raw = str(row.get("descriptor_path") or "")
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def role_supported_parts(descriptor: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for part in descriptor.get("parts") or []:
        if not isinstance(part, dict):
            continue
        role = str(part.get("role") or part.get("material_role") or "")
        if part.get("visual_part_evidence_version"):
            counts[role] = counts.get(role, 0) + 1
    return counts


def geometry_features(profile: dict[str, Any]) -> list[str]:
    features: list[str] = []
    if isinstance(profile.get("round_pair"), dict):
        features.append("round_pair")
    if isinstance(profile.get("line_structure"), dict):
        features.append("line_structure")
    return features


def build_report(run_dir: Path) -> dict[str, Any]:
    objects_csv = run_dir / "objects.csv"
    failures: list[str] = []
    if not objects_csv.exists():
        return {
            "status": "failed",
            "failures": [f"missing_objects_csv:{objects_csv}"],
            "rows": [],
        }
    rows_by_label = read_rows(objects_csv)
    rows: list[dict[str, Any]] = []
    for label, expected_roles in EXPECTED_ROLE_SUPPORT.items():
        expected_features = EXPECTED_GEOMETRY_FEATURES.get(label, set())
        row = rows_by_label.get(label)
        if row is None:
            failures.append(f"{label}:missing_row")
            continue
        descriptor_path = descriptor_path_from_row(row)
        if not descriptor_path.exists():
            failures.append(f"{label}:missing_descriptor:{descriptor_path}")
            continue
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        visual = descriptor.get("evidence", {}).get("visual_part_evidence") or {}
        visual_shape = descriptor.get("evidence", {}).get("visual_shape_conditioning") or {}
        visual_geometry = visual.get("geometry_profile") or {}
        round_pair = visual_geometry.get("round_pair") or {}
        line_structure = visual_geometry.get("line_structure") or {}
        features = set(geometry_features(visual_geometry))
        csv_roles = set(parse_listish(row.get("visual_part_evidence_roles")))
        descriptor_roles = set(visual.get("supported_roles") or [])
        part_role_counts = role_supported_parts(descriptor)
        supported_part_roles = set(part_role_counts)
        all_roles = descriptor_roles | csv_roles | supported_part_roles
        missing_expected = sorted(expected_roles - all_roles)
        missing_features = sorted(expected_features - features)
        label_used = bool(visual.get("label_used"))
        geometry_label_used = bool(visual_geometry.get("label_used"))
        evidence_sources = descriptor.get("evidence", {}).get("evidence_sources") or []
        pose = descriptor.get("pose") or {}
        descriptor_bytes = int(as_float(row.get("descriptor_bytes")))
        triangles = int(as_float(row.get("triangles")))
        wall_ms = as_float(row.get("wall_sec")) * 1000.0

        rows.append(
            {
                "case": label,
                "scope": visual.get("scope"),
                "roles": sorted(all_roles),
                "expected_roles": sorted(expected_roles),
                "part_role_counts": part_role_counts,
                "applied": bool(visual.get("applied")),
                "label_used": label_used,
                "geometry_profile_applied": bool(visual_geometry.get("applied")),
                "geometry_profile_features": sorted(features),
                "geometry_profile_version": visual_geometry.get("version"),
                "geometry_label_used": geometry_label_used,
                "round_pair_axis_angle_deg": round_pair.get("axis_angle_deg"),
                "round_pair_radius_ratio": round_pair.get("radius_ratio"),
                "round_pair_separation_radius_ratio": round_pair.get("separation_radius_ratio"),
                "line_dominant_angle_deg": line_structure.get("dominant_angle_deg"),
                "line_max_length_px": line_structure.get("max_line_length_px"),
                "yaw_source": pose.get("yaw_source"),
                "yaw_deg": pose.get("yaw_deg"),
                "yaw_coordinate_frame": pose.get("yaw_coordinate_frame"),
                "yaw_ambiguous": pose.get("yaw_ambiguous"),
                "visual_metric_yaw_consistency": (descriptor.get("evidence") or {}).get(
                    "visual_metric_yaw_consistency"
                ),
                "visual_shape_conditioning_applied": bool(visual_shape.get("applied")),
                "visual_shape_conditioning_added_parts": visual_shape.get("added_parts"),
                "visual_shape_conditioning_added_triangles": visual_shape.get("added_triangles"),
                "visual_shape_conditioning_additions": visual_shape.get("additions"),
                "descriptor_bytes": descriptor_bytes,
                "triangles": triangles,
                "wall_ms": round(wall_ms, 3),
            }
        )

        if not visual.get("applied"):
            failures.append(f"{label}:visual_part_evidence_not_applied")
        if label_used:
            failures.append(f"{label}:visual_part_evidence_used_label")
        if not visual_geometry.get("applied"):
            failures.append(f"{label}:visual_geometry_profile_not_applied")
        if geometry_label_used:
            failures.append(f"{label}:visual_geometry_profile_used_label")
        if "visual_part_evidence" not in evidence_sources:
            failures.append(f"{label}:descriptor_evidence_source_missing")
        if "visual_shape_conditioning" not in evidence_sources:
            failures.append(f"{label}:descriptor_evidence_source_missing_visual_shape_conditioning")
        if not visual_shape.get("applied"):
            failures.append(f"{label}:visual_shape_conditioning_not_applied")
        yaw_source = str(pose.get("yaw_source") or "")
        visual_metric = (descriptor.get("evidence") or {}).get("visual_metric_yaw_consistency") or {}
        if yaw_source == "projected_footprint_yaw_gate":
            if pose.get("yaw_coordinate_frame") != "declared_assumed_flight_replay_local_ned":
                failures.append(
                    f"{label}:projected_yaw_frame_not_declared_replay:{pose.get('yaw_coordinate_frame')}"
                )
            if not visual_metric.get("applied"):
                failures.append(f"{label}:projected_yaw_without_visual_metric_gate")
            if visual_metric.get("agreement") not in {"aligned", "weakly_aligned"}:
                failures.append(f"{label}:projected_yaw_without_nondivergent_visual_metric_gate")
        elif yaw_source.startswith("visual_"):
            if pose.get("yaw_coordinate_frame") != "image_space_px":
                failures.append(f"{label}:visual_orientation_frame_not_image_space:{pose.get('yaw_coordinate_frame')}")
        else:
            failures.append(f"{label}:unexpected_orientation_source:{pose.get('yaw_source')}")
        if pose.get("yaw_ambiguous") is not True:
            failures.append(f"{label}:visual_orientation_not_marked_ambiguous")
        if missing_expected:
            failures.append(f"{label}:missing_expected_roles:{','.join(missing_expected)}")
        if missing_features:
            failures.append(f"{label}:missing_geometry_features:{','.join(missing_features)}")
        if not supported_part_roles:
            failures.append(f"{label}:no_parts_annotated_with_visual_evidence")
        if descriptor_bytes > 32768:
            failures.append(f"{label}:descriptor_bytes_over_32768:{descriptor_bytes}")
        if triangles > 2500:
            failures.append(f"{label}:triangles_over_2500:{triangles}")
        if wall_ms > 10.0:
            failures.append(f"{label}:wall_ms_over_10:{wall_ms:.3f}")

    return {
        "status": "passed" if not failures else "failed",
        "claim_boundary": (
            "Visual part evidence is role-conditioned support from generic image-space cues. It can annotate "
            "existing SPPA roles in the descriptor and add low-cost conditioning primitives to those existing "
            "roles, but it cannot introduce new classes, replace the semantic normalizer, or claim ground-truth "
            "part segmentation. The associated geometry profile is image-space only and is recorded once per "
            "descriptor to avoid descriptor bloat."
        ),
        "run_dir": str(run_dir),
        "objects_csv": str(objects_csv),
        "rows": rows,
        "failures": failures,
    }


def tex_escape(value: Any) -> str:
    return str(value).replace("\\", "\\textbackslash{}").replace("_", "\\_")


def tex_case_label(value: Any) -> str:
    return tex_escape({"tractor_trailer": "tractor+trailer"}.get(str(value), str(value)))


def role_text(roles: list[str]) -> str:
    visible = {
        "vehicle_tire": "tire",
        "vehicle_metal_or_hub": "hub",
        "bike_frame": "frame",
        "vertical_structure_metal": "tower metal",
        "vehicle_attachment": "attachment",
        "container_detail": "container detail",
    }
    return ", ".join(visible.get(role, role.replace("_", " ")) for role in roles)


def scope_text(scope: Any) -> str:
    visible = {
        "round_part_pair_candidate": "round-pair candidate",
        "weak_round_pair_candidate": "weak round-pair candidate",
        "multi_line_structure_candidate": "multi-line candidate",
        "image_edge_axis_candidate": "edge-axis candidate",
        "mask_envelope_only": "mask envelope",
    }
    return visible.get(str(scope), str(scope).replace("_", " "))


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# SPPA Visual Part Evidence Audit",
        "",
        report["claim_boundary"],
        "",
        f"- Status: {report['status']}",
        f"- Failures: {report.get('failures') or 'none'}",
        "",
        "| Case | Scope | Roles | Geometry profile | Visual shape | Visual yaw | Wall ms | Tris | Descriptor bytes |",
        "|---|---|---|---|---|---|---:|---:|---:|",
    ]
    for row in report["rows"]:
        lines.append(
            f"| {row['case']} | {row['scope']} | {', '.join(row['roles'])} | "
            f"{', '.join(row['geometry_profile_features'])} | "
            f"+{row['visual_shape_conditioning_added_triangles']} tris | "
            f"{row['yaw_source']} @ {row['yaw_deg']} deg | "
            f"{row['wall_ms']:.3f} | {row['triangles']} | {row['descriptor_bytes']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_tex(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "\\begin{table}[H]",
        "\\centering",
        "\\footnotesize",
        "\\setlength{\\tabcolsep}{3pt}",
        "\\renewcommand{\\arraystretch}{1.08}",
        "\\caption{SPPA visual part evidence audit. Generic pixel cues from the detector crop annotate existing descriptor roles, store a compact image-space geometry profile, and may add budgeted conditioning primitives to existing roles. They do not change the semantic class or claim ground-truth part segmentation.}",
        "\\label{tab:sppa-visual-part-evidence}",
        "\\begin{tabularx}{\\linewidth}{@{}L{0.15\\linewidth}L{0.23\\linewidth}L{0.25\\linewidth}r r r Y@{}}",
        "\\toprule",
        "Case & Generic cue scope & Supported descriptor roles & Visual tris & ms & Tris & Boundary \\\\",
        "\\midrule",
    ]
    for row in report["rows"]:
        lines.append(
            f"{tex_case_label(row['case'])} & {tex_escape(scope_text(row['scope']))} & "
            f"{tex_escape(role_text(row['roles']))} & {row['visual_shape_conditioning_added_triangles']} & "
            f"{row['wall_ms']:.3f} & {row['triangles']} & existing roles only \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabularx}", "\\end{table}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify SPPA descriptor visual part evidence.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_visual_part_evidence_audit.json")
    parser.add_argument("--md-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_visual_part_evidence_audit.md")
    parser.add_argument("--tex-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_visual_part_evidence_audit.tex")
    args = parser.parse_args()

    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    report = build_report(run_dir)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(args.md_out, report)
    write_tex(args.tex_out, report)
    print(json.dumps({"status": report["status"], "failures": report["failures"], "json": str(args.json_out)}, indent=2))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
