#!/usr/bin/env python3
"""
FLIGHT CONTROLLER (The Brain) v1.1 - REALISTIC VISION
-----------------------------------------------------
Actualizado para usar parámetros realistas de visión:
- Reacción desacoplada de seguridad (REACTION_DISTANCE_M).
- Márgenes ajustados para evitar "enjaulamiento".
"""

import time, math, threading, sys, logging, json
from flask import Flask, request, jsonify
from pymavlink import mavutil
from porce_manager import PorcePlanner
from constants import (
    MAVLINK_HUB_HTTP_PORT,
    SITL_TCP_PORT,
    WAYPOINTS_FILE,
    NAV_SPEED_HORIZONTAL_MS,
    EARTH_RADIUS_M,
    SAFETY_DISTANCE_M,
    DETECTION_RANGE_M,
    REACTION_DISTANCE_M, # NUEVO: Distancia de reaccion explicita
    ARRIVAL_TOLERANCE_M,
    ALTITUDE_TOLERANCE_M,
    HEARTBEAT_TIMEOUT_S,
    OBSTACLE_EXPIRY_S,
    EVASION_VELOCITY_LATERAL_MS,
    MAVLINK_INTERVAL_HIGH_US,
    MAVLINK_INTERVAL_MED_US,
    MAVLINK_INTERVAL_LOW_US
)

print(f"DEBUG: ALTITUDE_TOLERANCE_M is {ALTITUDE_TOLERANCE_M}")

WP_TOLERANCE_M = ARRIVAL_TOLERANCE_M
if 'EVASION_SPEED_MS' not in locals(): EVASION_SPEED_MS = 3.0

logging.basicConfig(level=logging.INFO, format='%(asctime)s [BRAIN] %(message)s', datefmt='%H:%M:%S')
log_werkzeug = logging.getLogger('werkzeug')
log_werkzeug.setLevel(logging.ERROR)

log = logging.getLogger(__name__)

app = Flask(__name__)

# --- ESTADO GLOBAL ---
state = {
    'telemetry': {
        'lat': 0.0, 'lon': 0.0, 'alt': 0.0,
        'roll': 0, 'pitch': 0, 'yaw': 0,
        'heading': 0,
        'armed': False,
        'mode': 'UNKNOWN',
        'last_update': 0
    },
    'home': None,
    'waypoints': [],
    'current_wp_idx': 1,
    'mission_loaded': False,
    'obstacles': [],
    'last_obstacle_update': 0,
    'evasion_active': False,
    'evasion_path': [],
    'evasion_grid_origin': None, # NUEVO: Centro del grid A*
    'path_index': 0,
    'takeoff_initiated': False
}

state_lock = threading.Lock()
master = None
planner = PorcePlanner()

def haversine(lat1, lon1, lat2, lon2):
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def load_mission():
    wps = []
    try:
        with open(WAYPOINTS_FILE, 'r') as f:
            for line in f:
                if line.startswith('QGC') or not line.strip(): continue
                parts = line.split()
                if len(parts) >= 11:
                    wps.append({
                        'seq': int(parts[0]),
                        'lat': float(parts[8]),
                        'lon': float(parts[9]),
                        'alt': float(parts[10])
                    })
        if wps:
            with state_lock:
                state['home'] = wps[0]
                state['waypoints'] = wps
                state['mission_loaded'] = True
            log.info(f"Misión cargada: {len(wps)} WPs. Home: {wps[0]['lat']:.6f}, {wps[0]['lon']:.6f}")
            return True
    except Exception as e:
        log.error(f"Error cargando misión: {e}")
    return False

@app.route('/api/state/latest', methods=['GET'])
def get_telemetry():
    with state_lock:
        t = state['telemetry']
        active = (time.time() - t['last_update']) < HEARTBEAT_TIMEOUT_S
        return jsonify({
            "ts": time.time(),
            "active": active,
            "lat": t['lat'], "lon": t['lon'], "alt": t['alt'],
            "heading": t['heading'], "yaw": t['heading'],
            "roll": t['roll'], "pitch": t['pitch'],
            "armed": t['armed'], "mode": t['mode']
        })

@app.route('/api/states', methods=['GET'])
def get_states_opensky():
    with state_lock:
        t = state['telemetry']
        now = time.time()
        vehicle_data = [
            "ARDU001", "SITL", "Sim", int(now), int(now),
            t['lon'], t['lat'], t['alt'], not t['armed'],
            t.get('groundspeed', 0), t['heading'], 0, None,
            t.get('alt', 0), None, False, 0
        ]
        payload = { "time": int(now), "states": [vehicle_data] if t['last_update'] > 0 else [] }
        return jsonify(payload)

@app.route('/api/obstacles', methods=['POST'])
def rx_obstacles():
    try:
        data = request.get_json(force=True)
        obs_list = data.get('obstacles', [])
        clean_obs = []
        for o in obs_list:
            clean_obs.append({
                'id': o.get('id', 0),
                'distance': float(o.get('distance', 9999)),
                'lat': o.get('lat'), 'lon': o.get('lon')
            })
        with state_lock:
            state['obstacles'] = clean_obs
            state['last_obstacle_update'] = time.time()
        return jsonify(status="ok")
    except Exception as e:
        return jsonify(error=str(e)), 400

@app.route('/api/status', methods=['GET'])
def status():
    with state_lock:
        return jsonify({
            'mode': state['telemetry']['mode'],
            'wp_idx': state['current_wp_idx'],
            'evasion': state['evasion_active'],
            'obstacles_count': len(state['obstacles'])
        })

def mavlink_loop():
    global master
    conn_str = f"tcp:127.0.0.1:{SITL_TCP_PORT}"
    log.info(f"Conectando MAVLink en {conn_str}...")
    while True:
        try:
            log.info(f"Intentando conectar a {conn_str}...")
            log.debug(f"MAVLink Connection String: {conn_str}") 
            master = mavutil.mavlink_connection(conn_str, source_system=254)
            log.info("MAVLink: Conexión establecida. Esperando Heartbeat...")
            msg = master.wait_heartbeat(timeout=5)
            if msg is None:
                log.warning("Timeout esperando Heartbeat. Reintentando...")
                try: master.close()
                except: pass
                continue
            log.info("MAVLink: Heartbeat recibido. Conectado a ArduPilot!")
            
            params_to_set = {
                b'AHRS_EKF_TYPE': (10, mavutil.mavlink.MAV_PARAM_TYPE_INT8),
                b'ARMING_CHECK': (0, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
                b'FRAME_CLASS': (1, mavutil.mavlink.MAV_PARAM_TYPE_INT8),
                b'FRAME_TYPE': (1, mavutil.mavlink.MAV_PARAM_TYPE_INT8),
            }
            for param_id, (val, type_id) in params_to_set.items():
                master.mav.param_set_send(master.target_system, master.target_component,
                                        param_id, val, type_id)
                time.sleep(0.05)
            
            messages_to_stream = [
                (mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, MAVLINK_INTERVAL_HIGH_US),
                (mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE, MAVLINK_INTERVAL_HIGH_US),
                (mavutil.mavlink.MAVLINK_MSG_ID_GPS_RAW_INT, MAVLINK_INTERVAL_MED_US),
                (mavutil.mavlink.MAVLINK_MSG_ID_SYS_STATUS, MAVLINK_INTERVAL_LOW_US),
                (mavutil.mavlink.MAVLINK_MSG_ID_VFR_HUD, MAVLINK_INTERVAL_MED_US),
            ]
            for msg_id, interval in messages_to_stream:
                master.mav.command_long_send(master.target_system, master.target_component,
                                            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 
                                            0, msg_id, interval, 0, 0, 0, 0, 0)

            while True:
                try:
                    msg = master.recv_match(type=['GLOBAL_POSITION_INT', 'ATTITUDE', 'HEARTBEAT', 
                                                'GPS_RAW_INT', 'SYS_STATUS', 'VFR_HUD'], 
                                          blocking=True, timeout=1.0)
                    if not msg: continue
                    time.sleep(0.02)
                    msg_type = msg.get_type()
                    with state_lock:
                        if msg_type == 'GLOBAL_POSITION_INT':
                            state['telemetry']['lat'] = msg.lat / 1e7
                            state['telemetry']['lon'] = msg.lon / 1e7
                            state['telemetry']['alt'] = msg.alt / 1000.0
                            state['telemetry']['heading'] = msg.hdg / 100.0
                            state['telemetry']['last_update'] = time.time()
                        elif msg_type == 'ATTITUDE':
                            state['telemetry']['roll'] = msg.roll * 57.2958
                            state['telemetry']['pitch'] = msg.pitch * 57.2958
                            state['telemetry']['yaw'] = msg.yaw * 57.2958
                        elif msg_type == 'HEARTBEAT':
                            state['telemetry']['mode'] = mavutil.mode_string_v10(msg)
                            state['telemetry']['armed'] = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                        elif msg_type == 'VFR_HUD':
                            state['telemetry']['groundspeed'] = msg.groundspeed
                            state['telemetry']['airspeed'] = msg.airspeed
                            state['telemetry']['heading'] = msg.heading
                        elif msg_type == 'SYS_STATUS':
                            state['telemetry']['voltage'] = msg.voltage_battery / 1000.0
                            state['telemetry']['battery_remaining'] = msg.battery_remaining
                        elif msg_type == 'GPS_RAW_INT':
                            state['telemetry']['gps_fix'] = msg.fix_type
                            state['telemetry']['satellites'] = msg.satellites_visible
                except Exception as e:
                    log.error(f"Error en loop MAVLink: {e}")
                    time.sleep(1.0)
                    break
        except Exception as e:
            log.error(f"Error fatal conectando MAVLink: {e}")
            time.sleep(2)
        try: master.close()
        except: pass
        time.sleep(1)

def control_loop():
    time.sleep(2)
    while True:
        time.sleep(0.1)
        with state_lock:
            tel = state['telemetry'].copy()
            obs = list(state['obstacles'])
            obs_ts = state['last_obstacle_update']
            current_idx = state['current_wp_idx']
            wps = state['waypoints']
            home = state['home']

        if time.time() % 2.0 < 0.15:
            lat = tel.get('lat', 0)
            lon = tel.get('lon', 0)
            alt = tel.get('alt', 0)
            mode = tel.get('mode', 'UNK')
            obs_count = len(obs)
            log.info(f"[STATUS] Mode: {mode} | GPS: {lat:.6f}, {lon:.6f} Alt: {alt:.1f}m | WP: {current_idx} | Obs: {obs_count}")

        if (time.time() - tel['last_update']) > 2.0: continue
            
        if not tel['armed'] and tel['mode'] != 'GUIDED' and current_idx == 1:
             master.set_mode('GUIDED')
             
        if not tel['armed'] and current_idx == 1 and tel['mode'] == 'GUIDED':
            master.arducopter_arm()
            home_alt = home['alt'] if home else 0
            takeoff_alt = (wps[1]['alt'] - home_alt) if len(wps) > 1 else 30.0
            master.mav.command_long_send(master.target_system, master.target_component,
                                         mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, takeoff_alt)
            log.info(f"Iniciando Despegue a {takeoff_alt}m")
            with state_lock: state['takeoff_initiated'] = True
            master.mav.param_set_send(master.target_system, master.target_component, 
                                    b'WPNAV_SPEED', NAV_SPEED_HORIZONTAL_MS*100, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)

        if not tel['armed']: continue

        if current_idx < len(wps) and tel['mode'] not in ['GUIDED', 'LAND', 'RTL', 'AUTO']:
            log.warning(f"[MODE FIX] Detectado {tel['mode']} durante misión. Forzando GUIDED.")
            master.set_mode('GUIDED')

        with state_lock: takeoff_active = state['takeoff_initiated']

        if current_idx == 1 and takeoff_active:
            target_takeoff_alt_msl = wps[1]['alt']
            altitude_diff = abs(tel['alt'] - target_takeoff_alt_msl)
            if altitude_diff < ALTITUDE_TOLERANCE_M:
                log.info(f"[REACHED] WP{current_idx} alcanzado por altitud. Siguiente.")
                with state_lock:
                    state['takeoff_initiated'] = False
                    state['current_wp_idx'] += 1
                continue
            else:
                if time.time() % 2.0 < 0.15:
                    log.info(f"[TAKEOFF] Esperando altitud de despegue: {target_takeoff_alt_msl:.1f}m (Actual: {tel['alt']:.1f}m)")
                continue

        # --- ALGORITMO PORCE (EVASION) ---
        active_path = []
        path_idx = 0
        with state_lock:
            active_path = state['evasion_path']
            path_idx = state['path_index']
            if (time.time() - obs_ts) < OBSTACLE_EXPIRY_S and not active_path:
                nearest_obs = None
                min_dist = float('inf')
                for o in obs:
                    d = o.get('distance', 9999)
                    if d < min_dist: 
                        min_dist = d
                        nearest_obs = o
                
                # --- CAMBIO CLAVE: REACCION_DISTANCE_M ---
                if nearest_obs and min_dist < REACTION_DISTANCE_M:
                    log.warning(f"[PORCE] Obstáculo detectado a {min_dist:.1f}m. Planificando ruta A*...")
                    target_wp = wps[current_idx] if current_idx < len(wps) else wps[-1]
                    new_route = planner.plan_route(tel['lat'], tel['lon'], target_wp['lat'], target_wp['lon'], obs)
                    if new_route:
                        log.info(f"[PORCE] Ruta generada: {len(new_route)} sub-puntos.")
                        state['evasion_path'] = new_route
                        state['evasion_grid_origin'] = {'lat': tel['lat'], 'lon': tel['lon']}
                        state['path_index'] = 0
                        state['evasion_active'] = True
                        active_path = new_route
                    else:
                        log.error("[PORCE] A* falló. Manteniendo curso (Riesgo de colisión).")

        if active_path:
            if path_idx < len(active_path):
                sub_target = active_path[path_idx]
                dist_sub = haversine(tel['lat'], tel['lon'], sub_target['lat'], sub_target['lon'])
                if dist_sub < 3.0:
                    path_idx += 1
                    with state_lock: state['path_index'] = path_idx
                
                if path_idx < len(active_path):
                    next_pt = active_path[path_idx]
                    target_alt_rel = wps[current_idx]['alt'] - (home['alt'] if home else 0)
                    master.mav.set_position_target_global_int_send(
                        0, master.target_system, master.target_component,
                        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                        0b0000111111111000,
                        int(next_pt['lat'] * 1e7), int(next_pt['lon'] * 1e7),
                        target_alt_rel,
                        0, 0, 0, 0, 0, 0, 0, 0)
                    if time.time() % 1.0 < 0.1:
                        log.info(f"[PORCE] Navegando Evasión {path_idx+1}/{len(active_path)}")
                    continue
            else:
                log.info("[PORCE] Evasión completada. Retomando misión normal.")
                with state_lock:
                    state['evasion_path'] = []
                    state['evasion_active'] = False

        # --- NAVEGACION ESTANDAR ---
        if current_idx < len(wps):
            target = wps[current_idx]
            dist = haversine(tel['lat'], tel['lon'], target['lat'], target['lon'])
            if dist < WP_TOLERANCE_M:
                log.info(f"[REACHED] WP{current_idx} alcanzado. Siguiente.")
                with state_lock: state['current_wp_idx'] += 1
                continue
            home_alt = home['alt'] if home else 0
            alt_rel = target['alt'] - home_alt
            master.mav.set_position_target_global_int_send(
                0, master.target_system, master.target_component,
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                0b0000111111111000,
                int(target['lat']*1e7), int(target['lon']*1e7), alt_rel,
                0,0,0, 0,0,0, 0,0)
            if time.time() % 3.0 < 0.1:
                log.info(f"[NAV] Hacia WP{current_idx} (Dist: {dist:.1f}m)")
        else:
            if tel['mode'] != 'LAND':
                log.info("Misión Terminada. Aterrizando (LAND).")
                master.set_mode('LAND')

# --- UI DATA ENDPOINT (OBSERVABILITY) ---
@app.route('/api/ui/data', methods=['GET'])
def ui_data_endpoint():
    """
    Endpoint para herramientas de visualización (Sidecar).
    Expone el estado interno sin bloquear el bucle de control.
    """
    with state_lock:
        return jsonify({
            'telemetry': state['telemetry'],
            'home': state['home'],
            'waypoints': state['waypoints'],
            'obstacles': state['obstacles'],
            'evasion': {
                'active': state['evasion_active'], 
                'path': state['evasion_path'],
                'grid_origin': state['evasion_grid_origin']
            },
            'params': {
                'safety_dist': SAFETY_DISTANCE_M, 
                'detection_dist': DETECTION_RANGE_M
            }
        })

if __name__ == '__main__':
    if not load_mission():
        log.error("No se pudo cargar la misión. Saliendo.")
        sys.exit(1)
    t_mav = threading.Thread(target=mavlink_loop, daemon=True)
    t_mav.start()
    t_ctrl = threading.Thread(target=control_loop, daemon=True)
    t_ctrl.start()
    log.info(f"Iniciando CEREBRO en puerto {MAVLINK_HUB_HTTP_PORT}...")
    app.run(host='0.0.0.0', port=MAVLINK_HUB_HTTP_PORT, use_reloader=False, threaded=True)
