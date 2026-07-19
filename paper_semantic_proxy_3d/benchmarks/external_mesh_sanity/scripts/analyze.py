# external sanity check (exploratory, post-hoc)
"""Aggregate results -> external_sanity.json + external_sanity_table.tex (booktabs).

Bootstrap: 10000 resamples over cases, seed 77157 (same value as the sealed protocol).
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

METHODS = ("sppa_mvfit", "generic_mvfit", "sppa_text_only", "bbox", "ellipsoid", "capsule", "billboard", "nonsemantic_visual_hull")
BOOT_RESAMPLES = 10000
BOOT_SEED = 77157


def bootstrap_mean_ci(values: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    n = len(values)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    idx = rng.integers(0, n, size=(BOOT_RESAMPLES, n))
    means = values[idx].mean(axis=1)
    return float(values.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main() -> int:
    rows = [json.loads(line) for line in (common.RESULTS_DIR / "results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    manifest = common.load_manifest()
    selection = manifest["final_selection"]
    families = list(selection.keys())
    rng = np.random.default_rng(BOOT_SEED)

    clean = [r for r in rows if r["condition"] == "clean"]
    by_method_family: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in clean:
        by_method_family[r["method"]][r["family"]].append(r["voxel_iou"])

    summary: dict = {"label": common.LABEL, "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n_cases": len(selection and sum((v for v in selection.values()), [])), "families": {}, "methods": {}}
    # per family table
    for fam in families:
        fam_block = {"n": len(selection[fam])}
        for method in METHODS:
            vals = np.array(by_method_family[method].get(fam, []), dtype=float)
            mean, lo, hi = bootstrap_mean_ci(vals, rng)
            fam_block[method] = {"mean": mean, "ci95": [lo, hi]}
        summary["families"][fam] = fam_block
    # overall (pooled over cases)
    for method in METHODS:
        vals = np.array([r["voxel_iou"] for r in clean if r["method"] == method], dtype=float)
        mean, lo, hi = bootstrap_mean_ci(vals, rng)
        summary["methods"][method] = {"mean": mean, "ci95": [lo, hi]}
    # paired diff sppa vs generic
    sppa = {r["case_id"]: r["voxel_iou"] for r in clean if r["method"] == "sppa_mvfit"}
    gen = {r["case_id"]: r["voxel_iou"] for r in clean if r["method"] == "generic_mvfit"}
    common_ids = sorted(set(sppa) & set(gen))
    diffs = np.array([sppa[c] - gen[c] for c in common_ids], dtype=float)
    mean_d, lo_d, hi_d = bootstrap_mean_ci(diffs, rng)
    summary["paired_sppa_minus_generic"] = {"mean": mean_d, "ci95": [lo_d, hi_d], "n": len(common_ids)}
    # paired diff sppa vs visual hull
    vh = {r["case_id"]: r["voxel_iou"] for r in clean if r["method"] == "nonsemantic_visual_hull"}
    common_ids2 = sorted(set(sppa) & set(vh))
    diffs2 = np.array([sppa[c] - vh[c] for c in common_ids2], dtype=float)
    mean_d2, lo_d2, hi_d2 = bootstrap_mean_ci(diffs2, rng)
    summary["paired_sppa_minus_visual_hull"] = {"mean": mean_d2, "ci95": [lo_d2, hi_d2], "n": len(common_ids2)}
    # robustness probe
    mild = [r for r in rows if r["condition"] == "mild_morphology"]
    robust = {}
    for method in ("sppa_mvfit", "generic_mvfit"):
        clean_vals = {r["case_id"]: r["voxel_iou"] for r in clean if r["method"] == method}
        mild_vals = {r["case_id"]: r["voxel_iou"] for r in mild if r["method"] == method}
        ids = sorted(set(clean_vals) & set(mild_vals))
        deltas = np.array([mild_vals[c] - clean_vals[c] for c in ids], dtype=float)
        m_, lo_, hi_ = bootstrap_mean_ci(np.array([mild_vals[c] for c in ids]), rng)
        robust[method] = {"mild_mean": m_, "mild_ci95": [lo_, hi_], "delta_mean": float(deltas.mean()), "n": len(ids)}
    summary["robustness_mild_morphology"] = robust
    # timing
    timing = {method: float(np.mean([r["inference_ms"] for r in clean if r["method"] == method])) for method in METHODS}
    summary["inference_ms_mean"] = timing

    (common.OUTPUT_ROOT / "external_sanity.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")

    # ---------------- LaTeX booktabs table ----------------
    method_label = {
        "sppa_mvfit": "SPPA-MVFit",
        "generic_mvfit": "Generic-MVFit",
        "sppa_text_only": "SPPA text-only",
        "bbox": "AABB",
        "ellipsoid": "Ellipsoid",
        "capsule": "Capsule",
        "billboard": "Billboard",
        "nonsemantic_visual_hull": "Visual hull",
    }
    fam_label = {
        "compact_vehicle": "compact vehicle (ModelNet40 car)",
        "articulated_vehicle": "articulated vehicle (Objaverse truck/bus)",
        "quadruped": "quadruped (Objaverse horse/dog/cow)",
        "branching_vertical": "branching vertical (tree/plant)",
        "lattice_tower": "lattice tower (clock/water tower)",
        "rider_cycle": "rider cycle (bicycle/motorcycle)",
    }
    fam_short = {
        "compact_vehicle": "compact",
        "articulated_vehicle": "articulated",
        "quadruped": "quadruped",
        "branching_vertical": "branching",
        "lattice_tower": "lattice",
        "rider_cycle": "rider",
    }
    lines = []
    lines.append("% external sanity check (exploratory, post-hoc) - real meshes, clean condition")
    lines.append("% voxel IoU (64^3) mean [95% bootstrap CI], seed 77157, 10000 resamples")
    lines.append("\\begin{tabular}{l" + "r" * (len(families) + 1) + "}")
    lines.append("\\toprule")
    header = "Method & " + " & ".join(fam_short[f] for f in families) + " & All \\\\"
    lines.append(header)
    lines.append("\\midrule")
    for method in METHODS:
        cells = []
        for fam in families:
            s = summary["families"][fam][method]
            cells.append(f"{s['mean']:.3f}")
        cells.append(f"{summary['methods'][method]['mean']:.3f}")
        row = method_label[method] + " & " + " & ".join(cells) + " \\\\"
        if method == "sppa_mvfit":
            row = "\\textbf{" + method_label[method] + "} & " + " & ".join("\\textbf{%s}" % c for c in cells) + " \\\\"
        lines.append(row)
    lines.append("\\midrule")
    n_total_cases = sum(len(v) for v in selection.values())
    lines.append("\\multicolumn{8}{l}{\\footnotesize $n$ per family: " + ", ".join(f"{fam_label[f].split(' (')[0]}={len(selection[f])}" for f in families) + "; total=" + str(n_total_cases) + ".}\\\\")
    lines.append(f"\\multicolumn{{8}}{{l}}{{\\footnotesize Overall mean [CI95]: SPPA-MVFit {summary['methods']['sppa_mvfit']['mean']:.3f} [{summary['methods']['sppa_mvfit']['ci95'][0]:.3f}, {summary['methods']['sppa_mvfit']['ci95'][1]:.3f}]; Generic {summary['methods']['generic_mvfit']['mean']:.3f}; Visual hull {summary['methods']['nonsemantic_visual_hull']['mean']:.3f}.}}\\\\")
    lines.append(f"\\multicolumn{{8}}{{l}}{{\\footnotesize Paired SPPA$-$Generic: {summary['paired_sppa_minus_generic']['mean']:+.3f} [{summary['paired_sppa_minus_generic']['ci95'][0]:+.3f}, {summary['paired_sppa_minus_generic']['ci95'][1]:+.3f}].}}\\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    tex = "\n".join(lines) + "\n"
    (common.OUTPUT_ROOT / "external_sanity_table.tex").write_text(tex, encoding="utf-8")
    print(tex)
    manifest["steps"]["analyze"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    common.save_manifest(manifest)
    print("wrote external_sanity.json and external_sanity_table.tex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
