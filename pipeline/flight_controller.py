#!/usr/bin/env python3
"""
FLIGHT CONTROLLER (The Brain) v1.1 - REALISTIC VISION
-----------------------------------------------------
Actualizado para usar parametros realistas de vision:
- Reaccion desacoplada de seguridad (REACTION_DISTANCE_M).
- Margenes ajustados para evitar "enjaulamiento".
"""

import time, math, threading, sys, logging
from typing import Optional, Any
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
    OBS_STATIC_CLASS_NAMES,
    OBS_SOURCE_FILTER_ENABLE,
    OBS_ALLOWED_SOURCES,
    OBS_TRACK_TTL_STATIC_S,
    OBS_TRACK_TTL_DYNAMIC_S,
    OBS_TRACK_ASSOC_STATIC_M,
    OBS_TRACK_ASSOC_DYNAMIC_M,
    OBS_TRACK_MAX,
    EVASION_REPLAN_MIN_INTERVAL_S,
    EVASION_ROUTE_POINT_REACHED_M,
    EVASION_ROUTE_MIN_POINTS,
    EVASION_DYNAMIC_REACTION_ENABLE,
    EVASION_REACTION_BASE_M,
    EVASION_REACTION_SPEED_GAIN_S,
    EVASION_REACTION_MIN_M,
    EVASION_REACTION_MAX_M,
    EVASION_ALLOW_REPLAN_WHEN_ACTIVE,
    EVASION_ACTIVE_REPLAN_DISTANCE_M,
    EVASION_PLANNER_OBS_MAX_DISTANCE_M,
    EVASION_PLANNER_OBS_MAX_COUNT,
    EVASION_FAILSAFE_MIN_DIST_M,
    EVASION_WP_ADVANCE_MIN_OBS_DIST_M,
    EVASION_WP_BLOCK_CORRIDOR_HALF_WIDTH_M,
    EVASION_WP_BLOCK_FORCE_ADVANCE_ENABLE,
    EVASION_WP_BLOCK_MAX_HOLD_S,
    EVASION_FAILSAFE_HOLD_S,
    EVASION_FAILSAFE_ESCALATE_ENABLE,
    EVASION_FAILSAFE_ESCALATE_FAILS,
    EVASION_FAILSAFE_STAGE1_FAILS,
    EVASION_FAILSAFE_STAGE2_FAILS,
    EVASION_FAILSAFE_STAGE3_FAILS,
    EVASION_FAILSAFE_ESCALATE_WINDOW_S,
    EVASION_FAILSAFE_ESCALATE_COOLDOWN_S,
    EVASION_FAILSAFE_LATERAL_OFFSET_M,
    EVASION_FAILSAFE_LATERAL_FORWARD_GAIN,
    EVASION_FAILSAFE_LATERAL_MIN_INTERVAL_S,
    EVASION_FAILSAFE_ESCALATE_ACTION,
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
    UNREAL_TELEMETRY_INGEST_ENABLE,
    UNREAL_TELEMETRY_TOKEN,
    UNREAL_TELEMETRY_TOKEN_REQUIRED,
    UNREAL_TELEMETRY_ACTIVE_TIMEOUT_S,
    UNREAL_TELEMETRY_MAX_LOOKBACK_S,
    UNREAL_TELEMETRY_MAX_FUTURE_S,
    BRAIN_ENABLE_EVASION,
    BRAIN_MOCK_MAVLINK,
    BRAIN_FORCE_ARM,
    OBSTACLE_TOKEN,
    MOCK_MOVE_MIN_DIST_M,
)

PORCE_ENABLE_EVASION = bool(BRAIN_ENABLE_EVASION)
STATIC_OBS_CLASS_KEYS = {
    str(name).strip().lower()
    for name in OBS_STATIC_CLASS_NAMES
    if str(name).strip()
}
ALLOWED_OBS_SOURCE_KEYS = {
    str(name).strip().lower()
    for name in OBS_ALLOWED_SOURCES
    if str(name).strip()
}
if not ALLOWED_OBS_SOURCE_KEYS:
    ALLOWED_OBS_SOURCE_KEYS = {"vision"}

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
AUDIT_BRAIN_UNREAL_TRUTH_CSV = "unreal_truth.csv"
AUDIT_BRAIN_UNREAL_TRUTH_HEADERS = [
    "ts",
    "ue_ts",
    "lat",
    "lon",
    "alt_msl",
    "rel_alt",
    "yaw",
    "pitch",
    "roll",
    "x_m",
    "y_m",
    "z_m",
    "frame",
    "source",
]
_audit = ZeroTrustAudit(component="brain")
if _audit.enabled:
    _audit.init_csv(AUDIT_BRAIN_TRAJECTORY_CSV, AUDIT_BRAIN_TRAJECTORY_HEADERS)
    _audit.init_csv(AUDIT_BRAIN_UNREAL_TRUTH_CSV, AUDIT_BRAIN_UNREAL_TRUTH_HEADERS)
    _audit.log_event(
        "brain_config",
        reaction_distance_m=float(REACTION_DISTANCE_M),
        evasion_dynamic_reaction_enable=bool(EVASION_DYNAMIC_REACTION_ENABLE),
        evasion_reaction_base_m=float(EVASION_REACTION_BASE_M),
        evasion_reaction_speed_gain_s=float(EVASION_REACTION_SPEED_GAIN_S),
        evasion_reaction_min_m=float(EVASION_REACTION_MIN_M),
        evasion_reaction_max_m=float(EVASION_REACTION_MAX_M),
        safety_distance_m=float(SAFETY_DISTANCE_M),
        detection_range_m=float(DETECTION_RANGE_M),
        control_loop_period_s=float(CONTROL_LOOP_PERIOD_S),
        control_loop_stale_telemetry_s=float(CONTROL_LOOP_STALE_TELEMETRY_S),
        control_log_interval_s=float(CONTROL_LOG_INTERVAL_S),
        sitl_conn_string=str(SITL_CONN_STRING),
        obstacle_expiry_s=float(OBSTACLE_EXPIRY_S),
        obs_static_classes=list(STATIC_OBS_CLASS_KEYS),
        obs_source_filter_enable=bool(OBS_SOURCE_FILTER_ENABLE),
        obs_allowed_sources=list(ALLOWED_OBS_SOURCE_KEYS),
        obs_track_ttl_static_s=float(OBS_TRACK_TTL_STATIC_S),
        obs_track_ttl_dynamic_s=float(OBS_TRACK_TTL_DYNAMIC_S),
        obs_track_assoc_static_m=float(OBS_TRACK_ASSOC_STATIC_M),
        obs_track_assoc_dynamic_m=float(OBS_TRACK_ASSOC_DYNAMIC_M),
        obs_track_max=int(OBS_TRACK_MAX),
        evasion_replan_min_interval_s=float(EVASION_REPLAN_MIN_INTERVAL_S),
        evasion_route_point_reached_m=float(EVASION_ROUTE_POINT_REACHED_M),
        evasion_route_min_points=int(EVASION_ROUTE_MIN_POINTS),
        evasion_allow_replan_when_active=bool(EVASION_ALLOW_REPLAN_WHEN_ACTIVE),
        evasion_active_replan_distance_m=float(EVASION_ACTIVE_REPLAN_DISTANCE_M),
        evasion_planner_obs_max_distance_m=float(EVASION_PLANNER_OBS_MAX_DISTANCE_M),
        evasion_planner_obs_max_count=int(EVASION_PLANNER_OBS_MAX_COUNT),
        evasion_failsafe_min_dist_m=float(EVASION_FAILSAFE_MIN_DIST_M),
        evasion_wp_advance_min_obs_dist_m=float(EVASION_WP_ADVANCE_MIN_OBS_DIST_M),
        evasion_wp_block_corridor_half_width_m=float(EVASION_WP_BLOCK_CORRIDOR_HALF_WIDTH_M),
        evasion_wp_block_force_advance_enable=bool(EVASION_WP_BLOCK_FORCE_ADVANCE_ENABLE),
        evasion_wp_block_max_hold_s=float(EVASION_WP_BLOCK_MAX_HOLD_S),
        evasion_failsafe_hold_s=float(EVASION_FAILSAFE_HOLD_S),
        evasion_failsafe_escalate_enable=bool(EVASION_FAILSAFE_ESCALATE_ENABLE),
        evasion_failsafe_escalate_fails=int(EVASION_FAILSAFE_ESCALATE_FAILS),
        evasion_failsafe_stage1_fails=int(EVASION_FAILSAFE_STAGE1_FAILS),
        evasion_failsafe_stage2_fails=int(EVASION_FAILSAFE_STAGE2_FAILS),
        evasion_failsafe_stage3_fails=int(EVASION_FAILSAFE_STAGE3_FAILS),
        evasion_failsafe_escalate_window_s=float(EVASION_FAILSAFE_ESCALATE_WINDOW_S),
        evasion_failsafe_escalate_cooldown_s=float(EVASION_FAILSAFE_ESCALATE_COOLDOWN_S),
        evasion_failsafe_lateral_offset_m=float(EVASION_FAILSAFE_LATERAL_OFFSET_M),
        evasion_failsafe_lateral_forward_gain=float(EVASION_FAILSAFE_LATERAL_FORWARD_GAIN),
        evasion_failsafe_lateral_min_interval_s=float(EVASION_FAILSAFE_LATERAL_MIN_INTERVAL_S),
        evasion_failsafe_escalate_action=str(EVASION_FAILSAFE_ESCALATE_ACTION),
        porce_enable_evasion=bool(PORCE_ENABLE_EVASION),
        obstacle_token_required=bool(OBSTACLE_TOKEN_REQUIRED),
        obstacle_token_enabled=bool(OBSTACLE_TOKEN),
        unreal_telemetry_ingest_enabled=bool(UNREAL_TELEMETRY_INGEST_ENABLE),
        unreal_telemetry_token_required=bool(UNREAL_TELEMETRY_TOKEN_REQUIRED),
        unreal_telemetry_token_enabled=bool(UNREAL_TELEMETRY_TOKEN),
        unreal_telemetry_active_timeout_s=float(UNREAL_TELEMETRY_ACTIVE_TIMEOUT_S),
        unreal_telemetry_max_lookback_s=float(UNREAL_TELEMETRY_MAX_LOOKBACK_S),
        unreal_telemetry_max_future_s=float(UNREAL_TELEMETRY_MAX_FUTURE_S),
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
    'last_obstacle_track_seen': 0.0,
    'obstacle_tracks': {},
    'next_obstacle_track_id': 1,
    'evasion_active': False,
    'evasion_path': [],
    'evasion_grid_origin': None, # NUEVO: Centro del grid A*
    'path_index': 0,
    'evasion_last_replan_ts': 0.0,
    'evasion_replans': 0,
    'failsafe_hold_until_ts': 0.0,
    'failsafe_recent_route_fail_ts': [],
    'failsafe_last_escalate_ts': 0.0,
    'failsafe_last_lateral_replan_ts': 0.0,
    'failsafe_action_active': '',
    'wp_block_wp_idx': -1,
    'wp_block_since_ts': 0.0,
    'takeoff_initiated': False,
    # E2E / observability flags
    'saw_evasion': False,
    'mission_state': 'BOOTING',  # BOOTING -> RUNNING -> COMPLETED
    'last_error': None,
    # Zero-trust / observability counters (do not affect flight logic)
    'inject_posts_unauthorized': 0,
    'inject_posts_total': 0,
    'unreal_truth': {},
    'unreal_truth_last_update': 0.0,
    'unreal_truth_posts_total': 0,
    'unreal_truth_posts_unauthorized': 0,
    'unreal_truth_last_error': '',
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


def _obs_class_key(class_name) -> str:
    return str(class_name or "").strip().lower()


def _obs_is_static(class_name) -> bool:
    return _obs_class_key(class_name) in STATIC_OBS_CLASS_KEYS


def _obs_track_ttl_s(class_name) -> float:
    if _obs_is_static(class_name):
        return float(OBS_TRACK_TTL_STATIC_S)
    return float(OBS_TRACK_TTL_DYNAMIC_S)


def _obs_assoc_distance_m(class_name) -> float:
    if _obs_is_static(class_name):
        return float(OBS_TRACK_ASSOC_STATIC_M)
    return float(OBS_TRACK_ASSOC_DYNAMIC_M)


def _clean_obs_distance(raw_value) -> float:
    return _clean_float(raw_value, float(MAVLINK_UNKNOWN_DISTANCE_M))


def _clean_obs_source_id(raw_value):
    if raw_value is None:
        return None
    try:
        source_id = int(raw_value)
    except Exception:
        return None
    if source_id < 0:
        return None
    return int(source_id)


def _clean_float(raw_value, default_value: float) -> float:
    try:
        value = float(raw_value)
    except Exception:
        value = float(default_value)
    if not math.isfinite(value):
        value = float(default_value)
    return float(value)


def _as_map(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    return {}


def _pick_raw(maps: list[dict], keys: list[str]) -> Any:
    for mp in maps:
        if not isinstance(mp, dict):
            continue
        for key in keys:
            if key in mp:
                value = mp.get(key)
                if value is None:
                    continue
                if isinstance(value, str) and not value.strip():
                    continue
                return value
    return None


def _pick_float_from_maps(maps: list[dict], keys: list[str]) -> Optional[float]:
    raw = _pick_raw(maps, keys)
    if raw is None:
        return None
    try:
        value = float(raw)
    except Exception:
        return None
    if not math.isfinite(value):
        return None
    return float(value)


def _pick_int_from_maps(maps: list[dict], keys: list[str]) -> Optional[int]:
    raw = _pick_raw(maps, keys)
    if raw is None:
        return None
    try:
        return int(float(raw))
    except Exception:
        return None


def _parse_unreal_truth_payload(payload: Any, now_ts: float) -> tuple[Optional[dict], Optional[str]]:
    root = _as_map(payload)
    if not root:
        return None, "payload_not_object"

    telemetry = _as_map(root.get("telemetry"))
    drone = _as_map(root.get("drone"))
    state_map = _as_map(root.get("state"))
    geo = _as_map(root.get("geo"))
    transform = _as_map(root.get("transform"))
    location = _as_map(transform.get("location"))
    rotation = _as_map(transform.get("rotation"))
    pose = _as_map(root.get("pose"))
    pose_location = _as_map(pose.get("location"))
    pose_rotation = _as_map(pose.get("rotation"))

    maps_geo = [root, telemetry, drone, state_map, geo, transform, location, pose, pose_location]
    maps_att = [root, telemetry, drone, state_map, transform, rotation, pose, pose_rotation]
    maps_xyz = [root, telemetry, drone, state_map, transform, location, pose, pose_location]

    lat = _pick_float_from_maps(maps_geo, ["lat", "latitude", "lat_deg", "geo_lat"])
    lon = _pick_float_from_maps(maps_geo, ["lon", "lng", "longitude", "lon_deg", "geo_lon"])
    alt_msl = _pick_float_from_maps(maps_geo, ["alt_msl", "alt", "altitude_msl", "z_msl", "height_msl"])
    rel_alt = _pick_float_from_maps(maps_geo, ["rel_alt", "agl", "alt_agl", "height_agl"])

    yaw = _pick_float_from_maps(maps_att, ["yaw", "heading", "hdg"])
    pitch = _pick_float_from_maps(maps_att, ["pitch"])
    roll = _pick_float_from_maps(maps_att, ["roll"])

    x_m = _pick_float_from_maps(maps_xyz, ["x_m", "x", "ue_x", "east_m"])
    y_m = _pick_float_from_maps(maps_xyz, ["y_m", "y", "ue_y", "north_m"])
    z_m = _pick_float_from_maps(maps_xyz, ["z_m", "z", "ue_z", "up_m"])

    ue_ts = _pick_float_from_maps(
        [root, telemetry, drone, state_map],
        ["ue_ts", "ts_ue", "timestamp_ue", "ue_time_s", "sim_time_s", "time_s", "timestamp"],
    )
    if ue_ts is None:
        ue_ts = float(now_ts)

    frame = _pick_int_from_maps([root, telemetry, drone, state_map], ["frame", "frame_idx", "tick", "seq", "sequence"])
    source_raw = _pick_raw([root, telemetry, drone, state_map], ["source", "origin", "sender"])
    source = str(source_raw).strip() if source_raw is not None else "unreal"
    if not source:
        source = "unreal"

    if lat is None or lon is None:
        return None, "missing_lat_lon"
    if alt_msl is None and rel_alt is None:
        return None, "missing_altitude"

    age_s = float(now_ts) - float(ue_ts)
    if age_s > float(UNREAL_TELEMETRY_MAX_LOOKBACK_S):
        return None, f"ue_timestamp_too_old:{age_s:.3f}s"
    if age_s < -float(UNREAL_TELEMETRY_MAX_FUTURE_S):
        return None, f"ue_timestamp_in_future:{age_s:.3f}s"

    return {
        "ts": float(now_ts),
        "ue_ts": float(ue_ts),
        "lat": float(lat),
        "lon": float(lon),
        "alt_msl": None if alt_msl is None else float(alt_msl),
        "rel_alt": None if rel_alt is None else float(rel_alt),
        "yaw": None if yaw is None else float(yaw),
        "pitch": None if pitch is None else float(pitch),
        "roll": None if roll is None else float(roll),
        "x_m": None if x_m is None else float(x_m),
        "y_m": None if y_m is None else float(y_m),
        "z_m": None if z_m is None else float(z_m),
        "frame": None if frame is None else int(frame),
        "source": str(source),
    }, None


def _obs_distance_from_tel_m(tel_lat: float, tel_lon: float, obs: dict) -> float:
    d = _clean_obs_distance(obs.get("distance", float(MAVLINK_UNKNOWN_DISTANCE_M)))
    try:
        lat = obs.get("lat")
        lon = obs.get("lon")
        if lat is not None and lon is not None:
            d = haversine(float(tel_lat), float(tel_lon), float(lat), float(lon))
    except Exception:
        pass
    if not math.isfinite(d):
        d = float(MAVLINK_UNKNOWN_DISTANCE_M)
    return float(d)


def _obs_track_distance_m(obs: dict, track: dict) -> float:
    try:
        o_lat = obs.get("lat")
        o_lon = obs.get("lon")
        t_lat = track.get("lat")
        t_lon = track.get("lon")
        if o_lat is not None and o_lon is not None and t_lat is not None and t_lon is not None:
            return float(haversine(float(o_lat), float(o_lon), float(t_lat), float(t_lon)))
    except Exception:
        pass
    obs_dist = _clean_obs_distance(obs.get("distance", float(MAVLINK_UNKNOWN_DISTANCE_M)))
    track_dist = _clean_obs_distance(track.get("distance", float(MAVLINK_UNKNOWN_DISTANCE_M)))
    return float(abs(float(obs_dist) - float(track_dist)))


def _blend_float(prev, new, alpha: float):
    try:
        prev_f = float(prev)
        new_f = float(new)
    except Exception:
        return new
    if not math.isfinite(prev_f):
        return new_f
    if not math.isfinite(new_f):
        return prev_f
    a = min(1.0, max(0.0, float(alpha)))
    return float((1.0 - a) * prev_f + a * new_f)


def _evict_stalest_track_locked() -> None:
    tracks = state.get("obstacle_tracks")
    if not isinstance(tracks, dict) or not tracks:
        return
    stale_id = None
    stale_seen = float("inf")
    for track_id, track in tracks.items():
        try:
            seen = float(track.get("last_seen_ts", 0.0))
        except Exception:
            seen = 0.0
        if seen < stale_seen:
            stale_seen = float(seen)
            stale_id = track_id
    if stale_id is not None:
        tracks.pop(stale_id, None)


def _prune_obstacle_tracks_locked(now_ts: float) -> None:
    tracks = state.get("obstacle_tracks")
    if not isinstance(tracks, dict):
        state["obstacle_tracks"] = {}
        return
    dead_ids = []
    for track_id, track in tracks.items():
        class_name = track.get("type")
        ttl_s = _obs_track_ttl_s(class_name)
        try:
            age_s = float(now_ts) - float(track.get("last_seen_ts", 0.0))
        except Exception:
            age_s = float(ttl_s) + 1.0
        if age_s > float(ttl_s):
            dead_ids.append(track_id)
    for track_id in dead_ids:
        tracks.pop(track_id, None)


def _rebuild_active_obstacles_locked(now_ts: float) -> list[dict]:
    _prune_obstacle_tracks_locked(float(now_ts))
    tracks = state.get("obstacle_tracks")
    if not isinstance(tracks, dict):
        state["obstacle_tracks"] = {}
        state["obstacles"] = []
        state["last_obstacle_track_seen"] = 0.0
        return []

    active = []
    max_seen_ts = 0.0
    for track in tracks.values():
        try:
            last_seen = float(track.get("last_seen_ts", 0.0))
        except Exception:
            last_seen = 0.0
        if last_seen > max_seen_ts:
            max_seen_ts = float(last_seen)
        active.append(
            {
                "id": int(track.get("track_id", track.get("id", 0)) or 0),
                "entity_id": str(track.get("entity_id") or f"brain:{int(track.get('track_id', 0) or 0)}"),
                "source_id": _clean_obs_source_id(track.get("source_id")),
                "distance": _clean_obs_distance(track.get("distance", float(MAVLINK_UNKNOWN_DISTANCE_M))),
                "lat": track.get("lat"),
                "lon": track.get("lon"),
                "type": track.get("type"),
                "confidence": track.get("confidence"),
                "source": track.get("source"),
                "bbox": track.get("bbox"),
                "track_age_s": max(0.0, float(now_ts) - float(last_seen)),
                "track_seen_count": int(track.get("seen_count", 1) or 1),
                "track_static": bool(track.get("is_static", False)),
            }
        )

    active.sort(key=lambda o: _clean_obs_distance(o.get("distance", float(MAVLINK_UNKNOWN_DISTANCE_M))))
    state["obstacles"] = active
    state["last_obstacle_track_seen"] = float(max_seen_ts)
    return active


def _ingest_obstacles_locked(obs_list: list[dict], now_ts: float) -> list[dict]:
    tracks = state.get("obstacle_tracks")
    if not isinstance(tracks, dict):
        tracks = {}
        state["obstacle_tracks"] = tracks

    next_track_id = int(state.get("next_obstacle_track_id", 1) or 1)
    max_tracks = max(1, int(OBS_TRACK_MAX))

    for obs in obs_list:
        class_name = str(obs.get("type") or "unknown")
        class_key = _obs_class_key(class_name)
        obs_source = str(obs.get("source") or "").strip().lower()
        obs_source_id = _clean_obs_source_id(obs.get("source_id"))
        obs_entity_id = f"{obs_source}:{obs_source_id}" if obs_source and obs_source_id is not None else None
        assoc_m = float(_obs_assoc_distance_m(class_name))
        ttl_s = float(_obs_track_ttl_s(class_name))
        is_static_class = bool(_obs_is_static(class_name))

        same_source_id_track_id = None
        best_track_id = None
        best_dist_m = float("inf")
        for track_id, track in tracks.items():
            track_class_name = str(track.get("type") or "")
            track_class_key = _obs_class_key(track_class_name)
            track_is_static = bool(track.get("is_static", _obs_is_static(track_class_name)))
            track_ttl_s = float(_obs_track_ttl_s(track_class_name))
            track_source = str(track.get("source") or "").strip().lower()
            track_source_id = _clean_obs_source_id(track.get("source_id"))
            try:
                age_s = float(now_ts) - float(track.get("last_seen_ts", 0.0))
            except Exception:
                age_s = float(track_ttl_s) + 1.0
            if age_s > float(track_ttl_s):
                continue

            if obs_source and obs_source_id is not None:
                if track_source == obs_source and track_source_id == obs_source_id:
                    same_source_id_track_id = track_id
                    break

            if track_class_key != class_key:
                continue

            if obs_source and obs_source_id is not None:
                if track_source == obs_source and track_source_id is not None and track_source_id != obs_source_id:
                    if not is_static_class and not track_is_static:
                        continue
            dist_m = _obs_track_distance_m(obs, track)
            if dist_m < best_dist_m:
                best_dist_m = float(dist_m)
                best_track_id = track_id

        if same_source_id_track_id is not None:
            best_track_id = same_source_id_track_id
            best_dist_m = 0.0

        if best_track_id is not None and best_dist_m <= assoc_m:
            track = tracks.get(best_track_id, {})
            alpha = 0.25 if _obs_is_static(class_name) else 0.65
            prev_type = str(track.get("type") or class_name)
            prev_is_static = bool(track.get("is_static", _obs_is_static(prev_type)))
            merged_type = class_name
            if prev_is_static and not is_static_class and prev_type:
                merged_type = prev_type
            lat_new = obs.get("lat")
            lon_new = obs.get("lon")
            if lat_new is not None and lon_new is not None:
                track["lat"] = _blend_float(track.get("lat"), lat_new, alpha)
                track["lon"] = _blend_float(track.get("lon"), lon_new, alpha)
            track["distance"] = _blend_float(track.get("distance"), obs.get("distance"), alpha)
            track["confidence"] = max(
                _clean_float(track.get("confidence", 0.0), 0.0),
                _clean_float(obs.get("confidence", 0.0), 0.0),
            )
            track["bbox"] = obs.get("bbox")
            track["source"] = obs.get("source")
            if obs_source_id is not None:
                track["source_id"] = int(obs_source_id)
            if obs_entity_id:
                track["entity_id"] = str(obs_entity_id)
            track["type"] = str(merged_type)
            track["last_seen_ts"] = float(now_ts)
            track["seen_count"] = int(track.get("seen_count", 1) or 1) + 1
            track["is_static"] = bool(_obs_is_static(merged_type))
            tracks[best_track_id] = track
            continue

        while len(tracks) >= max_tracks:
            _evict_stalest_track_locked()
        track_id = int(next_track_id)
        next_track_id = int(next_track_id) + 1
        tracks[track_id] = {
            "track_id": int(track_id),
            "lat": obs.get("lat"),
            "lon": obs.get("lon"),
            "distance": _clean_obs_distance(obs.get("distance", float(MAVLINK_UNKNOWN_DISTANCE_M))),
            "type": class_name,
            "confidence": _clean_float(obs.get("confidence", 0.0), 0.0),
            "source": obs.get("source"),
            "source_id": obs_source_id,
            "entity_id": str(obs_entity_id) if obs_entity_id else f"brain:{int(track_id)}",
            "bbox": obs.get("bbox"),
            "first_seen_ts": float(now_ts),
            "last_seen_ts": float(now_ts),
            "seen_count": 1,
            "is_static": bool(_obs_is_static(class_name)),
        }

    state["next_obstacle_track_id"] = int(next_track_id)
    return _rebuild_active_obstacles_locked(float(now_ts))


def nearest_obstacle_info(tel, obstacles):
    nearest_obs = None
    min_dist = float("inf")
    tel_lat = float(tel.get("lat", 0.0) or 0.0)
    tel_lon = float(tel.get("lon", 0.0) or 0.0)
    for o in obstacles:
        d = _obs_distance_from_tel_m(float(tel_lat), float(tel_lon), o)
        if d < min_dist:
            min_dist = float(d)
            nearest_obs = o
    if nearest_obs is None:
        return None, None
    return nearest_obs, float(min_dist)


def planner_obstacle_subset(tel, obstacles):
    max_count = max(1, int(EVASION_PLANNER_OBS_MAX_COUNT))
    max_dist_m = float(EVASION_PLANNER_OBS_MAX_DISTANCE_M)
    tel_lat = float(tel.get("lat", 0.0) or 0.0)
    tel_lon = float(tel.get("lon", 0.0) or 0.0)

    ranked = []
    for o in obstacles:
        dist_m = _obs_distance_from_tel_m(float(tel_lat), float(tel_lon), o)
        if math.isfinite(max_dist_m) and max_dist_m > 0.0 and float(dist_m) > float(max_dist_m):
            continue
        ranked.append((float(dist_m), o))

    ranked.sort(key=lambda item: float(item[0]))
    return [item[1] for item in ranked[:max_count]]


def adaptive_reaction_distance_m(tel) -> tuple[float, float]:
    base_m = float(EVASION_REACTION_BASE_M)
    min_m = float(EVASION_REACTION_MIN_M)
    max_m = float(EVASION_REACTION_MAX_M)
    if not math.isfinite(min_m):
        min_m = float(base_m)
    if not math.isfinite(max_m):
        max_m = float(min_m)
    if max_m < min_m:
        max_m = float(min_m)

    speed_mps = _clean_float(tel.get("groundspeed", tel.get("airspeed", 0.0)), 0.0)
    speed_mps = max(0.0, float(speed_mps))
    if not bool(EVASION_DYNAMIC_REACTION_ENABLE):
        reaction_m = float(base_m)
    else:
        reaction_m = float(base_m) + float(speed_mps) * float(EVASION_REACTION_SPEED_GAIN_S)
    reaction_m = max(float(min_m), min(float(max_m), float(reaction_m)))
    return float(reaction_m), float(speed_mps)


def _failsafe_terminal_action() -> str:
    action = str(EVASION_FAILSAFE_ESCALATE_ACTION).strip().upper()
    if action in {"RTL", "LAND"}:
        return action
    return "LAND"


def _record_route_fail_for_failsafe_locked(now_ts: float) -> int:
    raw = state.get("failsafe_recent_route_fail_ts", [])
    if not isinstance(raw, list):
        raw = []
    window_s = float(EVASION_FAILSAFE_ESCALATE_WINDOW_S)
    kept = []
    for value in raw:
        ts = _clean_float(value, -1.0)
        if ts <= 0.0:
            continue
        if (float(now_ts) - float(ts)) <= float(window_s):
            kept.append(float(ts))
    kept.append(float(now_ts))
    state["failsafe_recent_route_fail_ts"] = kept
    return int(len(kept))


def _failsafe_stage_for_fail_count(fail_count: int) -> str:
    count = int(fail_count)
    if count >= int(EVASION_FAILSAFE_STAGE3_FAILS):
        return str(_failsafe_terminal_action())
    if count >= int(EVASION_FAILSAFE_STAGE2_FAILS):
        return "REPLAN_LATERAL"
    if count >= int(EVASION_FAILSAFE_STAGE1_FAILS):
        return "HOLD"
    return ""


def _activate_terminal_failsafe_locked(
    now_ts: float,
    *,
    action: str,
    fail_count: int,
    wp_idx: int,
    nearest_distance_m: Optional[float],
    nearest_type: Optional[str],
) -> bool:
    terminal_action = str(action).strip().upper()
    if terminal_action not in {"RTL", "LAND"}:
        return False
    last_escalate_ts = _clean_float(state.get("failsafe_last_escalate_ts", 0.0), 0.0)
    if (float(now_ts) - float(last_escalate_ts)) < float(EVASION_FAILSAFE_ESCALATE_COOLDOWN_S):
        return False
    state["failsafe_last_escalate_ts"] = float(now_ts)
    state["failsafe_action_active"] = str(terminal_action)
    state["evasion_path"] = []
    state["path_index"] = 0
    state["evasion_active"] = False
    state["evasion_grid_origin"] = None
    state["failsafe_hold_until_ts"] = 0.0
    state["mission_state"] = "FAILED"
    state["last_error"] = (
        f"failsafe_escalation_{str(terminal_action).lower()}_"
        f"fails={int(fail_count)}_window={float(EVASION_FAILSAFE_ESCALATE_WINDOW_S):.1f}s"
    )

    if _audit.enabled:
        _audit.log_event(
            "failsafe_escalation_triggered",
            action=str(terminal_action),
            fail_count=int(fail_count),
            threshold=int(EVASION_FAILSAFE_STAGE3_FAILS),
            stage1_fails=int(EVASION_FAILSAFE_STAGE1_FAILS),
            stage2_fails=int(EVASION_FAILSAFE_STAGE2_FAILS),
            stage3_fails=int(EVASION_FAILSAFE_STAGE3_FAILS),
            window_s=float(EVASION_FAILSAFE_ESCALATE_WINDOW_S),
            cooldown_s=float(EVASION_FAILSAFE_ESCALATE_COOLDOWN_S),
            nearest_distance_m=None if nearest_distance_m is None else float(nearest_distance_m),
            nearest_type=None if nearest_type is None else str(nearest_type),
            wp_idx=int(wp_idx),
        )
    return True


def _latlon_to_local_ne_m(lat_ref: float, lon_ref: float, lat: float, lon: float) -> tuple[float, float]:
    dlat = math.radians(float(lat) - float(lat_ref))
    dlon = math.radians(float(lon) - float(lon_ref))
    north_m = dlat * float(EARTH_RADIUS_M)
    east_m = dlon * float(EARTH_RADIUS_M) * (math.cos(math.radians(float(lat_ref))) or float(GEOMETRY_COS_LAT_EPS))
    return float(north_m), float(east_m)


def _offset_latlon_ne_m(lat_ref: float, lon_ref: float, north_m: float, east_m: float) -> tuple[float, float]:
    dlat = float(north_m) / float(EARTH_RADIUS_M)
    cos_lat = math.cos(math.radians(float(lat_ref))) or float(GEOMETRY_COS_LAT_EPS)
    dlon = float(east_m) / (float(EARTH_RADIUS_M) * float(cos_lat))
    return float(lat_ref) + math.degrees(float(dlat)), float(lon_ref) + math.degrees(float(dlon))


def waypoint_blocking_obstacle_info(tel: dict, target_wp: dict, obstacles: list[dict]) -> tuple[Optional[dict], Optional[float]]:
    tel_lat = float(tel.get("lat", 0.0) or 0.0)
    tel_lon = float(tel.get("lon", 0.0) or 0.0)
    target_lat = target_wp.get("lat")
    target_lon = target_wp.get("lon")
    if target_lat is None or target_lon is None:
        return None, None

    seg_n, seg_e = _latlon_to_local_ne_m(float(tel_lat), float(tel_lon), float(target_lat), float(target_lon))
    seg_len = math.hypot(float(seg_n), float(seg_e))
    if not math.isfinite(seg_len) or seg_len <= float(GEOMETRY_UNIT_EPS):
        return None, None

    seg_inv = 1.0 / max(float(seg_len), float(GEOMETRY_UNIT_EPS))
    corridor_half_w_m = float(EVASION_WP_BLOCK_CORRIDOR_HALF_WIDTH_M)
    max_obs_dist_m = float(EVASION_WP_ADVANCE_MIN_OBS_DIST_M)
    best_obs = None
    best_dist = float("inf")

    for obs in obstacles:
        lat = obs.get("lat")
        lon = obs.get("lon")
        if lat is None or lon is None:
            continue
        try:
            obs_n, obs_e = _latlon_to_local_ne_m(float(tel_lat), float(tel_lon), float(lat), float(lon))
        except Exception:
            continue

        along_m = ((float(obs_n) * float(seg_n)) + (float(obs_e) * float(seg_e))) * float(seg_inv)
        if along_m < 0.0:
            continue
        if along_m > (float(seg_len) + float(corridor_half_w_m)):
            continue

        cross_m = abs((float(seg_n) * float(obs_e)) - (float(seg_e) * float(obs_n))) * float(seg_inv)
        if cross_m > float(corridor_half_w_m):
            continue

        obs_dist = math.hypot(float(obs_n), float(obs_e))
        if obs_dist > float(max_obs_dist_m):
            continue

        if obs_dist < best_dist:
            best_dist = float(obs_dist)
            best_obs = obs

    if best_obs is None:
        return None, None
    return best_obs, float(best_dist)


def _choose_lateral_sign_order(
    nearest_north_m: Optional[float],
    nearest_east_m: Optional[float],
    lateral_north_unit: float,
    lateral_east_unit: float,
    offset_m: float,
    forward_north_unit: float,
    forward_east_unit: float,
    forward_gain: float,
) -> list[float]:
    signs = [1.0, -1.0]
    if nearest_north_m is None or nearest_east_m is None:
        return signs
    cand = []
    for sign in signs:
        cand_n = (float(forward_north_unit) * forward_gain + float(sign) * float(lateral_north_unit)) * float(offset_m)
        cand_e = (float(forward_east_unit) * forward_gain + float(sign) * float(lateral_east_unit)) * float(offset_m)
        clear_m = math.hypot(float(nearest_north_m) - float(cand_n), float(nearest_east_m) - float(cand_e))
        cand.append((float(clear_m), float(sign)))
    cand.sort(reverse=True)
    return [float(item[1]) for item in cand]


def build_lateral_replan_route(
    tel: dict,
    target_wp: dict,
    obstacles: list[dict],
    nearest_obs: Optional[dict],
) -> tuple[Optional[list[dict]], dict]:
    tel_lat = float(tel.get("lat", 0.0) or 0.0)
    tel_lon = float(tel.get("lon", 0.0) or 0.0)
    target_lat = target_wp.get("lat", tel_lat)
    target_lon = target_wp.get("lon", tel_lon)

    forward_n, forward_e = _latlon_to_local_ne_m(float(tel_lat), float(tel_lon), float(target_lat), float(target_lon))
    forward_norm = math.hypot(float(forward_n), float(forward_e))

    nearest_n = None
    nearest_e = None
    if nearest_obs is not None and nearest_obs.get("lat") is not None and nearest_obs.get("lon") is not None:
        try:
            nearest_n, nearest_e = _latlon_to_local_ne_m(
                float(tel_lat),
                float(tel_lon),
                float(nearest_obs.get("lat")),
                float(nearest_obs.get("lon")),
            )
        except Exception:
            nearest_n = None
            nearest_e = None

    if not math.isfinite(forward_norm) or forward_norm <= float(GEOMETRY_UNIT_EPS):
        if nearest_n is None or nearest_e is None:
            return None, {"reason": "no_direction_vector"}
        forward_n = -float(nearest_n)
        forward_e = -float(nearest_e)
        forward_norm = math.hypot(float(forward_n), float(forward_e))
        if not math.isfinite(forward_norm) or forward_norm <= float(GEOMETRY_UNIT_EPS):
            return None, {"reason": "degenerate_direction_vector"}

    forward_n_unit = float(forward_n) / float(forward_norm)
    forward_e_unit = float(forward_e) / float(forward_norm)
    lateral_n_unit = -float(forward_e_unit)
    lateral_e_unit = float(forward_n_unit)
    offset_m = float(EVASION_FAILSAFE_LATERAL_OFFSET_M)
    forward_gain = max(0.0, float(EVASION_FAILSAFE_LATERAL_FORWARD_GAIN))
    min_points = max(1, int(EVASION_ROUTE_MIN_POINTS))
    planner_obs = planner_obstacle_subset(tel, obstacles)
    planner_obs_count = int(len(planner_obs))

    signs = _choose_lateral_sign_order(
        nearest_north_m=None if nearest_n is None else float(nearest_n),
        nearest_east_m=None if nearest_e is None else float(nearest_e),
        lateral_north_unit=float(lateral_n_unit),
        lateral_east_unit=float(lateral_e_unit),
        offset_m=float(offset_m),
        forward_north_unit=float(forward_n_unit),
        forward_east_unit=float(forward_e_unit),
        forward_gain=float(forward_gain),
    )
    for sign in signs:
        cand_n = (float(forward_n_unit) * float(forward_gain) + float(sign) * float(lateral_n_unit)) * float(offset_m)
        cand_e = (float(forward_e_unit) * float(forward_gain) + float(sign) * float(lateral_e_unit)) * float(offset_m)
        cand_lat, cand_lon = _offset_latlon_ne_m(float(tel_lat), float(tel_lon), float(cand_n), float(cand_e))
        route = planner.plan_route(
            float(tel_lat),
            float(tel_lon),
            float(cand_lat),
            float(cand_lon),
            planner_obs,
        )
        route_len = 0 if route is None else int(len(route))
        if route and int(route_len) >= int(min_points):
            return route, {
                "planner_obs_count": int(planner_obs_count),
                "route_points": int(route_len),
                "sign": float(sign),
                "target_lat": float(cand_lat),
                "target_lon": float(cand_lon),
            }

    return None, {
        "reason": "lateral_route_failed",
        "planner_obs_count": int(planner_obs_count),
    }

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


def _merged_telemetry_for_vision_locked(now_ts: float) -> tuple[dict, bool, float]:
    t = state["telemetry"]
    merged = {
        "lat": float(t.get("lat", 0.0) or 0.0),
        "lon": float(t.get("lon", 0.0) or 0.0),
        "alt": float(t.get("alt", 0.0) or 0.0),
        "rel_alt": float(t.get("rel_alt", 0.0) or 0.0),
        "heading": float(t.get("heading", 0.0) or 0.0),
        "yaw": float(t.get("yaw", t.get("heading", 0.0)) or t.get("heading", 0.0) or 0.0),
        "pitch": float(t.get("pitch", 0.0) or 0.0),
        "roll": float(t.get("roll", 0.0) or 0.0),
        "armed": bool(t.get("armed", False)),
        "mode": str(t.get("mode", "UNKNOWN")),
        "last_update": float(t.get("last_update", 0.0) or 0.0),
    }

    if not bool(UNREAL_TELEMETRY_INGEST_ENABLE):
        return merged, False, float("inf")

    unreal_last_update = _clean_float(state.get("unreal_truth_last_update", 0.0), 0.0)
    unreal_age_s = float("inf")
    use_unreal_truth = False
    if unreal_last_update > 0.0:
        unreal_age_s = float(now_ts) - float(unreal_last_update)
    if (
        unreal_last_update > 0.0
        and math.isfinite(unreal_age_s)
        and unreal_age_s <= float(UNREAL_TELEMETRY_ACTIVE_TIMEOUT_S)
    ):
        truth = state.get("unreal_truth", {})
        if isinstance(truth, dict):
            lat = truth.get("lat")
            lon = truth.get("lon")
            try:
                lat_f = float(lat)
                lon_f = float(lon)
                if math.isfinite(lat_f) and math.isfinite(lon_f):
                    use_unreal_truth = True
                    merged["lat"] = float(lat_f)
                    merged["lon"] = float(lon_f)
            except Exception:
                use_unreal_truth = False
        if use_unreal_truth:
            truth = state.get("unreal_truth", {})
            alt_truth = truth.get("alt_msl", None)
            rel_alt_truth = truth.get("rel_alt", None)
            yaw_truth = truth.get("yaw", None)
            pitch_truth = truth.get("pitch", None)
            roll_truth = truth.get("roll", None)

            if alt_truth is not None:
                merged["alt"] = _clean_float(alt_truth, float(merged["alt"]))
            if rel_alt_truth is not None:
                merged["rel_alt"] = _clean_float(rel_alt_truth, float(merged["rel_alt"]))
            if yaw_truth is not None:
                merged["yaw"] = _clean_float(yaw_truth, float(merged["yaw"]))
                merged["heading"] = float(merged["yaw"])
            if pitch_truth is not None:
                merged["pitch"] = _clean_float(pitch_truth, float(merged["pitch"]))
            if roll_truth is not None:
                merged["roll"] = _clean_float(roll_truth, float(merged["roll"]))

    return merged, bool(use_unreal_truth), float(unreal_age_s)


@app.route('/api/state/latest', methods=['GET'])
def get_telemetry():
    with state_lock:
        now_ts = float(time.time())
        t = state['telemetry']
        active = (now_ts - float(t.get('last_update', 0.0) or 0.0)) < HEARTBEAT_TIMEOUT_S
        merged, use_unreal_truth, unreal_age_s = _merged_telemetry_for_vision_locked(now_ts)
        return jsonify({
            "ts": now_ts,
            "active": bool(active),
            "lat": float(merged["lat"]),
            "lon": float(merged["lon"]),
            "alt": float(merged["alt"]),
            # rel_alt is used by vision for pixel->ground projection (AGL approx in SIM).
            "rel_alt": float(merged["rel_alt"]),
            "heading": float(merged["heading"]),
            # Prefer attitude yaw (ATTITUDE) if available; fall back to heading.
            "yaw": float(merged["yaw"]),
            "roll": float(merged["roll"]),
            "pitch": float(merged["pitch"]),
            "armed": bool(merged["armed"]),
            "mode": str(merged["mode"]),
            "telemetry_source": "unreal_truth" if bool(use_unreal_truth) else "mavlink",
            "unreal_truth_active": bool(use_unreal_truth),
            "unreal_truth_age_s": None if not math.isfinite(unreal_age_s) else float(unreal_age_s),
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
        rejected_by_source = 0
        for o in obs_list:
            if not isinstance(o, dict):
                continue
            source_raw = str(o.get('source', '') or '').strip().lower()
            if bool(OBS_SOURCE_FILTER_ENABLE):
                if not source_raw or source_raw not in ALLOWED_OBS_SOURCE_KEYS:
                    rejected_by_source += 1
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
            confidence = o.get('confidence', 0.0)
            try:
                confidence = float(confidence)
            except Exception:
                confidence = 0.0
            if not math.isfinite(confidence):
                confidence = 0.0

            clean_obs.append({
                'id': o.get('id', 0),
                'source_id': _clean_obs_source_id(o.get('source_id', o.get('id'))),
                'distance': distance,
                'lat': lat,
                'lon': lon,
                # Optional metadata (kept for future audit/debug; ignored by planner for now)
                'type': o.get('type'),
                'confidence': confidence,
                'source': source_raw or o.get('source'),
                'bbox': o.get('bbox'),
            })
        with state_lock:
            state['inject_posts_total'] = int(state.get('inject_posts_total', 0)) + 1
            ingest_now = time.time()
            active_obs = _ingest_obstacles_locked(clean_obs, ingest_now)
            state['last_obstacle_update'] = float(ingest_now)
            total_posts = int(state.get('inject_posts_total', 0))
            unauthorized_posts = int(state.get('inject_posts_unauthorized', 0))
        if _audit.enabled:
            sample_n = min(int(AUDIT_BRAIN_MAX_OBS_IN_EVENT), len(active_obs))
            _audit.log_event(
                "obstacle_ingest",
                count=int(len(clean_obs)),
                active_count=int(len(active_obs)),
                sample=active_obs[:sample_n],
                sample_truncated=bool(len(active_obs) > sample_n),
                posts_total=int(total_posts),
                unauthorized_total=int(unauthorized_posts),
                rejected_by_source=int(rejected_by_source),
                source_filter_enable=bool(OBS_SOURCE_FILTER_ENABLE),
                allowed_sources=list(ALLOWED_OBS_SOURCE_KEYS),
                remote_addr=str(request.remote_addr or ""),
            )
        return jsonify(status="ok")
    except Exception as e:
        if _audit.enabled:
            _audit.log_event("obstacle_ingest_error", error=str(e))
        return jsonify(error=str(e)), 400


@app.route('/api/unreal/telemetry', methods=['POST'])
def rx_unreal_telemetry():
    if not bool(UNREAL_TELEMETRY_INGEST_ENABLE):
        with state_lock:
            state['unreal_truth_last_error'] = 'ingest_disabled'
        if _audit.enabled:
            _audit.log_event("unreal_truth_rejected", reason="ingest_disabled")
        return jsonify(error="unreal_telemetry_ingest_disabled"), 403

    expected_token = str(UNREAL_TELEMETRY_TOKEN)
    if UNREAL_TELEMETRY_TOKEN_REQUIRED and not expected_token:
        with state_lock:
            state['unreal_truth_last_error'] = 'token_required_but_not_configured'
        if _audit.enabled:
            _audit.log_event("unreal_truth_rejected", reason="token_required_but_not_configured")
        return jsonify(error="server_misconfigured_missing_unreal_token"), 503

    if expected_token:
        got = request.headers.get('X-PORCE-Token', '')
        if got != expected_token:
            with state_lock:
                state['unreal_truth_posts_unauthorized'] = int(state.get('unreal_truth_posts_unauthorized', 0)) + 1
                state['unreal_truth_last_error'] = 'unauthorized_token'
            if _audit.enabled:
                _audit.log_event(
                    "unreal_truth_rejected",
                    reason="unauthorized_token",
                    remote_addr=str(request.remote_addr or ""),
                )
            return jsonify(error="unauthorized"), 401

    try:
        data = request.get_json(force=True)
        now_ts = float(time.time())
        parsed, err = _parse_unreal_truth_payload(data, now_ts)
        if parsed is None:
            reason = str(err or "invalid_payload")
            with state_lock:
                state['unreal_truth_last_error'] = reason
            if _audit.enabled:
                _audit.log_event(
                    "unreal_truth_rejected",
                    reason=reason,
                    remote_addr=str(request.remote_addr or ""),
                )
            return jsonify(error=reason), 400

        with state_lock:
            home = state.get('home') or {}
            home_alt = _clean_float(home.get('alt', 0.0), 0.0)

            alt_msl = parsed.get('alt_msl', None)
            rel_alt = parsed.get('rel_alt', None)
            if alt_msl is None and rel_alt is not None:
                alt_msl = float(home_alt) + float(rel_alt)
            if rel_alt is None and alt_msl is not None:
                rel_alt = float(alt_msl) - float(home_alt)
            parsed['alt_msl'] = None if alt_msl is None else float(alt_msl)
            parsed['rel_alt'] = None if rel_alt is None else float(rel_alt)

            state['unreal_truth'] = dict(parsed)
            state['unreal_truth_last_update'] = float(now_ts)
            state['unreal_truth_last_error'] = ''
            state['unreal_truth_posts_total'] = int(state.get('unreal_truth_posts_total', 0)) + 1
            posts_total = int(state.get('unreal_truth_posts_total', 0))
            unauthorized_total = int(state.get('unreal_truth_posts_unauthorized', 0))

        if _audit.enabled:
            _audit.append_csv_row(
                AUDIT_BRAIN_UNREAL_TRUTH_CSV,
                AUDIT_BRAIN_UNREAL_TRUTH_HEADERS,
                {
                    "ts": float(parsed.get("ts", now_ts)),
                    "ue_ts": float(parsed.get("ue_ts", now_ts)),
                    "lat": float(parsed.get("lat", 0.0) or 0.0),
                    "lon": float(parsed.get("lon", 0.0) or 0.0),
                    "alt_msl": "" if parsed.get("alt_msl", None) is None else float(parsed.get("alt_msl")),
                    "rel_alt": "" if parsed.get("rel_alt", None) is None else float(parsed.get("rel_alt")),
                    "yaw": "" if parsed.get("yaw", None) is None else float(parsed.get("yaw")),
                    "pitch": "" if parsed.get("pitch", None) is None else float(parsed.get("pitch")),
                    "roll": "" if parsed.get("roll", None) is None else float(parsed.get("roll")),
                    "x_m": "" if parsed.get("x_m", None) is None else float(parsed.get("x_m")),
                    "y_m": "" if parsed.get("y_m", None) is None else float(parsed.get("y_m")),
                    "z_m": "" if parsed.get("z_m", None) is None else float(parsed.get("z_m")),
                    "frame": "" if parsed.get("frame", None) is None else int(parsed.get("frame")),
                    "source": str(parsed.get("source", "unreal")),
                },
            )
            _audit.log_event(
                "unreal_truth_ingest",
                posts_total=int(posts_total),
                unauthorized_total=int(unauthorized_total),
                remote_addr=str(request.remote_addr or ""),
                sample={
                    "lat": float(parsed.get("lat", 0.0) or 0.0),
                    "lon": float(parsed.get("lon", 0.0) or 0.0),
                    "alt_msl": parsed.get("alt_msl", None),
                    "rel_alt": parsed.get("rel_alt", None),
                    "yaw": parsed.get("yaw", None),
                    "pitch": parsed.get("pitch", None),
                    "roll": parsed.get("roll", None),
                    "ue_ts": float(parsed.get("ue_ts", now_ts)),
                },
            )
        return jsonify(status="ok")
    except Exception as e:
        with state_lock:
            state['unreal_truth_last_error'] = str(e)
        if _audit.enabled:
            _audit.log_event("unreal_truth_error", error=str(e))
        return jsonify(error=str(e)), 400


@app.route('/api/status', methods=['GET'])
def status():
    with state_lock:
        t = state['telemetry']
        telemetry_active = (time.time() - t['last_update']) < HEARTBEAT_TIMEOUT_S
        now_ts = float(time.time())
        unreal_last_update = float(state.get('unreal_truth_last_update', 0.0) or 0.0)
        unreal_age_s = float(now_ts - unreal_last_update) if unreal_last_update > 0.0 else float('inf')
        unreal_active = bool(
            bool(UNREAL_TELEMETRY_INGEST_ENABLE)
            and unreal_last_update > 0.0
            and unreal_age_s <= float(UNREAL_TELEMETRY_ACTIVE_TIMEOUT_S)
        )
        return jsonify({
            'mode': state['telemetry']['mode'],
            'armed': bool(state['telemetry']['armed']),
            'telemetry_active': bool(telemetry_active),
            'unreal_telemetry_ingest_enabled': bool(UNREAL_TELEMETRY_INGEST_ENABLE),
            'unreal_truth_active': bool(unreal_active),
            'unreal_truth_age_s': None if not math.isfinite(unreal_age_s) else float(unreal_age_s),
            'wp_idx': state['current_wp_idx'],
            'evasion': state['evasion_active'],
            'obstacles_count': len(state['obstacles']),
            'obstacle_tracks_count': len(state.get('obstacle_tracks', {})),
            'failsafe_action_active': str(state.get('failsafe_action_active', '') or ''),
            'saw_evasion': bool(state.get('saw_evasion', False)),
            'mission_state': state.get('mission_state', 'UNKNOWN'),
            'last_error': state.get('last_error'),
            'porce_enable_evasion': bool(PORCE_ENABLE_EVASION),
            'token_required': bool(OBSTACLE_TOKEN_REQUIRED),
            'token_enabled': bool(OBSTACLE_TOKEN),
            'inject_posts_total': int(state.get('inject_posts_total', 0)),
            'inject_posts_unauthorized': int(state.get('inject_posts_unauthorized', 0)),
            'unreal_truth_posts_total': int(state.get('unreal_truth_posts_total', 0)),
            'unreal_truth_posts_unauthorized': int(state.get('unreal_truth_posts_unauthorized', 0)),
            'unreal_truth_last_error': str(state.get('unreal_truth_last_error', '') or ''),
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
    last_failsafe_status_log_ts = 0.0
    last_wp_block_status_log_ts = 0.0
    last_evasion_active = False
    while True:
        time.sleep(float(CONTROL_LOOP_PERIOD_S))
        now_loop = time.time()
        with state_lock:
            obs = list(_rebuild_active_obstacles_locked(now_loop))
            tel = state['telemetry'].copy()
            obs_ts = float(state.get('last_obstacle_track_seen', 0.0) or 0.0)
            obs_ingest_ts = float(state.get('last_obstacle_update', 0.0) or 0.0)
            unreal_last_update_ts = float(state.get('unreal_truth_last_update', 0.0) or 0.0)
            unreal_posts_total = int(state.get('unreal_truth_posts_total', 0) or 0)
            unreal_posts_unauthorized = int(state.get('unreal_truth_posts_unauthorized', 0) or 0)
            unreal_last_error = str(state.get('unreal_truth_last_error', '') or '')
            current_idx = state['current_wp_idx']
            wps = state['waypoints']
            home = state['home']
            evasion_active_now = bool(state['evasion_active'])
            evasion_path_len_now = int(len(state['evasion_path']))
            evasion_path_idx_now = int(state['path_index'])
            mission_state_now = str(state.get('mission_state', 'UNKNOWN'))
            failsafe_hold_until_ts = float(state.get('failsafe_hold_until_ts', 0.0) or 0.0)
            failsafe_action_active_now = str(state.get('failsafe_action_active', '') or '').strip().upper()

        nearest_obs = None
        nearest_dist = None
        if obs:
            nearest_obs, nearest_dist = nearest_obstacle_info(tel, obs)

        if (now_loop - float(last_status_log_ts)) >= float(CONTROL_LOG_INTERVAL_S):
            last_status_log_ts = now_loop
            lat = tel.get('lat', 0)
            lon = tel.get('lon', 0)
            alt = tel.get('alt', 0)
            rel_alt = tel.get('rel_alt', 0.0)
            mode = tel.get('mode', 'UNK')
            obs_count = len(obs)
            unreal_age_s = float(now_loop - unreal_last_update_ts) if unreal_last_update_ts > 0.0 else float('inf')
            unreal_active = bool(
                bool(UNREAL_TELEMETRY_INGEST_ENABLE)
                and unreal_last_update_ts > 0.0
                and unreal_age_s <= float(UNREAL_TELEMETRY_ACTIVE_TIMEOUT_S)
            )
            unreal_age_txt = "n/a" if not math.isfinite(unreal_age_s) else f"{unreal_age_s:.2f}s"
            unreal_err_txt = unreal_last_error if unreal_last_error else "-"
            log.info(
                f"[STATUS] Mode: {mode} | GPS: {lat:.6f}, {lon:.6f} Alt: {alt:.1f}m (rel {rel_alt:.1f}m) "
                f"| WP: {current_idx} | Obs: {obs_count} "
                f"| UE: active={int(unreal_active)} age={unreal_age_txt} posts={unreal_posts_total} unauth={unreal_posts_unauthorized} err={unreal_err_txt}"
            )

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

        if failsafe_action_active_now:
            action = str(failsafe_action_active_now)
            if action == "HOLD":
                if tel.get('armed', False):
                    hold_alt_rel = float(tel.get('rel_alt', 0.0) or 0.0)
                    master.mav.set_position_target_global_int_send(
                        0, master.target_system, master.target_component,
                        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                        MAVLINK_SET_POSITION_TARGET_INT_IGNORE_MASK,
                        int(float(tel['lat']) * 1e7), int(float(tel['lon']) * 1e7),
                        hold_alt_rel,
                        0, 0, 0, 0, 0, 0, 0, 0
                    )
                if (now_loop - float(last_failsafe_status_log_ts)) >= float(CONTROL_LOG_INTERVAL_S):
                    last_failsafe_status_log_ts = now_loop
                    log.error("[FAILSAFE] HOLD activo por escalado de seguridad.")
                continue

            if action in {"RTL", "LAND"}:
                if str(tel.get('mode', '')) != action:
                    master.set_mode(action)
                if (now_loop - float(last_failsafe_status_log_ts)) >= float(CONTROL_LOG_INTERVAL_S):
                    last_failsafe_status_log_ts = now_loop
                    log.error(f"[FAILSAFE] {action} activo por escalado de seguridad.")
                continue

            with state_lock:
                state['failsafe_action_active'] = ''

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

        wp_target = None
        wp_dist_m = None
        wp_block_obs = None
        wp_block_dist = None
        wp_block_in_tolerance = False
        wp_block_elapsed_s = 0.0
        wp_block_timeout_ready = False

        if current_idx < len(wps):
            wp_target = wps[current_idx]
            wp_dist_m = haversine(tel['lat'], tel['lon'], wp_target['lat'], wp_target['lon'])
            if float(wp_dist_m) < float(WP_TOLERANCE_M):
                wp_block_obs, wp_block_dist = waypoint_blocking_obstacle_info(tel, wp_target, obs)
                if wp_block_obs is None:
                    near_obs_gate, near_obs_gate_dist = nearest_obstacle_info(tel, obs)
                    if (
                        near_obs_gate is not None
                        and near_obs_gate_dist is not None
                        and float(near_obs_gate_dist) <= float(EVASION_WP_ADVANCE_MIN_OBS_DIST_M)
                    ):
                        wp_block_obs = near_obs_gate
                        wp_block_dist = float(near_obs_gate_dist)
                wp_block_in_tolerance = bool(wp_block_obs is not None)

        with state_lock:
            if wp_block_in_tolerance:
                tracked_wp_idx = int(state.get('wp_block_wp_idx', -1) or -1)
                block_since_ts = float(state.get('wp_block_since_ts', 0.0) or 0.0)
                if tracked_wp_idx != int(current_idx) or block_since_ts <= 0.0:
                    block_since_ts = float(now_loop)
                    state['wp_block_wp_idx'] = int(current_idx)
                    state['wp_block_since_ts'] = float(block_since_ts)
                wp_block_elapsed_s = max(0.0, float(now_loop) - float(block_since_ts))
            else:
                state['wp_block_wp_idx'] = -1
                state['wp_block_since_ts'] = 0.0

        if (
            wp_block_in_tolerance
            and float(EVASION_WP_BLOCK_MAX_HOLD_S) > 0.0
            and float(wp_block_elapsed_s) >= float(EVASION_WP_BLOCK_MAX_HOLD_S)
        ):
            wp_block_timeout_ready = True

        # --- ALGORITMO PORCE (EVASION) ---
        active_path = []
        path_idx = 0
        decision_reason = "none"
        decision_triggered = False
        decision_route_points = 0
        decision_nearest_type = nearest_obs.get("type") if nearest_obs else None
        decision_replan_blocked = False
        decision_hold_active = False
        decision_failsafe_action = str(failsafe_action_active_now)
        decision_terminal_escalated = False
        evasion_last_replan_ts = 0.0
        obs_fresh = bool(obs)
        reaction_distance_eval_m, speed_eval_mps = adaptive_reaction_distance_m(tel)
        nearest_eval = None
        min_dist_eval = None
        planner_obs_count = 0
        can_replan_now = False
        if True:
            with state_lock:
                active_path = list(state['evasion_path'])
                path_idx = int(state['path_index'])
                evasion_last_replan_ts = float(state.get('evasion_last_replan_ts', 0.0))
                failsafe_hold_until_ts = float(state.get('failsafe_hold_until_ts', 0.0) or 0.0)
                decision_failsafe_action = str(state.get('failsafe_action_active', '') or '').strip().upper()
                hold_active = float(now_loop) < float(failsafe_hold_until_ts)
                decision_hold_active = bool(hold_active)
                interval_ok = (now_loop - float(evasion_last_replan_ts)) >= float(EVASION_REPLAN_MIN_INTERVAL_S)

            if (
                current_idx < len(wps)
                and wp_dist_m is not None
                and float(wp_dist_m) < float(WP_TOLERANCE_M)
                and wp_block_obs is None
                and not active_path
            ):
                log.info(f"[REACHED] WP{current_idx} alcanzado (pre-PORCE). Siguiente.")
                with state_lock:
                    state['current_wp_idx'] += 1
                    state['wp_block_wp_idx'] = -1
                    state['wp_block_since_ts'] = 0.0
                    state['failsafe_recent_route_fail_ts'] = []
                    state['failsafe_hold_until_ts'] = 0.0
                if _audit.enabled:
                    _audit.log_event(
                        "waypoint_advance_pre_porce",
                        wp_idx=int(current_idx),
                        wp_distance_m=float(wp_dist_m),
                    )
                continue

            if obs_fresh:
                nearest_eval, min_dist_eval = nearest_obstacle_info(tel, obs)
                decision_nearest_type = nearest_eval.get("type") if nearest_eval else decision_nearest_type

                if hold_active:
                    decision_reason = "failsafe_hold_active"
                elif wp_block_in_tolerance:
                    decision_reason = "wp_blocked_in_tolerance"
                    decision_replan_blocked = True
                    can_replan_now = False
                elif nearest_eval is None:
                    decision_reason = "no_obstacles"
                elif not PORCE_ENABLE_EVASION:
                    decision_reason = "evasion_disabled"
                elif float(min_dist_eval) >= float(reaction_distance_eval_m):
                    decision_reason = "distance_above_reaction"
                else:
                    can_replan_now = bool(interval_ok)
                    should_plan_route = False
                    if active_path:
                        if not bool(EVASION_ALLOW_REPLAN_WHEN_ACTIVE):
                            decision_reason = "evasion_in_progress"
                            decision_replan_blocked = True
                            can_replan_now = False
                        elif min_dist_eval is None:
                            decision_reason = "replan_blocked_active_no_distance"
                            decision_replan_blocked = True
                            can_replan_now = False
                        elif float(min_dist_eval) > float(EVASION_ACTIVE_REPLAN_DISTANCE_M):
                            decision_reason = "replan_blocked_active_distance"
                            decision_replan_blocked = True
                            can_replan_now = False
                        elif not interval_ok:
                            decision_reason = "replan_blocked_active_interval"
                            decision_replan_blocked = True
                            can_replan_now = False
                        else:
                            decision_reason = "trigger_plan_route_active"
                            decision_triggered = True
                            should_plan_route = True
                            can_replan_now = True
                    elif not interval_ok:
                        decision_reason = "replan_blocked"
                        decision_replan_blocked = True
                        can_replan_now = False
                    else:
                        decision_reason = "trigger_plan_route"
                        decision_triggered = True
                        should_plan_route = True
                        can_replan_now = True

                    if should_plan_route:
                        log.warning(f"[PORCE] Obstaculo detectado a {float(min_dist_eval):.1f}m. Planificando ruta A*...")
                        if len(wps) > 0:
                            target_wp = wps[current_idx] if current_idx < len(wps) else wps[-1]
                        else:
                            target_wp = {'lat': tel['lat'], 'lon': tel['lon']}

                        planner_obs = planner_obstacle_subset(tel, obs)
                        planner_obs_count = int(len(planner_obs))
                        new_route = planner.plan_route(
                            tel['lat'],
                            tel['lon'],
                            target_wp['lat'],
                            target_wp['lon'],
                            planner_obs,
                        )
                        min_route_points = max(1, int(EVASION_ROUTE_MIN_POINTS))
                        route_len = 0 if new_route is None else int(len(new_route))
                        route_valid = bool(new_route) and int(route_len) >= int(min_route_points)
                        route_single_point = bool(new_route) and int(route_len) == 1
                        route_degenerate = bool(new_route) and not bool(route_valid)
                        if route_valid:
                            state['evasion_path'] = new_route
                            state['evasion_grid_origin'] = {'lat': tel['lat'], 'lon': tel['lon']}
                            state['path_index'] = 0
                            state['evasion_active'] = True
                            state['saw_evasion'] = True
                            state['evasion_last_replan_ts'] = now_loop
                            state['evasion_replans'] = int(state.get('evasion_replans', 0)) + 1
                            state['failsafe_hold_until_ts'] = 0.0
                            state['failsafe_recent_route_fail_ts'] = []
                            active_path = list(new_route)
                            path_idx = 0
                            decision_route_points = int(route_len)
                            decision_reason = "route_generated"
                            if _audit.enabled:
                                _audit.log_event(
                                    "evasion_route_generated",
                                    nearest_distance_m=float(min_dist_eval),
                                    nearest_type=str(decision_nearest_type),
                                    route_points=int(route_len),
                                    planner_obs_count=int(planner_obs_count),
                                    wp_idx=int(current_idx),
                                    can_replan_now=bool(can_replan_now),
                                )
                            log.info(f"[PORCE] Ruta generada: {route_len} sub-puntos.")
                        elif route_single_point:
                            state['evasion_last_replan_ts'] = now_loop
                            state['failsafe_hold_until_ts'] = 0.0
                            failsafe_hold_until_ts = 0.0
                            decision_reason = "route_single_point"
                            log.warning(
                                "[PORCE] Ruta A* de 1 punto (objetivo en misma celda). "
                                "No se activa hold; continuando navegacion."
                            )
                            if _audit.enabled:
                                _audit.log_event(
                                    "evasion_route_single_point",
                                    nearest_distance_m=float(min_dist_eval),
                                    nearest_type=str(decision_nearest_type),
                                    route_points=int(route_len),
                                    route_min_points=int(min_route_points),
                                    planner_obs_count=int(planner_obs_count),
                                    wp_idx=int(current_idx),
                                )
                        else:
                            state['evasion_last_replan_ts'] = now_loop
                            decision_reason = "route_failed"
                            if route_degenerate:
                                decision_reason = "route_degenerate"
                                log.error(
                                    f"[PORCE] Ruta A* degenerada ({route_len} puntos). "
                                    f"Minimo requerido={min_route_points}. Tratando como fallo."
                                )
                                if _audit.enabled:
                                    _audit.log_event(
                                        "evasion_route_degenerate",
                                        nearest_distance_m=float(min_dist_eval),
                                        nearest_type=str(decision_nearest_type),
                                        route_points=int(route_len),
                                        route_min_points=int(min_route_points),
                                        planner_obs_count=int(planner_obs_count),
                                        wp_idx=int(current_idx),
                                    )
                            if (
                                min_dist_eval is not None
                                and float(min_dist_eval) <= float(EVASION_FAILSAFE_MIN_DIST_M)
                            ):
                                fail_count = int(_record_route_fail_for_failsafe_locked(float(now_loop)))
                                stage_action = "HOLD_ONLY"
                                if bool(EVASION_FAILSAFE_ESCALATE_ENABLE):
                                    stage_action = str(_failsafe_stage_for_fail_count(fail_count) or "HOLD").upper()
                                if _audit.enabled:
                                    _audit.log_event(
                                        "failsafe_stage_action",
                                        stage_action=str(stage_action),
                                        fail_count=int(fail_count),
                                        stage1_fails=int(EVASION_FAILSAFE_STAGE1_FAILS),
                                        stage2_fails=int(EVASION_FAILSAFE_STAGE2_FAILS),
                                        stage3_fails=int(EVASION_FAILSAFE_STAGE3_FAILS),
                                        nearest_distance_m=float(min_dist_eval),
                                        nearest_type=str(decision_nearest_type),
                                        planner_obs_count=int(planner_obs_count),
                                        wp_idx=int(current_idx),
                                    )

                                if stage_action == "REPLAN_LATERAL":
                                    last_lateral_replan_ts = _clean_float(
                                        state.get("failsafe_last_lateral_replan_ts", 0.0),
                                        0.0,
                                    )
                                    lateral_interval_ok = (
                                        float(now_loop) - float(last_lateral_replan_ts)
                                    ) >= float(EVASION_FAILSAFE_LATERAL_MIN_INTERVAL_S)
                                    lateral_meta = {}
                                    lateral_route = None
                                    if lateral_interval_ok:
                                        lateral_route, lateral_meta = build_lateral_replan_route(
                                            tel,
                                            target_wp,
                                            obs,
                                            nearest_eval,
                                        )
                                        state["failsafe_last_lateral_replan_ts"] = float(now_loop)
                                    else:
                                        lateral_meta = {"reason": "cooldown"}

                                    if lateral_route and int(len(lateral_route)) >= int(min_route_points):
                                        state['evasion_path'] = list(lateral_route)
                                        state['evasion_grid_origin'] = {'lat': tel['lat'], 'lon': tel['lon']}
                                        state['path_index'] = 0
                                        state['evasion_active'] = True
                                        state['saw_evasion'] = True
                                        state['evasion_last_replan_ts'] = now_loop
                                        state['evasion_replans'] = int(state.get('evasion_replans', 0)) + 1
                                        state['failsafe_hold_until_ts'] = 0.0
                                        state['failsafe_recent_route_fail_ts'] = []
                                        failsafe_hold_until_ts = 0.0
                                        active_path = list(lateral_route)
                                        path_idx = 0
                                        decision_route_points = int(len(lateral_route))
                                        decision_reason = "failsafe_lateral_replan"
                                        decision_triggered = True
                                        decision_hold_active = False
                                        can_replan_now = True
                                        log.warning(
                                            f"[PORCE] Failsafe etapa 2: ruta lateral generada ({len(lateral_route)} puntos)."
                                        )
                                        if _audit.enabled:
                                            _audit.log_event(
                                                "failsafe_lateral_replan",
                                                success=True,
                                                route_points=int(len(lateral_route)),
                                                fail_count=int(fail_count),
                                                nearest_distance_m=float(min_dist_eval),
                                                nearest_type=str(decision_nearest_type),
                                                planner_obs_count=int(planner_obs_count),
                                                wp_idx=int(current_idx),
                                            )
                                    else:
                                        if float(EVASION_FAILSAFE_HOLD_S) > 0.0:
                                            hold_until = float(now_loop) + float(EVASION_FAILSAFE_HOLD_S)
                                            state['failsafe_hold_until_ts'] = float(hold_until)
                                            failsafe_hold_until_ts = float(hold_until)
                                            decision_reason = "route_failed_hold"
                                            decision_hold_active = True
                                            log.error(
                                                "[PORCE] Failsafe etapa 2: no se pudo generar ruta lateral. "
                                                "Aplicando hold de seguridad."
                                            )
                                            if _audit.enabled:
                                                _audit.log_event(
                                                    "evasion_route_failed_hold",
                                                    nearest_distance_m=float(min_dist_eval),
                                                    nearest_type=str(decision_nearest_type),
                                                    hold_s=float(EVASION_FAILSAFE_HOLD_S),
                                                    planner_obs_count=int(planner_obs_count),
                                                    failsafe_fail_count=int(fail_count),
                                                    stage_action="REPLAN_LATERAL_FALLBACK_HOLD",
                                                    wp_idx=int(current_idx),
                                                )
                                        else:
                                            decision_reason = "route_failed_no_hold"
                                            log.error(
                                                "[PORCE] Failsafe etapa 2: no se pudo generar ruta lateral "
                                                "y hold deshabilitado."
                                            )
                                            if _audit.enabled:
                                                _audit.log_event(
                                                    "evasion_route_failed",
                                                    nearest_distance_m=float(min_dist_eval),
                                                    nearest_type=str(decision_nearest_type),
                                                    planner_obs_count=int(planner_obs_count),
                                                    failsafe_fail_count=int(fail_count),
                                                    stage_action="REPLAN_LATERAL_FAILED",
                                                    wp_idx=int(current_idx),
                                                )
                                        if _audit.enabled:
                                            _audit.log_event(
                                                "failsafe_lateral_replan",
                                                success=False,
                                                fail_count=int(fail_count),
                                                reason=str(lateral_meta.get("reason", "unknown")),
                                                nearest_distance_m=float(min_dist_eval),
                                                nearest_type=str(decision_nearest_type),
                                                planner_obs_count=int(planner_obs_count),
                                                wp_idx=int(current_idx),
                                            )
                                elif stage_action in {"LAND", "RTL"}:
                                    terminal_activated = _activate_terminal_failsafe_locked(
                                        float(now_loop),
                                        action=str(stage_action),
                                        fail_count=int(fail_count),
                                        wp_idx=int(current_idx),
                                        nearest_distance_m=float(min_dist_eval),
                                        nearest_type=None if decision_nearest_type is None else str(decision_nearest_type),
                                    )
                                    if terminal_activated:
                                        decision_reason = "failsafe_terminal_action"
                                        decision_terminal_escalated = True
                                        decision_failsafe_action = str(stage_action)
                                        log.error(
                                            f"[PORCE] Failsafe terminal activado ({stage_action}) "
                                            f"tras {fail_count} fallos en ventana."
                                        )
                                        if str(tel.get('mode', '')).upper() != str(stage_action):
                                            master.set_mode(str(stage_action))
                                        if _audit.enabled:
                                            _audit.log_event(
                                                "failsafe_terminal_action",
                                                action=str(stage_action),
                                                fail_count=int(fail_count),
                                                nearest_distance_m=float(min_dist_eval),
                                                nearest_type=str(decision_nearest_type),
                                                planner_obs_count=int(planner_obs_count),
                                                wp_idx=int(current_idx),
                                            )
                                    elif float(EVASION_FAILSAFE_HOLD_S) > 0.0:
                                        hold_until = float(now_loop) + float(EVASION_FAILSAFE_HOLD_S)
                                        state['failsafe_hold_until_ts'] = float(hold_until)
                                        failsafe_hold_until_ts = float(hold_until)
                                        decision_reason = "route_failed_hold"
                                        decision_hold_active = True
                                        if _audit.enabled:
                                            _audit.log_event(
                                                "evasion_route_failed_hold",
                                                nearest_distance_m=float(min_dist_eval),
                                                nearest_type=str(decision_nearest_type),
                                                hold_s=float(EVASION_FAILSAFE_HOLD_S),
                                                planner_obs_count=int(planner_obs_count),
                                                failsafe_fail_count=int(fail_count),
                                                stage_action=f"{stage_action}_COOLDOWN_HOLD",
                                                wp_idx=int(current_idx),
                                            )
                                elif float(EVASION_FAILSAFE_HOLD_S) > 0.0:
                                    hold_until = float(now_loop) + float(EVASION_FAILSAFE_HOLD_S)
                                    state['failsafe_hold_until_ts'] = float(hold_until)
                                    failsafe_hold_until_ts = float(hold_until)
                                    decision_reason = "route_failed_hold"
                                    decision_hold_active = True
                                    log.error("[PORCE] A* fallo cerca de obstaculo. Activando hold de seguridad.")
                                    if _audit.enabled:
                                        _audit.log_event(
                                            "evasion_route_failed_hold",
                                            nearest_distance_m=float(min_dist_eval),
                                            nearest_type=str(decision_nearest_type),
                                            hold_s=float(EVASION_FAILSAFE_HOLD_S),
                                            planner_obs_count=int(planner_obs_count),
                                            failsafe_fail_count=int(fail_count),
                                            stage_action=str(stage_action),
                                            wp_idx=int(current_idx),
                                        )
                                else:
                                    decision_reason = "route_failed_no_hold"
                                    log.error(
                                        "[PORCE] A* fallo cerca de obstaculo sin hold configurado."
                                    )
                                    if _audit.enabled:
                                        _audit.log_event(
                                            "evasion_route_failed",
                                            nearest_distance_m=float(min_dist_eval),
                                            nearest_type=str(decision_nearest_type),
                                            planner_obs_count=int(planner_obs_count),
                                            failsafe_fail_count=int(fail_count),
                                            stage_action=str(stage_action),
                                            wp_idx=int(current_idx),
                                        )
                            else:
                                if float(EVASION_FAILSAFE_HOLD_S) > 0.0:
                                    hold_until = float(now_loop) + float(EVASION_FAILSAFE_HOLD_S)
                                    state['failsafe_hold_until_ts'] = float(hold_until)
                                    failsafe_hold_until_ts = float(hold_until)
                                    decision_reason = "route_failed_hold_caution"
                                    decision_hold_active = True
                                    log.error(
                                        "[PORCE] A* fallo en zona de reaccion. Activando hold preventivo."
                                    )
                                    if _audit.enabled:
                                        _audit.log_event(
                                            "evasion_route_failed_hold_caution",
                                            nearest_distance_m=float(min_dist_eval),
                                            nearest_type=str(decision_nearest_type),
                                            hold_s=float(EVASION_FAILSAFE_HOLD_S),
                                            planner_obs_count=int(planner_obs_count),
                                            wp_idx=int(current_idx),
                                        )
                                else:
                                    decision_reason = "route_failed_no_hold"
                                    log.error(
                                        "[PORCE] A* fallo en zona de reaccion sin hold configurado."
                                    )
                                    if _audit.enabled:
                                        _audit.log_event(
                                            "evasion_route_failed",
                                            nearest_distance_m=float(min_dist_eval),
                                            nearest_type=str(decision_nearest_type),
                                            planner_obs_count=int(planner_obs_count),
                                            wp_idx=int(current_idx),
                                        )
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
                obs_ingest_age_s=float(max(0.0, now_loop - float(obs_ingest_ts))) if float(obs_ingest_ts) > 0.0 else None,
                nearest_distance_m=None if audit_min_dist is None else float(audit_min_dist),
                nearest_type=None if audit_nearest_type is None else str(audit_nearest_type),
                reaction_distance_base_m=float(EVASION_REACTION_BASE_M),
                reaction_distance_eval_m=float(reaction_distance_eval_m),
                speed_mps=float(speed_eval_mps),
                porce_enable_evasion=bool(PORCE_ENABLE_EVASION),
                evasion_active=bool(evasion_active_now),
                decision_reason=str(decision_reason),
                decision_triggered=bool(decision_triggered),
                decision_route_points=int(decision_route_points),
                obs_fresh=bool(obs_fresh),
                replan_blocked=bool(decision_replan_blocked),
                can_replan_now=bool(can_replan_now),
                planner_obs_count=int(planner_obs_count),
                failsafe_hold_active=bool(decision_hold_active),
                failsafe_hold_remaining_s=float(max(0.0, float(failsafe_hold_until_ts) - float(now_loop))),
                failsafe_action_active=str(decision_failsafe_action),
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

        if decision_terminal_escalated:
            continue

        hold_remaining_s = float(max(0.0, float(failsafe_hold_until_ts) - float(now_loop)))
        if (not active_path) and hold_remaining_s > 0.0:
            if current_idx < len(wps):
                target_alt_rel = wps[current_idx]['alt'] - (home['alt'] if home else 0)
            else:
                target_alt_rel = float(tel.get('rel_alt', 0.0) or 0.0)
            master.mav.set_position_target_global_int_send(
                0, master.target_system, master.target_component,
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                MAVLINK_SET_POSITION_TARGET_INT_IGNORE_MASK,
                int(float(tel['lat']) * 1e7), int(float(tel['lon']) * 1e7),
                target_alt_rel,
                0, 0, 0, 0, 0, 0, 0, 0
            )
            if (now_loop - float(last_failsafe_status_log_ts)) >= max(
                float(CONTROL_LOG_INTERVAL_S),
                float(EVASION_FAILSAFE_HOLD_S) / 2.0 if float(EVASION_FAILSAFE_HOLD_S) > 0.0 else float(CONTROL_LOG_INTERVAL_S),
            ):
                last_failsafe_status_log_ts = now_loop
                log.warning(f"[PORCE] Hold de seguridad activo ({hold_remaining_s:.1f}s restantes).")
            continue

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
                    state['failsafe_hold_until_ts'] = 0.0
                if _audit.enabled:
                    _audit.log_event("evasion_completed", wp_idx=int(current_idx))

        # --- NAVEGACION ESTANDAR ---
        if current_idx < len(wps):
            target = wp_target if wp_target is not None else wps[current_idx]
            dist = float(wp_dist_m) if wp_dist_m is not None else haversine(
                tel['lat'], tel['lon'], target['lat'], target['lon']
            )

            if dist < WP_TOLERANCE_M:
                if wp_block_obs is None:
                    log.info(f"[REACHED] WP{current_idx} alcanzado. Siguiente.")
                    with state_lock:
                        state['current_wp_idx'] += 1
                        state['wp_block_wp_idx'] = -1
                        state['wp_block_since_ts'] = 0.0
                        state['failsafe_recent_route_fail_ts'] = []
                        state['failsafe_hold_until_ts'] = 0.0
                    continue

                if wp_block_timeout_ready:
                    if bool(EVASION_WP_BLOCK_FORCE_ADVANCE_ENABLE):
                        log.warning(
                            f"[NAV] WP{current_idx} bloqueado {float(wp_block_elapsed_s):.1f}s; "
                            f"avance forzado al siguiente waypoint para evitar deadlock."
                        )
                        with state_lock:
                            state['current_wp_idx'] += 1
                            state['wp_block_wp_idx'] = -1
                            state['wp_block_since_ts'] = 0.0
                            state['failsafe_recent_route_fail_ts'] = []
                            state['failsafe_hold_until_ts'] = 0.0
                        if _audit.enabled:
                            _audit.log_event(
                                "waypoint_force_advance_blocked",
                                wp_idx=int(current_idx),
                                wp_distance_m=float(dist),
                                nearest_distance_m=None if wp_block_dist is None else float(wp_block_dist),
                                nearest_type=str(wp_block_obs.get("type", "unknown")),
                                blocked_elapsed_s=float(wp_block_elapsed_s),
                                max_hold_s=float(EVASION_WP_BLOCK_MAX_HOLD_S),
                                corridor_half_width_m=float(EVASION_WP_BLOCK_CORRIDOR_HALF_WIDTH_M),
                                min_obs_dist_m=float(EVASION_WP_ADVANCE_MIN_OBS_DIST_M),
                            )
                        continue

                    log.error(
                        f"[FAILSAFE] WP{current_idx} bloqueado {float(wp_block_elapsed_s):.1f}s; "
                        "activando LAND en sitio (sin RTL)."
                    )
                    with state_lock:
                        state['failsafe_action_active'] = 'LAND'
                        state['mission_state'] = 'FAILED'
                        state['last_error'] = (
                            f"waypoint_block_timeout_land_wp={int(current_idx)}_"
                            f"elapsed={float(wp_block_elapsed_s):.1f}s"
                        )
                        state['evasion_path'] = []
                        state['path_index'] = 0
                        state['evasion_active'] = False
                        state['evasion_grid_origin'] = None
                        state['failsafe_hold_until_ts'] = 0.0
                        state['failsafe_recent_route_fail_ts'] = []
                        state['wp_block_wp_idx'] = -1
                        state['wp_block_since_ts'] = 0.0
                    if str(tel.get('mode', '')) != 'LAND':
                        master.set_mode('LAND')
                    if _audit.enabled:
                        _audit.log_event(
                            "waypoint_block_timeout_land",
                            wp_idx=int(current_idx),
                            wp_distance_m=float(dist),
                            nearest_distance_m=None if wp_block_dist is None else float(wp_block_dist),
                            nearest_type=str(wp_block_obs.get("type", "unknown")),
                            blocked_elapsed_s=float(wp_block_elapsed_s),
                            max_hold_s=float(EVASION_WP_BLOCK_MAX_HOLD_S),
                            corridor_half_width_m=float(EVASION_WP_BLOCK_CORRIDOR_HALF_WIDTH_M),
                            min_obs_dist_m=float(EVASION_WP_ADVANCE_MIN_OBS_DIST_M),
                        )
                    continue

                target_alt_rel = target['alt'] - (home['alt'] if home else 0)
                master.mav.set_position_target_global_int_send(
                    0, master.target_system, master.target_component,
                    mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                    MAVLINK_SET_POSITION_TARGET_INT_IGNORE_MASK,
                    int(float(tel['lat']) * 1e7), int(float(tel['lon']) * 1e7),
                    target_alt_rel,
                    0, 0, 0, 0, 0, 0, 0, 0
                )
                if (now_loop - float(last_wp_block_status_log_ts)) >= float(CONTROL_LOG_INTERVAL_S):
                    last_wp_block_status_log_ts = now_loop
                    wp_block_dist_txt = "n/a" if wp_block_dist is None else f"{float(wp_block_dist):.1f}m"
                    log.warning(
                        f"[NAV] WP{current_idx} dentro de tolerancia pero bloqueado "
                        f"(obs={str(wp_block_obs.get('type', 'unknown'))}, d={wp_block_dist_txt}, "
                        f"bloqueado={float(wp_block_elapsed_s):.1f}s)."
                    )
                if _audit.enabled:
                    _audit.log_event(
                        "waypoint_reach_blocked",
                        wp_idx=int(current_idx),
                        wp_distance_m=float(dist),
                        nearest_distance_m=None if wp_block_dist is None else float(wp_block_dist),
                        nearest_type=str(wp_block_obs.get("type", "unknown")),
                        blocked_elapsed_s=float(wp_block_elapsed_s),
                        corridor_half_width_m=float(EVASION_WP_BLOCK_CORRIDOR_HALF_WIDTH_M),
                        min_obs_dist_m=float(EVASION_WP_ADVANCE_MIN_OBS_DIST_M),
                    )
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
        telemetry_out = dict(state['telemetry'])
        home_out = dict(state['home'])
        home_lat = home_out.get("lat")
        home_lon = home_out.get("lon")
        home_alt = home_out.get("alt")

        tel_lat = telemetry_out.get("lat")
        tel_lon = telemetry_out.get("lon")
        tel_rel_alt = telemetry_out.get("rel_alt")
        tel_alt = telemetry_out.get("alt")
        if home_lat is not None and home_lon is not None and tel_lat is not None and tel_lon is not None:
            tel_north_m, tel_east_m = _latlon_to_local_ne_m(
                float(home_lat),
                float(home_lon),
                float(tel_lat),
                float(tel_lon),
            )
            tel_up_m = None
            if tel_rel_alt is not None:
                try:
                    tel_up_m = float(tel_rel_alt)
                except Exception:
                    tel_up_m = None
            elif tel_alt is not None and home_alt is not None:
                try:
                    tel_up_m = float(tel_alt) - float(home_alt)
                except Exception:
                    tel_up_m = None
            telemetry_out["world_m"] = {
                "north": float(tel_north_m),
                "east": float(tel_east_m),
                "up": None if tel_up_m is None else float(tel_up_m),
            }

        obstacles_out = []
        for idx, obs in enumerate(state['obstacles']):
            obs_payload = dict(obs)
            obs_entity_id = str(
                obs_payload.get("entity_id")
                or f"obs:{int(obs_payload.get('source_id', obs_payload.get('id', idx)) or idx)}"
            )
            obs_payload["object_id"] = obs_entity_id
            obs_payload["object_type"] = str(obs_payload.get("type") or "unknown")
            obs_payload["entity_id"] = obs_entity_id

            obs_lat = obs_payload.get("lat")
            obs_lon = obs_payload.get("lon")
            if home_lat is not None and home_lon is not None and obs_lat is not None and obs_lon is not None:
                try:
                    obs_north_m, obs_east_m = _latlon_to_local_ne_m(
                        float(home_lat),
                        float(home_lon),
                        float(obs_lat),
                        float(obs_lon),
                    )
                    obs_payload["world_m"] = {
                        "north": float(obs_north_m),
                        "east": float(obs_east_m),
                        "up": None,
                    }
                except Exception:
                    pass
            obstacles_out.append(obs_payload)

        return jsonify({
            'telemetry': telemetry_out,
            'unreal_truth': state.get('unreal_truth', {}),
            'home': home_out,
            'waypoints': state['waypoints'],
            'obstacles': obstacles_out,
            'obstacle_tracks_count': len(state.get('obstacle_tracks', {})),
            'evasion': {
                'active': state['evasion_active'], 
                'path': state['evasion_path'],
                'grid_origin': state['evasion_grid_origin'],
                'failsafe_hold_until_ts': float(state.get('failsafe_hold_until_ts', 0.0) or 0.0),
                'failsafe_action_active': str(state.get('failsafe_action_active', '') or ''),
                'failsafe_recent_fail_count': int(len(state.get('failsafe_recent_route_fail_ts', []))),
            },
            'params': {
                'safety_dist': SAFETY_DISTANCE_M, 
                'detection_dist': DETECTION_RANGE_M,
                'reaction_distance_m': REACTION_DISTANCE_M,
                'evasion_dynamic_reaction_enable': EVASION_DYNAMIC_REACTION_ENABLE,
                'evasion_reaction_base_m': EVASION_REACTION_BASE_M,
                'evasion_reaction_speed_gain_s': EVASION_REACTION_SPEED_GAIN_S,
                'evasion_reaction_min_m': EVASION_REACTION_MIN_M,
                'evasion_reaction_max_m': EVASION_REACTION_MAX_M,
                'evasion_replan_min_interval_s': EVASION_REPLAN_MIN_INTERVAL_S,
                'evasion_route_point_reached_m': EVASION_ROUTE_POINT_REACHED_M,
                'evasion_route_min_points': EVASION_ROUTE_MIN_POINTS,
                'evasion_allow_replan_when_active': EVASION_ALLOW_REPLAN_WHEN_ACTIVE,
                'evasion_active_replan_distance_m': EVASION_ACTIVE_REPLAN_DISTANCE_M,
                'evasion_planner_obs_max_distance_m': EVASION_PLANNER_OBS_MAX_DISTANCE_M,
                'evasion_planner_obs_max_count': EVASION_PLANNER_OBS_MAX_COUNT,
                'evasion_failsafe_min_dist_m': EVASION_FAILSAFE_MIN_DIST_M,
                'evasion_wp_advance_min_obs_dist_m': EVASION_WP_ADVANCE_MIN_OBS_DIST_M,
                'evasion_wp_block_corridor_half_width_m': EVASION_WP_BLOCK_CORRIDOR_HALF_WIDTH_M,
                'evasion_wp_block_force_advance_enable': EVASION_WP_BLOCK_FORCE_ADVANCE_ENABLE,
                'evasion_wp_block_max_hold_s': EVASION_WP_BLOCK_MAX_HOLD_S,
                'evasion_failsafe_hold_s': EVASION_FAILSAFE_HOLD_S,
                'evasion_failsafe_escalate_enable': EVASION_FAILSAFE_ESCALATE_ENABLE,
                'evasion_failsafe_escalate_fails': EVASION_FAILSAFE_ESCALATE_FAILS,
                'evasion_failsafe_stage1_fails': EVASION_FAILSAFE_STAGE1_FAILS,
                'evasion_failsafe_stage2_fails': EVASION_FAILSAFE_STAGE2_FAILS,
                'evasion_failsafe_stage3_fails': EVASION_FAILSAFE_STAGE3_FAILS,
                'evasion_failsafe_escalate_window_s': EVASION_FAILSAFE_ESCALATE_WINDOW_S,
                'evasion_failsafe_escalate_cooldown_s': EVASION_FAILSAFE_ESCALATE_COOLDOWN_S,
                'evasion_failsafe_lateral_offset_m': EVASION_FAILSAFE_LATERAL_OFFSET_M,
                'evasion_failsafe_lateral_forward_gain': EVASION_FAILSAFE_LATERAL_FORWARD_GAIN,
                'evasion_failsafe_lateral_min_interval_s': EVASION_FAILSAFE_LATERAL_MIN_INTERVAL_S,
                'evasion_failsafe_escalate_action': EVASION_FAILSAFE_ESCALATE_ACTION,
                'obs_static_classes': list(STATIC_OBS_CLASS_KEYS),
                'obs_track_ttl_static_s': OBS_TRACK_TTL_STATIC_S,
                'obs_track_ttl_dynamic_s': OBS_TRACK_TTL_DYNAMIC_S,
                'obs_track_assoc_static_m': OBS_TRACK_ASSOC_STATIC_M,
                'obs_track_assoc_dynamic_m': OBS_TRACK_ASSOC_DYNAMIC_M,
                'obs_track_max': OBS_TRACK_MAX,
                'obs_source_filter_enable': OBS_SOURCE_FILTER_ENABLE,
                'obs_allowed_sources': list(ALLOWED_OBS_SOURCE_KEYS),
                'unreal_telemetry_ingest_enabled': bool(UNREAL_TELEMETRY_INGEST_ENABLE),
                'unreal_telemetry_token_required': UNREAL_TELEMETRY_TOKEN_REQUIRED,
                'unreal_telemetry_token_enabled': bool(UNREAL_TELEMETRY_TOKEN),
                'unreal_telemetry_active_timeout_s': UNREAL_TELEMETRY_ACTIVE_TIMEOUT_S,
                'unreal_telemetry_max_lookback_s': UNREAL_TELEMETRY_MAX_LOOKBACK_S,
                'unreal_telemetry_max_future_s': UNREAL_TELEMETRY_MAX_FUTURE_S,
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


