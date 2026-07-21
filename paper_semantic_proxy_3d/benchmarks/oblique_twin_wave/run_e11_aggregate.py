"""E11 "Oblique Twin Wave" - step 3: aggregate -> stats, consistency, table, figure.

Reads results.jsonl (per case x method, from run_e11_analysis.py) and produces:
  * e11_analysis.json  - full aggregate (per-ring, per-tower, consistency,
                         parameter spread, consensus proxy, wrong-token arm);
  * e11_main_table.tex - booktabs: per ring x method mean/median 3D IoU [CI]
                         + cross-view consistency rows (SPPA vs best baseline);
  * fig_e11_oblique.png - (a) sample frames with detections, (b) 3D IoU by
                         ring, (c) cross-view consistency per tower,
                         (d) oblique frame + fitted SPPA proxy reprojection.

Statistics: paired bootstrap 95% CI, 10k resamples, seed 20260720 (frozen).

Run:  python run_e11_aggregate.py
"""

from __future__ import annotations

import json
import math
from itertools import combinations
from pathlib import Path

import numpy as np

from e11_common import (
    CLASS_TO_FAMILY, E11_ROOT, EVAL_RES, METHODS, canonical_window,
    load_gt_geometry, load_manifest, mesh_in_window, mv, rasterize_masks,
    resample_occ_to_window, scaled_graphs_for_family, voxel_iou,
    voxelize_actor_in_window, voxelize_boxes_in_window, voxelize_mesh_solid,
)

RESULTS = E11_ROOT / "results.jsonl"
DETECTIONS = E11_ROOT / "detections.jsonl"
OUT_JSON = E11_ROOT / "e11_analysis.json"
OUT_TEX = E11_ROOT / "e11_main_table.tex"
OUT_FIG = E11_ROOT / "fig_e11_oblique.png"
BOOT_N = 10_000
BOOT_SEED = 20260720
RINGS = ("oblique30", "oblique45", "nadir")


# ---------------------------------------------------------------------------
# Bootstrap helpers
# ---------------------------------------------------------------------------
def boot_mean_ci(values: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    n = len(values)
    if n == 0:
        return (float("nan"), float("nan"))
    idx = rng.integers(0, n, size=(BOOT_N, n))
    means = values[idx].mean(axis=1)
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def stats_block(values: list[float], rng) -> dict | None:
    if not values:
        return None
    arr = np.asarray(values, dtype=float)
    lo, hi = boot_mean_ci(arr, rng)
    return {"n": int(arr.size), "mean": float(arr.mean()), "median": float(np.median(arr)),
            "p25": float(np.percentile(arr, 25)), "p75": float(np.percentile(arr, 75)),
            "ci95_mean": [lo, hi]}


# ---------------------------------------------------------------------------
# Canonical (cross-view) proxies
# ---------------------------------------------------------------------------
def canonical_occ(row: dict, can_window: dict) -> np.ndarray:
    """Re-express one fitted proxy in the tower's canonical window."""
    bearing = math.radians(row["bearing_deg"])
    method = row["method"]
    if method in ("sppa_mvfit", "generic_mvfit"):
        family = row["family_token"]
        mv.GRAPHS = scaled_graphs_for_family(family)  # in-memory only
        graph = family if method == "sppa_mvfit" else "generic"
        actor = mv.build_actor(graph, np.asarray(row["theta"], dtype=float))
        return voxelize_actor_in_window(actor, can_window, bearing, EVAL_RES)
    if method in ("obb", "aabb"):
        return voxelize_boxes_in_window(row["boxes"], can_window, bearing, EVAL_RES)
    # voxel baselines: rebuild the case occupancy from the stored observation
    # (deterministic) and resample into the canonical frame (declared approx).
    window = {a: tuple(row["window"][a]) for a in "xyz"}
    mv.WORLD = window  # in-memory only
    top, side = rasterize_masks(window, row["obs_length_m"], row["obs_width_m"], row["obs_height_m"])
    name = "nonsemantic_visual_hull" if method == "visual_hull" else "capsule"
    occ_case, _ = mv.baseline_occupancy(name, top, side, EVAL_RES)
    return resample_occ_to_window(occ_case, window, bearing, can_window, EVAL_RES)


def consistency_block(rows: list[dict], gt_actors: dict, rng) -> dict:
    """Per tower: canonical proxies (best tower-token detection per frame),
    pairwise cross-view IoU, parameter spread, consensus proxy vs GT."""
    correct = [r for r in rows if r["token_correct"]]
    # best (max-confidence) detection per (tower, frame)
    best: dict[tuple[str, str], dict] = {}
    for r in correct:
        key = (r["tower_id"], r["frame_id"])
        if key not in best or r["confidence"] > best[key]["confidence"]:
            best[key] = r
    cases = sorted(best.values(), key=lambda r: (r["tower_id"], r["frame_id"]))
    by_case = {(r["case_id"], r["method"]): r for r in rows}

    out: dict[str, dict] = {}
    for tower in sorted({r["tower_id"] for r in cases}):
        t_cases = [r for r in cases if r["tower_id"] == tower]
        can_window = canonical_window(tower, gt_actors)
        verts, faces = mesh_in_window(tower, 0.0, gt_actors)
        _, gt_solid = voxelize_mesh_solid(verts, faces, can_window, EVAL_RES)
        entry: dict = {"n_views": len(t_cases), "methods": {}}
        for method in METHODS:
            proxies = []  # (ring, occ)
            for c in t_cases:
                row = by_case.get((c["case_id"], method))
                if row is None:
                    continue
                proxies.append((c["ring"], canonical_occ(row, can_window)))
            cats: dict[str, list[float]] = {"within_oblique30": [], "within_oblique45": [],
                                            "oblique30_vs_oblique45": [], "nadir_vs_oblique": []}
            for (r1, o1), (r2, o2) in combinations(proxies, 2):
                iou = voxel_iou(o1, o2)
                if r1 == r2 == "oblique30":
                    cats["within_oblique30"].append(iou)
                elif r1 == r2 == "oblique45":
                    cats["within_oblique45"].append(iou)
                elif r1 == r2 == "nadir":
                    continue  # within-nadir pairs are not a declared category
                elif "nadir" in (r1, r2):
                    cats["nadir_vs_oblique"].append(iou)
                else:
                    cats["oblique30_vs_oblique45"].append(iou)
            entry["methods"][method] = {
                cat: ({"mean": float(np.mean(v)), "n_pairs": len(v)} if v else None)
                for cat, v in cats.items()
            }
        # parameter spread + consensus (SPPA thetas of this tower's views)
        thetas = np.array([by_case[(c["case_id"], "sppa_mvfit")]["theta"] for c in t_cases
                           if (c["case_id"], "sppa_mvfit") in by_case])
        if len(thetas):
            scales = np.exp(thetas[:, :3])
            entry["param_spread_std"] = {
                "scale_x": float(scales[:, 0].std()), "scale_y": float(scales[:, 1].std()),
                "scale_z": float(scales[:, 2].std()),
                "secondary_scale": float(thetas[:, 3].std()), "secondary_offset_x": float(thetas[:, 4].std()),
            }
            mv.GRAPHS = scaled_graphs_for_family("lattice_tower")
            actor = mv.build_actor("lattice_tower", np.median(thetas, axis=0))
            occ = voxelize_actor_in_window(actor, can_window, 0.0, EVAL_RES)
            entry["consensus_proxy_iou3d_vs_gt"] = voxel_iou(occ, gt_solid)
        out[tower] = entry
    # pooled summaries
    pooled: dict = {}
    for method in METHODS:
        m: dict = {}
        for cat in ("within_oblique30", "within_oblique45", "oblique30_vs_oblique45", "nadir_vs_oblique"):
            vals = [out[t]["methods"][method][cat]["mean"] for t in out
                    if out[t]["methods"][method][cat] is not None]
            m[cat] = stats_block(vals, rng) if vals else None
        pooled[method] = m
    consensus_vals = [out[t]["consensus_proxy_iou3d_vs_gt"] for t in out
                      if "consensus_proxy_iou3d_vs_gt" in out[t]]
    spread_vals = [out[t]["param_spread_std"] for t in out if "param_spread_std" in out[t]]
    return {"per_tower": out, "pooled": pooled,
            "consensus_proxy_iou3d_vs_gt": stats_block(consensus_vals, rng) if consensus_vals else None,
            "param_spread_mean": {k: float(np.mean([s[k] for s in spread_vals])) for k in spread_vals[0]} if spread_vals else None}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    rng = np.random.default_rng(BOOT_SEED)
    rows = [json.loads(line) for line in RESULTS.open("r", encoding="utf-8")]
    dets = [json.loads(line) for line in DETECTIONS.open("r", encoding="utf-8")]
    manifest = load_manifest()
    gt_actors = load_gt_geometry()
    print(f"rows={len(rows)} cases={len({r['case_id'] for r in rows})} dets={len(dets)}")

    # detection census (incl. observation failures, derivable by join)
    fitted_cases = {r["case_id"] for r in rows}
    census: dict = {}
    for d in dets:
        ring = manifest[d["frame_id"]]["ring"]
        cid = f"{d['frame_id']}::d{d['det_index']}"
        key = (ring, d["class"])
        c = census.setdefault(key, {"detections": 0, "fitted": 0})
        c["detections"] += 1
        c["fitted"] += int(cid in fitted_cases)

    # (a) per ring x method 3D IoU (+ pooled oblique), paired diffs vs SPPA
    per_ring: dict = {}
    for ring in RINGS + ("oblique_pooled",):
        sel = [r for r in rows if r["ring"] == ring] if ring != "oblique_pooled" else \
              [r for r in rows if r["ring"] in ("oblique30", "oblique45")]
        per_ring[ring] = {}
        for method in METHODS:
            per_ring[ring][method] = stats_block([r["iou_3d"] for r in sel if r["method"] == method], rng)
        diffs = {}
        case_ids = sorted({r["case_id"] for r in sel})
        lut = {(r["case_id"], r["method"]): r["iou_3d"] for r in sel}
        sppa = np.array([lut[(c, "sppa_mvfit")] for c in case_ids])
        for method in METHODS[1:]:
            other = np.array([lut[(c, method)] for c in case_ids])
            d = sppa - other
            lo, hi = boot_mean_ci(d, rng)
            diffs[f"sppa_minus_{method}"] = {"mean": float(d.mean()), "ci95": [lo, hi],
                                             "p_le_0": float((d <= 0).mean())}
        per_ring[ring]["paired_diffs"] = diffs

    # correct-token-only subset (matters for sppa/generic; box/voxel baselines
    # do not consume the family token at all)
    per_ring_correct: dict = {}
    for ring in RINGS:
        sel = [r for r in rows if r["ring"] == ring and r["token_correct"]]
        per_ring_correct[ring] = {m: stats_block([r["iou_3d"] for r in sel if r["method"] == m], rng)
                                  for m in METHODS}

    # (c) per-tower breakdown
    per_tower = {}
    for tower in sorted({r["tower_id"] for r in rows}):
        per_tower[tower] = {m: stats_block([r["iou_3d"] for r in rows
                                            if r["tower_id"] == tower and r["method"] == m], rng)
                            for m in METHODS}

    # (b) consistency
    consistency = consistency_block(rows, gt_actors, rng)

    # (d) wrong-token arm
    wrong = [r for r in rows if not r["token_correct"]]
    correct = [r for r in rows if r["token_correct"]]
    token_arm = {
        "n_wrong_token_cases": len({r["case_id"] for r in wrong}),
        "wrong_by_ring": {ring: len({r["case_id"] for r in wrong if r["ring"] == ring}) for ring in RINGS},
        "wrong_iou3d_sppa": stats_block([r["iou_3d"] for r in wrong if r["method"] == "sppa_mvfit"], rng),
        "correct_iou3d_sppa": stats_block([r["iou_3d"] for r in correct if r["method"] == "sppa_mvfit"], rng),
    }

    # GT voxelization sanity
    gt_sanity = {
        "solid_voxels": stats_block([r["gt_voxels_solid"] for r in rows if r["method"] == "sppa_mvfit"], rng),
        "surface_voxels": stats_block([r["gt_voxels_surface"] for r in rows if r["method"] == "sppa_mvfit"], rng),
    }

    analysis = {
        "label": "exploratory post-hoc analysis (not confirmatory)",
        "benchmark": "E11 Oblique Twin Wave",
        "protocol": "PROTOCOL_E11.md (frozen 2026-07-20)",
        "scope": "positions LOCKED to GT; reconstruction fidelity only; no localization metrics",
        "evidence": "hybrid: simulated twin imagery + real YOLO detector + exact simulator GT",
        "bootstrap": {"n": BOOT_N, "seed": BOOT_SEED, "paired": True},
        "detection_census": {f"{k[0]}|{k[1]}": v for k, v in sorted(census.items())},
        "per_ring": per_ring,
        "per_ring_correct_token": per_ring_correct,
        "per_tower": per_tower,
        "consistency": consistency,
        "token_arm": token_arm,
        "gt_voxelization_sanity": gt_sanity,
    }
    OUT_JSON.write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_JSON}")

    write_table(analysis)
    make_figure(rows, dets, manifest, gt_actors, analysis)
    return 0


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------
def write_table(a: dict) -> None:
    def fmt(block):
        if block is None:
            return "--"
        return f"{block['mean']:.3f} [{block['ci95_mean'][0]:.3f}, {block['ci95_mean'][1]:.3f}]"

    lines = [
        "% E11 Oblique Twin Wave - main table (exploratory post-hoc; positions LOCKED to GT)",
        "\\begin{tabular}{llccc}", "\\toprule",
        "Ring & Method & mean 3D IoU [95\\% CI] & $n$ & SPPA$-$method [95\\% CI] \\\\",
        "\\midrule",
    ]
    for ring in RINGS:
        block = a["per_ring"][ring]
        n_rows = 0
        for method in METHODS:
            st = block[method]
            if st is None:
                continue
            n_rows += 1
            diff = "" if method == "sppa_mvfit" else \
                f"{block['paired_diffs'][f'sppa_minus_{method}']['mean']:+.3f} [{block['paired_diffs'][f'sppa_minus_{method}']['ci95'][0]:+.3f}, {block['paired_diffs'][f'sppa_minus_{method}']['ci95'][1]:+.3f}]"
            ringcell = ring if method == "sppa_mvfit" else ""
            lines.append(f"{ringcell} & {method.replace('_', chr(92) + '_')} & {fmt(st)} & {st['n']} & {diff} \\\\")
        if n_rows:
            lines.append("\\midrule")
    lines += [
        "\\multicolumn{5}{l}{Correct-token subset (tower detections only; box/voxel baselines are token-free)} \\\\",
        "\\midrule",
    ]
    for ring in RINGS:
        for method in ("sppa_mvfit", "generic_mvfit"):
            st = a["per_ring_correct_token"][ring][method]
            if st is None:
                continue
            ringcell = f"{ring} (correct token)" if method == "sppa_mvfit" else ""
            lines.append(f"{ringcell} & {method} & {fmt(st)} & {st['n']} &  \\\\")
    lines.append("\\midrule")
    lines += [
        "\\multicolumn{5}{l}{Cross-view consistency (mean pairwise 3D IoU between proxies fitted from different views)} \\\\",
        "\\midrule",
    ]
    pooled = a["consistency"]["pooled"]
    for method in METHODS:
        cells = []
        for cat, label in (("within_oblique30", "obl30"), ("within_oblique45", "obl45")):
            st = pooled[method][cat]
            cells.append(f"{label} {st['mean']:.3f}" if st else f"{label} --")
        st = pooled[method]["nadir_vs_oblique"]
        cells.append(f"nadir-vs-obl {st['mean']:.3f}" if st else "nadir-vs-obl n/a")
        lines.append(f" & {method} & \\multicolumn{{3}}{{l}}{{{'; '.join(cells)}}} \\\\")
    cons = a["consistency"]["consensus_proxy_iou3d_vs_gt"]
    if cons:
        lines.append(f" & SPPA consensus proxy vs GT & \\multicolumn{{3}}{{l}}{{{cons['mean']:.3f} "
                     f"[{cons['ci95_mean'][0]:.3f}, {cons['ci95_mean'][1]:.3f}] (per-tower means)}} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", ""]
    OUT_TEX.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_TEX}")


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------
def make_figure(rows, dets, manifest, gt_actors, analysis) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.patches as patches
    import matplotlib.pyplot as plt
    from PIL import Image

    from e11_common import quat_to_R

    # 2026-07-21 (2nd readability pass): 2x2 layout, each panel half the text
    # width (was 2x4 mini-panels). Cell (0,0) carries both detection frames.
    fig = plt.figure(figsize=(11, 9))
    gs = fig.add_gridspec(2, 2, hspace=0.30, wspace=0.16)
    colors = {"tower": "lime", "biker": "red", "cow": "yellow"}
    det_by_frame: dict[str, list[dict]] = {}
    for d in dets:
        det_by_frame.setdefault(d["frame_id"], []).append(d)

    # (a) two sample frames with detections, side by side in cell (0,0)
    sub = gs[0, 0].subgridspec(1, 2, wspace=0.06)
    for i, fid in enumerate(("t0_oblique30_az000", "t0_oblique45_az120")):
        ax = fig.add_subplot(sub[0, i])
        ax.imshow(Image.open(E11_ROOT / "frames" / f"{fid}.png"))
        for d in det_by_frame.get(fid, []):
            b = d["bbox"]
            ax.add_patch(patches.Rectangle((b["x1"], b["y1"]), b["x2"] - b["x1"], b["y2"] - b["y1"],
                                           fill=False, edgecolor=colors[d["class"]], lw=1.4))
            ax.text(b["x1"], b["y1"] - 2, f'{d["class"][:4]} {d["confidence"]:.2f}',
                    color=colors[d["class"]], fontsize=8)
        ax.set_title(f"(a) detections:\n{fid}", fontsize=10)
        ax.axis("off")

    # (b) 3D IoU by ring
    ax = fig.add_subplot(gs[0, 1])
    x = np.arange(len(METHODS))
    width = 0.35
    for j, ring in enumerate(("oblique30", "oblique45")):
        means, los, his = [], [], []
        for m in METHODS:
            st = analysis["per_ring"][ring][m]
            means.append(st["mean"] if st else 0.0)
            los.append((st["mean"] - st["ci95_mean"][0]) if st else 0.0)
            his.append((st["ci95_mean"][1] - st["mean"]) if st else 0.0)
        ax.bar(x + (j - 0.5) * width, means, width, yerr=[los, his], capsize=2,
               label=ring, alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels([m.replace("_", "\n") for m in METHODS], fontsize=9)
    ax.set_ylabel("3D voxel IoU vs exact GT")
    ax.set_title("(b) reconstruction fidelity by ring (mean, 95% CI)", fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    # (c) cross-view consistency per tower
    ax = fig.add_subplot(gs[1, 1])
    per_t = analysis["consistency"]["per_tower"]
    towers = sorted(per_t)
    best_baseline = max(METHODS[1:], key=lambda m: (
        analysis["consistency"]["pooled"][m]["within_oblique30"] or {"mean": -1})["mean"])
    series_labels = {"sppa_mvfit": "sppa_mvfit (SPPA, ours)",
                     best_baseline: f"{best_baseline} (best baseline)"}
    for k, method in enumerate(("sppa_mvfit", best_baseline)):
        vals = []
        for t in towers:
            st30 = per_t[t]["methods"][method]["within_oblique30"]
            st45 = per_t[t]["methods"][method]["within_oblique45"]
            both = [s["mean"] for s in (st30, st45) if s]
            vals.append(float(np.mean(both)) if both else np.nan)
        ax.scatter(np.arange(len(towers)) + (k - 0.5) * 0.25, vals,
                   label=series_labels[method], marker="os"[k], s=28)
    ax.set_xticks(np.arange(len(towers)))
    ax.set_xticklabels(towers, rotation=45, fontsize=9)
    ax.set_ylabel("mean pairwise 3D IoU between proxies\nfitted from different views", fontsize=10)
    ax.set_title("(c) cross-view consistency per tower (within oblique rings)", fontsize=11)
    ax.legend(fontsize=9, loc="center left")
    ax.grid(axis="y", alpha=0.3)
    # panel (d) spans grid cells (5,8) and is created after this one, so its
    # image would otherwise paint over this panel's y-label/legend; draw this
    # axes above it with a transparent background.
    ax.set_zorder(2)
    ax.set_facecolor("none")

    # (d) oblique frame + fitted SPPA proxy reprojection
    ax = fig.add_subplot(gs[1, 0])
    sppa_rows = [r for r in rows if r["method"] == "sppa_mvfit" and r["token_correct"]
                 and r["ring"] == "oblique30"]
    best_row = max(sppa_rows, key=lambda r: r["iou_3d"])
    frame = manifest[best_row["frame_id"]]
    actor_gt = gt_actors[best_row["tower_id"]]
    ax.imshow(Image.open(E11_ROOT / "frames" / f"{best_row['frame_id']}.png"))
    b = best_row["bbox"] if "bbox" in best_row else None
    # project fitted actor occupancy through the exact manifest camera
    family = best_row["family_token"]
    mv.GRAPHS = scaled_graphs_for_family(family)
    actor = mv.build_actor(family, np.asarray(best_row["theta"], dtype=float))
    window = {a2: tuple(best_row["window"][a2]) for a2 in "xyz"}
    mv.WORLD = window
    occ = mv.voxelize_actor(actor, EVAL_RES)
    idx = np.argwhere(occ)
    from e11_common import cell_centers
    xs = cell_centers(window["x"], EVAL_RES)[idx[:, 0]]
    ys = cell_centers(window["y"], EVAL_RES)[idx[:, 1]]
    zs = cell_centers(window["z"], EVAL_RES)[idx[:, 2]]
    bearing = math.radians(best_row["bearing_deg"])
    cb, sb = math.cos(bearing), math.sin(bearing)
    dn = xs * cb - ys * sb
    de = xs * sb + ys * cb
    # window frame -> Unreal world (E=+ux, S=+uy, U=+uz), pivot-locked
    wl = actor_gt["world_location"]
    pts = np.stack([wl["x"] + de * 100.0, wl["y"] - dn * 100.0, wl["z"] + zs * 100.0], axis=1)
    q = frame["camera_rotation_quat"]
    R = quat_to_R(q)
    cw = frame["camera_world"]
    cam_pos = np.array([cw["x"], cw["y"], cw["z"]])
    d = (R.T @ (pts - cam_pos).T).T
    in_front = d[:, 0] > 1e-3
    f = 320.0 / math.tan(math.radians(70.0) / 2.0)
    u = f * d[in_front, 1] / d[in_front, 0] + 320.0
    v = -f * d[in_front, 2] / d[in_front, 0] + 320.0
    keep = (u >= 0) & (u < 640) & (v >= 0) & (v < 640)
    ax.scatter(u[keep], v[keep], s=1, c="cyan", alpha=0.4, label="SPPA proxy reprojection")
    det = next((dd for dd in det_by_frame.get(best_row["frame_id"], [])
                if f"{dd['frame_id']}::d{dd['det_index']}" == best_row["case_id"]), None)
    if det is not None:
        bb = det["bbox"]
        ax.add_patch(patches.Rectangle((bb["x1"], bb["y1"]), bb["x2"] - bb["x1"], bb["y2"] - bb["y1"],
                                       fill=False, edgecolor="lime", lw=1.4))
    ax.set_title(f"(d) {best_row['frame_id']} proxy reprojection (IoU3D={best_row['iou_3d']:.3f})", fontsize=11)
    ax.axis("off")

    # suptitle removed 2026-07-21: it duplicated the LaTeX caption and cost a
    # line of figure height at text width.
    fig.tight_layout()
    fig.savefig(OUT_FIG, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT_FIG}")


if __name__ == "__main__":
    raise SystemExit(main())
