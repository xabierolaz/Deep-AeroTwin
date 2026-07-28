from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from probe_agnostic_image_space_parts import ROOT, analyze_row, build_grid
from run_agnostic_synthetic_sweep import (
    make_blank_negative,
    make_line_structure,
    make_round_pair,
    make_single_circle_negative,
    make_texture_negative,
    precision_recall,
    expected_pass,
)

DEFAULT_RUN_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_agnostic_shape_fitting" / "20260704_synthetic_fuzz"
DEFAULT_RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"
DEFAULT_FIGURE = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_agnostic_synthetic_fuzz_examples.png"


def build_cases(run_dir: Path, seed: int, seed_index: int, per_family: int) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    seed_dir = run_dir / f"seed_{seed_index:02d}_{seed}"
    seed_dir.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, Any]] = []
    for idx in range(per_family):
        family_cases = [
            ("round_pair", make_round_pair(seed_dir, idx, rng, elongated=False)),
            ("elongated_round_pair", make_round_pair(seed_dir, idx, rng, elongated=True)),
            ("line_structure", make_line_structure(seed_dir, idx, rng)),
            ("blank_negative", make_blank_negative(seed_dir, idx, rng)),
            ("texture_negative", make_texture_negative(seed_dir, idx, rng)),
            ("single_circle_negative", make_single_circle_negative(seed_dir, idx, rng)),
        ]
        for family, row in family_cases:
            row["case_id"] = f"fuzz_s{seed_index:02d}_{family}_{idx:03d}"
            row["expected_sweep"]["fuzz_family"] = family
            row["expected_sweep"]["fuzz_seed"] = seed
            cases.append(row)
    return cases


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pass_count = sum(1 for row in rows if row["status"] == "pass")
    by_family: dict[str, dict[str, int]] = {}
    by_seed: dict[str, dict[str, int]] = {}
    for row in rows:
        for key, value in (("by_family", row["family"]), ("by_seed", str(row["seed"]))):
            target = by_family if key == "by_family" else by_seed
            item = target.setdefault(value, {"cases": 0, "passes": 0, "failures": 0})
            item["cases"] += 1
            item["passes" if row["status"] == "pass" else "failures"] += 1
    return {
        "case_count": len(rows),
        "pass_count": pass_count,
        "failure_count": len(rows) - pass_count,
        "primary_scope_accuracy": round(pass_count / float(max(1, len(rows))), 4),
        "by_family": by_family,
        "by_seed": by_seed,
    }


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    summary = result["summary"]
    round_pair = summary["round_pair"]
    line_structure = summary["line_structure"]
    lines = [
        "# SPPA Agnostic Synthetic Fuzz",
        "",
        result["claim_boundary"],
        "",
        f"- Status: {result['status']}",
        f"- Seeds: {', '.join(str(seed) for seed in result['seeds'])}",
        f"- Cases: {summary['case_count']}",
        f"- Passes: {summary['pass_count']}",
        f"- Failures: {summary['failure_count']}",
        f"- Primary-scope accuracy: {summary['primary_scope_accuracy']:.4f}",
        f"- Strong round-pair precision/recall/F1: {round_pair['precision']:.4f} / {round_pair['recall']:.4f} / {round_pair['f1']:.4f}",
        f"- Line-structure precision/recall/F1: {line_structure['precision']:.4f} / {line_structure['recall']:.4f} / {line_structure['f1']:.4f}",
        f"- Figure: `{result['figure']}`",
        "",
        "| Family | Cases | Passes | Failures |",
        "|---|---:|---:|---:|",
    ]
    for family, item in sorted(summary["by_family"].items()):
        lines.append(f"| {family} | {item['cases']} | {item['passes']} | {item['failures']} |")
    lines += ["", "| Seed | Cases | Passes | Failures |", "|---|---:|---:|---:|"]
    for seed, item in sorted(summary["by_seed"].items()):
        lines.append(f"| {seed} | {item['cases']} | {item['passes']} | {item['failures']} |")
    if result["failures"]:
        lines += ["", "## Failures", ""]
        for row in result["failures"][:60]:
            lines.append(f"- {row['case_id']}: {'; '.join(row['failures'])}")
    lines += [
        "",
        "## Boundary",
        "",
        "This is a reproducible randomized synthetic fuzz test over generic primitive cues. It is intentionally stronger than a hand-picked visual audit, but it remains synthetic and does not prove real UAV detector performance or universal 3D reconstruction.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reproducible multi-seed fuzz tests for the agnostic primitive fitter.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--figure", type=Path, default=DEFAULT_FIGURE)
    parser.add_argument("--seeds", type=int, nargs="+", default=[20260705, 20260706, 20260707, 20260708])
    parser.add_argument("--per-family", type=int, default=10)
    args = parser.parse_args()

    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    figure = args.figure if args.figure.is_absolute() else ROOT / args.figure
    run_dir.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, Any]] = []
    for seed_index, seed in enumerate(args.seeds):
        cases.extend(build_cases(run_dir, seed, seed_index, args.per_family))

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    reports_for_grid: list[dict[str, Any]] = []
    tiles_for_grid: dict[str, Any] = {}
    round_tp = round_fp = round_fn = 0
    line_tp = line_fp = line_fn = 0
    for case in cases:
        report, tiles = analyze_row(case)
        expected = case["expected_sweep"]
        cues = report["image_space_cues"]
        strong_pairs = sum(1 for pair in cues.get("validated_round_part_pairs") or [] if pair.get("strength") == "strong")
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
        ok, row_failures = expected_pass(case, report)
        row_summary = {
            "case_id": case["case_id"],
            "seed": expected.get("fuzz_seed"),
            "family": expected.get("fuzz_family"),
            "status": "pass" if ok else "fail",
            "expected_primary_scope": expected.get("expected_primary_scope"),
            "scope": cues.get("scope"),
            "expected_round_pair": exp_round,
            "strong_round_pairs": strong_pairs,
            "expected_line_structure": exp_line,
            "line_structure_scope": pred_line,
            "edge_density": cues.get("edge_density"),
            "failures": row_failures,
        }
        rows.append(row_summary)
        if row_failures:
            failures.append(row_summary)
        if len(reports_for_grid) < 20 and (row_failures or len(reports_for_grid) < 14):
            reports_for_grid.append(report)
            tiles_for_grid[str(report["case_id"])] = tiles
    build_grid(reports_for_grid, tiles_for_grid, figure)
    summary = summarize_rows(rows)
    summary["round_pair"] = precision_recall(round_tp, round_fp, round_fn)
    summary["line_structure"] = precision_recall(line_tp, line_fp, line_fn)
    result = {
        "schema": "SPPA-AGNOSTIC-SYNTHETIC-FUZZ-0.1",
        "status": "pass" if not failures else "fail",
        "seeds": args.seeds,
        "per_family": args.per_family,
        "summary": summary,
        "rows": rows,
        "failures": failures,
        "figure": str(figure),
        "claim_boundary": (
            "Reproducible multi-seed synthetic fuzz for agnostic image-space primitive cues. The fitter receives pixels, "
            "bbox, and unlabeled masks only. This tests randomized synthetic primitive behavior, not real detector quality."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / "sppa_agnostic_synthetic_fuzz.json"
    md_out = out_dir / "sppa_agnostic_synthetic_fuzz.md"
    json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_out, result)
    run_json = run_dir / "sppa_agnostic_synthetic_fuzz.json"
    run_md = run_dir / "sppa_agnostic_synthetic_fuzz.md"
    run_json.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(run_md, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "json": str(json_out),
                "markdown": str(md_out),
                "cases": len(rows),
                "failures": len(failures),
            },
            indent=2,
        )
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
