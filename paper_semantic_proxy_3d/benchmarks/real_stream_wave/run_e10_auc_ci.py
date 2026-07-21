"""E10 token-validation AUC confidence intervals (JGSA tribunal request).

The sealed-era e10_routing.json reports point AUCs on the 217 GT-matched
cases (138 wrong-token + 79 correct-token) but NO uncertainty intervals:

  * AUC(-confidence)        = 0.8470922766464869   (editor: 0.847)
  * AUC(+prior_mismatch)    = 0.0  =>  AUC(-mismatch) = 1.0   (editor: 1.000)
  * AUC(-obs_height)        = 1.0 (secondary raw signal)

Per-case scores ARE recoverable from results.jsonl (arm A = sppa_mvfit rows;
prior_mismatch = |ln(obs_height_m / H_family)| with the frozen H_family
recorded in e10_routing.json), so a case-level bootstrap is possible.

  * 10,000 resamples over the 217 matched cases with replacement, seed 77157.
  * AUC = Mann-Whitney with 0.5 tie correction (identical to run_e10_routing.py).
  * Percentile 95% CIs.

Reads results.jsonl / e10_routing.json READ-ONLY.
Writes NEW files only: e10_auc_ci.json, e10_auc_ci.md.

Run:  python run_e10_auc_ci.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results.jsonl"
ROUTING = ROOT / "e10_routing.json"
OUT_JSON = ROOT / "e10_auc_ci.json"
OUT_MD = ROOT / "e10_auc_ci.md"

SEED = 77157
N_BOOT = 10_000
ARM_A = "sppa_mvfit"


def mw_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Mann-Whitney AUC (P(score_pos > score_neg) + 0.5 ties); label 1 = wrong token."""
    pos = scores[labels == 1]
    neg = scores[labels == 0]
    wins = 0.0
    for p in pos:
        wins += float(np.sum(p > neg)) + 0.5 * float(np.sum(p == neg))
    return wins / (len(pos) * len(neg))


def main() -> None:
    routing = json.load(ROUTING.open(encoding="utf-8"))
    h_family = {k: float(v) for k, v in routing["h_family_m"].items()}

    rows = [json.loads(line) for line in RESULTS.open(encoding="utf-8")]
    cases = []
    for r in rows:
        if r["method"] != ARM_A or not r["matched"]:
            continue
        fam = str(r["family_token"])
        assert fam in h_family, f"unmapped family_token {fam}"
        obs_h = float(r["obs_height_m"])
        assert math.isfinite(obs_h) and obs_h > 0
        cases.append(
            {
                "case_id": r["case_id"],
                "label": 0 if r["token_correct"] else 1,
                "conf": float(r["confidence"]),
                "mismatch": abs(math.log(obs_h / h_family[fam])),
                "obs_h": obs_h,
            }
        )
    labels = np.array([c["label"] for c in cases])
    conf = np.array([c["conf"] for c in cases])
    mm = np.array([c["mismatch"] for c in cases])
    obsh = np.array([c["obs_h"] for c in cases])

    n_matched = len(cases)
    n_wrong = int(labels.sum())
    n_correct = int((1 - labels).sum())

    # point estimates ----------------------------------------------------------
    auc_neg_conf = mw_auc(-conf, labels)
    auc_pos_mm = mw_auc(mm, labels)
    auc_neg_mm = mw_auc(-mm, labels)
    auc_neg_obsh = mw_auc(-obsh, labels)

    ref = routing["token_arm"]
    verification = {
        "n_matched": {"new": n_matched, "e10": ref["n_matched"], "match": n_matched == ref["n_matched"]},
        "n_wrong": {"new": n_wrong, "e10": ref["n_wrong"], "match": n_wrong == ref["n_wrong"]},
        "n_correct": {"new": n_correct, "e10": ref["n_correct"], "match": n_correct == ref["n_correct"]},
        "auc_neg_confidence": {"new": auc_neg_conf, "e10": ref["auc_neg_confidence"],
                               "match": abs(auc_neg_conf - ref["auc_neg_confidence"]) < 1e-12},
        "auc_prior_mismatch": {"new": auc_pos_mm, "e10": ref["auc_prior_mismatch"],
                               "match": abs(auc_pos_mm - ref["auc_prior_mismatch"]) < 1e-12},
        "auc_neg_obs_height_m_secondary": {"new": auc_neg_obsh, "e10": ref["auc_neg_obs_height_m_secondary"],
                                           "match": abs(auc_neg_obsh - ref["auc_neg_obs_height_m_secondary"]) < 1e-12},
    }

    # bootstrap over cases ------------------------------------------------------
    rng = np.random.default_rng(SEED)
    b_neg_conf = np.empty(N_BOOT)
    b_neg_mm = np.empty(N_BOOT)
    b_neg_obsh = np.empty(N_BOOT)
    n_degenerate = 0
    for b in range(N_BOOT):
        idx = rng.integers(0, n_matched, n_matched)
        lb = labels[idx]
        if lb.sum() == 0 or lb.sum() == len(lb):
            n_degenerate += 1
            b_neg_conf[b] = b_neg_mm[b] = b_neg_obsh[b] = np.nan
            continue
        b_neg_conf[b] = mw_auc(-conf[idx], lb)
        b_neg_mm[b] = mw_auc(-mm[idx], lb)
        b_neg_obsh[b] = mw_auc(-obsh[idx], lb)

    def ci(a: np.ndarray) -> list[float]:
        a = a[~np.isnan(a)]
        return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]

    out = {
        "label": "editorial re-analysis (post-hoc); AUC confidence intervals",
        "experiment": "E10 wrong-token arm (token validation)",
        "data_source": "results.jsonl (arm A = sppa_mvfit, GT-matched cases), READ-ONLY",
        "resampling_unit": "matched case (217 cases)",
        "n_boot": N_BOOT,
        "seed": SEED,
        "ci_method": "percentile 2.5/97.5 over case-bootstrap replicates",
        "auc_estimator": "Mann-Whitney with 0.5 tie correction (as run_e10_routing.py)",
        "n_matched": n_matched,
        "n_wrong": n_wrong,
        "n_correct": n_correct,
        "results": {
            "auc_neg_confidence": {
                "point": auc_neg_conf,
                "ci95": ci(b_neg_conf),
                "note": "declared direction: LOW confidence -> wrong token",
            },
            "auc_neg_mismatch": {
                "point": auc_neg_mm,
                "ci95": ci(b_neg_mm),
                "note": ("editor-reported direction AUC(-mismatch); equals 1 - AUC(+mismatch). "
                         "AUC(+mismatch) point = " f"{auc_pos_mm}"),
            },
            "auc_pos_mismatch_raw": {
                "point": auc_pos_mm,
                "note": "as stored in e10_routing.json (auc_prior_mismatch = 0.0)",
            },
            "auc_neg_obs_height_secondary": {
                "point": auc_neg_obsh,
                "ci95": ci(b_neg_obsh),
                "note": "secondary raw signal reported by e10_routing.json",
            },
        },
        "n_degenerate_resamples": n_degenerate,
        "verification_vs_e10_routing": verification,
    }
    OUT_JSON.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {OUT_JSON.name}")

    bad = {k: v for k, v in verification.items() if not v["match"]}
    L = []
    L.append("# E10 token-validation AUC confidence intervals (JGSA editorial request)\n")
    L.append("**Generated:** 2026-07-20 by `run_e10_auc_ci.py` (new file; reads `results.jsonl` /")
    L.append("`e10_routing.json` READ-ONLY).\n")
    L.append("## Data availability\n")
    L.append("Per-case scores **were recoverable** from `results.jsonl` (217 GT-matched arm-A cases;")
    L.append(" prior mismatch recomputed as |ln(obs\\_height/H\\_family)| with the frozen H\\_family")
    L.append(" recorded in `e10_routing.json`). A case-level bootstrap is therefore well defined:\n")
    L.append(f"- resampling unit: matched case; {N_BOOT:,} resamples with replacement; seed {SEED};")
    L.append("  percentile 95% CI; AUC = Mann-Whitney with 0.5 tie correction (same estimator as the")
    L.append("  original `run_e10_routing.py`).\n")
    L.append("## Results\n")
    L.append("| signal | point AUC | 95% CI (case bootstrap) |")
    L.append("|---|---|---|")
    r = out["results"]
    L.append(f"| AUC(-confidence) | {r['auc_neg_confidence']['point']:.3f} | "
             f"[{r['auc_neg_confidence']['ci95'][0]:.3f}, {r['auc_neg_confidence']['ci95'][1]:.3f}] |")
    L.append(f"| AUC(-mismatch) | {r['auc_neg_mismatch']['point']:.3f} | "
             f"[{r['auc_neg_mismatch']['ci95'][0]:.3f}, {r['auc_neg_mismatch']['ci95'][1]:.3f}] |")
    L.append(f"| AUC(-obs\\_height) (secondary) | {r['auc_neg_obs_height_secondary']['point']:.3f} | "
             f"[{r['auc_neg_obs_height_secondary']['ci95'][0]:.3f}, {r['auc_neg_obs_height_secondary']['ci95'][1]:.3f}] |")
    L.append("")
    L.append("Notes / caveats:\n")
    L.append("- The editor's \"AUC(-mismatch) = 1.000\" equals 1 - `auc_prior_mismatch` stored in")
    L.append(f" `e10_routing.json` (stored value {auc_pos_mm}); the sign convention is now explicit.")
    L.append("- AUC(-mismatch) = 1.0 reflects **perfect separation** on the 217 matched cases; the")
    L.append("  bootstrap CI is degenerate/near-degenerate at the boundary and should be read as")
    L.append("  \"no observed overlap\", not as evidence the population AUC is exactly 1.")
    L.append(f"- Degenerate resamples (single-class draw): {n_degenerate}/{N_BOOT:,}.")
    L.append(f"- Verification vs `e10_routing.json`: {len(verification) - len(bad)}/{len(verification)}"
             f" checks reproduce exactly (counts 217 = 138 + 79; both stored AUCs)."
             + (f" MISMATCHES: {bad}" if bad else ""))
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT_MD.name}")


if __name__ == "__main__":
    main()
