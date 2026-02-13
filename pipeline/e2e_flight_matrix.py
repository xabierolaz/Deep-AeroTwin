from __future__ import annotations

import argparse
import math
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def log(msg: str) -> None:
    print(f"[{_ts()}] [E2E] {msg}", flush=True)


@dataclass(frozen=True)
class Scenario:
    name: str
    porce_enable: int
    inject: bool
    expect_saw_evasion: bool


SCENARIOS: dict[str, Scenario] = {
    "porce_off_no_detections": Scenario(
        name="porce_off_no_detections",
        porce_enable=0,
        inject=False,
        expect_saw_evasion=False,
    ),
    "porce_on_no_detections": Scenario(
        name="porce_on_no_detections",
        porce_enable=1,
        inject=False,
        expect_saw_evasion=False,
    ),
    "porce_off_with_detections": Scenario(
        name="porce_off_with_detections",
        porce_enable=0,
        inject=True,
        expect_saw_evasion=False,
    ),
    "porce_on_with_detections": Scenario(
        name="porce_on_with_detections",
        porce_enable=1,
        inject=True,
        expect_saw_evasion=True,
    ),
}


REPO_ROOT = Path(__file__).resolve().parents[1]


def _popen(
    args: list[str],
    *,
    env: Optional[dict[str, str]] = None,
    cwd: Optional[Path] = None,
    stdout_path: Optional[Path] = None,
) -> subprocess.Popen:
    stdout_handle = None
    if stdout_path is not None:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_handle = stdout_path.open("w", encoding="utf-8")

    # New process group so we can terminate child processes on timeout.
    return subprocess.Popen(
        args,
        env=env,
        cwd=str(cwd or REPO_ROOT),
        stdout=stdout_handle or subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=(stdout_handle is None),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
    )


def _kill_proc(proc: subprocess.Popen, name: str) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            if hasattr(os, "killpg"):
                os.killpg(proc.pid, signal.SIGTERM)
            else:
                proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _wslpath(win_path: Path) -> str:
    # `wsl wslpath -u` can mis-handle backslashes; pass a D:/... style path.
    win_arg = str(win_path).replace("\\", "/")
    out = subprocess.check_output(
        ["wsl", "wslpath", "-u", win_arg],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()
    if not out:
        raise RuntimeError(f"wslpath_empty:{win_path}")
    return out


def _wait_http_ok(url: str, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    last_err: str = ""
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200:
                return
            last_err = f"status={r.status_code}"
        except Exception as e:
            last_err = str(e)
        time.sleep(0.5)
    raise TimeoutError(f"http_not_ready:{url}:{last_err}")


def _get_status(base_url: str) -> dict:
    r = requests.get(f"{base_url}/api/status", timeout=2)
    r.raise_for_status()
    return r.json()


def _get_telemetry(base_url: str) -> dict:
    r = requests.get(f"{base_url}/api/state/latest", timeout=2)
    r.raise_for_status()
    return r.json()


def _inject_obstacles(base_url: str, token: str, *, duration_s: float = 15.0, hz: float = 3.0) -> dict[str, int | Optional[int]]:
    # Keep posting the same obstacle so it stays fresh (expiry-based store in the Brain).
    headers = {}
    if token:
        headers["X-PORCE-Token"] = token

    posts_unauthorized = 0
    last_status: Optional[int] = None

    # Place an obstacle close to the vehicle so Brain-computed distance (from lat/lon) is deterministic.
    target_dist_m = 35.0  # must be < REACTION_DISTANCE_M (45m in SIM) to trigger evasion
    obs_lat = 42.229300
    obs_lon = -1.234700

    try:
        tel = _get_telemetry(base_url)
        lat0 = float(tel.get("lat", 0.0) or 0.0)
        lon0 = float(tel.get("lon", 0.0) or 0.0)
        yaw_deg = float(tel.get("yaw", tel.get("heading", 0.0)) or 0.0)
        if abs(lat0) > 0.0001 or abs(lon0) > 0.0001:
            br = math.radians(yaw_deg)
            north_m = math.cos(br) * target_dist_m
            east_m = math.sin(br) * target_dist_m
            R = 6371000.0
            dlat = north_m / R
            denom = R * (math.cos(math.radians(lat0)) or 1e-6)
            dlon = east_m / denom
            obs_lat = lat0 + math.degrees(dlat)
            obs_lon = lon0 + math.degrees(dlon)
    except Exception:
        pass

    obstacle = {
        "id": 1,
        "lat": obs_lat,
        "lon": obs_lon,
        "distance": target_dist_m,
        "type": "injector_tower",
        "confidence": 0.99,
        "source": "injector",
        "bbox": None,
    }

    interval = 1.0 / max(0.1, float(hz))
    end = time.time() + float(duration_s)

    while time.time() < end:
        try:
            r = requests.post(f"{base_url}/api/obstacles", json={"obstacles": [obstacle]}, headers=headers, timeout=2)
            last_status = r.status_code
            if r.status_code == 401:
                posts_unauthorized += 1
        except Exception:
            pass
        time.sleep(interval)

    return {"inject_posts_unauthorized": posts_unauthorized, "inject_last_http_status": last_status}


def run_scenario(s: Scenario, args: argparse.Namespace) -> int:
    log(f"=== Running scenario: {s.name} ===")

    run_dir = REPO_ROOT / "pipeline" / "logs" / "e2e" / f"{s.name}_{time.strftime('%Y%m%d_%H%M%S')}"
    sitl_log = run_dir / "sitl.log"
    brain_log = run_dir / "brain.log"

    # Start SITL in WSL.
    wsl_script = _wslpath(REPO_ROOT / "pipeline" / "run_sitl.sh")
    sitl = _popen(["wsl", "-e", "bash", wsl_script], stdout_path=sitl_log)
    log(f"[{s.name}] SITL started via WSL (pid={sitl.pid}).")

    # Start Brain (Windows python). Assumes user runs inside a venv with pipeline deps installed.
    brain_env = os.environ.copy()
    brain_env["PORCE_SYSTEM_MODE"] = "SIMULATION"
    brain_env["PORCE_ENABLE_EVASION"] = str(int(s.porce_enable))
    if bool(getattr(args, "force_arm", False)):
        brain_env["PORCE_FORCE_ARM"] = "1"
    # Important: run with cwd=pipeline so relative assets (e.g. `ejea_default.waypoints`) resolve.
    brain = _popen(
        [sys.executable, "-u", "flight_controller.py"],
        env=brain_env,
        cwd=REPO_ROOT / "pipeline",
        stdout_path=brain_log,
    )
    log(f"[{s.name}] Brain started (PORCE_ENABLE_EVASION={s.porce_enable}).")

    base_url = f"http://127.0.0.1:{args.http_port}"
    token = os.environ.get("PORCE_OBSTACLE_TOKEN", "").strip()

    try:
        _wait_http_ok(f"{base_url}/health", timeout_s=45.0)
        log(f"[{s.name}] Brain HTTP ready.")

        # Wait until telemetry is active and we are armed.
        deadline = time.time() + float(args.arm_timeout)
        st = {}
        while time.time() < deadline:
            st = _get_status(base_url)
            if st.get("telemetry_active") and st.get("armed"):
                break
            time.sleep(0.5)
        if not st.get("telemetry_active"):
            raise TimeoutError("telemetry_inactive_timeout")
        if not st.get("armed"):
            raise TimeoutError("armed_timeout")
        log(f"[{s.name}] telemetry_active=true armed=true mode={st.get('mode')} wp_idx={st.get('wp_idx')}")

        # Fast-fail: confirm we actually take off (WP1 -> WP2 transition) before waiting full scenario timeout.
        takeoff_timeout = float(getattr(args, "takeoff_timeout", 90.0))
        deadline = time.time() + takeoff_timeout
        while time.time() < deadline:
            st = _get_status(base_url)
            if int(st.get("wp_idx") or 0) >= 2:
                break
            time.sleep(1.0)
        if int(st.get("wp_idx") or 0) < 2:
            raise TimeoutError(f"takeoff_timeout_wp_idx={st.get('wp_idx')} mode={st.get('mode')}")

        inject_metrics = {"inject_posts_unauthorized": 0, "inject_last_http_status": None}
        if s.inject:
            log(f"[{s.name}] Obstacle injector started (token_enabled={bool(token)}).")
            inject_metrics = _inject_obstacles(base_url, token, duration_s=15.0, hz=3.0)
            log(f"[{s.name}] Obstacle injector finished ({inject_metrics}).")

        # Wait for completion.
        deadline = time.time() + float(args.scenario_timeout)
        final = None
        while time.time() < deadline:
            final = _get_status(base_url)
            if final.get("mission_state") in ("COMPLETED", "FAILED"):
                break
            time.sleep(1.0)

        if not final:
            raise TimeoutError("no_status")
        if final.get("mission_state") != "COMPLETED":
            raise RuntimeError(f"mission_failed:{final.get('last_error')}")

        saw = bool(final.get("saw_evasion"))
        if saw != bool(s.expect_saw_evasion):
            raise AssertionError(f"saw_evasion_expected={s.expect_saw_evasion} got={saw}")

        # If token is configured, we require 0 unauthorized posts.
        if token:
            if int(final.get("inject_posts_unauthorized") or 0) != 0:
                raise AssertionError(f"brain_inject_posts_unauthorized={final.get('inject_posts_unauthorized')}")
            if int(inject_metrics.get("inject_posts_unauthorized") or 0) != 0:
                raise AssertionError(f"inject_posts_unauthorized={inject_metrics.get('inject_posts_unauthorized')}")

        log(f"[{s.name}] PASS (saw_evasion={saw})")
        return 0

    except Exception as e:
        log(f"[{s.name}] FAIL: {e}")
        return 1

    finally:
        _kill_proc(brain, "brain")
        _kill_proc(sitl, "sitl")
        # Extra safety cleanup (avoid orphan SITL processes).
        try:
            subprocess.run(["wsl", "-e", "pkill", "-9", "-f", "arducopter"], timeout=10, check=False)
        except Exception:
            pass


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="E2E scenario runner for Pipeline A (upstream-based)")
    p.add_argument("--scenario", required=True, choices=sorted(SCENARIOS.keys()))
    p.add_argument("--scenario-timeout", dest="scenario_timeout", type=float, default=420.0)
    p.add_argument("--arm-timeout", dest="arm_timeout", type=float, default=150.0)
    p.add_argument("--takeoff-timeout", dest="takeoff_timeout", type=float, default=90.0)
    p.add_argument("--http-port", type=int, default=8080)
    p.add_argument("--force-arm", dest="force_arm", action="store_true", help="Use PORCE_FORCE_ARM for Brain (SIM debug only).")
    p.add_argument("--skip-vision", action="store_true")  # reserved for future use
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    s = SCENARIOS[args.scenario]
    return run_scenario(s, args)


if __name__ == "__main__":
    raise SystemExit(main())
