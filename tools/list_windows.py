#!/usr/bin/env python3
"""
List visible top-level windows on Windows (title + class).

This helps configure `PORCE_CAPTURE_WINDOW_TITLE` for Pipeline A window capture.
"""

from __future__ import annotations

import os
import ctypes
from ctypes import wintypes


def main() -> int:
    if os.name != "nt":
        print("[error] Windows only.")
        return 2

    user32 = ctypes.windll.user32

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
            if not title.strip():
                return True
            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            cls = class_buf.value or ""
            rows.append((int(hwnd), cls, title))
        except Exception:
            pass
        return True

    user32.EnumWindows(EnumProc(_enum), 0)

    rows.sort(key=lambda r: (r[1], r[2]))
    for hwnd, cls, title in rows:
        print(f"{hwnd:10d}  {cls:24s}  {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

