"""A/B HUD test: inject obstacle on the mission bearing, sample PrintWindow frames,
quantify green-label pixels. Run with the game already launched (A: showhud 0, B: normal)."""
from __future__ import annotations

import ctypes
import json
import math
import os
import secrets
import subprocess
import sys
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(r"D:\Deep-AeroTwin-UE57-Test")
PIPELINE = REPO / "pipeline"
VENV_PY = REPO / "venv" / "Scripts" / "python.exe"
TAG = sys.argv[1] if len(sys.argv) > 1 else "A"
OUT = REPO / "tmp" / f"hud_ab_{TAG}.json"
PORT = 8080

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
PW = 0x2


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


def grab(hwnd):
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
        if not user32.PrintWindow(hwnd, mem, PW):
            return None

        class B(ctypes.Structure):
            _fields_ = [("a", wintypes.DWORD), ("w", ctypes.c_long), ("h", ctypes.c_long),
                        ("p", wintypes.WORD), ("bc", wintypes.WORD), ("c", wintypes.DWORD),
                        ("s", wintypes.DWORD), ("x", ctypes.c_long), ("y", ctypes.c_long),
                        ("u", wintypes.DWORD), ("i", wintypes.DWORD)]

        bi = B(); bi.a = ctypes.sizeof(B); bi.w = ww; bi.h = -wh; bi.p = 1; bi.bc = 32; bi.c = 0
        buf = ctypes.create_string_buffer(ww * wh * 4)
        gdi32.GetDIBits(mem, bmp, 0, wh, buf, ctypes.byref(bi), 0)
        img = np.frombuffer(buf, dtype=np.uint8).reshape(wh, ww, 4)[:, :, :3]
        return img[oy:oy + ch, ox:ox + cw].copy()
    finally:
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(hwnd, hdc)


def green_metric(img_bgr):
    b = img_bgr[:, :, 0].astype(int)
    g = img_bgr[:, :, 1].astype(int)
    r = img_bgr[:, :, 2].astype(int)
    mask = (g > 180) & (r < 120) & (b < 120)
    return int(mask.sum())


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


def main():
    res = {"tag": TAG, "ok": False}
    hwnd = find_hwnd()
    if not hwnd:
        res["error"] = "game window not found"
        OUT.write_text(json.dumps(res, indent=2)); print(json.dumps(res)); return

    token = secrets.token_hex(16)
    env = dict(os.environ); env.update(load_defaults())
    env.update({"PORCE_SYSTEM_MODE": "SIMULATION", "PORCE_MOCK_MAVLINK": "1", "PORCE_FORCE_ARM": "1",
                "PORCE_ENABLE_EVASION": "0", "PORCE_OBSTACLE_TOKEN": token,
                "PORCE_OBSTACLE_TOKEN_REQUIRED": "1", "PORCE_AUDIT_ENABLE": "0",
                "PORCE_CONFIG_BANNER": "0", "PORCE_BRAIN_HTTP_PORT": str(PORT)})
    brain = None
    try:
        log_fp = open(REPO / "tmp" / f"hud_ab_{TAG}_brain.log", "w")
        brain = subprocess.Popen([str(VENV_PY), "-u", "flight_controller.py"], cwd=str(PIPELINE),
                                 env=env, stdout=log_fp, stderr=subprocess.STDOUT)
        deadline = time.time() + 45
        while time.time() < deadline:
            if http_json(f"http://127.0.0.1:{PORT}/api/status"):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("brain not ready")
        time.sleep(6)
        ui = http_json(f"http://127.0.0.1:{PORT}/api/ui/data") or {}
        tel = ui.get("telemetry") or {}
        wps = ui.get("waypoints") or []
        lat0, lon0 = float(tel.get("lat")), float(tel.get("lon"))
        tgt = wps[1] if len(wps) > 1 else {"lat": lat0 - 0.001, "lon": lon0 + 0.001}
        north = math.radians(float(tgt["lat"]) - lat0) * 6371000.0
        east = math.radians(float(tgt["lon"]) - lon0) * 6371000.0 * math.cos(math.radians(lat0))
        norm = math.hypot(north, east) or 1.0
        dist = 45.0
        olat = lat0 + math.degrees(dist * north / norm / 6371000.0)
        olon = lon0 + math.degrees(dist * east / norm / (6371000.0 * math.cos(math.radians(lat0))))
        headers = {"X-PORCE-Token": token}
        payload = {"obstacles": [{"source": "vision", "source_id": 7, "type": "biker",
                                  "confidence": 0.95, "lat": olat, "lon": olon,
                                  "distance": 45.0,
                                  "bbox": {"x1": 290.0, "y1": 300.0, "x2": 350.0, "y2": 380.0}}]}
        metrics = []
        best = None
        t_end = time.time() + 40
        i = 0
        while time.time() < t_end:
            post(f"http://127.0.0.1:{PORT}/api/obstacles", payload, headers)
            if i % 4 == 0:
                img = grab(hwnd)
                if img is not None:
                    m = green_metric(img)
                    metrics.append(m)
                    if best is None or m > best[0]:
                        best = (m, img.copy())
            i += 1
            time.sleep(0.3)
        res["green_pixels"] = metrics
        res["green_max"] = max(metrics) if metrics else None
        if best is not None:
            Image.fromarray(best[1][:, :, ::-1]).save(REPO / "tmp" / f"hud_ab_{TAG}_worst.png")
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
