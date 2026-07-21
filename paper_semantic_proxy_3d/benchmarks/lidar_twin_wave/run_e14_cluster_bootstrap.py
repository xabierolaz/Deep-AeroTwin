"""E14 cluster bootstrap (editorial re-analysis, JGSA tribunal request).

Same editor objection as E11: per-arm CIs must not treat within-cluster
measurements as independent. Resampling unit declared explicitly: the TOWER.

  * clean arm:    11 towers (clusters), one fit per method per tower.
  * degraded arm: 11 towers attempted; 4 towers (t1, t2, t10, tower13) are
    detection failures for ALL methods (verified from results.jsonl); the
    bootstrap resamples the 7 towers with successful detections.

10,000 resamples, seed 77157 (seed of the sealed confirmatory study), towers
drawn with replacement, statistic = mean 3D IoU over sampled towers,
percentile 95% CI. One observation per tower per method per arm, so the
cluster bootstrap coincides with an ordinary bootstrap over towers; the
declaration still matters because the tower -- not the LiDAR return -- is
the independent unit.

Reads results.jsonl / e14_analysis.json READ-ONLY.
Writes NEW files only: e14_cluster_bootstrap.json, e14_table_full.tex,
e14_cluster_note.md.

Run:  python run_e14_cluster_bootstrap.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results.jsonl"
ANALYSIS = ROOT / "e14_analysis.json"
OUT_JSON = ROOT / "e14_cluster_bootstrap.json"
OUT_TEX = ROOT / "e14_table_full.tex"
OUT_MD = ROOT / "e14_cluster_note.md"

SEED = 77157
N_BOOT = 10_000
METHODS = ["sppa_mvfit", "generic_mvfit", "obb", "aabb", "visual_hull", "capsule"]
ARMS = ["clean", "degraded"]


def main() -> None:
    rows = [json.loads(line) for line in RESULTS.open(encoding="utf-8")]
    analysis = json.load(ANALYSIS.open(encoding="utf-8"))

    rng = np.random.default_rng(SEED)
    out = {
        "label": "editorial re-analysis (post-hoc); cluster bootstrap by tower",
        "experiment": "E14 LiDAR Twin Wave",
        "editor_objection": (
            "per-arm CIs must be computed at the independent-unit level; "
            "the resampling unit is declared to be the tower"
        ),
        "resampling_unit": "tower_id (one fit per method per tower per arm)",
        "n_boot": N_BOOT,
        "seed": SEED,
        "ci_method": "percentile 2.5/97.5 over cluster-bootstrap replicates",
        "arms": {},
        "verification_vs_e14_analysis": {},
    }

    for arm in ARMS:
        arows = [r for r in rows if r["arm"] == arm]
        towers = sorted({r["tower_id"] for r in arows})
        failed = sorted(
            {r["tower_id"] for r in arows if r["detection_failed"]}
        )
        ok_towers = [t for t in towers if t not in failed]

        vals = {}
        for m in METHODS:
            v = []
            for t in ok_towers:
                rec = [r for r in arows if r["tower_id"] == t and r["method"] == m]
                assert len(rec) == 1 and not rec[0]["detection_failed"]
                v.append(float(rec[0]["iou_3d"]))
            vals[m] = np.array(v)

        # verify point estimates vs the existing aggregate ---------------------
        for m in METHODS:
            ref = analysis["per_arm_method"][arm][m]["iou_3d"]
            new = float(vals[m].mean())
            out["verification_vs_e14_analysis"][f"{arm}:{m}"] = {
                "new_mean": new, "e14_analysis_mean": ref["mean"],
                "new_n": int(len(vals[m])), "e14_analysis_n": ref["n"],
                "match": abs(new - ref["mean"]) < 1e-12 and len(vals[m]) == ref["n"],
            }
        out["verification_vs_e14_analysis"][f"{arm}:n_detection_failed"] = {
            "new": len(failed),
            "e14_analysis": analysis["per_arm_method"][arm]["sppa_mvfit"]["n_detection_failed"],
            "match": len(failed) == analysis["per_arm_method"][arm]["sppa_mvfit"]["n_detection_failed"],
        }

        boot = {m: np.empty(N_BOOT) for m in METHODS}
        # supplementary: paired sppa - baseline deltas at tower level
        base = [m for m in METHODS if m != "sppa_mvfit"]
        boot_delta = {m: np.empty(N_BOOT) for m in base}
        for b in range(N_BOOT):
            idx = rng.integers(0, len(ok_towers), len(ok_towers))
            for m in METHODS:
                boot[m][b] = vals[m][idx].mean()
            for m in base:
                boot_delta[m][b] = (vals["sppa_mvfit"][idx] - vals[m][idx]).mean()

        def ci(a: np.ndarray) -> list[float]:
            return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]

        out["arms"][arm] = {
            "n_towers_attempted": len(towers),
            "n_detection_failed": len(failed),
            "detection_failed_towers": failed,
            "n_towers_fitted": len(ok_towers),
            "fitted_towers": ok_towers,
            "methods": {
                m: {
                    "mean": float(vals[m].mean()),
                    "median": float(np.median(vals[m])),
                    "ci95_mean_cluster": ci(boot[m]),
                    "ci95_mean_pseudo_replicate_was": analysis["per_arm_method"][arm][m]["iou_3d"]["ci95"],
                }
                for m in METHODS
            },
            "paired_delta_sppa_minus_supplementary": {
                m: {"mean": float((vals["sppa_mvfit"] - vals[m]).mean()),
                    "ci95_cluster": ci(boot_delta[m]),
                    "frac_le_0_cluster": float((boot_delta[m] <= 0).mean())}
                for m in base
            },
        }

    OUT_JSON.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {OUT_JSON.name}")
    write_tex(out)
    write_md(out)


def write_tex(out: dict) -> None:
    L = []
    L.append("% E14 LiDAR Twin Wave - RESTORED table (cluster bootstrap by tower)")
    L.append("% CIs: 10,000 cluster-bootstrap resamples over TOWERS (seed 77157), percentile method.")
    L.append("\\begin{tabular}{lcc}")
    L.append("\\toprule")
    L.append("Method & clean mean 3D IoU [95\\% CI] & degraded mean 3D IoU [95\\% CI] \\\\")
    L.append("\\midrule")
    for m in METHODS:
        c = out["arms"]["clean"]["methods"][m]
        d = out["arms"]["degraded"]["methods"][m]
        L.append(
            f"{m} & {c['mean']:.3f} [{c['ci95_mean_cluster'][0]:.3f}, {c['ci95_mean_cluster'][1]:.3f}] "
            f"& {d['mean']:.3f} [{d['ci95_mean_cluster'][0]:.3f}, {d['ci95_mean_cluster'][1]:.3f}] \\\\"
        )
    L.append("\\bottomrule")
    L.append("\\multicolumn{3}{l}{\\footnotesize Resampling unit: tower. clean: $n{=}11$ towers, 0 detection failures;}")
    L.append("\\\\")
    L.append("\\multicolumn{3}{l}{\\footnotesize degraded: $n{=}7$ fitted towers after 4/11 detection failures}")
    L.append("\\\\")
    L.append("\\multicolumn{3}{l}{\\footnotesize (t1, t2, t10, tower13, failed for all methods). 10{,}000 cluster}")
    L.append("\\\\")
    L.append("\\multicolumn{3}{l}{\\footnotesize bootstrap resamples over towers with replacement, seed 77157.}")
    L.append("\\\\")
    L.append("\\end{tabular}")
    OUT_TEX.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT_TEX.name}")


def write_md(out: dict) -> None:
    L = []
    L.append("# E14 cluster-bootstrap re-analysis (JGSA editorial request)\n")
    L.append("**Generated:** 2026-07-20 by `run_e14_cluster_bootstrap.py` (new file; reads sealed-era")
    L.append("`results.jsonl` / `e14_analysis.json` READ-ONLY).\n")
    L.append("## Declared resampling unit\n")
    L.append("The **tower** is the independent unit (one fit per method per tower per arm).")
    L.append(f" {out['n_boot']:,} resamples with replacement over towers, seed {out['seed']},")
    L.append(" percentile 95% CIs. Because each cluster contributes exactly one observation per")
    L.append(" method, the cluster bootstrap reduces to an ordinary bootstrap over towers; the")
    L.append(" declaration still fixes the independent unit unambiguously.\n")
    L.append("## n per arm (verified from `results.jsonl`)\n")
    for arm in ARMS:
        a = out["arms"][arm]
        L.append(f"- **{arm}**: {a['n_towers_fitted']} fitted towers of {a['n_towers_attempted']} attempted"
                 + (f"; detection failures: {', '.join(a['detection_failed_towers'])} (all methods)."
                    if a["n_detection_failed"] else "; no detection failures."))
    L.append("")
    L.append("## Results\n")
    L.append("| method | clean mean [cluster CI95] | degraded mean [cluster CI95] |")
    L.append("|---|---|---|")
    for m in METHODS:
        c = out["arms"]["clean"]["methods"][m]
        d = out["arms"]["degraded"]["methods"][m]
        L.append(f"| {m} | {c['mean']:.4f} [{c['ci95_mean_cluster'][0]:.4f}, {c['ci95_mean_cluster'][1]:.4f}] "
                 f"| {d['mean']:.4f} [{d['ci95_mean_cluster'][0]:.4f}, {d['ci95_mean_cluster'][1]:.4f}] |")
    L.append("")
    bad = {k: v for k, v in out["verification_vs_e14_analysis"].items() if not v["match"]}
    L.append(f"Verification vs `e14_analysis.json`: **{len(out['verification_vs_e14_analysis']) - len(bad)}/"
             f"{len(out['verification_vs_e14_analysis'])} checks match** (means, n per arm, detection-failure"
             " counts reproduce exactly)." + (f" MISMATCHES: {bad}" if bad else ""))
    L.append("\nSupplementary paired tower-level deltas (SPPA$-$baseline per arm) are in the JSON")
    L.append("(`paired_delta_sppa_minus_supplementary`).")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT_MD.name}")


if __name__ == "__main__":
    main()
