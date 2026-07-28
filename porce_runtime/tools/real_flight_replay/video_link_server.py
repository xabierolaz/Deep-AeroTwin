#!/usr/bin/env python3
"""Servidor de enlace de video simulado (Pipeline B, replay M_20_1RR).

Sirve el video grabado a bordo como frames JPEG sobre HTTP, imitando el enlace
de telemetria de video del dron real (companion computer -> estacion en tierra).

Modo principal (determinista, pull):
  GET /api/video/info   -> metadatos del clip (fps, frames, res, t0 unix)
  GET /api/video/next   -> siguiente frame JPEG; headers X-Frame-Idx y
                           X-Frame-Timestamp-Unix; 204 al final del clip
  GET /api/video/seek?idx=N -> reinicia el puntero secuencial
  GET /api/video/frame?idx=N&scale=1.0&quality=85 -> frame concreto (debug)

Modo streaming (realismo demostrativo):
  GET /api/video/mjpeg?fps=15&scale=0.5&quality=80 -> multipart MJPEG

Opciones de enlace (resolucion/calidad/tasa):
  --scale   reescala frames (1.0 = nativo 3840x2160)
  --quality calidad JPEG (1-100)
  --max-fps limita la entrega en /api/video/next (0 = sin limite; la vision marca el ritmo)

Uso:
  python video_link_server.py --port 8099
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import cv2

VIDEO = Path(__file__).resolve().parent.parent.parent.parent / "papers/pipeline_a_telemetry/data/M_20_1RR_VIDEO/video_2026-07-06_09-38-48_253.mp4"
SYNC_JSON = VIDEO.with_suffix(".json")


class LinkState:
    def __init__(self, video_path: Path, scale: float, quality: int, max_fps: float):
        self.video_path = video_path
        self.scale = max(0.05, float(scale))
        self.quality = min(100, max(1, int(quality)))
        self.max_fps = max(0.0, float(max_fps))
        self.lock = threading.Lock()
        self.cap = cv2.VideoCapture(str(video_path))
        if not self.cap.isOpened():
            raise SystemExit(f"no se pudo abrir {video_path}")
        self.fps = float(self.cap.get(cv2.CAP_PROP_FPS))
        self.n_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.idx = 0
        self.last_serve_ts = 0.0
        sync = json.loads(SYNC_JSON.read_text(encoding="utf-8"))
        self.t0_unix = float(sync["video_start_unix_ms"]) / 1000.0

    def _read_at(self, idx: int):
        with self.lock:
            if idx < self.idx:
                self.cap.release()
                self.cap = cv2.VideoCapture(str(self.video_path))
                self.idx = 0
            while self.idx < idx:
                ok = self.cap.grab()
                if not ok:
                    return None
                self.idx += 1
            ok, frame = self.cap.read()
            if not ok or frame is None:
                return None
            self.idx += 1
            return frame

    def next_frame(self):
        if self.max_fps > 0.0:
            now = time.perf_counter()
            wait = (1.0 / self.max_fps) - (now - self.last_serve_ts)
            if wait > 0.0:
                time.sleep(wait)
            self.last_serve_ts = time.perf_counter()
        return self._read_at(self.idx)

    def seek(self, idx: int):
        with self.lock:
            if idx < self.idx:
                self.cap.release()
                self.cap = cv2.VideoCapture(str(self.video_path))
                self.idx = 0
            target = self.idx
        self._read_at(target if idx is None else idx)

    def encode(self, frame, scale=None, quality=None):
        s = float(scale) if scale else self.scale
        q = int(quality) if quality else self.quality
        if abs(s - 1.0) > 1e-3:
            frame = cv2.resize(frame, (int(frame.shape[1] * s), int(frame.shape[0] * s)))
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, q])
        return buf.tobytes() if ok else None


def make_handler(state: LinkState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _jpeg(self, idx: int, frame):
            if frame is None:
                self.send_response(204)
                self.end_headers()
                return
            data = state.encode(frame)
            ts = state.t0_unix + idx / state.fps
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Frame-Idx", str(idx))
            self.send_header("X-Frame-Timestamp-Unix", f"{ts:.3f}")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path == "/api/video/info":
                body = json.dumps({
                    "fps": state.fps,
                    "frames": state.n_frames,
                    "width": state.width,
                    "height": state.height,
                    "duration_s": state.n_frames / state.fps,
                    "video_start_unix_s": state.t0_unix,
                    "scale": state.scale,
                    "quality": state.quality,
                    "idx": state.idx,
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif u.path == "/api/video/next":
                frame = state.next_frame()
                self._jpeg(state.idx - 1 if frame is not None else state.idx, frame)
            elif u.path == "/api/video/seek":
                idx = int(q.get("idx", ["0"])[0])
                with state.lock:
                    state.cap.release()
                    state.cap = cv2.VideoCapture(str(state.video_path))
                    state.idx = 0
                state._read_at(idx)
                body = json.dumps({"idx": state.idx}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif u.path == "/api/video/frame":
                idx = int(q.get("idx", ["0"])[0])
                frame = state._read_at(idx)
                if frame is None:
                    self.send_response(204)
                    self.end_headers()
                    return
                data = state.encode(frame, q.get("scale", [None])[0], q.get("quality", [None])[0])
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("X-Frame-Idx", str(idx))
                self.end_headers()
                self.wfile.write(data)
            elif u.path == "/api/video/mjpeg":
                fps_lim = float(q.get("fps", ["15"])[0])
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
                while True:
                    frame = state.next_frame()
                    if frame is None:
                        break
                    data = state.encode(frame, q.get("scale", [None])[0], q.get("quality", [None])[0])
                    try:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        break
                    if fps_lim > 0:
                        time.sleep(1.0 / fps_lim)
            else:
                self.send_response(404)
                self.end_headers()

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=Path, default=VIDEO)
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--quality", type=int, default=85)
    ap.add_argument("--max-fps", type=float, default=0.0)
    args = ap.parse_args()

    state = LinkState(args.video, args.scale, args.quality, args.max_fps)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(state))
    print(f"[video-link] {args.video.name} {state.width}x{state.height}@{state.fps:.2f} "
          f"({state.n_frames} frames) en http://127.0.0.1:{args.port} "
          f"scale={state.scale} quality={state.quality} max_fps={state.max_fps or 'ilimitado'}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
