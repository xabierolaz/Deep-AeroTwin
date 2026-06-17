"""Pre-check dry run: mock brain + vision against live PIE window (~150 s).

Validates the audit pre-check: YOLO sees the UE5.7 peloton (ciclista mode)
through the real capture path with production thresholds.
"""

from __future__ import annotations

import json
import math
import os
import secrets
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(r"D:\Deep-AeroTwin-UE57-Test")
PIPELINE = REPO / "pipeline"
VENV_PY = REPO / "venv" / "Scripts" / "python.exe"
OUT_DIR = REPO / "tmp" / ("precheck_dryrun_" + datetime.now().strftime("%H%M%S"))
SUMMARY = REPO / "tmp" / "precheck_dryrun_summary.json"
RUN_S = 280.0
PORT = 8080


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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(16)
    base = load_defaults()
    for k in ("PORCE_AUDIT_ROOT", "PORCE_OBSTACLE_TOKEN"):
        base.pop(k, None)

    common = dict(os.environ)
    common.update(base)
    common.update(
        {
            "PORCE_OBSTACLE_TOKEN": token,
            "PORCE_OBSTACLE_TOKEN_REQUIRED": "1",
            "PORCE_AUDIT_ENABLE": "1",
            "PORCE_AUDIT_ROOT": str(OUT_DIR),
            "PORCE_CONFIG_BANNER": "0",
            "PORCE_BRAIN_HTTP_PORT": str(PORT),
            "PORCE_BRAIN_HTTP_HOST": "127.0.0.1",
            "PORCE_BRAIN_APP_BIND_HOST": "127.0.0.1",
        }
    )

    brain_env = dict(common)
    brain_env.update(
        {
            "PORCE_SYSTEM_MODE": "SIMULATION",
            "PORCE_MOCK_MAVLINK": "1",
            "PORCE_FORCE_ARM": "1",
            "PORCE_ENABLE_EVASION": "1",
            "PORCE_UNREAL_TELEMETRY_INGEST_ENABLE": "0",
        }
    )
    vision_env = dict(common)
    vision_env.update(
        {
            "PORCE_SYSTEM_MODE": "SIMULATION",
            "PORCE_VISION_DEBUG_WINDOW": "0",
            "PORCE_VISION_DEBUG_DOCK": "0",
            # standalone -game window (NOT the editor window)
            "PORCE_CAPTURE_WINDOW_TITLE": "AirTraffic (64-bit",
            "PORCE_CAPTURE_WINDOW_EXACT": "0",
        }
    )

    summary: dict = {"out_dir": str(OUT_DIR), "ok": False}
    brain = vision = None
    try:
        with (OUT_DIR / "brain.log").open("w", encoding="utf-8") as blog:
            brain = subprocess.Popen(
                [str(VENV_PY), "-u", "flight_controller.py"],
                cwd=str(PIPELINE), env=brain_env, stdout=blog, stderr=subprocess.STDOUT,
            )
            deadline = time.time() + 45
            while time.time() < deadline:
                if http_json(f"http://127.0.0.1:{PORT}/api/status"):
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError("brain not ready")
            summary["brain_ready"] = True

            with (OUT_DIR / "vision.log").open("w", encoding="utf-8") as vlog:
                vision = subprocess.Popen(
                    [str(VENV_PY), "-u", "vision_system.py"],
                    cwd=str(PIPELINE), env=vision_env, stdout=vlog, stderr=subprocess.STDOUT,
                )
                time.sleep(RUN_S)
    finally:
        for proc in (vision, brain):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()

    # Analyze vision events
    ev_path = OUT_DIR / "vision" / "events.jsonl"
    frames = 0
    frames_with_dets = 0
    best = []
    published_biker = 0
    max_conf = 0.0
    if ev_path.exists():
        for line in ev_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                evt = json.loads(line)
            except Exception:
                continue
            if evt.get("kind") != "vision_frame":
                continue
            frames += 1
            outgoing = evt.get("outgoing") or []
            bikers = [o for o in outgoing if str(o.get("type", "")).lower() in ("biker", "bike")]
            if outgoing:
                frames_with_dets += 1
            if bikers:
                published_biker += 1
                top = max(float(b.get("confidence", 0) or 0) for b in bikers)
                max_conf = max(max_conf, top)
                if len(best) < 5:
                    best.append({"frame": evt.get("frame"), "n_bikers": len(bikers), "top_conf": top})
    status = http_json(f"http://127.0.0.1:{PORT}/api/status") or {}
    summary.update(
        {
            "frames": frames,
            "frames_with_outgoing": frames_with_dets,
            "frames_with_biker_published": published_biker,
            "max_published_biker_conf": round(max_conf, 3),
            "sample": best,
            "ok": published_biker > 0,
        }
    )
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
