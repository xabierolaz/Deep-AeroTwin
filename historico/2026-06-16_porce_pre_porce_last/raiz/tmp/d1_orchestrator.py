"""D1 orchestrator: real SITL (WSL) + brain + vision + viz against the live UE game window.

Functionally equivalent to tools/launch_workflow.bat SIMULATION (same components,
same defaults env), but with file-captured logs and deterministic supervision.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(r"D:\Deep-AeroTwin-UE57-Test")
PIPELINE = REPO / "pipeline"
VENV_PY = REPO / "venv" / "Scripts" / "python.exe"
WSL = r"C:\Windows\System32\wsl.exe"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
AUDIT_ROOT = PIPELINE / "logs" / "zero_trust" / STAMP
SUMMARY = REPO / "tmp" / "d1_summary.json"
PORT = 8080
MISSION_TIMEOUT_S = 900.0


def load_defaults() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (PIPELINE / "porce_defaults.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().replace("%PROJECT_ROOT%", str(REPO))
    return env


def http_json(url: str, timeout: float = 2.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def port_open(port: int) -> bool:
    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def main() -> None:
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    (PIPELINE / "logs" / "zero_trust" / "LATEST_RUN.txt").write_text(str(AUDIT_ROOT), encoding="utf-8")
    token = secrets.token_hex(16)

    base = load_defaults()
    base.pop("PORCE_OBSTACLE_TOKEN", None)
    base["PORCE_AUDIT_ROOT"] = str(AUDIT_ROOT)

    common = dict(os.environ)
    common["PATH"] = r"C:\Windows\System32;C:\Windows;" + common.get("PATH", "")
    common["PATHEXT"] = ".COM;.EXE;.BAT;.CMD"
    common.update(base)
    common.update(
        {
            "PORCE_SYSTEM_MODE": "SIMULATION",
            "PORCE_MOCK_MAVLINK": "0",
            "PORCE_OBSTACLE_TOKEN": token,
            "PORCE_OBSTACLE_TOKEN_REQUIRED": "1",
            "PORCE_UNREAL_TELEMETRY_TOKEN": token,
            "PORCE_AUDIT_ENABLE": "1",
            "PORCE_CONFIG_BANNER": "1",
            "PORCE_BRAIN_HTTP_PORT": str(PORT),
            "PORCE_SITL_ALLOW_HOME_FALLBACK": "0",
        }
    )

    vision_env = dict(common)
    vision_env.update(
        {
            "PORCE_VISION_DEBUG_WINDOW": "0",
            "PORCE_VISION_DEBUG_DOCK": "0",
            "PORCE_CAPTURE_WINDOW_TITLE": "AirTraffic (64-bit",
            "PORCE_CAPTURE_WINDOW_EXACT": "0",
            "PORCE_CAPTURE_WINDOW_METHOD": "printwindow",
            "PORCE_CAPTURE_WINDOW_TOPMOST": "0",
            "PORCE_CAPTURE_WINDOW_FOCUS": "0",
            "PORCE_AUDIT_VISION_FRAME_EVERY_N": "2",
        }
    )

    summary: dict = {"audit_root": str(AUDIT_ROOT), "stamp": STAMP, "ok": False, "stages": {}}
    procs: dict[str, subprocess.Popen] = {}
    logs = {}

    def start(name: str, args: list[str], env: dict, cwd: Path = PIPELINE):
        log_fp = (AUDIT_ROOT / f"{name}.log").open("w", encoding="utf-8")
        logs[name] = log_fp
        procs[name] = subprocess.Popen(args, cwd=str(cwd), env=env, stdout=log_fp, stderr=subprocess.STDOUT)

    SITL_PORT = 5790  # 5760 is squatted by a local service (svchost) that accepts and drops
    common["PORCE_SITL_TCP_PORT"] = str(SITL_PORT)
    vision_env["PORCE_SITL_TCP_PORT"] = str(SITL_PORT)

    try:
        # 1. SITL in WSL
        start(
            "sitl",
            [WSL, "-e", "sh", "-lc",
             f"cd /mnt/d/Deep-AeroTwin-UE57-Test/pipeline && SITL_SERIAL0=tcp:{SITL_PORT} bash run_sitl.sh"],
            common,
        )
        deadline = time.time() + 120
        while time.time() < deadline:
            if port_open(SITL_PORT):
                break
            if procs["sitl"].poll() is not None:
                raise RuntimeError("SITL exited early")
            time.sleep(1)
        else:
            raise RuntimeError(f"SITL port {SITL_PORT} not open")
        summary["stages"]["sitl_ready"] = True
        time.sleep(3)

        # 2. Brain
        start("brain", [str(VENV_PY), "-u", "flight_controller.py"], common)
        deadline = time.time() + 60
        while time.time() < deadline:
            if http_json(f"http://127.0.0.1:{PORT}/api/status"):
                break
            if procs["brain"].poll() is not None:
                raise RuntimeError("brain exited early")
            time.sleep(1)
        else:
            raise RuntimeError("brain HTTP not ready")
        summary["stages"]["brain_ready"] = True

        # 3. Vision + viz recorder
        start("vision", [str(VENV_PY), "-u", "vision_system.py"], vision_env)
        start("viz", [str(VENV_PY), "-u", "viz_recorder.py"], common)
        summary["stages"]["vision_viz_started"] = True

        # 3b. Anti-black sanity check on the first archived frames.
        time.sleep(20)
        frames_dir = AUDIT_ROOT / "vision" / "frames"
        try:
            from PIL import Image  # type: ignore
            import numpy as np  # type: ignore

            latest = sorted(frames_dir.glob("*.jpg"))[-1] if frames_dir.exists() else None
            if latest is not None:
                brightness = float(np.asarray(Image.open(latest).convert("L")).mean())
                summary["stages"]["first_frame_brightness"] = round(brightness, 1)
                if brightness < 3.0:
                    raise RuntimeError("capture is black — aborting early")
            else:
                summary["stages"]["first_frame_brightness"] = None
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001
            summary["stages"]["brightness_check_error"] = str(exc)

        # 4. Supervise mission
        t0 = time.time()
        last = {}
        while time.time() - t0 < MISSION_TIMEOUT_S:
            status = http_json(f"http://127.0.0.1:{PORT}/api/status") or {}
            last = status
            if str(status.get("mission_state")) == "COMPLETED":
                summary["stages"]["mission_completed"] = True
                break
            if str(status.get("mission_state")) == "FAILED":
                summary["stages"]["mission_failed"] = True
                break
            for name in ("sitl", "brain", "vision"):
                if procs[name].poll() is not None:
                    raise RuntimeError(f"{name} died mid-run")
            time.sleep(2)
        summary["last_status"] = {
            k: last.get(k)
            for k in ("mode", "armed", "wp_idx", "mission_state", "saw_evasion", "obstacles_count", "evasion")
        }
        time.sleep(3)
        summary["ok"] = bool(summary["stages"].get("mission_completed"))
    except Exception as exc:  # noqa: BLE001
        summary["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        for name, proc in procs.items():
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        for fp in logs.values():
            try:
                fp.close()
            except Exception:
                pass
        # ensure SITL is gone
        subprocess.run([WSL, "-e", "sh", "-lc", "pkill -f arducopter || true"], capture_output=True, timeout=30)

    # quick post-analysis
    try:
        ev_path = AUDIT_ROOT / "brain" / "events.jsonl"
        routes = []
        if ev_path.exists():
            for line in ev_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                try:
                    evt = json.loads(line)
                except Exception:
                    continue
                if evt.get("kind") == "evasion_route_generated":
                    routes.append(
                        {
                            "ts": evt["ts"],
                            "nearest_m": evt.get("nearest_distance_m"),
                            "type": evt.get("nearest_type"),
                            "obs_ids": evt.get("planner_obs_ids"),
                            "route_points": evt.get("route_points"),
                        }
                    )
        summary["evasion_routes"] = routes[:10]
        summary["evasion_route_count"] = len(routes)
        frames_dir = AUDIT_ROOT / "vision" / "frames"
        summary["vision_frames_archived"] = len(list(frames_dir.glob("*.jpg"))) if frames_dir.exists() else 0
    except Exception as exc:  # noqa: BLE001
        summary["post_error"] = str(exc)

    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
