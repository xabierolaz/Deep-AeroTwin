"""E7 "Real Stream Wave" - aggregation + LaTeX table (exploratory post-hoc).

Reads results.jsonl (one row per case x method) and writes:
  * e7_analysis.json      - all numbers used in the report / figure / table
  * real_stream_table.tex - booktabs tabular in the paper pattern (cf. e3_obb)

Run:  python analyze_e7.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

E7_ROOT = Path(__file__).resolve().parent
RESULTS = E7_ROOT / "results.jsonl"
OUT_JSON = E7_ROOT / "e7_analysis.json"
OUT_TEX = E7_ROOT / "real_stream_table.tex"

METHODS = ("sppa_mvfit", "generic_mvfit", "obb", "aabb", "visual_hull", "capsule")
METHOD_LABELS = {
    "sppa_mvfit": "SPPA-MVFit (this work)",
    "generic_mvfit": "Generic-MVFit",
    "obb": "OBB",
    "aabb": "AABB",
    "visual_hull": "Visual hull (non-semantic)",
    "capsule": "Capsule",
}


def stats(values: list[float]) -> dict:
    arr = np.asarray(values, dtype=float)
    return {"n": int(arr.size), "median": float(np.median(arr)),
            "p25": float(np.percentile(arr, 25)), "p75": float(np.percentile(arr, 75)),
            "mean": float(arr.mean())}


def main() -> int:
    rows = [json.loads(line) for line in RESULTS.open(encoding="utf-8")]
    analysis: dict = {"label": "exploratory post-hoc analysis (not confirmatory)"}

    per_method: dict[str, dict] = {}
    for method in METHODS:
        sel = [r for r in rows if r["method"] == method]
        matched = [r for r in sel if r["matched"]]
        tok_ok = [r for r in matched if r["token_correct"]]
        tok_bad = [r for r in matched if not r["token_correct"]]
        entry = {
            "n_cases": len(sel),
            "n_matched": len(matched),
            "n_matched_token_correct": len(tok_ok),
            "n_matched_wrong_token": len(tok_bad),
            "loc_err_3d_m": stats([r["loc_err_3d_m"] for r in matched if r["loc_err_3d_m"] is not None]),
            "loc_err_3d_m_token_correct": stats([r["loc_err_3d_m"] for r in tok_ok if r["loc_err_3d_m"] is not None]),
            "loc_err_3d_m_wrong_token": stats([r["loc_err_3d_m"] for r in tok_bad if r["loc_err_3d_m"] is not None]),
            "footprint_iou": stats([r["footprint_iou"] for r in matched if r["footprint_iou"] is not None]),
            "reproj_iou": stats([r["reproj_iou"] for r in sel]),
            "latency_ms": stats([r["latency_ms"] for r in sel]),
            "per_class": {},
        }
        for cls in ("tower", "cow", "biker"):
            cls_sel = [r for r in sel if r["det_class"] == cls]
            entry["per_class"][cls] = {
                "n_cases": len(cls_sel),
                "reproj_iou": stats([r["reproj_iou"] for r in cls_sel]),
            }
        per_method[method] = entry
    analysis["per_method"] = per_method

    # Observation error floor: distance footprint center -> matched GT anchor.
    sppa = [r for r in rows if r["method"] == "sppa_mvfit" and r["matched"]]
    # (match distance is identical for every method; stored implicitly via loc of OBB-centred proxies
    #  but recomputed here from case join would need e7_common; use token-correct tower split only)
    analysis["matched_composition"] = {
        "tower_tower": sum(1 for r in sppa if r["det_class"] == "tower" and r["gt_class"] == "tower"),
        "cow_tower": sum(1 for r in sppa if r["det_class"] == "cow" and r["gt_class"] == "tower"),
        "biker_tower": sum(1 for r in sppa if r["det_class"] == "biker" and r["gt_class"] == "tower"),
        "any_cow_anchor": sum(1 for r in sppa if r["gt_class"] == "cow"),
    }

    # Token arm (SPPA only): wrong-token matched cases, real vs correct-token refit.
    wrong = [r for r in rows if r["method"] == "sppa_mvfit" and r["matched"] and not r["token_correct"]]
    refit = {r["case_id"]: r for r in rows if r["method"] == "sppa_mvfit_correct_token"}
    analysis["token_arm"] = {
        "n_wrong_token_matched": len(wrong),
        "real_token_reproj_iou": stats([r["reproj_iou"] for r in wrong]),
        "correct_token_reproj_iou": stats([refit[r["case_id"]]["reproj_iou"] for r in wrong if r["case_id"] in refit]),
    }

    OUT_JSON.write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------ tex
    def med_iqr(d: dict, digits: int = 2) -> str:
        return f"{d['median']:.{digits}f} [{d['p25']:.{digits}f}, {d['p75']:.{digits}f}]"

    lines = [
        "% E7 Real Stream Wave - exploratory post-hoc (not confirmatory).",
        "% Loc./footprint columns: GT-matched subset (n=217, tower anchors; wrong detector",
        "% tokens kept as a natural condition). Reprojection/latency: all n=1902 cases.",
        "\\begin{tabular}{@{}lrrrrr@{}}",
        "\\toprule",
        "Method & $n$ & Loc. err. 3D med. [P25, P75] (m)$^{\\dagger}$ & Footprint IoU$^{\\dagger}$ & 2D reproj. IoU & Latency (ms) \\\\",
        "\\midrule",
    ]
    for method in METHODS:
        e = per_method[method]
        lines.append(
            f"{METHOD_LABELS[method]} & {e['n_cases']} & {med_iqr(e['loc_err_3d_m'])} & "
            f"{e['footprint_iou']['median']:.3f} & {med_iqr(e['reproj_iou'], 3)} & {e['latency_ms']['median']:.2f} \\\\"
        )
    lines += [
        "\\bottomrule",
        "\\end{tabular}",
        "",
        "% Token arm (SPPA-MVFit only): the 138 GT-matched cases where the REAL detector",
        "% emitted a wrong family token (114 cow->tower, 24 biker->tower confusions).",
        "\\begin{tabular}{@{}lrr@{}}",
        "\\toprule",
        "Token condition & $n$ & 2D reproj. IoU med. [P25, P75] \\\\",
        "\\midrule",
    ]
    ta = analysis["token_arm"]
    lines.append(
        f"Real detector token (wrong) & {ta['n_wrong_token_matched']} & {med_iqr(ta['real_token_reproj_iou'], 3)} \\\\"
    )
    lines.append(
        f"Correct-token refit (counterfactual) & {ta['n_wrong_token_matched']} & {med_iqr(ta['correct_token_reproj_iou'], 3)} \\\\"
    )
    lines += ["\\bottomrule", "\\end{tabular}", ""]
    OUT_TEX.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_JSON} and {OUT_TEX}")
    print(json.dumps({m: {"reproj_med": round(per_method[m]["reproj_iou"]["median"], 3),
                          "loc_med": round(per_method[m]["loc_err_3d_m"]["median"], 2)}
                      for m in METHODS}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
