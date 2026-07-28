from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from probe_agnostic_image_space_parts import DEFAULT_REPLAY_JSON, ROOT, analyze_row

DEFAULT_RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"

IDENTITY_ONLY_KEYS = {
    "case_id",
    "detector_label_for_audit_only",
    "reviewed_semantic_tag_for_audit_only",
}


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def scrub_identity_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: scrub_identity_fields(item)
            for key, item in value.items()
            if key not in IDENTITY_ONLY_KEYS
        }
    if isinstance(value, list):
        return [scrub_identity_fields(item) for item in value]
    return value


def mutate_case_identity(row: dict[str, Any], row_index: int) -> dict[str, Any]:
    mutated = copy.deepcopy(row)
    mutated["case_id"] = f"unseen_object_crop_{row_index:03d}"
    return mutated


def compare_reports(original_row: dict[str, Any], mutated_row: dict[str, Any]) -> dict[str, Any]:
    original_report, _ = analyze_row(original_row)
    mutated_report, _ = analyze_row(mutated_row)
    original_normalized = scrub_identity_fields(original_report)
    mutated_normalized = scrub_identity_fields(mutated_report)
    original_hash = stable_hash(original_normalized)
    mutated_hash = stable_hash(mutated_normalized)
    changed = original_hash != mutated_hash
    return {
        "original_case_id": original_report.get("case_id"),
        "mutated_case_id": mutated_report.get("case_id"),
        "status": "fail" if changed else "pass",
        "geometry_changed_after_identity_mutation": changed,
        "baseline_hash": original_hash,
        "mutated_hash": mutated_hash,
    }


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# SPPA Agnostic Identity-Invariance Verification",
        "",
        f"- Status: {result['status']}",
        f"- Replay JSON: `{result['replay_json']}`",
        f"- Rows checked: {result['rows_checked']}",
        f"- Failures: {len(result['failures'])}",
        "",
        "| Original case | Mutated case | Geometry changed | Baseline hash | Mutated hash | Status |",
        "|---|---|---:|---|---|---|",
    ]
    for row in result["rows"]:
        lines.append(
            f"| {row['original_case_id']} | {row['mutated_case_id']} | "
            f"{str(row['geometry_changed_after_identity_mutation']).lower()} | "
            f"`{row['baseline_hash'][:12]}` | `{row['mutated_hash'][:12]}` | {row['status']} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "This verifier renames each frozen real-image replay row to an unseen neutral object ID and reruns the agnostic image-space fitter. A pass means the normalized geometric primitive report is invariant to the example identity after removing identity-only audit fields. It does not prove that the visible primitive cues are correct; it only guards against case-name hardcoding.",
        "",
    ]
    if result["failures"]:
        lines += ["## Failures", ""]
        lines.extend(f"- {failure}" for failure in result["failures"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify that agnostic image-space fitting is invariant to case identity.")
    parser.add_argument("--replay-json", type=Path, default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    args = parser.parse_args()

    replay_json = args.replay_json if args.replay_json.is_absolute() else ROOT / args.replay_json
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    data = json.loads(replay_json.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for row_index, row in enumerate(data.get("rows") or []):
        mutated = mutate_case_identity(row, row_index)
        comparison = compare_reports(row, mutated)
        rows.append(comparison)
        if comparison["status"] != "pass":
            failures.append(
                f"{comparison['original_case_id']}: geometry changed after case identity mutation "
                f"to {comparison['mutated_case_id']}"
            )
    result = {
        "schema": "SPPA-AGNOSTIC-IDENTITY-INVARIANCE-VERIFY-0.1",
        "status": "pass" if not failures else "fail",
        "replay_json": str(replay_json),
        "rows_checked": len(rows),
        "rows": rows,
        "failures": failures,
        "claim_boundary": (
            "This verifies case-identity invariance for the agnostic image-space primitive-cue fitter on the frozen "
            "real-image replay. It guards against example-name hardcoding but does not prove primitive correctness."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / "sppa_agnostic_identity_invariance.json"
    md_out = out_dir / "sppa_agnostic_identity_invariance.md"
    json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_out, result)
    print(json.dumps({"status": result["status"], "json": str(json_out), "markdown": str(md_out)}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
