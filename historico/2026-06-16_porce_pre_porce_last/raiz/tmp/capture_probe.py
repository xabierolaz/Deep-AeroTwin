"""Standalone capture probe: replicate vision's window->mss path, report brightness."""
import ctypes
import json
from ctypes import wintypes

import mss
import numpy as np
from PIL import Image

user32 = ctypes.windll.user32
OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\capture_probe.json"
PNG = r"D:\Deep-AeroTwin-UE57-Test\tmp\capture_probe.png"
TARGET = "airtraffic (64-bit"

matches = []

def enum_cb(hwnd, lparam):
    if not user32.IsWindowVisible(hwnd):
        return True
    length = user32.GetWindowTextLengthW(hwnd)
    if not length:
        return True
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    if TARGET in (buf.value or "").lower():
        matches.append((hwnd, buf.value))
    return True

EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows(EnumProc(enum_cb), 0)

info = {"matches": [(h, t) for h, t in matches]}
if matches:
    hwnd = matches[0][0]
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    region = {"left": pt.x, "top": pt.y, "width": rect.right - rect.left, "height": rect.bottom - rect.top}
    info["region"] = region
    with mss.mss() as sct:
        info["monitors"] = sct.monitors
        img = np.array(sct.grab(region))
    info["mean_brightness"] = float(img[:, :, :3].mean())
    Image.fromarray(img[:, :, :3][:, :, ::-1]).save(PNG)

open(OUT, "w").write(json.dumps(info, indent=2, default=str))
print(json.dumps(info, indent=2, default=str)[:800])
