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

MUTATED_TOP_LEVEL_KEYS = {
    "detector_label": "synthetic_wrong_label",
    "reviewed_semantic_tag": "synthetic_wrong_tag",
    "sppa_tag": "synthetic_wrong_sppa_tag",
    "publication_label": "synthetic_wrong_publication_label",
    "normalization_rule": "synthetic_wrong_normalization_rule",
    "semantic_text_source": "synthetic_wrong_semantic_source",
    "runtime_archetype_id": "synthetic_wrong_runtime_archetype",
    "detector_model": "synthetic_wrong_detector_model",
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


def mutate_semantic_fields(row: dict[str, Any], row_index: int) -> dict[str, Any]:
    mutated = copy.deepcopy(row)
    for key, value in MUTATED_TOP_LEVEL_KEYS.items():
        if key in mutated:
            mutated[key] = f"{value}_{row_index}"
    for det_index, detection in enumerate(mutated.get("used_detections") or []):
        if "class_id" in detection:
            detection["class_id"] = 9000 + row_index * 100 + det_index
        if "class_name" in detection:
            detection["class_name"] = f"synthetic_wrong_detection_class_{row_index}_{det_index}"
    native_mask = mutated.get("native_detector_mask")
    if isinstance(native_mask, dict):
        for key in ("class_id", "class_name", "label", "tag"):
            if key in native_mask:
                native_mask[key] = f"synthetic_wrong_native_mask_{row_index}_{key}"
    return mutated


def compare_reports(original_row: dict[str, Any], mutated_row: dict[str, Any]) -> dict[str, Any]:
    original_report, _ = analyze_row(original_row)
    mutated_report, _ = analyze_row(mutated_row)
    original_normalized = scrub_audit_fields(original_report)
    mutated_normalized = scrub_audit_fields(mutated_report)
    original_hash = stable_hash(original_normalized)
    mutated_hash = stable_hash(mutated_normalized)
    changed = original_hash != mutated_hash
    return {
        "case_id": original_report.get("case_id"),
        "status": "fail" if changed else "pass",
        "geometry_changed_after_label_mutation": changed,
        "baseline_hash": original_hash,
        "mutated_hash": mutated_hash,
        "mutated_semantic_fields": sorted(MUTATED_TOP_LEVEL_KEYS),
        "mutated_detection_class_fields": True,
    }


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# SPPA Agnostic Label-Invariance Verification",
        "",
        f"- Status: {result['status']}",
        f"- Replay JSON: `{result['replay_json']}`",
        f"- Rows checked: {result['rows_checked']}",
        f"- Failures: {len(result['failures'])}",
        "",
        "| Case | Geometry changed after label mutation | Baseline hash | Mutated hash | Status |",
        "|---|---:|---|---|---|",
    ]
    for row in result["rows"]:
        lines.append(
            f"| {row['case_id']} | {str(row['geometry_changed_after_label_mutation']).lower()} | "
            f"`{row['baseline_hash'][:12]}` | `{row['mutated_hash'][:12]}` | {row['status']} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "This verifier mutates detector labels, reviewed SPPA tags, publication labels, normalization strings, detector model names, and nested detection class IDs/names. It then reruns the agnostic image-space fitter and compares normalized geometry reports after removing audit-only label fields. A pass means the geometric primitive cues are invariant to those semantic fields for the frozen real-image replay.",
        "",
    ]
    if result["failures"]:
        lines += ["## Failures", ""]
        lines.extend(f"- {failure}" for failure in result["failures"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify that agnostic image-space fitting is invariant to labels/tags.")
    parser.add_argument("--replay-json", type=Path, default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    args = parser.parse_args()

    replay_json = args.replay_json if args.replay_json.is_absolute() else ROOT / args.replay_json
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    data = json.loads(replay_json.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for row_index, row in enumerate(data.get("rows") or []):
        mutated = mutate_semantic_fields(row, row_index)
        comparison = compare_reports(row, mutated)
        rows.append(comparison)
        if comparison["status"] != "pass":
            failures.append(f"{comparison['case_id']}: geometry changed after semantic-label mutation")
    result = {
        "schema": "SPPA-AGNOSTIC-LABEL-INVARIANCE-VERIFY-0.1",
        "status": "pass" if not failures else "fail",
        "replay_json": str(replay_json),
        "rows_checked": len(rows),
        "rows": rows,
        "failures": failures,
        "claim_boundary": (
            "This verifies label/tag invariance for the agnostic image-space primitive-cue fitter on the frozen "
            "real-image replay. It does not prove correctness of the detected primitive cues."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / "sppa_agnostic_label_invariance.json"
    md_out = out_dir / "sppa_agnostic_label_invariance.md"
    json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_out, result)
    print(json.dumps({"status": result["status"], "json": str(json_out), "markdown": str(md_out)}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
