from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from probe_agnostic_image_space_parts import DEFAULT_REPLAY_JSON, ROOT, analyze_row
from probe_agnostic_silhouette_parts import root_path

DEFAULT_RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"
DEFAULT_NEUTRAL_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_agnostic_shape_fitting" / "20260704_path_invariance" / "neutral_inputs"

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


def neutral_image_path(row: dict[str, Any], row_index: int, neutral_dir: Path) -> Path:
    source = root_path(row.get("image"))
    if source is None or not source.exists():
        raise FileNotFoundError(f"missing source image for {row.get('case_id')}: {row.get('image')}")
    suffix = source.suffix.lower() or ".png"
    neutral_dir.mkdir(parents=True, exist_ok=True)
    target = neutral_dir / f"object_crop_{row_index:03d}{suffix}"
    shutil.copy2(source, target)
    return target


def mutate_image_path(row: dict[str, Any], row_index: int, neutral_dir: Path) -> dict[str, Any]:
    mutated = copy.deepcopy(row)
    target = neutral_image_path(row, row_index, neutral_dir)
    mutated["image"] = target.relative_to(ROOT).as_posix()
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
        "original_image": original_row.get("image"),
        "mutated_image": mutated_row.get("image"),
        "status": "fail" if changed else "pass",
        "geometry_changed_after_path_mutation": changed,
        "baseline_hash": original_hash,
        "mutated_hash": mutated_hash,
    }


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# SPPA Agnostic Path-Invariance Verification",
        "",
        f"- Status: {result['status']}",
        f"- Replay JSON: `{result['replay_json']}`",
        f"- Neutral image dir: `{result['neutral_image_dir']}`",
        f"- Rows checked: {result['rows_checked']}",
        f"- Failures: {len(result['failures'])}",
        "",
        "| Case | Mutated image | Geometry changed | Baseline hash | Mutated hash | Status |",
        "|---|---|---:|---|---|---|",
    ]
    for row in result["rows"]:
        lines.append(
            f"| {row['case_id']} | `{row['mutated_image']}` | "
            f"{str(row['geometry_changed_after_path_mutation']).lower()} | "
            f"`{row['baseline_hash'][:12]}` | `{row['mutated_hash'][:12]}` | {row['status']} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "This verifier copies each frozen real input image to a neutral filename that does not contain object words such as cyclist, tower, tractor, or trailer. It then reruns the agnostic image-space fitter with only the image path changed. A pass means the normalized primitive report is invariant to file naming and directory naming for this replay. It does not prove primitive correctness; it guards against path/name hardcoding.",
        "",
    ]
    if result["failures"]:
        lines += ["## Failures", ""]
        lines.extend(f"- {failure}" for failure in result["failures"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify that agnostic image-space fitting is invariant to image path names.")
    parser.add_argument("--replay-json", type=Path, default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--neutral-dir", type=Path, default=DEFAULT_NEUTRAL_DIR)
    args = parser.parse_args()

    replay_json = args.replay_json if args.replay_json.is_absolute() else ROOT / args.replay_json
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    neutral_dir = args.neutral_dir if args.neutral_dir.is_absolute() else ROOT / args.neutral_dir
    data = json.loads(replay_json.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for row_index, row in enumerate(data.get("rows") or []):
        mutated = mutate_image_path(row, row_index, neutral_dir)
        comparison = compare_reports(row, mutated)
        rows.append(comparison)
        if comparison["status"] != "pass":
            failures.append(
                f"{comparison['case_id']}: geometry changed after image path mutation "
                f"to {comparison['mutated_image']}"
            )
    result = {
        "schema": "SPPA-AGNOSTIC-PATH-INVARIANCE-VERIFY-0.1",
        "status": "pass" if not failures else "fail",
        "replay_json": str(replay_json),
        "neutral_image_dir": str(neutral_dir),
        "rows_checked": len(rows),
        "rows": rows,
        "failures": failures,
        "claim_boundary": (
            "This verifies image-path and filename invariance for the agnostic image-space primitive-cue fitter on "
            "the frozen real-image replay. It guards against path/name hardcoding but does not prove primitive correctness."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / "sppa_agnostic_path_invariance.json"
    md_out = out_dir / "sppa_agnostic_path_invariance.md"
    json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_out, result)
    print(json.dumps({"status": result["status"], "json": str(json_out), "markdown": str(md_out)}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
