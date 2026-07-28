from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from probe_agnostic_image_space_parts import DEFAULT_REPLAY_JSON, ROOT, analyze_row
from probe_agnostic_silhouette_parts import root_path

DEFAULT_RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"
DEFAULT_PHOTOMETRIC_DIR = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_agnostic_shape_fitting"
    / "20260704_photometric_stability"
    / "variant_inputs"
)


def strong_round_pair_count(report: dict[str, Any]) -> int:
    cues = report.get("image_space_cues") or {}
    return int(cues.get("validated_strong_round_part_pair_count") or 0)


def cue_family(scope: str | None) -> str:
    if scope in {"round_part_pair_candidate", "weak_round_pair_candidate"}:
        return "round_pair"
    if scope in {"multi_line_structure_candidate", "image_edge_axis_candidate"}:
        return "linear_structure"
    if scope == "mask_envelope_only":
        return "envelope"
    return str(scope or "unknown")


def transform_image(image: Image.Image, variant: str, seed: int) -> Image.Image:
    rgb = image.convert("RGB")
    if variant == "dark_low_contrast":
        return ImageEnhance.Contrast(ImageEnhance.Brightness(rgb).enhance(0.62)).enhance(0.82)
    if variant == "bright_high_contrast":
        return ImageEnhance.Contrast(ImageEnhance.Brightness(rgb).enhance(1.28)).enhance(1.16)
    if variant == "soft_blur":
        return rgb.filter(ImageFilter.GaussianBlur(radius=1.15))
    if variant == "mild_sensor_noise":
        rng = np.random.default_rng(seed)
        arr = np.array(rgb).astype(np.int16)
        noisy = np.clip(arr + rng.normal(0.0, 5.5, arr.shape), 0, 255).astype(np.uint8)
        return Image.fromarray(noisy)
    raise ValueError(f"unknown photometric variant: {variant}")


def write_variant_image(row: dict[str, Any], row_index: int, variant: str, out_dir: Path) -> str:
    source = root_path(row.get("image"))
    if source is None or not source.exists():
        raise FileNotFoundError(f"missing source image for {row.get('case_id')}: {row.get('image')}")
    target_dir = out_dir / variant
    target_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        transformed = transform_image(image, variant, seed=20260704 + row_index * 100 + len(variant))
    suffix = source.suffix.lower() or ".png"
    target = target_dir / f"object_{row_index:03d}{suffix}"
    transformed.save(target)
    return target.relative_to(ROOT).as_posix()


def mutate_row_image(row: dict[str, Any], row_index: int, variant: str, out_dir: Path) -> dict[str, Any]:
    mutated = copy.deepcopy(row)
    mutated["case_id"] = f"{row.get('case_id')}_{variant}"
    mutated["image"] = write_variant_image(row, row_index, variant, out_dir)
    return mutated


def compare_variant(base_report: dict[str, Any], variant_report: dict[str, Any], variant: str) -> dict[str, Any]:
    failures: list[str] = []
    audit_warnings: list[str] = []
    diagnostic_notes: list[str] = []
    base_cues = base_report.get("image_space_cues") or {}
    variant_cues = variant_report.get("image_space_cues") or {}
    if base_report.get("proposal_scope") != variant_report.get("proposal_scope"):
        failures.append(
            f"{variant}: mask proposal scope changed {base_report.get('proposal_scope')} -> {variant_report.get('proposal_scope')}"
        )
    if cue_family(base_cues.get("scope")) != cue_family(variant_cues.get("scope")):
        failures.append(
            f"{variant}: image cue family changed "
            f"{cue_family(base_cues.get('scope'))} -> {cue_family(variant_cues.get('scope'))}"
        )
    elif base_cues.get("scope") != variant_cues.get("scope"):
        diagnostic_notes.append(f"{variant}: image cue confidence changed {base_cues.get('scope')} -> {variant_cues.get('scope')}")
    if strong_round_pair_count(base_report) != strong_round_pair_count(variant_report):
        diagnostic_notes.append(
            f"{variant}: strong round pair count changed "
            f"{strong_round_pair_count(base_report)} -> {strong_round_pair_count(variant_report)}"
        )

    base_edge = float(base_cues.get("edge_density") or 0.0)
    variant_edge = float(variant_cues.get("edge_density") or 0.0)
    if abs(base_edge - variant_edge) > 0.045:
        diagnostic_notes.append(f"{variant}: edge density changed {base_edge:.5f} -> {variant_edge:.5f}")
    if int(base_cues.get("line_primitive_count") or 0) != int(variant_cues.get("line_primitive_count") or 0):
        diagnostic_notes.append(
            f"{variant}: line primitive count changed "
            f"{base_cues.get('line_primitive_count')} -> {variant_cues.get('line_primitive_count')}"
        )
    if int(base_cues.get("validated_round_part_pair_count") or 0) != int(
        variant_cues.get("validated_round_part_pair_count") or 0
    ):
        diagnostic_notes.append(
            f"{variant}: all round-pair count changed "
            f"{base_cues.get('validated_round_part_pair_count')} -> {variant_cues.get('validated_round_part_pair_count')}"
        )
    return {
        "variant": variant,
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "audit_warnings": audit_warnings,
        "diagnostic_notes": diagnostic_notes,
        "baseline_scope": base_cues.get("scope"),
        "variant_scope": variant_cues.get("scope"),
        "baseline_family": cue_family(base_cues.get("scope")),
        "variant_family": cue_family(variant_cues.get("scope")),
        "baseline_strong_round_pairs": strong_round_pair_count(base_report),
        "variant_strong_round_pairs": strong_round_pair_count(variant_report),
        "baseline_edge_density": base_cues.get("edge_density"),
        "variant_edge_density": variant_cues.get("edge_density"),
        "baseline_lines": base_cues.get("line_primitive_count"),
        "variant_lines": variant_cues.get("line_primitive_count"),
    }


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# SPPA Agnostic Photometric Stability Verification",
        "",
        f"- Status: {result['status']}",
        f"- Replay JSON: `{result['replay_json']}`",
        f"- Variant image dir: `{result['variant_image_dir']}`",
        f"- Rows checked: {result['rows_checked']}",
        f"- Variants checked: {result['variants_checked']}",
        f"- Failures: {len(result['failures'])}",
        f"- Audit warnings: {len(result['audit_warnings'])}",
        f"- Diagnostic notes: {len(result.get('diagnostic_notes', []))}",
        "",
        "| Case | Variant | Status | Scope -> variant | Strong pairs -> variant | Edge density -> variant | Lines -> variant | Diagnostics |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in result["rows"]:
        for variant in row["variants"]:
            lines.append(
                f"| {row['case_id']} | {variant['variant']} | {variant['status']} | "
                f"{variant['baseline_scope']} -> {variant['variant_scope']} | "
                f"{variant['baseline_strong_round_pairs']} -> {variant['variant_strong_round_pairs']} | "
                f"{variant['baseline_edge_density']} -> {variant['variant_edge_density']} | "
                f"{variant['baseline_lines']} -> {variant['variant_lines']} | {len(variant.get('diagnostic_notes', []))} |"
            )
    lines += [
        "",
        "## Interpretation",
        "",
        "This verifier applies deterministic photometric perturbations to each real input image while keeping bbox and unlabeled detector masks unchanged. A pass means the primary agnostic primitive decision is stable under brightness, contrast, blur, and mild sensor-noise changes for the frozen replay. Audit warnings record secondary edge, line, or weak-pair drift; this is not a real-world illumination benchmark.",
        "",
    ]
    if result["failures"]:
        lines += ["## Failures", ""]
        lines.extend(f"- {failure}" for failure in result["failures"])
        lines.append("")
    if result["audit_warnings"]:
        lines += ["## Audit Warnings", ""]
        lines.extend(f"- {warning}" for warning in result["audit_warnings"][:80])
        lines.append("")
    if result.get("diagnostic_notes"):
        lines += ["## Diagnostic Notes", ""]
        lines.extend(f"- {note}" for note in result["diagnostic_notes"][:80])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify photometric stability of the agnostic image-space fitter.")
    parser.add_argument("--replay-json", type=Path, default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--variant-dir", type=Path, default=DEFAULT_PHOTOMETRIC_DIR)
    parser.add_argument(
        "--variants",
        nargs="+",
        default=["dark_low_contrast", "bright_high_contrast", "soft_blur", "mild_sensor_noise"],
    )
    args = parser.parse_args()

    replay_json = args.replay_json if args.replay_json.is_absolute() else ROOT / args.replay_json
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    variant_dir = args.variant_dir if args.variant_dir.is_absolute() else ROOT / args.variant_dir
    data = json.loads(replay_json.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    audit_warnings: list[str] = []
    diagnostic_notes: list[str] = []
    variants_checked = 0
    for row_index, row in enumerate(data.get("rows") or []):
        base_report, _ = analyze_row(row)
        variant_rows: list[dict[str, Any]] = []
        for variant in args.variants:
            variant_report, _ = analyze_row(mutate_row_image(row, row_index, variant, variant_dir))
            comparison = compare_variant(base_report, variant_report, variant)
            variant_rows.append(comparison)
            variants_checked += 1
            failures.extend(f"{base_report.get('case_id')}: {failure}" for failure in comparison["failures"])
            audit_warnings.extend(
                f"{base_report.get('case_id')}: {warning}" for warning in comparison["audit_warnings"]
            )
            diagnostic_notes.extend(
                f"{base_report.get('case_id')}: {note}" for note in comparison.get("diagnostic_notes", [])
            )
        rows.append({"case_id": base_report.get("case_id"), "variants": variant_rows})
    result = {
        "schema": "SPPA-AGNOSTIC-PHOTOMETRIC-STABILITY-VERIFY-0.1",
        "status": "pass" if not failures else "fail",
        "replay_json": str(replay_json),
        "variant_image_dir": str(variant_dir),
        "rows_checked": len(rows),
        "variants_checked": variants_checked,
        "variants": args.variants,
        "rows": rows,
        "failures": failures,
        "audit_warnings": audit_warnings,
        "diagnostic_notes": diagnostic_notes,
        "claim_boundary": (
            "This verifies primary-decision stability under deterministic photometric perturbations on the frozen "
            "real-image replay. Diagnostic notes record secondary edge, line, or weak-pair drift that is not used as a "
            "SPPA contract claim. It guards against trivial illumination dependence, but not real-world illumination coverage."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / "sppa_agnostic_photometric_stability.json"
    md_out = out_dir / "sppa_agnostic_photometric_stability.md"
    json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_out, result)
    print(json.dumps({"status": result["status"], "json": str(json_out), "markdown": str(md_out)}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
