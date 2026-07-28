from __future__ import annotations

import argparse
import ast
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260704_real_detector_refined_sppa"
DEFAULT_RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"
EXPECTED = {
    "biker": "biker",
    "tower": "vertical_structure",
    "tractor": "farm_vehicle",
    "tractor_trailer": "articulated_vehicle",
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


def as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def dims_text(dims: dict[str, Any]) -> str:
    if not dims:
        return "-"
    return f"{as_float(dims.get('length')):.2f} x {as_float(dims.get('width')):.2f} x {as_float(dims.get('height')):.2f}"


def rule_label(rule: Any) -> str:
    labels = {
        "composed_person_plus_two_wheel": "person+two-wheel",
        "specific_power_infrastructure_label": "power infrastructure",
        "farm_vehicle_label": "farm vehicle",
        "metric_long_footprint_articulated_proxy": "long-footprint metric refinement",
    }
    return labels.get(str(rule or ""), str(rule or "-").replace("_", " "))


def tex_escape(value: Any) -> str:
    return str(value).replace("\\", "\\textbackslash{}").replace("_", "\\_")


def tex_case_label(value: Any) -> str:
    labels = {
        "tractor_trailer": "tractor+trailer",
    }
    return tex_escape(labels.get(str(value), str(value)))


def read_rows(objects_csv: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with objects_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("event") != "SPPA_OBJECT" or row.get("model") != "sppa":
                continue
            row["effective_dims_m"] = parse_dictish(row.get("effective_dims_m"))
            row["raw_metric_dims_m"] = parse_dictish(row.get("raw_metric_dims_m"))
            row["fused_metric_dims_m"] = parse_dictish(row.get("fused_metric_dims_m"))
            rows[str(row.get("label") or "")] = row
    return rows


def build_report(run_dir: Path) -> dict[str, Any]:
    objects_csv = run_dir / "objects.csv"
    failures: list[str] = []
    if not objects_csv.exists():
        return {
            "status": "failed",
            "failures": [f"missing_objects_csv:{objects_csv}"],
            "run_dir": str(run_dir),
            "rows": [],
        }

    by_label = read_rows(objects_csv)
    for label in EXPECTED:
        if label not in by_label:
            failures.append(f"missing_label:{label}")

    rows: list[dict[str, Any]] = []
    total_wall_ms = 0.0
    for label, expected_semantic in EXPECTED.items():
        row = by_label.get(label, {})
        wall_ms = as_float(row.get("wall_sec")) * 1000.0
        total_wall_ms += wall_ms
        semantic_label = row.get("semantic_label") or ""
        archetype = row.get("archetype") or ""
        rule = row.get("detector_refined_rule") or ""
        refinement_applied = truthy(row.get("detector_refinement_applied"))
        semantic_source = row.get("semantic_text_source") or ""
        semantic_mode = row.get("semantic_selection_mode") or ""
        triangles = int(as_float(row.get("triangles")))
        descriptor_bytes = int(as_float(row.get("descriptor_bytes")))
        mesh_bytes = int(as_float(row.get("mesh_bytes")))
        dims = row.get("effective_dims_m") or row.get("fused_metric_dims_m") or {}

        rows.append(
            {
                "case": label,
                "semantic_label": semantic_label,
                "archetype": archetype,
                "expected_semantic_label": expected_semantic,
                "detector_refined_rule": rule,
                "detector_refinement_applied": refinement_applied,
                "semantic_selection_mode": semantic_mode,
                "semantic_text_source": semantic_source,
                "effective_dims_m": dims,
                "wall_ms": round(wall_ms, 3),
                "triangles": triangles,
                "descriptor_bytes": descriptor_bytes,
                "mesh_bytes": mesh_bytes,
            }
        )

        if semantic_mode != "detector_refined":
            failures.append(f"{label}:not_detector_refined_mode")
        if not semantic_source.startswith("detector_observation_refined_tag"):
            failures.append(f"{label}:unexpected_semantic_source:{semantic_source}")
        if semantic_label != expected_semantic:
            failures.append(f"{label}:semantic_label:{semantic_label}:expected:{expected_semantic}")
        if archetype != expected_semantic:
            failures.append(f"{label}:archetype:{archetype}:expected:{expected_semantic}")
        if wall_ms > 10.0:
            failures.append(f"{label}:wall_ms_over_10:{wall_ms:.3f}")
        if triangles > 2500:
            failures.append(f"{label}:triangles_over_2500:{triangles}")
        if descriptor_bytes > 30000:
            failures.append(f"{label}:descriptor_bytes_over_30000:{descriptor_bytes}")
        if mesh_bytes > 60000:
            failures.append(f"{label}:mesh_bytes_over_60000:{mesh_bytes}")

    trailer = by_label.get("tractor_trailer", {})
    if trailer:
        if trailer.get("detector_refined_sppa_tag") != "articulated_vehicle":
            failures.append("tractor_trailer:not_refined_to_articulated_vehicle")
        if trailer.get("detector_refined_rule") != "metric_long_footprint_articulated_proxy":
            failures.append("tractor_trailer:missing_metric_long_footprint_rule")
        if not truthy(trailer.get("detector_refinement_applied")):
            failures.append("tractor_trailer:refinement_not_applied")
        if trailer.get("semantic_label") == "tractor_trailer":
            failures.append("tractor_trailer:image_path_overclaimed_reviewed_text_class")

    if total_wall_ms > 20.0:
        failures.append(f"total_wall_ms_over_20:{total_wall_ms:.3f}")

    return {
        "status": "passed" if not failures else "failed",
        "claim_boundary": (
            "This verifies the detector-plus-observation SPPA route on the frozen real probes. It proves that "
            "weak detector labels can be refined to conservative proxy families under runtime budgets; it does "
            "not prove exact class recognition or ground-truth 3D reconstruction."
        ),
        "run_dir": str(run_dir),
        "objects_csv": str(objects_csv),
        "total_wall_ms": round(total_wall_ms, 3),
        "max_triangles": max((row["triangles"] for row in rows), default=0),
        "max_descriptor_bytes": max((row["descriptor_bytes"] for row in rows), default=0),
        "max_mesh_bytes": max((row["mesh_bytes"] for row in rows), default=0),
        "rows": rows,
        "failures": failures,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# SPPA Detector Observation Refinement Audit",
        "",
        report["claim_boundary"],
        "",
        f"- Status: {report['status']}",
        f"- Total wall time: {report['total_wall_ms']:.3f} ms",
        f"- Max triangles: {report['max_triangles']}",
        f"- Max descriptor bytes: {report['max_descriptor_bytes']}",
        f"- Max mesh bytes: {report['max_mesh_bytes']}",
        f"- Failures: {report.get('failures') or 'none'}",
        "",
        "| Case | Detector+obs semantic | Rule | Dims LxWxH | Wall ms | Tris |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in report["rows"]:
        lines.append(
            f"| {row['case']} | `{row['semantic_label']}` -> `{row['archetype']}` | "
            f"`{row['detector_refined_rule']}` | {dims_text(row['effective_dims_m'])} | "
            f"{row['wall_ms']:.3f} | {row['triangles']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_tex(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "\\begin{table}[H]",
        "\\centering",
        "\\footnotesize",
        "\\setlength{\\tabcolsep}{3pt}",
        "\\renewcommand{\\arraystretch}{1.08}",
        "\\caption{Detector-plus-observation SPPA route on frozen real probes. This route uses YOLOE semantic evidence plus replay metric dimensions, without the reviewed text tag, and remains bounded by the lightweight proxy budget.}",
        "\\label{tab:sppa-detector-observation-refinement}",
        "\\begin{tabularx}{\\linewidth}{@{}L{0.16\\linewidth}L{0.22\\linewidth}L{0.28\\linewidth}r r Y@{}}",
        "\\toprule",
        "Case & Detector+obs SPPA & Rule & ms & Tris & Boundary \\\\",
        "\\midrule",
    ]
    for row in report["rows"]:
        boundary = "conservative family"
        lines.append(
            f"{tex_case_label(row['case'])} & \\texttt{{{tex_escape(row['semantic_label'])}}} $\\rightarrow$ "
            f"\\texttt{{{tex_escape(row['archetype'])}}} & {tex_escape(rule_label(row['detector_refined_rule']))} & "
            f"{row['wall_ms']:.3f} & {row['triangles']} & {boundary} \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabularx}", "\\end{table}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify detector-plus-observation SPPA real-input route.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_detector_observation_refinement_audit.json")
    parser.add_argument("--md-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_detector_observation_refinement_audit.md")
    parser.add_argument("--tex-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_detector_observation_refinement_audit.tex")
    args = parser.parse_args()

    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    report = build_report(run_dir)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(args.md_out, report)
    write_tex(args.tex_out, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "failures": report["failures"],
                "total_wall_ms": report["total_wall_ms"],
                "max_triangles": report["max_triangles"],
                "json": str(args.json_out),
            },
            indent=2,
        )
    )
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
