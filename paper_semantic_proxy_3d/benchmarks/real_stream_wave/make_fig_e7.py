"""E7 "Real Stream Wave" - figure (exploratory post-hoc).

2x2 panels, JGSA style (Okabe-Ito, 300 dpi):
  (a) REAL frame with REAL detector bboxes + exact GT anchors reprojected
      through the same camera model (geometry validation).
  (b) Plan view of one GT-matched tower case: declared GT base rect, observed
      oriented footprint, and fitted proxy footprints (SPPA / OBB / capsule).
  (c) 2D reprojection IoU (fit to the real image evidence), method x class.
  (d) Observation-bound localization: footprint-centre -> anchor distance vs
      fitted-proxy centroid 3D error (SPPA-MVFit), y=x reference.

Run:  python make_fig_e7.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw

E7_ROOT = Path(__file__).resolve().parent
JGSA = E7_ROOT.parents[1] / "tools" / "jgsa_figures"
sys.path.insert(0, str(JGSA))
sys.path.insert(0, str(E7_ROOT))
import jgsa_style  # noqa
from e7_common import (CAMERA, CLASS_TO_FAMILY, EVENTS_JSONL, FRAMES_DIR,  # noqa
                       GT_FOOTPRINT_DIMS_M, GeoProjector, build_observation,
                       iter_cases, llh_to_ne_m, load_gt_static, match_gt, mv,
                       scaled_graphs_for_family)
from run_e7_real_stream import (EVAL_RES, case_window, cell_centers,  # noqa
                                rasterize_masks, run_method)
from sanity_geometry import ned_to_px  # noqa

jgsa_style.apply_style()
OI = jgsa_style.OI
METHOD_COLORS = {
    "sppa_mvfit": OI["blue"], "generic_mvfit": OI["vermillion"], "obb": OI["gray"],
    "aabb": OI["light_gray"], "visual_hull": OI["bluish_green"], "capsule": OI["reddish_purple"],
}
METHOD_LABELS = {"sppa_mvfit": "SPPA-MVFit", "generic_mvfit": "Generic-MVFit", "obb": "OBB",
                 "aabb": "AABB", "visual_hull": "Visual hull", "capsule": "Capsule"}
FIG_FRAME = 478

# ---------------------------------------------------------------------------
# Panel (a): frame overlay
# ---------------------------------------------------------------------------


def panel_frame(ax) -> None:
    gt = load_gt_static()
    event = None
    with EVENTS_JSONL.open(encoding="utf-8") as handle:
        for line in handle:
            e = json.loads(line)
            if e.get("kind") == "vision_frame" and e.get("frame") == FIG_FRAME:
                event = e
                break
    tel = event["telemetry"]
    tel_small = {k: float(tel[k]) for k in ("yaw", "pitch", "roll")}
    drone_n, drone_e = llh_to_ne_m(float(tel["lat"]), float(tel["lon"]))
    img = Image.open(FRAMES_DIR / f"yolo_{FIG_FRAME:06d}.jpg").convert("RGB")
    draw = ImageDraw.Draw(img)
    for det in event["detections"]:
        b = det["bbox"]
        draw.rectangle([b["x1"], b["y1"], b["x2"], b["y2"]], outline=OI["vermillion"], width=2)
        draw.text((b["x1"], max(0, b["y1"] - 11)), f"{det['type']} {det['confidence']:.2f}", fill=OI["vermillion"])
    for a in gt:
        dn, de = a["north_m"] - drone_n, a["east_m"] - drone_e
        if math.hypot(dn, de) > 300:
            continue
        ddown = float(tel["alt_msl"]) - a["height_msl"]
        obj_h = 25.0 if a["cls"] == "tower" else 1.5
        p_base = ned_to_px(dn, de, ddown, tel_small)
        p_top = ned_to_px(dn, de, ddown - obj_h, tel_small)
        if p_base and p_top:
            draw.line([p_base, p_top], fill=OI["sky_blue"], width=2)
        if p_base:
            draw.ellipse([p_base[0] - 3, p_base[1] - 3, p_base[0] + 3, p_base[1] + 3],
                         outline=OI["bluish_green"], width=2)
            draw.text((p_base[0] + 5, p_base[1] - 5), a["label"], fill=OI["bluish_green"])
    ax.imshow(np.asarray(img))
    ax.set_title("(a) Real frame f478: detector bboxes (red) vs exact GT anchors (green/blue)",
                 fontsize=8)
    ax.axis("off")


# ---------------------------------------------------------------------------
# Panel (b): plan view of one matched tower case
# ---------------------------------------------------------------------------


def occ_to_ne(occ: np.ndarray, window: dict, fp: dict, bearing: float,
              drone_n: float, drone_e: float) -> tuple[np.ndarray, np.ndarray]:
    top2d = occ.any(axis=2)
    idx = np.argwhere(top2d)
    xs = cell_centers(window["x"], EVAL_RES)[idx[:, 0]]
    ys = cell_centers(window["y"], EVAL_RES)[idx[:, 1]]
    cb, sb = math.cos(bearing), math.sin(bearing)
    n = drone_n + fp["center_north_m"] + xs * cb - ys * sb
    e = drone_e + fp["center_east_m"] + xs * sb + ys * cb
    return n, e


def rect_ne(center_n: float, center_e: float, length: float, width: float,
            bearing: float) -> np.ndarray:
    cb, sb = math.cos(bearing), math.sin(bearing)
    corners = np.array([(length / 2, width / 2), (length / 2, -width / 2),
                        (-length / 2, -width / 2), (-length / 2, width / 2), (length / 2, width / 2)])
    n = center_n + corners[:, 0] * cb - corners[:, 1] * sb
    e = center_e + corners[:, 0] * sb + corners[:, 1] * cb
    return np.stack([n, e], axis=1)


def panel_plan(ax) -> None:
    rows = [json.loads(line) for line in (E7_ROOT / "results.jsonl").open(encoding="utf-8")]
    tower_ok = [r for r in rows if r["method"] == "sppa_mvfit" and r["det_class"] == "tower"
                and r["matched"] and r["token_correct"]]
    med = float(np.median([r["loc_err_3d_m"] for r in tower_ok]))
    chosen = min(tower_ok, key=lambda r: abs(r["loc_err_3d_m"] - med))
    case_id = chosen["case_id"]

    cases, _ = iter_cases()
    gt = load_gt_static()
    case = next(c for c in cases if c["case_id"] == case_id)
    gt_match = match_gt(case, gt)
    fp = case["footprint"]
    bearing = math.radians(fp["orientation_deg_axial"])
    dn, de = case["drone_north_m"], case["drone_east_m"]
    cn, ce = dn + fp["center_north_m"], de + fp["center_east_m"]

    family = case["family"]
    mv.GRAPHS = scaled_graphs_for_family(family)
    window = case_window(fp["length_m"], fp["width_m"], case["height_m"], family)
    mv.WORLD = {"x": window["x"], "y": window["y"], "z": window["z"]}
    top, side = rasterize_masks(window, fp["length_m"], fp["width_m"], case["height_m"])

    # observed footprint rect (the common observation)
    obs_rect = rect_ne(cn, ce, fp["length_m"], fp["width_m"], bearing)
    ax.plot(obs_rect[:, 1], obs_rect[:, 0], color=OI["black"], lw=1.4, ls="--",
            label="Observed footprint (common)")
    # declared GT base rect
    gl, gw = GT_FOOTPRINT_DIMS_M["tower"]
    gt_rect = rect_ne(gt_match["north_m"], gt_match["east_m"], gl, gw,
                      math.radians(gt_match["yaw_deg"] % 180.0))
    ax.plot(gt_rect[:, 1], gt_rect[:, 0], color=OI["bluish_green"], lw=2.0,
            label="GT base (declared 5$\\times$5 m)")
    ax.scatter([gt_match["east_m"]], [gt_match["north_m"]], marker="o", s=40,
               color=OI["bluish_green"], zorder=5)
    ax.annotate(f"GT {gt_match['label']}", (gt_match["east_m"], gt_match["north_m"]),
                textcoords="offset points", xytext=(6, 6), fontsize=7, color=OI["bluish_green"])

    for method, size in (("capsule", 7), ("obb", 5), ("sppa_mvfit", 3)):
        occ = run_method(method, family, top, side, window, case["height_m"], case, bearing)
        n, e = occ_to_ne(occ, window, fp, bearing, dn, de)
        ax.scatter(e, n, marker="s", s=size, alpha=0.5, color=METHOD_COLORS[method],
                   label=f"{METHOD_LABELS[method]} proxy")
    ax.scatter([de], [dn], marker="^", s=60, color=OI["black"], zorder=6)
    ax.annotate("UAV", (de, dn), textcoords="offset points", xytext=(6, -12), fontsize=7)
    ax.plot([de, ce], [dn, cn], color=OI["black"], lw=0.7, alpha=0.4)
    ax.set_title(f"(b) Plan view, tower case {case_id} (loc. err. = observation-bound)", fontsize=8)
    ax.set_xlabel("East (m)", fontsize=7)
    ax.set_ylabel("North (m)", fontsize=7)
    ax.set_aspect("equal")
    ax.legend(fontsize=5.5, loc="best", framealpha=0.9)
    ax.tick_params(labelsize=6)


# ---------------------------------------------------------------------------
# Panels (c) and (d)
# ---------------------------------------------------------------------------


def panel_bars(ax, analysis: dict) -> None:
    methods = ("sppa_mvfit", "generic_mvfit", "obb", "aabb", "visual_hull", "capsule")
    classes = ("tower", "cow", "biker")
    cls_colors = {"tower": OI["blue"], "cow": OI["orange"], "biker": OI["bluish_green"]}
    x = np.arange(len(methods))
    width = 0.26
    for i, cls in enumerate(classes):
        meds = [analysis["per_method"][m]["per_class"][cls]["reproj_iou"]["median"] for m in methods]
        p25 = [analysis["per_method"][m]["per_class"][cls]["reproj_iou"]["p25"] for m in methods]
        p75 = [analysis["per_method"][m]["per_class"][cls]["reproj_iou"]["p75"] for m in methods]
        err = np.array([np.array(meds) - np.array(p25), np.array(p75) - np.array(meds)])
        ax.bar(x + (i - 1) * width, meds, width, yerr=err, capsize=2,
               color=cls_colors[cls], label=f"{cls} dets", edgecolor="white", linewidth=0.3,
               error_kw=dict(lw=0.7))
    ax.set_xticks(x)
    ax.set_xticklabels([METHOD_LABELS[m] for m in methods], fontsize=6, rotation=18, ha="right")
    ax.set_ylabel("2D reprojection IoU (median)", fontsize=7)
    ax.set_title("(c) Fit to the real image evidence, by detector class", fontsize=8)
    ax.legend(fontsize=6)
    ax.tick_params(labelsize=6)
    ax.set_ylim(0, 0.62)


def panel_scatter(ax) -> None:
    cases, _ = iter_cases()
    gt = load_gt_static()
    obs_err = {}
    for case in cases:
        m = match_gt(case, gt)
        if m is not None:
            obs_err[case["case_id"]] = (m["match_distance_m"], m["cls"] == case["det_class"])
    rows = [json.loads(line) for line in (E7_ROOT / "results.jsonl").open(encoding="utf-8")]
    sppa = [r for r in rows if r["method"] == "sppa_mvfit" and r["matched"] and r["loc_err_3d_m"] is not None]
    for ok, color, label in ((True, OI["blue"], "token correct (tower)"),
                             (False, OI["vermillion"], "wrong token (cow/biker on tower)")):
        xs = [obs_err[r["case_id"]][0] for r in sppa if obs_err[r["case_id"]][1] == ok]
        ys = [r["loc_err_3d_m"] for r in sppa if obs_err[r["case_id"]][1] == ok]
        ax.scatter(xs, ys, s=9, alpha=0.55, color=color, label=f"{label} (n={len(xs)})",
                   edgecolors="none")
    lim = 55
    ax.plot([0, lim], [0, lim], color=OI["black"], lw=0.9, ls="--")
    ax.annotate("y = x: proxy error = observation error", (24, 20.5), fontsize=6.5, rotation=24)
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_aspect("equal")
    ax.set_xlabel("Observation error: footprint centre $\\to$ GT anchor (m)", fontsize=7)
    ax.set_ylabel("SPPA-MVFit centroid 3D error (m)", fontsize=7)
    ax.set_title("(d) Localization is observation-bound", fontsize=8)
    ax.legend(fontsize=6, loc="upper left")
    ax.tick_params(labelsize=6)


def main() -> int:
    analysis = json.loads((E7_ROOT / "e7_analysis.json").read_text(encoding="utf-8"))
    fig, axes = plt.subplots(2, 2, figsize=(9.2, 8.0))
    panel_frame(axes[0, 0])
    panel_plan(axes[0, 1])
    panel_bars(axes[1, 0], analysis)
    panel_scatter(axes[1, 1])
    fig.suptitle("E7 Real Stream Wave — real UAV stream, real detector, exploratory post-hoc (not sealed)",
                 fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = E7_ROOT / "fig_real_stream.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    print("saved", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
