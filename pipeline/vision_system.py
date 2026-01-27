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
TARGET_CLASSES = [0, 1, 19]  # COCO: 0=Person, 1=Bicycle, 19=Cow
MODEL_PATH = "yolo11n.pt"    # Busca en root
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
    """Convierte pixeles 2D a coordenadas GPS 3D"""
    @staticmethod
    def pixel_to_gps(px_y, px_x, drone_lat, drone_lon, drone_alt, drone_heading, drone_pitch):
        # 1. Calcular angulo vertical desde el centro de la camara
        # Pixel Y va de 0 (arriba) a Height (abajo). 
        # Centro es Height/2.
        # Si px_y < center, estamos mirando arriba del eje del dron.
        
        # Grados por pixel
        deg_per_px = CAMERA_FOV_VERTICAL / CAMERA_HEIGHT
        
        # Desviacion vertical desde el centro optico (pitch del dron incluido)
        # Asumimos que camera pitch = drone pitch
        # Un valor positivo de px_offset significa "abajo" en la imagen
        center_y = CAMERA_HEIGHT / 2
        delta_px = px_y - center_y
        delta_angle_deg = delta_px * deg_per_px
        
        # Angulo total respecto al horizonte (Pitch dron - Angulo pixel)
        # Pitch positivo = Morro arriba. Pitch negativo = Morro abajo.
        # Si miro abajo en la imagen (delta_angle > 0), el angulo de depresion aumenta.
        
        # Angulo de depresion total (desde el horizonte hacia abajo)
        # Nota: ArduPilot pitch positivo es morro arriba.
        # Depresion = -(Pitch) + (Angulo Visual Vertical)
        
        # Simplificacion Flat Earth:
        # Distance = Altura_Relativa / tan(Angulo_Depresion)
        
        alt_rel = drone_alt - TERRAIN_ELEVATION_MSL
        if alt_rel < 1.0: alt_rel = 1.0 # Evitar division por cero o alturas negativas
        
        # Estimacion muy burda de distancia basada en tamaño de caja o posicion Y
        # Si está muy abajo en la imagen, está cerca. Si está al centro, está en el horizonte.
        # Mapeamos eje Y [High...Center] a Distancia [Min...Max]
        
        # Factor de correccion empirico para simulacion
        normalized_y = max(0, min(1, (px_y / CAMERA_HEIGHT)))
        if normalized_y < 0.5:
            dist_m = DETECTION_RANGE_M # Horizonte o cielo
        else:
            # Mapeo no lineal: Cuanto mas abajo, mas cerca
            # 0.5 -> 80m
            # 1.0 -> 0m (debajo del dron)
            factor = (1.0 - normalized_y) * 2.0 # 0 a 1
            dist_m = factor * DETECTION_RANGE_M
            
        if dist_m > DETECTION_RANGE_M: dist_m = DETECTION_RANGE_M
        if dist_m < 2.0: dist_m = 2.0

        # 2. Proyectar Lat/Lon
        # Formula de Haversine inversa simplificada o proyeccion plana
        # NewLat = Lat + (Dist * cos(Heading)) / EarthRadius
        R = EARTH_RADIUS_M
        
        # Heading en radianes
        bearing = math.radians(drone_heading)
        
        lat_rad = math.radians(drone_lat)
        lon_rad = math.radians(drone_lon)
        
        new_lat = math.asin(math.sin(lat_rad)*math.cos(dist_m/R) + 
                            math.cos(lat_rad)*math.sin(dist_m/R)*math.cos(bearing))
                            
        new_lon = lon_rad + math.atan2(math.sin(bearing)*math.sin(dist_m/R)*math.cos(lat_rad),
                                       math.cos(dist_m/R)-math.sin(lat_rad)*math.sin(new_lat))
                                       
        return math.degrees(new_lat), math.degrees(new_lon), dist_m

class VisionSystem:
    def __init__(self):
        log("Inicializando sistema de vision YOLOv11...")
        
        # 1. Cargar Modelo
        try:
            self.model = YOLO(MODEL_PATH)
            log(f"Modelo cargado correctamente: {MODEL_PATH}")
            # Warmup
            log("Realizando inferencia de calentamiento (Warmup)...")
            self.model.predict(source=np.zeros((640,640,3), dtype=np.uint8), verbose=False)
        except Exception as e:
            log(f"ERROR CRITICO cargando modelo: {e}")
            sys.exit(1)

        self.projector = GeoProjector()
        self.sct = mss.mss()
        self.session = requests.Session()
        
        # Definir zona de captura (Pantalla completa por defecto, ajustar segun necesidad)
        # Se asume monitor principal 1920x1080
        self.monitor = self.sct.monitors[1] 
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
            dron_alt = telemetry.get('alt', 0)
            dron_hdg = telemetry.get('heading', 0)
            dron_pitch = telemetry.get('pitch', 0)

            # 2. Captura de Pantalla
            screenshot = np.array(self.sct.grab(self.monitor))
            # Convertir BGRA a BGR
            img_bgr = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            
            # Redimensionar para velocidad (opcional, YOLO lo hace auto, pero para visualizacion consistente)
            # img_resized = cv2.resize(img_bgr, (640, 640))
            
            # 3. Inferencia YOLO
            # classes=TARGET_CLASSES filtra person, bicycle, cow
            results = self.model.predict(img_bgr, conf=CONFIDENCE_THRESHOLD, classes=TARGET_CLASSES, verbose=False)
            
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
                    class_name = self.model.names[cls]
                    
                    # Centro del objeto
                    cx = (x1 + x2) / 2
                    cy = y1 + y2  # Usamos la base (pies) para mejor estimacion de distancia
                    
                    # Proyeccion GPS
                    obj_lat, obj_lon, dist = self.projector.pixel_to_gps(
                        cy, cx, dron_lat, dron_lon, dron_alt, dron_hdg, dron_pitch
                    )
                    
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
                        'type': class_name
                    })

            # 5. Visualizacion (Ventana Debug)
            # Reducir tamaño para que quepa en pantalla si es 4K
            display_img = cv2.resize(img_bgr, (1024, 768)) 
            cv2.imshow("YOLO V11 VISION DEBUG", display_img)
            
            # 6. Enviar al Brain
            if detected_obstacles:
                log(f"Detectados {len(detected_obstacles)} objetos. Enviando...")
                try:
                    self.session.post(OBSTACLES_URL, json={'obstacles': detected_obstacles}, timeout=0.1)
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
