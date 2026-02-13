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
import cv2
import numpy as np
import mss
from datetime import datetime
import requests
from ultralytics import YOLO
from pathlib import Path
from typing import Optional, Tuple

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

class VisionSystem:
    def __init__(self):
        log("Inicializando sistema de vision YOLOv11...")
        
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
        
        # Definir zona de captura (Pantalla completa por defecto, ajustar segun necesidad)
        # Se asume monitor principal 1920x1080
        monitor_idx = int(os.environ.get("PORCE_CAPTURE_MONITOR", "1"))
        self.monitor = self.sct.monitors[monitor_idx]
        # Optional ROI override (match Unreal camera viewport for correct geometry).
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
        log(f"Zona de captura: {self.monitor}")

    def get_telemetry(self):
        try:
            r = self.session.get(TELEMETRY_URL, timeout=0.5)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return None

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
            
            detected_obstacles = []
            
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
                    
                    # Centro del objeto
                    cx = (x1 + x2) / 2
                    cy = y2  # Base del bbox (pies). Antes era y1+y2 (bug) => fuera de frame.
                    
                    # Proyeccion GPS
                    H, W = img_bgr.shape[:2]
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
                    
                    # Agregar a lista para enviar al Brain
                    # Usamos ID basado en coordenadas para "tracking" simple
                    obs_id = int((obj_lat + obj_lon) * 10000) 
                    detected_obstacles.append({
                        'id': obs_id,
                        'lat': obj_lat,
                        'lon': obj_lon,
                        'distance': dist,
                        'type': class_name,
                        'confidence': conf,
                        'source': 'vision',
                        'bbox': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2},
                    })

            # 5. Visualizacion (Ventana Debug)
            # Reducir tamaño para que quepa en pantalla si es 4K
            display_img = cv2.resize(img_bgr, (1024, 768)) 
            cv2.imshow("YOLO V11 VISION DEBUG", display_img)
            
            # 6. Enviar al Brain
            if detected_obstacles:
                log(f"Detectados {len(detected_obstacles)} objetos. Enviando...")
                try:
                    headers = {}
                    if self._obstacle_token:
                        headers["X-PORCE-Token"] = self._obstacle_token
                    self.session.post(OBSTACLES_URL, json={'obstacles': detected_obstacles}, headers=headers, timeout=0.1)
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
