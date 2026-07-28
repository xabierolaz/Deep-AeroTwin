#!/usr/bin/env python
"""Audit the paper decision for the two SPPA truck figures."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PAPER_DIR = ROOT.parent / "papers" / "semantic_proxy_3d"
MAIN_TEX = PAPER_DIR / "semantic_proxy_3d_paper.tex"
DEFAULT_JSON_OUT = PAPER_DIR / "TRUCK_FIGURE_DECISION.json"
DEFAULT_MD_OUT = PAPER_DIR / "TRUCK_FIGURE_DECISION.md"

MAIN_FIGURE = PAPER_DIR / "figures" / "sppa_language_to_parts_to_3d_v17.png"
SUPPORTING_FIGURE = PAPER_DIR / "figures" / "sppa_truck_role_adaptation.png"
INVARIANCE_JSON = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_scale_variants" / "20260702_parametric_parts" / "parametric_part_invariance_check.json"
INVARIANCE_RERUN_JSON = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_scale_variants" / "20260703_parametric_part_invariance_after_scheduler_policy.json"
INVARIANCE_CSV = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_scale_variants" / "20260702_parametric_parts" / "truck_same_width_height_part_invariance.csv"


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def include_count(tex: str, figure_name: str) -> int:
    return len(re.findall(re.escape(figure_name), tex))


def metric_summary(path: Path) -> dict[str, Any]:
    data = load_json(path)
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "failures": data.get("failures", []),
        "cab_scale_max_abs_delta": data.get("cab_scale_max_abs_delta"),
        "tire_scale_max_abs_delta": data.get("tire_scale_max_abs_delta"),
        "cargo_length_delta_m": data.get("cargo_length_delta_m"),
        "tire_count_delta": data.get("tire_count_delta"),
        "short_tire_count": data.get("short_tire_count"),
        "long_tire_count": data.get("long_tire_count"),
    }


def metrics_pass(metrics: dict[str, Any]) -> bool:
    if not metrics["exists"] or metrics["status"] != "ok" or metrics["failures"]:
        return False
    cab_delta = metrics.get("cab_scale_max_abs_delta")
    tire_delta = metrics.get("tire_scale_max_abs_delta")
    cargo_delta = metrics.get("cargo_length_delta_m")
    tire_count_delta = metrics.get("tire_count_delta")
    if cab_delta is None or tire_delta is None or cargo_delta is None or tire_count_delta is None:
        return False
    return (
        float(cab_delta) <= 1e-6
        and float(tire_delta) <= 1e-6
        and float(cargo_delta) > 0.0
        and int(tire_count_delta) > 0
    )


def build_report() -> dict[str, Any]:
    tex = MAIN_TEX.read_text(encoding="utf-8", errors="ignore") if MAIN_TEX.exists() else ""
    main_name = "sppa_language_to_parts_to_3d_v17.png"
    supporting_name = "sppa_truck_role_adaptation.png"
    metrics = metric_summary(INVARIANCE_JSON)
    rerun_metrics = metric_summary(INVARIANCE_RERUN_JSON)
    checks = {
        "main_tex_exists": MAIN_TEX.exists(),
        "main_figure_exists": MAIN_FIGURE.exists(),
        "supporting_figure_exists": SUPPORTING_FIGURE.exists(),
        "main_figure_included_once": include_count(tex, main_name) == 1,
        "supporting_figure_not_included_in_main": include_count(tex, supporting_name) == 0,
        "main_text_mentions_artifact_log_for_component_views": "artifact log rather than used as main-paper" in tex,
        "invariance_metrics_pass": metrics_pass(metrics),
        "rerun_invariance_metrics_pass": metrics_pass(rerun_metrics),
        "invariance_csv_exists": INVARIANCE_CSV.exists(),
    }
    decision = {
        "selected_main_figure": rel(MAIN_FIGURE),
        "supporting_artifact_figure": rel(SUPPORTING_FIGURE),
        "should_fuse_figures": False,
        "recommendation": "Use the language-to-parts-to-3D figure in the main paper; keep the standalone truck role-preservation graphic as a supporting artifact.",
        "rationale": [
            "The selected main figure explains the offline-to-runtime mechanism and already includes short/long truck contrast.",
            "The standalone truck figure is clearer as a diagnostic, but it repeats the same visual claim and should not consume main-paper space.",
            "The quantitative evidence is the part-invariance check, not the standalone graphic itself.",
        ],
        "claim_boundary": "This supports role-specific parametric adaptation under synthetic dimensions. It is not proof that SPPA recovers truck morphology from UAV imagery and not an image-to-3D SOTA comparison.",
    }
    return {
        "decision": decision,
        "checks": checks,
        "metrics": metrics,
        "rerun_metrics": rerun_metrics,
        "pass": all(checks.values()),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    decision = report["decision"]
    lines = [
        "# SPPA Truck Figure Decision",
        "",
        "Generated by `tools/sppa_sota_benchmark/audit_truck_figure_decision.py`.",
        "",
        "## Verdict",
        "",
        f"- Pass: {report['pass']}",
        f"- Selected main figure: `{decision['selected_main_figure']}`",
        f"- Supporting artifact figure: `{decision['supporting_artifact_figure']}`",
        f"- Fuse figures: {decision['should_fuse_figures']}",
        f"- Recommendation: {decision['recommendation']}",
        f"- Claim boundary: {decision['claim_boundary']}",
        "",
        "## Rationale",
        "",
    ]
    lines.extend(f"- {item}" for item in decision["rationale"])
    lines += ["", "## Checks", ""]
    for key, value in report["checks"].items():
        lines.append(f"- `{key}`: {value}")
    lines += ["", "## Quantitative Evidence", ""]
    for title, metrics in [("Original check", report["metrics"]), ("After-scheduler-policy rerun", report["rerun_metrics"])]:
        lines += [
            f"### {title}",
            "",
            f"- Path: `{metrics['path']}`",
            f"- Status: {metrics['status']}",
            f"- Failures: {metrics['failures'] or 'none'}",
            f"- Cab scale max abs delta: {metrics['cab_scale_max_abs_delta']}",
            f"- Tire scale max abs delta: {metrics['tire_scale_max_abs_delta']}",
            f"- Cargo length delta: {metrics['cargo_length_delta_m']} m",
            f"- Tire count: {metrics['short_tire_count']} -> {metrics['long_tire_count']} (delta {metrics['tire_count_delta']})",
            "",
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when the truck figure decision audit fails.")
    args = parser.parse_args()

    report = build_report()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(args.md_out, report)
    print(
        json.dumps(
            {
                "json": str(args.json_out),
                "markdown": str(args.md_out),
                "pass": report["pass"],
            },
            indent=2,
        )
    )
    if args.strict and not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
