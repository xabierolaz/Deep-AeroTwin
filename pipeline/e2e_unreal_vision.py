from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from e2e_common import (
    get_status as _get_status,
    kill_proc as _kill_proc,
    popen as _popen,
    wait_http_ok as _wait_http_ok,
    wslpath as _wslpath,
)


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def log(msg: str) -> None:
    print(f"[{_ts()}] [E2E-UNREAL] {msg}", flush=True)


@dataclass(frozen=True)
class Scenario:
    name: str
    porce_enable: int
    vision_send: bool
    require_vision_posts: bool
    expect_saw_evasion: Optional[bool]


SCENARIOS: dict[str, Scenario] = {
    # Vision runs, but is configured to never emit obstacles (filters block everything).
    "porce_off_no_detections": Scenario(
        name="porce_off_no_detections",
        porce_enable=0,
        vision_send=False,
        require_vision_posts=False,
        expect_saw_evasion=False,
    ),
    "porce_on_no_detections": Scenario(
        name="porce_on_no_detections",
        porce_enable=1,
        vision_send=False,
        require_vision_posts=False,
        expect_saw_evasion=False,
    ),
    # Vision runs normally (YOLO + projection + POST /api/obstacles).
    "porce_off_with_detections": Scenario(
        name="porce_off_with_detections",
        porce_enable=0,
        vision_send=True,
        require_vision_posts=True,
        expect_saw_evasion=False,
    ),
    "porce_on_with_detections": Scenario(
        name="porce_on_with_detections",
        porce_enable=1,
        vision_send=True,
        require_vision_posts=True,
        # With real detections this can vary by scene/route; do not hard-assert.
        expect_saw_evasion=None,
    ),
}


REPO_ROOT = Path(__file__).resolve().parents[1]


def _file_contains_any(path: Path, needles: list[str]) -> bool:
    try:
        if not path.exists():
            return False
        data = path.read_text(encoding="utf-8", errors="ignore")
        return any(n in data for n in needles)
    except Exception:
        return False


def _wait_for_vision_window_acquired(
    vision_log: Path,
    timeout_s: float,
    *,
    window_title: str,
    window_class: str,
) -> None:
    deadline = time.time() + timeout_s
    needles = ["[CAPTURE] Window ready", "[CAPTURE] Window acquired"]
    while time.time() < deadline:
        if _file_contains_any(vision_log, needles):
            return
        time.sleep(0.5)
    raise TimeoutError(
        "vision_window_not_acquired: expected Unreal PIE window visible "
        f"(title contains {window_title!r}, class={window_class!r}). "
        "Tip: run `python tools/list_windows.py` and set PORCE_CAPTURE_WINDOW_TITLE accordingly."
    )


def run_scenario(s: Scenario, args: argparse.Namespace) -> int:
    log(f"=== Running scenario: {s.name} ===")

    run_dir = REPO_ROOT / "pipeline" / "logs" / "e2e_unreal" / f"{s.name}_{time.strftime('%Y%m%d_%H%M%S')}"
    sitl_log = run_dir / "sitl.log"
    brain_log = run_dir / "brain.log"
    vision_log = run_dir / "vision.log"

    sitl: Optional[subprocess.Popen] = None
    if not bool(getattr(args, "mock_sitl", False)):
        wsl_script = _wslpath(REPO_ROOT / "pipeline" / "run_sitl.sh")
        sitl = _popen(["wsl", "-e", "bash", wsl_script], stdout_path=sitl_log)
        log(f"[{s.name}] SITL started via WSL (pid={sitl.pid}).")
    else:
        log(f"[{s.name}] MOCK SITL enabled (PORCE_MOCK_MAVLINK=1). Not starting WSL SITL.")

    base_url = f"http://127.0.0.1:{args.http_port}"

    brain_env = os.environ.copy()
    brain_env["PORCE_SYSTEM_MODE"] = "SIMULATION"
    brain_env["PORCE_ENABLE_EVASION"] = str(int(s.porce_enable))
    if bool(getattr(args, "mock_sitl", False)):
        brain_env["PORCE_MOCK_MAVLINK"] = "1"
    if bool(getattr(args, "force_arm", False)):
        brain_env["PORCE_FORCE_ARM"] = "1"

    brain = _popen(
        [sys.executable, "-u", "flight_controller.py"],
        env=brain_env,
        cwd=REPO_ROOT / "pipeline",
        stdout_path=brain_log,
    )
    log(f"[{s.name}] Brain started (PORCE_ENABLE_EVASION={s.porce_enable}).")

    vision_env = os.environ.copy()
    vision_env["PORCE_SYSTEM_MODE"] = "SIMULATION"
    vision_env["PORCE_CAPTURE_WINDOW_TITLE"] = args.window_title
    if args.window_class:
        vision_env["PORCE_CAPTURE_WINDOW_CLASS"] = args.window_class
    vision_env["PORCE_CAPTURE_EXPECT_WIDTH"] = str(int(args.expect_w))
    vision_env["PORCE_CAPTURE_EXPECT_HEIGHT"] = str(int(args.expect_h))
    vision_env["PORCE_VISION_DEBUG_WINDOW"] = "1" if args.debug_window else "0"
    vision_env["PORCE_VISION_DEBUG_DOCK"] = "1" if args.debug_dock else "0"

    # In "no detections" scenarios, keep Vision running but block outgoing obstacles.
    if not s.vision_send:
        vision_env["PORCE_VISION_MIN_BOX_HEIGHT_PX"] = "99999"
        vision_env["PORCE_VISION_MIN_BOX_AREA_FRAC"] = "1.0"

    vision = _popen(
        [sys.executable, "-u", "vision_system.py"],
        env=vision_env,
        cwd=REPO_ROOT / "pipeline",
        stdout_path=vision_log,
    )
    log(f"[{s.name}] Vision started (send_enabled={int(s.vision_send)} pid={vision.pid}).")

    try:
        _wait_http_ok(f"{base_url}/health", timeout_s=45.0)
        log(f"[{s.name}] Brain HTTP ready.")

        # Ensure Unreal window is actually acquired for capture.
        _wait_for_vision_window_acquired(
            vision_log,
            timeout_s=float(args.vision_window_timeout),
            window_title=str(args.window_title),
            window_class=str(args.window_class),
        )
        log(f"[{s.name}] Vision capture window acquired.")

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

        # Confirm takeoff/mission progress.
        takeoff_timeout = float(getattr(args, "takeoff_timeout", 90.0))
        deadline = time.time() + takeoff_timeout
        while time.time() < deadline:
            st = _get_status(base_url)
            if int(st.get("wp_idx") or 0) >= 2:
                break
            time.sleep(1.0)
        if int(st.get("wp_idx") or 0) < 2:
            raise TimeoutError(f"takeoff_timeout_wp_idx={st.get('wp_idx')} mode={st.get('mode')}")

        # If we expect real detections, require at least one Vision obstacle POST to the Brain.
        if s.require_vision_posts:
            start_posts = int((_get_status(base_url).get("inject_posts_total") or 0))
            deadline = time.time() + float(args.detections_timeout)
            while time.time() < deadline:
                st = _get_status(base_url)
                posts = int(st.get("inject_posts_total") or 0)
                if posts > start_posts:
                    break
                time.sleep(0.5)
            posts = int((_get_status(base_url).get("inject_posts_total") or 0))
            if posts <= start_posts:
                raise TimeoutError("no_vision_obstacle_posts_detected")
            log(f"[{s.name}] Vision obstacle posts observed (inject_posts_total={posts}).")

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
        if s.expect_saw_evasion is not None and saw != bool(s.expect_saw_evasion):
            raise AssertionError(f"saw_evasion_expected={s.expect_saw_evasion} got={saw}")

        # If a token is configured, we require 0 unauthorized posts.
        if final.get("token_enabled"):
            if int(final.get("inject_posts_unauthorized") or 0) != 0:
                raise AssertionError(f"brain_inject_posts_unauthorized={final.get('inject_posts_unauthorized')}")

        log(f"[{s.name}] PASS (saw_evasion={saw})")
        log(f"[{s.name}] Logs: {run_dir}")
        return 0

    except Exception as e:
        log(f"[{s.name}] FAIL: {e}")
        log(f"[{s.name}] Logs: {run_dir}")
        return 1

    finally:
        _kill_proc(vision, "vision")
        _kill_proc(brain, "brain")
        if sitl is not None:
            _kill_proc(sitl, "sitl")
        if not bool(getattr(args, "mock_sitl", False)):
            try:
                subprocess.run(["wsl", "-e", "pkill", "-9", "-f", "arducopter"], timeout=10, check=False)
            except Exception:
                pass


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="E2E runner for Pipeline A with Unreal window capture + Vision (YOLO).")
    p.add_argument("--scenario", required=True, choices=sorted(SCENARIOS.keys()))
    p.add_argument("--scenario-timeout", dest="scenario_timeout", type=float, default=420.0)
    p.add_argument("--arm-timeout", dest="arm_timeout", type=float, default=240.0)
    p.add_argument("--takeoff-timeout", dest="takeoff_timeout", type=float, default=180.0)
    p.add_argument("--http-port", type=int, default=8080)
    p.add_argument("--force-arm", dest="force_arm", action="store_true", help="Use PORCE_FORCE_ARM for Brain (SIM debug only).")
    p.add_argument(
        "--mock-sitl",
        dest="mock_sitl",
        action="store_true",
        help="Run without WSL/SITL by enabling PORCE_MOCK_MAVLINK in the Brain.",
    )

    p.add_argument("--window-title", dest="window_title", default="AirTraffic Preview")
    p.add_argument("--window-class", dest="window_class", default="UnrealWindow")
    p.add_argument("--expect-width", dest="expect_w", type=int, default=640)
    p.add_argument("--expect-height", dest="expect_h", type=int, default=640)
    p.add_argument("--debug-window", dest="debug_window", action="store_true", default=False)
    p.add_argument("--debug-dock", dest="debug_dock", action="store_true", default=False)

    p.add_argument("--vision-window-timeout", dest="vision_window_timeout", type=float, default=60.0)
    p.add_argument("--detections-timeout", dest="detections_timeout", type=float, default=180.0)
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    s = SCENARIOS[args.scenario]
    return run_scenario(s, args)


if __name__ == "__main__":
    raise SystemExit(main())
