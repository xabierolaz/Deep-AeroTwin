"""T2 - Generic-graph-without-fitting cell and the 2x2 graph x fitting table.

Exploratory post-hoc analysis (not confirmatory).

The missing fourth cell of the 2x2 design is the generic graph evaluated with
the default parameter vector theta0 = default_theta() = [0,0,0,1,0], i.e. the
prior geometry with NO observation evidence. This mirrors the sealed
sppa_text_only method, which also ignores the masks and uses theta0 (see
method/sppa_mvfit.py infer_method: sppa_text_only returns
build_actor(family, default_theta())). We therefore use theta0 with no
mask-driven initialization as the "no-fit" cell for the generic graph:
build_actor('generic', default_theta()) voxelized at 64^3 with the sealed
method voxelizer, compared against the released private GT re-voxelized with
the sealed source voxelizer.

The other three cells come from the sealed raw_metrics.csv (clean condition):
  SPPA-fit     = sppa_mvfit      clean mean ~ 0.557
  SPPA-nofit   = sppa_text_only  clean mean ~ 0.427 (condition-independent)
  Generic-fit  = generic_mvfit   clean mean ~ 0.367
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from common import (  # noqa: E402
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    STRATA,
    fmt,
    load_private_actors,
    load_raw_rows,
    stratified_paired_bootstrap,
    write_json,
    write_tex,
)
from method.sppa_mvfit import build_actor, default_theta, voxelize_actor  # noqa: E402
from source.source_generators import voxelize_source  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
CELLS = ("generic_nofit", "generic_fit", "sppa_nofit", "sppa_fit")
CELL_LABELS = {
    "generic_nofit": "Generic graph, no fit ($\\theta_0$ prior)",
    "generic_fit": "Generic graph, MVFit",
    "sppa_nofit": "SPPA family graph, no fit ($\\theta_0$ prior)",
    "sppa_fit": "SPPA family graph, MVFit",
}


def effect(pairs, label, seed):
    result = stratified_paired_bootstrap(pairs, seed=seed, resamples=BOOTSTRAP_RESAMPLES)
    result["effect"] = label
    return result


def main() -> int:
    rows = load_raw_rows()
    clean = [row for row in rows if row["condition"] == "clean"]

    # --- sealed per-actor values for the three fitted/prior cells ----------
    per_case: dict[str, dict] = {}
    for row in clean:
        per_case.setdefault(row["case_id"], {"family": row["family"], "stratum": row["stratum"]})
        if row["method"] == "sppa_mvfit":
            per_case[row["case_id"]]["sppa_fit"] = row["voxel_iou"]
        elif row["method"] == "generic_mvfit":
            per_case[row["case_id"]]["generic_fit"] = row["voxel_iou"]
        elif row["method"] == "sppa_text_only":
            per_case[row["case_id"]]["sppa_nofit"] = row["voxel_iou"]
    assert len(per_case) == 240 and all(len(v) == 5 for v in per_case.values())

    # --- NEW cell: generic graph at default theta, voxelized 64^3 ----------
    actors = load_private_actors()
    generic_prior = voxelize_actor(build_actor("generic", default_theta()), 64)
    for case_id, entry in per_case.items():
        gt = voxelize_source(actors[case_id], 64)
        union = int(np.count_nonzero(gt | generic_prior))
        inter = int(np.count_nonzero(gt & generic_prior))
        entry["generic_nofit"] = 1.0 if union == 0 else inter / union

    def cell_mean(cell, subset=None):
        values = [entry[cell] for entry in per_case.values() if subset is None or entry["stratum"] == subset]
        return float(np.mean(values))

    # --- sanity checks against the sealed/known values ---------------------
    assert abs(cell_mean("sppa_fit") - 0.5574) < 0.001
    assert abs(cell_mean("generic_fit") - 0.3674) < 0.001
    assert abs(cell_mean("sppa_nofit") - 0.427) < 0.001

    # --- decomposition, overall and per stratum ----------------------------
    def paired(cell_a, cell_b, stratum=None):
        return [
            (entry["family"], entry["stratum"], entry[cell_a], entry[cell_b])
            for entry in per_case.values()
            if stratum is None or entry["stratum"] == stratum
        ]

    effects: dict[str, dict] = {}
    effects["overall"] = {
        "graph_effect_nofit": effect(paired("sppa_nofit", "generic_nofit"), "SPPA-nofit - Generic-nofit", BOOTSTRAP_SEED),
        "fitting_effect_generic": effect(paired("generic_fit", "generic_nofit"), "Generic-fit - Generic-nofit", BOOTSTRAP_SEED),
        "fitting_effect_sppa": effect(paired("sppa_fit", "sppa_nofit"), "SPPA-fit - SPPA-nofit", BOOTSTRAP_SEED),
        "graph_effect_fit": effect(paired("sppa_fit", "generic_fit"), "SPPA-fit - Generic-fit (headline)", BOOTSTRAP_SEED),
    }
    ov = effects["overall"]
    interaction = (
        ov["fitting_effect_sppa"]["mean_difference"] - ov["fitting_effect_generic"]["mean_difference"]
    )
    for stratum in STRATA:
        effects[stratum] = {
            "graph_effect_nofit": effect(paired("sppa_nofit", "generic_nofit", stratum), "SPPA-nofit - Generic-nofit", BOOTSTRAP_SEED),
            "fitting_effect_generic": effect(paired("generic_fit", "generic_nofit", stratum), "Generic-fit - Generic-nofit", BOOTSTRAP_SEED),
            "fitting_effect_sppa": effect(paired("sppa_fit", "sppa_nofit", stratum), "SPPA-fit - SPPA-nofit", BOOTSTRAP_SEED),
            "graph_effect_fit": effect(paired("sppa_fit", "generic_fit", stratum), "SPPA-fit - Generic-fit (headline)", BOOTSTRAP_SEED),
        }

    cell_means = {
        "overall": {cell: cell_mean(cell) for cell in CELLS},
        **{stratum: {cell: cell_mean(cell, stratum) for cell in CELLS} for stratum in STRATA},
    }

    payload = {
        "schema": "sppa-mvfit-posthoc-graph-x-fitting-2x2-v1",
        "analysis_type": "exploratory post-hoc analysis (not confirmatory)",
        "condition": "clean",
        "actors": 240,
        "new_cell_definition": (
            "generic_nofit = voxelize_actor(build_actor('generic', default_theta()), 64) vs "
            "voxelize_source(private GT, 64); theta0 = [0,0,0,1,0]; no mask-driven "
            "initialization, mirroring sealed sppa_text_only which also ignores masks"
        ),
        "sources": {
            "generic_nofit": "NEW: computed from sealed method module + released private GT",
            "other_cells": "sealed raw_metrics.csv clean rows",
        },
        "cell_mean_voxel_iou": cell_means,
        "effects": effects,
        "interaction_overall": interaction,
        "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED, "stratification": "family x stratum cells"},
    }
    write_json(OUT_DIR / "graph_x_fitting_2x2.json", payload)

    # --- LaTeX: 2x2 table ---------------------------------------------------
    m = cell_means["overall"]
    lines = [
        r"\begin{tabular}{@{}lrrr@{}}",
        r"\toprule",
        r"Graph prior & No fit ($\theta_0$) & MVFit & Fitting effect \\",
        r"\midrule",
        f"Generic graph & {fmt(m['generic_nofit'])} & {fmt(m['generic_fit'])} & "
        f"{fmt(ov['fitting_effect_generic']['mean_difference'])} \\\\",
        f"SPPA family graph & {fmt(m['sppa_nofit'])} & {fmt(m['sppa_fit'])} & "
        f"{fmt(ov['fitting_effect_sppa']['mean_difference'])} \\\\",
        r"\midrule",
        f"Graph effect (SPPA $-$ Generic) & {fmt(ov['graph_effect_nofit']['mean_difference'])} & "
        f"{fmt(ov['graph_effect_fit']['mean_difference'])} & {fmt(interaction)} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        "",
    ]
    write_tex(OUT_DIR / "graph_x_fitting_2x2_table.tex", "\n".join(lines))

    # --- LaTeX: effects with CIs, overall + per stratum ---------------------
    effect_rows = [
        ("graph_effect_nofit", r"Graph effect at no-fit"),
        ("fitting_effect_generic", r"Fitting effect, generic graph"),
        ("fitting_effect_sppa", r"Fitting effect, SPPA family graph"),
        ("graph_effect_fit", r"Total (SPPA-fit $-$ Generic-fit)"),
    ]
    lines = [
        r"\begin{tabular}{@{}lrrr@{}}",
        r"\toprule",
        r"Effect & Estimate & 95\% CI & $n$ \\",
        r"\midrule",
    ]
    for key, label in effect_rows:
        e = ov[key]
        lines.append(
            f"{label} & {fmt(e['mean_difference'])} & "
            f"[{fmt(e['ci95_low_percentile'])}, {fmt(e['ci95_high_percentile'])}] & {e['actor_count']} \\\\"
        )
    lines.append(f"Interaction (fitting$\\times$graph) & {fmt(interaction)} & -- & 240 \\\\")
    lines += [r"\midrule", r"\multicolumn{4}{@{}l@{}}{\emph{By stratum}}\\"]
    for stratum in STRATA:
        for key, label in effect_rows:
            e = effects[stratum][key]
            tag = "CSG-ID" if stratum == "csg_id" else "Implicit-OOD"
            lines.append(
                f"{label} ({tag}) & {fmt(e['mean_difference'])} & "
                f"[{fmt(e['ci95_low_percentile'])}, {fmt(e['ci95_high_percentile'])}] & {e['actor_count']} \\\\"
            )
    lines += [r"\bottomrule", r"\end{tabular}", ""]
    write_tex(OUT_DIR / "graph_x_fitting_effects_table.tex", "\n".join(lines))

    print("cell means:", {k: round(v, 4) for k, v in m.items()})
    for key, _ in effect_rows:
        e = ov[key]
        print(f"{key:24s} {e['mean_difference']:.4f} [{e['ci95_low_percentile']:.4f}, {e['ci95_high_percentile']:.4f}]")
    print(f"{'interaction':24s} {interaction:.4f}")
    for stratum in STRATA:
        print(stratum, {k: round(v, 4) for k, v in cell_means[stratum].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
