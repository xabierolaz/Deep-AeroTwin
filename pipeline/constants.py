#!/usr/bin/env python3
"""
Constantes globales del sistema PORCE.
Centraliza valores compartidos para evitar duplicados y mantener coherencia.
"""

import os

# ============================================================================
# MODO DEL SISTEMA (PIPELINE SELECTOR)
# ============================================================================
SYSTEM_MODE = os.environ.get('PORCE_SYSTEM_MODE', 'SIMULATION')
print(f"[{os.path.basename(__file__)}] SYSTEM_MODE inicializado como: {SYSTEM_MODE}")

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)

# ============================================================================
# CONSTANTES FISICAS
# ============================================================================
EARTH_RADIUS_M = 6371000

# ============================================================================
# CONFIGURACION DE RED
# ============================================================================
MAVLINK_HUB_HTTP_PORT = 8080
PORCE_HTTP_PORT = 9001
SANDU_HTTP_PORT = 9002
MAVLINK_TCP_PORT = 5761
SITL_TCP_PORT = 5760
SITL_UDP_PORT = 14551

# ============================================================================
# DISTANCIAS CRITICAS (VISION BASED - REALISTIC)
# ============================================================================
# Ajustado para simular visión por computadora (más ruido, menor rango que LIDAR)

SAFETY_DISTANCE_M = 12.0    # "Muro" físico. Margen de seguridad real (12m es estándar industrial).
REACTION_DISTANCE_M = 45.0  # Distancia de reacción. Aquí el A* empieza a calcular.

# ============================================================================
# GRID (Planificacion de Rutas)
# ============================================================================
GRID_CELL_SIZE_M = 10.0

# ============================================================================
# TIMEOUTS HTTP
# ============================================================================
HTTP_TIMEOUT_TELEMETRY_S = 10.0
HTTP_TIMEOUT_COMMAND_S = 10.0
HTTP_TIMEOUT_HEALTH_CHECK_S = 1.0

# ============================================================================
# ARCHIVOS DE CONFIGURACION
# ============================================================================
WAYPOINTS_FILE = 'ejea_default.waypoints'
UNREAL_BRIDGE_JSON_PATH = os.path.join(_current_dir, "logs", "unreal_state.json")

# ============================================================================
# VELOCIDADES DE NAVEGACION (m/s)
# ============================================================================
NAV_SPEED_HORIZONTAL_MS = 8.0
NAV_SPEED_UP_MS = 2.5
NAV_SPEED_DOWN_MS = 1.5

# ============================================================================
# DETECCION DE OBSTACULOS (VISION REALISTA)
# ============================================================================
# Simula un sistema de visión High-End (AI Depth Estimation / Stereo)
# Rango efectivo de medición fiable: ~80m (vs 300m irreal anterior)

DETECTION_RANGE_M = 80.0  

RAW_IMAGE_PATH = os.path.join(_project_root, "Unreal", "Saved", "Screenshots", "WindowsEditor", "raw_capture.png")
TERRAIN_ELEVATION_MSL = 435.0
YOLO_IMG_SIZE = 640
YOLO_CONF_THRESHOLD = 0.3
YOLO_IOU_THRESHOLD = 0.45
YOLO_LETTERBOX_PADDING = 114
YOLO_MIN_AREA = 25
YOLO_MIN_ASPECT_RATIO = 0.1
YOLO_MAX_ASPECT_RATIO = 10.0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FOV_HORIZONTAL = 60.0
CAMERA_FOV_VERTICAL = 45.0
YOLO_SHOW_WINDOW = False
YOLO_SAVE_DETECTIONS_DIR = "detection_results"
YOLO_VISUALIZATION_HIGH_CONF = 0.7
YOLO_VISUALIZATION_MED_CONF = 0.5
SIMULATION_POLLING_INTERVAL_S = 1.0

# ============================================================================
# ESTIMACION DE DISTANCIA
# ============================================================================
USE_DISTANCE_APPROXIMATION = True
TOWER_TYPICAL_HEIGHT_M = 20.0
DISTANCE_CALIBRATION_FACTOR = 1.0

# ============================================================================
# VISUALIZACION
# ============================================================================
VISUALIZATION_PNG_INTERVAL_S = 5.0
VISUALIZATION_OUTPUT_DIR = "logs"
COLOR_PLANNED_CELL = (0.5, 0.7, 1.0)
COLOR_VISITED_CELL = (0.3, 0.8, 0.3)
COLOR_OBSTACLE_CELL = (1.0, 0.3, 0.3)
COLOR_SIMULATED_TOWER = (0.5, 0.5, 0.5)
COLOR_DETECTED_OBSTACLE = (1.0, 0.0, 0.0)
COLOR_DRONE = (0.0, 0.0, 0.0)
COLOR_GRID_LINE = (0.7, 0.7, 0.7)

# ============================================================================
# MAVLINK HUB & CONTROL
# ============================================================================
MAVLINK_DISCONNECT_TIMEOUT_S = 30
MAVLINK_LOG_RATE_LIMIT_S = 5.0
HEARTBEAT_TIMEOUT_S = 3.0
EVASION_VELOCITY_LATERAL_MS = 0.5
OBSTACLE_EXPIRY_S = 1.0  # Caducidad rápida para simular ruido de visión
TELEMETRY_REFRESH_HZ = 10
MAVLINK_INTERVAL_HIGH_US = 100000
MAVLINK_INTERVAL_MED_US = 250000
MAVLINK_INTERVAL_LOW_US = 1000000
ARRIVAL_TOLERANCE_M = 5.5
ALTITUDE_TOLERANCE_M = 1.0