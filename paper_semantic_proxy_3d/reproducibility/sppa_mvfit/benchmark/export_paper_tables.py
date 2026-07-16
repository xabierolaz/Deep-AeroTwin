"""Export held-out confirmatory tables for the manuscript (from sealed results only)."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = PACKAGE_ROOT.parents[1]
RESULTS = PACKAGE_ROOT / "results" / "test"
BENCH = PAPER_ROOT / "benchmarks" / "results"

METHODS = [
    "sppa_mvfit",
    "generic_mvfit",
    "sppa_text_only",
    "nonsemantic_visual_hull",
    "ellipsoid",
    "capsule",
    "bbox",
    "billboard",
]
LABELS = {
    "sppa_mvfit": "SPPA-MVFit",
    "generic_mvfit": "Generic-MVFit",
    "sppa_text_only": "SPPA text-only",
    "nonsemantic_visual_hull": "Visual hull",
    "ellipsoid": "Ellipsoid",
    "capsule": "Capsule",
    "bbox": "Axis-aligned box",
    "billboard": "Billboard",
}


def main() -> int:
    rows = list(csv.DictReader((RESULTS / "raw_metrics.csv").open(encoding="utf-8")))
    clean = [r for r in rows if r["condition"] == "clean"]
    conf = json.loads((RESULTS / "confirmatory_summary.json").read_text(encoding="utf-8"))
    sens = json.loads((RESULTS / "resolution_sensitivity.json").read_text(encoding="utf-8"))
    BENCH.mkdir(parents=True, exist_ok=True)

    def stats(method: str) -> tuple[float, float, float, float]:
        ious = [float(r["voxel_iou"]) for r in clean if r["method"] == method]
        ms = [float(r["inference_ms"]) for r in clean if r["method"] == method]
        return float(np.mean(ious)), float(np.median(ious)), float(np.median(ms)), float(np.percentile(ms, 95))

    means = []
    means.append(r"\begin{tabular}{@{}lrrrr@{}}")
    means.append(r"\toprule")
    means.append(r"Method & Mean IoU & Median IoU & Median ms & p95 ms \\")
    means.append(r"\midrule")
    for method in METHODS:
        mu, md, tmed, tp95 = stats(method)
        means.append(f"{LABELS[method]} & {mu:.3f} & {md:.3f} & {tmed:.2f} & {tp95:.2f} \\\\")
    means.append(r"\bottomrule")
    means.append(r"\end{tabular}")
    (BENCH / "sppa_mvfit_method_means.tex").write_text("\n".join(means) + "\n", encoding="utf-8")

    primary = conf["primary"]
    h1 = []
    h1.append(r"\begin{tabular}{@{}ll@{}}")
    h1.append(r"\toprule")
    h1.append(r"Quantity & Value \\")
    h1.append(r"\midrule")
    h1.append(
        rf"Primary mean $\Delta$ IoU (SPPA-MVFit $-$ Generic-MVFit) & {primary['mean_difference']:.3f} \\"
    )
    h1.append(
        rf"Stratified bootstrap 95\% CI & [{primary['ci95_low_percentile']:.3f}, {primary['ci95_high_percentile']:.3f}] \\"
    )
    h1.append(rf"Prespecified superiority margin & +{conf['h1_superiority_margin']:.3f} \\")
    h1.append(rf"H1 decision (lower bound $>$ margin) & {'PASS' if conf['h1_pass'] else 'FAIL'} \\")
    h1.append(rf"Actors (analysis units) & {primary['actor_count']} \\")
    h1.append(rf"CSG-ID stratum mean $\Delta$ & {conf['ood_stratum_point_estimates']['csg_id']:.3f} \\")
    h1.append(
        rf"Implicit-OOD stratum mean $\Delta$ & {conf['ood_stratum_point_estimates']['implicit_ood']:.3f} \\"
    )
    h1.append(rf"Resolution sensitivity 48/64/80 & {'PASS' if sens.get('pass') else 'FAIL'} \\")
    h1.append(r"\bottomrule")
    h1.append(r"\end{tabular}")
    (BENCH / "sppa_mvfit_h1_summary.tex").write_text("\n".join(h1) + "\n", encoding="utf-8")

    sec = []
    sec.append(r"\begin{tabular}{@{}lrrr@{}}")
    sec.append(r"\toprule")
    sec.append(r"Comparator & Mean $\Delta$ IoU & 95\% CI low & 95\% CI high \\")
    sec.append(r"\midrule")
    sec.append(
        rf"Generic-MVFit (H1) & {primary['mean_difference']:.3f} & {primary['ci95_low_percentile']:.3f} & {primary['ci95_high_percentile']:.3f} \\"
    )
    for method in [
        "sppa_text_only",
        "nonsemantic_visual_hull",
        "ellipsoid",
        "capsule",
        "bbox",
        "billboard",
    ]:
        value = conf["secondary_bootstrap"][method]
        sec.append(
            rf"{LABELS[method]} & {value['mean_difference']:.3f} & {value['ci95_low_percentile']:.3f} & {value['ci95_high_percentile']:.3f} \\"
        )
    sec.append(r"\bottomrule")
    sec.append(r"\end{tabular}")
    (BENCH / "sppa_mvfit_secondary_deltas.tex").write_text("\n".join(sec) + "\n", encoding="utf-8")

    md = [
        "# SPPA-MVFit held-out confirmatory summary",
        "",
        f"- H1 pass: **{conf['h1_pass']}**",
        f"- Mean Δ IoU: {primary['mean_difference']:.4f}",
        f"- 95% CI: [{primary['ci95_low_percentile']:.4f}, {primary['ci95_high_percentile']:.4f}]",
        f"- CSG-ID / OOD: {conf['ood_stratum_point_estimates']['csg_id']:.4f} / {conf['ood_stratum_point_estimates']['implicit_ood']:.4f}",
        f"- Resolution sensitivity pass: {sens.get('pass')}",
        "",
        "| Method | Mean IoU | Med ms | p95 ms |",
        "|---|---:|---:|---:|",
    ]
    for method in METHODS:
        mu, _, tmed, tp95 = stats(method)
        md.append(f"| {LABELS[method]} | {mu:.3f} | {tmed:.2f} | {tp95:.2f} |")
    (RESULTS / "confirmatory_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": [str(BENCH / "sppa_mvfit_h1_summary.tex"), str(BENCH / "sppa_mvfit_method_means.tex"), str(BENCH / "sppa_mvfit_secondary_deltas.tex")]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
