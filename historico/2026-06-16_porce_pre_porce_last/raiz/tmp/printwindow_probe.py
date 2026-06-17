"""Probe: capture the UE game window via PrintWindow(PW_RENDERFULLCONTENT).

Validates that we get real window content (not screen region), even if occluded.
"""
import ctypes
import json
from ctypes import wintypes

import numpy as np
from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\printwindow_probe.json"
PNG = r"D:\Deep-AeroTwin-UE57-Test\tmp\printwindow_probe.png"
TARGET = "airtraffic (64-bit"
PW_RENDERFULLCONTENT = 0x00000002

matches = []

def enum_cb(hwnd, lparam):
    if not user32.IsWindowVisible(hwnd):
        return True
    n = user32.GetWindowTextLengthW(hwnd)
    if not n:
        return True
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    if TARGET in (buf.value or "").lower():
        matches.append((hwnd, buf.value))
    return True

EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows(EnumProc(enum_cb), 0)

info = {"matches": [(h, t) for h, t in matches]}
if matches:
    hwnd = matches[0][0]

    # window rect (full, incl. frame) — PrintWindow renders the whole window
    wrect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(wrect))
    ww, wh = wrect.right - wrect.left, wrect.bottom - wrect.top

    crect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(crect))
    cw, ch = crect.right - crect.left, crect.bottom - crect.top
    # client origin offset inside window
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    off_x, off_y = pt.x - wrect.left, pt.y - wrect.top
    info["window"] = {"w": ww, "h": wh}
    info["client"] = {"w": cw, "h": ch, "off_x": off_x, "off_y": off_y}

    hdc_win = user32.GetWindowDC(hwnd)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_win, ww, wh)
    gdi32.SelectObject(hdc_mem, hbmp)
    ok = user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)
    info["printwindow_ok"] = bool(ok)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
            ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
            ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
        ]

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = ww
    bmi.biHeight = -wh  # top-down
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0

    buf = ctypes.create_string_buffer(ww * wh * 4)
    DIB_RGB_COLORS = 0
    got = gdi32.GetDIBits(hdc_mem, hbmp, 0, wh, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
    info["getdibits_lines"] = got

    img = np.frombuffer(buf, dtype=np.uint8).reshape(wh, ww, 4)[:, :, :3]  # BGR
    client = img[off_y:off_y + ch, off_x:off_x + cw]
    info["client_mean_brightness"] = float(client.mean())
    Image.fromarray(client[:, :, ::-1]).save(PNG)

    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(hwnd, hdc_win)

open(OUT, "w").write(json.dumps(info, indent=2, default=str))
print(json.dumps(info, indent=2, default=str)[:600])
