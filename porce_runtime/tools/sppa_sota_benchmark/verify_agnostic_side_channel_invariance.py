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
DEFAULT_NEUTRAL_DIR = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_agnostic_shape_fitting"
    / "20260704_side_channel_invariance"
    / "neutral_inputs"
)

IDENTITY_AND_AUDIT_KEYS = {
    "case_id",
    "detector_label_for_audit_only",
    "reviewed_semantic_tag_for_audit_only",
}

SEMANTIC_TOP_LEVEL_MUTATIONS = {
    "detector_label": "adversarial_semantic_noise",
    "reviewed_semantic_tag": "adversarial_semantic_noise",
    "sppa_tag": "adversarial_semantic_noise",
    "publication_label": "adversarial_semantic_noise",
    "normalization_rule": "adversarial_semantic_noise",
    "semantic_text_source": "adversarial_semantic_noise",
    "runtime_archetype_id": "adversarial_semantic_noise",
    "detector_runtime_archetype_id": "adversarial_semantic_noise",
    "detector_model": "adversarial_semantic_noise",
    "detector_source": "adversarial_semantic_noise",
    "claim_status": "adversarial_semantic_noise",
}


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def scrub_identity_and_audit_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: scrub_identity_and_audit_fields(item)
            for key, item in value.items()
            if key not in IDENTITY_AND_AUDIT_KEYS
        }
    if isinstance(value, list):
        return [scrub_identity_and_audit_fields(item) for item in value]
    return value


def copy_to_neutral_path(row: dict[str, Any], row_index: int, neutral_dir: Path) -> str:
    source = root_path(row.get("image"))
    if source is None or not source.exists():
        raise FileNotFoundError(f"missing source image for {row.get('case_id')}: {row.get('image')}")
    neutral_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower() or ".png"
    target = neutral_dir / f"object_crop_{row_index:03d}{suffix}"
    shutil.copy2(source, target)
    return target.relative_to(ROOT).as_posix()


def mutate_side_channels(row: dict[str, Any], row_index: int, neutral_dir: Path) -> dict[str, Any]:
    mutated = copy.deepcopy(row)
    mutated["case_id"] = f"anonymous_detected_object_{row_index:03d}"
    mutated["image"] = copy_to_neutral_path(row, row_index, neutral_dir)
    for key, value in SEMANTIC_TOP_LEVEL_MUTATIONS.items():
        if key in mutated:
            mutated[key] = f"{value}_{row_index}_{key}"

    detections = copy.deepcopy(mutated.get("used_detections") or [])
    for det_index, detection in enumerate(detections):
        if "class_id" in detection:
            detection["class_id"] = 880000 + row_index * 100 + det_index
        if "class_name" in detection:
            detection["class_name"] = f"adversarial_detection_class_{row_index}_{det_index}"
        for key in ("label", "tag", "semantic_tag", "archetype_id"):
            if key in detection:
                detection[key] = f"adversarial_detection_{key}_{row_index}_{det_index}"
    mutated["used_detections"] = list(reversed(detections)) + list(reversed(copy.deepcopy(detections)))

    native_mask = mutated.get("native_detector_mask")
    if isinstance(native_mask, dict):
        for key in ("class_id", "class_name", "label", "tag", "semantic_tag", "archetype_id"):
            if key in native_mask:
                native_mask[key] = f"adversarial_native_mask_{row_index}_{key}"
    mutated.pop("native_detector_mask", None)
    mutated["native_detector_mask_available"] = False
    return mutated


def compare_reports(row: dict[str, Any], row_index: int, neutral_dir: Path) -> dict[str, Any]:
    baseline_report, _ = analyze_row(row)
    mutated_row = mutate_side_channels(row, row_index, neutral_dir)
    mutated_report, _ = analyze_row(mutated_row)
    baseline_hash = stable_hash(scrub_identity_and_audit_fields(baseline_report))
    mutated_hash = stable_hash(scrub_identity_and_audit_fields(mutated_report))
    changed = baseline_hash != mutated_hash
    return {
        "original_case_id": baseline_report.get("case_id"),
        "mutated_case_id": mutated_report.get("case_id"),
        "mutated_image": mutated_row.get("image"),
        "status": "fail" if changed else "pass",
        "geometry_changed_after_side_channel_mutation": changed,
        "baseline_hash": baseline_hash,
        "mutated_hash": mutated_hash,
        "mutations": [
            "neutral_case_id",
            "neutral_image_path",
            "adversarial_semantic_fields",
            "adversarial_detection_class_fields",
            "reversed_and_duplicated_used_detections",
            "removed_redundant_native_mask",
        ],
    }


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# SPPA Agnostic Side-Channel Invariance Verification",
        "",
        f"- Status: {result['status']}",
        f"- Replay JSON: `{result['replay_json']}`",
        f"- Neutral image dir: `{result['neutral_image_dir']}`",
        f"- Rows checked: {result['rows_checked']}",
        f"- Failures: {len(result['failures'])}",
        "",
        "| Original case | Mutated case | Mutated image | Geometry changed | Baseline hash | Mutated hash | Status |",
        "|---|---|---|---:|---|---|---|",
    ]
    for row in result["rows"]:
        lines.append(
            f"| {row['original_case_id']} | {row['mutated_case_id']} | `{row['mutated_image']}` | "
            f"{str(row['geometry_changed_after_side_channel_mutation']).lower()} | "
            f"`{row['baseline_hash'][:12]}` | `{row['mutated_hash'][:12]}` | {row['status']} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "This verifier combines the side-channel mutations that would most easily hide object-specific shortcuts: neutral case IDs, neutral image paths, adversarial labels/tags/model strings, adversarial nested detector class fields, reversed and duplicated detector masks, and removal of a redundant native mask. A pass means the normalized agnostic primitive report is stable under this combined non-geometric mutation for every frozen real replay row. It does not prove primitive correctness or universal 3D reconstruction.",
        "",
    ]
    if result["failures"]:
        lines += ["## Failures", ""]
        lines.extend(f"- {failure}" for failure in result["failures"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify agnostic invariance to combined non-geometric side channels.")
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
        comparison = compare_reports(row, row_index, neutral_dir)
        rows.append(comparison)
        if comparison["status"] != "pass":
            failures.append(
                f"{comparison['original_case_id']}: geometry changed after combined side-channel mutation"
            )
    result = {
        "schema": "SPPA-AGNOSTIC-SIDE-CHANNEL-INVARIANCE-VERIFY-0.1",
        "status": "pass" if not failures else "fail",
        "replay_json": str(replay_json),
        "neutral_image_dir": str(neutral_dir),
        "rows_checked": len(rows),
        "rows": rows,
        "failures": failures,
        "claim_boundary": (
            "This verifies combined non-geometric side-channel invariance for the agnostic image-space primitive-cue "
            "fitter on the frozen real-image replay. It guards against label, identity, filename, detector-class, "
            "detector-order, duplicate-mask, and redundant-native-mask shortcuts, but not primitive correctness."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / "sppa_agnostic_side_channel_invariance.json"
    md_out = out_dir / "sppa_agnostic_side_channel_invariance.md"
    json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_out, result)
    print(json.dumps({"status": result["status"], "json": str(json_out), "markdown": str(md_out)}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
