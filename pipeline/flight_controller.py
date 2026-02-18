#!/usr/bin/env python3
"""
FLIGHT CONTROLLER (The Brain) v1.1 - REALISTIC VISION
-----------------------------------------------------
Actualizado para usar parametros realistas de vision:
- Reaccion desacoplada de seguridad (REACTION_DISTANCE_M).
- Margenes ajustados para evitar "enjaulamiento".
"""

import time, math, threading, sys, logging
from flask import Flask, request, jsonify
from pymavlink import mavutil
from porce_manager import PorcePlanner
from zero_trust_audit import ZeroTrustAudit
from constants import (
    MAVLINK_HUB_HTTP_PORT,
    BRAIN_APP_BIND_HOST,
    SITL_CONN_STRING,
    WAYPOINTS_FILE,
    NAV_SPEED_HORIZONTAL_MS,
    EARTH_RADIUS_M,
    SAFETY_DISTANCE_M,
    CONTROL_LOOP_PERIOD_S,
    CONTROL_LOOP_STALE_TELEMETRY_S,
    CONTROL_LOG_INTERVAL_S,
    DETECTION_RANGE_M,
    REACTION_DISTANCE_M, # NUEVO: Distancia de reaccion explicita
    ARRIVAL_TOLERANCE_M,
    ALTITUDE_TOLERANCE_M,
    HEARTBEAT_TIMEOUT_S,
    OBSTACLE_EXPIRY_S,
    EVASION_REPLAN_MIN_INTERVAL_S,
    EVASION_ROUTE_POINT_REACHED_M,
    LAND_COMPLETED_REL_ALT_M,
    LAND_COMPLETION_GROUNDSPEED_MPS,
    LAND_DISARM_DELAY_S,
    MAVLINK_ALTITUDE_SCALE_M,
    MAVLINK_ATTITUDE_RAD_TO_DEG,
    MAVLINK_ARM_FORCE_CODE,
    MAVLINK_ERROR_RETRY_SLEEP_S,
    MAVLINK_HEADING_SCALE,
    MAVLINK_LOOP_SLEEP_S,
    MAVLINK_RECONNECT_SLEEP_S,
    MAVLINK_RECV_TIMEOUT_S,
    MAVLINK_SPEED_SCALE_CM,
    MAVLINK_UNKNOWN_DISTANCE_M,
    MAVLINK_VOLTAGE_SCALE_MV_TO_V,
    MOCK_TAKEOFF_ALT_M,
    MOCK_CLIMB_RATE_MPS,
    CONTROL_LOOP_STARTUP_DELAY_S,
    CONTROL_GUIDED_RETRY_INTERVAL_S,
    CONTROL_ARM_RETRY_INTERVAL_S,
    CONTROL_DISARM_RETRY_INTERVAL_S,
    CONTROL_EVASION_PROGRESS_LOG_MIN_S,
    CONTROL_NAV_LOG_MIN_S,
    CONTROL_NAV_LOG_INTERVAL_MULTIPLIER,
    TAKEOFF_DEFAULT_ALT_MSL_M,
    MOCK_LAND_DONE_ALT_M,
    MOCK_LOOP_MIN_DT_S,
    MOCK_HOME_LAT,
    MOCK_HOME_LON,
    MOCK_HOME_ALT_M,
    PLANNER_GRID_RADIUS_CELLS,
    PLANNER_MAX_ITERATIONS,
    PLANNER_BOUNDARY_SEARCH_RANGE_CELLS,
    PLANNER_ALLOW_DIAGONAL,
    GEOMETRY_COS_LAT_EPS,
    GEOMETRY_UNIT_EPS,
    GEOMETRY_EPS,
    MAVLINK_INTERVAL_HIGH_US,
    MAVLINK_INTERVAL_MED_US,
    MAVLINK_INTERVAL_LOW_US,
    MAVLINK_SET_POSITION_TARGET_INT_IGNORE_MASK,
    AUDIT_BRAIN_TRAJ_EVERY_S,
    AUDIT_BRAIN_DECISION_EVERY_S,
    AUDIT_BRAIN_MAX_OBS_IN_EVENT,
    OBSTACLE_TOKEN_REQUIRED,
    BRAIN_ENABLE_EVASION,
    BRAIN_MOCK_MAVLINK,
    BRAIN_FORCE_ARM,
    OBSTACLE_TOKEN,
    MOCK_MOVE_MIN_DIST_M,
)

PORCE_ENABLE_EVASION = bool(BRAIN_ENABLE_EVASION)

WP_TOLERANCE_M = ARRIVAL_TOLERANCE_M

logging.basicConfig(level=logging.INFO, format='%(asctime)s [BRAIN] %(message)s', datefmt='%H:%M:%S')
log_werkzeug = logging.getLogger('werkzeug')
log_werkzeug.setLevel(logging.ERROR)

log = logging.getLogger(__name__)

AUDIT_BRAIN_TRAJECTORY_CSV = "trajectory.csv"
AUDIT_BRAIN_TRAJECTORY_HEADERS = [
    "ts",
    "lat",
    "lon",
    "alt_msl",
    "rel_alt",
    "mode",
    "armed",
    "wp_idx",
    "obs_count",
    "nearest_obs_dist_m",
    "evasion_active",
    "evasion_path_len",
    "evasion_path_idx",
]
_audit = ZeroTrustAudit(component="brain")
if _audit.enabled:
    _audit.init_csv(AUDIT_BRAIN_TRAJECTORY_CSV, AUDIT_BRAIN_TRAJECTORY_HEADERS)
    _audit.log_event(
        "brain_config",
        reaction_distance_m=float(REACTION_DISTANCE_M),
        safety_distance_m=float(SAFETY_DISTANCE_M),
        detection_range_m=float(DETECTION_RANGE_M),
        control_loop_period_s=float(CONTROL_LOOP_PERIOD_S),
        control_loop_stale_telemetry_s=float(CONTROL_LOOP_STALE_TELEMETRY_S),
        control_log_interval_s=float(CONTROL_LOG_INTERVAL_S),
        sitl_conn_string=str(SITL_CONN_STRING),
        obstacle_expiry_s=float(OBSTACLE_EXPIRY_S),
        evasion_replan_min_interval_s=float(EVASION_REPLAN_MIN_INTERVAL_S),
        evasion_route_point_reached_m=float(EVASION_ROUTE_POINT_REACHED_M),
        porce_enable_evasion=bool(PORCE_ENABLE_EVASION),
        obstacle_token_required=bool(OBSTACLE_TOKEN_REQUIRED),
        obstacle_token_enabled=bool(OBSTACLE_TOKEN),
        planner_grid_radius_cells=int(PLANNER_GRID_RADIUS_CELLS),
        planner_max_iterations=int(PLANNER_MAX_ITERATIONS),
        planner_boundary_search_range_cells=int(PLANNER_BOUNDARY_SEARCH_RANGE_CELLS),
        traj_every_s=float(AUDIT_BRAIN_TRAJ_EVERY_S),
        decision_every_s=float(AUDIT_BRAIN_DECISION_EVERY_S),
    )
    log.info(
        "[AUDIT] Brain audit enabled: "
        f"traj_every={AUDIT_BRAIN_TRAJ_EVERY_S:.2f}s "
        f"decision_every={AUDIT_BRAIN_DECISION_EVERY_S:.2f}s"
    )

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
    'evasion_last_replan_ts': 0.0,
    'evasion_replans': 0,
    'takeoff_initiated': False,
    # E2E / observability flags
    'saw_evasion': False,
    'mission_state': 'BOOTING',  # BOOTING -> RUNNING -> COMPLETED
    'last_error': None,
    # Zero-trust / observability counters (do not affect flight logic)
    'inject_posts_unauthorized': 0,
    'inject_posts_total': 0
}

state_lock = threading.Lock()
master = None
planner = PorcePlanner(
    grid_radius_cells=PLANNER_GRID_RADIUS_CELLS,
    max_iterations=PLANNER_MAX_ITERATIONS,
    boundary_search_range_cells=PLANNER_BOUNDARY_SEARCH_RANGE_CELLS,
    allow_diagonal=PLANNER_ALLOW_DIAGONAL,
    log_fn=lambda m: log.debug(f"[PORCE-PLANNER] {m}"),
)

# -----------------------------------------------------------------------------
# MOCK MAVLINK BACKEND (for environments where SITL/WSL is unavailable)
# Enable with: set PORCE_MOCK_MAVLINK=1
# -----------------------------------------------------------------------------
_MOCK_MAVLINK = bool(BRAIN_MOCK_MAVLINK)

class _MockMav:
    def __init__(self, parent):
        self._p = parent

    def command_long_send(self, target_system, target_component, command, confirmation,
                          param1, param2, param3, param4, param5, param6, param7):
        # Only a small subset is needed for the Brain control loop.
        self._p._on_command_long(command, param1, param2, param7)

    def param_set_send(self, *args, **kwargs):
        return

    def set_position_target_global_int_send(
        self,
        time_boot_ms,
        target_system,
        target_component,
        frame,
        type_mask,
        lat_int,
        lon_int,
        alt_rel,
        vx,
        vy,
        vz,
        afx,
        afy,
        afz,
        yaw,
        yaw_rate,
    ):
        self._p._on_position_target(lat_int, lon_int, alt_rel)


class MockMaster:
    def __init__(self):
        self.target_system = 1
        self.target_component = 1
        self.mav = _MockMav(self)
        self._lock = threading.Lock()
        self._desired_mode = "STABILIZE"
        self._desired_armed = False
        self._takeoff_alt_rel = None
        self._target_lat_int = None
        self._target_lon_int = None
        self._target_alt_rel = None

    def close(self):
        return

    def set_mode(self, mode):
        with self._lock:
            self._desired_mode = str(mode)

    def arducopter_arm(self):
        with self._lock:
            self._desired_armed = True

    def _on_command_long(self, command, param1, param2, param7):
        # MAV_CMD_NAV_TAKEOFF=22, MAV_CMD_COMPONENT_ARM_DISARM=400
        cmd_nav_takeoff = mavutil.mavlink.MAV_CMD_NAV_TAKEOFF
        cmd_component_arm_disarm = mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM
        try:
            cmd = int(command)
        except Exception:
            return
        with self._lock:
            if cmd == cmd_nav_takeoff:
                try:
                    self._takeoff_alt_rel = float(param7)
                except Exception:
                    self._takeoff_alt_rel = float(MOCK_TAKEOFF_ALT_M)
            elif cmd == cmd_component_arm_disarm:
                try:
                    self._desired_armed = bool(int(param1) == 1)
                except Exception:
                    return

    def _on_position_target(self, lat_int, lon_int, alt_rel):
        with self._lock:
            try:
                self._target_lat_int = int(lat_int)
                self._target_lon_int = int(lon_int)
                self._target_alt_rel = float(alt_rel)
            except Exception:
                return

    def snapshot(self):
        with self._lock:
            return {
                'mode': self._desired_mode,
                'armed': self._desired_armed,
                'takeoff_alt_rel': self._takeoff_alt_rel,
                'target_lat_int': self._target_lat_int,
                'target_lon_int': self._target_lon_int,
                'target_alt_rel': self._target_alt_rel,
            }


def _mock_vehicle_loop():
    # Deterministic vehicle simulation for E2E without a real autopilot.
    with state_lock:
        home = state.get('home') or {}
        cur_lat = float(home.get('lat', MOCK_HOME_LAT) or MOCK_HOME_LAT)
        cur_lon = float(home.get('lon', MOCK_HOME_LON) or MOCK_HOME_LON)
        home_alt = float(home.get('alt', MOCK_HOME_ALT_M) or MOCK_HOME_ALT_M)
        state['telemetry'].update({
            'lat': cur_lat, 'lon': cur_lon, 'alt': home_alt,
            'rel_alt': 0.0,
            'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0,
            'heading': 0.0,
            'armed': False,
            'mode': 'STABILIZE',
            'groundspeed': 0.0,
            'last_update': time.time(),
        })

    cur_rel_alt = 0.0
    cur_mode = 'STABILIZE'
    cur_armed = False
    cur_groundspeed = 0.0

    last_ts = time.time()
    while True:
        now = time.time()
        dt = now - last_ts
        if dt <= 0.0:
            dt = float(MOCK_LOOP_MIN_DT_S)
        last_ts = now

        snap = {}
        if isinstance(master, MockMaster):
            snap = master.snapshot()

        desired_mode = str(snap.get('mode') or cur_mode)
        desired_armed = bool(snap.get('armed', cur_armed))
        takeoff_alt_rel = snap.get('takeoff_alt_rel')
        tgt_lat_int = snap.get('target_lat_int')
        tgt_lon_int = snap.get('target_lon_int')
        tgt_alt_rel = snap.get('target_alt_rel')

        cur_mode = desired_mode
        cur_armed = desired_armed

        # Altitude control (simple rate-limited tracking of commanded rel_alt).
        desired_rel_alt = cur_rel_alt
        if cur_mode == 'LAND':
            desired_rel_alt = 0.0
        elif tgt_alt_rel is not None:
            try:
                desired_rel_alt = float(tgt_alt_rel)
            except Exception:
                pass
        elif takeoff_alt_rel is not None:
            try:
                desired_rel_alt = float(takeoff_alt_rel)
            except Exception:
                desired_rel_alt = float(MOCK_TAKEOFF_ALT_M)

        climb_rate = float(MOCK_CLIMB_RATE_MPS)
        da = desired_rel_alt - cur_rel_alt
        step = climb_rate * dt
        if abs(da) <= step:
            cur_rel_alt = desired_rel_alt
        else:
            cur_rel_alt += step if da > 0.0 else -step

        # Horizontal motion toward the last position target.
        cur_groundspeed = 0.0
        if tgt_lat_int is not None and tgt_lon_int is not None and cur_armed and cur_mode != 'LAND':
            try:
                tgt_lat = float(int(tgt_lat_int)) / 1e7
                tgt_lon = float(int(tgt_lon_int)) / 1e7
                R = float(EARTH_RADIUS_M)
                dlat = math.radians(tgt_lat - cur_lat)
                dlon = math.radians(tgt_lon - cur_lon)
                north = dlat * R
                east = dlon * R * (math.cos(math.radians(cur_lat)) or float(GEOMETRY_COS_LAT_EPS))
                dist = math.hypot(north, east)
                if dist > float(MOCK_MOVE_MIN_DIST_M):
                    spd = float(NAV_SPEED_HORIZONTAL_MS)
                    d = min(dist, spd * dt)
                    s = d / (dist + float(GEOMETRY_EPS))
                    north_s = north * s
                    east_s = east * s
                    cur_lat += math.degrees(north_s / R)
                    cur_lon += math.degrees(east_s / (R * (math.cos(math.radians(cur_lat)) or float(GEOMETRY_COS_LAT_EPS))))
                    cur_groundspeed = d / dt if dt > float(GEOMETRY_UNIT_EPS) else 0.0
            except Exception:
                pass

        # Auto-disarm on touchdown in LAND for determinism.
        if cur_mode == 'LAND' and cur_rel_alt <= float(MOCK_LAND_DONE_ALT_M):
            cur_armed = False
            if isinstance(master, MockMaster):
                with master._lock:
                    master._desired_armed = False

        with state_lock:
            state['telemetry']['lat'] = cur_lat
            state['telemetry']['lon'] = cur_lon
            state['telemetry']['alt'] = home_alt + cur_rel_alt
            state['telemetry']['rel_alt'] = cur_rel_alt
            state['telemetry']['mode'] = cur_mode
            state['telemetry']['armed'] = cur_armed
            state['telemetry']['groundspeed'] = float(cur_groundspeed)
            state['telemetry']['heading'] = 0.0
            state['telemetry']['yaw'] = 0.0
            state['telemetry']['last_update'] = now

        time.sleep(max(0.0, float(MOCK_LOOP_MIN_DT_S)))


def _start_mock_mavlink():
    global master
    master = MockMaster()
    t = threading.Thread(target=_mock_vehicle_loop, daemon=True)
    t.start()
    log.warning('[MOCK] PORCE_MOCK_MAVLINK=1 enabled: running without real SITL/MAVLink.')


def haversine(lat1, lon1, lat2, lon2):
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def nearest_obstacle_info(tel, obstacles):
    nearest_obs = None
    min_dist = float("inf")
    tel_lat = float(tel.get("lat", 0.0) or 0.0)
    tel_lon = float(tel.get("lon", 0.0) or 0.0)
    for o in obstacles:
        d_reported = o.get("distance", float(MAVLINK_UNKNOWN_DISTANCE_M))
        try:
            d_reported = float(d_reported)
        except Exception:
            d_reported = float(MAVLINK_UNKNOWN_DISTANCE_M)
        if not math.isfinite(d_reported):
            d_reported = float(MAVLINK_UNKNOWN_DISTANCE_M)
        d = d_reported
        try:
            if o.get("lat") is not None and o.get("lon") is not None:
                d = haversine(tel_lat, tel_lon, float(o["lat"]), float(o["lon"]))
        except Exception:
            d = d_reported
        if d < min_dist:
            min_dist = float(d)
            nearest_obs = o
    if nearest_obs is None:
        return None, None
    return nearest_obs, float(min_dist)

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
            log.info(f"Mision cargada: {len(wps)} WPs. Home: {wps[0]['lat']:.6f}, {wps[0]['lon']:.6f}")
            return True
    except Exception as e:
        log.error(f"Error cargando mision: {e}")
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
            # rel_alt is used by vision for pixel->ground projection (AGL approx in SIM).
            "rel_alt": float(t.get('rel_alt', 0.0) or 0.0),
            "heading": t['heading'],
            # Prefer attitude yaw (ATTITUDE) if available; fall back to heading.
            "yaw": float(t.get('yaw', t['heading']) or t['heading']),
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

@app.route('/health', methods=['GET'])
def health():
    # Minimal readiness endpoint for test harnesses.
    return jsonify(status="ok")

@app.route('/api/obstacles', methods=['POST'])
def rx_obstacles():
    # Zero-trust: if a token is configured, require it on every obstacle ingestion POST.
    expected_token = str(OBSTACLE_TOKEN)
    if OBSTACLE_TOKEN_REQUIRED and not expected_token:
        if _audit.enabled:
            _audit.log_event("obstacle_ingest_rejected", reason="token_required_but_not_configured")
        return jsonify(error="server_misconfigured_missing_token"), 503
    if expected_token:
        got = request.headers.get('X-PORCE-Token', '')
        if got != expected_token:
            with state_lock:
                state['inject_posts_unauthorized'] = int(state.get('inject_posts_unauthorized', 0)) + 1
            if _audit.enabled:
                _audit.log_event(
                    "obstacle_ingest_rejected",
                    reason="unauthorized_token",
                    remote_addr=str(request.remote_addr or ""),
                )
            return jsonify(error="unauthorized"), 401

    try:
        data = request.get_json(force=True)
        obs_list = data.get('obstacles', [])
        clean_obs = []
        for o in obs_list:
            if not isinstance(o, dict):
                continue
            lat = o.get('lat')
            lon = o.get('lon')
            try:
                lat = None if lat is None else float(lat)
                lon = None if lon is None else float(lon)
            except Exception:
                lat = None
                lon = None
            distance = o.get('distance', float(MAVLINK_UNKNOWN_DISTANCE_M))
            try:
                distance = float(distance)
            except Exception:
                distance = float(MAVLINK_UNKNOWN_DISTANCE_M)

            clean_obs.append({
                'id': o.get('id', 0),
                'distance': distance,
                'lat': lat,
                'lon': lon,
                # Optional metadata (kept for future audit/debug; ignored by planner for now)
                'type': o.get('type'),
                'confidence': o.get('confidence'),
                'source': o.get('source'),
                'bbox': o.get('bbox'),
            })
        with state_lock:
            state['inject_posts_total'] = int(state.get('inject_posts_total', 0)) + 1
            state['obstacles'] = clean_obs
            state['last_obstacle_update'] = time.time()
            total_posts = int(state.get('inject_posts_total', 0))
            unauthorized_posts = int(state.get('inject_posts_unauthorized', 0))
        if _audit.enabled:
            sample_n = min(int(AUDIT_BRAIN_MAX_OBS_IN_EVENT), len(clean_obs))
            _audit.log_event(
                "obstacle_ingest",
                count=int(len(clean_obs)),
                sample=clean_obs[:sample_n],
                sample_truncated=bool(len(clean_obs) > sample_n),
                posts_total=int(total_posts),
                unauthorized_total=int(unauthorized_posts),
                remote_addr=str(request.remote_addr or ""),
            )
        return jsonify(status="ok")
    except Exception as e:
        if _audit.enabled:
            _audit.log_event("obstacle_ingest_error", error=str(e))
        return jsonify(error=str(e)), 400

@app.route('/api/status', methods=['GET'])
def status():
    with state_lock:
        t = state['telemetry']
        telemetry_active = (time.time() - t['last_update']) < HEARTBEAT_TIMEOUT_S
        return jsonify({
            'mode': state['telemetry']['mode'],
            'armed': bool(state['telemetry']['armed']),
            'telemetry_active': bool(telemetry_active),
            'wp_idx': state['current_wp_idx'],
            'evasion': state['evasion_active'],
            'obstacles_count': len(state['obstacles']),
            'saw_evasion': bool(state.get('saw_evasion', False)),
            'mission_state': state.get('mission_state', 'UNKNOWN'),
            'last_error': state.get('last_error'),
            'porce_enable_evasion': bool(PORCE_ENABLE_EVASION),
            'token_required': bool(OBSTACLE_TOKEN_REQUIRED),
            'token_enabled': bool(OBSTACLE_TOKEN),
            'inject_posts_total': int(state.get('inject_posts_total', 0)),
            'inject_posts_unauthorized': int(state.get('inject_posts_unauthorized', 0)),
        })

# --- PIPELINE B: UNREAL SYNC ENDPOINT ---
@app.route('/api/unreal/sync', methods=['GET'])
def unreal_sync():
    """
    Endpoint especifico para que Unreal Engine (VaRest) consulte
    que objetos debe spawnear en el Gemelo Digital.
    """
    with state_lock:
        # Formato simplificado para Blueprint
        return jsonify({
            "timestamp": time.time(),
            "obstacles": state['obstacles']
        })

def mavlink_loop():
    global master
    conn_str = str(SITL_CONN_STRING)
    log.info(f"Conectando MAVLink en {conn_str}...")
    while True:
        try:
            log.info(f"Intentando conectar a {conn_str}...")
            log.debug(f"MAVLink Connection String: {conn_str}") 
            master = mavutil.mavlink_connection(conn_str, source_system=254)
            log.info("MAVLink: Conexion establecida. Esperando Heartbeat...")
            msg = master.wait_heartbeat(timeout=float(MAVLINK_RECV_TIMEOUT_S))
            if msg is None:
                log.warning("Timeout esperando Heartbeat. Reintentando...")
                try: master.close()
                except: pass
                continue
            log.info("MAVLink: Heartbeat recibido. Conectado a ArduPilot!")
            # NOTE: The Brain must not relax autopilot safety checks (e.g. ARMING_CHECK)
            # or mutate vehicle tuning as part of normal operation. Keep the SITL/vehicle
            # configuration in the SITL defaults/params to ensure reproducibility.
            
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
                                                'GPS_RAW_INT', 'SYS_STATUS', 'VFR_HUD',
                                                'STATUSTEXT', 'COMMAND_ACK'], 
                                          blocking=True, timeout=float(MAVLINK_RECV_TIMEOUT_S))
                    if not msg: continue
                    time.sleep(float(MAVLINK_LOOP_SLEEP_S))
                    msg_type = msg.get_type()
                    with state_lock:
                        if msg_type == 'GLOBAL_POSITION_INT':
                            state['telemetry']['lat'] = msg.lat / 1e7
                            state['telemetry']['lon'] = msg.lon / 1e7
                            state['telemetry']['alt'] = msg.alt / float(MAVLINK_ALTITUDE_SCALE_M)
                            # Relative to home position (useful for takeoff checks).
                            state['telemetry']['rel_alt'] = getattr(msg, 'relative_alt', 0) / float(MAVLINK_ALTITUDE_SCALE_M)
                            state['telemetry']['heading'] = msg.hdg / float(MAVLINK_HEADING_SCALE)
                            state['telemetry']['last_update'] = time.time()
                        elif msg_type == 'ATTITUDE':
                            state['telemetry']['roll'] = msg.roll * float(MAVLINK_ATTITUDE_RAD_TO_DEG)
                            state['telemetry']['pitch'] = msg.pitch * float(MAVLINK_ATTITUDE_RAD_TO_DEG)
                            state['telemetry']['yaw'] = msg.yaw * float(MAVLINK_ATTITUDE_RAD_TO_DEG)
                        elif msg_type == 'HEARTBEAT':
                            state['telemetry']['mode'] = mavutil.mode_string_v10(msg)
                            state['telemetry']['armed'] = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                        elif msg_type == 'VFR_HUD':
                            state['telemetry']['groundspeed'] = msg.groundspeed
                            state['telemetry']['airspeed'] = msg.airspeed
                            state['telemetry']['heading'] = msg.heading
                        elif msg_type == 'SYS_STATUS':
                            state['telemetry']['voltage'] = msg.voltage_battery / float(MAVLINK_VOLTAGE_SCALE_MV_TO_V)
                            state['telemetry']['battery_remaining'] = msg.battery_remaining
                        elif msg_type == 'GPS_RAW_INT':
                            state['telemetry']['gps_fix'] = msg.fix_type
                            state['telemetry']['satellites'] = msg.satellites_visible
                        elif msg_type == 'STATUSTEXT':
                            # Surface autopilot prearm/arm errors into logs for debugging.
                            text = getattr(msg, 'text', '')
                            sev = getattr(msg, 'severity', None)
                            state['telemetry']['last_statustext'] = text
                            state['telemetry']['last_statustext_severity'] = sev
                            state['telemetry']['last_statustext_ts'] = time.time()
                            # Log only relevant messages to avoid flooding.
                            if isinstance(text, str) and ("PreArm" in text or "Arm" in text or "EKF" in text or "GPS" in text or "Takeoff" in text or "takeoff" in text):
                                log.warning(f"[STATUSTEXT] {text}")
                        elif msg_type == 'COMMAND_ACK':
                            cmd = getattr(msg, 'command', None)
                            res = getattr(msg, 'result', None)
                            state['telemetry']['last_command_ack'] = {'command': cmd, 'result': res, 'ts': time.time()}

                    # Also log key ACKs outside the lock to avoid blocking.
                    if msg_type == 'COMMAND_ACK':
                        try:
                            cmd = int(getattr(msg, 'command', -1))
                        except Exception:
                            cmd = -1
                        try:
                            res = int(getattr(msg, 'result', -1))
                        except Exception:
                            res = -1

                        cmd_name = None
                        try:
                            cmd_name = mavutil.mavlink.enums['MAV_CMD'][cmd].name  # type: ignore[index]
                        except Exception:
                            cmd_name = f"CMD_{cmd}"

                        res_name = None
                        try:
                            res_name = mavutil.mavlink.enums['MAV_RESULT'][res].name  # type: ignore[index]
                        except Exception:
                            res_name = f"RES_{res}"

                        if cmd in (
                            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                        ) or res != mavutil.mavlink.MAV_RESULT_ACCEPTED:
                            log.info(f"[ACK] {cmd_name}({cmd}) -> {res_name}({res})")
                except Exception as e:
                    log.error(f"Error en loop MAVLink: {e}")
                    time.sleep(float(MAVLINK_ERROR_RETRY_SLEEP_S))
                    break
        except Exception as e:
            log.error(f"Error fatal conectando MAVLink: {e}")
            time.sleep(float(MAVLINK_RECONNECT_SLEEP_S))
        try: master.close()
        except: pass
        time.sleep(float(MAVLINK_ERROR_RETRY_SLEEP_S))

def control_loop():
    time.sleep(float(CONTROL_LOOP_STARTUP_DELAY_S))
    last_arm_attempt_ts = 0.0
    last_guided_attempt_ts = 0.0
    takeoff_cmd_sent = False
    land_start_ts = None
    last_disarm_attempt_ts = 0.0
    last_traj_audit_ts = 0.0
    last_decision_audit_ts = 0.0
    last_status_log_ts = 0.0
    last_takeoff_status_log_ts = 0.0
    last_evasion_status_log_ts = 0.0
    last_nav_status_log_ts = 0.0
    last_evasion_active = False
    while True:
        time.sleep(float(CONTROL_LOOP_PERIOD_S))
        now_loop = time.time()
        with state_lock:
            tel = state['telemetry'].copy()
            obs = list(state['obstacles'])
            obs_ts = state['last_obstacle_update']
            current_idx = state['current_wp_idx']
            wps = state['waypoints']
            home = state['home']
            evasion_active_now = bool(state['evasion_active'])
            evasion_path_len_now = int(len(state['evasion_path']))
            evasion_path_idx_now = int(state['path_index'])
            mission_state_now = str(state.get('mission_state', 'UNKNOWN'))

        nearest_obs = None
        nearest_dist = None
        if (now_loop - float(obs_ts)) < float(OBSTACLE_EXPIRY_S):
            nearest_obs, nearest_dist = nearest_obstacle_info(tel, obs)

        if (now_loop - float(last_status_log_ts)) >= float(CONTROL_LOG_INTERVAL_S):
            last_status_log_ts = now_loop
            lat = tel.get('lat', 0)
            lon = tel.get('lon', 0)
            alt = tel.get('alt', 0)
            rel_alt = tel.get('rel_alt', 0.0)
            mode = tel.get('mode', 'UNK')
            obs_count = len(obs)
            log.info(f"[STATUS] Mode: {mode} | GPS: {lat:.6f}, {lon:.6f} Alt: {alt:.1f}m (rel {rel_alt:.1f}m) | WP: {current_idx} | Obs: {obs_count}")

        if _audit.enabled and (now_loop - last_traj_audit_ts) >= float(AUDIT_BRAIN_TRAJ_EVERY_S):
            last_traj_audit_ts = now_loop
            _audit.append_csv_row(
                AUDIT_BRAIN_TRAJECTORY_CSV,
                AUDIT_BRAIN_TRAJECTORY_HEADERS,
                {
                    "ts": float(now_loop),
                    "lat": float(tel.get("lat", 0.0) or 0.0),
                    "lon": float(tel.get("lon", 0.0) or 0.0),
                    "alt_msl": float(tel.get("alt", 0.0) or 0.0),
                    "rel_alt": float(tel.get("rel_alt", 0.0) or 0.0),
                    "mode": str(tel.get("mode", "UNKNOWN")),
                    "armed": int(bool(tel.get("armed", False))),
                    "wp_idx": int(current_idx),
                    "obs_count": int(len(obs)),
                    "nearest_obs_dist_m": "" if nearest_dist is None else float(nearest_dist),
                    "evasion_active": int(bool(evasion_active_now)),
                    "evasion_path_len": int(evasion_path_len_now),
                    "evasion_path_idx": int(evasion_path_idx_now),
                },
            )

        if (now_loop - float(tel['last_update'])) > float(CONTROL_LOOP_STALE_TELEMETRY_S):
            continue

        # Mark RUNNING on first valid telemetry.
        with state_lock:
            if state.get('mission_state') == 'BOOTING':
                state['mission_state'] = 'RUNNING'

        # --- ARM + TAKEOFF STATE MACHINE (WP1) ---
        if current_idx == 1:
            # Ensure GUIDED before arming.
            if tel['mode'] != 'GUIDED':
                now = time.time()
                if now - last_guided_attempt_ts > float(CONTROL_GUIDED_RETRY_INTERVAL_S):
                    last_guided_attempt_ts = now
                    master.set_mode('GUIDED')
                continue

            if not tel['armed']:
                now = time.time()
                if now - last_arm_attempt_ts > float(CONTROL_ARM_RETRY_INTERVAL_S):
                    last_arm_attempt_ts = now
                    # Optional force-arm for SITL automation.
                    force_arm = bool(BRAIN_FORCE_ARM)
                    if force_arm:
                        master.mav.command_long_send(
                            master.target_system,
                            master.target_component,
                            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                            0,
                            1,      # arm
                            int(MAVLINK_ARM_FORCE_CODE),  # force
                            0, 0, 0, 0, 0
                        )
                        log.warning("[ARM] Force-arm requested (PORCE_FORCE_ARM=1).")
                    else:
                        master.arducopter_arm()
                        log.info("[ARM] Arm requested.")
                continue

            # Armed: command takeoff. If it gets rejected (EKF not ready) or doesn't climb,
            # command it once.
            if not takeoff_cmd_sent:
                home_alt = home['alt'] if home else 0
                takeoff_alt = (wps[1]['alt'] - home_alt) if len(wps) > 1 else float(TAKEOFF_DEFAULT_ALT_MSL_M)
                master.mav.command_long_send(
                    master.target_system,
                    master.target_component,
                    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                    0,
                    0, 0, 0, 0,
                    0, 0,  # take off from current location (avoids GPS/EKF timing issues)
                    float(takeoff_alt),
                )
                log.info(f"[TAKEOFF] Commanded takeoff to {takeoff_alt:.1f}m (rel).")
                takeoff_cmd_sent = True
                with state_lock:
                    state['takeoff_initiated'] = True
                master.mav.param_set_send(
                    master.target_system,
                    master.target_component,
                    b'WPNAV_SPEED',
                    NAV_SPEED_HORIZONTAL_MS * float(MAVLINK_SPEED_SCALE_CM),
                    mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
                )

        if not tel['armed']:
            continue

        if current_idx < len(wps) and tel['mode'] not in ['GUIDED', 'LAND', 'RTL', 'AUTO']:
            log.warning(f"[MODE FIX] Detectado {tel['mode']} durante mision. Forzando GUIDED.")
            master.set_mode('GUIDED')

        with state_lock:
            takeoff_active = state['takeoff_initiated']

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
                if (now_loop - float(last_takeoff_status_log_ts)) >= float(CONTROL_LOG_INTERVAL_S):
                    last_takeoff_status_log_ts = now_loop
                    log.info(f"[TAKEOFF] Esperando altitud de despegue: {target_takeoff_alt_msl:.1f}m (Actual: {tel['alt']:.1f}m)")
                continue

        # --- ALGORITMO PORCE (EVASION) ---
        active_path = []
        path_idx = 0
        decision_reason = "none"
        decision_triggered = False
        decision_route_points = 0
        decision_nearest_type = nearest_obs.get("type") if nearest_obs else None
        decision_replan_blocked = False
        evasion_last_replan_ts = 0.0
        obs_fresh = (now_loop - float(obs_ts)) < float(OBSTACLE_EXPIRY_S)
        nearest_eval = None
        min_dist_eval = None
        with state_lock:
            active_path = state['evasion_path']
            path_idx = state['path_index']
            evasion_last_replan_ts = float(state.get('evasion_last_replan_ts', 0.0))

            if not active_path:
                can_replan_now = True
            else:
                can_replan_now = (now_loop - float(evasion_last_replan_ts)) >= float(EVASION_REPLAN_MIN_INTERVAL_S)

            if obs_fresh:
                nearest_eval, min_dist_eval = nearest_obstacle_info(tel, obs)
                decision_nearest_type = nearest_eval.get("type") if nearest_eval else decision_nearest_type

                if nearest_eval is None:
                    decision_reason = "no_obstacles"
                elif not PORCE_ENABLE_EVASION:
                    decision_reason = "evasion_disabled"
                elif float(min_dist_eval) >= float(REACTION_DISTANCE_M):
                    decision_reason = "distance_above_reaction"
                elif not can_replan_now:
                    decision_reason = "replan_blocked"
                    decision_replan_blocked = True
                else:
                    decision_reason = "trigger_plan_route"
                    decision_triggered = True
                    log.warning(f"[PORCE] Obstaculo detectado a {float(min_dist_eval):.1f}m. Planificando ruta A*...")
                    if len(wps) > 0:
                        target_wp = wps[current_idx] if current_idx < len(wps) else wps[-1]
                    else:
                        target_wp = {'lat': tel['lat'], 'lon': tel['lon']}

                    new_route = planner.plan_route(tel['lat'], tel['lon'], target_wp['lat'], target_wp['lon'], obs)
                    if new_route:
                        state['evasion_path'] = new_route
                        state['evasion_grid_origin'] = {'lat': tel['lat'], 'lon': tel['lon']}
                        state['path_index'] = 0
                        state['evasion_active'] = True
                        state['saw_evasion'] = True
                        state['evasion_last_replan_ts'] = now_loop
                        state['evasion_replans'] = int(state.get('evasion_replans', 0)) + 1
                        active_path = new_route
                        path_idx = 0
                        decision_route_points = int(len(new_route))
                        decision_reason = "route_generated"
                        if _audit.enabled:
                            _audit.log_event(
                                "evasion_route_generated",
                                nearest_distance_m=float(min_dist_eval),
                                nearest_type=str(decision_nearest_type),
                                route_points=int(len(new_route)),
                                wp_idx=int(current_idx),
                                can_replan_now=bool(can_replan_now),
                            )
                        log.info(f"[PORCE] Ruta generada: {len(new_route)} sub-puntos.")
                    else:
                        log.error("[PORCE] A* fallo. Manteniendo curso (Riesgo de colision).")
                        decision_reason = "route_failed"
                        if _audit.enabled:
                            _audit.log_event(
                                "evasion_route_failed",
                                nearest_distance_m=float(min_dist_eval),
                                nearest_type=str(decision_nearest_type),
                                wp_idx=int(current_idx),
                            )
                        state['evasion_last_replan_ts'] = now_loop
            elif active_path:
                decision_reason = "evasion_in_progress"
            else:
                decision_reason = "obstacles_stale_or_empty"

        if _audit.enabled and (now_loop - last_decision_audit_ts) >= float(AUDIT_BRAIN_DECISION_EVERY_S):
            last_decision_audit_ts = now_loop
            sample_n = min(int(AUDIT_BRAIN_MAX_OBS_IN_EVENT), len(obs))
            audit_min_dist = min_dist_eval if min_dist_eval is not None else nearest_dist
            audit_nearest_type = decision_nearest_type if decision_nearest_type is not None else None
            _audit.log_event(
                "decision_snapshot",
                wp_idx=int(current_idx),
                mission_state=str(mission_state_now),
                mode=str(tel.get("mode", "UNKNOWN")),
                armed=bool(tel.get("armed", False)),
                obs_count=int(len(obs)),
                obs_age_s=float(max(0.0, now_loop - float(obs_ts))),
                nearest_distance_m=None if audit_min_dist is None else float(audit_min_dist),
                nearest_type=None if audit_nearest_type is None else str(audit_nearest_type),
                reaction_distance_m=float(REACTION_DISTANCE_M),
                porce_enable_evasion=bool(PORCE_ENABLE_EVASION),
                evasion_active=bool(evasion_active_now),
                decision_reason=str(decision_reason),
                decision_triggered=bool(decision_triggered),
                decision_route_points=int(decision_route_points),
                obs_fresh=bool(obs_fresh),
                replan_blocked=bool(decision_replan_blocked),
                can_replan_now=bool((not active_path) or ((now_loop - float(evasion_last_replan_ts)) >= float(EVASION_REPLAN_MIN_INTERVAL_S))),
                obs_sample=obs[:sample_n],
                obs_sample_truncated=bool(len(obs) > sample_n),
            )

        evasion_flag = bool(active_path)
        if _audit.enabled and (evasion_flag != bool(last_evasion_active)):
            _audit.log_event(
                "evasion_state_change",
                active=bool(evasion_flag),
                wp_idx=int(current_idx),
                nearest_distance_m=None if nearest_dist is None else float(nearest_dist),
                nearest_type=str(decision_nearest_type) if decision_nearest_type is not None else None,
            )
            last_evasion_active = bool(evasion_flag)

        if active_path:
            if path_idx < len(active_path):
                sub_target = active_path[path_idx]
                dist_sub = haversine(tel['lat'], tel['lon'], sub_target['lat'], sub_target['lon'])
                if dist_sub < float(EVASION_ROUTE_POINT_REACHED_M):
                    path_idx += 1
                    with state_lock:
                        state['path_index'] = path_idx
                    if _audit.enabled:
                        _audit.log_event(
                            "evasion_progress",
                            step=int(path_idx),
                            total=int(len(active_path)),
                            dist_to_step_m=float(dist_sub),
                            wp_idx=int(current_idx),
                        )

                if path_idx < len(active_path):
                    next_pt = active_path[path_idx]
                    target_alt_rel = wps[current_idx]['alt'] - (home['alt'] if home else 0)
                    master.mav.set_position_target_global_int_send(
                        0, master.target_system, master.target_component,
                        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                        MAVLINK_SET_POSITION_TARGET_INT_IGNORE_MASK,
                        int(next_pt['lat'] * 1e7), int(next_pt['lon'] * 1e7),
                        target_alt_rel,
                        0, 0, 0, 0, 0, 0, 0, 0
                    )
                    if (now_loop - float(last_evasion_status_log_ts)) >= max(
                        float(CONTROL_EVASION_PROGRESS_LOG_MIN_S),
                        float(CONTROL_LOG_INTERVAL_S),
                    ):
                        last_evasion_status_log_ts = now_loop
                        log.info(f"[PORCE] Navegando Evasion {path_idx+1}/{len(active_path)}")
                    continue
            else:
                log.info("[PORCE] Evasion completada. Retomando mision normal.")
                with state_lock:
                    state['evasion_path'] = []
                    state['path_index'] = 0
                    state['evasion_active'] = False
                    state['evasion_grid_origin'] = None
                if _audit.enabled:
                    _audit.log_event("evasion_completed", wp_idx=int(current_idx))

        # --- NAVEGACION ESTANDAR ---
        if current_idx < len(wps):
            target = wps[current_idx]
            dist = haversine(tel['lat'], tel['lon'], target['lat'], target['lon'])
            if dist < WP_TOLERANCE_M:
                log.info(f"[REACHED] WP{current_idx} alcanzado. Siguiente.")
                with state_lock:
                    state['current_wp_idx'] += 1
                continue
            home_alt = home['alt'] if home else 0
            alt_rel = target['alt'] - home_alt
            master.mav.set_position_target_global_int_send(
                0, master.target_system, master.target_component,
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                MAVLINK_SET_POSITION_TARGET_INT_IGNORE_MASK,
                int(target['lat']*1e7), int(target['lon']*1e7), alt_rel,
                0,0,0, 0,0,0, 0,0)
            if (now_loop - float(last_nav_status_log_ts)) >= max(
                float(CONTROL_NAV_LOG_MIN_S),
                float(CONTROL_LOG_INTERVAL_S) * float(CONTROL_NAV_LOG_INTERVAL_MULTIPLIER),
            ):
                last_nav_status_log_ts = now_loop
                log.info(f"[NAV] Hacia WP{current_idx} (Dist: {dist:.1f}m)")
        else:
            if tel['mode'] != 'LAND':
                log.info("Mision Terminada. Aterrizando (LAND).")
                master.set_mode('LAND')
                land_start_ts = time.time()
            else:
                # Consider the mission complete on touchdown even if ArduPilot stays armed
                # for a while in LAND.
                rel_alt = float(tel.get('rel_alt', float(MAVLINK_UNKNOWN_DISTANCE_M)) or 0.0)
                groundspeed = float(tel.get('groundspeed', float(MAVLINK_UNKNOWN_DISTANCE_M)) or 0.0)
                landed = (rel_alt <= float(LAND_COMPLETED_REL_ALT_M)) and (groundspeed <= float(LAND_COMPLETION_GROUNDSPEED_MPS))
                if landed or (not tel['armed']):
                    with state_lock:
                        if state.get('mission_state') != 'COMPLETED':
                            state['mission_state'] = 'COMPLETED'

                # Ask for a clean disarm if we've touched down but are still armed.
                if landed and tel['armed']:
                    now = time.time()
                    if (
                        land_start_ts
                        and (now - land_start_ts) > float(LAND_DISARM_DELAY_S)
                        and (now - last_disarm_attempt_ts) > float(CONTROL_DISARM_RETRY_INTERVAL_S)
                    ):
                        last_disarm_attempt_ts = now
                        master.mav.command_long_send(
                            master.target_system,
                            master.target_component,
                            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                            0,
                            0,  # disarm
                            0,
                            0, 0, 0, 0, 0
                        )
                        log.info("[DISARM] Landed; disarm requested.")
# --- UI DATA ENDPOINT (OBSERVABILITY) ---
@app.route('/api/ui/data', methods=['GET'])
def ui_data_endpoint():
    """
    Endpoint para herramientas de visualizacion (Sidecar).
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
                'detection_dist': DETECTION_RANGE_M,
                'evasion_replan_min_interval_s': EVASION_REPLAN_MIN_INTERVAL_S,
                'evasion_route_point_reached_m': EVASION_ROUTE_POINT_REACHED_M,
                'land_completed_rel_alt_m': LAND_COMPLETED_REL_ALT_M,
                'land_completion_groundspeed_mps': LAND_COMPLETION_GROUNDSPEED_MPS,
                'evasion_replans': int(state.get('evasion_replans', 0)),
            }
        })

if __name__ == '__main__':
    if not load_mission():
        log.error("No se pudo cargar la mision. Saliendo.")
        sys.exit(1)
    if _MOCK_MAVLINK:
        _start_mock_mavlink()
    else:
        t_mav = threading.Thread(target=mavlink_loop, daemon=True)
        t_mav.start()
    t_ctrl = threading.Thread(target=control_loop, daemon=True)
    t_ctrl.start()
    log.info(f"Iniciando CEREBRO en http://{BRAIN_APP_BIND_HOST}:{MAVLINK_HUB_HTTP_PORT}...")
    app.run(host=BRAIN_APP_BIND_HOST, port=MAVLINK_HUB_HTTP_PORT, use_reloader=False, threaded=True)


