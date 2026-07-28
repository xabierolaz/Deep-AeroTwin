from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from validate_sppa_contract import validate


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = ROOT / "tools" / "sppa_sota_benchmark" / "sppa_descriptor_schema_v02.json"
DEFAULT_RUN_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260704_real_all_sppa_unified"
DEFAULT_RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"


def descriptor_rows(run_dir: Path) -> list[dict[str, Any]]:
    objects_csv = run_dir / "objects.csv"
    if not objects_csv.exists():
        return []
    rows: list[dict[str, Any]] = []
    with objects_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("event") != "SPPA_OBJECT" or row.get("model") != "sppa":
                continue
            descriptor_path = Path(str(row.get("descriptor_path") or ""))
            if not descriptor_path.is_absolute():
                descriptor_path = ROOT / descriptor_path
            rows.append({"case": row.get("label"), "descriptor_path": descriptor_path})
    return rows


def build_report(schema_path: Path, run_dir: Path) -> dict[str, Any]:
    failures: list[str] = []
    if not schema_path.exists():
        return {
            "status": "failed",
            "failures": [f"missing_schema:{schema_path}"],
            "rows": [],
        }
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for item in descriptor_rows(run_dir):
        case = str(item.get("case") or "")
        descriptor_path = item["descriptor_path"]
        if not descriptor_path.exists():
            failures.append(f"{case}:missing_descriptor:{descriptor_path}")
            continue
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        errors = validate(descriptor, schema)
        evidence_sources = (descriptor.get("evidence") or {}).get("evidence_sources") or []
        visual_metric = (descriptor.get("evidence") or {}).get("visual_metric_yaw_consistency") or {}
        pose = descriptor.get("pose") or {}
        rows.append(
            {
                "case": case,
                "descriptor_id": descriptor.get("descriptor_id"),
                "descriptor_path": str(descriptor_path),
                "descriptor_bytes": (descriptor.get("cost") or {}).get("descriptor_bytes"),
                "schema": descriptor.get("descriptor_schema"),
                "error_count": len(errors),
                "errors": errors,
                "has_visual_metric_yaw_consistency": "visual_metric_yaw_consistency" in evidence_sources,
                "visual_metric_agreement": visual_metric.get("agreement"),
                "pose_yaw_source": pose.get("yaw_source"),
                "pose_yaw_frame": pose.get("yaw_coordinate_frame"),
            }
        )
        if errors:
            failures.append(f"{case}:schema_errors:{';'.join(errors)}")
    if not rows:
        failures.append(f"missing_descriptor_rows:{run_dir}")
    return {
        "status": "passed" if not failures else "failed",
        "claim_boundary": (
            "This validates SPPA-DESC-0.2 required fields plus conditional descriptor-contract fields. "
            "When visual_metric_yaw_consistency is declared as an evidence source, the descriptor must record "
            "the projected visual-axis gate and select projected_footprint_yaw_gate as an ambiguous axial yaw "
            "in the declared replay frame."
        ),
        "schema": str(schema_path),
        "run_dir": str(run_dir),
        "rows": rows,
        "row_count": len(rows),
        "failed_count": sum(1 for row in rows if row["error_count"]),
        "visual_metric_contract_count": sum(1 for row in rows if row["has_visual_metric_yaw_consistency"]),
        "max_descriptor_bytes": max((int(row.get("descriptor_bytes") or 0) for row in rows), default=0),
        "failures": failures,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# SPPA Descriptor Contract Audit",
        "",
        report["claim_boundary"],
        "",
        f"- Status: {report['status']}",
        f"- Rows: {report['row_count']}",
        f"- Failed rows: {report['failed_count']}",
        f"- Visual-metric contract rows: {report['visual_metric_contract_count']}",
        f"- Max descriptor bytes: {report['max_descriptor_bytes']}",
        f"- Failures: {report['failures'] or 'none'}",
        "",
        "| Case | Schema errors | Visual-metric gate | Pose yaw source | Frame | Bytes |",
        "|---|---:|---|---|---|---:|",
    ]
    for row in report["rows"]:
        lines.append(
            f"| {row['case']} | {row['error_count']} | {row['visual_metric_agreement']} | "
            f"{row['pose_yaw_source']} | {row['pose_yaw_frame']} | {row['descriptor_bytes']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify SPPA descriptor schema and conditional visual-metric yaw contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_descriptor_contract_audit.json")
    parser.add_argument("--md-out", type=Path, default=DEFAULT_RESULTS_DIR / "sppa_descriptor_contract_audit.md")
    args = parser.parse_args()

    schema = args.schema if args.schema.is_absolute() else ROOT / args.schema
    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    report = build_report(schema, run_dir)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(args.md_out, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "rows": report["row_count"],
                "visual_metric_contract_rows": report["visual_metric_contract_count"],
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
