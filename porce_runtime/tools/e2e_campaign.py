#!/usr/bin/env python3
"""E2E statistical campaign harness (D2, 2026-06-12).

Rebuilds the Feb-17 mock-MAVLink ablation harness: 4 scenarios
(PORCE on/off x detections/no-detections), N runs each, parallel workers.

Each run:
  - starts pipeline/flight_controller.py with PORCE_MOCK_MAVLINK=1
  - waits for HTTP ready and takeoff completion (wp_idx >= 2)
  - (with_detections) injects a synthetic biker obstacle via POST /api/obstacles
    (source=vision, passes the zero-trust source filter) at 3 Hz for 15 s,
    placed ~35 m ahead of the drone along the bearing to the active waypoint
  - waits for mission completion (mission_state == COMPLETED) or timeout
  - archives brain.log (launcher-compatible format) + zero-trust audit dir
    (brain/events.jsonl with planner_obs_ids from the D3 patch, trajectory.csv)

Usage (Windows, from repo root):
  venv\\Scripts\\python.exe tools\\e2e_campaign.py --runs 10 --workers 4
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = REPO_ROOT / "pipeline"
E2E_ROOT = PIPELINE_DIR / "logs" / "e2e"
VENV_PY = REPO_ROOT.parent / "venv" / "Scripts" / "python.exe"
DEFAULTS_ENV = PIPELINE_DIR / "porce_defaults.env"

SCENARIOS = {
    "porce_on_with_detections": {"evasion": "1", "inject": True},
    "porce_off_with_detections": {"evasion": "0", "inject": True},
    "porce_on_no_detections": {"evasion": "1", "inject": False},
    "porce_off_no_detections": {"evasion": "0", "inject": False},
}

HTTP_READY_TIMEOUT_S = 45.0
TAKEOFF_TIMEOUT_S = 180.0
SCENARIO_TIMEOUT_S = 420.0
TAKEOFF_COMPLETE_WP_IDX = 2
INJECT_DURATION_S = 15.0
INJECT_HZ = 3.0
INJECT_DISTANCE_M = 35.0
INJECT_MARGIN = 0.95
INJECT_TYPE = "biker"
INJECT_SOURCE = "vision"
INJECT_CONFIDENCE = 0.99
POLL_S = 1.0

STATUS_RE = re.compile(
    r"^(?P<h>\d\d):(?P<m>\d\d):(?P<s>\d\d).+?GPS: (?P<lat>[-0-9.]+), (?P<lon>[-0-9.]+) "
    r"Alt: (?P<alt>[-0-9.]+)m .*?\| WP: (?P<wp>\d+) \| Obs: (?P<obs>\d+)"
)

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_defaults_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if not DEFAULTS_ENV.exists():
        return env
    for line in DEFAULTS_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().replace("%PROJECT_ROOT%", str(REPO_ROOT))
        if key:
            env[key] = value
    return env


def http_json(url: str, *, timeout: float = 2.0) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def http_post_json(url: str, payload: dict, headers: dict[str, str], *, timeout: float = 2.0) -> int:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except Exception:
        return -1


def offset_latlon(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    dlat = math.degrees(north_m / 6_371_000.0)
    dlon = math.degrees(east_m / (6_371_000.0 * max(math.cos(math.radians(lat)), 1e-6)))
    return lat + dlat, lon + dlon


def bearing_unit(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    north = math.radians(lat2 - lat1) * 6_371_000.0
    east = math.radians(lon2 - lon1) * 6_371_000.0 * max(math.cos(math.radians(lat1)), 1e-6)
    norm = math.hypot(north, east)
    if norm < 1e-9:
        return 1.0, 0.0
    return north / norm, east / norm


def kill_port_listeners(port: int) -> None:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue).OwningProcess"],
            capture_output=True, text=True, timeout=15,
        ).stdout
        for pid in {p.strip() for p in out.splitlines() if p.strip().isdigit()}:
            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True, timeout=10)
    except Exception:
        pass


def parse_brain_log(path: Path) -> dict:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = STATUS_RE.match(line)
        if not m:
            continue
        rows.append(
            {
                "t": int(m.group("h")) * 3600 + int(m.group("m")) * 60 + int(m.group("s")),
                "lat": float(m.group("lat")),
                "lon": float(m.group("lon")),
                "wp": int(m.group("wp")),
                "obs": int(m.group("obs")),
            }
        )
    if not rows:
        return {"duration_s": None, "path_length_m": None, "max_wp_idx": None, "mean_obstacles": None}
    path_m = 0.0
    for a, b in zip(rows, rows[1:]):
        p1 = math.radians(a["lat"]); p2 = math.radians(b["lat"])
        dphi = math.radians(b["lat"] - a["lat"]); dlmb = math.radians(b["lon"] - a["lon"])
        h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
        path_m += 2 * 6_371_000.0 * math.asin(math.sqrt(h))
    return {
        "duration_s": rows[-1]["t"] - rows[0]["t"],
        "path_length_m": round(path_m, 1),
        "max_wp_idx": max(r["wp"] for r in rows),
        "mean_obstacles": round(sum(r["obs"] for r in rows) / len(rows), 2),
    }


def run_one(scenario: str, run_idx: int, port: int, base_env: dict[str, str], jitter: bool) -> dict:
    cfg = SCENARIOS[scenario]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"{scenario}_{stamp}_r{run_idx:02d}"
    run_dir = E2E_ROOT / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(16)

    env = dict(os.environ)
    env.update(base_env)
    env.update(
        {
            "PORCE_SYSTEM_MODE": "SIMULATION",
            "PORCE_MOCK_MAVLINK": "1",
            "PORCE_FORCE_ARM": "1",
            "PORCE_ENABLE_EVASION": cfg["evasion"],
            "PORCE_BRAIN_HTTP_PORT": str(port),
            "PORCE_BRAIN_HTTP_HOST": "127.0.0.1",
            "PORCE_BRAIN_APP_BIND_HOST": "127.0.0.1",
            "PORCE_OBSTACLE_TOKEN": token,
            "PORCE_OBSTACLE_TOKEN_REQUIRED": "1",
            "PORCE_UNREAL_TELEMETRY_INGEST_ENABLE": "0",
            "PORCE_AUDIT_ENABLE": "1",
            "PORCE_AUDIT_ROOT": str(run_dir),
            "PORCE_CONFIG_BANNER": "0",
        }
    )

    kill_port_listeners(port)
    brain_log = run_dir / "brain.log"
    meta: dict = {
        "run": run_name,
        "scenario": scenario,
        "run_idx": run_idx,
        "port": port,
        "evasion": cfg["evasion"] == "1",
        "inject": cfg["inject"],
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "ok": False,
        "mission_completed": False,
        "saw_evasion": False,
        "timeout": False,
        "error": None,
        "inject_meta": None,
    }
    base_url = f"http://127.0.0.1:{port}"
    proc = None
    try:
        with brain_log.open("w", encoding="utf-8") as log_fp:
            proc = subprocess.Popen(
                [str(VENV_PY), "-u", "flight_controller.py"],
                cwd=str(PIPELINE_DIR),
                env=env,
                stdout=log_fp,
                stderr=subprocess.STDOUT,
            )
            deadline = time.time() + HTTP_READY_TIMEOUT_S
            status = None
            while time.time() < deadline:
                status = http_json(f"{base_url}/api/status")
                if status:
                    break
                if proc.poll() is not None:
                    raise RuntimeError("brain exited during startup")
                time.sleep(0.5)
            if not status:
                raise RuntimeError("brain HTTP not ready")

            deadline = time.time() + TAKEOFF_TIMEOUT_S
            while time.time() < deadline:
                status = http_json(f"{base_url}/api/status") or {}
                if int(status.get("wp_idx", 0) or 0) >= TAKEOFF_COMPLETE_WP_IDX:
                    break
                if proc.poll() is not None:
                    raise RuntimeError("brain exited before takeoff")
                time.sleep(POLL_S)
            else:
                raise RuntimeError("takeoff timeout")

            if cfg["inject"]:
                ui = http_json(f"{base_url}/api/ui/data") or {}
                tel = ui.get("telemetry") or {}
                lat0 = float(tel.get("lat"))
                lon0 = float(tel.get("lon"))
                wps = ui.get("waypoints") or []
                wp_idx = int((http_json(f"{base_url}/api/status") or {}).get("wp_idx", 2) or 2)
                target = wps[min(wp_idx, len(wps) - 1)] if wps else {"lat": lat0 + 0.001, "lon": lon0}
                n_unit, e_unit = bearing_unit(lat0, lon0, float(target["lat"]), float(target["lon"]))
                dist = INJECT_DISTANCE_M * INJECT_MARGIN
                lat_n = dist * n_unit
                lon_e = dist * e_unit
                if jitter:
                    lateral = random.uniform(-3.0, 3.0)
                    lat_n += -e_unit * lateral
                    lon_e += n_unit * lateral
                obs_lat, obs_lon = offset_latlon(lat0, lon0, lat_n, lon_e)
                meta["inject_meta"] = {
                    "obs_lat": obs_lat,
                    "obs_lon": obs_lon,
                    "from_lat": lat0,
                    "from_lon": lon0,
                    "distance_m": dist,
                    "type": INJECT_TYPE,
                    "source": INJECT_SOURCE,
                }
                headers = {"X-PORCE-Token": token}
                payload = {
                    "obstacles": [
                        {
                            "source": INJECT_SOURCE,
                            "source_id": 1,
                            "type": INJECT_TYPE,
                            "confidence": INJECT_CONFIDENCE,
                            "lat": obs_lat,
                            "lon": obs_lon,
                        }
                    ]
                }
                inject_end = time.time() + INJECT_DURATION_S
                post_codes = []
                while time.time() < inject_end:
                    post_codes.append(http_post_json(f"{base_url}/api/obstacles", payload, headers))
                    time.sleep(1.0 / INJECT_HZ)
                meta["inject_meta"]["posts"] = len(post_codes)
                meta["inject_meta"]["posts_ok"] = sum(1 for c in post_codes if c == 200)

            deadline = time.time() + SCENARIO_TIMEOUT_S
            while time.time() < deadline:
                status = http_json(f"{base_url}/api/status") or {}
                meta["saw_evasion"] = bool(status.get("saw_evasion", meta["saw_evasion"]))
                if str(status.get("mission_state", "")) == "COMPLETED":
                    meta["mission_completed"] = True
                    break
                if proc.poll() is not None:
                    raise RuntimeError("brain exited mid-mission")
                time.sleep(POLL_S)
            else:
                meta["timeout"] = True
            time.sleep(2.0)
            meta["ok"] = bool(meta["mission_completed"])
    except Exception as exc:  # noqa: BLE001
        meta["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        kill_port_listeners(port)

    meta["ended_at"] = datetime.now().isoformat(timespec="seconds")
    try:
        meta["metrics"] = parse_brain_log(brain_log)
    except Exception as exc:  # noqa: BLE001
        meta["metrics"] = {"error": str(exc)}
    (run_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log(
        f"{run_name}: ok={meta['ok']} completed={meta['mission_completed']} "
        f"saw_evasion={meta['saw_evasion']} err={meta['error']} metrics={meta.get('metrics')}"
    )
    return meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--base-port", type=int, default=18090)
    parser.add_argument("--no-jitter", action="store_true")
    parser.add_argument("--scenarios", nargs="*", default=list(SCENARIOS))
    args = parser.parse_args()

    base_env = load_defaults_env()
    # These keys must not leak from defaults into the per-run env.
    for key in ("PORCE_AUDIT_ROOT", "PORCE_OBSTACLE_TOKEN", "PORCE_BRAIN_HTTP_PORT",
                "PORCE_MOCK_MAVLINK", "PORCE_FORCE_ARM", "PORCE_ENABLE_EVASION",
                "PORCE_SYSTEM_MODE"):
        base_env.pop(key, None)

    jobs = []
    for scenario in args.scenarios:
        if scenario not in SCENARIOS:
            print(f"unknown scenario: {scenario}", file=sys.stderr)
            return 2
        for run_idx in range(args.runs):
            jobs.append((scenario, run_idx))

    E2E_ROOT.mkdir(parents=True, exist_ok=True)
    campaign_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log(f"campaign start: {len(jobs)} runs, {args.workers} workers")

    results = []
    port_lock = threading.Lock()
    port_pool = list(range(args.base_port, args.base_port + args.workers))

    def worker(job):
        scenario, run_idx = job
        with port_lock:
            port = port_pool.pop(0)
        try:
            return run_one(scenario, run_idx, port, base_env, jitter=not args.no_jitter)
        finally:
            with port_lock:
                port_pool.append(port)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(worker, job) for job in jobs]
        for fut in as_completed(futures):
            results.append(fut.result())

    summary = {
        "campaign": campaign_stamp,
        "runs_per_scenario": args.runs,
        "jitter": not args.no_jitter,
        "inject_type": INJECT_TYPE,
        "inject_source": INJECT_SOURCE,
        "results": results,
        "scenario_stats": {},
    }
    for scenario in args.scenarios:
        rs = [r for r in results if r["scenario"] == scenario]
        completed = [r for r in rs if r["mission_completed"]]
        durations = [r["metrics"]["duration_s"] for r in completed if r.get("metrics", {}).get("duration_s")]
        paths = [r["metrics"]["path_length_m"] for r in completed if r.get("metrics", {}).get("path_length_m")]

        def mean_std(vals):
            if not vals:
                return None, None
            mean = sum(vals) / len(vals)
            if len(vals) < 2:
                return round(mean, 1), 0.0
            var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
            return round(mean, 1), round(math.sqrt(var), 1)

        d_mean, d_std = mean_std(durations)
        p_mean, p_std = mean_std(paths)
        summary["scenario_stats"][scenario] = {
            "runs": len(rs),
            "completed": len(completed),
            "saw_evasion": sum(1 for r in rs if r["saw_evasion"]),
            "duration_mean_s": d_mean,
            "duration_std_s": d_std,
            "path_mean_m": p_mean,
            "path_std_m": p_std,
        }

    out_path = E2E_ROOT / f"campaign_{campaign_stamp}.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log(f"campaign done -> {out_path}")
    print(json.dumps(summary["scenario_stats"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
