"""Export family×stratum table and regenerate confirmatory analysis with valid null-centered p.

H1 CI decision fields are recomputed from raw_metrics with the same seed/resamples.
Does not re-run methods or re-seal predictions.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
PAPER = PACKAGE.parents[1]
RESULTS = PACKAGE / "results" / "test"
BENCH = PAPER / "benchmarks" / "results"


def bootstrap(rows: list[dict], method_a: str, method_b: str, seed: int = 77157, resamples: int = 10000) -> dict:
    by_case: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        if row["condition"] == "clean":
            by_case[row["case_id"]][row["method"]] = row
    strata: dict[tuple[str, str], list[float]] = defaultdict(list)
    for pair in by_case.values():
        if method_a in pair and method_b in pair:
            a, b = pair[method_a], pair[method_b]
            strata[(a["family"], a["stratum"])].append(float(a["voxel_iou"]) - float(b["voxel_iou"]))
    cells = [np.asarray(values, dtype=np.float64) for _, values in sorted(strata.items())]
    keys = list(sorted(strata.keys()))
    observed = float(np.mean([c.mean() for c in cells]))
    rng = np.random.default_rng(seed)
    draws = np.empty(resamples, dtype=np.float64)
    null = np.empty(resamples, dtype=np.float64)
    for index in range(resamples):
        draws[index] = float(np.mean([rng.choice(c, size=len(c), replace=True).mean() for c in cells]))
        null[index] = float(np.mean([rng.choice(c - c.mean(), size=len(c), replace=True).mean() for c in cells]))
    return {
        "mean_difference": observed,
        "ci95_low_percentile": float(np.quantile(draws, 0.025)),
        "ci95_high_percentile": float(np.quantile(draws, 0.975)),
        "bootstrap_resamples": resamples,
        "bootstrap_seed": seed,
        "actor_count": int(sum(len(c) for c in cells)),
        "stratum_counts": {"|".join(k): int(len(v)) for k, v in sorted(strata.items())},
        "stratum_point_estimates": {"|".join(k): float(np.mean(v)) for k, v in sorted(strata.items())},
        "null_centered_two_sided_p": float(np.mean(np.abs(null) >= abs(observed))),
    }


def main() -> int:
    rows = list(csv.DictReader((RESULTS / "raw_metrics.csv").open(encoding="utf-8")))
    primary = bootstrap(rows, "sppa_mvfit", "generic_mvfit")
    secondaries = {
        method: bootstrap(rows, "sppa_mvfit", method)
        for method in ("sppa_text_only", "bbox", "ellipsoid", "capsule", "billboard", "nonsemantic_visual_hull")
    }
    # Holm on valid null-centered p for six secondaries
    ordered = sorted(secondaries.items(), key=lambda item: item[1]["null_centered_two_sided_p"])
    holm: dict[str, float] = {}
    m = len(ordered)
    running = 0.0
    for rank, (method, result) in enumerate(ordered):
        adjusted = min(1.0, (m - rank) * result["null_centered_two_sided_p"])
        running = max(running, adjusted)
        holm[method] = running

    by_stratum: dict[str, list[float]] = defaultdict(list)
    for key, value in primary["stratum_point_estimates"].items():
        _, stratum = key.split("|", 1)
        by_stratum[stratum].append(value)
    ood = {key: float(np.mean(values)) for key, values in by_stratum.items()}
    sensitivity = json.loads((RESULTS / "resolution_sensitivity.json").read_text(encoding="utf-8"))

    report = {
        "schema": "sppa-mvfit-confirmatory-analysis-v2",
        "provenance": "synthetic_geometry",
        "primary_endpoint": "clean_64cubed_voxel_iou_sppa_mvfit_minus_generic_mvfit",
        "primary": primary,
        "h1_superiority_margin": 0.03,
        "h1_pass": primary["ci95_low_percentile"] > 0.03,
        "ood_stratum_point_estimates": ood,
        "ood_nonpositive_warning": ood.get("implicit_ood", 0.0) <= 0.0,
        "secondary_bootstrap": secondaries,
        "holm_adjusted_two_sided_p": holm,
        "p_value_definition": "null_centered_stratified_bootstrap_two_sided",
        "resolution_sensitivity": sensitivity,
        "interpretation": "A passing H1 interval is still synthetic internal evidence and does not establish real-world, geospatial, flight, or universal reconstruction validity.",
        "analysis_note": "v2 replaces invalid draws_two_sided_p with null-centered p; predictions were not re-sealed.",
    }
    (RESULTS / "confirmatory_summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    families = sorted({k.split("|")[0] for k in primary["stratum_point_estimates"]})
    lines = [
        r"\begin{tabular}{@{}lrrr@{}}",
        r"\toprule",
        r"Family & CSG-ID $\Delta$ & Implicit-OOD $\Delta$ & Mean $\Delta$ \\",
        r"\midrule",
    ]
    for family in families:
        a = primary["stratum_point_estimates"][f"{family}|csg_id"]
        b = primary["stratum_point_estimates"][f"{family}|implicit_ood"]
        label = family.replace("_", r"\_")
        lines.append(rf"{label} & {a:.3f} & {b:.3f} & {0.5 * (a + b):.3f} \\")
    lines.extend(
        [
            r"\midrule",
            rf"Equal-stratum aggregate & {ood['csg_id']:.3f} & {ood['implicit_ood']:.3f} & {primary['mean_difference']:.3f} \\",
            r"\bottomrule",
            r"\end{tabular}",
        ]
    )
    BENCH.mkdir(parents=True, exist_ok=True)
    (BENCH / "sppa_mvfit_family_strata.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "h1_pass": report["h1_pass"],
                "mean": primary["mean_difference"],
                "ci": [primary["ci95_low_percentile"], primary["ci95_high_percentile"]],
                "primary_p": primary["null_centered_two_sided_p"],
                "holm": holm,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
