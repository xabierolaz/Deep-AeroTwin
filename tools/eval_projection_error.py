#!/usr/bin/env python3
"""
Evaluate the Vision geo-projection math (pixel -> ground lat/lon) against known ground truth.

Important:
- This does NOT query Unreal ground truth. It is a controlled geometric evaluation.
- It measures sensitivity to pixel noise (proxy for bbox jitter) and small telemetry noise.

Output:
- position error (meters): difference between predicted and true ground point
- distance error (meters): abs(pred_dist - true_horizontal_dist)
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Optional, Tuple

import numpy as np

# Reuse the exact implementation used by the pipeline.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "pipeline"))
from vision_system import GeoProjector  # noqa: E402


@dataclass(frozen=True)
class EvalCfg:
    samples: int
    seed: int
    image_w: int
    image_h: int
    vfov_deg: float
    true_vfov_deg: float
    mount_pitch_deg: float
    mount_roll_deg: float
    mount_yaw_deg: float
    true_mount_pitch_deg: float
    true_mount_roll_deg: float
    true_mount_yaw_deg: float
    yaw_deg: float
    pitch_deg: float
    roll_deg: float
    alt_agl_m: float
    max_range_m: float
    min_range_m: float
    max_east_m: float


def _fx_fy(image_w: int, image_h: int, vfov_deg: float) -> Tuple[float, float, float, float]:
    H = float(image_h)
    W = float(image_w)
    vfov_rad = math.radians(float(vfov_deg))
    fy = (H / 2.0) / math.tan(vfov_rad / 2.0)
    hfov_rad = 2.0 * math.atan(math.tan(vfov_rad / 2.0) * (W / H))
    fx = (W / 2.0) / math.tan(hfov_rad / 2.0)
    cx = W / 2.0
    cy = H / 2.0
    return fx, fy, cx, cy


def _project_ground_to_pixel(
    north_m: float,
    east_m: float,
    cfg: EvalCfg,
) -> Optional[Tuple[float, float]]:
    # Object is on ground plane; in NED, ground point is at down=alt_agl.
    p_ned = np.array([float(north_m), float(east_m), float(cfg.alt_agl_m)], dtype=float)

    R_ned_body = GeoProjector._ned_from_body(float(cfg.yaw_deg), float(cfg.pitch_deg), float(cfg.roll_deg))
    p_body = R_ned_body.T @ p_ned

    R_body_cam_align = np.array(
        [
            [0.0, 0.0, 1.0],  # body_x = cam_z
            [1.0, 0.0, 0.0],  # body_y = cam_x
            [0.0, 1.0, 0.0],  # body_z = cam_y
        ],
        dtype=float,
    )
    R_mount = (
        GeoProjector._rot_z(float(cfg.true_mount_yaw_deg))
        @ GeoProjector._rot_y(float(cfg.true_mount_pitch_deg))
        @ GeoProjector._rot_x(float(cfg.true_mount_roll_deg))
    )

    # body -> cam (OpenCV): ray_cam = R_body_cam_align^T * R_mount^T * ray_body
    p_cam = R_body_cam_align.T @ (R_mount.T @ p_body)
    z = float(p_cam[2])
    if not math.isfinite(z) or z <= 1e-9:
        return None

    fx, fy, cx, cy = _fx_fy(cfg.image_w, cfg.image_h, cfg.true_vfov_deg)
    u = fx * (float(p_cam[0]) / z) + cx
    v = fy * (float(p_cam[1]) / z) + cy
    return float(u), float(v)


def _offset_latlon(lat0: float, lon0: float, north_m: float, east_m: float) -> Tuple[float, float]:
    R = 6371000.0
    lat_rad = math.radians(float(lat0))
    dlat = float(north_m) / R
    denom = R * (math.cos(lat_rad) or 1e-6)
    dlon = float(east_m) / denom
    return float(lat0) + math.degrees(dlat), float(lon0) + math.degrees(dlon)


def _latlon_delta_m(lat0: float, lon0: float, lat1: float, lon1: float) -> Tuple[float, float]:
    R = 6371000.0
    dlat = math.radians(float(lat1 - lat0))
    dlon = math.radians(float(lon1 - lon0))
    north = dlat * R
    east = dlon * R * (math.cos(math.radians(float(lat0))) or 1e-6)
    return float(north), float(east)


def _percentile(x: np.ndarray, p: float) -> float:
    if x.size == 0:
        return float("nan")
    return float(np.percentile(x, p))


def _stats(x: np.ndarray) -> dict:
    if x.size == 0:
        return {"mean": float("nan"), "p50": float("nan"), "p95": float("nan"), "p99": float("nan"), "max": float("nan")}
    return {
        "mean": float(np.mean(x)),
        "p50": _percentile(x, 50),
        "p95": _percentile(x, 95),
        "p99": _percentile(x, 99),
        "max": float(np.max(x)),
    }


def run_eval(cfg: EvalCfg, *, px_sigma: float, yaw_sigma: float, pitch_sigma: float, roll_sigma: float, alt_sigma: float) -> dict:
    rng = np.random.default_rng(int(cfg.seed))

    # Fixed drone global reference (errors are computed in meters).
    drone_lat = 42.0
    drone_lon = -1.0

    points = []
    attempts = 0
    max_attempts = int(cfg.samples * 60)
    while len(points) < cfg.samples and attempts < max_attempts:
        attempts += 1
        north = float(rng.uniform(cfg.min_range_m, cfg.max_range_m))
        east = float(rng.uniform(-cfg.max_east_m, cfg.max_east_m))
        if math.hypot(north, east) > float(cfg.max_range_m):
            continue
        uv = _project_ground_to_pixel(north, east, cfg)
        if uv is None:
            continue
        u, v = uv
        if 0.0 <= u < float(cfg.image_w) and 0.0 <= v < float(cfg.image_h):
            points.append((north, east, u, v))

    if len(points) < cfg.samples:
        raise SystemExit(f"insufficient_visible_samples: got={len(points)} target={cfg.samples} attempts={attempts}")

    pos_err = []
    dist_err = []
    invalid = 0

    for north, east, u_gt, v_gt in points:
        # True global coords for the ground point.
        gt_lat, gt_lon = _offset_latlon(drone_lat, drone_lon, north, east)
        gt_dist = math.hypot(north, east)

        # Add noise (bbox jitter + telemetry noise).
        u = float(u_gt + rng.normal(0.0, float(px_sigma)))
        v = float(v_gt + rng.normal(0.0, float(px_sigma)))

        yaw = float(cfg.yaw_deg + rng.normal(0.0, float(yaw_sigma)))
        pitch = float(cfg.pitch_deg + rng.normal(0.0, float(pitch_sigma)))
        roll = float(cfg.roll_deg + rng.normal(0.0, float(roll_sigma)))
        alt = float(cfg.alt_agl_m + rng.normal(0.0, float(alt_sigma)))

        pred = GeoProjector.pixel_to_gps(
            v,
            u,
            image_height=int(cfg.image_h),
            image_width=int(cfg.image_w),
            drone_lat=float(drone_lat),
            drone_lon=float(drone_lon),
            drone_yaw_deg=float(yaw),
            drone_pitch_deg=float(pitch),
            drone_roll_deg=float(roll),
            alt_agl_m=float(alt),
            camera_vfov_deg=float(cfg.vfov_deg),
            mount_roll_deg=float(cfg.mount_roll_deg),
            mount_pitch_deg=float(cfg.mount_pitch_deg),
            mount_yaw_deg=float(cfg.mount_yaw_deg),
            max_range_m=float(cfg.max_range_m),
        )
        if pred is None:
            invalid += 1
            continue

        pred_lat, pred_lon, pred_dist = pred
        dn, de = _latlon_delta_m(gt_lat, gt_lon, pred_lat, pred_lon)
        pos_err.append(math.hypot(dn, de))
        dist_err.append(abs(float(pred_dist) - float(gt_dist)))

    pos_err_arr = np.array(pos_err, dtype=float)
    dist_err_arr = np.array(dist_err, dtype=float)

    return {
        "px_sigma": float(px_sigma),
        "yaw_sigma": float(yaw_sigma),
        "pitch_sigma": float(pitch_sigma),
        "roll_sigma": float(roll_sigma),
        "alt_sigma": float(alt_sigma),
        "invalid_frac": float(invalid) / float(cfg.samples),
        "pos_err": _stats(pos_err_arr),
        "dist_err": _stats(dist_err_arr),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate pixel->ground projection error.")
    p.add_argument("--samples", type=int, default=5000)
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--image-w", type=int, default=640)
    p.add_argument("--image-h", type=int, default=640)
    p.add_argument("--vfov-deg", type=float, default=45.0)
    p.add_argument("--true-vfov-deg", type=float, default=None, help="Ground-truth VFOV (defaults to --vfov-deg).")
    p.add_argument("--mount-pitch-deg", type=float, default=-30.0)
    p.add_argument("--mount-roll-deg", type=float, default=0.0)
    p.add_argument("--mount-yaw-deg", type=float, default=0.0)
    p.add_argument("--true-mount-pitch-deg", type=float, default=None, help="Ground-truth mount pitch (defaults to --mount-pitch-deg).")
    p.add_argument("--true-mount-roll-deg", type=float, default=None, help="Ground-truth mount roll (defaults to --mount-roll-deg).")
    p.add_argument("--true-mount-yaw-deg", type=float, default=None, help="Ground-truth mount yaw (defaults to --mount-yaw-deg).")
    p.add_argument("--yaw-deg", type=float, default=0.0)
    p.add_argument("--pitch-deg", type=float, default=0.0)
    p.add_argument("--roll-deg", type=float, default=0.0)
    p.add_argument("--alt-agl-m", type=float, default=30.0)
    p.add_argument("--max-range-m", type=float, default=75.0)
    p.add_argument("--min-range-m", type=float, default=5.0)
    p.add_argument("--max-east-m", type=float, default=40.0)
    p.add_argument("--px-sigmas", type=str, default="0,2,5,10,20", help="Comma-separated pixel stddev list (bbox jitter proxy).")
    p.add_argument("--yaw-sigma-deg", type=float, default=0.5)
    p.add_argument("--pitch-sigma-deg", type=float, default=0.5)
    p.add_argument("--roll-sigma-deg", type=float, default=0.5)
    p.add_argument("--alt-sigma-m", type=float, default=0.5)
    return p.parse_args()


def main() -> int:
    args = parse_args()

    true_vfov_deg = float(args.vfov_deg if args.true_vfov_deg is None else args.true_vfov_deg)
    true_mount_pitch_deg = float(args.mount_pitch_deg if args.true_mount_pitch_deg is None else args.true_mount_pitch_deg)
    true_mount_roll_deg = float(args.mount_roll_deg if args.true_mount_roll_deg is None else args.true_mount_roll_deg)
    true_mount_yaw_deg = float(args.mount_yaw_deg if args.true_mount_yaw_deg is None else args.true_mount_yaw_deg)

    cfg = EvalCfg(
        samples=int(args.samples),
        seed=int(args.seed),
        image_w=int(args.image_w),
        image_h=int(args.image_h),
        vfov_deg=float(args.vfov_deg),
        true_vfov_deg=true_vfov_deg,
        mount_pitch_deg=float(args.mount_pitch_deg),
        mount_roll_deg=float(args.mount_roll_deg),
        mount_yaw_deg=float(args.mount_yaw_deg),
        true_mount_pitch_deg=true_mount_pitch_deg,
        true_mount_roll_deg=true_mount_roll_deg,
        true_mount_yaw_deg=true_mount_yaw_deg,
        yaw_deg=float(args.yaw_deg),
        pitch_deg=float(args.pitch_deg),
        roll_deg=float(args.roll_deg),
        alt_agl_m=float(args.alt_agl_m),
        max_range_m=float(args.max_range_m),
        min_range_m=float(args.min_range_m),
        max_east_m=float(args.max_east_m),
    )

    def _parse_sigmas(s: str) -> list[float]:
        out: list[float] = []
        for part in str(s).split(","):
            part = part.strip()
            if not part:
                continue
            out.append(float(part))
        if not out:
            raise SystemExit("empty_px_sigmas")
        return out

    px_sigmas = _parse_sigmas(args.px_sigmas)

    # Telemetry noise (use 0 for SITL-ideal projection sanity checks).
    yaw_sigma = float(args.yaw_sigma_deg)
    pitch_sigma = float(args.pitch_sigma_deg)
    roll_sigma = float(args.roll_sigma_deg)
    alt_sigma = float(args.alt_sigma_m)

    print("[eval] cfg:", cfg)
    print(f"[eval] telemetry_noise: yaw/pitch/roll_sigma={yaw_sigma}deg alt_sigma={alt_sigma}m")
    rows = []
    for px_sigma in px_sigmas:
        name = f"px{px_sigma:g}"
        out = run_eval(cfg, px_sigma=px_sigma, yaw_sigma=yaw_sigma, pitch_sigma=pitch_sigma, roll_sigma=roll_sigma, alt_sigma=alt_sigma)
        rows.append((name, out))

    # Print a compact table.
    header = "scenario  invalid%  pos_p50  pos_p95  pos_p99  pos_max  dist_p50  dist_p95  dist_p99  dist_max"
    print(header)
    for name, out in rows:
        inv = 100.0 * float(out["invalid_frac"])
        pe = out["pos_err"]
        de = out["dist_err"]
        print(
            f"{name:8s}  {inv:7.2f}  {pe['p50']:7.2f}  {pe['p95']:7.2f}  {pe['p99']:7.2f}  {pe['max']:7.2f}"
            f"  {de['p50']:8.2f}  {de['p95']:8.2f}  {de['p99']:8.2f}  {de['max']:8.2f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
