#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VISION SYSTEM (The Eyes) v2.3 - FIXED
-------------------------------------
Correcciones:
- SANITIZACIÓN: Elimina espacios en blanco de SYSTEM_MODE (El error invisible).
- DIAGNOSTICO: Mantiene logs de distancia para verificar la corrección.
"""

import os
import time
import math
import sys
from datetime import datetime
import traceback
import requests

# --- CORRECCIÓN CRITICA: LIMPIEZA DE VARIABLE ---
from constants import SYSTEM_MODE
# Eliminar espacios invisibles que rompen la comparación
SYSTEM_MODE = SYSTEM_MODE.strip() 

# --- CONFIGURACION DE SEGURIDAD ---
DISABLE_OPENVINO_IN_SIM = True 

OPENVINO_AVAILABLE = False
if SYSTEM_MODE == 'SIMULATION' and DISABLE_OPENVINO_IN_SIM:
    print(f"[VISION-BOOT] OpenVINO deshabilitado en modo '{SYSTEM_MODE}'.")
else:
    try:
        from openvino.runtime import Core
        OPENVINO_AVAILABLE = True
    except ImportError:
        pass
    except Exception as e:
        print(f"[VISION-BOOT] Error fatal importando OpenVINO: {e}")

from constants import (
    MAVLINK_HUB_HTTP_PORT, DETECTION_RANGE_M, EARTH_RADIUS_M,
    HTTP_TIMEOUT_TELEMETRY_S, HTTP_TIMEOUT_COMMAND_S,
    SIMULATION_POLLING_INTERVAL_S
)

def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    # Forzamos flush para saltar el buffer de tee.py
    print(f"[{timestamp}] [VISION-{SYSTEM_MODE}] {msg}", flush=True)

BRAIN_URL = f"http://127.0.0.1:{MAVLINK_HUB_HTTP_PORT}"
TELEMETRY_URL = f"{BRAIN_URL}/api/state/latest"
OBSTACLES_URL = f"{BRAIN_URL}/api/obstacles"

SIMULATED_OBSTACLES = [
    [0, 42.228091, -1.233701, 487.0], # El obstáculo crítico
    [1, 42.225386, -1.231448, 486.0],
    [2, 42.222318, -1.228736, 479.0],
    [3, 42.220865, -1.227464, 481.0],
    [4, 42.219378, -1.226187, 478.0],
]

class ALMUCalculator:
    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        R = EARTH_RADIUS_M
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

class VisionSystem:
    def __init__(self):
        log(f"Iniciando VISION SYSTEM v2.3. Modo detectado: '{SYSTEM_MODE}'")
        self.almu = ALMUCalculator()
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
        self.session.mount('http://', adapter)
        log("Sesion HTTP iniciada.")

    def run(self):
        last_check = 0
        last_heartbeat = 0
        
        while True:
            try:
                # --- HEARTBEAT ---
                if time.time() - last_heartbeat > 5.0:
                    log("--- HEARTBEAT: Vision System Operativo ---")
                    last_heartbeat = time.time()

                # 1. Telemetría
                try:
                    r = self.session.get(TELEMETRY_URL, timeout=2.0)
                except requests.exceptions.RequestException:
                    time.sleep(1); continue

                if r.status_code != 200: 
                    time.sleep(1); continue
                
                telemetry = r.json()

                # ----------------------------------------------------
                # PIPELINE 1: SIMULATION
                # ----------------------------------------------------
                # AQUI ESTABA EL FALLO: 'SIMULATION ' != 'SIMULATION'
                if SYSTEM_MODE == 'SIMULATION':
                    if time.time() - last_check < SIMULATION_POLLING_INTERVAL_S:
                        time.sleep(0.1); continue
                    last_check = time.time()
                    
                    detected = []
                    dron_lat = telemetry.get('lat')
                    dron_lon = telemetry.get('lon')

                    for obs in SIMULATED_OBSTACLES:
                        dist = self.almu.haversine(dron_lat, dron_lon, obs[1], obs[2])
                        
                        # LOG UNCONDICIONAL DEBUG PARA VERIFICAR MATEMATICA
                        if obs[0] == 0 and dist < 1000.0:
                             # Imprimimos solo si estamos a menos de 1km para no saturar
                             if time.time() % 2.0 < 0.2:
                                 log(f"[DEBUG] Distancia Obs 0: {dist:.1f}m (Umbral: {DETECTION_RANGE_M}m)")

                        if dist <= DETECTION_RANGE_M:
                            detected.append({
                                'id': obs[0], 
                                'lat': obs[1], 
                                'lon': obs[2], 
                                'distance': dist
                            })
                    
                    if detected:
                        log(f"¡ALERTA! Enviando {len(detected)} obstaculos al Brain.")
                        try:
                            self.session.post(OBSTACLES_URL, json={'obstacles': detected}, timeout=2.0)
                        except Exception as e:
                            log(f"Error POST Brain: {e}")

            except Exception as e:
                log(f"CRASH LOOP: {e}")
                traceback.print_exc()
                time.sleep(1)

if __name__ == '__main__':
    sys.stdout.reconfigure(line_buffering=True)
    VisionSystem().run()