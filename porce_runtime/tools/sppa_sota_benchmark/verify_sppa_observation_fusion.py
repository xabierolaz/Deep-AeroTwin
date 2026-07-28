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
EXPECTED = ["biker", "tower", "tractor", "tractor_trailer"]
GATE_LABELS = {
    "vehicle_soft_low_confidence_fusion": "soft low-conf fusion",
    "vehicle_soft_aspect_fusion": "soft aspect fusion",
    "vehicle_soft_constraint_fusion": "soft constraint fusion",
    "vertical_height_only_low_confidence_shape": "height-only fusion",
    "accepted": "accepted",
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
        loaded = json.loads(text)
        return loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        pass
    try:
        loaded = ast.literal_eval(text)
        return loaded if isinstance(loaded, dict) else {}
    except (SyntaxError, ValueError, TypeError):
        return {}


def as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def aspect(dims: dict[str, Any]) -> float:
    length = max(as_float(dims.get("length")), as_float(dims.get("width")))
    width = max(0.01, min(as_float(dims.get("length")), as_float(dims.get("width"))))
    return length / width


def dims_text(dims: dict[str, Any]) -> str:
    if not dims:
        return "-"
    return f"{as_float(dims.get('length')):.2f} x {as_float(dims.get('width')):.2f} x {as_float(dims.get('height')):.2f}"


def gate_text(value: Any) -> str:
    return GATE_LABELS.get(str(value or ""), str(value or "-").replace("_", " "))


def tex_escape(text: Any) -> str:
    return str(text).replace("\\", "\\textbackslash{}").replace("_", "\\_")


def read_rows(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = {}
        for row in csv.DictReader(handle):
            if row.get("event") == "SPPA_OBJECT" and row.get("model") == "sppa":
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
            "failures": [f"missing objects.csv: {objects_csv}"],
            "rows": [],
        }
    rows_by_label = read_rows(objects_csv)
    for label in EXPECTED:
        if label not in rows_by_label:
            failures.append(f"missing_label:{label}")

    rows: list[dict[str, Any]] = []
    for label in EXPECTED:
        row = rows_by_label.get(label, {})
        raw_dims = row.get("raw_metric_dims_m") or {}
        fused_dims = row.get("fused_metric_dims_m") or {}
        applied = str(row.get("observation_applied") or "").lower() in {"true", "1", "yes"}
        pose_used = str(row.get("observation_image_geometry_applied") or "").lower() in {"true", "1", "yes"}
        raw_aspect = aspect(raw_dims)
        fused_aspect = aspect(fused_dims)
        rows.append(
            {
                "label": label,
                "gate": row.get("observation_gate"),
                "raw_dims_m": raw_dims,
                "fused_dims_m": fused_dims,
                "raw_aspect": round(raw_aspect, 3),
                "fused_aspect": round(fused_aspect, 3),
                "observation_applied": applied,
                "image_pose_used": pose_used,
                "wall_ms": round(as_float(row.get("wall_sec")) * 1000.0, 3),
                "triangles": int(as_float(row.get("triangles"))),
                "descriptor_bytes": int(as_float(row.get("descriptor_bytes"))),
            }
        )

    def row_for(label: str) -> dict[str, Any]:
        return next(item for item in rows if item["label"] == label)

    for item in rows:
        if not item["observation_applied"]:
            failures.append(f"{item['label']}:observation_not_applied")
        if not item["fused_dims_m"]:
            failures.append(f"{item['label']}:missing_fused_dims")
        if item["wall_ms"] > 10.0:
            failures.append(f"{item['label']}:wall_ms_over_budget")
        if item["triangles"] > 2500:
            failures.append(f"{item['label']}:triangles_over_budget")

    tractor = row_for("tractor")
    if not (tractor["raw_aspect"] < 1.25 and tractor["fused_aspect"] >= 1.45):
        failures.append("tractor_aspect_not_repaired")
    tower = row_for("tower")
    if not (
        as_float(tower["fused_dims_m"].get("height")) >= 20.0
        and as_float(tower["fused_dims_m"].get("length")) < as_float(tower["raw_dims_m"].get("length"))
    ):
        failures.append("tower_height_or_footprint_not_constrained")
    trailer = row_for("tractor_trailer")
    if not (
        as_float(trailer["fused_dims_m"].get("length")) >= 10.0
        and as_float(trailer["fused_dims_m"].get("width")) < as_float(trailer["raw_dims_m"].get("width"))
    ):
        failures.append("tractor_trailer_scale_not_soft_fused")
    biker = row_for("biker")
    if not (
        as_float(biker["fused_dims_m"].get("length")) < as_float(biker["raw_dims_m"].get("length"))
        and as_float(biker["fused_dims_m"].get("height")) >= 1.5
    ):
        failures.append("biker_low_confidence_scale_not_constrained")

    return {
        "status": "passed" if not failures else "failed",
        "claim_boundary": (
            "Real-input SPPA observation-fusion audit. It verifies deterministic "
            "constraint fusion over detector-derived replay dimensions; it does "
            "not prove ground-truth 3D reconstruction or detector mask correctness."
        ),
        "run_dir": str(run_dir),
        "objects_csv": str(objects_csv),
        "rows": rows,
        "failures": failures,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# SPPA Observation Fusion Audit",
        "",
        report.get("claim_boundary", ""),
        "",
        f"- Status: {report['status']}",
        f"- Run: `{report.get('run_dir')}`",
        f"- Failures: {report.get('failures') or 'none'}",
        "",
        "| Case | Raw dims LxWxH | SPPA dims LxWxH | Raw aspect | SPPA aspect | Gate | Pose used | Wall ms | Tris |",
        "|---|---:|---:|---:|---:|---|---|---:|---:|",
    ]
    for row in report.get("rows", []):
        lines.append(
            f"| {row['label']} | {dims_text(row['raw_dims_m'])} | {dims_text(row['fused_dims_m'])} | "
            f"{row['raw_aspect']:.3f} | {row['fused_aspect']:.3f} | {gate_text(row['gate'])} | "
            f"{'yes' if row['image_pose_used'] else 'no'} | {row['wall_ms']:.3f} | {row['triangles']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_tex(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "\\begin{table}[H]",
        "\\centering",
        "\\footnotesize",
        "\\setlength{\\tabcolsep}{3pt}",
        "\\renewcommand{\\arraystretch}{1.08}",
        "\\caption{Real-input SPPA observation-fusion audit. Raw replay dimensions come from YOLOE mask/bbox projection under declared assumed-flight telemetry; SPPA dimensions are the selected constraint-fused proxy dimensions.}",
        "\\label{tab:sppa-observation-fusion-audit}",
        "\\begin{tabularx}{\\linewidth}{@{}L{0.14\\linewidth}L{0.19\\linewidth}L{0.19\\linewidth}L{0.19\\linewidth}r r Y@{}}",
        "\\toprule",
        "Case & Raw L/W/H (m) & SPPA L/W/H (m) & Gate & Pose & Tris & Boundary \\\\",
        "\\midrule",
    ]
    for row in report.get("rows", []):
        boundary = "scale only" if not row["image_pose_used"] else "scale+pose"
        lines.append(
            f"{tex_escape(row['label'])} & {dims_text(row['raw_dims_m'])} & "
            f"{dims_text(row['fused_dims_m'])} & {tex_escape(gate_text(row['gate']))} & "
            f"{'yes' if row['image_pose_used'] else 'no'} & {row['triangles']} & {boundary} \\\\"
        )
    lines += [
        "\\bottomrule",
        "\\end{tabularx}",
        "\\end{table}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify SPPA real-input observation fusion.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_observation_fusion_audit.json")
    parser.add_argument("--md-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_observation_fusion_audit.md")
    parser.add_argument("--tex-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_observation_fusion_audit.tex")
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
