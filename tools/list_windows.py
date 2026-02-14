#!/usr/bin/env python3
"""
List visible top-level windows on Windows (title + class).

This helps configure `PORCE_CAPTURE_WINDOW_TITLE` for Pipeline A window capture.
"""

from __future__ import annotations

import os
import sys
import ctypes
from ctypes import wintypes


def main() -> int:
    if os.name != "nt":
        print("[error] Windows only.")
        return 2

    # Avoid crashes when the console can't encode window titles (e.g. zero-width chars).
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

    user32 = ctypes.windll.user32
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    rows = []

    def _enum(hwnd, lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            title_buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title_buf, length + 1)
            title = title_buf.value or ""
            # Make titles one-line and console-safe (some apps include weird separators).
            title = " ".join(title.replace("\r", " ").replace("\n", " ").split())
            if not title.strip():
                return True
            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            cls = class_buf.value or ""
            rect = wintypes.RECT()
            cw = ch = 0
            try:
                if user32.GetClientRect(hwnd, ctypes.byref(rect)):
                    cw = int(rect.right - rect.left)
                    ch = int(rect.bottom - rect.top)
            except Exception:
                pass

            pid = wintypes.DWORD()
            try:
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            except Exception:
                pid = wintypes.DWORD(0)

            rows.append((int(hwnd), int(pid.value), cw, ch, cls, title))
        except Exception:
            pass
        return True

    user32.EnumWindows(EnumProc(_enum), 0)

    rows.sort(key=lambda r: (r[4], r[5]))
    for hwnd, pid, cw, ch, cls, title in rows:
        print(f"{hwnd:10d}  {pid:6d}  {cw:4d}x{ch:<4d}  {cls:24s}  {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
