from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260704_real_all_sppa_unified"
DEFAULT_RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"

BUDGETS = {
    "max_wall_ms_per_proxy": 10.0,
    "max_build_ms_per_proxy": 5.0,
    "max_export_ms_per_proxy": 8.0,
    "max_total_wall_ms": 50.0,
    "max_triangles_per_proxy": 2500,
    "max_vertices_per_proxy": 1500,
    "max_mesh_bytes_per_proxy": 65536,
    "max_descriptor_bytes_per_proxy": 32768,
}


def as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def read_rows(objects_csv: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with objects_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("event") != "SPPA_OBJECT":
                continue
            if row.get("model") != "sppa":
                continue
            rows.append(
                {
                    "model": "sppa",
                    "label": row.get("label"),
                    "status": row.get("status"),
                    "build_ms": as_float(row.get("build_sec")) * 1000.0,
                    "export_ms": as_float(row.get("export_sec")) * 1000.0,
                    "wall_ms": as_float(row.get("wall_sec")) * 1000.0,
                    "triangles": as_int(row.get("triangles")),
                    "vertices": as_int(row.get("vertices")),
                    "mesh_bytes": as_int(row.get("mesh_bytes")),
                    "descriptor_bytes": as_int(row.get("descriptor_bytes")),
                    "mesh_path": row.get("mesh_path"),
                    "descriptor_path": row.get("descriptor_path"),
                }
            )
    return rows


def fail_if(condition: bool, failures: list[str], message: str) -> None:
    if condition:
        failures.append(message)


def build_report(run_dir: Path) -> dict[str, Any]:
    objects_csv = run_dir / "objects.csv"
    failures: list[str] = []
    if not objects_csv.exists():
        return {
            "status": "failed",
            "run_dir": str(run_dir),
            "objects_csv": str(objects_csv),
            "budgets": BUDGETS,
            "rows": [],
            "summary": {},
            "failures": [f"missing objects.csv: {objects_csv}"],
        }
    rows = read_rows(objects_csv)
    fail_if(not rows, failures, "objects.csv contains no SPPA rows")

    total_wall_ms = sum(float(row["wall_ms"]) for row in rows)
    summary = {
        "row_count": len(rows),
        "total_wall_ms": round(total_wall_ms, 3),
        "max_wall_ms": round(max((float(row["wall_ms"]) for row in rows), default=0.0), 3),
        "max_build_ms": round(max((float(row["build_ms"]) for row in rows), default=0.0), 3),
        "max_export_ms": round(max((float(row["export_ms"]) for row in rows), default=0.0), 3),
        "max_triangles": max((int(row["triangles"]) for row in rows), default=0),
        "max_vertices": max((int(row["vertices"]) for row in rows), default=0),
        "max_mesh_bytes": max((int(row["mesh_bytes"]) for row in rows), default=0),
        "max_descriptor_bytes": max((int(row["descriptor_bytes"]) for row in rows), default=0),
        "total_triangles_all_outputs": sum(int(row["triangles"]) for row in rows),
        "total_mesh_bytes_all_outputs": sum(int(row["mesh_bytes"]) for row in rows),
        "total_descriptor_bytes_all_outputs": sum(int(row["descriptor_bytes"]) for row in rows),
    }

    for row in rows:
        prefix = f"{row['model']}/{row['label']}"
        fail_if(row["status"] != "ok", failures, f"{prefix}: status is {row['status']}")
        fail_if(float(row["wall_ms"]) > BUDGETS["max_wall_ms_per_proxy"], failures, f"{prefix}: wall_ms {row['wall_ms']:.3f} exceeds budget")
        fail_if(float(row["build_ms"]) > BUDGETS["max_build_ms_per_proxy"], failures, f"{prefix}: build_ms {row['build_ms']:.3f} exceeds budget")
        fail_if(float(row["export_ms"]) > BUDGETS["max_export_ms_per_proxy"], failures, f"{prefix}: export_ms {row['export_ms']:.3f} exceeds budget")
        fail_if(int(row["triangles"]) > BUDGETS["max_triangles_per_proxy"], failures, f"{prefix}: triangles {row['triangles']} exceeds budget")
        fail_if(int(row["vertices"]) > BUDGETS["max_vertices_per_proxy"], failures, f"{prefix}: vertices {row['vertices']} exceeds budget")
        fail_if(int(row["mesh_bytes"]) > BUDGETS["max_mesh_bytes_per_proxy"], failures, f"{prefix}: mesh_bytes {row['mesh_bytes']} exceeds budget")
        fail_if(
            int(row["descriptor_bytes"]) > BUDGETS["max_descriptor_bytes_per_proxy"],
            failures,
            f"{prefix}: descriptor_bytes {row['descriptor_bytes']} exceeds budget",
        )
    fail_if(total_wall_ms > BUDGETS["max_total_wall_ms"], failures, f"total wall_ms {total_wall_ms:.3f} exceeds budget")

    compact_rows = [
        {
            **row,
            "build_ms": round(float(row["build_ms"]), 3),
            "export_ms": round(float(row["export_ms"]), 3),
            "wall_ms": round(float(row["wall_ms"]), 3),
        }
        for row in rows
    ]
    return {
        "status": "passed" if not failures else "failed",
        "claim_boundary": (
            "SPPA runtime budget regression for the real-input single-proxy run. "
            "It guards lightweight proxy generation cost; it does not measure detector latency or Unreal frame time."
        ),
        "run_dir": str(run_dir),
        "objects_csv": str(objects_csv),
        "budgets": BUDGETS,
        "summary": summary,
        "rows": compact_rows,
        "failures": failures,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# SPPA Runtime Budget",
        "",
        report.get("claim_boundary", ""),
        "",
        f"- Status: {report['status']}",
        f"- Run: `{report['run_dir']}`",
        f"- Rows: {report.get('summary', {}).get('row_count', 0)}",
        f"- Total wall time: {report.get('summary', {}).get('total_wall_ms', 0)} ms",
        f"- Max wall time: {report.get('summary', {}).get('max_wall_ms', 0)} ms",
        f"- Max triangles: {report.get('summary', {}).get('max_triangles', 0)}",
        f"- Max OBJ bytes: {report.get('summary', {}).get('max_mesh_bytes', 0)}",
        f"- Max descriptor bytes: {report.get('summary', {}).get('max_descriptor_bytes', 0)}",
        "",
        "## Budgets",
        "",
    ]
    for key, value in report.get("budgets", {}).items():
        lines.append(f"- `{key}`: {value}")
    lines += [
        "",
        "## Rows",
        "",
        "| Model | Label | Wall ms | Build ms | Export ms | Triangles | Vertices | OBJ bytes | Descriptor bytes |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report.get("rows", []):
        lines.append(
            f"| {row['model']} | {row['label']} | {row['wall_ms']:.3f} | {row['build_ms']:.3f} | "
            f"{row['export_ms']:.3f} | {row['triangles']} | {row['vertices']} | "
            f"{row['mesh_bytes']} | {row['descriptor_bytes']} |"
        )
    lines += ["", "## Failures", ""]
    lines.extend([f"- {item}" for item in report.get("failures", [])] or ["- None"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "model",
        "label",
        "status",
        "wall_ms",
        "build_ms",
        "export_ms",
        "triangles",
        "vertices",
        "mesh_bytes",
        "descriptor_bytes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify SPPA runtime, geometry, and payload budgets.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_runtime_budget.json")
    parser.add_argument("--md-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_runtime_budget.md")
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_runtime_budget.csv")
    args = parser.parse_args()

    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    report = build_report(run_dir)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(args.md_out, report)
    write_csv(args.csv_out, report.get("rows", []))
    print(
        json.dumps(
            {
                "json": str(args.json_out),
                "markdown": str(args.md_out),
                "csv": str(args.csv_out),
                "status": report["status"],
                "summary": report.get("summary", {}),
                "failures": len(report.get("failures", [])),
            },
            indent=2,
        )
    )
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
