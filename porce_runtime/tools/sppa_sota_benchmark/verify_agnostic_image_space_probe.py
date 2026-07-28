from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROBE_JSON = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sppa_agnostic_image_space_parts_probe.json"
DEFAULT_RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"

ALLOWED_VISUAL_INPUTS = {
    "real_image_crop_pixels",
    "detector_bbox_xyxy",
    "unlabeled_detector_mask_polygons",
}


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def max_pair_score(row: dict[str, Any]) -> float:
    pairs = row.get("image_space_cues", {}).get("validated_round_part_pairs") or []
    if not pairs:
        return 0.0
    return max(float(pair.get("score") or 0.0) for pair in pairs)


def verify_row(row: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    case_id = row.get("case_id", "<unknown>")
    if row.get("label_used_by_fitter") is not False:
        fail(f"{case_id}: label_used_by_fitter must be false", failures)
    if row.get("semantic_inputs_used_by_fitter") not in ([], None):
        fail(f"{case_id}: semantic_inputs_used_by_fitter must be empty", failures)
    visual_inputs = set(row.get("visual_inputs_used_by_fitter") or [])
    if not visual_inputs:
        fail(f"{case_id}: visual_inputs_used_by_fitter is empty", failures)
    if not visual_inputs.issubset(ALLOWED_VISUAL_INPUTS):
        fail(f"{case_id}: unexpected visual inputs {sorted(visual_inputs - ALLOWED_VISUAL_INPUTS)}", failures)
    cues = row.get("image_space_cues") or {}
    if cues.get("label_used") is not False:
        fail(f"{case_id}: image_space_cues.label_used must be false", failures)
    if not cues.get("raw_image_pixels_used"):
        fail(f"{case_id}: raw image pixels should be declared as used", failures)
    scope = cues.get("scope")
    pair_count = int(cues.get("validated_round_part_pair_count") or 0)
    pair_score = max_pair_score(row)
    line_coherence = cues.get("line_coherence") or {}
    coherent = bool(line_coherence.get("coherent"))
    multi_orientation = bool(line_coherence.get("multi_orientation_structure"))
    if scope == "round_part_pair_candidate" and (pair_count < 1 or pair_score < 0.35):
        fail(f"{case_id}: strong round scope requires a validated pair score >= 0.35", failures)
    if scope == "weak_round_pair_candidate" and (pair_count < 1 or pair_score >= 0.35):
        fail(f"{case_id}: weak round scope requires at least one pair below 0.35", failures)
    if scope == "multi_line_structure_candidate" and not (coherent or multi_orientation):
        fail(f"{case_id}: multi-line scope requires coherent or multi-orientation line evidence", failures)
    claim_boundary = str(row.get("claim_boundary") or "") + " " + str(cues.get("claim_boundary") or "")
    if "does not use" not in claim_boundary.lower() and "label" not in claim_boundary.lower():
        fail(f"{case_id}: claim boundary does not state anti-label constraint", failures)
    return failures


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# SPPA Agnostic Image-Space Probe Verification",
        "",
        f"- Status: {result['status']}",
        f"- Rows checked: {result['rows_checked']}",
        f"- Failures: {len(result['failures'])}",
        "",
        "| Case | Scope | Pair score | Coherent lines | Multi-orientation lines | Status |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in result["rows"]:
        lines.append(
            f"| {row['case_id']} | {row['scope']} | {row['max_pair_score']:.4f} | "
            f"{str(row['coherent_lines']).lower()} | {str(row['multi_orientation_lines']).lower()} | {row['status']} |"
        )
    if result["failures"]:
        lines += ["", "## Failures", ""]
        lines.extend(f"- {item}" for item in result["failures"])
    lines += [
        "",
        "## Boundary",
        "",
        "This verification checks that the image-space fitter declares no semantic label input and that strong primitive claims are backed by their own geometry metrics.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify SPPA agnostic image-space probe anti-hardcode constraints.")
    parser.add_argument("--probe-json", type=Path, default=DEFAULT_PROBE_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    args = parser.parse_args()

    probe_json = args.probe_json if args.probe_json.is_absolute() else ROOT / args.probe_json
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    data = json.loads(probe_json.read_text(encoding="utf-8"))
    figure = Path(data.get("figure") or "")
    failures: list[str] = []
    if not figure.exists():
        failures.append(f"figure missing: {figure}")
    rows_summary: list[dict[str, Any]] = []
    for row in data.get("rows") or []:
        row_failures = verify_row(row)
        failures.extend(row_failures)
        cues = row.get("image_space_cues") or {}
        line_coherence = cues.get("line_coherence") or {}
        rows_summary.append(
            {
                "case_id": row.get("case_id"),
                "scope": cues.get("scope"),
                "max_pair_score": max_pair_score(row),
                "coherent_lines": bool(line_coherence.get("coherent")),
                "multi_orientation_lines": bool(line_coherence.get("multi_orientation_structure")),
                "status": "fail" if row_failures else "pass",
            }
        )
    result = {
        "schema": "SPPA-AGNOSTIC-IMAGE-SPACE-PROBE-VERIFY-0.1",
        "probe_json": str(probe_json),
        "figure": str(figure),
        "status": "pass" if not failures else "fail",
        "rows_checked": len(data.get("rows") or []),
        "rows": rows_summary,
        "failures": failures,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / "sppa_agnostic_image_space_parts_verify.json"
    md_out = out_dir / "sppa_agnostic_image_space_parts_verify.md"
    json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_out, result)
    print(json.dumps({"status": result["status"], "json": str(json_out), "markdown": str(md_out)}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
