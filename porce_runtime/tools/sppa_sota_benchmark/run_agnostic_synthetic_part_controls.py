from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw

from probe_agnostic_image_space_parts import ROOT, analyze_row, build_grid

DEFAULT_RUN_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_agnostic_shape_fitting" / "20260704_synthetic_controls"
DEFAULT_RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"
DEFAULT_FIGURE = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_agnostic_synthetic_controls_grid.png"


def rect_poly(x1: int, y1: int, x2: int, y2: int) -> list[list[float]]:
    return [[float(x1), float(y1)], [float(x2), float(y1)], [float(x2), float(y2)], [float(x1), float(y2)]]


def circle_poly(cx: float, cy: float, radius: float, points: int = 32) -> list[list[float]]:
    return [
        [round(cx + math.cos(2.0 * math.pi * idx / points) * radius, 3), round(cy + math.sin(2.0 * math.pi * idx / points) * radius, 3)]
        for idx in range(points)
    ]


def mask_area(mask: Image.Image) -> int:
    return int((np.array(mask.convert("L")) > 0).sum())


def save_case(
    run_dir: Path,
    case_id: str,
    image: Image.Image,
    mask_polygons: list[list[list[float]]],
    bbox: list[float],
    expected: dict[str, Any],
) -> dict[str, Any]:
    image_path = run_dir / f"{case_id}.png"
    image.save(image_path)
    mask_img = Image.new("L", image.size, 0)
    mask_draw = ImageDraw.Draw(mask_img)
    for polygon in mask_polygons:
        mask_draw.polygon([(x, y) for x, y in polygon], fill=255)
    used_detections = []
    for idx, polygon in enumerate(mask_polygons):
        used_detections.append(
            {
                "class_id": 1000 + idx,
                "class_name": f"withheld_synthetic_class_{idx}",
                "confidence": 1.0,
                "mask_area_px": mask_area(mask_img),
                "mask_polygon_area_px2": None,
                "mask_polygon_point_count": len(polygon),
                "mask_polygon_px": polygon,
                "mask_source": "synthetic_control_mask",
                "xyxy": bbox,
            }
        )
    return {
        "case_id": case_id,
        "image": str(image_path.relative_to(ROOT)),
        "bbox_xyxy": bbox,
        "detector_confidence": 1.0,
        "detector_label": "withheld_synthetic_label_for_audit_only",
        "reviewed_semantic_tag": "withheld_synthetic_tag_for_audit_only",
        "native_detector_mask": {
            "polygon": mask_polygons[0],
            "quality_score": 1.0,
        },
        "used_detections": used_detections,
        "expected_control": expected,
    }


def base_canvas(size: int = 256) -> Image.Image:
    return Image.new("RGB", (size, size), (104, 104, 104))


def draw_noisy_background(image: Image.Image, seed: int, strength: int = 7) -> None:
    rng = np.random.default_rng(seed)
    arr = np.array(image).astype(np.int16)
    noise = rng.normal(0, strength, arr.shape).astype(np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    image.paste(Image.fromarray(arr), (0, 0))


def make_round_pair_control(run_dir: Path) -> dict[str, Any]:
    image = base_canvas()
    draw_noisy_background(image, seed=10, strength=3)
    draw = ImageDraw.Draw(image)
    bbox = [50.0, 72.0, 206.0, 178.0]
    draw.line((78, 136, 178, 136), fill=(210, 210, 210), width=5)
    draw.line((80, 136, 130, 88), fill=(205, 205, 205), width=4)
    draw.line((130, 88, 176, 136), fill=(205, 205, 205), width=4)
    for cx in (82, 176):
        draw.ellipse((cx - 23, 136 - 23, cx + 23, 136 + 23), outline=(235, 235, 235), width=5)
    mask = [rect_poly(45, 64, 214, 188)]
    return save_case(
        run_dir,
        "synthetic_round_pair",
        image,
        mask,
        bbox,
        {
            "positive_scope": "round_part_pair_candidate",
            "min_round_pairs": 1,
            "max_validated_round_pairs": None,
            "line_coherence_required": False,
        },
    )


def make_elongated_round_pair_control(run_dir: Path) -> dict[str, Any]:
    image = base_canvas()
    draw_noisy_background(image, seed=11, strength=2)
    draw = ImageDraw.Draw(image)
    bbox = [26.0, 96.0, 230.0, 166.0]
    draw.rounded_rectangle((28, 102, 228, 158), radius=12, outline=(185, 185, 185), width=3)
    draw.line((68, 138, 188, 138), fill=(220, 220, 220), width=4)
    for cx in (66, 190):
        draw.ellipse((cx - 20, 138 - 20, cx + 20, 138 + 20), outline=(238, 238, 238), width=5)
    mask = [rect_poly(22, 88, 234, 174)]
    return save_case(
        run_dir,
        "synthetic_elongated_round_pair",
        image,
        mask,
        bbox,
        {
            "positive_scope": "round_part_pair_candidate",
            "min_round_pairs": 1,
            "max_validated_round_pairs": None,
            "line_coherence_required": False,
        },
    )


def make_line_structure_control(run_dir: Path) -> dict[str, Any]:
    image = base_canvas()
    draw_noisy_background(image, seed=12, strength=3)
    draw = ImageDraw.Draw(image)
    bbox = [98.0, 32.0, 158.0, 228.0]
    draw.line((128, 34, 104, 226), fill=(232, 232, 232), width=3)
    draw.line((128, 34, 152, 226), fill=(232, 232, 232), width=3)
    draw.line((104, 226, 152, 226), fill=(232, 232, 232), width=3)
    for y in (74, 112, 150, 188):
        half = int((y - 34) * 0.12 + 10)
        draw.line((128 - half, y, 128 + half, y), fill=(218, 218, 218), width=3)
        draw.line((128 - half, y, 128 + half - 5, y + 28), fill=(214, 214, 214), width=2)
        draw.line((128 + half, y, 128 - half + 5, y + 28), fill=(214, 214, 214), width=2)
    mask = [[[128.0, 30.0], [96.0, 228.0], [160.0, 228.0]]]
    return save_case(
        run_dir,
        "synthetic_line_structure",
        image,
        mask,
        bbox,
        {
            "positive_scope": "multi_line_structure_candidate",
            "min_round_pairs": 0,
            "max_strong_round_pairs": 0,
            "line_coherence_required": True,
        },
    )


def make_blank_mask_negative(run_dir: Path) -> dict[str, Any]:
    image = base_canvas()
    draw_noisy_background(image, seed=13, strength=2)
    bbox = [72.0, 76.0, 184.0, 182.0]
    mask = [rect_poly(70, 74, 186, 184)]
    return save_case(
        run_dir,
        "synthetic_blank_mask_negative",
        image,
        mask,
        bbox,
        {
            "forbidden_scopes": ["round_part_pair_candidate", "multi_line_structure_candidate"],
            "max_validated_round_pairs": 0,
            "line_coherence_required": False,
        },
    )


def make_texture_negative(run_dir: Path) -> dict[str, Any]:
    image = base_canvas()
    draw_noisy_background(image, seed=14, strength=4)
    arr = np.array(image).astype(np.uint8)
    rng = np.random.default_rng(15)
    x1, y1, x2, y2 = 58, 70, 202, 188
    texture = rng.normal(116, 15, (y2 - y1, x2 - x1, 3)).clip(0, 255).astype(np.uint8)
    texture = cv2.GaussianBlur(texture, (7, 7), 0)
    arr[y1:y2, x1:x2] = texture
    image = Image.fromarray(arr)
    bbox = [float(x1), float(y1), float(x2), float(y2)]
    mask = [rect_poly(x1, y1, x2, y2)]
    return save_case(
        run_dir,
        "synthetic_texture_negative",
        image,
        mask,
        bbox,
        {
            "forbidden_scopes": ["round_part_pair_candidate"],
            "max_validated_round_pairs": 0,
            "line_coherence_required": False,
        },
    )


def expected_pass(row: dict[str, Any], report: dict[str, Any]) -> tuple[bool, list[str]]:
    expected = row.get("expected_control") or {}
    cues = report.get("image_space_cues") or {}
    failures: list[str] = []
    scope = cues.get("scope")
    if expected.get("positive_scope") and scope != expected["positive_scope"]:
        failures.append(f"expected scope {expected['positive_scope']}, got {scope}")
    if scope in set(expected.get("forbidden_scopes") or []):
        failures.append(f"forbidden scope produced: {scope}")
    pair_count = int(cues.get("validated_round_part_pair_count") or 0)
    min_pairs = expected.get("min_round_pairs")
    if min_pairs is not None and pair_count < int(min_pairs):
        failures.append(f"expected at least {min_pairs} round pairs, got {pair_count}")
    max_pairs = expected.get("max_validated_round_pairs")
    if max_pairs is not None and pair_count > int(max_pairs):
        failures.append(f"expected at most {max_pairs} round pairs, got {pair_count}")
    strong_pair_count = sum(1 for pair in cues.get("validated_round_part_pairs") or [] if float(pair.get("score") or 0.0) >= 0.35)
    max_strong_pairs = expected.get("max_strong_round_pairs")
    if max_strong_pairs is not None and strong_pair_count > int(max_strong_pairs):
        failures.append(f"expected at most {max_strong_pairs} strong round pairs, got {strong_pair_count}")
    line_summary = cues.get("line_coherence") or {}
    coherent = bool(line_summary.get("coherent"))
    multi_orientation = bool(line_summary.get("multi_orientation_structure"))
    if expected.get("line_coherence_required") is True and not (coherent or multi_orientation):
        failures.append("expected coherent or multi-orientation line structure")
    return not failures, failures


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# SPPA Agnostic Synthetic Part Controls",
        "",
        result["claim_boundary"],
        "",
        f"- Status: {result['status']}",
        f"- Controls: {result['control_count']}",
        f"- Failures: {len(result['failures'])}",
        "",
        "| Case | Expected | Scope | Round pairs | Strong pairs | Line structure | Edge density | Status |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in result["rows"]:
        lines.append(
            f"| {row['case_id']} | {row['expected_summary']} | {row['scope']} | "
            f"{row['round_pairs']} | {row['strong_round_pairs']} | {str(row['line_structure']).lower()} | "
            f"{row['edge_density']:.5f} | {row['status']} |"
        )
    if result["failures"]:
        lines += ["", "## Failures", ""]
        lines.extend(f"- {failure}" for failure in result["failures"])
    lines += [
        "",
        "## Interpretation",
        "",
        "These are synthetic geometry controls, not detector benchmarks. They evaluate whether the agnostic image-space fitter responds to known primitive evidence and avoids strong part claims on blank or texture-only masks, without semantic labels.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run synthetic controls for the agnostic image-space primitive fitter.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--figure", type=Path, default=DEFAULT_FIGURE)
    args = parser.parse_args()

    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    figure = args.figure if args.figure.is_absolute() else ROOT / args.figure
    run_dir.mkdir(parents=True, exist_ok=True)
    controls = [
        make_round_pair_control(run_dir),
        make_elongated_round_pair_control(run_dir),
        make_line_structure_control(run_dir),
        make_blank_mask_negative(run_dir),
        make_texture_negative(run_dir),
    ]
    replay = {
        "schema": "SPPA-AGNOSTIC-SYNTHETIC-CONTROLS-REPLAY-0.1",
        "rows": controls,
        "claim_boundary": "Synthetic geometry controls for primitive cue extraction. Labels are audit-only.",
    }
    replay_json = run_dir / "synthetic_agnostic_controls_replay.json"
    replay_json.write_text(json.dumps(replay, indent=2, sort_keys=True), encoding="utf-8")

    rows: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    tiles: dict[str, Any] = {}
    failures: list[str] = []
    for control in controls:
        report, row_tiles = analyze_row(control)
        reports.append(report)
        tiles[str(report["case_id"])] = row_tiles
        ok, row_failures = expected_pass(control, report)
        cues = report["image_space_cues"]
        expected = control.get("expected_control") or {}
        expected_summary = expected.get("positive_scope") or "not " + ",".join(expected.get("forbidden_scopes") or [])
        rows.append(
            {
                "case_id": control["case_id"],
                "status": "pass" if ok else "fail",
                "expected_summary": expected_summary,
                "scope": cues.get("scope"),
                "grade": cues.get("grade"),
                "round_pairs": int(cues.get("validated_round_part_pair_count") or 0),
                "strong_round_pairs": sum(
                    1 for pair in cues.get("validated_round_part_pairs") or [] if float(pair.get("score") or 0.0) >= 0.35
                ),
                "round_raw": int(cues.get("round_primitive_count") or 0),
                "coherent_lines": bool((cues.get("line_coherence") or {}).get("coherent")),
                "line_structure": bool(
                    (cues.get("line_coherence") or {}).get("coherent")
                    or (cues.get("line_coherence") or {}).get("multi_orientation_structure")
                ),
                "edge_density": float(cues.get("edge_density") or 0.0),
                "failures": row_failures,
                "label_used_by_fitter": report.get("label_used_by_fitter"),
                "semantic_inputs_used_by_fitter": report.get("semantic_inputs_used_by_fitter"),
            }
        )
        failures.extend(f"{control['case_id']}: {failure}" for failure in row_failures)
    result = {
        "schema": "SPPA-AGNOSTIC-SYNTHETIC-PART-CONTROLS-0.1",
        "status": "pass" if not failures else "fail",
        "control_count": len(controls),
        "replay_json": str(replay_json),
        "figure": str(figure),
        "rows": rows,
        "failures": failures,
        "claim_boundary": (
            "Synthetic controls for the agnostic image-space primitive-cue fitter. They test primitive-cue behavior "
            "under known geometry, not detector quality or real-world semantic correctness."
        ),
    }
    build_grid(reports, tiles, figure)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / "sppa_agnostic_synthetic_part_controls.json"
    md_out = out_dir / "sppa_agnostic_synthetic_part_controls.md"
    json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_out, result)
    run_json = run_dir / "sppa_agnostic_synthetic_part_controls.json"
    run_md = run_dir / "sppa_agnostic_synthetic_part_controls.md"
    run_json.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(run_md, result)
    print(json.dumps({"status": result["status"], "json": str(json_out), "markdown": str(md_out), "failures": len(failures)}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
