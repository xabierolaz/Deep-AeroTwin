#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VISION SYSTEM (The Eyes) v3.0 - YOLO11 INTEGRATION
--------------------------------------------------
- Real-time Screen Capture (MSS)
- YOLOv11 Inference (Ultralytics)
- GPS Projection (Pixel -> GeoCoords)
- Debug Visualization Window
"""

import os
import time
import math
import sys
import ctypes
from ctypes import wintypes
import cv2
import numpy as np
import mss
from datetime import datetime
import requests

# Ultralytics writes settings under %APPDATA% by default, which can be locked down
# in some Windows environments. It honors YOLO_CONFIG_DIR as an override.
_default_yolo_cfg = os.path.join(os.path.dirname(__file__), "logs")
if "YOLO_CONFIG_DIR" not in os.environ:
    os.makedirs(_default_yolo_cfg, exist_ok=True)
    os.environ["YOLO_CONFIG_DIR"] = _default_yolo_cfg

from ultralytics import YOLO
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

from geo_projector import GeoProjector

# --- CONFIGURACIÓN E IMPORTACIONES ---
try:
    from constants import (
        MAVLINK_HUB_HTTP_PORT, DETECTION_RANGE_M, EARTH_RADIUS_M,
        CAMERA_FOV_VERTICAL, CAMERA_HEIGHT, CAMERA_WIDTH,
        TERRAIN_ELEVATION_MSL, SYSTEM_MODE
    )
except ImportError:
    # Fallback si se ejecuta directo sin contexto
    MAVLINK_HUB_HTTP_PORT = 8080
    DETECTION_RANGE_M = 80.0
    EARTH_RADIUS_M = 6371000
    CAMERA_FOV_VERTICAL = 45.0
    CAMERA_HEIGHT = 640 # Ajustado para captura
    CAMERA_WIDTH = 640
    TERRAIN_ELEVATION_MSL = 435.0
    SYSTEM_MODE = 'SIMULATION'

# --- CONSTANTES DE VISION ---
CONFIDENCE_THRESHOLD = 0.40  # Solo mostrar si está 40% seguro
TARGET_CLASS_NAMES = ["biker", "cow", "tower"]  # Custom synthetic classes (3d_to_dataset_xabi)

MIN_BOX_HEIGHT_PX = float(os.environ.get("PORCE_VISION_MIN_BOX_HEIGHT_PX", "10"))
MIN_BOX_AREA_FRAC = float(os.environ.get("PORCE_VISION_MIN_BOX_AREA_FRAC", "0.001"))
TRACK_TTL_S = float(os.environ.get("PORCE_VISION_TRACK_TTL_S", "2.0"))
TRACK_HOLD_S = float(os.environ.get("PORCE_VISION_TRACK_HOLD_S", "0.8"))
SMOOTH_TAU_S = float(os.environ.get("PORCE_VISION_SMOOTH_TAU_S", "0.6"))
ID_BUCKET_PX = int(float(os.environ.get("PORCE_VISION_ID_BUCKET_PX", "64")))
MAX_OBS_PER_FRAME = int(float(os.environ.get("PORCE_VISION_MAX_OBS_PER_FRAME", "25")))
HEARTBEAT_S = float(os.environ.get("PORCE_VISION_HEARTBEAT_S", "5.0"))

PIPELINE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = PIPELINE_DIR / "weights" / "yolo_3d_dome_v1_best.pt"
MODEL_PATH = os.environ.get("PORCE_YOLO_MODEL", str(DEFAULT_MODEL_PATH))

# Back-compat fallbacks (older docs referenced COCO weights).
if not Path(MODEL_PATH).exists():
    MODEL_PATH = "yolo11n.pt"  # repo root / cwd fallback
if not os.path.exists(MODEL_PATH):
    # Intento buscar en subcarpeta si no está en root
    MODEL_PATH = "3d_to_dataset_xabi/yolo11n.pt"

BRAIN_URL = f"http://127.0.0.1:{MAVLINK_HUB_HTTP_PORT}"
TELEMETRY_URL = f"{BRAIN_URL}/api/state/latest"
OBSTACLES_URL = f"{BRAIN_URL}/api/obstacles"

def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] [VISION-YOLO] {msg}", flush=True)

@dataclass(frozen=True)
class VisionTrack:
    obs_id: int
    class_name: str
    lat: float
    lon: float
    dist: float
    conf: float
    bbox: dict
    cx: float
    cy: float
    last_seen_ts: float
    seen_count: int


class VisionSystem:
    def __init__(self):
        log("Inicializando sistema de vision YOLOv11...")

        # Avoid coordinate mismatches on high-DPI displays (important for window/ROI capture).
        self._set_windows_dpi_aware()

        # 1. Cargar Modelo
        try:
            self.model = YOLO(MODEL_PATH)
            log(f"Modelo cargado correctamente: {MODEL_PATH}")

            # Resolve class indices by name so this works for both custom-trained and COCO weights.
            names = self.model.names
            if isinstance(names, dict):
                id_by_name = {str(v): int(k) for k, v in names.items()}
            else:
                id_by_name = {str(v): int(i) for i, v in enumerate(list(names))}

            target_names = list(TARGET_CLASS_NAMES)
            # If the custom names are missing, fall back to common COCO labels.
            if not any(n in id_by_name for n in target_names):
                target_names = ["person", "bicycle", "cow"]

            self._target_class_ids = sorted({id_by_name[n] for n in target_names if n in id_by_name})
            log(f"Clases objetivo: {target_names} -> ids={self._target_class_ids}")
            # Warmup
            log("Realizando inferencia de calentamiento (Warmup)...")
            self.model.predict(source=np.zeros((640,640,3), dtype=np.uint8), verbose=False)
        except Exception as e:
            log(f"ERROR CRITICO cargando modelo: {e}")
            sys.exit(1)

        # Projection config (defaults tuned for Pipeline A SIM).
        # Camera tilt: 30deg down from horizon => mount_pitch=-30deg unless overridden.
        self._camera_vfov_deg = float(os.environ.get("PORCE_CAMERA_VFOV_DEG", str(CAMERA_FOV_VERTICAL)))
        self._mount_roll_deg = float(os.environ.get("PORCE_CAMERA_MOUNT_ROLL_DEG", "0"))
        self._mount_pitch_deg = float(os.environ.get("PORCE_CAMERA_MOUNT_PITCH_DEG", "-30"))
        self._mount_yaw_deg = float(os.environ.get("PORCE_CAMERA_MOUNT_YAW_DEG", "0"))
        self.projector = GeoProjector()
        self.sct = mss.mss()
        self.session = requests.Session()
        self._obstacle_token = os.environ.get("PORCE_OBSTACLE_TOKEN", "").strip()
        
        # --- Capture configuration ---
        # Pipeline A expectation: Unreal "Play In New Window" renders the drone camera at 640x640.
        self._expect_w = int(os.environ.get("PORCE_CAPTURE_EXPECT_WIDTH", str(CAMERA_WIDTH)))
        self._expect_h = int(os.environ.get("PORCE_CAPTURE_EXPECT_HEIGHT", str(CAMERA_HEIGHT)))

        # Preferred: capture by window title (robust against being behind other windows).
        self._capture_window_title = os.environ.get("PORCE_CAPTURE_WINDOW_TITLE", "").strip()
        self._capture_window_class = os.environ.get("PORCE_CAPTURE_WINDOW_CLASS", "").strip()
        self._capture_window_exact = os.environ.get("PORCE_CAPTURE_WINDOW_EXACT", "").strip() in ("1", "true", "True")
        self._capture_window_focus = os.environ.get("PORCE_CAPTURE_WINDOW_FOCUS", "1").strip() in ("1", "true", "True")
        self._capture_window_topmost = os.environ.get("PORCE_CAPTURE_WINDOW_TOPMOST", "0").strip() in ("1", "true", "True")
        self._capture_hwnd = None

        if self._capture_window_title:
            self._capture_mode = "window"
            self._capture_hwnd = self._win32_find_window()
            if self._capture_hwnd:
                self._win32_prepare_window(self._capture_hwnd)
                self.monitor = self._win32_client_region(self._capture_hwnd)
            else:
                self.monitor = None
            log(f"Zona de captura (window): title={self._capture_window_title!r} exact={self._capture_window_exact} class={self._capture_window_class!r}")
            if self._capture_hwnd and self.monitor:
                log(
                    "[CAPTURE] Window ready hwnd={hwnd} client={w}x{h} at ({l},{t})".format(
                        hwnd=int(self._capture_hwnd),
                        w=int(self.monitor.get("width", 0) or 0),
                        h=int(self.monitor.get("height", 0) or 0),
                        l=int(self.monitor.get("left", 0) or 0),
                        t=int(self.monitor.get("top", 0) or 0),
                    )
                )
            else:
                log("[CAPTURE] Window not found yet; will retry in run loop.")
        else:
            # Fallback: monitor capture, optionally with ROI override (match Unreal camera viewport for correct geometry).
            monitor_idx = int(os.environ.get("PORCE_CAPTURE_MONITOR", "1"))
            self.monitor = self.sct.monitors[monitor_idx]
            roi_left = os.environ.get("PORCE_CAPTURE_LEFT")
            roi_top = os.environ.get("PORCE_CAPTURE_TOP")
            roi_w = os.environ.get("PORCE_CAPTURE_WIDTH")
            roi_h = os.environ.get("PORCE_CAPTURE_HEIGHT")
            if roi_left and roi_top and roi_w and roi_h:
                self.monitor = {
                    "left": int(roi_left),
                    "top": int(roi_top),
                    "width": int(roi_w),
                    "height": int(roi_h),
                }
            self._capture_mode = "roi_or_monitor"
            log(f"Zona de captura: {self.monitor}")

        # --- Debug window (YOLO overlay) ---
        # Default: enabled, and when capturing a window we "dock" the debug view next to it.
        self._debug_title = os.environ.get("PORCE_VISION_DEBUG_TITLE", "YOLO V11 VISION DEBUG").strip() or "YOLO V11 VISION DEBUG"
        self._debug_enabled = os.environ.get("PORCE_VISION_DEBUG_WINDOW", "1").strip() in ("1", "true", "True")
        self._debug_scale = float(os.environ.get("PORCE_VISION_DEBUG_SCALE", "1.0"))
        self._debug_dock = os.environ.get("PORCE_VISION_DEBUG_DOCK", "").strip() in ("1", "true", "True")
        if not os.environ.get("PORCE_VISION_DEBUG_DOCK"):
            self._debug_dock = (self._capture_mode == "window")
        self._debug_dock_gap_px = int(float(os.environ.get("PORCE_VISION_DEBUG_DOCK_GAP_PX", "8")))
        self._debug_topmost = os.environ.get("PORCE_VISION_DEBUG_TOPMOST", "0").strip() in ("1", "true", "True")
        self._debug_last_dock_anchor = None
        self._debug_last_size = None

        # Vision loop rate control (0 = as fast as possible).
        self._target_fps = float(os.environ.get("PORCE_VISION_TARGET_FPS", "0"))

        # FPS measurement (EMA).
        self._last_frame_ts = None
        self._fps_ema = 0.0

        if self._debug_enabled:
            try:
                cv2.namedWindow(self._debug_title, cv2.WINDOW_NORMAL)
                base_w = max(1, int(self._expect_w))
                base_h = max(1, int(self._expect_h))
                scale = float(self._debug_scale) if math.isfinite(self._debug_scale) and self._debug_scale > 0.0 else 1.0
                cv2.resizeWindow(self._debug_title, int(base_w * scale), int(base_h * scale))
                if self._debug_topmost and hasattr(cv2, "WND_PROP_TOPMOST"):
                    try:
                        cv2.setWindowProperty(self._debug_title, cv2.WND_PROP_TOPMOST, 1)
                    except Exception:
                        pass
            except Exception as e:
                log(f"[WARN] No se pudo crear la ventana debug de YOLO: {e}")
                self._debug_enabled = False

        # Local coordinate origin (ENU meters): set once we have a real GPS fix.
        # Z is "up" in meters relative to the local ground under the origin.
        self._origin_lat: Optional[float] = None
        self._origin_lon: Optional[float] = None
        self._origin_ground_msl: Optional[float] = None
        self._overlay_max_obs = int(float(os.environ.get("PORCE_VISION_OVERLAY_MAX_OBS", "5")))

        # Simple temporal stabilizer (reduces bbox/telemetry jitter in the projected lat/lon).
        self._tracks: dict[int, VisionTrack] = {}
        # Ensure we log once when the PIE window becomes available.
        self._capture_found_logged = bool(self._capture_hwnd and self.monitor)

    @staticmethod
    def _set_windows_dpi_aware() -> None:
        if os.name != "nt":
            return
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    def _win32_find_window(self):
        if os.name != "nt":
            return None

        user32 = ctypes.windll.user32

        target = str(self._capture_window_title)
        target_l = target.lower()
        want_class = str(self._capture_window_class) if self._capture_window_class else ""

        matches = []

        EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _enum(hwnd, lparam):
            try:
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value or ""
                if not title:
                    return True

                if self._capture_window_exact:
                    ok = (title == target)
                else:
                    ok = (target_l in title.lower())
                if not ok:
                    return True

                if want_class:
                    cbuf = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, cbuf, 256)
                    if (cbuf.value or "") != want_class:
                        return True

                matches.append(hwnd)
            except Exception:
                pass
            return True

        try:
            user32.EnumWindows(EnumProc(_enum), 0)
        except Exception:
            return None

        return matches[0] if matches else None

    def _win32_prepare_window(self, hwnd) -> None:
        if os.name != "nt" or not hwnd:
            return
        user32 = ctypes.windll.user32

        # Best-effort: ensure the window is visible and on top so MSS screen capture sees it.
        try:
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)
        except Exception:
            pass

        if self._capture_window_focus:
            try:
                user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

        if self._capture_window_topmost:
            try:
                HWND_TOPMOST = -1
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_SHOWWINDOW = 0x0040
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
            except Exception:
                pass

    def _win32_client_region(self, hwnd):
        if os.name != "nt" or not hwnd:
            return None
        user32 = ctypes.windll.user32

        rect = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        w = int(rect.right - rect.left)
        h = int(rect.bottom - rect.top)
        if w <= 0 or h <= 0:
            return None

        # Client (0,0) -> screen coords.
        pt = wintypes.POINT(0, 0)
        if not user32.ClientToScreen(hwnd, ctypes.byref(pt)):
            return None

        region = {"left": int(pt.x), "top": int(pt.y), "width": int(w), "height": int(h)}
        return region

    def _maybe_dock_debug_window(self) -> None:
        if not self._debug_enabled:
            return
        if not self._debug_dock:
            return
        if self._capture_mode != "window":
            return
        if not self.monitor:
            return
        try:
            anchor = (
                int(self.monitor.get("left", 0)),
                int(self.monitor.get("top", 0)),
                int(self.monitor.get("width", 0)),
                int(self.monitor.get("height", 0)),
            )
            if anchor == self._debug_last_dock_anchor:
                return
            x = int(anchor[0]) + int(anchor[2]) + int(self._debug_dock_gap_px)
            y = int(anchor[1])
            cv2.moveWindow(self._debug_title, x, y)
            self._debug_last_dock_anchor = anchor
        except Exception:
            pass

    def get_telemetry(self):
        try:
            r = self.session.get(TELEMETRY_URL, timeout=0.5)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return None

    @staticmethod
    def _alpha_from_dt(dt_s: float) -> float:
        tau = float(SMOOTH_TAU_S)
        if not math.isfinite(tau) or tau <= 0.0:
            return 1.0
        dt = max(0.0, float(dt_s))
        return float(1.0 - math.exp(-dt / tau))

    @staticmethod
    def _make_obs_id(cls: int, cx: float, cy: float) -> int:
        bucket = int(ID_BUCKET_PX) if int(ID_BUCKET_PX) > 0 else 64
        bx = int(max(0.0, float(cx)) // bucket)
        by = int(max(0.0, float(cy)) // bucket)
        return int((int(cls) + 1) * 1_000_000 + by * 1000 + bx)

    def _purge_tracks(self, now_s: float) -> None:
        ttl = float(TRACK_TTL_S)
        if not math.isfinite(ttl) or ttl <= 0.0:
            self._tracks.clear()
            return
        dead = [k for k, t in self._tracks.items() if (now_s - float(t.last_seen_ts)) > ttl]
        for k in dead:
            self._tracks.pop(k, None)

    @staticmethod
    def _enu_xy_m(origin_lat: float, origin_lon: float, lat: float, lon: float) -> Tuple[float, float]:
        # Local tangent plane approximation: good enough for <~1km.
        R = float(EARTH_RADIUS_M)
        dlat = math.radians(float(lat) - float(origin_lat))
        dlon = math.radians(float(lon) - float(origin_lon))
        north = dlat * R
        east = dlon * R * (math.cos(math.radians(float(origin_lat))) or 1e-6)
        # ENU: x=east, y=north
        return float(east), float(north)

    @staticmethod
    def _estimate_height_m_from_bbox(
        *,
        ray_top_ned: np.ndarray,
        base_north_m: float,
        base_east_m: float,
        alt_agl_m: float,
        dist_h_m: float,
    ) -> Optional[float]:
        """Estimate object height (meters) assuming:

        - bbox bottom touches ground (base point),
        - bbox top is roughly vertically above the base.

        Returns None if the geometry is inconsistent (e.g. huge false-positive boxes).
        """
        try:
            n = float(ray_top_ned[0])
            e = float(ray_top_ned[1])
            d = float(ray_top_ned[2])
        except Exception:
            return None

        # Least-squares t to align (n*t, e*t) with the base (north,east).
        denom = n * n + e * e
        if denom <= 1e-12:
            return None
        t = (n * float(base_north_m) + e * float(base_east_m)) / denom
        if not math.isfinite(t) or t <= 0.0:
            return None

        pred_n = n * t
        pred_e = e * t
        err = math.hypot(pred_n - float(base_north_m), pred_e - float(base_east_m))
        # If the ray misses the vertical line too much, reject (often caused by massive boxes).
        if err > max(2.0, 0.25 * max(1.0, float(dist_h_m))):
            return None

        z_down = d * t
        h = float(alt_agl_m)
        if not math.isfinite(z_down) or not math.isfinite(h) or h <= 0.5:
            return None

        height = h - z_down
        if not math.isfinite(height):
            return None

        # Clamp to avoid overlay explosions.
        height = max(0.0, min(float(height), 200.0))
        return float(height)

    def run(self):
        log("Sistema listo. Esperando visualizacion...")

        hb_every_s = float(HEARTBEAT_S)
        hb_last_ts = time.time()
        frame_count = 0
        last_dets = 0
        last_send = 0
        
        while True:
            frame_now = time.perf_counter()
            if self._last_frame_ts is not None:
                dt = float(frame_now) - float(self._last_frame_ts)
                if math.isfinite(dt) and dt > 1e-6:
                    fps_inst = 1.0 / dt
                    self._fps_ema = float(fps_inst) if self._fps_ema <= 0.0 else float(0.9 * self._fps_ema + 0.1 * fps_inst)
            self._last_frame_ts = float(frame_now)
             
            # 1. Obtener Telemetria (Necesaria para proyeccion)
            telemetry = self.get_telemetry()
            if not telemetry:
                # Si no hay telemetria, esperamos
                time.sleep(0.5)
                continue
                
            dron_lat = float(telemetry.get('lat', 0) or 0.0)
            dron_lon = float(telemetry.get('lon', 0) or 0.0)
            dron_alt_msl = float(telemetry.get('alt', 0) or 0.0)
            # Prefer AGL if provided by Brain, else use MSL - terrain.
            dron_alt_agl = telemetry.get('rel_alt', None)
            if dron_alt_agl is None:
                dron_alt_agl = float(dron_alt_msl) - float(TERRAIN_ELEVATION_MSL)
            dron_alt_agl = float(dron_alt_agl or 0.0)
            dron_hdg = telemetry.get('heading', 0)
            dron_yaw = float(telemetry.get('yaw', dron_hdg) or 0.0)
            dron_pitch = float(telemetry.get('pitch', 0) or 0.0)
            dron_roll = float(telemetry.get('roll', 0) or 0.0)

            ground_msl = float(dron_alt_msl) - float(dron_alt_agl)

            # Establish a local origin once we have a non-zero GPS fix.
            if self._origin_lat is None:
                if (abs(float(dron_lat)) > 0.0001) and (abs(float(dron_lon)) > 0.0001) and math.isfinite(ground_msl):
                    self._origin_lat = float(dron_lat)
                    self._origin_lon = float(dron_lon)
                    self._origin_ground_msl = float(ground_msl)
                    log(f"[ORIGIN] ENU origin set at lat={self._origin_lat:.6f} lon={self._origin_lon:.6f} ground_msl={self._origin_ground_msl:.1f}m")

            drone_x_m = drone_y_m = 0.0
            if self._origin_lat is not None and self._origin_lon is not None:
                drone_x_m, drone_y_m = self._enu_xy_m(self._origin_lat, self._origin_lon, float(dron_lat), float(dron_lon))
            drone_z_m = float(dron_alt_agl)  # "up" meters above local ground

            # 2. Captura de Pantalla
            if self._capture_mode == "window":
                if not self._capture_hwnd:
                    self._capture_hwnd = self._win32_find_window()
                    if self._capture_hwnd:
                        self._win32_prepare_window(self._capture_hwnd)
                if not self._capture_hwnd:
                    # No window yet (Unreal PIE not started?)
                    time.sleep(0.5)
                    continue

                self.monitor = self._win32_client_region(self._capture_hwnd)
                if not self.monitor:
                    time.sleep(0.2)
                    continue

                if not self._capture_found_logged:
                    self._capture_found_logged = True
                    log(
                        "[CAPTURE] Window acquired hwnd={hwnd} client={w}x{h} at ({l},{t})".format(
                            hwnd=int(self._capture_hwnd),
                            w=int(self.monitor.get("width", 0) or 0),
                            h=int(self.monitor.get("height", 0) or 0),
                            l=int(self.monitor.get("left", 0) or 0),
                            t=int(self.monitor.get("top", 0) or 0),
                        )
                    )

                if (int(self.monitor.get("width", 0)) != int(self._expect_w)) or (int(self.monitor.get("height", 0)) != int(self._expect_h)):
                    log(f"[WARN] Client area is {self.monitor.get('width')}x{self.monitor.get('height')} (expected {self._expect_w}x{self._expect_h}). Projection assumes the true camera viewport.")

                # Keep on top if requested (helps if the window gets covered).
                self._win32_prepare_window(self._capture_hwnd)
                self._maybe_dock_debug_window()

            if not self.monitor:
                time.sleep(0.5)
                continue

            screenshot = np.array(self.sct.grab(self.monitor))
            # Convertir BGRA a BGR
            img_bgr = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            frame_count += 1
            
            # Redimensionar para velocidad (opcional, YOLO lo hace auto, pero para visualizacion consistente)
            # img_resized = cv2.resize(img_bgr, (640, 640))
            
            # 3. Inferencia YOLO
            # Filter by class IDs when available (reduces spurious detections on COCO weights).
            class_filter = getattr(self, "_target_class_ids", None)
            if not class_filter:
                results = self.model.predict(img_bgr, conf=CONFIDENCE_THRESHOLD, verbose=False)
            else:
                results = self.model.predict(img_bgr, conf=CONFIDENCE_THRESHOLD, classes=class_filter, verbose=False)
            
            now_s = time.time()
            self._purge_tracks(now_s)

            H, W = img_bgr.shape[:2]
            if self._debug_enabled:
                try:
                    scale = float(self._debug_scale) if math.isfinite(self._debug_scale) and self._debug_scale > 0.0 else 1.0
                    dw = max(1, int(W * scale))
                    dh = max(1, int(H * scale))
                    if self._debug_last_size != (dw, dh):
                        cv2.resizeWindow(self._debug_title, dw, dh)
                        self._debug_last_size = (dw, dh)
                except Exception:
                    pass
            frame_dets: dict[int, dict] = {}
              
            # 4. Procesar Detecciones
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    # Bounding Box
                    x1, y1, x2, y2 = box.xyxy[0]
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    class_name = str(self.model.names[cls])
                    
                    # Filtros basicos:
                    # - La proyeccion pixel->suelo es extremadamente sensible para bboxes pequenas (cerca del horizonte).
                    bw = x2 - x1
                    bh = y2 - y1
                    if bw <= 1 or bh <= 1:
                        continue
                    if bh < float(MIN_BOX_HEIGHT_PX):
                        continue
                    if (bw * bh) < (float(MIN_BOX_AREA_FRAC) * float(H) * float(W)):
                        continue

                    # Centro del objeto (base del bbox = "pies" en el suelo)
                    cx = float((x1 + x2) / 2.0)
                    cy = float(y2)  # Base del bbox. Antes era y1+y2 (bug) => fuera de frame.
                    cx = float(min(max(cx, 0.0), float(W - 1)))
                    cy = float(min(max(cy, 0.0), float(H - 1)))
                    
                    # Proyeccion GPS
                    projected = self.projector.pixel_to_gps(
                        cy,
                        cx,
                        image_height=int(H),
                        image_width=int(W),
                        drone_lat=float(dron_lat),
                        drone_lon=float(dron_lon),
                        drone_yaw_deg=float(dron_yaw),
                        drone_pitch_deg=float(dron_pitch),
                        drone_roll_deg=float(dron_roll),
                        alt_agl_m=float(dron_alt_agl),
                        camera_vfov_deg=float(self._camera_vfov_deg),
                        mount_roll_deg=float(self._mount_roll_deg),
                        mount_pitch_deg=float(self._mount_pitch_deg),
                        mount_yaw_deg=float(self._mount_yaw_deg),
                        max_range_m=float(DETECTION_RANGE_M),
                    )
                    if not projected:
                        continue
                    obj_lat, obj_lon, dist = projected

                    # Local ENU coordinates for overlay/debug (meters).
                    obj_x_m = obj_y_m = 0.0
                    if self._origin_lat is not None and self._origin_lon is not None:
                        obj_x_m, obj_y_m = self._enu_xy_m(self._origin_lat, self._origin_lon, float(obj_lat), float(obj_lon))

                    # Estimate object "height" (z, meters up) from bbox top vs base intersection.
                    obj_z_m = 0.0
                    obj_alt_msl_est = float(ground_msl)
                    try:
                        # Base offsets relative to drone, reconstructed from projected lat/lon.
                        R = float(EARTH_RADIUS_M)
                        dlat = math.radians(float(obj_lat) - float(dron_lat))
                        dlon = math.radians(float(obj_lon) - float(dron_lon))
                        base_north_m = dlat * R
                        base_east_m = dlon * R * (math.cos(math.radians(float(dron_lat))) or 1e-6)
                        dist_h = math.hypot(base_north_m, base_east_m)
                        ray_top = self.projector.pixel_to_ray_ned(
                            float(y1),
                            float(cx),
                            image_height=int(H),
                            image_width=int(W),
                            drone_yaw_deg=float(dron_yaw),
                            drone_pitch_deg=float(dron_pitch),
                            drone_roll_deg=float(dron_roll),
                            camera_vfov_deg=float(self._camera_vfov_deg),
                            mount_roll_deg=float(self._mount_roll_deg),
                            mount_pitch_deg=float(self._mount_pitch_deg),
                            mount_yaw_deg=float(self._mount_yaw_deg),
                        )
                        if ray_top is not None:
                            h_est = self._estimate_height_m_from_bbox(
                                ray_top_ned=ray_top,
                                base_north_m=float(base_north_m),
                                base_east_m=float(base_east_m),
                                alt_agl_m=float(dron_alt_agl),
                                dist_h_m=float(dist_h),
                            )
                            if h_est is not None:
                                obj_z_m = float(h_est)
                                obj_alt_msl_est = float(ground_msl) + float(h_est)
                    except Exception:
                        pass
                     
                    label = f"{class_name} {conf:.2f} | {dist:.1f}m z={obj_z_m:.1f}m"
                     
                    # Dibujar en Debug
                    cv2.rectangle(img_bgr, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(img_bgr, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    # Agregar a lista para enviar al Brain (con ID estable por bucket de pixeles)
                    obs_id = self._make_obs_id(cls, cx, cy)
                    prev = frame_dets.get(obs_id)
                    if (prev is None) or (conf > float(prev.get("confidence", 0.0))):
                        frame_dets[obs_id] = {
                            'id': int(obs_id),
                            'lat': float(obj_lat),
                            'lon': float(obj_lon),
                            'alt_msl': float(obj_alt_msl_est),
                            'distance': float(dist),
                            'type': str(class_name),
                            'confidence': float(conf),
                            'source': 'vision',
                            'bbox': {'x1': int(x1), 'y1': int(y1), 'x2': int(x2), 'y2': int(y2)},
                            'cx': float(cx),
                            'cy': float(cy),
                            # Debug-only local frame (ENU meters, z=up/height).
                            'x_m': float(obj_x_m),
                            'y_m': float(obj_y_m),
                            'z_m': float(obj_z_m),
                        }

            # Overlay debug telemetry in the YOLO window (zero-trust: this is the current estimate).
            if self._debug_enabled:
                try:
                    overlay = []
                    overlay.append(f"FPS: {self._fps_ema:.1f}  Dets: {len(frame_dets)}  Tracks: {len(self._tracks)}")
                    overlay.append("XYZ frame: ENU meters (x=East, y=North, z=Up/height)")
                    overlay.append(
                        f"DRONE lat={float(dron_lat):.6f} lon={float(dron_lon):.6f} alt_msl={float(dron_alt_msl):.1f}m agl={float(dron_alt_agl):.1f}m"
                    )
                    overlay.append(
                        f"DRONE RPY deg: roll={float(dron_roll):.1f} pitch={float(dron_pitch):.1f} yaw={float(dron_yaw):.1f}"
                    )
                    overlay.append(f"DRONE XYZ[m]: x={float(drone_x_m):.1f} y={float(drone_y_m):.1f} z={float(drone_z_m):.1f}")
                    if self._origin_lat is None:
                        overlay.append("(waiting for GPS to set local origin...)")

                    dets_sorted = sorted(frame_dets.values(), key=lambda d: float(d.get("distance", 9999.0)))
                    max_n = max(0, int(self._overlay_max_obs))
                    if max_n > 0:
                        dets_sorted = dets_sorted[:max_n]
                    for i, d in enumerate(dets_sorted, 1):
                        overlay.append(
                            f"{i}) {d.get('type')} conf={float(d.get('confidence', 0.0)):.2f} d={float(d.get('distance', 0.0)):.1f}m "
                            f"XYZ=({float(d.get('x_m', 0.0)):.1f},{float(d.get('y_m', 0.0)):.1f},{float(d.get('z_m', 0.0)):.1f}) "
                            f"lat={float(d.get('lat', 0.0)):.6f} lon={float(d.get('lon', 0.0)):.6f} alt~{float(d.get('alt_msl', 0.0)):.1f}m"
                        )

                    x0, y0 = 10, 22
                    dy = 20
                    for idx, text in enumerate(overlay):
                        y = y0 + idx * dy
                        # Outline for readability
                        cv2.putText(img_bgr, text, (x0, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3)
                        cv2.putText(img_bgr, text, (x0, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)
                except Exception:
                    pass

            # 5. Visualizacion (Ventana Debug)
            if self._debug_enabled:
                try:
                    scale = float(self._debug_scale) if math.isfinite(self._debug_scale) and self._debug_scale > 0.0 else 1.0
                    if abs(scale - 1.0) > 1e-6:
                        disp = cv2.resize(img_bgr, (int(W * scale), int(H * scale)), interpolation=cv2.INTER_LINEAR)
                    else:
                        disp = img_bgr
                    cv2.imshow(self._debug_title, disp)
                except Exception:
                    pass
            
            # 6. Enviar al Brain
            seen_ids = set(frame_dets.keys())
            for obs_id, d in frame_dets.items():
                prev_t = self._tracks.get(obs_id)
                if prev_t is None:
                    self._tracks[obs_id] = VisionTrack(
                        obs_id=int(obs_id),
                        class_name=str(d.get('type')),
                        lat=float(d.get('lat')),
                        lon=float(d.get('lon')),
                        dist=float(d.get('distance')),
                        conf=float(d.get('confidence')),
                        bbox=d.get('bbox') or {},
                        cx=float(d.get('cx')),
                        cy=float(d.get('cy')),
                        last_seen_ts=float(now_s),
                        seen_count=1,
                    )
                    continue

                dt = float(now_s) - float(prev_t.last_seen_ts)
                a = self._alpha_from_dt(dt)
                lat = float(prev_t.lat) + a * (float(d.get('lat')) - float(prev_t.lat))
                lon = float(prev_t.lon) + a * (float(d.get('lon')) - float(prev_t.lon))
                dist = float(prev_t.dist) + a * (float(d.get('distance')) - float(prev_t.dist))
                conf_s = max(float(prev_t.conf), float(d.get('confidence')))
                self._tracks[obs_id] = VisionTrack(
                    obs_id=int(obs_id),
                    class_name=str(d.get('type')),
                    lat=float(lat),
                    lon=float(lon),
                    dist=float(dist),
                    conf=float(conf_s),
                    bbox=d.get('bbox') or {},
                    cx=float(d.get('cx')),
                    cy=float(d.get('cy')),
                    last_seen_ts=float(now_s),
                    seen_count=int(prev_t.seen_count) + 1,
                )

            outgoing = []
            hold_s = float(TRACK_HOLD_S)
            for obs_id, t in self._tracks.items():
                if obs_id in seen_ids:
                    ok = True
                else:
                    age_s = float(now_s) - float(t.last_seen_ts)
                    ok = math.isfinite(hold_s) and hold_s > 0.0 and age_s <= hold_s and int(t.seen_count) >= 2
                if not ok:
                    continue

                outgoing.append({
                    'id': int(t.obs_id),
                    'lat': float(t.lat),
                    'lon': float(t.lon),
                    'distance': float(t.dist),
                    'type': str(t.class_name),
                    'confidence': float(t.conf),
                    'source': 'vision',
                    'bbox': t.bbox,
                })

            outgoing.sort(key=lambda o: float(o.get('distance', 9999.0)))
            max_out = int(MAX_OBS_PER_FRAME) if int(MAX_OBS_PER_FRAME) > 0 else len(outgoing)
            outgoing = outgoing[:max_out]
            last_dets = int(len(frame_dets))
            last_send = int(len(outgoing))

            if outgoing:
                log(f"Dets frame={len(frame_dets)} tracks={len(self._tracks)} send={len(outgoing)}")
                try:
                    headers = {}
                    if self._obstacle_token:
                        headers["X-PORCE-Token"] = self._obstacle_token
                    self.session.post(OBSTACLES_URL, json={'obstacles': outgoing}, headers=headers, timeout=0.1)
                except:
                    pass

            # Heartbeat for observability (also useful for E2E harnesses when detections are sparse).
            if math.isfinite(hb_every_s) and hb_every_s > 0.0:
                wall_now = time.time()
                if wall_now - hb_last_ts >= hb_every_s:
                    hb_last_ts = wall_now
                    try:
                        log(
                            f"[HB] fps={self._fps_ema:.1f} frame={frame_count} "
                            f"capture={W}x{H} dets={last_dets} tracks={len(self._tracks)} send={last_send}"
                        )
                    except Exception:
                        pass

            # Control de FPS (0 = as fast as possible). `cv2.waitKey` is required to refresh the debug window.
            if math.isfinite(self._target_fps) and self._target_fps > 0.0:
                min_period = 1.0 / float(self._target_fps)
                elapsed = time.perf_counter() - float(frame_now)
                if elapsed < min_period:
                    time.sleep(min_period - elapsed)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                 
            # log(f"Ciclo Vision: {time.perf_counter() - frame_now:.3f}s")

        cv2.destroyAllWindows()

if __name__ == '__main__':
    VisionSystem().run()
