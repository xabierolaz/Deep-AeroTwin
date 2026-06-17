"""D4: REAL_TWIN spawn/update/despawn demo against the live UE viewer.

Requires the game running on a map with PorceTelemetry ENABLED (/Game/Ejea).
Phases: spawn (post 3 entities) -> update (move them) -> despawn (stop posting).
Evidence: PrintWindow captures per phase + /api/ui/data counts + UE log lines.
"""
from __future__ import annotations

import ctypes
import json
import math
import os
import secrets
import subprocess
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(r"D:\Deep-AeroTwin-UE57-Test")
PIPELINE = REPO / "pipeline"
VENV_PY = REPO / "venv" / "Scripts" / "python.exe"
OUTDIR = REPO / "tmp" / "d4_twin"
OUT = REPO / "tmp" / "d4_twin_result.json"
PORT = 8080

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


def find_hwnd():
    res = []

    def cb(h, l):
        if not user32.IsWindowVisible(h):
            return True
        n = user32.GetWindowTextLengthW(h)
        if not n:
            return True
        b = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(h, b, n + 1)
        if "airtraffic (64-bit" in (b.value or "").lower():
            res.append(h)
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return res[0] if res else None


def grab_save(hwnd, path):
    wr = wintypes.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(wr))
    cr = wintypes.RECT(); user32.GetClientRect(hwnd, ctypes.byref(cr))
    pt = wintypes.POINT(0, 0); user32.ClientToScreen(hwnd, ctypes.byref(pt))
    ww, wh = wr.right - wr.left, wr.bottom - wr.top
    cw, ch = cr.right - cr.left, cr.bottom - cr.top
    ox, oy = pt.x - wr.left, pt.y - wr.top
    hdc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, ww, wh)
    old = gdi32.SelectObject(mem, bmp)
    try:
        if not user32.PrintWindow(hwnd, mem, 2):
            return False

        class B(ctypes.Structure):
            _fields_ = [("a", wintypes.DWORD), ("w", ctypes.c_long), ("h", ctypes.c_long),
                        ("p", wintypes.WORD), ("bc", wintypes.WORD), ("c", wintypes.DWORD),
                        ("s", wintypes.DWORD), ("x", ctypes.c_long), ("y", ctypes.c_long),
                        ("u", wintypes.DWORD), ("i", wintypes.DWORD)]

        bi = B(); bi.a = ctypes.sizeof(B); bi.w = ww; bi.h = -wh; bi.p = 1; bi.bc = 32
        buf = ctypes.create_string_buffer(ww * wh * 4)
        gdi32.GetDIBits(mem, bmp, 0, wh, buf, ctypes.byref(bi), 0)
        img = np.frombuffer(buf, dtype=np.uint8).reshape(wh, ww, 4)[:, :, :3]
        Image.fromarray(img[oy:oy + ch, ox:ox + cw][:, :, ::-1]).save(path)
        return True
    finally:
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(hwnd, hdc)


def http_json(url, timeout=2.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def post(url, payload, headers):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status
    except Exception:
        return -1


def load_defaults():
    env = {}
    for line in (PIPELINE / "porce_defaults.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().replace("%PROJECT_ROOT%", str(REPO))
    return env


def entities(lat0, lon0, t):
    """3 entities; bike moves east over time t (s)."""
    d = 6371000.0
    north = lambda m: math.degrees(m / d)
    east = lambda m: math.degrees(m / (d * math.cos(math.radians(lat0))))
    bike_e = 25.0 + 2.0 * t  # 2 m/s eastwards
    return [
        {"source": "vision", "source_id": 41, "type": "biker", "confidence": 0.92,
         "lat": lat0 + north(30.0), "lon": lon0 + east(bike_e), "distance": 40.0},
        {"source": "vision", "source_id": 42, "type": "cow", "confidence": 0.88,
         "lat": lat0 + north(18.0), "lon": lon0 + east(-12.0), "distance": 25.0},
        {"source": "vision", "source_id": 43, "type": "tower", "confidence": 0.97,
         "lat": lat0 + north(45.0), "lon": lon0 + east(8.0), "distance": 50.0},
    ]


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    res = {"ok": False, "phases": {}}
    hwnd = find_hwnd()
    if not hwnd:
        res["error"] = "game window not found"
        OUT.write_text(json.dumps(res, indent=2)); print(json.dumps(res)); return

    token = secrets.token_hex(16)
    env = dict(os.environ); env.update(load_defaults())
    env.update({"PORCE_SYSTEM_MODE": "REAL_TWIN", "PORCE_MOCK_MAVLINK": "1",
                "PORCE_OBSTACLE_TOKEN": token, "PORCE_OBSTACLE_TOKEN_REQUIRED": "1",
                "PORCE_AUDIT_ENABLE": "0", "PORCE_CONFIG_BANNER": "0",
                "PORCE_BRAIN_HTTP_PORT": str(PORT)})
    brain = None
    try:
        log_fp = open(OUTDIR / "brain_twin.log", "w")
        brain = subprocess.Popen([str(VENV_PY), "-u", "flight_controller.py"], cwd=str(PIPELINE),
                                 env=env, stdout=log_fp, stderr=subprocess.STDOUT)
        deadline = time.time() + 45
        while time.time() < deadline:
            s = http_json(f"http://127.0.0.1:{PORT}/api/status")
            if s:
                res["workflow"] = s.get("workflow")
                res["control_mode"] = s.get("control_mode")
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("brain not ready")
        time.sleep(6)
        ui = http_json(f"http://127.0.0.1:{PORT}/api/ui/data") or {}
        home = ui.get("home") or {}
        lat0, lon0 = float(home.get("lat", 42.2297)), float(home.get("lon", -1.2351))
        headers = {"X-PORCE-Token": token}

        # phase 1: spawn + sustained updates (movement)
        t0 = time.time()
        while time.time() - t0 < 12:
            t = time.time() - t0
            post(f"http://127.0.0.1:{PORT}/api/obstacles", {"obstacles": entities(lat0, lon0, t)}, headers)
            time.sleep(0.4)
        ui_spawn = http_json(f"http://127.0.0.1:{PORT}/api/ui/data") or {}
        res["phases"]["spawn_update"] = {
            "ui_obstacles": len(ui_spawn.get("obstacles") or []),
            "entity_ids": [o.get("entity_id") for o in (ui_spawn.get("obstacles") or [])],
            "shot": grab_save(hwnd, OUTDIR / "d4_phase_update.png"),
        }
        # keep posting a bit to grab a second shot with moved bike
        t1 = time.time()
        while time.time() - t1 < 6:
            t = time.time() - t0
            post(f"http://127.0.0.1:{PORT}/api/obstacles", {"obstacles": entities(lat0, lon0, t)}, headers)
            time.sleep(0.4)
        grab_save(hwnd, OUTDIR / "d4_phase_update2.png")

        # phase 2: despawn (stop posting; dynamic TTL 3 s + twin DespawnAfterS 3 s)
        time.sleep(8)
        ui_desp = http_json(f"http://127.0.0.1:{PORT}/api/ui/data") or {}
        res["phases"]["despawn"] = {
            "ui_obstacles": len(ui_desp.get("obstacles") or []),
            "shot": grab_save(hwnd, OUTDIR / "d4_phase_despawn.png"),
        }
        res["ok"] = True
    except Exception as exc:
        res["error"] = str(exc)
    finally:
        if brain is not None and brain.poll() is None:
            brain.terminate()
    OUT.write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
