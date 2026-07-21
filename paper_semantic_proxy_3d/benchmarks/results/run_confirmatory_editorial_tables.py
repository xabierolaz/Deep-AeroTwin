"""Confirmatory editorial tables (JGSA tribunal request): family x stratum and
paired deltas vs baselines.

READ-ONLY inputs (nothing sealed is modified):
  * reproducibility/sppa_mvfit/results/test/confirmatory_summary.json  (sealed)
  * reproducibility/sppa_mvfit/results/test/raw_metrics.csv            (sealed)
  * benchmarks/mvfit_posthoc_analysis/t5_drop_one_family/drop_one_family.json
    (existing post-hoc artifact; NOT part of the sealed confirmatory package)

What is sealed vs what is new:
  * SEALED: primary aggregate 0.190 [0.181, 0.199]; all per-family x stratum
    POINT estimates; all six secondary paired deltas + CIs; Holm p's.
  * NEW (this script, post-hoc): per-cell 95% CIs, because the sealed summary
    stores only stratum point estimates. Convention mirrors the sealed
    bootstrap (benchmark/analyze_test.py): resample actors within the cell
    with replacement (n=20 per cell), 10,000 resamples, seed 77157,
    percentile 95% CI, clean condition, voxel_iou, paired sppa - generic.
  * Drop-one-family range [0.152, 0.214]: taken from the EXISTING post-hoc
    artifact t5_drop_one_family (exploratory, not sealed confirmatory).

Writes NEW files only (in benchmarks/results/):
  per_family_stratum_table.tex, per_family_stratum_note.md,
  per_family_stratum_ci.json,
  paired_deltas_table.tex, paired_deltas_note.md

Run:  python run_confirmatory_editorial_tables.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent  # benchmarks/results
REPRO = ROOT.parents[1] / "reproducibility" / "sppa_mvfit" / "results" / "test"
SUMMARY = REPRO / "confirmatory_summary.json"
RAW = REPRO / "raw_metrics.csv"
DROP1 = ROOT.parent / "mvfit_posthoc_analysis" / "t5_drop_one_family" / "drop_one_family.json"

SEED = 77157
N_BOOT = 10_000
FAMILIES = ["articulated_vehicle", "branching_vertical", "compact_vehicle",
            "lattice_tower", "quadruped", "rider_cycle"]
STRATA = ["csg_id", "implicit_ood"]
METHOD_ORDER = ["sppa_mvfit", "nonsemantic_visual_hull", "sppa_text_only",
                "generic_mvfit", "ellipsoid", "capsule", "bbox", "billboard"]


def load_clean() -> dict:
    """case_id -> {family, stratum, method -> voxel_iou} for the clean condition."""
    cases: dict[str, dict] = {}
    with RAW.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["condition"] != "clean":
                continue
            c = cases.setdefault(row["case_id"], {"family": row["family"],
                                                  "stratum": row["stratum"], "iou": {}})
            c["iou"][row["method"]] = float(row["voxel_iou"])
    return cases


def main() -> None:
    summary = json.load(SUMMARY.open(encoding="utf-8"))
    drop1 = json.load(DROP1.open(encoding="utf-8"))
    cases = load_clean()
    assert len(cases) == 240, f"expected 240 clean cases, got {len(cases)}"

    # ---- per family x stratum paired deltas (sppa - generic) ------------------
    cells: dict[tuple[str, str], np.ndarray] = {}
    for (fam, strat) in [(f, s) for f in FAMILIES for s in STRATA]:
        deltas = [c["iou"]["sppa_mvfit"] - c["iou"]["generic_mvfit"]
                  for c in cases.values() if c["family"] == fam and c["stratum"] == strat]
        assert len(deltas) == 20, f"cell {fam}|{strat} has {len(deltas)} actors"
        cells[(fam, strat)] = np.array(deltas)

    # verify point estimates against the sealed summary -------------------------
    verification = {}
    sealed_cells = summary["primary"]["stratum_point_estimates"]
    for (fam, strat), arr in cells.items():
        key = f"{fam}|{strat}"
        new = float(arr.mean())
        verification[key] = {"new": new, "sealed": sealed_cells[key],
                             "match": abs(new - sealed_cells[key]) < 1e-12}

    # NEW per-cell bootstrap CIs -------------------------------------------------
    cell_ci = {}
    for (fam, strat), arr in cells.items():
        rng = np.random.default_rng(SEED)
        boot = np.empty(N_BOOT)
        for b in range(N_BOOT):
            boot[b] = rng.choice(arr, size=len(arr), replace=True).mean()
        cell_ci[(fam, strat)] = [float(np.percentile(boot, 2.5)),
                                 float(np.percentile(boot, 97.5))]

    # ---- method means / medians (clean, voxel_iou) -----------------------------
    method_stats = {}
    for m in METHOD_ORDER:
        v = np.array([c["iou"][m] for c in cases.values()])
        method_stats[m] = {"mean": float(v.mean()), "median": float(np.median(v)), "n": int(v.size)}

    # ---- sealed paired deltas vs every baseline --------------------------------
    sealed_deltas = {"generic_mvfit": {
        "mean_difference": summary["primary"]["mean_difference"],
        "ci95_low_percentile": summary["primary"]["ci95_low_percentile"],
        "ci95_high_percentile": summary["primary"]["ci95_high_percentile"],
        "kind": "primary (H1 endpoint)"}}
    for m, blk in summary["secondary_bootstrap"].items():
        sealed_deltas[m] = {"mean_difference": blk["mean_difference"],
                            "ci95_low_percentile": blk["ci95_low_percentile"],
                            "ci95_high_percentile": blk["ci95_high_percentile"],
                            "kind": "secondary (Holm-adjusted)"}

    # ---- editor-number checks ----------------------------------------------------
    editor_checks = {
        "rider_cycle|csg_id ~= 0.458": {
            "sealed": sealed_cells["rider_cycle|csg_id"],
            "match": abs(sealed_cells["rider_cycle|csg_id"] - 0.458) < 0.001},
        "compact_vehicle|implicit_ood ~= 0.043": {
            "sealed": sealed_cells["compact_vehicle|implicit_ood"],
            "match": abs(sealed_cells["compact_vehicle|implicit_ood"] - 0.043) < 0.001},
        "aggregate 0.190 [0.181, 0.199]": {
            "sealed": [summary["primary"]["mean_difference"],
                       summary["primary"]["ci95_low_percentile"],
                       summary["primary"]["ci95_high_percentile"]],
            "match": (abs(summary["primary"]["mean_difference"] - 0.190) < 0.001
                      and abs(summary["primary"]["ci95_low_percentile"] - 0.181) < 0.001
                      and abs(summary["primary"]["ci95_high_percentile"] - 0.199) < 0.001)},
        "vs visual_hull +0.036 [0.027, 0.044]": {
            "sealed": [sealed_deltas["nonsemantic_visual_hull"]["mean_difference"],
                       sealed_deltas["nonsemantic_visual_hull"]["ci95_low_percentile"],
                       sealed_deltas["nonsemantic_visual_hull"]["ci95_high_percentile"]],
            "match": (abs(sealed_deltas["nonsemantic_visual_hull"]["mean_difference"] - 0.036) < 0.001
                      and abs(sealed_deltas["nonsemantic_visual_hull"]["ci95_low_percentile"] - 0.027) < 0.001
                      and abs(sealed_deltas["nonsemantic_visual_hull"]["ci95_high_percentile"] - 0.044) < 0.001)},
        "vs capsule +0.233": {
            "sealed": sealed_deltas["capsule"]["mean_difference"],
            "match": abs(sealed_deltas["capsule"]["mean_difference"] - 0.233) < 0.001},
        "vs bbox +0.310": {
            "sealed": sealed_deltas["bbox"]["mean_difference"],
            "match": abs(sealed_deltas["bbox"]["mean_difference"] - 0.310) < 0.001},
        "median inversion hull 0.567 > sppa 0.563": {
            "sealed": [method_stats["nonsemantic_visual_hull"]["median"],
                       method_stats["sppa_mvfit"]["median"]],
            "match": (abs(method_stats["nonsemantic_visual_hull"]["median"] - 0.567) < 0.001
                      and abs(method_stats["sppa_mvfit"]["median"] - 0.563) < 0.001
                      and method_stats["nonsemantic_visual_hull"]["median"] > method_stats["sppa_mvfit"]["median"])},
    }

    # drop-one-family range from the existing post-hoc artifact -------------------
    d1 = {k: v["mean_difference"] for k, v in drop1["results"].items() if k.startswith("drop_")}
    drop_range = [min(d1.values()), max(d1.values())]
    editor_checks["drop-one-family range 0.152-0.214"] = {
        "posthoc_artifact": drop_range,
        "match": abs(drop_range[0] - 0.152) < 0.001 and abs(drop_range[1] - 0.214) < 0.001,
        "caveat": "exploratory post-hoc artifact (t5_drop_one_family), not sealed confirmatory"}

    doc = {
        "label": "editorial re-analysis (post-hoc); per-cell CIs are NEW, point estimates are sealed",
        "resampling_for_new_cell_cis": "actors within family x stratum cell (n=20), 10,000 resamples, seed 77157, percentile 95%",
        "sealed_primary": summary["primary"],
        "per_cell": {f"{f}|{s}": {"point_sealed": float(cells[(f, s)].mean()),
                                  "ci95_new_posthoc": cell_ci[(f, s)], "n": 20}
                     for f in FAMILIES for s in STRATA},
        "method_stats_clean": method_stats,
        "sealed_paired_deltas": sealed_deltas,
        "drop_one_family_posthoc": {"range": drop_range, "per_drop": d1,
                                    "all_families": drop1["results"]["all_families"]["mean_difference"]},
        "editor_checks": editor_checks,
        "verification_point_estimates_vs_sealed": verification,
    }
    (ROOT / "per_family_stratum_ci.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print("wrote per_family_stratum_ci.json")

    write_family_tex(doc)
    write_family_md(doc)
    write_deltas_tex(doc)
    write_deltas_md(doc)


def ci3(c) -> str:
    return f"[{c[0]:.3f}, {c[1]:.3f}]"


def write_family_tex(doc: dict) -> None:
    L = []
    L.append("% Family x stratum table (preregistration section 6 obligation) - RESTORED")
    L.append("% Point estimates: SEALED confirmatory_summary.json (sppa_mvfit - generic_mvfit,")
    L.append("% clean 64^3 voxel IoU, paired per actor, n=20 actors per cell).")
    L.append("% Cell CIs: NEW post-hoc bootstrap over the 20 actors within each cell")
    L.append("% (10,000 resamples, seed 77157, percentile) - the sealed package stores no cell CIs.")
    L.append("\\begin{tabular}{lcc}")
    L.append("\\toprule")
    L.append("Family & CSG-ID $\\Delta$IoU [95\\% CI] & implicit-OOD $\\Delta$IoU [95\\% CI] \\\\")
    L.append("\\midrule")
    for f in FAMILIES:
        a = doc["per_cell"][f"{f}|csg_id"]
        b = doc["per_cell"][f"{f}|implicit_ood"]
        fam = f.replace("_", "\\_")
        L.append(f"{fam} & +{a['point_sealed']:.3f} {ci3(a['ci95_new_posthoc'])} "
                 f"& +{b['point_sealed']:.3f} {ci3(b['ci95_new_posthoc'])} \\\\")
    L.append("\\midrule")
    p = doc["sealed_primary"]
    L.append(f"\\textbf{{Aggregate (sealed)}} & \\multicolumn{{2}}{{c}}{{"
             f"+{p['mean_difference']:.3f} [{p['ci95_low_percentile']:.3f}, {p['ci95_high_percentile']:.3f}]"
             f" \\; ($n{{}}={{}}{p['actor_count']}$, sealed stratified bootstrap)}} \\\\")
    dr = doc["drop_one_family_posthoc"]["range"]
    L.append(f"Drop-one-family range (post-hoc) & \\multicolumn{{2}}{{c}}{{"
             f"{dr[0]:.3f}--{dr[1]:.3f} \\; (exploratory artifact t5\\_drop\\_one\\_family)}} \\\\")
    L.append("\\bottomrule")
    L.append("\\end{tabular}")
    (ROOT / "per_family_stratum_table.tex").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote per_family_stratum_table.tex")


def write_family_md(doc: dict) -> None:
    L = []
    L.append("# Family x stratum table — restored (preregistration §6)\n")
    L.append("**Generated:** 2026-07-20 by `run_confirmatory_editorial_tables.py` (new file).")
    L.append(" Sealed inputs read READ-ONLY from `reproducibility/sppa_mvfit/results/test/`;\n")
    L.append("nothing under `reproducibility/` was modified.\n")
    L.append("## Provenance\n")
    L.append("- **Point estimates and the aggregate row are SEALED** (`confirmatory_summary.json`,")
    L.append("  schema `sppa-mvfit-confirmatory-analysis-v2`; endpoint = clean 64³ voxel IoU,")
    L.append("  paired sppa_mvfit − generic_mvfit, 240 actors, stratified bootstrap 10k seed 77157).")
    L.append("- **Cell CIs are NEW (post-hoc)**: the sealed summary stores only per-cell point")
    L.append("  estimates. CIs here use the sealed bootstrap convention restricted to one cell:")
    L.append("  resample the 20 actors of the cell with replacement, 10,000 resamples,")
    L.append("  seed 77157, percentile 95%. Documented in `per_family_stratum_ci.json`.")
    L.append("- **Drop-one-family range** comes from the EXISTING exploratory post-hoc artifact")
    L.append("  `benchmarks/mvfit_posthoc_analysis/t5_drop_one_family/drop_one_family.json`")
    L.append("  (schema `sppa-mvfit-posthoc-drop-one-family-v1`) — it is NOT part of the sealed")
    L.append("  confirmatory package, and the table says so.\n")
    L.append("## Editor checks\n")
    for k, v in doc["editor_checks"].items():
        L.append(f"- {k}: **{'VERIFIED' if v['match'] else 'DISCREPANCY'}** ({v.get('sealed', v.get('posthoc_artifact'))})"
                 + (f" — {v['caveat']}" if 'caveat' in v else ""))
    L.append("\n## Cells (ΔIoU sppa−generic, clean)\n")
    L.append("| family | CSG-ID | implicit-OOD |")
    L.append("|---|---|---|")
    for f in FAMILIES:
        a = doc["per_cell"][f"{f}|csg_id"]
        b = doc["per_cell"][f"{f}|implicit_ood"]
        L.append(f"| {f} | +{a['point_sealed']:.4f} {ci3(a['ci95_new_posthoc'])} "
                 f"| +{b['point_sealed']:.4f} {ci3(b['ci95_new_posthoc'])} |")
    bad = {k: v for k, v in doc["verification_point_estimates_vs_sealed"].items() if not v["match"]}
    L.append(f"\nVerification: all 12 cell point estimates reproduce the sealed summary exactly"
             f" ({'12/12 match' if not bad else f'MISMATCHES: {bad}'}).")
    (ROOT / "per_family_stratum_note.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote per_family_stratum_note.md")


def write_deltas_tex(doc: dict) -> None:
    ms = doc["method_stats_clean"]
    sd = doc["sealed_paired_deltas"]
    L = []
    L.append("% Paired deltas vs baselines - RESTORED. All deltas SEALED (confirmatory_summary.json):")
    L.append("% paired sppa_mvfit - method, clean 64^3 voxel IoU, 240 actors, stratified")
    L.append("% bootstrap 10,000 seed 77157. Means/medians recomputed READ-ONLY from sealed raw_metrics.csv.")
    L.append("\\begin{tabular}{lccc}")
    L.append("\\toprule")
    L.append("Method & mean IoU & median IoU & SPPA$-$method $\\Delta$ [95\\% CI] (sealed) \\\\")
    L.append("\\midrule")
    for m in METHOD_ORDER:
        row = f"{m.replace('_', '\\_')} & {ms[m]['mean']:.3f} & {ms[m]['median']:.3f} & "
        if m == "sppa_mvfit":
            row += " \\\\"
        else:
            d = sd[m]
            kind = " (primary)" if m == "generic_mvfit" else (" (ablation)" if m == "sppa_text_only" else "")
            row += f"+{d['mean_difference']:.3f} [{d['ci95_low_percentile']:.3f}, {d['ci95_high_percentile']:.3f}]{kind} \\\\"
        L.append(row)
    L.append("\\bottomrule")
    L.append("\\end{tabular}")
    (ROOT / "paired_deltas_table.tex").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote paired_deltas_table.tex")


def write_deltas_md(doc: dict) -> None:
    ms = doc["method_stats_clean"]
    sd = doc["sealed_paired_deltas"]
    L = []
    L.append("# Paired deltas vs baselines — restored table\n")
    L.append("**Generated:** 2026-07-20 by `run_confirmatory_editorial_tables.py` (new file).\n")
    L.append("- All Δ values and CIs are **SEALED** (`confirmatory_summary.json`: paired")
    L.append("  sppa_mvfit − method, clean 64³ voxel IoU, 240 actors, stratified bootstrap")
    L.append("  10,000 resamples, seed 77157; primary endpoint = vs generic\\_mvfit; secondaries")
    L.append("  Holm-adjusted, all adjusted p = 0).")
    L.append("- Means/medians recomputed READ-ONLY from the sealed `raw_metrics.csv` (clean).\n")
    L.append("| method | mean | median | Δ sppa−method [CI] |")
    L.append("|---|---|---|---|")
    for m in METHOD_ORDER:
        if m == "sppa_mvfit":
            L.append(f"| {m} | {ms[m]['mean']:.4f} | {ms[m]['median']:.4f} | — |")
        else:
            d = sd[m]
            L.append(f"| {m} | {ms[m]['mean']:.4f} | {ms[m]['median']:.4f} "
                     f"| +{d['mean_difference']:.4f} [{d['ci95_low_percentile']:.4f}, {d['ci95_high_percentile']:.4f}] |")
    L.append("\n## Editor checks\n")
    for k in ("vs visual_hull +0.036 [0.027, 0.044]", "vs capsule +0.233", "vs bbox +0.310",
              "median inversion hull 0.567 > sppa 0.563"):
        v = doc["editor_checks"][k]
        L.append(f"- {k}: **{'VERIFIED' if v['match'] else 'DISCREPANCY'}** (sealed: {v['sealed']})")
    L.append("\nMedian discussion: nonsemantic\\_visual\\_hull has a HIGHER median "
             f"({ms['nonsemantic_visual_hull']['median']:.4f}) than sppa\\_mvfit "
             f"({ms['sppa_mvfit']['median']:.4f}) but a LOWER mean "
             f"({ms['nonsemantic_visual_hull']['mean']:.4f} vs {ms['sppa_mvfit']['mean']:.4f}); "
             "the sealed paired mean difference is +0.0357 [+0.0273, +0.0441]. The inversion is")
    L.append("real in the sealed data and should be discussed as a skew/heavy-tail property, not")
    L.append("as a contradiction.")
    (ROOT / "paired_deltas_note.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote paired_deltas_note.md")


if __name__ == "__main__":
    main()
