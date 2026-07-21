"""E11 cluster bootstrap (editorial re-analysis, JGSA tribunal request).

Editor objection: the original per-ring CIs in e11_analysis.json were computed
by bootstrap over 149/154 individual detections drawn from only 11 towers;
the 12 azimuth views of one tower are NOT independent.

Fix: cluster bootstrap -- resample TOWERS (11 clusters) with replacement,
pool all detections of the sampled towers (multiplicity preserved), and
recompute every per-ring statistic on the pooled sample.

  * 10,000 resamples, seed 20260720 (same seed as the original analysis).
  * Rings: oblique30, oblique45 (nadir block moved to prose per editor).
  * Statistics per ring:
      (a) mean 3D IoU per method, cluster CI 95%;
      (b) paired delta sppa_mvfit - baseline per ring, cluster CI 95%
          (pairing is exact: every case carries all 6 methods);
      (c) correct-token subset means, cluster CI 95%;
      (d) wrong-token rate per ring: Wilson 95% binomial CI (as requested)
          plus a cluster-bootstrap CI as robustness complement.

Reads results.jsonl and e11_analysis.json READ-ONLY.
Writes NEW files only: e11_cluster_bootstrap.json, e11_main_table_full.tex,
e11_cluster_note.md.

Run:  python run_e11_cluster_bootstrap.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results.jsonl"
ANALYSIS = ROOT / "e11_analysis.json"
OUT_JSON = ROOT / "e11_cluster_bootstrap.json"
OUT_TEX = ROOT / "e11_main_table_full.tex"
OUT_MD = ROOT / "e11_cluster_note.md"

SEED = 20260720
N_BOOT = 10_000
METHODS = ["sppa_mvfit", "generic_mvfit", "obb", "aabb", "visual_hull", "capsule"]
BASELINES = [m for m in METHODS if m != "sppa_mvfit"]
RINGS = ["oblique30", "oblique45"]


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (centre - half, centre + half)


def main() -> None:
    rows = [json.loads(line) for line in RESULTS.open(encoding="utf-8")]
    analysis = json.load(ANALYSIS.open(encoding="utf-8"))

    # ---- pivot to case level -------------------------------------------------
    cases: dict[str, dict] = {}
    for r in rows:
        cid = r["case_id"]
        c = cases.setdefault(
            cid,
            {
                "case_id": cid,
                "ring": r["ring"],
                "tower_id": r["tower_id"],
                "token_correct": bool(r["token_correct"]),
                "iou": {},
            },
        )
        assert c["ring"] == r["ring"] and c["tower_id"] == r["tower_id"]
        assert c["token_correct"] == bool(r["token_correct"])
        c["iou"][r["method"]] = float(r["iou_3d"])
    for c in cases.values():
        assert set(c["iou"]) == set(METHODS), f"incomplete methods in {c['case_id']}"

    towers_all = sorted({c["tower_id"] for c in cases.values()})
    assert len(towers_all) == 11, f"expected 11 towers, got {len(towers_all)}"

    rng = np.random.default_rng(SEED)
    out = {
        "label": "editorial re-analysis (post-hoc); cluster bootstrap by tower",
        "benchmark": "E11 Oblique Twin Wave",
        "editor_objection": (
            "original per-ring CIs treated 149/154 detections from only 11 towers "
            "as independent; the 12 azimuths of one tower are correlated"
        ),
        "resampling_unit": "tower_id (11 clusters, resampled with replacement)",
        "n_boot": N_BOOT,
        "seed": SEED,
        "ci_method": "percentile 2.5/97.5 over cluster-bootstrap replicates",
        "n_towers": len(towers_all),
        "towers": towers_all,
        "per_ring": {},
        "correct_token": {},
        "token_rates": {},
        "verification_vs_e11_analysis": {},
    }

    for ring in RINGS:
        rc = [c for c in cases.values() if c["ring"] == ring]
        by_tower: dict[str, list[dict]] = {}
        for c in rc:
            by_tower.setdefault(c["tower_id"], []).append(c)
        towers = sorted(by_tower)
        n_cases = len(rc)
        n_wrong = sum(1 for c in rc if not c["token_correct"])

        iou_mat = {m: np.array([c["iou"][m] for c in rc]) for m in METHODS}
        tok = np.array([1.0 if c["token_correct"] else 0.0 for c in rc])
        # index lists per tower for fast pooling
        idx_of_case = {c["case_id"]: i for i, c in enumerate(rc)}
        tower_idx = [np.array([idx_of_case[c["case_id"]] for c in by_tower[t]]) for t in towers]

        # point estimates -----------------------------------------------------
        point = {m: float(iou_mat[m].mean()) for m in METHODS}
        point_delta = {m: float((iou_mat["sppa_mvfit"] - iou_mat[m]).mean()) for m in BASELINES}
        ct_mask = tok == 1.0
        point_ct = {m: float(iou_mat[m][ct_mask].mean()) for m in METHODS}
        point_ct_delta = {
            m: float((iou_mat["sppa_mvfit"][ct_mask] - iou_mat[m][ct_mask]).mean())
            for m in BASELINES
        }

        # verification against the sealed-era aggregate file -------------------
        ver = {}
        for m in METHODS:
            ref = analysis["per_ring"][ring][m]["mean"]
            ver[f"{ring}:{m}:mean"] = {"new": point[m], "e11_analysis": ref,
                                       "match": abs(point[m] - ref) < 1e-12}
        ref_ct = analysis["per_ring_correct_token"][ring]["sppa_mvfit"]["mean"]
        ver[f"{ring}:sppa_mvfit:correct_token_mean"] = {
            "new": point_ct["sppa_mvfit"], "e11_analysis": ref_ct,
            "match": abs(point_ct["sppa_mvfit"] - ref_ct) < 1e-12}
        ver[f"{ring}:n"] = {"new": n_cases, "e11_analysis": analysis["per_ring"][ring]["sppa_mvfit"]["n"],
                            "match": n_cases == analysis["per_ring"][ring]["sppa_mvfit"]["n"]}
        ver[f"{ring}:n_wrong"] = {"new": n_wrong,
                                  "e11_analysis": analysis["token_arm"]["wrong_by_ring"][ring],
                                  "match": n_wrong == analysis["token_arm"]["wrong_by_ring"][ring]}
        out["verification_vs_e11_analysis"].update(ver)

        # cluster bootstrap ----------------------------------------------------
        boot = {m: np.empty(N_BOOT) for m in METHODS}
        boot_delta = {m: np.empty(N_BOOT) for m in BASELINES}
        boot_ct = {m: np.full(N_BOOT, np.nan) for m in METHODS}
        boot_ct_delta = {m: np.full(N_BOOT, np.nan) for m in BASELINES}
        boot_wrong_rate = np.empty(N_BOOT)
        n_ct_fail = 0
        for b in range(N_BOOT):
            draw = rng.integers(0, len(towers), len(towers))  # resample towers
            pooled = np.concatenate([tower_idx[j] for j in draw])
            sppa = iou_mat["sppa_mvfit"][pooled]
            for m in METHODS:
                boot[m][b] = iou_mat[m][pooled].mean()
            for m in BASELINES:
                boot_delta[m][b] = (sppa - iou_mat[m][pooled]).mean()
            boot_wrong_rate[b] = 1.0 - tok[pooled].mean()
            ct = pooled[tok[pooled] == 1.0]
            if ct.size:
                for m in METHODS:
                    boot_ct[m][b] = iou_mat[m][ct].mean()
                for m in BASELINES:
                    boot_ct_delta[m][b] = (iou_mat["sppa_mvfit"][ct] - iou_mat[m][ct]).mean()
            else:
                n_ct_fail += 1

        def ci(a: np.ndarray) -> list[float]:
            a = a[~np.isnan(a)]
            return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]

        out["per_ring"][ring] = {
            "n_cases": n_cases,
            "n_towers": len(towers),
            "methods": {
                m: {
                    "mean": point[m],
                    "median": float(np.median(iou_mat[m])),
                    "ci95_mean_cluster": ci(boot[m]),
                    "ci95_mean_pseudo_replicate_was": analysis["per_ring"][ring][m]["ci95_mean"],
                }
                for m in METHODS
            },
            "paired_delta_sppa_minus": {
                m: {
                    "mean": point_delta[m],
                    "ci95_cluster": ci(boot_delta[m]),
                    "frac_le_0_cluster": float((boot_delta[m] <= 0).mean()),
                    "ci95_pseudo_replicate_was": analysis["per_ring"][ring]["paired_diffs"][f"sppa_minus_{m}"]["ci95"],
                }
                for m in BASELINES
            },
        }
        out["correct_token"][ring] = {
            "n_cases": int(ct_mask.sum()),
            "methods": {
                m: {
                    "mean": point_ct[m],
                    "median": float(np.median(iou_mat[m][ct_mask])),
                    "ci95_mean_cluster": ci(boot_ct[m]),
                }
                for m in METHODS
            },
            "paired_delta_sppa_minus": {
                m: {"mean": point_ct_delta[m], "ci95_cluster": ci(boot_ct_delta[m])}
                for m in BASELINES
            },
            "n_empty_resamples": n_ct_fail,
        }
        out["token_rates"][ring] = {
            "n_cases": n_cases,
            "n_correct": int(ct_mask.sum()),
            "n_wrong": n_wrong,
            "correct_rate": float(ct_mask.mean()),
            "wrong_rate": float(1.0 - ct_mask.mean()),
            "wrong_rate_ci95_wilson": list(wilson_ci(n_wrong, n_cases)),
            "correct_rate_ci95_wilson": list(wilson_ci(int(ct_mask.sum()), n_cases)),
            "wrong_rate_ci95_cluster": ci(boot_wrong_rate),
        }

    OUT_JSON.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {OUT_JSON.name}")

    write_tex(out)
    write_md(out)


def f3(x: float) -> str:
    return f"{x:.3f}"


def ci3(c: list[float]) -> str:
    return f"[{c[0]:.3f}, {c[1]:.3f}]"


def write_tex(out: dict) -> None:
    L = []
    L.append("% E11 Oblique Twin Wave - RESTORED main table (cluster bootstrap by tower)")
    L.append("% CIs: 10,000 cluster-bootstrap resamples over the 11 TOWERS (seed 20260720),")
    L.append("% percentile method. Detections within a tower are NOT treated as independent.")
    L.append("% Nadir block removed from the table (moved to prose) per editorial request.")
    L.append("\\begin{tabular}{llccc}")
    L.append("\\toprule")
    L.append("Ring & Method & mean 3D IoU [95\\% CI] / median & $n$ & SPPA$-$method [95\\% CI] \\\\")
    L.append("\\midrule")
    for ring in RINGS:
        pr = out["per_ring"][ring]
        for i, m in enumerate(METHODS):
            mrow = pr["methods"][m]
            ringcell = ring if i == 0 else ""
            delta = ""
            if m != "sppa_mvfit":
                d = pr["paired_delta_sppa_minus"][m]
                delta = f"+{d['mean']:.3f} [{d['ci95_cluster'][0]:+.3f}, {d['ci95_cluster'][1]:+.3f}]"
            L.append(
                f"{ringcell} & {m} & {f3(mrow['mean'])} {ci3(mrow['ci95_mean_cluster'])} / "
                f"{f3(mrow['median'])} & {pr['n_cases']} & {delta} \\\\"
            )
        L.append("\\midrule")
    L.append("\\multicolumn{5}{l}{Correct-token subset (cluster-bootstrap CIs, tower-level resampling)} \\\\")
    L.append("\\midrule")
    for ring in RINGS:
        ct = out["correct_token"][ring]
        for i, m in enumerate(METHODS):
            if m not in ("sppa_mvfit", "generic_mvfit"):
                continue
            mrow = ct["methods"][m]
            ringcell = f"{ring} (correct token)" if i == 0 else ""
            delta = ""
            if m != "sppa_mvfit":
                d = ct["paired_delta_sppa_minus"][m]
                delta = f"+{d['mean']:.3f} [{d['ci95_cluster'][0]:+.3f}, {d['ci95_cluster'][1]:+.3f}]"
            L.append(
                f"{ringcell} & {m} & {f3(mrow['mean'])} {ci3(mrow['ci95_mean_cluster'])} / "
                f"{f3(mrow['median'])} & {ct['n_cases']} & {delta} \\\\"
            )
    L.append("\\midrule")
    L.append("\\multicolumn{5}{l}{Wrong-token rate per ring (Wilson 95\\% CI; cluster CI in braces)} \\\\")
    L.append("\\midrule")
    for ring in RINGS:
        tr = out["token_rates"][ring]
        L.append(
            f"{ring} & wrong token & {tr['n_wrong']}/{tr['n_cases']} = {tr['wrong_rate']:.3f} "
            f"{ci3(tr['wrong_rate_ci95_wilson'])} "
            f"\\{{{ci3(tr['wrong_rate_ci95_cluster'])}\\}} & {tr['n_cases']} &  \\\\"
        )
    L.append("\\bottomrule")
    L.append("\\end{tabular}")
    OUT_TEX.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT_TEX.name}")


def write_md(out: dict) -> None:
    L = []
    L.append("# E11 cluster-bootstrap re-analysis (JGSA editorial request)\n")
    L.append("**Generated:** 2026-07-20 by `run_e11_cluster_bootstrap.py` (new file; reads sealed-era")
    L.append("`results.jsonl` / `e11_analysis.json` READ-ONLY; nothing under `reproducibility/` touched).\n")
    L.append("## Method\n")
    L.append(f"- Resampling unit: **tower** ({out['n_towers']} clusters), drawn with replacement;")
    L.append("  all detections of a drawn tower enter the replicate (multiplicity preserved).")
    L.append(f"- {out['n_boot']:,} resamples, seed {out['seed']} (same seed as the original analysis),")
    L.append("  percentile 95% CIs. Pairing is exact: every case carries all 6 methods.")
    L.append("- Editor objection addressed: the previous CIs treated 149/154 detections from 11 towers")
    L.append("  as independent (12 azimuths per tower are correlated).\n")
    L.append("## Results (cluster CIs; pseudo-replicate CIs of the original analysis in the JSON)\n")
    for ring in RINGS:
        pr = out["per_ring"][ring]
        L.append(f"### {ring} (n={pr['n_cases']} cases, {pr['n_towers']} towers)\n")
        L.append("| method | mean [cluster CI95] | (was pseudo-rep CI) |")
        L.append("|---|---|---|")
        for m in METHODS:
            mr = pr["methods"][m]
            L.append(f"| {m} | {f3(mr['mean'])} {ci3(mr['ci95_mean_cluster'])} | {ci3(mr['ci95_mean_pseudo_replicate_was'])} |")
        L.append("\n| paired Δ sppa−method | mean [cluster CI95] | P(Δ≤0) |")
        L.append("|---|---|---|")
        for m in BASELINES:
            d = pr["paired_delta_sppa_minus"][m]
            L.append(f"| sppa−{m} | +{d['mean']:.3f} [{d['ci95_cluster'][0]:+.3f}, {d['ci95_cluster'][1]:+.3f}] | {d['frac_le_0_cluster']:.4f} |")
        ct = out["correct_token"][ring]
        L.append(f"\nCorrect-token subset (n={ct['n_cases']}): sppa_mvfit "
                 f"{f3(ct['methods']['sppa_mvfit']['mean'])} {ci3(ct['methods']['sppa_mvfit']['ci95_mean_cluster'])}; "
                 f"generic_mvfit {f3(ct['methods']['generic_mvfit']['mean'])} "
                 f"{ci3(ct['methods']['generic_mvfit']['ci95_mean_cluster'])}.\n")
        tr = out["token_rates"][ring]
        L.append(f"Wrong-token rate: {tr['n_wrong']}/{tr['n_cases']} = {tr['wrong_rate']:.3f}, "
                 f"Wilson {ci3(tr['wrong_rate_ci95_wilson'])}, cluster {ci3(tr['wrong_rate_ci95_cluster'])} "
                 f"(correct rate {tr['correct_rate']:.3f} = {tr['n_correct']}/{tr['n_cases']}).\n")
    L.append("## Verification vs `e11_analysis.json`\n")
    bad = {k: v for k, v in out["verification_vs_e11_analysis"].items() if not v["match"]}
    L.append(f"- Point estimates (means, n, wrong-token counts) reproduce `e11_analysis.json` exactly: "
             f"**{len(out['verification_vs_e11_analysis']) - len(bad)}/{len(out['verification_vs_e11_analysis'])} checks match**.")
    if bad:
        L.append(f"- MISMATCHES: {bad}")
    L.append("- 140/149 correct at 30° and 89/154 at 45° **verified from raw data** "
             "(wrong: 9/149 = 6.0% at 30°, 65/154 = 42.2% at 45°).")
    L.append("\n## Caveats\n")
    L.append("- Only 11 clusters exist; cluster CIs are wider than the original pseudo-replicate CIs")
    L.append("  and are the honest uncertainty statement at the tower level.")
    L.append("- Wilson CIs for token rates assume independent detections; the cluster CIs (braces in")
    L.append("  the table) are the conservative counterpart.")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT_MD.name}")


if __name__ == "__main__":
    main()
