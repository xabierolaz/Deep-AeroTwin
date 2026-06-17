"""HUD test: mock brain + injected biker obstacle + PrintWindow probe.

Checks whether the in-game debug labels still render with showhud 0.
"""
from __future__ import annotations

import json
import math
import os
import secrets
import subprocess
import time
import urllib.request
from pathlib import Path

REPO = Path(r"D:\Deep-AeroTwin-UE57-Test")
PIPELINE = REPO / "pipeline"
VENV_PY = REPO / "venv" / "Scripts" / "python.exe"
OUT = REPO / "tmp" / "hud_test_result.json"
PORT = 8080


def load_defaults():
    env = {}
    for line in (PIPELINE / "porce_defaults.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().replace("%PROJECT_ROOT%", str(REPO))
    return env


def http_json(url, timeout=2.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def post(url, payload, headers, timeout=2.0):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except Exception:
        return -1


def main():
    token = secrets.token_hex(16)
    env = dict(os.environ)
    env.update(load_defaults())
    env.update({
        "PORCE_SYSTEM_MODE": "SIMULATION",
        "PORCE_MOCK_MAVLINK": "1",
        "PORCE_FORCE_ARM": "1",
        "PORCE_ENABLE_EVASION": "0",
        "PORCE_OBSTACLE_TOKEN": token,
        "PORCE_OBSTACLE_TOKEN_REQUIRED": "1",
        "PORCE_AUDIT_ENABLE": "0",
        "PORCE_CONFIG_BANNER": "0",
        "PORCE_BRAIN_HTTP_PORT": str(PORT),
    })
    res = {"ok": False}
    brain = None
    try:
        log_fp = open(REPO / "tmp" / "hud_test_brain.log", "w", encoding="utf-8")
        brain = subprocess.Popen([str(VENV_PY), "-u", "flight_controller.py"],
                                 cwd=str(PIPELINE), env=env, stdout=log_fp, stderr=subprocess.STDOUT)
        deadline = time.time() + 45
        while time.time() < deadline:
            if http_json(f"http://127.0.0.1:{PORT}/api/status"):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("brain not ready")
        # wait for home + telemetry
        time.sleep(8)
        ui = http_json(f"http://127.0.0.1:{PORT}/api/ui/data") or {}
        tel = ui.get("telemetry") or {}
        lat0, lon0 = float(tel.get("lat", 42.2297)), float(tel.get("lon", -1.2351))
        # obstacle 30 m north
        dlat = math.degrees(30.0 / 6371000.0)
        headers = {"X-PORCE-Token": token}
        payload = {"obstacles": [{"source": "vision", "source_id": 7, "type": "biker",
                                  "confidence": 0.95, "lat": lat0 + dlat, "lon": lon0}]}
        codes = []
        captured = False
        t_start = time.time()
        t_end = t_start + 14
        while time.time() < t_end:
            codes.append(post(f"http://127.0.0.1:{PORT}/api/obstacles", payload, headers))
            if not captured and time.time() - t_start > 7:
                captured = True
                probe = subprocess.run(
                    [str(VENV_PY), str(REPO / "tmp" / "printwindow_probe.py")],
                    capture_output=True, timeout=60,
                )
                res["probe_rc"] = probe.returncode
            time.sleep(0.33)
        res["posts_ok"] = sum(1 for c in codes if c == 200)
        ui2 = http_json(f"http://127.0.0.1:{PORT}/api/ui/data") or {}
        res["ui_obstacles"] = len(ui2.get("obstacles") or [])
        res["ok"] = True
    except Exception as exc:
        res["error"] = str(exc)
    finally:
        if brain is not None and brain.poll() is None:
            brain.terminate()
    OUT.write_text(json.dumps(res, indent=2))
    print(json.dumps(res))


if __name__ == "__main__":
    main()
