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
from ultralytics import YOLO
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

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

class GeoProjector:
    """Convierte pixeles 2D a coordenadas GPS usando geometria (pinhole + actitud + suelo plano).

    Zero-trust:
    - No inventa distancia con heuristicas por Y.
    - Si el rayo no intersecta el suelo (p.ej. cielo/horizonte), devuelve None.

    Supuestos/limitaciones:
    - Terreno local plano bajo el dron (necesita AGL).
    - Camara rigidamente montada con offsets fijos.
    - Sin calibracion intrinseca precisa: usa VFOV aproximado.
    """

    @staticmethod
    def _rot_x(deg: float) -> np.ndarray:
        r = math.radians(deg)
        c, s = math.cos(r), math.sin(r)
        return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]], dtype=float)

    @staticmethod
    def _rot_y(deg: float) -> np.ndarray:
        r = math.radians(deg)
        c, s = math.cos(r), math.sin(r)
        return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]], dtype=float)

    @staticmethod
    def _rot_z(deg: float) -> np.ndarray:
        r = math.radians(deg)
        c, s = math.cos(r), math.sin(r)
        return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=float)

    @staticmethod
    def _ned_from_body(yaw_deg: float, pitch_deg: float, roll_deg: float) -> np.ndarray:
        # Body (x forward, y right, z down) -> NED (x north, y east, z down)
        return GeoProjector._rot_z(yaw_deg) @ GeoProjector._rot_y(pitch_deg) @ GeoProjector._rot_x(roll_deg)

    @staticmethod
    def _offset_latlon(drone_lat: float, drone_lon: float, north_m: float, east_m: float) -> Tuple[float, float]:
        # Proyeccion local (suficiente para offsets <~1km)
        R = float(EARTH_RADIUS_M)
        lat_rad = math.radians(float(drone_lat))
        dlat = float(north_m) / R
        denom = R * (math.cos(lat_rad) or 1e-6)
        dlon = float(east_m) / denom
        return float(drone_lat) + math.degrees(dlat), float(drone_lon) + math.degrees(dlon)

    @staticmethod
    def pixel_to_gps(
        px_y: float,
        px_x: float,
        *,
        image_height: int,
        image_width: int,
        drone_lat: float,
        drone_lon: float,
        drone_yaw_deg: float,
        drone_pitch_deg: float,
        drone_roll_deg: float,
        alt_agl_m: float,
        camera_vfov_deg: float,
        mount_roll_deg: float,
        mount_pitch_deg: float,
        mount_yaw_deg: float,
        max_range_m: float,
    ) -> Optional[Tuple[float, float, float]]:
        if image_height <= 0 or image_width <= 0:
            return None

        # Clamp (YOLO puede dar boxes ligeramente fuera del frame)
        u = float(max(0.0, min(float(image_width - 1), float(px_x))))
        v = float(max(0.0, min(float(image_height - 1), float(px_y))))

        h = float(alt_agl_m)
        if not math.isfinite(h) or h < 0.5:
            return None

        vfov_rad = math.radians(float(camera_vfov_deg))
        if not (0.01 < vfov_rad < math.radians(179.0)):
            return None

        # Camera intrinsics from VFOV + aspect ratio
        H = float(image_height)
        W = float(image_width)
        fy = (H / 2.0) / math.tan(vfov_rad / 2.0)
        hfov_rad = 2.0 * math.atan(math.tan(vfov_rad / 2.0) * (W / H))
        fx = (W / 2.0) / math.tan(hfov_rad / 2.0)
        cx = W / 2.0
        cy = H / 2.0

        # OpenCV camera frame: x right, y down, z forward
        x_cam = (u - cx) / fx
        y_cam = (v - cy) / fy
        z_cam = 1.0
        ray_cam = np.array([x_cam, y_cam, z_cam], dtype=float)
        ray_cam = ray_cam / (np.linalg.norm(ray_cam) + 1e-12)

        # camera->body aligned (camera forward == body forward).
        # Body frame (MAVLink): x forward, y right, z down.
        R_body_cam_align = np.array(
            [
                [0.0, 0.0, 1.0],  # body_x = cam_z
                [1.0, 0.0, 0.0],  # body_y = cam_x
                [0.0, 1.0, 0.0],  # body_z = cam_y
            ],
            dtype=float,
        )

        # Mount rotation (default mount_pitch=-30deg => camera tilted down 30deg).
        R_mount = GeoProjector._rot_z(mount_yaw_deg) @ GeoProjector._rot_y(mount_pitch_deg) @ GeoProjector._rot_x(mount_roll_deg)
        ray_body = R_mount @ (R_body_cam_align @ ray_cam)

        # Body -> NED using vehicle attitude.
        R_ned_body = GeoProjector._ned_from_body(float(drone_yaw_deg), float(drone_pitch_deg), float(drone_roll_deg))
        ray_ned = R_ned_body @ ray_body

        # Intersect with ground plane at z = h (NED down positive).
        down = float(ray_ned[2])
        if not math.isfinite(down) or down <= 1e-6:
            return None

        t = h / down
        if not math.isfinite(t) or t <= 0.0:
            return None

        north_m = float(ray_ned[0]) * t
        east_m = float(ray_ned[1]) * t
        dist_h = math.hypot(north_m, east_m)
        if not math.isfinite(dist_h):
            return None

        # Clamp to detection range to avoid near-horizon blowups.
        max_r = float(max_range_m)
        if math.isfinite(max_r) and max_r > 0.0 and dist_h > max_r:
            scale = max_r / (dist_h + 1e-9)
            north_m *= scale
            east_m *= scale
            dist_h = max_r

        obj_lat, obj_lon = GeoProjector._offset_latlon(float(drone_lat), float(drone_lon), north_m, east_m)
        return float(obj_lat), float(obj_lon), float(dist_h)


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

        # Simple temporal stabilizer (reduces bbox/telemetry jitter in the projected lat/lon).
        self._tracks: dict[int, VisionTrack] = {}

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

    def run(self):
        log("Sistema listo. Esperando visualizacion...")
        
        while True:
            start_time = time.time()
            
            # 1. Obtener Telemetria (Necesaria para proyeccion)
            telemetry = self.get_telemetry()
            if not telemetry:
                # Si no hay telemetria, esperamos
                time.sleep(0.5)
                continue
                
            dron_lat = telemetry.get('lat', 0)
            dron_lon = telemetry.get('lon', 0)
            dron_alt_msl = telemetry.get('alt', 0)
            # Prefer AGL if provided by Brain, else use MSL - terrain.
            dron_alt_agl = telemetry.get('rel_alt', None)
            if dron_alt_agl is None:
                dron_alt_agl = float(dron_alt_msl) - float(TERRAIN_ELEVATION_MSL)
            dron_hdg = telemetry.get('heading', 0)
            dron_yaw = telemetry.get('yaw', dron_hdg)
            dron_pitch = telemetry.get('pitch', 0)
            dron_roll = telemetry.get('roll', 0)

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

                if (int(self.monitor.get("width", 0)) != int(self._expect_w)) or (int(self.monitor.get("height", 0)) != int(self._expect_h)):
                    log(f"[WARN] Client area is {self.monitor.get('width')}x{self.monitor.get('height')} (expected {self._expect_w}x{self._expect_h}). Projection assumes the true camera viewport.")

                # Keep on top if requested (helps if the window gets covered).
                self._win32_prepare_window(self._capture_hwnd)

            if not self.monitor:
                time.sleep(0.5)
                continue

            screenshot = np.array(self.sct.grab(self.monitor))
            # Convertir BGRA a BGR
            img_bgr = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            
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
                    
                    label = f"{class_name} {conf:.2f} | {dist:.1f}m"
                    
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
                            'distance': float(dist),
                            'type': str(class_name),
                            'confidence': float(conf),
                            'source': 'vision',
                            'bbox': {'x1': int(x1), 'y1': int(y1), 'x2': int(x2), 'y2': int(y2)},
                            'cx': float(cx),
                            'cy': float(cy),
                        }

            # 5. Visualizacion (Ventana Debug)
            # Reducir tamaño para que quepa en pantalla si es 4K
            display_img = cv2.resize(img_bgr, (1024, 768)) 
            cv2.imshow("YOLO V11 VISION DEBUG", display_img)
            
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

            if outgoing:
                log(f"Dets frame={len(frame_dets)} tracks={len(self._tracks)} send={len(outgoing)}")
                try:
                    headers = {}
                    if self._obstacle_token:
                        headers["X-PORCE-Token"] = self._obstacle_token
                    self.session.post(OBSTACLES_URL, json={'obstacles': outgoing}, headers=headers, timeout=0.1)
                except:
                    pass

            # Control de FPS (aprox 1-2 FPS como pidio el usuario para "cada segundo")
            # cv2.waitKey(1) es necesario para refrescar la ventana
            if cv2.waitKey(500) & 0xFF == ord('q'):
                break
                
            # log(f"Ciclo Vision: {time.time() - start_time:.3f}s")

        cv2.destroyAllWindows()

if __name__ == '__main__':
    VisionSystem().run()
