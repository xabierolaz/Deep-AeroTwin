from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from probe_agnostic_image_space_parts import DEFAULT_REPLAY_JSON, ROOT, analyze_row
from probe_agnostic_silhouette_parts import root_path

DEFAULT_RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"
DEFAULT_MIRROR_DIR = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_agnostic_shape_fitting"
    / "20260704_mirror_equivariance"
    / "mirrored_inputs"
)


def axial_delta_deg(a: float, b: float) -> float:
    return abs((float(a) - float(b) + 90.0) % 180.0 - 90.0)


def mirror_angle_deg(angle: float) -> float:
    return (180.0 - float(angle)) % 180.0


def mirror_edge_x(x: float, width: int) -> float:
    return float(width) - float(x)


def mirror_point_x(x: float, width: int) -> float:
    return float(width - 1) - float(x)


def mirror_bbox_xyxy(bbox: list[float], width: int) -> list[float]:
    x1, y1, x2, y2 = [float(value) for value in bbox]
    return [mirror_edge_x(x2, width), y1, mirror_edge_x(x1, width), y2]


def mirror_polygon(poly: list[list[float]], width: int) -> list[list[float]]:
    return [[mirror_point_x(point[0], width), float(point[1])] for point in poly]


def write_mirrored_image(row: dict[str, Any], row_index: int, mirror_dir: Path) -> tuple[str, int, int]:
    source = root_path(row.get("image"))
    if source is None or not source.exists():
        raise FileNotFoundError(f"missing source image for {row.get('case_id')}: {row.get('image')}")
    mirror_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        rgb = image.convert("RGB")
        mirrored = ImageOps.mirror(rgb)
        width, height = rgb.size
    suffix = source.suffix.lower() or ".png"
    target = mirror_dir / f"mirrored_object_crop_{row_index:03d}{suffix}"
    mirrored.save(target)
    return target.relative_to(ROOT).as_posix(), width, height


def mutate_row_to_mirror(row: dict[str, Any], row_index: int, mirror_dir: Path) -> dict[str, Any]:
    mutated = copy.deepcopy(row)
    image_rel, width, _ = write_mirrored_image(row, row_index, mirror_dir)
    mutated["image"] = image_rel
    mutated["case_id"] = f"{row.get('case_id')}_mirror"
    if len(mutated.get("bbox_xyxy") or []) == 4:
        mutated["bbox_xyxy"] = mirror_bbox_xyxy(mutated["bbox_xyxy"], width)
    native = mutated.get("native_detector_mask")
    if isinstance(native, dict) and len(native.get("polygon") or []) >= 3:
        native["polygon"] = mirror_polygon(native["polygon"], width)
    for detection in mutated.get("used_detections") or []:
        if len(detection.get("mask_polygon_px") or []) >= 3:
            detection["mask_polygon_px"] = mirror_polygon(detection["mask_polygon_px"], width)
    silhouette = mutated.get("silhouette_proxy")
    if isinstance(silhouette, dict) and len(silhouette.get("polygon") or []) >= 3:
        silhouette["polygon"] = mirror_polygon(silhouette["polygon"], width)
    return mutated


def pair_summary(report: dict[str, Any]) -> list[dict[str, float]]:
    pairs = (report.get("image_space_cues") or {}).get("validated_round_part_pairs") or []
    summary: list[dict[str, Any]] = []
    for pair in pairs:
        summary.append(
            {
                "centers_xy": [[float(x), float(y)] for x, y in pair.get("centers_xy") or []],
                "distance_px": float(pair.get("distance_px") or 0.0),
                "radius_ratio": float(pair.get("radius_ratio") or 0.0),
                "radii_px": [float(value) for value in pair.get("radii_px") or []],
                "score": float(pair.get("score") or 0.0),
                "strength": str(pair.get("strength") or ""),
                "vertical_pair_fraction": float(pair.get("vertical_pair_fraction") or 0.0),
            }
        )
    return sorted(summary, key=lambda item: (item["distance_px"], item["radius_ratio"]))


def pair_match_cost(base_pair: dict[str, Any], mirror_pair: dict[str, Any], crop_width: float) -> float:
    base_centers = base_pair.get("centers_xy") or []
    mirror_centers = mirror_pair.get("centers_xy") or []
    if len(base_centers) != 2 or len(mirror_centers) != 2:
        return 1e9
    expected = [[float(crop_width - 1.0) - float(x), float(y)] for x, y in base_centers]
    direct = math.hypot(expected[0][0] - mirror_centers[0][0], expected[0][1] - mirror_centers[0][1]) + math.hypot(
        expected[1][0] - mirror_centers[1][0], expected[1][1] - mirror_centers[1][1]
    )
    swapped = math.hypot(expected[0][0] - mirror_centers[1][0], expected[0][1] - mirror_centers[1][1]) + math.hypot(
        expected[1][0] - mirror_centers[0][0], expected[1][1] - mirror_centers[0][1]
    )
    radius_penalty = abs(float(base_pair.get("radius_ratio") or 0.0) - float(mirror_pair.get("radius_ratio") or 0.0))
    return min(direct, swapped) + 3.0 * radius_penalty


def match_pairs_by_mirrored_geometry(
    base_pairs: list[dict[str, Any]],
    mirror_pairs: list[dict[str, Any]],
    crop_width: float,
) -> list[tuple[int, int, float]]:
    candidates: list[tuple[float, int, int]] = []
    for base_idx, base_pair in enumerate(base_pairs):
        for mirror_idx, mirror_pair in enumerate(mirror_pairs):
            candidates.append((pair_match_cost(base_pair, mirror_pair, crop_width), base_idx, mirror_idx))
    used_base: set[int] = set()
    used_mirror: set[int] = set()
    matches: list[tuple[int, int, float]] = []
    for cost, base_idx, mirror_idx in sorted(candidates):
        if base_idx in used_base or mirror_idx in used_mirror:
            continue
        used_base.add(base_idx)
        used_mirror.add(mirror_idx)
        matches.append((base_idx, mirror_idx, cost))
    return matches


def compare_numeric(name: str, base: float, mirror: float, tolerance: float, failures: list[str]) -> None:
    if abs(float(base) - float(mirror)) > tolerance:
        failures.append(f"{name}: {base} vs {mirror} exceeds tolerance {tolerance}")


def compare_reports(base_report: dict[str, Any], mirror_report: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    audit_warnings: list[str] = []
    diagnostic_notes: list[str] = []
    base_cues = base_report.get("image_space_cues") or {}
    mirror_cues = mirror_report.get("image_space_cues") or {}
    base_pca = base_report.get("pca") or {}
    mirror_pca = mirror_report.get("pca") or {}
    base_lines = base_cues.get("line_coherence") or {}
    mirror_lines = mirror_cues.get("line_coherence") or {}

    if base_report.get("proposal_scope") != mirror_report.get("proposal_scope"):
        failures.append(f"proposal_scope changed: {base_report.get('proposal_scope')} vs {mirror_report.get('proposal_scope')}")
    if base_cues.get("scope") != mirror_cues.get("scope"):
        failures.append(f"image cue scope changed: {base_cues.get('scope')} vs {mirror_cues.get('scope')}")
    if base_cues.get("grade") != mirror_cues.get("grade"):
        failures.append(f"image cue grade changed: {base_cues.get('grade')} vs {mirror_cues.get('grade')}")

    mask_area_tolerance = max(8.0, float(base_report.get("mask_area_px") or 0) * 0.0015)
    compare_numeric(
        "mask_area_px",
        base_report.get("mask_area_px") or 0,
        mirror_report.get("mask_area_px") or 0,
        mask_area_tolerance,
        failures,
    )
    compare_numeric("mask_fill_ratio", base_report.get("mask_fill_ratio") or 0, mirror_report.get("mask_fill_ratio") or 0, 0.002, failures)
    compare_numeric("pca_elongation", base_pca.get("elongation") or 0, mirror_pca.get("elongation") or 0, 0.02, failures)
    expected_mirror_pca_angle = mirror_angle_deg(float(base_pca.get("angle_deg") or 0.0))
    pca_delta = axial_delta_deg(expected_mirror_pca_angle, float(mirror_pca.get("angle_deg") or 0.0))
    if pca_delta > 2.0:
        failures.append(
            f"pca angle not mirror-equivariant: expected {expected_mirror_pca_angle:.3f}, "
            f"got {mirror_pca.get('angle_deg')} delta {pca_delta:.3f}"
        )

    compare_numeric("edge_density", base_cues.get("edge_density") or 0, mirror_cues.get("edge_density") or 0, 0.01, failures)
    if int(base_cues.get("validated_strong_round_part_pair_count") or 0) != int(
        mirror_cues.get("validated_strong_round_part_pair_count") or 0
    ):
        failures.append(
            "validated strong round pair count changed: "
            f"{base_cues.get('validated_strong_round_part_pair_count')} vs "
            f"{mirror_cues.get('validated_strong_round_part_pair_count')}"
        )
    if abs(int(base_cues.get("line_primitive_count") or 0) - int(mirror_cues.get("line_primitive_count") or 0)) > 2:
        diagnostic_notes.append(
            f"line primitive count changed too much: {base_cues.get('line_primitive_count')} vs {mirror_cues.get('line_primitive_count')}"
        )
    compare_numeric(
        "line orientation_order",
        base_lines.get("orientation_order") or 0,
        mirror_lines.get("orientation_order") or 0,
        0.08,
        diagnostic_notes,
    )
    if base_lines.get("dominant_angle_deg") is not None and mirror_lines.get("dominant_angle_deg") is not None:
        expected_line_angle = mirror_angle_deg(float(base_lines.get("dominant_angle_deg") or 0.0))
        line_delta = axial_delta_deg(expected_line_angle, float(mirror_lines.get("dominant_angle_deg") or 0.0))
        if line_delta > 10.0:
            diagnostic_notes.append(
                f"dominant line angle not mirror-equivariant: expected {expected_line_angle:.3f}, "
                f"got {mirror_lines.get('dominant_angle_deg')} delta {line_delta:.3f}"
            )

    base_pairs = pair_summary(base_report)
    mirror_pairs = pair_summary(mirror_report)
    if len(base_pairs) != len(mirror_pairs):
        diagnostic_notes.append(f"weak/audit round pair count changed: {len(base_pairs)} vs {len(mirror_pairs)}")
    crop_xyxy = base_report.get("crop_xyxy") or []
    crop_width = float(crop_xyxy[2] - crop_xyxy[0]) if len(crop_xyxy) == 4 else 0.0
    matches = match_pairs_by_mirrored_geometry(base_pairs, mirror_pairs, crop_width)
    unmatched = abs(len(base_pairs) - len(matches)) + abs(len(mirror_pairs) - len(matches))
    if unmatched:
        diagnostic_notes.append(f"unmatched weak/audit round pairs after mirror matching: {unmatched}")
    for idx, (base_idx, mirror_idx, match_cost) in enumerate(matches):
        base_pair = base_pairs[base_idx]
        mirror_pair = mirror_pairs[mirror_idx]
        if match_cost > 10.0:
            diagnostic_notes.append(f"pair[{idx}].mirror_center_match_cost {match_cost:.3f} exceeds tolerance 10.0")
        compare_numeric(f"pair[{idx}].distance_px", base_pair["distance_px"], mirror_pair["distance_px"], 4.0, diagnostic_notes)
        compare_numeric(f"pair[{idx}].radius_ratio", base_pair["radius_ratio"], mirror_pair["radius_ratio"], 0.08, diagnostic_notes)
        compare_numeric(
            f"pair[{idx}].vertical_pair_fraction",
            base_pair["vertical_pair_fraction"],
            mirror_pair["vertical_pair_fraction"],
            0.06,
            diagnostic_notes,
        )

    return {
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "audit_warnings": audit_warnings,
        "diagnostic_notes": diagnostic_notes,
        "baseline_scope": base_cues.get("scope"),
        "mirrored_scope": mirror_cues.get("scope"),
        "baseline_round_pairs": base_cues.get("validated_round_part_pair_count"),
        "mirrored_round_pairs": mirror_cues.get("validated_round_part_pair_count"),
        "baseline_strong_round_pairs": base_cues.get("validated_strong_round_part_pair_count"),
        "mirrored_strong_round_pairs": mirror_cues.get("validated_strong_round_part_pair_count"),
        "baseline_lines": base_cues.get("line_primitive_count"),
        "mirrored_lines": mirror_cues.get("line_primitive_count"),
        "pca_angle_delta_deg": round(float(pca_delta), 4),
    }


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# SPPA Agnostic Mirror-Equivariance Verification",
        "",
        f"- Status: {result['status']}",
        f"- Replay JSON: `{result['replay_json']}`",
        f"- Mirrored image dir: `{result['mirror_image_dir']}`",
        f"- Rows checked: {result['rows_checked']}",
        f"- Failures: {len(result['failures'])}",
        f"- Audit warnings: {len(result['audit_warnings'])}",
        f"- Diagnostic notes: {len(result.get('diagnostic_notes', []))}",
        "",
        "| Case | Status | Scope -> mirror | Strong pairs -> mirror | All pairs -> mirror | Lines -> mirror | PCA mirror delta deg |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for row in result["rows"]:
        lines.append(
            f"| {row['case_id']} | {row['status']} | {row['baseline_scope']} -> {row['mirrored_scope']} | "
            f"{row['baseline_strong_round_pairs']} -> {row['mirrored_strong_round_pairs']} | "
            f"{row['baseline_round_pairs']} -> {row['mirrored_round_pairs']} | "
            f"{row['baseline_lines']} -> {row['mirrored_lines']} | {row['pca_angle_delta_deg']} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "This verifier mirrors each real image and mirrors its bbox and unlabeled detector polygons together, then reruns the same agnostic fitter. It checks that normalized geometry is equivariant to this image-space transformation: scopes should stay stable, mask mass and PCA should mirror, round-pair counts should remain stable, and line evidence should remain close within deterministic computer-vision tolerances. A pass guards against left/right orientation shortcuts; it is not a proof of universal primitive correctness.",
        "",
    ]
    if result["failures"]:
        lines += ["## Failures", ""]
        lines.extend(f"- {failure}" for failure in result["failures"])
        lines.append("")
    if result["audit_warnings"]:
        lines += ["## Audit Warnings", ""]
        lines.extend(f"- {warning}" for warning in result["audit_warnings"])
        lines.append("")
    if result.get("diagnostic_notes"):
        lines += ["## Diagnostic Notes", ""]
        lines.extend(f"- {note}" for note in result["diagnostic_notes"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify mirror equivariance of the agnostic image-space fitter.")
    parser.add_argument("--replay-json", type=Path, default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--mirror-dir", type=Path, default=DEFAULT_MIRROR_DIR)
    args = parser.parse_args()

    replay_json = args.replay_json if args.replay_json.is_absolute() else ROOT / args.replay_json
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    mirror_dir = args.mirror_dir if args.mirror_dir.is_absolute() else ROOT / args.mirror_dir
    data = json.loads(replay_json.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    audit_warnings: list[str] = []
    diagnostic_notes: list[str] = []
    for row_index, row in enumerate(data.get("rows") or []):
        base_report, _ = analyze_row(row)
        mirrored_row = mutate_row_to_mirror(row, row_index, mirror_dir)
        mirror_report, _ = analyze_row(mirrored_row)
        comparison = compare_reports(base_report, mirror_report)
        comparison["case_id"] = base_report.get("case_id")
        comparison["mirrored_case_id"] = mirror_report.get("case_id")
        comparison["mirrored_image"] = mirrored_row.get("image")
        rows.append(comparison)
        audit_warnings.extend(f"{comparison['case_id']}: {warning}" for warning in comparison["audit_warnings"])
        diagnostic_notes.extend(f"{comparison['case_id']}: {note}" for note in comparison.get("diagnostic_notes", []))
        if comparison["status"] != "pass":
            failures.extend(f"{comparison['case_id']}: {failure}" for failure in comparison["failures"])
    result = {
        "schema": "SPPA-AGNOSTIC-MIRROR-EQUIVARIANCE-VERIFY-0.1",
        "status": "pass" if not failures else "fail",
        "replay_json": str(replay_json),
        "mirror_image_dir": str(mirror_dir),
        "rows_checked": len(rows),
        "rows": rows,
        "failures": failures,
        "audit_warnings": audit_warnings,
        "diagnostic_notes": diagnostic_notes,
        "claim_boundary": (
            "This verifies horizontal mirror equivariance for the agnostic image-space primitive-cue fitter on the "
            "frozen real-image replay. The pass/fail status covers primary geometry decisions; diagnostic notes record "
            "secondary Hough-line or weak-pair drift that is not used as a SPPA contract claim. It guards against "
            "left/right orientation shortcuts, but not primitive correctness."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / "sppa_agnostic_mirror_equivariance.json"
    md_out = out_dir / "sppa_agnostic_mirror_equivariance.md"
    json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_out, result)
    print(json.dumps({"status": result["status"], "json": str(json_out), "markdown": str(md_out)}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
