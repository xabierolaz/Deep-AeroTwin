"""T4 - Failure analysis and local-search convergence.

Exploratory post-hoc analysis (not confirmatory).

(a) Failure rate (voxel IoU < 0.25) per family x stratum for sppa_mvfit clean,
    the failing case_ids, and the 10 worst cases per family (sealed CSV).
(b) lattice_tower failure hypothesis: inspect the source actors of the worst
    lattice_tower cases (component dimensions vs the 64^3 voxel cells
    0.15 x 0.10 x 0.10 world units) and quantify sub-voxel structure via a
    high-resolution (512^3) reference volume per component.
(c) Convergence of the frozen local search from sealed_method_outputs.jsonl
    metadata.trace (31 evaluations: init + 3 sweeps x 5 parameters x 2
    directions): improvement in the last sweep, theta-at-bound rate,
    improvement-per-evaluation curve (mean and p90), init-already-best rate.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

import common  # noqa: E402,F401  (sets sys.path for the sealed package)
from common import (  # noqa: E402
    FAMILIES,
    METHOD_LABELS,
    STRATA,
    VOXEL_SIZE,
    fmt,
    load_private_actors,
    load_raw_rows,
    load_sealed_records,
    write_json,
    write_tex,
)
from method.sppa_mvfit import BOUNDS  # noqa: E402
from source.source_generators import voxelize_source  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
FAIL_THRESHOLD = 0.25
WORLD_EXTENT = {"x": 9.6, "y": 6.4, "z": 6.4}
CELL_VOLUME = VOXEL_SIZE["x"] * VOXEL_SIZE["y"] * VOXEL_SIZE["z"]


def component_min_dims(component: dict) -> dict:
    """Human-readable minimum cross-section dims per component kind."""
    kind = component["kind"]
    if kind in {"box", "ellipsoid", "cylinder", "superellipsoid"}:
        size = [float(v) for v in component["size"]]
        return {"size": size, "min_dim": min(size)}
    if kind == "tube":
        radius = float(component["radius"])
        length = float(np.linalg.norm(np.asarray(component["p1"]) - np.asarray(component["p0"])))
        return {"diameter": 2 * radius, "length": length, "min_dim": 2 * radius}
    if kind == "tapered_extrusion":
        bottom = [float(v) for v in component["bottom"]]
        top = [float(v) for v in component["top"]]
        return {"bottom_full": bottom, "top_full": top, "min_dim": 2 * min(min(bottom), min(top))}
    if kind == "torus_y":
        return {"minor_diameter": 2 * float(component["minor"]), "min_dim": 2 * float(component["minor"])}
    return {"min_dim": float("nan")}


def component_capture(component: dict, hires: int = 512) -> dict:
    """Voxel capture of one component at 64^3 vs a 512^3 reference volume."""
    solo = {"components": [component]}
    vox64 = voxelize_source(solo, 64)
    vox_hi = voxelize_source(solo, hires)
    volume = float(np.count_nonzero(vox_hi)) * (WORLD_EXTENT["x"] / hires) * (WORLD_EXTENT["y"] / hires) * (WORLD_EXTENT["z"] / hires)
    expected_cells = volume / CELL_VOLUME
    hit = int(np.count_nonzero(vox64))
    return {
        "voxels_hit_64": hit,
        "reference_volume": volume,
        "expected_cells_64": expected_cells,
        "capture_ratio": (hit / expected_cells) if expected_cells > 0 else 1.0,
    }


def main() -> int:
    rows = load_raw_rows()
    sppa_clean = [row for row in rows if row["method"] == "sppa_mvfit" and row["condition"] == "clean"]
    assert len(sppa_clean) == 240

    # ---------------- (a) failure rates + worst cases ----------------------
    failures_by_cell: dict[str, dict] = {}
    for family in FAMILIES:
        for stratum in STRATA:
            subset = [row for row in sppa_clean if row["family"] == family and row["stratum"] == stratum]
            failing = [row for row in subset if row["voxel_iou"] < FAIL_THRESHOLD]
            failures_by_cell[f"{family}|{stratum}"] = {
                "n": len(subset),
                "failures": len(failing),
                "rate": len(failing) / len(subset),
                "case_ids": [row["case_id"] for row in sorted(failing, key=lambda r: r["voxel_iou"])],
            }
    family_worst: dict[str, list] = {}
    for family in FAMILIES:
        subset = sorted(
            [row for row in sppa_clean if row["family"] == family], key=lambda r: r["voxel_iou"]
        )[:10]
        family_worst[family] = [
            {
                "case_id": row["case_id"],
                "stratum": row["stratum"],
                "voxel_iou": row["voxel_iou"],
                "normalized_symmetric_chamfer": row["normalized_symmetric_chamfer"],
                "volume_error": row["volume_error"],
            }
            for row in subset
        ]
    worst_overall = sorted(sppa_clean, key=lambda r: r["voxel_iou"])[:10]

    # ---------------- (a3) other methods on the failing cases (context) -----
    failing_ids = sorted(
        {cid for key, cell in failures_by_cell.items() for cid in cell["case_ids"]}
    )
    other_methods_on_failures: dict[str, dict] = {}
    for case_id in failing_ids:
        subset = [row for row in rows if row["case_id"] == case_id and row["condition"] == "clean"]
        other_methods_on_failures[case_id] = {
            row["method"]: row["voxel_iou"] for row in subset
        }

    # ---------------- (b) lattice_tower sub-voxel inspection ---------------
    actors = load_private_actors()
    lattice_fail_ids = sorted(
        {cid for key, cell in failures_by_cell.items() if key.startswith("lattice_tower") for cid in cell["case_ids"]}
    )
    inspected: dict[str, dict] = {}
    for case_id in lattice_fail_ids[:3]:
        actor = actors[case_id]
        components = []
        for component in actor["components"]:
            dims = component_min_dims(component)
            capture = component_capture(component)
            components.append({"kind": component["kind"], **dims, **capture})
        total_vox = int(np.count_nonzero(voxelize_source(actor, 64)))
        inspected[case_id] = {
            "family": actor["family"],
            "stratum": actor["stratum"],
            "component_count": len(actor["components"]),
            "gt_voxels_64": total_vox,
            "components": components,
        }

    # ---------------- (c) convergence from sealed traces -------------------
    convergence: dict[str, dict] = {}
    for method in ("sppa_mvfit", "generic_mvfit"):
        per_case_best_curves: list[np.ndarray] = []
        last_sweep_improved = 0
        theta_at_bound = 0
        init_was_best = 0
        total_improvements: list[float] = []
        n = 0
        for record in load_sealed_records():
            if record["method"] != method or record["condition"] != "clean":
                continue
            trace = record["metadata"].get("trace")
            if not trace:
                continue
            n += 1
            objectives = np.asarray([entry["objective"] for entry in trace], dtype=np.float64)
            best = np.minimum.accumulate(objectives)
            per_case_best_curves.append(best)
            fractions = [entry.get("step_fraction") for entry in trace[1:]]
            last_fraction = max(f for f in fractions if f is not None)  # placeholder, replaced below
            last_fraction = min(f for f in fractions if f is not None)
            last_idx = [i + 1 for i, f in enumerate(fractions) if f == last_fraction]
            first_last = min(last_idx)
            if best[first_last - 1] - best[-1] > 1e-12:
                last_sweep_improved += 1
            if best[-1] >= objectives[0] - 1e-12:
                init_was_best += 1
            total_improvements.append(float(objectives[0] - best[-1]))
            theta = np.asarray(record["metadata"]["theta"], dtype=np.float64)
            if bool(np.any(np.abs(theta - BOUNDS[:, 0]) < 1e-9) or np.any(np.abs(theta - BOUNDS[:, 1]) < 1e-9)):
                theta_at_bound += 1
        curves = np.stack(per_case_best_curves)
        improvements = -np.diff(curves, axis=1)  # improvement at evaluation k=1..30
        convergence[method] = {
            "n_cases": n,
            "trace_length": int(curves.shape[1]),
            "last_sweep_step_fraction": 0.05,
            "last_sweep_improved_count": last_sweep_improved,
            "last_sweep_improved_rate": last_sweep_improved / n,
            "theta_at_bound_count": theta_at_bound,
            "theta_at_bound_rate": theta_at_bound / n,
            "init_already_best_count": init_was_best,
            "init_already_best_rate": init_was_best / n,
            "total_objective_improvement_mean": float(np.mean(total_improvements)),
            "total_objective_improvement_median": float(np.median(total_improvements)),
            "init_objective_mean": float(curves[:, 0].mean()),
            "final_objective_mean": float(curves[:, -1].mean()),
            "improvement_per_evaluation_mean": improvements.mean(axis=0).tolist(),
            "improvement_per_evaluation_p90": np.quantile(improvements, 0.9, axis=0).tolist(),
            "best_objective_curve_mean": curves.mean(axis=0).tolist(),
            "best_objective_curve_p10": np.quantile(curves, 0.1, axis=0).tolist(),
            "best_objective_curve_p90": np.quantile(curves, 0.9, axis=0).tolist(),
        }

    payload = {
        "schema": "sppa-mvfit-posthoc-failure-convergence-v1",
        "analysis_type": "exploratory post-hoc analysis (not confirmatory)",
        "failure_threshold_iou": FAIL_THRESHOLD,
        "failures_by_family_stratum": failures_by_cell,
        "family_worst10": family_worst,
        "worst_overall_10": [
            {"case_id": r["case_id"], "family": r["family"], "stratum": r["stratum"], "voxel_iou": r["voxel_iou"]}
            for r in worst_overall
        ],
        "lattice_tower_inspection": inspected,
        "all_methods_on_failing_cases": other_methods_on_failures,
        "voxel_cell_world_units": VOXEL_SIZE,
        "convergence": convergence,
    }
    write_json(OUT_DIR / "failure_analysis.json", payload)
    write_json(OUT_DIR / "convergence_stats.json", {
        "schema": "sppa-mvfit-posthoc-convergence-v1",
        "analysis_type": "exploratory post-hoc analysis (not confirmatory)",
        "condition": "clean",
        "trace": "metadata.trace of sealed_method_outputs.jsonl (evaluation 0 = init; 1-30 = candidates)",
        "convergence": convergence,
    })

    # ---------------- worst-cases LaTeX table ------------------------------
    lines = [
        r"\begin{tabular}{@{}lllrrr@{}}",
        r"\toprule",
        r"Case & Family & Stratum & IoU & Chamfer & Vol.\ err \\",
        r"\midrule",
    ]
    for row in worst_overall:
        lines.append(
            f"{row['case_id'].replace('_', r'\_')} & {row['family'].replace('_', r'\_')} & {row['stratum'].replace('_', r'\_')} & "
            f"{fmt(row['voxel_iou'])} & {fmt(row['normalized_symmetric_chamfer'])} & {fmt(row['volume_error'])} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", ""]
    write_tex(OUT_DIR / "worst_cases_table.tex", "\n".join(lines))

    # ---------------- failure_analysis.md ----------------------------------
    md: list[str] = [
        "# T4 — Failure analysis and local-search convergence",
        "",
        "**exploratory post-hoc analysis (not confirmatory)**",
        "",
        f"Failure = voxel IoU < {FAIL_THRESHOLD}, method sppa_mvfit, condition clean (n = 240).",
        "",
        "## (a) Failure rate by family × stratum",
        "",
        "| Family | Stratum | n | Failures | Rate | Case ids |",
        "|---|---|---|---|---|---|",
    ]
    for key, cell in failures_by_cell.items():
        family, stratum = key.split("|")
        ids = ", ".join(cell["case_ids"]) if cell["case_ids"] else "—"
        md.append(f"| {family} | {stratum} | {cell['n']} | {cell['failures']} | {cell['rate']:.3f} | {ids} |")
    md += ["", "## (a2) Ten worst cases per family (sppa_mvfit, clean)", ""]
    for family in FAMILIES:
        md.append(f"### {family}")
        md.append("")
        md.append("| # | case_id | stratum | voxel IoU | Chamfer | vol. err |")
        md.append("|---|---|---|---|---|---|")
        for rank, entry in enumerate(family_worst[family], 1):
            md.append(
                f"| {rank} | {entry['case_id']} | {entry['stratum']} | {entry['voxel_iou']:.4f} | "
                f"{entry['normalized_symmetric_chamfer']:.4f} | {entry['volume_error']:.4f} |"
            )
        md.append("")
    md += [
        "## (b) lattice_tower failure hypothesis: sub-voxel structure",
        "",
        f"Voxel cells at 64³: {VOXEL_SIZE['x']:.3f} (x) × {VOXEL_SIZE['y']:.3f} (y) × {VOXEL_SIZE['z']:.3f} (z) world units; "
        f"cell volume {CELL_VOLUME:.4f}. Components thinner than a cell can be missed by cell-centre sampling.",
        "",
    ]
    for case_id, info in inspected.items():
        md.append(f"### {case_id} ({info['stratum']}, {info['component_count']} components, GT {info['gt_voxels_64']} voxels)")
        md.append("")
        md.append("| kind | min dim (world) | min dim / cell | voxels hit @64³ | expected cells | capture ratio |")
        md.append("|---|---|---|---|---|---|")
        for comp in info["components"]:
            min_dim = comp["min_dim"]
            md.append(
                f"| {comp['kind']} | {min_dim:.3f} | {min_dim / VOXEL_SIZE['y']:.2f} | {comp['voxels_hit_64']} | "
                f"{comp['expected_cells_64']:.1f} | {comp['capture_ratio']:.3f} |"
            )
        md.append("")
    md += [
        "### All methods on the failing lattice_tower cases (clean voxel IoU)",
        "",
        "| case_id | " + " | ".join(METHOD_LABELS[m] for m in ("sppa_mvfit", "generic_mvfit", "sppa_text_only", "nonsemantic_visual_hull", "bbox", "ellipsoid", "capsule", "billboard")) + " |",
        "|---|" + "---|" * 8,
    ]
    for case_id, per_method in other_methods_on_failures.items():
        md.append(
            f"| {case_id} | "
            + " | ".join(f"{per_method[m]:.3f}" for m in ("sppa_mvfit", "generic_mvfit", "sppa_text_only", "nonsemantic_visual_hull", "bbox", "ellipsoid", "capsule", "billboard"))
            + " |"
        )
    md += [
        "",
        "**Interpretation (b).** The failing lattice_tower actors are built from",
        "legs and ring plates whose thickness (0.09–0.23 world units) is at or below",
        "the voxel cell size (0.10–0.15). The 512³-reference capture ratios are close",
        "to 1.0, so the components do NOT vanish at 64³ — but they are only 1–2 voxels",
        "thick, the whole GT occupies ~500–1100 voxels (0.2–0.4 % of the grid), and",
        "the IoU denominator is tiny. For 1-voxel-thick structures a one-cell",
        "misalignment destroys overlap, so voxel IoU is inherently unstable at this",
        "resolution; the failure is a sub-voxel / thin-shell resolution effect, not a",
        "graph-prior miss (the SPPA lattice_tower graph has the right topology).",
        "",
        "## (c) Local-search convergence (clean, from sealed metadata.trace)", ""]
    for method, stats in convergence.items():
        md.append(f"### {method} (n = {stats['n_cases']})")
        md.append("")
        md.append(f"- Cases with improvement in the last sweep (step fraction 0.05): "
                  f"{stats['last_sweep_improved_count']}/{stats['n_cases']} = {stats['last_sweep_improved_rate']:.3f}")
        md.append(f"- Cases with final θ on a bound: {stats['theta_at_bound_count']}/{stats['n_cases']} = {stats['theta_at_bound_rate']:.3f}")
        md.append(f"- Cases where the initial θ was already the best: {stats['init_already_best_count']}/{stats['n_cases']} = {stats['init_already_best_rate']:.3f}")
        md.append(f"- Mean objective: init {stats['init_objective_mean']:.4f} → final {stats['final_objective_mean']:.4f} "
                  f"(mean improvement {stats['total_objective_improvement_mean']:.4f}, median {stats['total_objective_improvement_median']:.4f})")
        md.append("")
    (OUT_DIR / "failure_analysis.md").write_text("\n".join(md), encoding="utf-8")

    # ---------------- console summary ---------------------------------------
    total_fail = sum(c["failures"] for c in failures_by_cell.values())
    print(f"total failures: {total_fail}/240")
    for key, cell in failures_by_cell.items():
        if cell["failures"]:
            print(" FAIL", key, cell["failures"], cell["case_ids"])
    print("worst overall:", [(r["case_id"], round(r["voxel_iou"], 4)) for r in worst_overall[:5]])
    for method, stats in convergence.items():
        print(
            f"{method}: last-sweep {stats['last_sweep_improved_rate']:.3f}, bound {stats['theta_at_bound_rate']:.3f}, "
            f"init-best {stats['init_already_best_rate']:.3f}, obj {stats['init_objective_mean']:.4f}->{stats['final_objective_mean']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
