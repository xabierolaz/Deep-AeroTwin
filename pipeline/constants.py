#!/usr/bin/env python3
"""
CONSTANTES GLOBALES - SISTEMA DUAL (SIMULACION / REALIDAD)
----------------------------------------------------------
Estructura:
1. SELECTOR DE MODO (Environment Variable)
2. CONSTANTES FISICAS (Inmutables, compartidas)
3. CONFIGURACION DE RED (Inmutable, compartida para compatibilidad)
4. PERFILES DE TUNING (Específicos por modo)
"""

import os

# ============================================================================
# 1. SELECTOR DE MODO (MASTER SWITCH)
# ============================================================================
# Opciones: 'SIMULATION' (Pipeline A) | 'REAL_TWIN' (Pipeline B)
SYSTEM_MODE = os.environ.get('PORCE_SYSTEM_MODE', 'SIMULATION').upper().strip()

print(f"[{os.path.basename(__file__)}] ----------------------------------------")
print(f"[{os.path.basename(__file__)}] INICIANDO CONFIGURACION EN MODO: {SYSTEM_MODE}")
print(f"[{os.path.basename(__file__)}] ----------------------------------------")

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)

# ============================================================================
# 2. CONSTANTES FISICAS Y MATEMATICAS (SHARED CORE)
# ============================================================================
# Estas NO deben cambiar entre modos para mantener la coherencia lógica.
EARTH_RADIUS_M = 6371000
GRID_CELL_SIZE_M = 10.0   # Resolución del A*
SAFETY_DISTANCE_M = 12.0  # Radio "duro" de seguridad física

# ============================================================================
# 3. CONFIGURACION DE RED (SHARED PROTOCOL)
# ============================================================================
# Los puertos se mantienen iguales para que las herramientas de debug sirvan en ambos.
MAVLINK_HUB_HTTP_PORT = 8080  # Brain API
VIZ_RECORDER_PORT = 8080      # Viz se conecta aquí
LOG_SERVER_PORT = 9090
SITL_TCP_PORT = 5760          # Solo relevante en SIM, ignorado en REAL

# Timeouts
HTTP_TIMEOUT_TELEMETRY_S = 10.0
HTTP_TIMEOUT_COMMAND_S = 10.0

# ============================================================================
# 4. PERFILES DE TUNING (MODE SPECIFIC)
# ============================================================================

if SYSTEM_MODE == 'SIMULATION':
    # --- PERFIL A: SIMULACION (Entorno ideal, mss screen capture) ---
    REACTION_DISTANCE_M = 45.0
    DETECTION_RANGE_M = 80.0      # Limitado artificialmente para realismo
    
    # Visión
    VISION_SOURCE = 'SCREEN_CAPTURE' # mss
    YOLO_CONF_THRESHOLD = 0.40
    
    # Navegación
    NAV_SPEED_HORIZONTAL_MS = 8.0
    ARRIVAL_TOLERANCE_M = 5.5     # Tolerancia laxa para SITL
    ALTITUDE_TOLERANCE_M = 1.0

elif SYSTEM_MODE == 'REAL_TWIN':
    # --- PERFIL B: GEMELO DIGITAL (Entorno ruidoso, video real) ---
    REACTION_DISTANCE_M = 60.0    # Más conservador en la realidad
    DETECTION_RANGE_M = 150.0     # Aprovechar al máximo la cámara real
    
    # Visión
    VISION_SOURCE = 'VIDEO_STREAM' # cv2.VideoCapture / RTSP
    YOLO_CONF_THRESHOLD = 0.55    # Más estricto para evitar falsos positivos
    
    # Navegación
    NAV_SPEED_HORIZONTAL_MS = 5.0 # Más lento por seguridad
    ARRIVAL_TOLERANCE_M = 3.0     # Se asume GPS RTK o mejor precisión
    ALTITUDE_TOLERANCE_M = 2.0    # Barómetros reales fluctúan más

else:
    raise ValueError(f"MODO DESCONOCIDO: {SYSTEM_MODE}")

# ============================================================================
# 5. RUTAS Y RESOURCES
# ============================================================================
WAYPOINTS_FILE = 'ejea_default.waypoints'
RAW_IMAGE_PATH = os.path.join(_project_root, "Unreal", "Saved", "Screenshots", "WindowsEditor", "raw_capture.png")

# Parametros derivados de Vision
CAMERA_FOV_VERTICAL = 45.0
CAMERA_HEIGHT = 640
CAMERA_WIDTH = 640
TERRAIN_ELEVATION_MSL = 435.0 # Ajustar esto dinámicamente en B sería ideal

# ============================================================================
# MAVLINK TIMING
# ============================================================================
MAVLINK_INTERVAL_HIGH_US = 100000
MAVLINK_INTERVAL_MED_US = 250000
MAVLINK_INTERVAL_LOW_US = 1000000
HEARTBEAT_TIMEOUT_S = 3.0
OBSTACLE_EXPIRY_S = 1.0
EVASION_VELOCITY_LATERAL_MS = 0.5
