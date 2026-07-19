"""E7 sanity check: project exact GT anchors into the REAL image plane.

Validates the camera model (VFOV 70, mount pitch -25) end-to-end against the
real detector: for frames with tower/cow detections, where does the exact
simulator anchor land relative to the detector bbox? Also quantifies the
inherent bbox-footprint smear for tall objects.

Exploratory post-hoc. Read-only on all inputs.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

E7_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(E7_ROOT))
from e7_common import CAMERA, EVENTS_JSONL, GeoProjector, load_gt_static, llh_to_ne_m  # noqa


def ned_to_px(dn: float, de: float, ddown: float, tel: dict) -> tuple[float, float] | None:
    """World NED offset (drone frame) -> pixel, exact inverse of pixel_to_ray_ned."""
    R_ned_body = GeoProjector._ned_from_body(tel["yaw"], tel["pitch"], tel["roll"])
    R_mount = (GeoProjector._rot_z(CAMERA["mount_yaw_deg"]) @ GeoProjector._rot_y(CAMERA["mount_pitch_deg"])
               @ GeoProjector._rot_x(CAMERA["mount_roll_deg"]))
    A = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    cam = A.T @ (R_mount.T @ (R_ned_body.T @ np.array([dn, de, ddown])))
    if cam[2] <= 1e-6:
        return None
    H, W = CAMERA["image_height"], CAMERA["image_width"]
    fy = (H / 2.0) / math.tan(math.radians(CAMERA["vfov_deg"]) / 2.0)
    fx = fy
    return fx * cam[0] / cam[2] + W / 2.0, fy * cam[1] / cam[2] + H / 2.0


def main() -> None:
    gt = load_gt_static()
    rows = []
    with EVENTS_JSONL.open("r", encoding="utf-8") as handle:
        for line in handle:
            e = json.loads(line)
            if e.get("kind") != "vision_frame":
                continue
            tel = e["telemetry"]
            if float(tel["lat"]) == 0.0 or float(tel["alt_agl"]) < 10.0:
                continue
            dets = e.get("detections") or []
            if not dets:
                continue
            drone_n, drone_e = llh_to_ne_m(float(tel["lat"]), float(tel["lon"]))
            for det in dets:
                b = det["bbox"]
                bcx, bcy = (b["x1"] + b["x2"]) / 2, (b["y1"] + b["y2"]) / 2
                # candidate anchors of the same class, within 250 m horizontal
                best = None
                for a in gt:
                    if a["cls"] != det["type"]:
                        continue
                    dn = a["north_m"] - drone_n
                    de = a["east_m"] - drone_e
                    if math.hypot(dn, de) > 250:
                        continue
                    ddown_base = float(tel["alt_msl"]) - a["height_msl"]
                    for frac, label in ((0.0, "base"), (0.5, "mid"), (1.0, "top")):
                        obj_h = 25.0 if a["cls"] == "tower" else 1.5
                        px = ned_to_px(dn, de, ddown_base - frac * obj_h, tel)
                        if px is None:
                            continue
                        dist_px = math.hypot(px[0] - bcx, px[1] - bcy)
                        inside = b["x1"] <= px[0] <= b["x2"] and b["y1"] <= px[1] <= b["y2"]
                        if best is None or dist_px < best["dist_px"]:
                            best = {"actor": a["label"], "dist_px": dist_px, "inside": inside,
                                    "part": label, "px": px, "horiz_m": math.hypot(dn, de)}
                if best:
                    rows.append({"frame": e["frame"], "cls": det["type"], "conf": det["confidence"],
                                 "bbox": b, "alt_agl": float(tel["alt_agl"]), **best})

    print(f"n detection-anchor pairs: {len(rows)}")
    for cls in ("tower", "cow", "biker"):
        sel = [r for r in rows if r["cls"] == cls]
        if not sel:
            continue
        inside = sum(1 for r in sel if r["inside"])
        med = float(np.median([r["dist_px"] for r in sel]))
        print(f"{cls}: n={len(sel)} anchor-inside-bbox={inside}/{len(sel)} median_dist_px={med:.1f}")
        parts = {}
        for r in sel:
            parts.setdefault(r["part"], 0)
            parts[r["part"]] += 1
        print("   nearest-height-part counts:", parts)
    print("\nsample tower rows:")
    for r in [r for r in rows if r["cls"] == "tower"][:8]:
        print(f"  f{r['frame']} {r['actor']} conf={r['conf']:.2f} dist_px={r['dist_px']:.0f} "
              f"inside={r['inside']} part={r['part']} horiz={r['horiz_m']:.0f}m bbox={r['bbox']}")


if __name__ == "__main__":
    main()
