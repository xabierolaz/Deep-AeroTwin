from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from probe_agnostic_image_space_parts import DEFAULT_REPLAY_JSON, ROOT, analyze_row

DEFAULT_RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"

AUDIT_ONLY_KEYS = {
    "detector_label_for_audit_only",
    "reviewed_semantic_tag_for_audit_only",
}


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def scrub_audit_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: scrub_audit_fields(item)
            for key, item in value.items()
            if key not in AUDIT_ONLY_KEYS
        }
    if isinstance(value, list):
        return [scrub_audit_fields(item) for item in value]
    return value


def detection_representation_mutations(row: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    detections = list(row.get("used_detections") or [])
    mutations: list[tuple[str, dict[str, Any]]] = []
    reversed_row = copy.deepcopy(row)
    reversed_row["used_detections"] = list(reversed(copy.deepcopy(detections)))
    mutations.append(("reversed_used_detections", reversed_row))

    duplicated_row = copy.deepcopy(row)
    duplicated_row["used_detections"] = copy.deepcopy(detections) + copy.deepcopy(detections)
    mutations.append(("duplicated_used_detections", duplicated_row))

    no_native_row = copy.deepcopy(row)
    no_native_row.pop("native_detector_mask", None)
    no_native_row["native_detector_mask_available"] = False
    mutations.append(("removed_redundant_native_mask", no_native_row))
    return mutations


def compare_reports(row: dict[str, Any]) -> dict[str, Any]:
    baseline_report, _ = analyze_row(row)
    baseline_normalized = scrub_audit_fields(baseline_report)
    baseline_hash = stable_hash(baseline_normalized)
    variants: list[dict[str, Any]] = []
    failures: list[str] = []
    for mutation_name, mutated_row in detection_representation_mutations(row):
        mutated_report, _ = analyze_row(mutated_row)
        mutated_hash = stable_hash(scrub_audit_fields(mutated_report))
        changed = baseline_hash != mutated_hash
        variants.append(
            {
                "mutation": mutation_name,
                "geometry_changed": changed,
                "baseline_hash": baseline_hash,
                "mutated_hash": mutated_hash,
                "status": "fail" if changed else "pass",
            }
        )
        if changed:
            failures.append(f"{mutation_name}: geometry changed")
    return {
        "case_id": baseline_report.get("case_id"),
        "status": "pass" if not failures else "fail",
        "baseline_hash": baseline_hash,
        "variants": variants,
        "failures": failures,
    }


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# SPPA Agnostic Detection-Representation Invariance",
        "",
        f"- Status: {result['status']}",
        f"- Replay JSON: `{result['replay_json']}`",
        f"- Rows checked: {result['rows_checked']}",
        f"- Variants checked: {result['variants_checked']}",
        f"- Failures: {len(result['failures'])}",
        "",
        "| Case | Mutation | Geometry changed | Baseline hash | Mutated hash | Status |",
        "|---|---|---:|---|---|---|",
    ]
    for row in result["rows"]:
        for variant in row["variants"]:
            lines.append(
                f"| {row['case_id']} | {variant['mutation']} | {str(variant['geometry_changed']).lower()} | "
                f"`{variant['baseline_hash'][:12]}` | `{variant['mutated_hash'][:12]}` | {variant['status']} |"
            )
    lines += [
        "",
        "## Interpretation",
        "",
        "This verifier reruns the agnostic image-space fitter after representation-only mutations of detector evidence: reversing detection order, duplicating identical detection masks, and removing a redundant native mask when used detection masks are present. A pass means the normalized primitive report depends on the unlabeled geometry, not on JSON ordering or duplicate mask entries. It does not prove primitive correctness.",
        "",
    ]
    if result["failures"]:
        lines += ["## Failures", ""]
        lines.extend(f"- {failure}" for failure in result["failures"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify invariance to detector mask ordering and duplicate representation.")
    parser.add_argument("--replay-json", type=Path, default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    args = parser.parse_args()

    replay_json = args.replay_json if args.replay_json.is_absolute() else ROOT / args.replay_json
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    data = json.loads(replay_json.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    variants_checked = 0
    for row in data.get("rows") or []:
        comparison = compare_reports(row)
        rows.append(comparison)
        variants_checked += len(comparison["variants"])
        failures.extend(f"{comparison['case_id']}: {failure}" for failure in comparison["failures"])
    result = {
        "schema": "SPPA-AGNOSTIC-DETECTION-REPRESENTATION-INVARIANCE-0.1",
        "status": "pass" if not failures else "fail",
        "replay_json": str(replay_json),
        "rows_checked": len(rows),
        "variants_checked": variants_checked,
        "rows": rows,
        "failures": failures,
        "claim_boundary": (
            "This verifies invariance to representation-only detector-mask ordering and duplicate entries on the frozen "
            "real-image replay. It guards against JSON-order/duplication bias, not primitive correctness."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / "sppa_agnostic_detection_representation_invariance.json"
    md_out = out_dir / "sppa_agnostic_detection_representation_invariance.md"
    json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_out, result)
    print(json.dumps({"status": result["status"], "json": str(json_out), "markdown": str(md_out)}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
