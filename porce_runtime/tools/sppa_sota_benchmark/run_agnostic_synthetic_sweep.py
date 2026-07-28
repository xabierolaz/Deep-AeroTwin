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
from run_agnostic_synthetic_part_controls import rect_poly

DEFAULT_RUN_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_agnostic_shape_fitting" / "20260704_synthetic_sweep"
DEFAULT_RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"
DEFAULT_FIGURE = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_agnostic_synthetic_sweep_examples.png"


def base_canvas(size: int = 256, tone: int = 104) -> Image.Image:
    return Image.new("RGB", (size, size), (tone, tone, tone))


def noisy(image: Image.Image, rng: np.random.Generator, sigma: float = 3.0) -> Image.Image:
    arr = np.array(image).astype(np.int16)
    arr = np.clip(arr + rng.normal(0.0, sigma, arr.shape), 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def rotate_point(cx: float, cy: float, x: float, y: float, angle: float) -> tuple[float, float]:
    ca, sa = math.cos(angle), math.sin(angle)
    dx, dy = x - cx, y - cy
    return cx + dx * ca - dy * sa, cy + dx * sa + dy * ca


def rotated_rect_poly(cx: float, cy: float, width: float, height: float, angle_deg: float) -> list[list[float]]:
    angle = math.radians(angle_deg)
    corners = [
        (cx - width / 2, cy - height / 2),
        (cx + width / 2, cy - height / 2),
        (cx + width / 2, cy + height / 2),
        (cx - width / 2, cy + height / 2),
    ]
    return [[round(x, 3), round(y, 3)] for x, y in (rotate_point(cx, cy, x, y, angle) for x, y in corners)]


def bbox_from_poly(poly: list[list[float]], pad: float = 0.0) -> list[float]:
    xs = [float(x) for x, _ in poly]
    ys = [float(y) for _, y in poly]
    return [min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad]


def draw_rotated_line(draw: ImageDraw.ImageDraw, center: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], angle: float, fill: tuple[int, int, int], width: int) -> None:
    cx, cy = center
    x1, y1 = rotate_point(cx, cy, p1[0], p1[1], angle)
    x2, y2 = rotate_point(cx, cy, p2[0], p2[1], angle)
    draw.line((x1, y1, x2, y2), fill=fill, width=width)


def draw_rotated_circle(draw: ImageDraw.ImageDraw, center: tuple[float, float], point: tuple[float, float], angle: float, radius: float, fill: tuple[int, int, int], width: int) -> tuple[float, float]:
    cx, cy = center
    x, y = rotate_point(cx, cy, point[0], point[1], angle)
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=fill, width=width)
    return x, y


def save_case(run_dir: Path, case_id: str, image: Image.Image, polygons: list[list[list[float]]], bbox: list[float], expected: dict[str, Any]) -> dict[str, Any]:
    image_path = run_dir / f"{case_id}.png"
    image.save(image_path)
    return {
        "case_id": case_id,
        "image": str(image_path.relative_to(ROOT)),
        "bbox_xyxy": [round(float(v), 3) for v in bbox],
        "detector_confidence": 1.0,
        "detector_label": "withheld_sweep_label_for_audit_only",
        "reviewed_semantic_tag": "withheld_sweep_tag_for_audit_only",
        "native_detector_mask": {
            "polygon": polygons[0],
            "quality_score": 1.0,
        },
        "used_detections": [
            {
                "class_id": 7000 + idx,
                "class_name": f"withheld_sweep_class_{idx}",
                "confidence": 1.0,
                "mask_area_px": None,
                "mask_polygon_area_px2": None,
                "mask_polygon_point_count": len(poly),
                "mask_polygon_px": poly,
                "mask_source": "synthetic_sweep_mask",
                "xyxy": [round(float(v), 3) for v in bbox],
            }
            for idx, poly in enumerate(polygons)
        ],
        "expected_sweep": expected,
    }


def make_round_pair(run_dir: Path, idx: int, rng: np.random.Generator, elongated: bool = False) -> dict[str, Any]:
    image = noisy(base_canvas(tone=int(rng.integers(92, 116))), rng, sigma=float(rng.uniform(1.5, 4.0)))
    draw = ImageDraw.Draw(image)
    cx, cy = 128.0, 128.0
    angle_deg = float(rng.uniform(-32.0, 32.0))
    angle = math.radians(angle_deg)
    sep = float(rng.uniform(86.0, 132.0))
    radius = float(rng.uniform(15.0, 24.0))
    frame_h = float(rng.uniform(42.0, 72.0))
    body_w = sep + radius * 2.5
    body_h = max(radius * 3.0, frame_h + radius * 2.0)
    if elongated:
        body_w *= float(rng.uniform(1.08, 1.28))
        body_h *= float(rng.uniform(0.72, 0.9))
    fill = tuple(int(v) for v in [rng.integers(205, 243)] * 3)
    left = (cx - sep / 2, cy + frame_h / 4)
    right = (cx + sep / 2, cy + frame_h / 4)
    top = (cx + float(rng.uniform(-8.0, 8.0)), cy - frame_h / 2)
    draw_rotated_line(draw, (cx, cy), left, right, angle, fill, width=int(rng.integers(3, 6)))
    draw_rotated_line(draw, (cx, cy), left, top, angle, fill, width=int(rng.integers(3, 5)))
    draw_rotated_line(draw, (cx, cy), top, right, angle, fill, width=int(rng.integers(3, 5)))
    draw_rotated_circle(draw, (cx, cy), left, angle, radius, fill, width=int(rng.integers(4, 7)))
    draw_rotated_circle(draw, (cx, cy), right, angle, radius * float(rng.uniform(0.94, 1.06)), fill, width=int(rng.integers(4, 7)))
    poly = rotated_rect_poly(cx, cy, body_w, body_h, angle_deg)
    return save_case(
        run_dir,
        f"sweep_round_pair_{idx:02d}" if not elongated else f"sweep_elongated_round_pair_{idx:02d}",
        image,
        [poly],
        bbox_from_poly(poly, pad=2.0),
        {
            "expected_primary_scope": "round_part_pair_candidate",
            "expected_round_pair": True,
            "expected_line_structure": None,
            "forbidden_primary_scopes": [],
        },
    )


def make_line_structure(run_dir: Path, idx: int, rng: np.random.Generator) -> dict[str, Any]:
    image = noisy(base_canvas(tone=int(rng.integers(88, 112))), rng, sigma=float(rng.uniform(1.5, 4.0)))
    draw = ImageDraw.Draw(image)
    cx, cy = 128.0, 132.0
    angle_deg = float(rng.uniform(-18.0, 18.0))
    angle = math.radians(angle_deg)
    height = float(rng.uniform(145.0, 198.0))
    base_w = float(rng.uniform(44.0, 72.0))
    top_y = cy - height / 2
    bot_y = cy + height / 2
    fill = tuple(int(v) for v in [rng.integers(205, 242)] * 3)
    left_bot = (cx - base_w / 2, bot_y)
    right_bot = (cx + base_w / 2, bot_y)
    top = (cx + float(rng.uniform(-4.0, 4.0)), top_y)
    draw_rotated_line(draw, (cx, cy), left_bot, top, angle, fill, width=3)
    draw_rotated_line(draw, (cx, cy), right_bot, top, angle, fill, width=3)
    draw_rotated_line(draw, (cx, cy), left_bot, right_bot, angle, fill, width=3)
    levels = int(rng.integers(4, 7))
    for level in range(1, levels + 1):
        t = level / float(levels + 1)
        y = top_y * (1 - t) + bot_y * t
        half = base_w * t / 2
        left = (cx - half, y)
        right = (cx + half, y)
        draw_rotated_line(draw, (cx, cy), left, right, angle, fill, width=2)
        if level < levels:
            next_t = (level + 0.65) / float(levels + 1)
            next_y = top_y * (1 - next_t) + bot_y * next_t
            next_half = base_w * next_t / 2
            draw_rotated_line(draw, (cx, cy), left, (cx + next_half, next_y), angle, fill, width=2)
            draw_rotated_line(draw, (cx, cy), right, (cx - next_half, next_y), angle, fill, width=2)
    poly = [[round(x, 3), round(y, 3)] for x, y in [
        rotate_point(cx, cy, *top, angle),
        rotate_point(cx, cy, *right_bot, angle),
        rotate_point(cx, cy, *left_bot, angle),
    ]]
    return save_case(
        run_dir,
        f"sweep_line_structure_{idx:02d}",
        image,
        [poly],
        bbox_from_poly(poly, pad=3.0),
        {
            "expected_primary_scope": "multi_line_structure_candidate",
            "expected_round_pair": False,
            "expected_line_structure": True,
            "max_strong_round_pairs": 0,
            "forbidden_primary_scopes": ["round_part_pair_candidate"],
        },
    )


def make_blank_negative(run_dir: Path, idx: int, rng: np.random.Generator) -> dict[str, Any]:
    image = noisy(base_canvas(tone=int(rng.integers(92, 116))), rng, sigma=float(rng.uniform(1.0, 4.0)))
    w = int(rng.integers(78, 146))
    h = int(rng.integers(68, 138))
    x1 = int(rng.integers(38, 218 - w))
    y1 = int(rng.integers(38, 218 - h))
    poly = rect_poly(x1, y1, x1 + w, y1 + h)
    return save_case(
        run_dir,
        f"sweep_blank_negative_{idx:02d}",
        image,
        [poly],
        bbox_from_poly(poly),
        {
            "expected_primary_scope": None,
            "expected_round_pair": False,
            "expected_line_structure": False,
            "max_strong_round_pairs": 0,
            "forbidden_primary_scopes": ["round_part_pair_candidate", "multi_line_structure_candidate"],
        },
    )


def make_texture_negative(run_dir: Path, idx: int, rng: np.random.Generator) -> dict[str, Any]:
    image = noisy(base_canvas(tone=int(rng.integers(90, 112))), rng, sigma=float(rng.uniform(1.0, 3.0)))
    arr = np.array(image).astype(np.uint8)
    w = int(rng.integers(92, 154))
    h = int(rng.integers(76, 142))
    x1 = int(rng.integers(34, 220 - w))
    y1 = int(rng.integers(34, 220 - h))
    texture = rng.normal(114, float(rng.uniform(6.0, 18.0)), (h, w, 3)).clip(0, 255).astype(np.uint8)
    texture = cv2.GaussianBlur(texture, (7, 7), 0)
    arr[y1 : y1 + h, x1 : x1 + w] = texture
    image = Image.fromarray(arr)
    poly = rect_poly(x1, y1, x1 + w, y1 + h)
    return save_case(
        run_dir,
        f"sweep_texture_negative_{idx:02d}",
        image,
        [poly],
        bbox_from_poly(poly),
        {
            "expected_primary_scope": None,
            "expected_round_pair": False,
            "expected_line_structure": False,
            "max_strong_round_pairs": 0,
            "forbidden_primary_scopes": ["round_part_pair_candidate", "multi_line_structure_candidate"],
        },
    )


def make_single_circle_negative(run_dir: Path, idx: int, rng: np.random.Generator) -> dict[str, Any]:
    image = noisy(base_canvas(tone=int(rng.integers(92, 116))), rng, sigma=float(rng.uniform(1.0, 3.0)))
    draw = ImageDraw.Draw(image)
    cx = float(rng.uniform(82.0, 174.0))
    cy = float(rng.uniform(82.0, 174.0))
    radius = float(rng.uniform(18.0, 34.0))
    fill = tuple(int(v) for v in [rng.integers(212, 244)] * 3)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=fill, width=int(rng.integers(4, 7)))
    poly = rect_poly(int(cx - radius - 18), int(cy - radius - 18), int(cx + radius + 18), int(cy + radius + 18))
    return save_case(
        run_dir,
        f"sweep_single_circle_negative_{idx:02d}",
        image,
        [poly],
        bbox_from_poly(poly),
        {
            "expected_primary_scope": None,
            "expected_round_pair": False,
            "expected_line_structure": False,
            "max_strong_round_pairs": 0,
            "forbidden_primary_scopes": ["round_part_pair_candidate", "multi_line_structure_candidate"],
        },
    )


def expected_pass(row: dict[str, Any], report: dict[str, Any]) -> tuple[bool, list[str]]:
    expected = row.get("expected_sweep") or {}
    cues = report.get("image_space_cues") or {}
    scope = cues.get("scope")
    strong_pairs = sum(1 for pair in cues.get("validated_round_part_pairs") or [] if pair.get("strength") == "strong")
    line_summary = cues.get("line_coherence") or {}
    line_structure = bool(line_summary.get("coherent") or line_summary.get("multi_orientation_structure"))
    failures: list[str] = []
    expected_scope = expected.get("expected_primary_scope")
    if expected_scope and scope != expected_scope:
        failures.append(f"expected primary scope {expected_scope}, got {scope}")
    if scope in set(expected.get("forbidden_primary_scopes") or []):
        failures.append(f"forbidden primary scope produced: {scope}")
    if expected.get("expected_round_pair") is True and strong_pairs < 1:
        failures.append(f"expected at least one strong round pair, got {strong_pairs}")
    if expected.get("expected_round_pair") is False and strong_pairs > 0:
        failures.append(f"expected no strong round pair, got {strong_pairs}")
    if expected.get("max_strong_round_pairs") is not None and strong_pairs > int(expected["max_strong_round_pairs"]):
        failures.append(f"expected at most {expected['max_strong_round_pairs']} strong round pairs, got {strong_pairs}")
    if expected.get("expected_line_structure") is True and not line_structure:
        failures.append("expected line-structure evidence")
    if expected.get("expected_line_structure") is False and scope == "multi_line_structure_candidate":
        failures.append("unexpected primary line-structure scope")
    return not failures, failures


def precision_recall(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision = tp / float(max(1, tp + fp))
    recall = tp / float(max(1, tp + fn))
    f1 = 2.0 * precision * recall / max(1e-9, precision + recall)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    summary = result["summary"]
    lines = [
        "# SPPA Agnostic Synthetic Sweep",
        "",
        result["claim_boundary"],
        "",
        f"- Status: {result['status']}",
        f"- Cases: {summary['case_count']}",
        f"- Passes: {summary['pass_count']}",
        f"- Failures: {summary['failure_count']}",
        f"- Primary-scope accuracy: {summary['primary_scope_accuracy']:.4f}",
        f"- Strong round-pair precision/recall/F1: {summary['round_pair']['precision']:.4f} / {summary['round_pair']['recall']:.4f} / {summary['round_pair']['f1']:.4f}",
        f"- Line-structure precision/recall/F1: {summary['line_structure']['precision']:.4f} / {summary['line_structure']['recall']:.4f} / {summary['line_structure']['f1']:.4f}",
        f"- Figure: `{result['figure']}`",
        "",
        "| Family | Cases | Passes | Failures |",
        "|---|---:|---:|---:|",
    ]
    for family, item in sorted(summary["by_family"].items()):
        lines.append(f"| {family} | {item['cases']} | {item['passes']} | {item['failures']} |")
    if result["failures"]:
        lines += ["", "## Failures", ""]
        for row in result["failures"][:30]:
            lines.append(f"- {row['case_id']}: {'; '.join(row['failures'])}")
    lines += [
        "",
        "## Boundary",
        "",
        "This sweep evaluates geometry-cue behavior on deterministic synthetic images. It is stronger than hand-picked examples, but it is not a real detector benchmark and does not prove real-world universal part recovery.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a deterministic synthetic sweep for the agnostic primitive fitter.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--figure", type=Path, default=DEFAULT_FIGURE)
    parser.add_argument("--seed", type=int, default=20260704)
    parser.add_argument("--per-family", type=int, default=12)
    args = parser.parse_args()

    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    figure = args.figure if args.figure.is_absolute() else ROOT / args.figure
    run_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    controls: list[dict[str, Any]] = []
    for idx in range(args.per_family):
        controls.append(make_round_pair(run_dir, idx, rng, elongated=False))
        controls.append(make_round_pair(run_dir, idx, rng, elongated=True))
        controls.append(make_line_structure(run_dir, idx, rng))
        controls.append(make_blank_negative(run_dir, idx, rng))
        controls.append(make_texture_negative(run_dir, idx, rng))
        controls.append(make_single_circle_negative(run_dir, idx, rng))

    rows: list[dict[str, Any]] = []
    reports_for_grid: list[dict[str, Any]] = []
    tiles_for_grid: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []
    round_tp = round_fp = round_fn = 0
    line_tp = line_fp = line_fn = 0
    by_family: dict[str, dict[str, int]] = {}
    for control in controls:
        report, tiles = analyze_row(control)
        expected = control["expected_sweep"]
        cues = report["image_space_cues"]
        strong_pairs = sum(1 for pair in cues.get("validated_round_part_pairs") or [] if pair.get("strength") == "strong")
        line_summary = cues.get("line_coherence") or {}
        pred_round = strong_pairs >= 1
        pred_line = cues.get("scope") == "multi_line_structure_candidate"
        exp_round = expected.get("expected_round_pair") is True
        exp_line = expected.get("expected_line_structure") is True
        if exp_round and pred_round:
            round_tp += 1
        elif exp_round and not pred_round:
            round_fn += 1
        elif not exp_round and pred_round:
            round_fp += 1
        if exp_line and pred_line:
            line_tp += 1
        elif exp_line and not pred_line:
            line_fn += 1
        elif not exp_line and pred_line:
            line_fp += 1
        ok, row_failures = expected_pass(control, report)
        family = control["case_id"].removeprefix("sweep_").rsplit("_", 1)[0]
        family_summary = by_family.setdefault(family, {"cases": 0, "passes": 0, "failures": 0})
        family_summary["cases"] += 1
        family_summary["passes" if ok else "failures"] += 1
        row_summary = {
            "case_id": control["case_id"],
            "family": family,
            "status": "pass" if ok else "fail",
            "expected_primary_scope": expected.get("expected_primary_scope"),
            "scope": cues.get("scope"),
            "expected_round_pair": exp_round,
            "strong_round_pairs": strong_pairs,
            "expected_line_structure": exp_line,
            "line_structure_scope": pred_line,
            "line_structure_evidence": bool(line_summary.get("coherent") or line_summary.get("multi_orientation_structure")),
            "edge_density": cues.get("edge_density"),
            "label_used_by_fitter": report.get("label_used_by_fitter"),
            "semantic_inputs_used_by_fitter": report.get("semantic_inputs_used_by_fitter"),
            "failures": row_failures,
        }
        rows.append(row_summary)
        if row_failures:
            failures.append(row_summary)
        if len(reports_for_grid) < 18 and (len(reports_for_grid) < 12 or row_failures):
            reports_for_grid.append(report)
            tiles_for_grid[str(report["case_id"])] = tiles
    build_grid(reports_for_grid, tiles_for_grid, figure)
    pass_count = sum(1 for row in rows if row["status"] == "pass")
    summary = {
        "case_count": len(rows),
        "pass_count": pass_count,
        "failure_count": len(rows) - pass_count,
        "primary_scope_accuracy": round(pass_count / float(max(1, len(rows))), 4),
        "round_pair": precision_recall(round_tp, round_fp, round_fn),
        "line_structure": precision_recall(line_tp, line_fp, line_fn),
        "by_family": by_family,
    }
    result = {
        "schema": "SPPA-AGNOSTIC-SYNTHETIC-SWEEP-0.1",
        "status": "pass" if not failures else "fail",
        "seed": args.seed,
        "per_family": args.per_family,
        "summary": summary,
        "rows": rows,
        "failures": failures,
        "figure": str(figure),
        "claim_boundary": (
            "Deterministic synthetic sweep for agnostic image-space primitive cues. The fitter receives pixels, bbox, "
            "and unlabeled masks only. The sweep measures synthetic primitive behavior, not real detector quality."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / "sppa_agnostic_synthetic_sweep.json"
    md_out = out_dir / "sppa_agnostic_synthetic_sweep.md"
    json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_out, result)
    run_json = run_dir / "sppa_agnostic_synthetic_sweep.json"
    run_md = run_dir / "sppa_agnostic_synthetic_sweep.md"
    run_json.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(run_md, result)
    print(json.dumps({"status": result["status"], "json": str(json_out), "markdown": str(md_out), "cases": len(rows), "failures": len(failures)}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
