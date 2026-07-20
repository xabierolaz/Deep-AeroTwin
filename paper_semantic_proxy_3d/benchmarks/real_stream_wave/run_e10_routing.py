"""E10 "Measured mode routing" - exploratory post-hoc, NOT sealed.

Implements e10_protocol.md (FROZEN 2026-07-19 before any routing outcome was
computed) on the E7 real-stream results:

  * Arms: A = SPPA-MVFit (operational top-only + height anchor), B = OBB
    (best box proxy, declared from the published E7 table).
  * Routing signals: detector confidence (ROUTING ONLY, never fitter input -
    the sealed protocol forbids it as fit input) and prior mismatch
    |ln(obs_height / H_family)| with H_family derived from the frozen graphs
    at nominal theta.
  * Policies on the frozen grid: always-SPPA, always-proxy, oracle,
    conf<tau (15 values on [0.10, 0.77]), mismatch>mu (15 values on the
    empirical signal range), AND/OR of the best tau*/mu*.
  * Stats: paired case-level bootstrap (10,000 resamples, seed 20260719),
    McNemar-style win/tie/lose.
  * Wrong-token arm: ROC/AUC of -confidence and +mismatch on the 217
    GT-matched cases; wrong-token rate above/below tau*/mu*.
  * Token-routing interaction: 138 correct-token refits joined by case_id.

Reads results.jsonl READ-ONLY; writes only e10_* files in this folder.

Run:  python run_e10_routing.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

E7_ROOT = Path(__file__).resolve().parent
RESULTS = E7_ROOT / "results.jsonl"
OUT_JSON = E7_ROOT / "e10_routing.json"
OUT_TEX = E7_ROOT / "e10_routing_table.tex"
OUT_FIG = E7_ROOT / "fig_e10_routing.png"

import sys

JGSA = E7_ROOT.parents[1] / "tools" / "jgsa_figures"
sys.path.insert(0, str(JGSA))
sys.path.insert(0, str(E7_ROOT))
import jgsa_style  # noqa: E402
from e7_common import FAMILY_NOMINAL_HEIGHT_M, graph_extent_units  # noqa: E402

jgsa_style.apply_style()
OI = jgsa_style.OI

# ---------------------------------------------------------------------------
# Frozen protocol constants (e10_protocol.md)
# ---------------------------------------------------------------------------
SEED = 20260719
N_BOOT = 10_000
N_GRID = 15
CONF_GRID = np.linspace(0.10, 0.77, N_GRID)  # declared literal grid
ARM_A = "sppa_mvfit"   # SPPA-MVFit operational top-only mode
ARM_B = "obb"          # best box proxy (declared from published E7 table)
TIE_TOL = 1e-12

# H_family: z-extent of the frozen graph at nominal theta x declared metric
# scale (derivation documented in e10_protocol.md section 2).
H_FAMILY = {}
for _fam in ("lattice_tower", "quadruped", "rider_cycle"):
    _ext = graph_extent_units(_fam)[2]                  # graph units, pristine graphs
    _scale = FAMILY_NOMINAL_HEIGHT_M[_fam] / _ext       # declared m/unit (e7_common)
    H_FAMILY[_fam] = _ext * _scale                      # derived nominal height (m)


# ---------------------------------------------------------------------------
# Load + case table
# ---------------------------------------------------------------------------
def load_cases() -> tuple[list[dict], dict[str, float], dict[str, float]]:
    rows = [json.loads(line) for line in RESULTS.open(encoding="utf-8")]
    arm_a = {r["case_id"]: r for r in rows if r["method"] == ARM_A}
    arm_b = {r["case_id"]: r for r in rows if r["method"] == ARM_B}
    refit = {r["case_id"]: r["reproj_iou"] for r in rows if r["method"] == "sppa_mvfit_correct_token"}

    # --- sanity (protocol section 8) --------------------------------------
    assert len(arm_a) == 1902, f"expected 1902 {ARM_A} rows, got {len(arm_a)}"
    assert len(arm_b) == 1902, f"expected 1902 {ARM_B} rows, got {len(arm_b)}"
    assert set(arm_a) == set(arm_b), "arm A/B case_id mismatch"
    assert len(refit) == 138, f"expected 138 refit rows, got {len(refit)}"

    cases = []
    for cid, ra in sorted(arm_a.items()):
        conf = float(ra["confidence"])
        obs_h = float(ra["obs_height_m"])
        ya = float(ra["reproj_iou"])
        yb = float(arm_b[cid]["reproj_iou"])
        for name, v in (("confidence", conf), ("obs_height_m", obs_h),
                        ("reproj_A", ya), ("reproj_B", yb)):
            assert math.isfinite(v), f"non-finite {name} in case {cid}"
        assert obs_h > 0.0, f"non-positive obs_height_m in case {cid}"
        fam = str(ra["family_token"])
        assert fam in H_FAMILY, f"unmapped family_token {fam} in case {cid}"
        cases.append(
            {
                "case_id": cid,
                "det_class": str(ra["det_class"]),
                "family_token": fam,
                "confidence": conf,
                "obs_height_m": obs_h,
                "h_family_m": H_FAMILY[fam],
                "prior_mismatch": abs(math.log(obs_h / H_FAMILY[fam])),
                "matched": bool(ra["matched"]),
                "token_correct": bool(ra["token_correct"]),
                "y_a": ya,
                "y_b": yb,
            }
        )
    n_matched = sum(1 for c in cases if c["matched"])
    n_wrong = sum(1 for c in cases if c["matched"] and not c["token_correct"])
    n_correct = sum(1 for c in cases if c["matched"] and c["token_correct"])
    assert n_matched == 217 and n_wrong == 138 and n_correct == 79, (
        f"matched composition {n_matched}/{n_wrong}/{n_correct} != 217/138/79"
    )
    n_refit_join = sum(1 for c in cases if c["matched"] and not c["token_correct"] and c["case_id"] in refit)
    assert n_refit_join == 138, f"refit join {n_refit_join}/138"
    return cases, {c["case_id"]: c["y_b"] for c in cases}, refit


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------
def roc_curve(scores: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """ROC points (FPR, TPR) from pooled sorted scores; AUC = Mann-Whitney."""
    pos = scores[labels == 1]
    neg = scores[labels == 0]
    # Mann-Whitney AUC with tie correction.
    wins = sum(float(np.sum(p > neg)) + 0.5 * float(np.sum(p == neg)) for p in pos)
    auc = wins / (len(pos) * len(neg))
    thresholds = np.unique(scores)[::-1]
    tpr = np.concatenate(([0.0], [np.mean(pos >= t) for t in thresholds], [1.0]))
    fpr = np.concatenate(([0.0], [np.mean(neg >= t) for t in thresholds], [1.0]))
    order = np.argsort(fpr)
    return fpr[order], tpr[order], float(auc)


def win_tie_lose(y_policy: np.ndarray, y_base: np.ndarray) -> dict:
    d = y_policy - y_base
    return {
        "win": int(np.sum(d > TIE_TOL)),
        "tie": int(np.sum(np.abs(d) <= TIE_TOL)),
        "lose": int(np.sum(d < -TIE_TOL)),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    cases, _, refit = load_cases()
    n = len(cases)
    conf = np.array([c["confidence"] for c in cases])
    mm = np.array([c["prior_mismatch"] for c in cases])
    y_a = np.array([c["y_a"] for c in cases])
    y_b = np.array([c["y_b"] for c in cases])

    print("sanity: head of the aggregated per-case frame")
    print(f"{'case_id':<12} {'det_class':<7} {'family_token':<13} {'conf':>6} "
          f"{'obs_h':>7} {'H_fam':>6} {'mismatch':>8} {'y_A':>6} {'y_B':>6}")
    for c in cases[:5]:
        print(f"{c['case_id']:<12} {c['det_class']:<7} {c['family_token']:<13} "
              f"{c['confidence']:>6.3f} {c['obs_height_m']:>7.2f} {c['h_family_m']:>6.1f} "
              f"{c['prior_mismatch']:>8.3f} {c['y_a']:>6.3f} {c['y_b']:>6.3f}")
    print(f"sanity OK: {n} cases, no NaNs, matched 217 = 138 wrong + 79 correct, refit join 138/138")
    print(f"H_family (derived from frozen graphs at nominal theta): "
          f"{json.dumps({k: round(v, 3) for k, v in H_FAMILY.items()})}")

    # --- frozen grids ------------------------------------------------------
    mm_lo, mm_hi = float(mm.min()), float(mm.max())
    assert mm_hi > mm_lo, "degenerate prior_mismatch signal"
    mm_grid = np.linspace(mm_lo, mm_hi, N_GRID)

    policies: dict[str, dict] = {}
    masks: dict[str, np.ndarray] = {}

    def add_policy(name: str, route_b: np.ndarray, rule: str, family: str) -> None:
        y = np.where(route_b, y_b, y_a)
        masks[name] = route_b
        policies[name] = {"rule": rule, "family": family, "route_b": route_b, "y": y,
                          "median": float(np.median(y)), "cov_sppa": float(1.0 - route_b.mean())}

    add_policy("always_sppa", np.zeros(n, dtype=bool), "all -> SPPA", "fixed")
    add_policy("always_proxy", np.ones(n, dtype=bool), "all -> proxy", "fixed")
    oracle_b = y_b > y_a  # ties -> SPPA (protocol)
    add_policy("oracle", oracle_b, "per-case argmax (upper bound)", "oracle")
    for tau in CONF_GRID:
        key = f"conf_tau_{tau:.4f}"
        add_policy(key, conf < tau, f"conf < {tau:.4f} -> proxy", "conf")
        policies[key]["threshold"] = float(tau)
    for mu in mm_grid:
        key = f"mismatch_mu_{mu:.4f}"
        add_policy(key, mm > mu, f"mismatch > {mu:.4f} -> proxy", "mismatch")
        policies[key]["threshold"] = float(mu)

    # Best single-signal thresholds (selection on the frozen grid = frozen procedure).
    tau_key = max((k for k, p in policies.items() if p["family"] == "conf"),
                  key=lambda k: policies[k]["median"])
    mu_key = max((k for k, p in policies.items() if p["family"] == "mismatch"),
                 key=lambda k: policies[k]["median"])
    tau_best = float(policies[tau_key]["threshold"])
    mu_best = float(policies[mu_key]["threshold"])
    add_policy("conf_best", conf < tau_best, f"conf < {tau_best:.4f} -> proxy", "conf_best")
    add_policy("mismatch_best", mm > mu_best, f"mismatch > {mu_best:.4f} -> proxy", "mismatch_best")
    add_policy("and_best", (conf < tau_best) & (mm > mu_best),
               f"conf < {tau_best:.4f} AND mismatch > {mu_best:.4f} -> proxy", "combined")
    add_policy("or_best", (conf < tau_best) | (mm > mu_best),
               f"conf < {tau_best:.4f} OR mismatch > {mu_best:.4f} -> proxy", "combined")

    routed = {k: p for k, p in policies.items() if p["family"] in ("conf_best", "mismatch_best", "combined")}
    best_name = max(routed, key=lambda k: routed[k]["median"])
    best = policies[best_name]

    # --- paired bootstrap (protocol section 5) ------------------------------
    names = list(policies)
    P = np.stack([policies[k]["y"] for k in names], axis=1)
    d_best_a = best["y"] - y_a
    d_best_b = best["y"] - y_b
    rng = np.random.default_rng(SEED)
    boot = np.empty((N_BOOT, len(names)))
    boot_da = np.empty(N_BOOT)
    boot_db = np.empty(N_BOOT)
    for i in range(N_BOOT):
        idx = rng.integers(0, n, n)
        boot[i] = np.median(P[idx], axis=0)
        boot_da[i] = np.median(d_best_a[idx])
        boot_db[i] = np.median(d_best_b[idx])
    ci = {k: (float(np.percentile(boot[:, j], 2.5)), float(np.percentile(boot[:, j], 97.5)))
          for j, k in enumerate(names)}
    ci_da = (float(np.percentile(boot_da, 2.5)), float(np.percentile(boot_da, 97.5)))
    ci_db = (float(np.percentile(boot_db, 2.5)), float(np.percentile(boot_db, 97.5)))

    for k, p in policies.items():
        p["ci95"] = ci[k]
        p["n_to_sppa"] = int(n - int(p["route_b"].sum()))
        p["n_to_proxy"] = int(p["route_b"].sum())
        del p["route_b"], p["y"]  # not JSON-serializable; recomputed below if needed

    y_best = np.where(masks[best_name], y_b, y_a)
    wtl = {
        "best_vs_always_sppa": win_tie_lose(y_best, y_a),
        "best_vs_always_proxy": win_tie_lose(y_best, y_b),
        "oracle_vs_always_sppa": win_tie_lose(np.where(oracle_b, y_b, y_a), y_a),
        "oracle_vs_always_proxy": win_tie_lose(np.where(oracle_b, y_b, y_a), y_b),
    }

    # --- wrong-token arm (protocol section 6) -------------------------------
    matched = [c for c in cases if c["matched"]]
    labels = np.array([0 if c["token_correct"] else 1 for c in matched])
    m_conf = np.array([c["confidence"] for c in matched])
    m_mm = np.array([c["prior_mismatch"] for c in matched])
    m_obsh = np.array([c["obs_height_m"] for c in matched])
    fpr_c, tpr_c, auc_c = roc_curve(-m_conf, labels)   # declared: LOW conf -> wrong
    fpr_m, tpr_m, auc_m = roc_curve(m_mm, labels)      # declared: HIGH mismatch -> wrong
    _, _, auc_h = roc_curve(-m_obsh, labels)           # secondary raw signal

    def wt_rate(mask: np.ndarray) -> dict:
        sel = labels[mask]
        return {"n": int(mask.sum()), "n_wrong": int(sel.sum()),
                "wrong_rate": float(sel.mean()) if mask.sum() else None}

    token_arm = {
        "n_matched": len(matched),
        "n_wrong": int(labels.sum()),
        "n_correct": int((1 - labels).sum()),
        "auc_neg_confidence": auc_c,
        "auc_prior_mismatch": auc_m,
        "auc_neg_obs_height_m_secondary": auc_h,
        "below_tau_star": wt_rate(m_conf < tau_best),
        "above_eq_tau_star": wt_rate(m_conf >= tau_best),
        "above_mu_star": wt_rate(m_mm > mu_best),
        "below_eq_mu_star": wt_rate(m_mm <= mu_best),
    }

    # --- token-routing interaction (protocol section 7) ---------------------
    wrong_idx = [i for i, c in enumerate(cases) if c["matched"] and not c["token_correct"]]
    route_b_best = masks[best_name]
    n_away = sum(1 for i in wrong_idx if route_b_best[i])
    kept = [cases[i] for i in wrong_idx if not route_b_best[i]]  # routed TO SPPA
    real_tok = np.array([c["y_a"] for c in kept])
    corr_tok = np.array([refit[c["case_id"]] for c in kept])
    d_tok = corr_tok - real_tok
    boot_dt = np.empty(N_BOOT)
    if len(kept) > 0:
        for i in range(N_BOOT):
            idx = rng.integers(0, len(kept), len(kept))
            boot_dt[i] = np.median(d_tok[idx])
        ci_dt = (float(np.percentile(boot_dt, 2.5)), float(np.percentile(boot_dt, 97.5)))
    else:
        ci_dt = (None, None)
    interaction = {
        "best_policy": best_name,
        "n_wrong_token": len(wrong_idx),
        "n_routed_away_from_sppa": int(n_away),
        "frac_routed_away": float(n_away / len(wrong_idx)),
        "n_routed_to_sppa": len(kept),
        "real_token_median": float(np.median(real_tok)) if len(kept) else None,
        "correct_token_median": float(np.median(corr_tok)) if len(kept) else None,
        "median_diff_correct_minus_real": float(np.median(d_tok)) if len(kept) else None,
        "median_diff_ci95": ci_dt,
    }

    # --- JSON ----------------------------------------------------------------
    out = {
        "label": "E10 measured mode routing - exploratory post-hoc analysis (not confirmatory)",
        "protocol": "e10_protocol.md (frozen 2026-07-19 before computing outcomes)",
        "seed": SEED, "n_boot": N_BOOT, "n_cases": n,
        "arms": {"A": ARM_A, "B": ARM_B},
        "h_family_m": H_FAMILY,
        "grids": {"conf": [float(v) for v in CONF_GRID],
                  "mismatch": [float(v) for v in mm_grid]},
        "tau_star": tau_best, "mu_star": mu_best, "best_policy": best_name,
        "policies": {k: {kk: vv for kk, vv in p.items()} for k, p in policies.items()},
        "paired_median_diff": {
            "best_minus_always_sppa": {"median": float(np.median(d_best_a)), "ci95": ci_da},
            "best_minus_always_proxy": {"median": float(np.median(d_best_b)), "ci95": ci_db},
        },
        "win_tie_lose": wtl,
        "token_arm": token_arm,
        "token_routing_interaction": interaction,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_JSON}")

    # --- LaTeX table (booktabs, real_stream_main_table.tex pattern) ----------
    def row(label: str, key: str) -> str:
        p = policies[key]
        lo, hi = p["ci95"]
        return (f"{label} & {p['rule']} & {100 * p['cov_sppa']:.1f}\\% & "
                f"{p['median']:.3f} [{lo:.3f}, {hi:.3f}] \\\\")

    lines = [
        "% E10 measured mode routing - exploratory post-hoc (not confirmatory).",
        "% n = 1902 real-stream cases; outcome = 2D reprojection IoU of the routed method.",
        "% CIs: case-level paired bootstrap, 10 000 resamples, seed 20260719.",
        "\\begin{tabular}{@{}llcc@{}}",
        "\\toprule",
        "Policy & Rule & Cov. $\\to$ SPPA & 2D reproj. IoU med. [95\\% CI] \\\\",
        "\\midrule",
        row("Always SPPA-MVFit", "always_sppa"),
        row("Always proxy (OBB)", "always_proxy"),
        row("Oracle (upper bound)", "oracle"),
        "\\midrule",
        row("Best conf. threshold", "conf_best"),
        row("Best mismatch threshold", "mismatch_best"),
        row("Best combined (AND)", "and_best"),
        row("Best combined (OR)", "or_best"),
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ]
    OUT_TEX.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_TEX}")

    # --- Figure (2 panels, JGSA style) ---------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.2, 3.6))
    conf_meds = [policies[f"conf_tau_{t:.4f}"]["median"] for t in CONF_GRID]
    mm_meds = [policies[f"mismatch_mu_{m:.4f}"]["median"] for m in mm_grid]
    ax1.plot(CONF_GRID, conf_meds, color=OI["blue"], lw=1.6, marker="o", ms=3,
             label="route by conf $<\\tau$")
    ax1.axhline(policies["always_sppa"]["median"], color=OI["black"], lw=0.9, ls=":",
                label=f"always SPPA ({policies['always_sppa']['median']:.3f})")
    ax1.axhline(policies["always_proxy"]["median"], color=OI["gray"], lw=0.9, ls="--",
                label=f"always proxy ({policies['always_proxy']['median']:.3f})")
    ax1.axhline(policies["oracle"]["median"], color=OI["bluish_green"], lw=0.9, ls="-.",
                label=f"oracle ({policies['oracle']['median']:.3f})")
    ax1.axvline(tau_best, color=OI["blue"], lw=0.7, alpha=0.4)
    ax1.set_xlabel("confidence threshold $\\tau$ (blue, bottom)", fontsize=7, color=OI["blue"])
    ax1.set_ylabel("Median 2D reprojection IoU", fontsize=7)
    ax1.tick_params(labelsize=6)
    ax1_top = ax1.twiny()
    ax1_top.plot(mm_grid, mm_meds, color=OI["vermillion"], lw=1.6, marker="s", ms=3,
                 label="route by mismatch $>\\mu$")
    ax1_top.axvline(mu_best, color=OI["vermillion"], lw=0.7, alpha=0.4)
    ax1_top.set_xlabel("prior-mismatch threshold $\\mu$ (red, top)", fontsize=7,
                       color=OI["vermillion"])
    ax1_top.tick_params(labelsize=6, colors=OI["vermillion"])
    ax1.tick_params(axis="x", colors=OI["blue"])
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax1_top.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, fontsize=5.5, loc="lower right", framealpha=0.9)
    ax1.set_title("(a) Median reproj. IoU vs routing threshold", fontsize=8)

    ax2.plot(fpr_c, tpr_c, color=OI["blue"], lw=1.6,
             label=f"$-$confidence (AUC = {auc_c:.3f})")
    ax2.plot(fpr_m, tpr_m, color=OI["vermillion"], lw=1.6,
             label=f"prior mismatch (AUC = {auc_m:.3f})")
    ax2.plot([0, 1], [0, 1], color=OI["gray"], lw=0.9, ls="--", label="chance")
    ax2.set_xlabel("False positive rate", fontsize=7)
    ax2.set_ylabel("True positive rate", fontsize=7)
    ax2.set_title("(b) Wrong-token separation (217 GT-matched)", fontsize=8)
    ax2.legend(fontsize=6, loc="lower right")
    ax2.tick_params(labelsize=6)
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1.02)
    fig.suptitle("E10 measured mode routing — real detector stream, exploratory post-hoc (not sealed)",
                 fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(OUT_FIG, dpi=300, bbox_inches="tight")
    print(f"saved {OUT_FIG}")

    # --- console digest -------------------------------------------------------
    digest = {
        "always_sppa": policies["always_sppa"]["median"],
        "always_proxy": policies["always_proxy"]["median"],
        "oracle": policies["oracle"]["median"],
        "best_policy": best_name,
        "best_median": best["median"],
        "tau_star": tau_best, "mu_star": mu_best,
        "diff_best_minus_sppa": out["paired_median_diff"]["best_minus_always_sppa"],
        "diff_best_minus_proxy": out["paired_median_diff"]["best_minus_always_proxy"],
        "auc_neg_conf": auc_c, "auc_mismatch": auc_m,
        "interaction": interaction,
    }
    print(json.dumps(digest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
