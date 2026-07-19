"""E7 debug: one tower case, end-to-end geometry + reprojection overlay."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

E7_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(E7_ROOT))
from e7_common import (CAMERA, EVENTS_JSONL, FRAMES_DIR, GeoProjector,  # noqa
                       build_observation, llh_to_ne_m, load_gt_static)
from sanity_geometry import ned_to_px  # noqa


def main(frame_no: int = 478) -> None:
    gt = load_gt_static()
    event = None
    with EVENTS_JSONL.open(encoding="utf-8") as handle:
        for line in handle:
            e = json.loads(line)
            if e.get("kind") == "vision_frame" and e.get("frame") == frame_no:
                event = e
                break
    assert event, "frame not found"
    tel = event["telemetry"]
    print("tel:", {k: round(float(v), 3) for k, v in tel.items() if isinstance(v, (int, float))})
    drone_n, drone_e = llh_to_ne_m(float(tel["lat"]), float(tel["lon"]))
    print("drone NE:", round(drone_n, 1), round(drone_e, 1))

    for i, det in enumerate(event["detections"]):
        print(f"\n=== det {i}: {det['type']} conf={det['confidence']:.2f} bbox={det['bbox']}")
        if det["type"] != "tower":
            continue
        obs = build_observation(det, tel)
        if obs is None:
            print("  observation FAILED")
            continue
        fp = obs["footprint"]
        cn, ce = drone_n + fp["center_north_m"], drone_e + fp["center_east_m"]
        print(f"  footprint: len={fp['length_m']:.1f} wid={fp['width_m']:.1f} "
              f"yaw={fp['orientation_deg_axial']:.0f} npts={fp['point_count']}")
        print(f"  height_est={obs['height_m']:.1f} m  base_dist={obs['base_distance_m']:.1f} m")
        for a in gt:
            d = math.hypot(a["north_m"] - cn, a["east_m"] - ce)
            if d < 120:
                print(f"  -> fp center vs {a['label']}({a['cls']}): {d:.1f} m")
        # where do the 8 bbox perimeter points land on the ground?
        b = det["bbox"]
        common = dict(image_height=640, image_width=640, drone_yaw_deg=float(tel["yaw"]),
                      drone_pitch_deg=float(tel["pitch"]), drone_roll_deg=float(tel["roll"]),
                      camera_vfov_deg=70.0, mount_roll_deg=0.0, mount_pitch_deg=-25.0,
                      mount_yaw_deg=0.0)
        pts = [(b["x1"], b["y1"]), (b["x2"], b["y1"]), (b["x2"], b["y2"]), (b["x1"], b["y2"]),
               ((b["x1"] + b["x2"]) / 2, b["y1"]), ((b["x1"] + b["x2"]) / 2, b["y2"]),
               (b["x1"], (b["y1"] + b["y2"]) / 2), (b["x2"], (b["y1"] + b["y2"]) / 2)]
        names = ["TL", "TR", "BR", "BL", "TM", "BM", "ML", "MR"]
        for name, (px, py) in zip(names, pts):
            g = GeoProjector.pixel_to_ground_offset_m(py, px, alt_agl_m=float(tel["alt_agl"]),
                                                      max_range_m=80.0, clamp_to_max_range=False, **common)
            txt = "None" if g is None else "dist=%.1f" % g["distance_m"]
            print(f"    {name}: {txt}", end="")
        print()

    # overlay on the real frame
    img_path = FRAMES_DIR / f"yolo_{frame_no:06d}.jpg"
    print("\nframe image:", img_path, img_path.exists())
    if not img_path.exists():
        return
    img = Image.open(img_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    for det in event["detections"]:
        b = det["bbox"]
        draw.rectangle([b["x1"], b["y1"], b["x2"], b["y2"]], outline=(255, 80, 80), width=2)
        draw.text((b["x1"], b["y1"] - 10), f"{det['type']} {det['confidence']:.2f}", fill=(255, 80, 80))
    # GT anchors projected: base (green), tower top (cyan)
    for a in gt:
        dn, de = a["north_m"] - drone_n, a["east_m"] - drone_e
        if math.hypot(dn, de) > 300:
            continue
        ddown = float(tel["alt_msl"]) - a["height_msl"]
        p_base = ned_to_px(dn, de, ddown, {k: float(tel[k]) for k in ("yaw", "pitch", "roll")})
        obj_h = 25.0 if a["cls"] == "tower" else 1.5
        p_top = ned_to_px(dn, de, ddown - obj_h, {k: float(tel[k]) for k in ("yaw", "pitch", "roll")})
        if p_base:
            draw.ellipse([p_base[0] - 3, p_base[1] - 3, p_base[0] + 3, p_base[1] + 3], outline=(0, 255, 0), width=2)
        if p_base and p_top:
            draw.line([p_base, p_top], fill=(0, 255, 255), width=2)
        if p_base:
            draw.text((p_base[0] + 4, p_base[1] - 4), a["label"], fill=(0, 255, 0))
    out = E7_ROOT / f"debug_frame_{frame_no}.png"
    img.save(out)
    print("saved", out)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 478)
