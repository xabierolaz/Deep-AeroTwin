#!/usr/bin/env python3
r"""
live_viewer.py — cliente del visor en vivo (Windows, usa venv del proyecto).

Captura la ventana de Unreal con PrintWindow(PW_RENDERFULLCONTENT) (robusto a
oclusión), la envía al live_server.py (WSL/GPU) y muestra una ventana OpenCV con:
  - vista lado a lado  INPUT | RESTYLED
  - un TRACKBAR de noise_scale (0-100 -> 0.00-1.00) que cambia el realismo EN VIVO
Teclas: [q] salir · [r] reiniciar sesión del modelo · [+/-] mover el slider.

Ejecutar (Windows, con la ventana de Unreal abierta):
  venv\Scripts\python.exe neural\live_viewer.py --title "airtraffic (64-bit" --server http://127.0.0.1:9500

Modo prueba sin Unreal (alimenta un vídeo en bucle):
  venv\Scripts\python.exe neural\live_viewer.py --video tmp\ejea_clip_input.mp4 --server http://127.0.0.1:9500

NO probado end-to-end desde el sandbox (necesita la ventana de Unreal + el server
GPU). La captura PrintWindow es la misma que tmp\printwindow_probe.py (probada).
"""
import argparse, ctypes, time, urllib.request, urllib.error
from ctypes import wintypes
import numpy as np
import cv2

PW_RENDERFULLCONTENT = 0x00000002


# ---------- captura PrintWindow ----------
class WindowGrabber:
    def __init__(self, title_substr):
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32
        self.title = title_substr.lower()
        self.hwnd = self._find()
        if not self.hwnd:
            raise RuntimeError(f"No encuentro ventana que contenga: {title_substr!r}")

    def _find(self):
        found = []
        def cb(hwnd, _):
            if not self.user32.IsWindowVisible(hwnd):
                return True
            n = self.user32.GetWindowTextLengthW(hwnd)
            if not n:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            self.user32.GetWindowTextW(hwnd, buf, n + 1)
            if self.title in (buf.value or "").lower():
                found.append(hwnd)
            return True
        proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        self.user32.EnumWindows(proc(cb), 0)
        return found[0] if found else None

    def grab(self):
        u, g = self.user32, self.gdi32
        wrect = wintypes.RECT(); u.GetWindowRect(self.hwnd, ctypes.byref(wrect))
        ww, wh = wrect.right - wrect.left, wrect.bottom - wrect.top
        if ww <= 0 or wh <= 0:
            return None
        crect = wintypes.RECT(); u.GetClientRect(self.hwnd, ctypes.byref(crect))
        cw, ch = crect.right - crect.left, crect.bottom - crect.top
        pt = wintypes.POINT(0, 0); u.ClientToScreen(self.hwnd, ctypes.byref(pt))
        ox, oy = pt.x - wrect.left, pt.y - wrect.top

        hdc_win = u.GetWindowDC(self.hwnd)
        hdc_mem = g.CreateCompatibleDC(hdc_win)
        hbmp = g.CreateCompatibleBitmap(hdc_win, ww, wh)
        old = g.SelectObject(hdc_mem, hbmp)
        u.PrintWindow(self.hwnd, hdc_mem, PW_RENDERFULLCONTENT)

        class BIH(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long),
                        ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD),
                        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                        ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
                        ("biClrImportant", wintypes.DWORD)]
        bmi = BIH(); bmi.biSize = ctypes.sizeof(BIH); bmi.biWidth = ww
        bmi.biHeight = -wh; bmi.biPlanes = 1; bmi.biBitCount = 32; bmi.biCompression = 0
        buf = ctypes.create_string_buffer(ww * wh * 4)
        g.GetDIBits(hdc_mem, hbmp, 0, wh, buf, ctypes.byref(bmi), 0)
        img = np.frombuffer(buf, np.uint8).reshape(wh, ww, 4)[:, :, :3]  # BGR

        # liberar GDI en orden correcto (evita el leak conocido)
        g.SelectObject(hdc_mem, old)
        g.DeleteObject(hbmp); g.DeleteDC(hdc_mem); u.ReleaseDC(self.hwnd, hdc_win)

        client = img[oy:oy + ch, ox:ox + cw]
        return client.copy() if client.size else None


# ---------- cliente HTTP ----------
def post_frame(server, bgr, noise_scale, timeout=10):
    ok, enc = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        return None
    url = f"{server}/infer?noise_scale={noise_scale:.3f}"
    req = urllib.request.Request(url, data=enc.tobytes(),
                                 headers={"Content-Type": "application/octet-stream"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status == 204:
                return None
            data = r.read()
            return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    except urllib.error.URLError as e:
        print("[viewer] server error:", e)
        return None


def post_params(server, **kw):
    import json
    try:
        req = urllib.request.Request(f"{server}/params",
            data=json.dumps(kw).encode(), headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as e:
        print("[viewer] /params error:", e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:9500")
    ap.add_argument("--title", default="airtraffic (64-bit")
    ap.add_argument("--video", default=None, help="modo prueba: vídeo en bucle en vez de la ventana")
    ap.add_argument("--size", type=int, default=480)
    ap.add_argument("--ns0", type=int, default=80, help="noise_scale inicial 0-100")
    args = ap.parse_args()

    src = None
    grab = None
    if args.video:
        src = cv2.VideoCapture(args.video)
    else:
        grab = WindowGrabber(args.title)

    win = "AeroTwin live restyle  [q]salir [r]reset"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.createTrackbar("noise_scale x100", win, args.ns0, 100, lambda v: None)

    S = args.size
    last_out = np.zeros((S, S, 3), np.uint8)
    fps_t, fps_n, fps = time.time(), 0, 0.0

    while True:
        if src is not None:
            ok, frame = src.read()
            if not ok:
                src.set(cv2.CAP_PROP_POS_FRAMES, 0); continue
        else:
            frame = grab.grab()
            if frame is None:
                time.sleep(0.05); continue
        frame = cv2.resize(frame, (S, S))

        ns = cv2.getTrackbarPos("noise_scale x100", win) / 100.0
        out = post_frame(args.server, frame, ns)
        if out is not None:
            last_out = cv2.resize(out, (S, S))
            fps_n += 1
            if time.time() - fps_t >= 1.0:
                fps = fps_n / (time.time() - fps_t); fps_t = time.time(); fps_n = 0

        sep = np.full((S, 4, 3), 60, np.uint8)
        canvas = np.hstack([frame, sep, last_out])
        cv2.putText(canvas, f"INPUT", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
        cv2.putText(canvas, f"RESTYLED ns={ns:.2f}  out~{fps:.1f}fps", (S+12, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,180), 2)
        cv2.imshow(win, canvas)

        k = cv2.waitKey(1) & 0xFF
        if k == ord('q'):
            break
        elif k == ord('r'):
            post_params(args.server, restart=True)
            print("[viewer] sesión reiniciada")
        elif k in (ord('+'), ord('=')):
            cv2.setTrackbarPos("noise_scale x100", win, min(100, int(ns*100)+5))
        elif k == ord('-'):
            cv2.setTrackbarPos("noise_scale x100", win, max(0, int(ns*100)-5))

    if src is not None:
        src.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
