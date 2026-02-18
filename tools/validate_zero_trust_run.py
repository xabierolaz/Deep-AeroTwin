#!/usr/bin/env python3
"""Zero-trust validator for Pipeline A audit runs."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _to_float(value: Any, default: float = float("nan")) -> float:
    try:
        if value is None:
            return float(default)
        text = str(value).strip()
        if not text:
            return float(default)
        return float(text)
    except Exception:
        return float(default)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        text = str(value).strip()
        if not text:
            return int(default)
        return int(float(text))
    except Exception:
        return int(default)


def _pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    vals = sorted(float(v) for v in values)
    if len(vals) == 1:
        return float(vals[0])
    rank = (len(vals) - 1) * (float(p) / 100.0)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return float(vals[lo])
    frac = rank - lo
    return float(vals[lo] * (1.0 - frac) + vals[hi] * frac)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6_371_000.0
    p1 = math.radians(float(lat1))
    p2 = math.radians(float(lat2))
    dp = math.radians(float(lat2) - float(lat1))
    dl = math.radians(float(lon2) - float(lon1))
    a = (math.sin(dp / 2.0) ** 2) + math.cos(p1) * math.cos(p2) * (math.sin(dl / 2.0) ** 2)
    return float(2.0 * radius_m * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a))))


def _parse_waypoints(path: Path) -> list[dict[str, float | int]]:
    waypoints: list[dict[str, float | int]] = []
    with path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            line = raw.strip()
            if (not line) or line.startswith("QGC"):
                continue
            parts = line.split()
            if len(parts) < 11:
                continue
            waypoints.append(
                {
                    "seq": _to_int(parts[0], 0),
                    "lat": _to_float(parts[8], 0.0),
                    "lon": _to_float(parts[9], 0.0),
                    "alt": _to_float(parts[10], 0.0),
                }
            )
    return waypoints


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if (not line) or line.startswith("#") or ("=" not in line):
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def _resolve_run_dir(project_root: Path, run_dir_arg: str) -> Path:
    if run_dir_arg:
        run_dir = Path(run_dir_arg).expanduser()
    else:
        latest_file = project_root / "pipeline" / "logs" / "zero_trust" / "LATEST_RUN.txt"
        if not latest_file.exists():
            raise FileNotFoundError(f"LATEST_RUN.txt no existe: {latest_file}")
        latest = latest_file.read_text(encoding="utf-8", errors="replace").strip()
        if not latest:
            raise RuntimeError(f"LATEST_RUN.txt vacio: {latest_file}")
        run_dir = Path(latest)

    if not run_dir.exists():
        raise FileNotFoundError(f"Run dir no existe: {run_dir}")

    # Compatibilidad: aceptar root run, o path directo a /brain
    if (run_dir / "brain" / "trajectory.csv").exists():
        return run_dir
    if run_dir.name.lower() == "brain" and (run_dir / "trajectory.csv").exists():
        return run_dir.parent
    if (run_dir / "trajectory.csv").exists() and run_dir.name.lower() == "brain":
        return run_dir.parent
    if (run_dir / "trajectory.csv").exists() and (run_dir.parent / "vision").exists():
        return run_dir.parent
    raise FileNotFoundError(
        "No encuentro trajectory.csv en run dir. Esperado: <run>/brain/trajectory.csv"
    )


def _load_trajectory(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        for raw in reader:
            ts = _to_float(raw.get("ts"), float("nan"))
            if not math.isfinite(ts):
                continue
            lat = _to_float(raw.get("lat"), 0.0)
            lon = _to_float(raw.get("lon"), 0.0)
            rows.append(
                {
                    "ts": float(ts),
                    "lat": float(lat),
                    "lon": float(lon),
                    "alt_msl": _to_float(raw.get("alt_msl"), 0.0),
                    "rel_alt": _to_float(raw.get("rel_alt"), 0.0),
                    "mode": str(raw.get("mode", "") or "").strip().upper(),
                    "armed": bool(_to_int(raw.get("armed"), 0)),
                    "wp_idx": _to_int(raw.get("wp_idx"), 0),
                }
            )
    rows.sort(key=lambda r: float(r["ts"]))
    return rows


def _load_vision_metrics(path: Path) -> dict[str, Any]:
    dims_counter: Counter[tuple[int, int]] = Counter()
    max_abs_pitch = 0.0
    max_abs_roll = 0.0
    valid_att_samples = 0
    if not path.exists():
        return {
            "vision_events_found": False,
            "capture_dims_counter": {},
            "max_abs_pitch_deg": float("nan"),
            "max_abs_roll_deg": float("nan"),
            "valid_att_samples": 0,
        }
    with path.open("r", encoding="utf-8", errors="replace") as fp:
        for raw in fp:
            line = raw.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("kind") != "vision_frame":
                continue
            cap = rec.get("capture") or {}
            w = _to_int(cap.get("w"), -1)
            h = _to_int(cap.get("h"), -1)
            if w > 0 and h > 0:
                dims_counter[(w, h)] += 1
            tel = rec.get("telemetry") or {}
            pitch = _to_float(tel.get("pitch"), float("nan"))
            roll = _to_float(tel.get("roll"), float("nan"))
            lat = _to_float(tel.get("lat"), float("nan"))
            lon = _to_float(tel.get("lon"), float("nan"))
            if not (math.isfinite(pitch) and math.isfinite(roll)):
                continue
            if not (math.isfinite(lat) and math.isfinite(lon)):
                continue
            if abs(float(lat)) < 1e-9 and abs(float(lon)) < 1e-9:
                continue
            valid_att_samples += 1
            max_abs_pitch = max(max_abs_pitch, abs(float(pitch)))
            max_abs_roll = max(max_abs_roll, abs(float(roll)))
    return {
        "vision_events_found": True,
        "capture_dims_counter": {f"{k[0]}x{k[1]}": int(v) for k, v in dims_counter.items()},
        "max_abs_pitch_deg": float(max_abs_pitch),
        "max_abs_roll_deg": float(max_abs_roll),
        "valid_att_samples": int(valid_att_samples),
    }


def _format_f(value: float, ndigits: int = 2) -> str:
    if not math.isfinite(value):
        return "nan"
    return f"{value:.{ndigits}f}"


def main() -> int:
    p = argparse.ArgumentParser(description="Zero-trust validation de vuelo (altura + waypoints + captura).")
    p.add_argument("--run-dir", default="", help="Directorio del run audit. Por defecto usa LATEST_RUN.txt.")
    p.add_argument("--waypoints", default="pipeline/ejea_default.waypoints")
    p.add_argument("--arrival-tol-m", type=float, default=5.5)
    p.add_argument("--alt-tol-m", type=float, default=1.0)
    p.add_argument("--land-rel-alt-max-m", type=float, default=0.3)
    p.add_argument("--expect-vfov-deg", type=float, default=84.0)
    p.add_argument("--expect-camera-pitch-deg", type=float, default=-15.0)
    p.add_argument("--expect-capture-w", type=int, default=640)
    p.add_argument("--expect-capture-h", type=int, default=640)
    p.add_argument(
        "--max-abs-pitch-deg",
        type=float,
        default=-1.0,
        help="Si <0, no valida pitch absoluto.",
    )
    p.add_argument(
        "--max-abs-roll-deg",
        type=float,
        default=-1.0,
        help="Si <0, no valida roll absoluto.",
    )
    p.add_argument("--json-out", default="", help="Ruta opcional para guardar reporte JSON.")
    args = p.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    run_dir = _resolve_run_dir(project_root, args.run_dir)
    trajectory_path = run_dir / "brain" / "trajectory.csv"
    vision_events_path = run_dir / "vision" / "events.jsonl"
    env_path = run_dir / "PORCE_ENV.txt"
    waypoints_path = Path(args.waypoints)
    if not waypoints_path.is_absolute():
        waypoints_path = project_root / waypoints_path

    rows = _load_trajectory(trajectory_path)
    if not rows:
        raise RuntimeError(f"trajectory vacia: {trajectory_path}")
    waypoints = _parse_waypoints(waypoints_path)
    if len(waypoints) < 2:
        raise RuntimeError(f"waypoints invalidos: {waypoints_path}")

    valid_rows = [r for r in rows if not (abs(float(r["lat"])) < 1e-9 and abs(float(r["lon"])) < 1e-9)]
    if not valid_rows:
        raise RuntimeError("No hay telemetry GPS valida en trajectory.csv")

    home_alt = float(waypoints[0]["alt"])
    last_nav_idx = max(2, len(waypoints) - 2)
    nav_indices = [i for i in range(2, len(waypoints) - 1)]

    takeoff_target_rel = float(waypoints[1]["alt"]) - home_alt
    wp1_rows = [r for r in rows if int(r["wp_idx"]) <= 2]
    takeoff_peak_rel = max([float(r["rel_alt"]) for r in wp1_rows], default=float("nan"))
    takeoff_ok = math.isfinite(takeoff_peak_rel) and (takeoff_peak_rel >= (takeoff_target_rel - float(args.alt_tol_m)))

    cruise_rows = [r for r in valid_rows if 2 <= int(r["wp_idx"]) <= int(last_nav_idx)]
    cruise_errs: list[float] = []
    for r in cruise_rows:
        wp_idx = int(r["wp_idx"])
        if wp_idx >= len(waypoints):
            continue
        target_rel = float(waypoints[wp_idx]["alt"]) - home_alt
        cruise_errs.append(abs(float(r["rel_alt"]) - target_rel))
    cruise_p50 = _pct(cruise_errs, 50.0)
    cruise_p95 = _pct(cruise_errs, 95.0)
    cruise_max = max(cruise_errs) if cruise_errs else float("nan")
    cruise_ok = bool(cruise_errs) and math.isfinite(cruise_p95) and (cruise_p95 <= float(args.alt_tol_m) * 1.5)

    land_rows = [r for r in rows if str(r["mode"]) == "LAND" or int(r["wp_idx"]) >= len(waypoints)]
    land_final_rel = float(land_rows[-1]["rel_alt"]) if land_rows else float(rows[-1]["rel_alt"])
    land_ok = land_final_rel <= float(args.land_rel_alt_max_m)

    wp_results: list[dict[str, Any]] = []
    nav_reached = 0
    nav_alt_ok = 0
    for wp_idx in nav_indices:
        wp = waypoints[wp_idx]
        subset = [r for r in valid_rows if int(r["wp_idx"]) == int(wp_idx)]
        subset_global = valid_rows
        if not subset:
            wp_results.append(
                {
                    "wp_idx": int(wp_idx),
                    "samples": 0,
                    "target_rel_alt_m": float(wp["alt"]) - home_alt,
                    "min_dist_m": float("nan"),
                    "min_alt_err_m": float("nan"),
                    "reached": False,
                    "alt_ok": False,
                }
            )
            continue
        dists = [
            _haversine_m(float(r["lat"]), float(r["lon"]), float(wp["lat"]), float(wp["lon"]))
            for r in subset
        ]
        dists_global = [
            _haversine_m(float(r["lat"]), float(r["lon"]), float(wp["lat"]), float(wp["lon"]))
            for r in subset_global
        ]
        target_rel = float(wp["alt"]) - home_alt
        alt_errs = [abs(float(r["rel_alt"]) - target_rel) for r in subset]
        min_dist = min(dists_global) if dists_global else float("nan")
        min_alt_err = min(alt_errs) if alt_errs else float("nan")
        reached = bool(math.isfinite(min_dist) and (min_dist <= float(args.arrival_tol_m)))
        alt_ok = bool(math.isfinite(min_alt_err) and (min_alt_err <= float(args.alt_tol_m)))
        nav_reached += int(reached)
        nav_alt_ok += int(alt_ok)
        wp_results.append(
            {
                "wp_idx": int(wp_idx),
                "samples": len(subset),
                "target_rel_alt_m": float(target_rel),
                "min_dist_m": float(min_dist),
                "min_alt_err_m": float(min_alt_err),
                "reached": bool(reached),
                "alt_ok": bool(alt_ok),
            }
        )

    nav_total = len(nav_indices)
    nav_reached_ok = (nav_total == 0) or (nav_reached == nav_total)
    nav_alt_ok_all = (nav_total == 0) or (nav_alt_ok == nav_total)

    max_wp_idx_seen = max(int(r["wp_idx"]) for r in rows)
    mission_progress_ok = max_wp_idx_seen >= len(waypoints)

    env_map = _parse_env_file(env_path)
    vfov_env = _to_float(env_map.get("PORCE_CAMERA_VFOV_DEG"), float("nan"))
    pitch_env = _to_float(env_map.get("PORCE_CAMERA_MOUNT_PITCH_DEG"), float("nan"))
    cap_w_env = _to_int(env_map.get("PORCE_CAPTURE_EXPECT_WIDTH"), -1)
    cap_h_env = _to_int(env_map.get("PORCE_CAPTURE_EXPECT_HEIGHT"), -1)
    camera_env_checked = (
        math.isfinite(vfov_env)
        and math.isfinite(pitch_env)
        and (cap_w_env > 0)
        and (cap_h_env > 0)
    )
    camera_env_ok = True
    if camera_env_checked:
        camera_env_ok = (
            (abs(vfov_env - float(args.expect_vfov_deg)) <= 1e-6)
            and (abs(pitch_env - float(args.expect_camera_pitch_deg)) <= 1e-6)
            and (cap_w_env == int(args.expect_capture_w))
            and (cap_h_env == int(args.expect_capture_h))
        )

    vision_metrics = _load_vision_metrics(vision_events_path)
    dims_counter = vision_metrics["capture_dims_counter"]
    dims_ok = False
    if dims_counter:
        dims_ok = (len(dims_counter) == 1) and (f"{args.expect_capture_w}x{args.expect_capture_h}" in dims_counter)
    pitch_max = _to_float(vision_metrics.get("max_abs_pitch_deg"), float("nan"))
    roll_max = _to_float(vision_metrics.get("max_abs_roll_deg"), float("nan"))
    attitude_checked = float(args.max_abs_pitch_deg) >= 0.0 and float(args.max_abs_roll_deg) >= 0.0
    attitude_ok = True
    if attitude_checked:
        attitude_ok = (
            math.isfinite(pitch_max)
            and math.isfinite(roll_max)
            and (pitch_max <= float(args.max_abs_pitch_deg))
            and (roll_max <= float(args.max_abs_roll_deg))
        )

    checks = {
        "mission_progress_ok": bool(mission_progress_ok),
        "takeoff_altitude_ok": bool(takeoff_ok),
        "cruise_altitude_ok": bool(cruise_ok),
        "landing_altitude_ok": bool(land_ok),
        "nav_waypoints_reached_ok": bool(nav_reached_ok),
        "nav_waypoint_altitudes_ok": bool(nav_alt_ok_all),
        "camera_env_ok": bool(camera_env_ok),
        "capture_dims_ok": bool(dims_ok),
        "attitude_flat_ok": bool(attitude_ok),
    }
    overall_ok = all(checks.values())

    summary = {
        "run_dir": str(run_dir),
        "trajectory_path": str(trajectory_path),
        "waypoints_path": str(waypoints_path),
        "rows_total": int(len(rows)),
        "rows_valid_gps": int(len(valid_rows)),
        "duration_s": float(rows[-1]["ts"] - rows[0]["ts"]),
        "home_alt_msl_m": float(home_alt),
        "max_wp_idx_seen": int(max_wp_idx_seen),
        "waypoints_count": int(len(waypoints)),
        "takeoff": {
            "target_rel_alt_m": float(takeoff_target_rel),
            "peak_rel_alt_m": float(takeoff_peak_rel),
            "tol_m": float(args.alt_tol_m),
            "ok": bool(takeoff_ok),
        },
        "cruise": {
            "samples": int(len(cruise_errs)),
            "rel_alt_err_p50_m": float(cruise_p50),
            "rel_alt_err_p95_m": float(cruise_p95),
            "rel_alt_err_max_m": float(cruise_max),
            "ok": bool(cruise_ok),
        },
        "landing": {
            "final_rel_alt_m": float(land_final_rel),
            "max_rel_alt_m": float(args.land_rel_alt_max_m),
            "ok": bool(land_ok),
        },
        "nav_waypoints": {
            "total": int(nav_total),
            "reached": int(nav_reached),
            "alt_ok": int(nav_alt_ok),
            "arrival_tol_m": float(args.arrival_tol_m),
            "alt_tol_m": float(args.alt_tol_m),
            "per_wp": wp_results,
        },
        "camera_env": {
            "PORCE_CAMERA_VFOV_DEG": vfov_env,
            "PORCE_CAMERA_MOUNT_PITCH_DEG": pitch_env,
            "PORCE_CAPTURE_EXPECT_WIDTH": cap_w_env,
            "PORCE_CAPTURE_EXPECT_HEIGHT": cap_h_env,
            "checked": bool(camera_env_checked),
            "ok": bool(camera_env_ok),
        },
        "vision_capture": {
            "dims_counter": dims_counter,
            "max_abs_pitch_deg": float(pitch_max),
            "max_abs_roll_deg": float(roll_max),
            "valid_att_samples": int(vision_metrics.get("valid_att_samples", 0) or 0),
            "dims_ok": bool(dims_ok),
            "attitude_checked": bool(attitude_checked),
            "attitude_ok": bool(attitude_ok),
        },
        "checks": checks,
        "overall_ok": bool(overall_ok),
    }

    print(f"[ZERO-TRUST] run={run_dir}")
    print(
        f"[ZERO-TRUST] rows={len(rows)} valid_gps={len(valid_rows)} duration={_format_f(summary['duration_s'], 1)}s "
        f"wps={len(waypoints)} max_wp_idx={max_wp_idx_seen}"
    )
    print(
        f"[CHECK] takeoff alt: target_rel={_format_f(takeoff_target_rel)}m peak={_format_f(takeoff_peak_rel)}m "
        f"tol={_format_f(float(args.alt_tol_m))} -> {'PASS' if takeoff_ok else 'FAIL'}"
    )
    print(
        f"[CHECK] cruise alt err: p50={_format_f(cruise_p50)}m p95={_format_f(cruise_p95)}m max={_format_f(cruise_max)}m "
        f"-> {'PASS' if cruise_ok else 'FAIL'}"
    )
    print(
        f"[CHECK] landing rel_alt: final={_format_f(land_final_rel)}m max={_format_f(float(args.land_rel_alt_max_m))}m "
        f"-> {'PASS' if land_ok else 'FAIL'}"
    )
    print(
        f"[CHECK] nav reached: {nav_reached}/{nav_total} (tol={_format_f(float(args.arrival_tol_m))}m) "
        f"-> {'PASS' if nav_reached_ok else 'FAIL'}"
    )
    print(
        f"[CHECK] nav alt ok: {nav_alt_ok}/{nav_total} (tol={_format_f(float(args.alt_tol_m))}m) "
        f"-> {'PASS' if nav_alt_ok_all else 'FAIL'}"
    )
    camera_status = "PASS" if camera_env_ok else "FAIL"
    if not camera_env_checked:
        camera_status = "SKIP"
    print(
        f"[CHECK] camera env: vfov={_format_f(vfov_env)} pitch={_format_f(pitch_env)} "
        f"cap={cap_w_env}x{cap_h_env} -> {camera_status}"
    )
    print(f"[CHECK] capture dims: {dims_counter if dims_counter else '{}'} -> {'PASS' if dims_ok else 'FAIL'}")
    att_status = "PASS" if attitude_ok else "FAIL"
    if not attitude_checked:
        att_status = "SKIP"
    print(
        f"[CHECK] attitude flat: |pitch|max={_format_f(pitch_max)}deg |roll|max={_format_f(roll_max)}deg "
        f"-> {att_status}"
    )
    print(f"[RESULT] {'PASS' if overall_ok else 'FAIL'}")

    out_path = Path(args.json_out) if args.json_out else (run_dir / "ZERO_TRUST_FLIGHT_REPORT.json")
    if not out_path.is_absolute():
        out_path = (project_root / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[REPORT] {out_path}")

    return 0 if overall_ok else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[ABORT] KeyboardInterrupt", file=sys.stderr)
        raise SystemExit(130)
