#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VISION SYSTEM (The Eyes) v3.0 - YOLO11 INTEGRATION
--------------------------------------------------
- Real-time capture (MSS screen or video file/stream)
- YOLOv11 Inference (Ultralytics)
- GPS Projection (Pixel -> GeoCoords)
- Debug Visualization Window
"""

import os
import time
import math
import sys
import ctypes
import uuid
import csv
from ctypes import wintypes
from collections import defaultdict
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
from typing import Optional, Tuple
from dataclasses import dataclass

from geo_projector import GeoProjector
from sppa_semantic_normalizer import normalize_runtime_detection
from sppa_runtime_descriptor import build_sppa_descriptor_payload

# --- CONFIGURACION E IMPORTACIONES ---
from constants import (
    MAVLINK_HUB_HTTP_PORT,
    BRAIN_HTTP_HOST,
    DETECTION_RANGE_M,
    EARTH_RADIUS_M,
    CAMERA_FOV_VERTICAL,
    CAMERA_HEIGHT,
    CAMERA_WIDTH,
    TERRAIN_ELEVATION_MSL,
    SYSTEM_MODE,
    YOLO_CONF_THRESHOLD,
    VISION_CAMERA_VFOV_DEG,
    VISION_CAMERA_MOUNT_ROLL_DEG,
    VISION_CAMERA_MOUNT_PITCH_DEG,
    VISION_CAMERA_MOUNT_YAW_DEG,
    VISION_CAPTURE_EXPECT_WIDTH,
    VISION_CAPTURE_EXPECT_HEIGHT,
    VISION_CAPTURE_WINDOW_TITLE,
    VISION_CAPTURE_WINDOW_CLASS,
    VISION_CAPTURE_WINDOW_EXACT,
    VISION_CAPTURE_WINDOW_FOCUS,
    VISION_CAPTURE_WINDOW_CLICK_FOCUS,
    VISION_CAPTURE_WINDOW_TOPMOST,
    VISION_CAPTURE_WINDOW_METHOD,
    VISION_CAPTURE_MONITOR,
    VISION_CAPTURE_LEFT,
    VISION_CAPTURE_TOP,
    VISION_CAPTURE_WIDTH,
    VISION_CAPTURE_HEIGHT,
    VISION_SOURCE,
    VISION_VIDEO_PATH,
    VISION_VIDEO_LOOP,
    VISION_VIDEO_REOPEN_SLEEP_S,
    VISION_DEBUG_TITLE,
    VISION_DEBUG_WINDOW,
    VISION_DEBUG_SCALE,
    VISION_DEBUG_DOCK,
    VISION_DEBUG_DOCK_GAP_PX,
    VISION_DEBUG_TOPMOST,
    VISION_TARGET_FPS,
    VISION_OVERLAY_MAX_OBS,
    VISION_OVERLAY_MODE,
    VISION_PAPER_OVERLAY_BARS,
    VISION_PAPER_OVERLAY_SHOW_FPS,
    VISION_PAPER_OVERLAY_TITLE,
    VISION_PAPER_OVERLAY_ALPHA,
    VISION_PAPER_OVERLAY_TOP_H,
    VISION_PAPER_OVERLAY_BOTTOM_H,
    VISION_PAPER_OVERLAY_TEXT_SCALE,
    VISION_PAPER_OVERLAY_LABEL_SCALE,
    VISION_PAPER_OVERLAY_LINE_THICKNESS,
    VISION_DET_CONF,
    VISION_PUBLISH_CONF,
    VISION_MIN_AGL_TO_PUBLISH_M,
    VISION_MIN_BOX_HEIGHT_PX,
    VISION_MIN_BOX_AREA_FRAC,
    VISION_MAX_BOX_AREA_FRAC,
    VISION_MAX_BOX_AREA_FRAC_BIKER,
    VISION_MAX_BOX_AREA_FRAC_COW,
    VISION_MAX_BOX_AREA_FRAC_TOWER,
    VISION_FPS_EMA_ALPHA,
    VISION_BBOX_MIN_SIDE_PX,
    VISION_MIN_SEEN_TO_PUBLISH,
    VISION_MIN_SEEN_TO_PUBLISH_BIKER,
    VISION_MIN_SEEN_TO_PUBLISH_COW,
    VISION_MIN_SEEN_TO_PUBLISH_TOWER,
    VISION_TARGET_CLASS_NAMES,
    VISION_TARGET_CLASS_FALLBACK_NAMES,
    VISION_YOLOE_ENABLE,
    VISION_YOLOE_CLASS_NAMES,
    VISION_SPPA_METRIC_FOOTPRINT_ENABLE,
    VISION_SPPA_DESCRIPTOR_ENABLE,
    VISION_SPPA_DESCRIPTOR_MAX_BYTES,
    VISION_SPPA_MASK_MAX_POINTS,
    VISION_CLASS_ALIASES,
    OBS_STATIC_CLASS_NAMES,
    VISION_YOLO_MODEL,
    OBSTACLE_TOKEN,
    VISION_TRACK_TTL_S,
    VISION_TRACK_HOLD_S,
    VISION_SMOOTH_TAU_S,
    VISION_TRACK_DENOM_EPS,
    VISION_TRACK_SMOOTH_DENOM_EPS,
    VISION_TRACK_COS_DENOM_EPS,
    VISION_TRACK_MATCH_MAX_PX,
    VISION_TRACK_MATCH_MAX_DIST_M,
    VISION_STATIC_TRACK_MATCH_MAX_DIST_M,
    VISION_STATIC_DIST_MAX_STEP_M,
    VISION_STATIC_DIST_RATE_MPS,
    VISION_TRACK_MAX_ACTIVE,
    VISION_DYNAMIC_CLUSTER_ENABLE,
    VISION_DYNAMIC_CLUSTER_CLASS_NAMES,
    VISION_DYNAMIC_CLUSTER_GEO_M,
    VISION_DYNAMIC_CLUSTER_DIST_M,
    VISION_MAX_OBS_PER_FRAME,
    VISION_HEARTBEAT_S,
    OBSTACLE_TOKEN_REQUIRED,
    VISION_IGNORE_BOTTOM_PX,
    VISION_IGNORE_BOTTOM_FRAC,
    VISION_IGNORE_TOP_PX,
    VISION_IGNORE_TOP_FRAC,
    AUDIT_VISION_FRAME_EVERY_N,
    AUDIT_VISION_ONLY_WITH_DETS,
    AUDIT_VISION_MAX_DET_DETAILS,
    AUDIT_VISION_JPEG_QUALITY,
    VISION_TELEMETRY_TIMEOUT_S,
    VISION_TELEMETRY_REPLAY_FILE,
    VISION_TELEMETRY_REPLAY_POST_ENABLE,
    VISION_VIDEO_ROTATE_DEG,
    VISION_VIDEO_LINK_URL,
    VISION_IMGSZ,
    VISION_SLEEP_NO_TELEMETRY_S,
    VISION_SLEEP_NO_WINDOW_S,
    VISION_SLEEP_INVALID_MONITOR_S,
    VISION_SLEEP_NO_MONITOR_S,
    VISION_POST_TIMEOUT_S,
    VISION_GUI_WAITKEY_MS,
    VISION_PROCESS_PRIORITY,
    VISION_MIN_DT_S_FOR_FPS,
    VISION_HEIGHT_ERR_MIN_M,
    VISION_HEIGHT_ERR_SLOPE,
    VISION_HEIGHT_CLAMP_M,
    VISION_DEBUG_BBOX_COLOR,
    VISION_DEBUG_BBOX_THICKNESS,
    VISION_DEBUG_BBOX_LABEL_SCALE,
    VISION_DEBUG_BBOX_LABEL_THICKNESS,
    VISION_DEBUG_BBOX_LABEL_COLOR,
    VISION_DEBUG_BBOX_BASE_OUTLINE_COLOR,
    VISION_DEBUG_BBOX_BASE_OUTLINE_THICKNESS,
    VISION_DEBUG_OVERLAY_X0,
    VISION_DEBUG_OVERLAY_Y0,
    VISION_DEBUG_OVERLAY_LINE_STEP,
    VISION_DEBUG_OVERLAY_TEXT_SCALE,
    VISION_DEBUG_OVERLAY_TEXT_COLOR,
    VISION_DEBUG_OVERLAY_OUTLINE_THICKNESS,
    VISION_DEBUG_OVERLAY_TEXT_THICKNESS,
    VISION_DEBUG_OVERLAY_OUTLINE_COLOR,
    VISION_DEBUG_FOOTER_OVERLAY_COLOR,
    VISION_DEBUG_FOOTER_OVERLAY_ALPHA,
    VISION_DEBUG_FOOTER_LINE_COLOR,
    VISION_DEBUG_FOOTER_LINE_THICKNESS,
    VISION_DEBUG_FOOTER_LABEL_SCALE,
    VISION_DEBUG_FOOTER_LABEL_THICKNESS,
    VISION_DEBUG_FOOTER_LABEL_X0,
    VISION_DEBUG_FOOTER_LABEL_Y_OFFSET,
    MAVLINK_UNKNOWN_DISTANCE_M,
    VISION_RECORD_ENABLE,
    VISION_RECORD_PATH,
    VISION_RECORD_FPS,
    VISION_RECORD_CODEC,
    VISION_RECORD_MAX_SECONDS,
    VISION_DETECTIONS_LOG_INTERVAL_S,
    VISION_DEBUG_SCALE_EPS,
    GEOMETRY_COS_LAT_EPS,
    GEOMETRY_EPS,
    GEOMETRY_UNIT_EPS,
    GEOMETRY_PIXEL_EPS,
    VISION_HEIGHT_DIST_FLOOR_M,
    VISION_PROJECT_CLAMP_TO_MAX_RANGE,
    VISION_PROJECT_MAX_RANGE_MARGIN_M,
)
from zero_trust_audit import ZeroTrustAudit

# --- CONSTANTES DE VISION ---
TARGET_CLASS_NAMES = list(VISION_TARGET_CLASS_NAMES)
YOLOE_CLASS_NAMES = list(VISION_YOLOE_CLASS_NAMES)
YOLOE_ENABLE = bool(VISION_YOLOE_ENABLE)
STATIC_CLASS_KEYS = {
    str(name).strip().lower()
    for name in OBS_STATIC_CLASS_NAMES
    if str(name).strip()
}
DYNAMIC_CLUSTER_CLASS_KEYS = {
    str(name).strip().lower()
    for name in VISION_DYNAMIC_CLUSTER_CLASS_NAMES
    if str(name).strip()
}

# Split detection threshold (model output) and publish threshold (what is sent to Brain).
DETECTION_CONFIDENCE_THRESHOLD = float(VISION_DET_CONF)
PUBLISH_CONFIDENCE_THRESHOLD = float(VISION_PUBLISH_CONF)
MIN_AGL_TO_PUBLISH_M = float(VISION_MIN_AGL_TO_PUBLISH_M)

# Keep recall for small far objects, but reject pathological giant boxes.
MIN_BOX_HEIGHT_PX = float(VISION_MIN_BOX_HEIGHT_PX)
MIN_BOX_AREA_FRAC = float(VISION_MIN_BOX_AREA_FRAC)
MAX_BOX_AREA_FRAC = float(VISION_MAX_BOX_AREA_FRAC)
MAX_BOX_AREA_FRAC_BIKER = float(VISION_MAX_BOX_AREA_FRAC_BIKER)
MAX_BOX_AREA_FRAC_COW = float(VISION_MAX_BOX_AREA_FRAC_COW)
MAX_BOX_AREA_FRAC_TOWER = float(VISION_MAX_BOX_AREA_FRAC_TOWER)

# Zero-trust publish gate: require repeated observations before Brain ingestion.
MIN_SEEN_TO_PUBLISH = int(VISION_MIN_SEEN_TO_PUBLISH)
MIN_SEEN_TO_PUBLISH_BIKER = int(VISION_MIN_SEEN_TO_PUBLISH_BIKER)
MIN_SEEN_TO_PUBLISH_COW = int(VISION_MIN_SEEN_TO_PUBLISH_COW)
MIN_SEEN_TO_PUBLISH_TOWER = int(VISION_MIN_SEEN_TO_PUBLISH_TOWER)

TRACK_TTL_S = float(VISION_TRACK_TTL_S)
TRACK_HOLD_S = float(VISION_TRACK_HOLD_S)
SMOOTH_TAU_S = float(VISION_SMOOTH_TAU_S)
TRACK_MATCH_MAX_PX = float(VISION_TRACK_MATCH_MAX_PX)
TRACK_MATCH_MAX_DIST_M = float(VISION_TRACK_MATCH_MAX_DIST_M)
STATIC_TRACK_MATCH_MAX_DIST_M = float(VISION_STATIC_TRACK_MATCH_MAX_DIST_M)
STATIC_DIST_MAX_STEP_M = float(VISION_STATIC_DIST_MAX_STEP_M)
STATIC_DIST_RATE_MPS = float(VISION_STATIC_DIST_RATE_MPS)
PROJECT_CLAMP_TO_MAX_RANGE = bool(VISION_PROJECT_CLAMP_TO_MAX_RANGE)
PROJECT_MAX_RANGE_MARGIN_M = float(VISION_PROJECT_MAX_RANGE_MARGIN_M)
TRACK_MAX_ACTIVE = int(VISION_TRACK_MAX_ACTIVE)
DYNAMIC_CLUSTER_ENABLE = bool(VISION_DYNAMIC_CLUSTER_ENABLE)
DYNAMIC_CLUSTER_GEO_M = float(VISION_DYNAMIC_CLUSTER_GEO_M)
DYNAMIC_CLUSTER_DIST_M = float(VISION_DYNAMIC_CLUSTER_DIST_M)
MAX_OBS_PER_FRAME = int(VISION_MAX_OBS_PER_FRAME)
HEARTBEAT_S = float(VISION_HEARTBEAT_S)
IGNORE_BOTTOM_PX = int(VISION_IGNORE_BOTTOM_PX)
IGNORE_BOTTOM_FRAC = float(VISION_IGNORE_BOTTOM_FRAC)
IGNORE_TOP_PX = int(VISION_IGNORE_TOP_PX)
IGNORE_TOP_FRAC = float(VISION_IGNORE_TOP_FRAC)
AUDIT_VISION_FRAME_EVERY_N = int(AUDIT_VISION_FRAME_EVERY_N)
AUDIT_VISION_ONLY_WITH_DETS = bool(AUDIT_VISION_ONLY_WITH_DETS)
AUDIT_VISION_MAX_DET_DETAILS = int(AUDIT_VISION_MAX_DET_DETAILS)
AUDIT_VISION_JPEG_QUALITY = int(AUDIT_VISION_JPEG_QUALITY)

MODEL_PATH = str(VISION_YOLO_MODEL)

BRAIN_URL = f"http://{BRAIN_HTTP_HOST}:{MAVLINK_HUB_HTTP_PORT}"
TELEMETRY_URL = f"{BRAIN_URL}/api/state/latest"
OBSTACLES_URL = f"{BRAIN_URL}/api/obstacles"

def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] [VISION-YOLO] {msg}", flush=True)


def _truthy(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

def _parse_class_aliases(items) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for item in items:
        text = str(item).strip()
        if not text or ":" not in text:
            continue
        raw, canonical = text.split(":", 1)
        raw = raw.strip().lower()
        canonical = canonical.strip()
        if raw and canonical:
            aliases[raw] = canonical
    return aliases

CLASS_ALIASES = _parse_class_aliases(VISION_CLASS_ALIASES)
SPPA_SEMANTIC_META_KEYS = (
    "range_clamped",
    "detector_type",
    "canonical_type",
    "sppa_tag",
    "sppa_archetype",
    "sppa_match",
    "sppa_claim_status",
    "sppa_conservative",
    "world_m",
    "world_north_m",
    "world_east_m",
    "world_up_m",
    "yaw_deg",
    "heading_deg",
    "sppa_yaw_source",
    "sppa_yaw_ambiguous",
    "sppa_footprint_m",
    "sppa_footprint_source",
    "sppa_metric_dims_m",
    "sppa_scale_source",
    "sppa_shape_policy",
    "sppa_descriptor_id",
    "sppa_descriptor_json",
    "sppa_descriptor_error",
)
SPPA_DYNAMIC_META_KEYS = (
    "range_clamped",
    "world_m",
    "world_north_m",
    "world_east_m",
    "world_up_m",
    "yaw_deg",
    "heading_deg",
    "sppa_yaw_source",
    "sppa_yaw_ambiguous",
    "sppa_footprint_m",
    "sppa_footprint_source",
    "sppa_metric_dims_m",
    "sppa_scale_source",
    "sppa_shape_policy",
    "sppa_descriptor_id",
    "sppa_descriptor_json",
    "sppa_descriptor_error",
)


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
    semantic_meta: dict | None = None


class VisionSystem:
    @staticmethod
    def _set_process_priority() -> None:
        priority = str(VISION_PROCESS_PRIORITY or "").strip().lower()
        if not priority or os.name != "nt":
            return
        priority_map = {
            "normal": 0x00000020,
            "above_normal": 0x00008000,
            "abovenormal": 0x00008000,
            "high": 0x00000080,
        }
        priority_class = priority_map.get(priority)
        if priority_class is None:
            log(f"[WARN] Prioridad de vision desconocida: {priority!r}")
            return
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            handle = kernel32.GetCurrentProcess()
            if not kernel32.SetPriorityClass(handle, int(priority_class)):
                raise ctypes.WinError(ctypes.get_last_error())
            log(f"[PERF] Vision process priority={priority}")
        except Exception as exc:
            log(f"[WARN] No se pudo ajustar prioridad de vision: {exc}")

    @staticmethod
    def _canonical_class_name(class_name: str) -> str:
        key = str(class_name).strip().lower()
        return CLASS_ALIASES.get(key, str(class_name).strip())

    def __init__(self):
        log("Inicializando sistema de vision YOLOv11...")

        # Avoid coordinate mismatches on high-DPI displays (important for window/ROI capture).
        self._set_windows_dpi_aware()
        self._set_process_priority()

        # 1. Cargar Modelo
        try:
            self.model = YOLO(MODEL_PATH)
            log(f"Modelo cargado correctamente: {MODEL_PATH}")
            self._yoloe_enabled = bool(YOLOE_ENABLE)
            if self._yoloe_enabled:
                if hasattr(self.model, "set_classes"):
                    prompts = list(YOLOE_CLASS_NAMES)
                    self.model.set_classes(prompts)
                    log(f"YOLOE prompts activados: {prompts}")
                else:
                    log("[WARN] PORCE_YOLOE_ENABLE=1 pero el modelo no soporta set_classes(); se usara como YOLO cerrado.")
                    self._yoloe_enabled = False

            # Resolve class indices by name so this works for both custom-trained and COCO weights.
            names = self.model.names
            if isinstance(names, dict):
                id_by_name = {str(v): int(k) for k, v in names.items()}
            else:
                id_by_name = {str(v): int(i) for i, v in enumerate(list(names))}

            target_names = list(YOLOE_CLASS_NAMES) if self._yoloe_enabled else list(TARGET_CLASS_NAMES)
            # If the custom names are missing, fall back to known COCO labels.
            if (not self._yoloe_enabled) and not any(n in id_by_name for n in target_names):
                target_names = list(VISION_TARGET_CLASS_FALLBACK_NAMES)

            self._target_class_ids = sorted({id_by_name[n] for n in target_names if n in id_by_name})
            log(f"Clases objetivo: {target_names} -> ids={self._target_class_ids}")
            # Warmup
            log("Realizando inferencia de calentamiento (Warmup)...")
            self.model.predict(
                source=np.zeros(
                    (max(1, int(CAMERA_HEIGHT)), max(1, int(CAMERA_WIDTH)), 3),
                    dtype=np.uint8,
                ),
                verbose=False,
            )
            log(
                "Filtros Vision: "
                f"det_conf={DETECTION_CONFIDENCE_THRESHOLD:.2f} "
                f"pub_conf={PUBLISH_CONFIDENCE_THRESHOLD:.2f} "
                f"min_agl_pub={MIN_AGL_TO_PUBLISH_M:.1f}m "
                f"min_h={MIN_BOX_HEIGHT_PX:.1f}px "
                f"min_area={MIN_BOX_AREA_FRAC:.6f} "
                f"max_area_global={MAX_BOX_AREA_FRAC:.3f} "
                f"max_area[biker]={MAX_BOX_AREA_FRAC_BIKER:.3f} "
                f"max_area[cow]={MAX_BOX_AREA_FRAC_COW:.3f} "
                f"max_area[tower]={MAX_BOX_AREA_FRAC_TOWER:.3f} "
                f"min_seen_default={MIN_SEEN_TO_PUBLISH} "
                f"track_match_px={TRACK_MATCH_MAX_PX:.1f} "
                f"track_match_dist={TRACK_MATCH_MAX_DIST_M:.1f}m "
                f"track_match_dist_static={STATIC_TRACK_MATCH_MAX_DIST_M:.1f}m "
                f"static_dist_step={STATIC_DIST_MAX_STEP_M:.1f}m "
                f"static_dist_rate={STATIC_DIST_RATE_MPS:.1f}mps "
                f"project_clamp={int(PROJECT_CLAMP_TO_MAX_RANGE)} "
                f"project_range_margin={PROJECT_MAX_RANGE_MARGIN_M:.1f}m "
                f"track_max_active={int(TRACK_MAX_ACTIVE)} "
                f"ignore_bottom_px={IGNORE_BOTTOM_PX} "
                f"ignore_bottom_frac={IGNORE_BOTTOM_FRAC:.3f}"
            )
        except Exception as e:
            log(f"ERROR CRITICO cargando modelo: {e}")
            sys.exit(1)

        # Projection config (defaults tuned for SIM mode).
        # Camera tilt: 30deg down from horizon => mount_pitch=-30deg unless overridden.
        self._camera_vfov_deg = float(VISION_CAMERA_VFOV_DEG)
        self._mount_roll_deg = float(VISION_CAMERA_MOUNT_ROLL_DEG)
        self._mount_pitch_deg = float(VISION_CAMERA_MOUNT_PITCH_DEG)
        self._mount_yaw_deg = float(VISION_CAMERA_MOUNT_YAW_DEG)
        self.projector = GeoProjector()
        self.sct = None
        self.session = requests.Session()
        self._source_session_id = f"vision-{uuid.uuid4().hex}"
        self._source_sequence = 0
        self._obstacle_token = str(OBSTACLE_TOKEN)
        if OBSTACLE_TOKEN_REQUIRED and not self._obstacle_token:
            log("[WARN] PORCE_OBSTACLE_TOKEN_REQUIRED=1 pero PORCE_OBSTACLE_TOKEN no esta definido; Brain rechazara /api/obstacles.")

        self._vision_source = str(VISION_SOURCE or "").strip().upper()
        if not self._vision_source:
            self._vision_source = "SCREEN_CAPTURE"
        self._video_capture = None
        self._video_path = str(VISION_VIDEO_PATH or "").strip()
        self._video_loop = bool(VISION_VIDEO_LOOP)
        # Replay determinista de vuelo real: filas frame->pose del CSV (lazy).
        self._telemetry_replay_rows = None
        # Enlace de video simulado: frames JPEG por HTTP con indice por frame.
        self._video_link = self._vision_source == "VIDEO_LINK"
        self._video_link_url = str(VISION_VIDEO_LINK_URL or "").strip().rstrip("/")
        self._video_link_frame_idx = -1
        self._video_reopen_sleep_s = max(0.05, float(VISION_VIDEO_REOPEN_SLEEP_S))

        # --- Capture configuration ---
        # Expected capture in SIM: Unreal "Play In New Window" at 640x640.
        self._expect_w = int(VISION_CAPTURE_EXPECT_WIDTH)
        self._expect_h = int(VISION_CAPTURE_EXPECT_HEIGHT)

        # Preferred: capture by window title (robust against being behind other windows).
        self._capture_window_title = str(VISION_CAPTURE_WINDOW_TITLE).strip()
        self._capture_window_class = str(VISION_CAPTURE_WINDOW_CLASS).strip()
        self._capture_window_exact = _truthy(VISION_CAPTURE_WINDOW_EXACT)
        self._capture_window_focus = _truthy(VISION_CAPTURE_WINDOW_FOCUS)
        self._capture_window_click_focus = _truthy(VISION_CAPTURE_WINDOW_CLICK_FOCUS)
        self._capture_window_topmost = _truthy(VISION_CAPTURE_WINDOW_TOPMOST)
        self._capture_window_method = str(VISION_CAPTURE_WINDOW_METHOD).strip().lower() or "mss"
        self._capture_hwnd = None
        self._printwindow_warned = False
        self._capture_focus_click_done = False

        if self._vision_source == "VIDEO_LINK":
            self._capture_mode = "video"
            self.monitor = None
            if not self._video_link_url:
                log("[ERROR] VISION_SOURCE=VIDEO_LINK requiere PORCE_VISION_VIDEO_LINK_URL.")
                sys.exit(2)
            log(f"Zona de captura (video-link): url={self._video_link_url!r}")
        elif self._vision_source in {"VIDEO", "VIDEO_FILE", "VIDEO_STREAM"}:
            self._capture_mode = "video"
            self.monitor = None
            if not self._video_path:
                log(
                    "[ERROR] VISION_SOURCE requiere video pero PORCE_VISION_VIDEO_PATH esta vacio. "
                    "Ejemplo: set PORCE_VISION_VIDEO_PATH=D:\\ruta\\video.mp4"
                )
                sys.exit(2)
            if not self._open_video_capture():
                sys.exit(2)
            log(
                "Zona de captura (video): "
                f"path={self._video_path!r} loop={int(self._video_loop)}"
            )
            cap_w = int(self._video_capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            cap_h = int(self._video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            if cap_w > 0 and cap_h > 0:
                log(f"[CAPTURE] Video ready {cap_w}x{cap_h}")
        else:
            self.sct = mss.mss()
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
                monitor_idx = int(VISION_CAPTURE_MONITOR)
                self.monitor = self.sct.monitors[monitor_idx]
                roi_left = VISION_CAPTURE_LEFT
                roi_top = VISION_CAPTURE_TOP
                roi_w = VISION_CAPTURE_WIDTH
                roi_h = VISION_CAPTURE_HEIGHT
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
        self._debug_title = str(VISION_DEBUG_TITLE).strip() or "YOLO V11 VISION DEBUG"
        self._debug_enabled = _truthy(VISION_DEBUG_WINDOW)
        self._debug_scale = float(VISION_DEBUG_SCALE)
        self._debug_dock = _truthy(VISION_DEBUG_DOCK)
        if str(VISION_DEBUG_DOCK).strip() == "":
            self._debug_dock = (self._capture_mode == "window")
        self._debug_dock_gap_px = int(float(VISION_DEBUG_DOCK_GAP_PX))
        self._debug_topmost = _truthy(VISION_DEBUG_TOPMOST)
        self._debug_last_dock_anchor = None
        self._debug_last_size = None

        # Vision loop rate control (0 = as fast as possible).
        self._target_fps = float(VISION_TARGET_FPS)
        self._record_enabled = bool(VISION_RECORD_ENABLE)
        self._record_path = str(VISION_RECORD_PATH).strip()
        self._record_fps = max(1.0, float(VISION_RECORD_FPS))
        self._record_codec = (str(VISION_RECORD_CODEC).strip() or "mp4v")[:4]
        self._record_max_seconds = max(0.0, float(VISION_RECORD_MAX_SECONDS))
        self._record_writer = None
        self._record_frame_size = None
        self._record_frame_count = 0

        # FPS measurement (EMA).
        self._last_frame_ts = None
        self._fps_ema = 0.0

        if self._record_enabled:
            log(
                "[REC] YOLO overlay recording enabled: "
                f"path={self._record_path} fps={self._record_fps:.1f} "
                f"codec={self._record_codec} max_s={self._record_max_seconds:.1f}"
            )

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
        self._overlay_max_obs = int(float(VISION_OVERLAY_MAX_OBS))
        self._overlay_mode = str(VISION_OVERLAY_MODE or "paper").strip().lower()
        if self._overlay_mode not in {"paper", "debug", "off"}:
            self._overlay_mode = "paper"

        # Simple temporal stabilizer (reduces bbox/telemetry jitter in the projected lat/lon).
        self._tracks: dict[int, VisionTrack] = {}
        self._next_track_id: int = 1
        # Ensure we log once when the PIE window becomes available.
        self._capture_found_logged = bool(self._capture_hwnd and self.monitor)
        self._capture_size_warned: Optional[Tuple[int, int]] = None
        self._capture_crop_logged: Optional[Tuple[int, int, int, int, int, int]] = None

        # Zero-trust audit sink (shared session root via PORCE_AUDIT_ROOT).
        self._audit = ZeroTrustAudit(component="vision")
        if self._audit.enabled:
            self._audit.log_event(
                "vision_config",
                det_conf=float(DETECTION_CONFIDENCE_THRESHOLD),
                publish_conf=float(PUBLISH_CONFIDENCE_THRESHOLD),
                min_agl_to_publish_m=float(MIN_AGL_TO_PUBLISH_M),
                min_box_height_px=float(MIN_BOX_HEIGHT_PX),
                min_box_area_frac=float(MIN_BOX_AREA_FRAC),
                max_box_area_frac=float(MAX_BOX_AREA_FRAC),
                max_box_area_frac_biker=float(MAX_BOX_AREA_FRAC_BIKER),
                max_box_area_frac_cow=float(MAX_BOX_AREA_FRAC_COW),
                max_box_area_frac_tower=float(MAX_BOX_AREA_FRAC_TOWER),
                min_seen_to_publish=int(MIN_SEEN_TO_PUBLISH),
                min_seen_biker=int(MIN_SEEN_TO_PUBLISH_BIKER),
                min_seen_cow=int(MIN_SEEN_TO_PUBLISH_COW),
                min_seen_tower=int(MIN_SEEN_TO_PUBLISH_TOWER),
                track_match_max_px=float(TRACK_MATCH_MAX_PX),
                track_match_max_dist_m=float(TRACK_MATCH_MAX_DIST_M),
                static_track_match_max_dist_m=float(STATIC_TRACK_MATCH_MAX_DIST_M),
                static_dist_max_step_m=float(STATIC_DIST_MAX_STEP_M),
                static_dist_rate_mps=float(STATIC_DIST_RATE_MPS),
                static_classes=list(STATIC_CLASS_KEYS),
                project_clamp_to_max_range=bool(PROJECT_CLAMP_TO_MAX_RANGE),
                project_max_range_margin_m=float(PROJECT_MAX_RANGE_MARGIN_M),
                track_max_active=int(TRACK_MAX_ACTIVE),
                dynamic_cluster_enable=bool(DYNAMIC_CLUSTER_ENABLE),
                dynamic_cluster_classes=list(DYNAMIC_CLUSTER_CLASS_KEYS),
                dynamic_cluster_geo_m=float(DYNAMIC_CLUSTER_GEO_M),
                dynamic_cluster_dist_m=float(DYNAMIC_CLUSTER_DIST_M),
                max_obs_per_frame=int(MAX_OBS_PER_FRAME),
                ignore_bottom_px=int(IGNORE_BOTTOM_PX),
                ignore_bottom_frac=float(IGNORE_BOTTOM_FRAC),
                vision_source=str(self._vision_source),
                capture_mode=str(self._capture_mode),
                capture_title=str(self._capture_window_title),
                capture_class=str(self._capture_window_class),
                video_path=str(self._video_path),
                video_loop=bool(self._video_loop),
                expect_w=int(self._expect_w),
                expect_h=int(self._expect_h),
                target_fps=float(self._target_fps),
                model_path=str(MODEL_PATH),
                obstacle_token_required=bool(OBSTACLE_TOKEN_REQUIRED),
                obstacle_token_enabled=bool(self._obstacle_token),
                audit_frame_every_n=int(AUDIT_VISION_FRAME_EVERY_N),
                audit_only_with_dets=bool(AUDIT_VISION_ONLY_WITH_DETS),
                audit_max_det_details=int(AUDIT_VISION_MAX_DET_DETAILS),
            )
            log(
                "Audit vision enabled: "
                f"frame_every_n={AUDIT_VISION_FRAME_EVERY_N} "
                f"only_with_dets={int(AUDIT_VISION_ONLY_WITH_DETS)}"
            )

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

                score = 0
                title_l = title.lower()
                if "preview" in title_l:
                    score += 30
                if "unreal editor" not in title_l:
                    score += 20
                if target_l and title_l.startswith(target_l):
                    score += 10
                if "airtraffic" in title_l:
                    score += 5
                matches.append((score, hwnd))
            except Exception:
                pass
            return True

        try:
            user32.EnumWindows(EnumProc(_enum), 0)
        except Exception:
            return None

        if not matches:
            return None
        matches.sort(key=lambda item: item[0], reverse=True)
        return matches[0][1]

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
            if self._capture_window_click_focus and not self._capture_focus_click_done:
                try:
                    rect = wintypes.RECT()
                    if user32.GetClientRect(hwnd, ctypes.byref(rect)):
                        pt = wintypes.POINT(0, 0)
                        if user32.ClientToScreen(hwnd, ctypes.byref(pt)):
                            center_x = int(pt.x + max(1, int(rect.right - rect.left)) // 2)
                            center_y = int(pt.y + max(1, int(rect.bottom - rect.top)) // 2)
                            user32.SetCursorPos(center_x, center_y)
                            MOUSEEVENTF_LEFTDOWN = 0x0002
                            MOUSEEVENTF_LEFTUP = 0x0004
                            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                            self._capture_focus_click_done = True
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

    def _printwindow_grab(self, hwnd):
        """Capture the window's client area via PrintWindow(PW_RENDERFULLCONTENT).

        Unlike MSS screen-region capture, this reads the window's own DWM
        surface, so frames stay clean even when other windows cover it.
        Returns a BGR ndarray (already cropped to expected size if larger),
        or None on failure.
        """
        if os.name != "nt" or not hwnd:
            return None
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        PW_RENDERFULLCONTENT = 0x00000002

        wrect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(wrect)):
            return None
        ww = int(wrect.right - wrect.left)
        wh = int(wrect.bottom - wrect.top)
        crect = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(crect)):
            return None
        cw = int(crect.right - crect.left)
        ch = int(crect.bottom - crect.top)
        if ww <= 0 or wh <= 0 or cw <= 0 or ch <= 0:
            return None
        pt = wintypes.POINT(0, 0)
        if not user32.ClientToScreen(hwnd, ctypes.byref(pt)):
            return None
        off_x = int(pt.x - wrect.left)
        off_y = int(pt.y - wrect.top)

        hdc_win = user32.GetWindowDC(hwnd)
        if not hdc_win:
            return None

        # PrintWindow paints at the target window's own DPI scale, while this
        # process (if per-monitor aware) sees physical metrics. Rescale all
        # geometry by win_dpi/dc_dpi so the bitmap matches the painted size.
        try:
            win_dpi = int(user32.GetDpiForWindow(hwnd)) or 96
        except Exception:
            win_dpi = 96
        try:
            LOGPIXELSX = 88
            dc_dpi = int(ctypes.windll.gdi32.GetDeviceCaps(hdc_win, LOGPIXELSX)) or 96
        except Exception:
            dc_dpi = 96
        if win_dpi != dc_dpi and win_dpi > 0 and dc_dpi > 0:
            f = float(win_dpi) / float(dc_dpi)
            ww = max(1, int(round(ww * f)))
            wh = max(1, int(round(wh * f)))
            cw = max(1, int(round(cw * f)))
            ch = max(1, int(round(ch * f)))
            off_x = int(round(off_x * f))
            off_y = int(round(off_y * f))
        img = None
        hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_win, ww, wh)
        old_bmp = None
        try:
            old_bmp = gdi32.SelectObject(hdc_mem, hbmp)
            if not user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT):
                return None

            class _BMIH(ctypes.Structure):
                _fields_ = [
                    ("biSize", wintypes.DWORD),
                    ("biWidth", ctypes.c_long),
                    ("biHeight", ctypes.c_long),
                    ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", ctypes.c_long),
                    ("biYPelsPerMeter", ctypes.c_long),
                    ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD),
                ]

            bmi = _BMIH()
            bmi.biSize = ctypes.sizeof(_BMIH)
            bmi.biWidth = ww
            bmi.biHeight = -wh  # top-down rows
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0
            buf = ctypes.create_string_buffer(ww * wh * 4)
            if not gdi32.GetDIBits(hdc_mem, hbmp, 0, wh, buf, ctypes.byref(bmi), 0):
                return None
            full = np.frombuffer(buf, dtype=np.uint8).reshape(wh, ww, 4)[:, :, :3]
            img = full[off_y:off_y + ch, off_x:off_x + cw].copy()  # BGR client area
        finally:
            # Deselect hbmp before deleting it: DeleteObject silently fails on a
            # bitmap still selected into a DC, leaking GDI handles every frame.
            if old_bmp is not None:
                gdi32.SelectObject(hdc_mem, old_bmp)
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(hwnd, hdc_win)

        # Same crop policy as _window_capture_region: center-x, bottom-aligned.
        exp_w = max(1, int(self._expect_w))
        exp_h = max(1, int(self._expect_h))
        h, w = img.shape[:2]
        if w > exp_w or h > exp_h:
            x_off = max(0, (w - exp_w) // 2)
            y_off = max(0, h - exp_h)
            img = img[y_off:y_off + exp_h, x_off:x_off + exp_w]
        return np.ascontiguousarray(img)

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

    def _pump_debug_status(self, message: str) -> bool:
        """Keep the OpenCV debug window responsive while Vision is waiting."""
        if not self._debug_enabled:
            return False
        try:
            w = max(320, int(self._expect_w or CAMERA_WIDTH or 640))
            h = max(240, int(self._expect_h or CAMERA_HEIGHT or 480))
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            lines = [
                "YOLO V11 VISION DEBUG",
                str(message),
                f"capture={self._capture_mode} title={self._capture_window_title or '-'}",
            ]
            y = 34
            for idx, line in enumerate(lines):
                color = (0, 220, 255) if idx == 0 else (220, 220, 220)
                cv2.putText(
                    frame,
                    line[:96],
                    (18, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    color,
                    1,
                    cv2.LINE_AA,
                )
                y += 28
            cv2.imshow(self._debug_title, frame)
            return bool(cv2.waitKey(max(1, int(VISION_GUI_WAITKEY_MS))) & 0xFF == ord("q"))
        except Exception:
            return False

    def _ensure_record_writer(self, width: int, height: int) -> bool:
        if not self._record_enabled:
            return False
        if self._record_writer is not None and self._record_frame_size == (int(width), int(height)):
            return True

        try:
            if self._record_writer is not None:
                self._record_writer.release()
        except Exception:
            pass
        self._record_writer = None
        self._record_frame_size = None

        try:
            out_dir = os.path.dirname(os.path.abspath(self._record_path))
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            codec = (self._record_codec + "mp4v")[:4]
            writer = cv2.VideoWriter(
                self._record_path,
                cv2.VideoWriter_fourcc(*codec),
                float(self._record_fps),
                (int(width), int(height)),
            )
            if not writer.isOpened():
                log(f"[REC][WARN] No se pudo abrir VideoWriter: {self._record_path}")
                self._record_enabled = False
                return False
            self._record_writer = writer
            self._record_frame_size = (int(width), int(height))
            log(f"[REC] Writing YOLO overlay video {int(width)}x{int(height)} -> {self._record_path}")
            return True
        except Exception as exc:
            log(f"[REC][WARN] Error inicializando VideoWriter: {exc}")
            self._record_enabled = False
            return False

    def _record_overlay_frame(self, image_bgr) -> None:
        if not self._record_enabled or image_bgr is None:
            return
        if self._record_max_seconds > 0.0:
            max_frames = int(math.ceil(float(self._record_max_seconds) * float(self._record_fps)))
            if self._record_frame_count >= max_frames:
                try:
                    if self._record_writer is not None:
                        self._record_writer.release()
                        log(f"[REC] YOLO overlay video closed at max duration: {self._record_path} frames={self._record_frame_count}")
                except Exception:
                    pass
                self._record_writer = None
                self._record_frame_size = None
                self._record_enabled = False
                return
        try:
            height, width = image_bgr.shape[:2]
            if not self._ensure_record_writer(int(width), int(height)):
                return
            frame = image_bgr
            if self._record_frame_size != (int(width), int(height)):
                frame = cv2.resize(image_bgr, self._record_frame_size, interpolation=cv2.INTER_LINEAR)
            self._record_writer.write(frame)
            self._record_frame_count += 1
        except Exception as exc:
            log(f"[REC][WARN] Error grabando frame YOLO: {exc}")

    def _window_capture_region(self) -> Optional[dict]:
        if not self.monitor:
            return None
        region = {
            "left": int(self.monitor.get("left", 0) or 0),
            "top": int(self.monitor.get("top", 0) or 0),
            "width": int(self.monitor.get("width", 0) or 0),
            "height": int(self.monitor.get("height", 0) or 0),
        }
        cur_w = int(region["width"])
        cur_h = int(region["height"])
        exp_w = max(1, int(self._expect_w))
        exp_h = max(1, int(self._expect_h))
        if cur_w <= 0 or cur_h <= 0:
            return region
        if cur_w == exp_w and cur_h == exp_h:
            return region
        if cur_w < exp_w or cur_h < exp_h:
            if self._capture_size_warned != (cur_w, cur_h):
                log(
                    f"[WARN] Client area is {cur_w}x{cur_h} but expected {exp_w}x{exp_h}. "
                    "No crop possible (window smaller than expected)."
                )
                self._capture_size_warned = (cur_w, cur_h)
            return region

        # Strict viewport crop: keep bottom (remove top toolbar overflow), center in X.
        x_off = max(0, (cur_w - exp_w) // 2)
        y_off = max(0, cur_h - exp_h)
        cropped = {
            "left": int(region["left"]) + int(x_off),
            "top": int(region["top"]) + int(y_off),
            "width": int(exp_w),
            "height": int(exp_h),
        }
        sig = (cur_w, cur_h, exp_w, exp_h, x_off, y_off)
        if self._capture_crop_logged != sig:
            log(
                f"[CAPTURE] Cropping client {cur_w}x{cur_h} -> {exp_w}x{exp_h} "
                f"(x_off={x_off}, y_off={y_off}, y-bottom aligned)."
            )
            self._capture_crop_logged = sig
        return cropped

    def _open_video_capture(self) -> bool:
        try:
            if self._video_capture is not None:
                self._video_capture.release()
        except Exception:
            pass

        source_raw = str(self._video_path or "").strip()
        source_obj = int(source_raw) if source_raw.isdigit() else source_raw
        cap = cv2.VideoCapture(source_obj)
        if not cap or not cap.isOpened():
            log(f"[ERROR] No se pudo abrir video fuente: {source_raw!r}")
            try:
                if cap:
                    cap.release()
            except Exception:
                pass
            self._video_capture = None
            return False

        self._video_capture = cap
        return True

    def _read_video_frame(self) -> Optional[np.ndarray]:
        if self._video_link:
            frame = self._fetch_link_frame()
        else:
            if self._video_capture is None:
                if not self._open_video_capture():
                    return None

            ok = False
            frame = None
            try:
                ok, frame = self._video_capture.read()
            except Exception:
                ok, frame = False, None

            if not ok or frame is None:
                if not self._video_loop:
                    return None

                reopened = False
                try:
                    if self._video_capture is not None:
                        self._video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ok2, frame2 = self._video_capture.read()
                        if ok2 and frame2 is not None:
                            reopened = True
                            frame = frame2
                except Exception:
                    reopened = False

                if not reopened:
                    if not self._open_video_capture():
                        return None
                    try:
                        ok3, frame3 = self._video_capture.read()
                    except Exception:
                        ok3, frame3 = False, None
                    if not ok3 or frame3 is None:
                        return None
                    frame = frame3

                log("[CAPTURE] EOF video detectado; reiniciando desde el inicio.")

        return self._postprocess_video_frame(frame)

    def _postprocess_video_frame(self, frame) -> Optional[np.ndarray]:
        if frame is None:
            return None

        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        elif frame.ndim == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        # Rotacion declarada del clip (p.ej. metadata rotate=270 en M_20_1RR).
        rot_deg = int(VISION_VIDEO_ROTATE_DEG) % 360
        if rot_deg == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif rot_deg == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif rot_deg == 270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        return frame

    def _fetch_link_frame(self) -> Optional[np.ndarray]:
        # Siguiente frame del enlace de video simulado (JPEG + indice por HTTP).
        try:
            r = self.session.get(f"{self._video_link_url}/api/video/next", timeout=2.0)
            if r.status_code == 204 or not r.content:
                self._video_link_frame_idx = -1
                return None
            if r.status_code != 200:
                return None
            self._video_link_frame_idx = int(r.headers.get("X-Frame-Idx", "-1"))
            arr = np.frombuffer(r.content, dtype=np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception:
            return None

    def get_telemetry(self, frame_idx: Optional[int] = None):
        # Replay determinista: la pose sale del CSV (frame->pose), no del Brain.
        if str(VISION_TELEMETRY_REPLAY_FILE or "").strip():
            return self._get_replay_telemetry(frame_idx)
        try:
            r = self.session.get(TELEMETRY_URL, timeout=float(VISION_TELEMETRY_TIMEOUT_S))
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return None

    def _load_replay_rows(self) -> list:
        if self._telemetry_replay_rows is not None:
            return self._telemetry_replay_rows
        rows = []
        path = str(VISION_TELEMETRY_REPLAY_FILE)
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
        self._telemetry_replay_rows = rows
        log(f"[REPLAY] Telemetria replay cargada: {len(rows)} filas desde {path}")
        return rows

    def _get_replay_telemetry(self, frame_idx: Optional[int]):
        rows = self._load_replay_rows()
        idx = int(frame_idx if frame_idx is not None else 0)
        if idx < 0 or idx >= len(rows):
            # Replay agotado (o enlace sin indice): el bucle espera y no se publica pose.
            return None
        r = rows[idx]
        yaw_deg = float(r["yaw"])
        # Misma convencion que el path en vivo (Brain ATTITUDE yaw: -180..180).
        yaw_wrapped = (yaw_deg + 180.0) % 360.0 - 180.0
        telemetry = {
            "ts": float(r["t_unix"]),
            "active": True,
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "alt": float(r["alt_msl"]),
            "rel_alt": float(r["rel_alt"]),
            "heading": yaw_deg,
            "yaw": yaw_wrapped,
            "roll": float(r["roll"]),
            "pitch": float(r["pitch"]),
            "armed": True,
            "mode": "REPLAY",
            "telemetry_source": "replay",
            "mission_state": "REPLAY",
            "evasion_active": False,
            "failsafe_action_active": "",
        }
        if bool(VISION_TELEMETRY_REPLAY_POST_ENABLE):
            self._post_replay_pose(telemetry)
        return telemetry

    def _post_replay_pose(self, telemetry: dict) -> None:
        # Publica la pose del frame al Brain para que /api/ui/data la exponga al twin.
        try:
            headers = {"X-PORCE-Token": self._obstacle_token} if self._obstacle_token else {}
            self.session.post(
                f"{BRAIN_URL}/api/replay/telemetry",
                json={
                    "lat": telemetry["lat"],
                    "lon": telemetry["lon"],
                    "alt": telemetry["alt"],
                    "rel_alt": telemetry["rel_alt"],
                    "heading": telemetry["heading"],
                    "yaw": telemetry["yaw"],
                    "roll": telemetry["roll"],
                    "pitch": telemetry["pitch"],
                    "mode": "REPLAY",
                    "armed": True,
                },
                headers=headers,
                timeout=0.5,
            )
        except Exception:
            pass

    @staticmethod
    def _alpha_from_dt(dt_s: float) -> float:
        tau = float(SMOOTH_TAU_S)
        if not math.isfinite(tau) or tau <= 0.0:
            return 1.0
        dt = max(0.0, float(dt_s))
        alpha = 1.0 - math.exp(-dt / tau)
        return max(0.0, min(1.0, float(alpha)))

    @staticmethod
    def _safe_float(raw_value, default: float = float("nan")) -> float:
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _haversine_m(lat1, lon1, lat2, lon2) -> float:
        lat1_f = VisionSystem._safe_float(lat1)
        lon1_f = VisionSystem._safe_float(lon1)
        lat2_f = VisionSystem._safe_float(lat2)
        lon2_f = VisionSystem._safe_float(lon2)
        if not (
            math.isfinite(lat1_f) and math.isfinite(lon1_f)
            and math.isfinite(lat2_f) and math.isfinite(lon2_f)
        ):
            return float("inf")
        dlat = math.radians(float(lat2_f) - float(lat1_f))
        dlon = math.radians(float(lon2_f) - float(lon1_f))
        a = (
            math.sin(dlat / 2.0) ** 2
            + math.cos(math.radians(float(lat1_f)))
            * math.cos(math.radians(float(lat2_f)))
            * (math.sin(dlon / 2.0) ** 2)
        )
        c = 2.0 * math.atan2(math.sqrt(max(0.0, a)), math.sqrt(max(0.0, 1.0 - a)))
        return float(EARTH_RADIUS_M) * float(c)

    @staticmethod
    def _bbox_iou(box_a: dict, box_b: dict) -> float:
        if not isinstance(box_a, dict) or not isinstance(box_b, dict):
            return 0.0
        ax1 = VisionSystem._safe_float(box_a.get("x1"))
        ay1 = VisionSystem._safe_float(box_a.get("y1"))
        ax2 = VisionSystem._safe_float(box_a.get("x2"))
        ay2 = VisionSystem._safe_float(box_a.get("y2"))
        bx1 = VisionSystem._safe_float(box_b.get("x1"))
        by1 = VisionSystem._safe_float(box_b.get("y1"))
        bx2 = VisionSystem._safe_float(box_b.get("x2"))
        by2 = VisionSystem._safe_float(box_b.get("y2"))
        values = [ax1, ay1, ax2, ay2, bx1, by1, bx2, by2]
        if not all(math.isfinite(v) for v in values):
            return 0.0
        if ax2 <= ax1 or ay2 <= ay1 or bx2 <= bx1 or by2 <= by1:
            return 0.0
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0
        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        area_a = (ax2 - ax1) * (ay2 - ay1)
        area_b = (bx2 - bx1) * (by2 - by1)
        union = max(float(GEOMETRY_EPS), float(area_a + area_b - inter_area))
        return max(0.0, min(1.0, float(inter_area) / float(union)))

    def _temporal_match_gate_s(self, class_name: str) -> float:
        ttl_s = max(0.05, float(TRACK_TTL_S))
        hold_s = max(0.05, float(TRACK_HOLD_S))
        if self._is_static_class(class_name):
            return min(float(ttl_s), max(float(hold_s) * 3.0, 2.0))
        return min(float(ttl_s), max(float(hold_s), 0.6))

    def _static_dedupe_gates(self, class_name: str) -> tuple[float, float, float, float]:
        class_key = self._class_name_key(class_name)
        base_px = max(6.0, float(TRACK_MATCH_MAX_PX))
        base_dist = max(0.5, float(TRACK_MATCH_MAX_DIST_M))
        if class_key == "cow":
            px_gate = max(6.0, min(float(base_px) * 0.25, 18.0))
            dist_gate = max(0.8, min(float(base_dist) * 0.18, 3.0))
            geo_gate = max(0.8, min(float(base_dist) * 0.14, 2.5))
            iou_gate = 0.38
            return float(px_gate), float(dist_gate), float(geo_gate), float(iou_gate)
        if class_key == "tower":
            px_gate = max(8.0, min(float(base_px) * 0.35, 24.0))
            dist_gate = max(1.0, min(float(base_dist) * 0.25, 4.5))
            geo_gate = max(1.0, min(float(base_dist) * 0.20, 4.0))
            iou_gate = 0.32
            return float(px_gate), float(dist_gate), float(geo_gate), float(iou_gate)
        px_gate = max(6.0, min(float(base_px) * 0.30, 20.0))
        dist_gate = max(0.8, min(float(base_dist) * 0.20, 3.5))
        geo_gate = max(0.8, min(float(base_dist) * 0.16, 3.0))
        iou_gate = 0.35
        return float(px_gate), float(dist_gate), float(geo_gate), float(iou_gate)

    def _static_outlier_link_gates(self, class_name: str) -> tuple[float, float, float, float]:
        class_key = self._class_name_key(class_name)
        if class_key == "cow":
            return 10.0, 2.0, 0.45, 30.0
        if class_key == "tower":
            return 14.0, 3.5, 0.40, 45.0
        return 12.0, 2.5, 0.42, 35.0

    def _is_same_static_detection(self, det_a: dict, det_b: dict) -> bool:
        class_a = self._class_name_key(str(det_a.get("type", "")))
        class_b = self._class_name_key(str(det_b.get("type", "")))
        if class_a != class_b:
            return False
        if not self._is_static_class(class_a):
            return False

        iou = self._bbox_iou(det_a.get("bbox") or {}, det_b.get("bbox") or {})
        cx_a = self._safe_float(det_a.get("cx"))
        cy_a = self._safe_float(det_a.get("cy"))
        cx_b = self._safe_float(det_b.get("cx"))
        cy_b = self._safe_float(det_b.get("cy"))
        if not all(math.isfinite(v) for v in [cx_a, cy_a, cx_b, cy_b]):
            return False
        px_d = math.hypot(float(cx_a) - float(cx_b), float(cy_a) - float(cy_b))
        dist_a = self._safe_float(det_a.get("distance"))
        dist_b = self._safe_float(det_b.get("distance"))
        if not (math.isfinite(dist_a) and math.isfinite(dist_b)):
            return False
        dist_d = abs(float(dist_a) - float(dist_b))
        geo_d = self._haversine_m(
            det_a.get("lat"),
            det_a.get("lon"),
            det_b.get("lat"),
            det_b.get("lon"),
        )
        if not math.isfinite(geo_d):
            return False

        px_gate, dist_gate, geo_gate, iou_gate = self._static_dedupe_gates(class_a)

        px_ok = (float(px_d) <= float(px_gate)) or (float(iou) >= float(iou_gate))
        dist_ok = float(dist_d) <= float(dist_gate)
        geo_ok = float(geo_d) <= float(geo_gate)
        return bool(px_ok and dist_ok and geo_ok)

    def _merge_duplicate_det_inplace(self, primary: dict, duplicate: dict) -> None:
        conf_a = max(0.0, self._safe_float(primary.get("confidence"), 0.0))
        conf_b = max(0.0, self._safe_float(duplicate.get("confidence"), 0.0))
        denom = max(float(GEOMETRY_EPS), float(conf_a + conf_b))
        wa = float(conf_a) / float(denom)
        wb = float(conf_b) / float(denom)

        for key in ("lat", "lon", "distance", "cx", "cy", "x_m", "y_m", "z_m", "alt_msl"):
            a = self._safe_float(primary.get(key))
            b = self._safe_float(duplicate.get(key))
            if not (math.isfinite(a) and math.isfinite(b)):
                continue
            primary[key] = float(a) * float(wa) + float(b) * float(wb)

        primary["confidence"] = max(float(conf_a), float(conf_b))
        if float(conf_b) > float(conf_a) and isinstance(duplicate.get("bbox"), dict):
            primary["bbox"] = dict(duplicate.get("bbox") or {})

    def _dedupe_frame_detections(self, frame_dets: list[dict]) -> list[dict]:
        if len(frame_dets) <= 1:
            return frame_dets
        deduped: list[dict] = []
        det_order = sorted(
            range(len(frame_dets)),
            key=lambda i: float(frame_dets[i].get("confidence", 0.0)),
            reverse=True,
        )
        for det_idx in det_order:
            det = frame_dets[det_idx]
            det_class = self._class_name_key(str(det.get("type", "")))
            if not self._is_static_class(det_class):
                deduped.append(det)
                continue
            merged = False
            for kept in deduped:
                if self._class_name_key(str(kept.get("type", ""))) != det_class:
                    continue
                if self._is_same_static_detection(det, kept):
                    self._merge_duplicate_det_inplace(kept, det)
                    merged = True
                    break
            if not merged:
                deduped.append(det)
        return deduped

    @staticmethod
    def _outgoing_numeric_id(out_item: dict) -> Optional[int]:
        for key in ("source_id", "id"):
            try:
                value = int(out_item.get(key))
            except (TypeError, ValueError):
                continue
            if value >= 0:
                return int(value)
        return None

    def _is_same_static_outgoing(self, a: dict, b: dict) -> bool:
        class_a = self._class_name_key(str(a.get("type", "")))
        class_b = self._class_name_key(str(b.get("type", "")))
        if class_a != class_b:
            return False
        if not self._is_static_class(class_a):
            return False

        _, dist_gate, geo_gate, _ = self._static_dedupe_gates(class_a)
        merge_geo_gate = max(float(geo_gate) * 1.4, float(geo_gate) + 0.6)
        merge_dist_gate = max(float(dist_gate) * 2.0, float(dist_gate) + 1.5)

        geo_d = self._haversine_m(
            a.get("lat"),
            a.get("lon"),
            b.get("lat"),
            b.get("lon"),
        )
        if not math.isfinite(geo_d) or float(geo_d) > float(merge_geo_gate):
            return False

        dist_a = self._safe_float(a.get("distance"))
        dist_b = self._safe_float(b.get("distance"))
        if not (math.isfinite(dist_a) and math.isfinite(dist_b)):
            return False
        if abs(float(dist_a) - float(dist_b)) > float(merge_dist_gate):
            return False
        return True

    def _merge_static_outgoing_inplace(self, primary: dict, duplicate: dict) -> None:
        self._merge_outgoing_inplace(primary, duplicate)

    def _merge_outgoing_inplace(self, primary: dict, duplicate: dict) -> None:
        conf_a = max(0.0, self._safe_float(primary.get("confidence"), 0.0))
        conf_b = max(0.0, self._safe_float(duplicate.get("confidence"), 0.0))
        denom = max(float(GEOMETRY_EPS), float(conf_a + conf_b))
        wa = float(conf_a) / float(denom)
        wb = float(conf_b) / float(denom)

        for key in ("lat", "lon", "distance"):
            a = self._safe_float(primary.get(key))
            b = self._safe_float(duplicate.get(key))
            if math.isfinite(a) and math.isfinite(b):
                primary[key] = float(a) * float(wa) + float(b) * float(wb)
            elif math.isfinite(b):
                primary[key] = float(b)

        primary["confidence"] = max(float(conf_a), float(conf_b))

        if float(conf_b) > float(conf_a) and isinstance(duplicate.get("bbox"), dict):
            primary["bbox"] = dict(duplicate.get("bbox") or {})

        id_a = self._outgoing_numeric_id(primary)
        id_b = self._outgoing_numeric_id(duplicate)
        if id_a is None and id_b is not None:
            primary["id"] = int(id_b)
            primary["source_id"] = int(id_b)
            return
        if id_b is None:
            return
        if id_a is None or int(id_b) < int(id_a):
            primary["id"] = int(id_b)
            primary["source_id"] = int(id_b)

    def _is_dynamic_cluster_class(self, class_name: str) -> bool:
        class_key = self._class_name_key(str(class_name))
        return bool(DYNAMIC_CLUSTER_ENABLE and class_key in DYNAMIC_CLUSTER_CLASS_KEYS and not self._is_static_class(class_key))

    def _is_same_dynamic_outgoing(self, a: dict, b: dict) -> bool:
        class_a = self._class_name_key(str(a.get("type", "")))
        class_b = self._class_name_key(str(b.get("type", "")))
        if not (self._is_dynamic_cluster_class(class_a) and self._is_dynamic_cluster_class(class_b)):
            return False

        geo_d = self._haversine_m(
            a.get("lat"),
            a.get("lon"),
            b.get("lat"),
            b.get("lon"),
        )
        if not math.isfinite(geo_d) or float(geo_d) > float(DYNAMIC_CLUSTER_GEO_M):
            return False

        dist_a = self._safe_float(a.get("distance"))
        dist_b = self._safe_float(b.get("distance"))
        if not (math.isfinite(dist_a) and math.isfinite(dist_b)):
            return False
        if abs(float(dist_a) - float(dist_b)) > float(DYNAMIC_CLUSTER_DIST_M):
            return False
        return True

    def _collapse_dynamic_outgoing(self, outgoing: list[dict]) -> list[dict]:
        if (not DYNAMIC_CLUSTER_ENABLE) or len(outgoing) <= 1:
            return outgoing

        passthrough: list[dict] = []
        merged_dynamic: list[dict] = []
        for item in outgoing:
            class_key = self._class_name_key(str(item.get("type", "")))
            if not self._is_dynamic_cluster_class(class_key):
                passthrough.append(dict(item))
                continue

            merged = False
            for existing in merged_dynamic:
                if self._is_same_dynamic_outgoing(item, existing):
                    self._merge_outgoing_inplace(existing, item)
                    merged = True
                    break
            if not merged:
                merged_dynamic.append(dict(item))

        return merged_dynamic + passthrough

    def _collapse_static_outgoing(self, outgoing: list[dict]) -> list[dict]:
        if len(outgoing) <= 1:
            return outgoing

        dynamic_items: list[dict] = []
        merged_static: list[dict] = []
        for item in outgoing:
            class_key = self._class_name_key(str(item.get("type", "")))
            if not self._is_static_class(class_key):
                dynamic_items.append(dict(item))
                continue

            merged = False
            for existing in merged_static:
                if self._is_same_static_outgoing(item, existing):
                    self._merge_static_outgoing_inplace(existing, item)
                    merged = True
                    break
            if not merged:
                merged_static.append(dict(item))

        return dynamic_items + merged_static

    def _next_track_obs_id(self) -> int:
        obs_id = int(self._next_track_id)
        self._next_track_id = int(self._next_track_id) + 1
        return int(obs_id)

    @staticmethod
    def _track_match_score(det: dict, track: VisionTrack) -> tuple[float, float]:
        px_d = math.hypot(float(det.get("cx", 0.0)) - float(track.cx), float(det.get("cy", 0.0)) - float(track.cy))
        dist_d = abs(float(det.get("distance", 0.0)) - float(track.dist))
        return float(px_d), float(dist_d)

    def _match_track_id(self, det: dict, used_track_ids: set[int], now_s: float) -> Optional[int]:
        max_px = float(TRACK_MATCH_MAX_PX)
        max_dist_m = float(TRACK_MATCH_MAX_DIST_M)
        if not (math.isfinite(max_px) and max_px > 0.0 and math.isfinite(max_dist_m) and max_dist_m > 0.0):
            return None

        det_class = self._class_name_key(str(det.get("type", "")))
        det_is_static = bool(self._is_static_class(det_class))
        dist_gate_m = float(max_dist_m)
        geo_gate_m = max(
            1.0,
            min(
                10.0 if det_is_static else 6.0,
                float(TRACK_MATCH_MAX_DIST_M) * (0.55 if det_is_static else 0.35),
            ),
        )
        iou_gate = 0.20 if det_is_static else 0.10
        if det_is_static:
            dist_gate_m = max(float(max_dist_m), float(STATIC_TRACK_MATCH_MAX_DIST_M))
            if det_class == "cow":
                dist_gate_m = min(float(dist_gate_m), max(1.5, min(float(max_dist_m) * 0.35, 6.0)))
                geo_gate_m = max(1.0, min(float(max_dist_m) * 0.22, 4.0))
                iou_gate = 0.24
            elif det_class == "tower":
                dist_gate_m = min(float(dist_gate_m), max(2.0, min(float(max_dist_m) * 0.55, 10.0)))
                geo_gate_m = max(1.5, min(float(max_dist_m) * 0.45, 8.0))
                iou_gate = 0.20
        temporal_gate_s = float(self._temporal_match_gate_s(det_class))
        best_id: Optional[int] = None
        best_score = float("inf")
        for track_id, track in self._tracks.items():
            if int(track_id) in used_track_ids:
                continue
            if self._class_name_key(str(track.class_name)) != det_class:
                continue
            age_s = max(0.0, float(now_s) - float(track.last_seen_ts))
            if float(age_s) > float(temporal_gate_s):
                continue
            px_d, dist_d = self._track_match_score(det, track)
            iou = self._bbox_iou(det.get("bbox") or {}, track.bbox or {})
            geo_d = self._haversine_m(
                det.get("lat"),
                det.get("lon"),
                track.lat,
                track.lon,
            )
            px_ok = float(px_d) <= float(max_px) or float(iou) >= float(iou_gate)
            if not px_ok:
                continue
            if not math.isfinite(geo_d) or float(geo_d) > float(geo_gate_m):
                continue
            allow_outlier_link = False
            if float(dist_d) > float(dist_gate_m):
                if det_is_static:
                    strict_px_gate, strict_geo_gate, strict_iou_gate, outlier_dist_gate = self._static_outlier_link_gates(det_class)
                    close_visual = float(px_d) <= float(strict_px_gate) or float(iou) >= float(strict_iou_gate)
                    close_geo = float(geo_d) <= float(strict_geo_gate)
                    recent_track = float(age_s) <= min(1.2, float(temporal_gate_s))
                    if close_visual and close_geo and recent_track and float(dist_d) <= float(outlier_dist_gate):
                        allow_outlier_link = True
                if not allow_outlier_link:
                    continue
            score = (
                (float(px_d) / max(float(max_px), float(GEOMETRY_EPS)))
                + (float(dist_d) / max(float(dist_gate_m), float(GEOMETRY_EPS)))
                + (float(geo_d) / max(float(geo_gate_m), float(GEOMETRY_EPS)))
                + (float(age_s) / max(float(temporal_gate_s), float(GEOMETRY_EPS)))
                - (0.20 * float(iou))
            )
            if allow_outlier_link:
                score += 0.8
            if score < best_score:
                best_score = float(score)
                best_id = int(track_id)
        return best_id

    def _trim_tracks_capacity(self) -> None:
        max_active = int(TRACK_MAX_ACTIVE)
        if max_active <= 0:
            return
        if len(self._tracks) <= max_active:
            return
        sorted_tracks = sorted(
            self._tracks.items(),
            key=lambda kv: float(getattr(kv[1], "last_seen_ts", 0.0)),
        )
        to_remove = len(self._tracks) - max_active
        for idx in range(max(0, int(to_remove))):
            track_id = int(sorted_tracks[idx][0])
            self._tracks.pop(track_id, None)

    def _update_tracks_from_detections(self, frame_dets: list[dict], now_s: float) -> set[int]:
        seen_ids: set[int] = set()
        used_track_ids: set[int] = set()
        if not frame_dets:
            return seen_ids

        det_order = sorted(
            range(len(frame_dets)),
            key=lambda i: float(frame_dets[i].get("confidence", 0.0)),
            reverse=True,
        )
        for det_idx in det_order:
            d = frame_dets[det_idx]
            matched_id = self._match_track_id(d, used_track_ids, float(now_s))
            prev_t = self._tracks.get(int(matched_id)) if matched_id is not None else None

            if prev_t is None:
                obs_id = int(self._next_track_obs_id())
                self._tracks[obs_id] = VisionTrack(
                    obs_id=int(obs_id),
                    class_name=str(d.get("type")),
                    lat=float(d.get("lat")),
                    lon=float(d.get("lon")),
                    dist=float(d.get("distance")),
                    conf=float(d.get("confidence")),
                    bbox=d.get("bbox") or {},
                    cx=float(d.get("cx")),
                    cy=float(d.get("cy")),
                    last_seen_ts=float(now_s),
                    seen_count=1,
                    semantic_meta=self._semantic_meta_from_detection(d),
                )
                d["id"] = int(obs_id)
                seen_ids.add(int(obs_id))
                used_track_ids.add(int(obs_id))
                continue

            obs_id = int(prev_t.obs_id)
            dt = float(now_s) - float(prev_t.last_seen_ts)
            a = self._alpha_from_dt(dt)
            lat = float(prev_t.lat) + a * (float(d.get("lat")) - float(prev_t.lat))
            lon = float(prev_t.lon) + a * (float(d.get("lon")) - float(prev_t.lon))
            dist_meas = float(d.get("distance"))
            if self._is_static_class(str(prev_t.class_name)):
                class_key = self._class_name_key(str(prev_t.class_name))
                max_step_m = max(
                    float(STATIC_DIST_MAX_STEP_M),
                    float(STATIC_DIST_RATE_MPS) * max(0.0, float(dt)),
                )
                px_d = math.hypot(float(d.get("cx")) - float(prev_t.cx), float(d.get("cy")) - float(prev_t.cy))
                dist_jump = abs(float(dist_meas) - float(prev_t.dist))
                geo_jump = self._haversine_m(
                    d.get("lat"),
                    d.get("lon"),
                    prev_t.lat,
                    prev_t.lon,
                )
                if class_key == "cow":
                    jitter_px_gate = 8.0
                    jitter_dist_gate = max(2.0, float(max_step_m) * 1.5)
                    jitter_geo_gate = 2.0
                elif class_key == "tower":
                    jitter_px_gate = 12.0
                    jitter_dist_gate = max(3.0, float(max_step_m) * 2.0)
                    jitter_geo_gate = 3.5
                else:
                    jitter_px_gate = 10.0
                    jitter_dist_gate = max(2.5, float(max_step_m) * 1.8)
                    jitter_geo_gate = 2.5
                if (
                    math.isfinite(px_d)
                    and math.isfinite(geo_jump)
                    and float(px_d) <= float(jitter_px_gate)
                    and float(geo_jump) <= float(jitter_geo_gate)
                    and float(dist_jump) > float(jitter_dist_gate)
                ):
                    dist_meas = float(prev_t.dist)
                else:
                    dist_meas = max(float(prev_t.dist) - float(max_step_m), min(float(prev_t.dist) + float(max_step_m), float(dist_meas)))
            dist = float(prev_t.dist) + a * (float(dist_meas) - float(prev_t.dist))
            conf_s = max(float(prev_t.conf), float(d.get("confidence")))
            semantic_meta = dict(prev_t.semantic_meta or {})
            if float(d.get("confidence")) >= float(prev_t.conf):
                semantic_meta = self._semantic_meta_from_detection(d)
            else:
                semantic_meta = self._merge_dynamic_sppa_meta(semantic_meta, d)
            self._tracks[obs_id] = VisionTrack(
                obs_id=int(obs_id),
                class_name=str(d.get("type")),
                lat=float(lat),
                lon=float(lon),
                dist=float(dist),
                conf=float(conf_s),
                bbox=d.get("bbox") or {},
                cx=float(d.get("cx")),
                cy=float(d.get("cy")),
                last_seen_ts=float(now_s),
                seen_count=int(prev_t.seen_count) + 1,
                semantic_meta=semantic_meta,
            )
            d["id"] = int(obs_id)
            seen_ids.add(int(obs_id))
            used_track_ids.add(int(obs_id))

        self._trim_tracks_capacity()
        return seen_ids

    def _footer_ignore_px(self, image_h: int) -> int:
        if int(image_h) <= int(GEOMETRY_PIXEL_EPS):
            return 0
        by_frac = int(round(float(IGNORE_BOTTOM_FRAC) * float(image_h)))
        px = max(int(IGNORE_BOTTOM_PX), int(by_frac))
        return max(0, min(int(image_h - 1), int(px)))

    def _header_ignore_px(self, image_h: int) -> int:
        if int(image_h) <= int(GEOMETRY_PIXEL_EPS):
            return 0
        by_frac = int(round(float(IGNORE_TOP_FRAC) * float(image_h)))
        px = max(int(IGNORE_TOP_PX), int(by_frac))
        return max(0, min(int(image_h - 1), int(px)))

    @staticmethod
    def _class_name_key(class_name: str) -> str:
        return str(class_name or "").strip().lower()

    @staticmethod
    def _semantic_meta_from_detection(det: dict) -> dict:
        return {
            key: det.get(key)
            for key in SPPA_SEMANTIC_META_KEYS
            if key in det and det.get(key) is not None
        }

    @staticmethod
    def _merge_dynamic_sppa_meta(meta: dict, det: dict) -> dict:
        merged = dict(meta or {})
        for key in SPPA_DYNAMIC_META_KEYS:
            if key in det and det.get(key) is not None:
                merged[key] = det.get(key)
        return merged

    @staticmethod
    def _sample_mask_polygon(mask_xy, max_points: int) -> list[list[float]] | None:
        if mask_xy is None:
            return None
        try:
            points = np.asarray(mask_xy, dtype=float)
        except Exception:
            return None
        if points.ndim != 2 or points.shape[0] < 3 or points.shape[1] < 2:
            return None
        points = points[:, :2]
        if points.shape[0] > int(max_points):
            step = max(1, int(math.ceil(points.shape[0] / float(max_points))))
            points = points[::step]
        out: list[list[float]] = []
        for x, y in points:
            xf = float(x)
            yf = float(y)
            if math.isfinite(xf) and math.isfinite(yf):
                out.append([xf, yf])
        return out if len(out) >= 3 else None

    def _is_static_class(self, class_name: str) -> bool:
        return self._class_name_key(class_name) in STATIC_CLASS_KEYS

    def _max_box_area_frac_for_class(self, class_name: str) -> float:
        k = self._class_name_key(class_name)
        if k in ("biker", "bicycle", "person"):
            return max(0.0, min(float(MAX_BOX_AREA_FRAC), float(MAX_BOX_AREA_FRAC_BIKER)))
        if k == "cow":
            return max(0.0, min(float(MAX_BOX_AREA_FRAC), float(MAX_BOX_AREA_FRAC_COW)))
        if k == "tower":
            return max(0.0, min(float(MAX_BOX_AREA_FRAC), float(MAX_BOX_AREA_FRAC_TOWER)))
        return max(0.0, float(MAX_BOX_AREA_FRAC))

    def _min_seen_to_publish_for_class(self, class_name: str) -> int:
        k = self._class_name_key(class_name)
        if k in ("biker", "bicycle", "person"):
            return int(MIN_SEEN_TO_PUBLISH_BIKER)
        if k == "cow":
            return int(MIN_SEEN_TO_PUBLISH_COW)
        if k == "tower":
            return int(MIN_SEEN_TO_PUBLISH_TOWER)
        return int(MIN_SEEN_TO_PUBLISH)

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
        east = dlon * R * (math.cos(math.radians(float(origin_lat))) or float(GEOMETRY_COS_LAT_EPS))
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
        if denom <= float(VISION_TRACK_DENOM_EPS) or denom <= float(GEOMETRY_EPS):
            return None
        t = (n * float(base_north_m) + e * float(base_east_m)) / denom
        if not math.isfinite(t) or t <= 0.0:
            return None

        pred_n = n * t
        pred_e = e * t
        err = math.hypot(pred_n - float(base_north_m), pred_e - float(base_east_m))
        # If the ray misses the vertical line too much, reject (often caused by massive boxes).
        if err > max(
            float(VISION_HEIGHT_ERR_MIN_M),
            float(VISION_HEIGHT_ERR_SLOPE) * max(float(VISION_HEIGHT_DIST_FLOOR_M), float(dist_h_m)),
        ):
            return None

        z_down = d * t
        h = float(alt_agl_m)
        if not math.isfinite(z_down) or not math.isfinite(h) or h <= float(VISION_HEIGHT_ERR_MIN_M):
            return None

        height = h - z_down
        if not math.isfinite(height):
            return None

        # Clamp to avoid overlay explosions.
        height = max(0.0, min(float(height), float(VISION_HEIGHT_CLAMP_M)))
        return float(height)

    def _draw_text_with_outline(self, image_bgr, text: str, xy: tuple[int, int], *, scale: float, color, thickness: int = 1) -> None:
        cv2.putText(
            image_bgr,
            str(text),
            (int(xy[0]), int(xy[1])),
            cv2.FONT_HERSHEY_SIMPLEX,
            float(scale),
            (0, 0, 0),
            max(1, int(thickness) + 2),
            cv2.LINE_AA,
        )
        cv2.putText(
            image_bgr,
            str(text),
            (int(xy[0]), int(xy[1])),
            cv2.FONT_HERSHEY_SIMPLEX,
            float(scale),
            tuple(color),
            max(1, int(thickness)),
            cv2.LINE_AA,
        )

    @staticmethod
    def _fit_text_to_width(text: str, max_width_px: int, *, scale: float, thickness: int = 1) -> str:
        text = str(text)
        max_width_px = max(8, int(max_width_px))
        try:
            width = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, float(scale), max(1, int(thickness)))[0][0]
            if width <= max_width_px:
                return text
            suffix = "..."
            lo, hi = 0, len(text)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                candidate = text[:mid].rstrip() + suffix
                cand_w = cv2.getTextSize(candidate, cv2.FONT_HERSHEY_SIMPLEX, float(scale), max(1, int(thickness)))[0][0]
                if cand_w <= max_width_px:
                    lo = mid
                else:
                    hi = mid - 1
            return text[:lo].rstrip() + suffix
        except Exception:
            return text[:96]

    def _paper_class_color(self, class_name: str, *, published: bool = False) -> tuple[int, int, int]:
        key = self._class_name_key(str(class_name))
        if key == "biker":
            return (80, 235, 170) if published else (70, 190, 145)
        if key == "tower":
            return (0, 215, 255) if published else (0, 170, 220)
        if key == "cow":
            return (170, 185, 115) if published else (130, 150, 90)
        return (230, 230, 230)

    def _paper_track_state(self, track: VisionTrack, outgoing_ids: set[int], seen_ids: set[int], now_s: float) -> str:
        track_id = int(track.obs_id)
        if track_id in outgoing_ids:
            return "published" if track_id in seen_ids else "held"
        hold_s = float(TRACK_HOLD_S)
        age_s = max(0.0, float(now_s) - float(track.last_seen_ts))
        if track_id not in seen_ids and age_s > hold_s:
            return "lost"
        return "tracking"

    def _paper_planner_label(self, telemetry: dict) -> str:
        failsafe = str(telemetry.get("failsafe_action_active", "") or "").strip().upper()
        if failsafe:
            return f"failsafe {failsafe}"
        evasion_raw = telemetry.get("evasion_active", telemetry.get("evasion", False))
        if bool(evasion_raw):
            return "avoidance"
        return "monitoring"

    def _draw_paper_bar(self, image_bgr, y0: int, y1: int) -> None:
        if y1 <= y0:
            return
        H, W = image_bgr.shape[:2]
        y0 = max(0, min(int(H), int(y0)))
        y1 = max(0, min(int(H), int(y1)))
        if y1 <= y0:
            return
        overlay_img = image_bgr.copy()
        cv2.rectangle(overlay_img, (0, y0), (int(W - 1), int(y1 - 1)), (18, 22, 24), thickness=-1)
        cv2.addWeighted(
            overlay_img,
            float(VISION_PAPER_OVERLAY_ALPHA),
            image_bgr,
            1.0 - float(VISION_PAPER_OVERLAY_ALPHA),
            0.0,
            image_bgr,
        )

    def _draw_paper_overlay(
        self,
        image_bgr,
        *,
        tracks_sorted: list[VisionTrack],
        outgoing_ids: set[int],
        seen_ids: set[int],
        telemetry: dict,
        now_s: float,
        outgoing_count: int,
    ) -> None:
        H, W = image_bgr.shape[:2]
        top_h = int(VISION_PAPER_OVERLAY_TOP_H) if bool(VISION_PAPER_OVERLAY_BARS) else 0
        bottom_h = int(VISION_PAPER_OVERLAY_BOTTOM_H) if bool(VISION_PAPER_OVERLAY_BARS) else 0
        text_scale = float(VISION_PAPER_OVERLAY_TEXT_SCALE)
        label_scale = float(VISION_PAPER_OVERLAY_LABEL_SCALE)
        line_thickness = int(VISION_PAPER_OVERLAY_LINE_THICKNESS)

        if top_h > 0:
            self._draw_paper_bar(image_bgr, 0, top_h)
            target_text = ",".join(TARGET_CLASS_NAMES) if TARGET_CLASS_NAMES else "all"
            top_parts = [str(VISION_PAPER_OVERLAY_TITLE), f"targets {target_text}", f"pub {int(outgoing_count)}"]
            if bool(VISION_PAPER_OVERLAY_SHOW_FPS):
                top_parts.append(f"{float(self._fps_ema):.1f} FPS")
            top_text = self._fit_text_to_width(
                " | ".join(top_parts),
                int(W - 20),
                scale=text_scale,
                thickness=1,
            )
            self._draw_text_with_outline(
                image_bgr,
                top_text,
                (10, max(18, int(top_h * 0.68))),
                scale=text_scale,
                color=(235, 245, 245),
                thickness=1,
            )

        max_n = max(0, min(int(self._overlay_max_obs), len(tracks_sorted)))
        for track in tracks_sorted[:max_n]:
            bbox = dict(track.bbox or {})
            try:
                x1 = int(max(0, min(W - 1, int(bbox.get("x1", 0)))))
                y1 = int(max(0, min(H - 1, int(bbox.get("y1", 0)))))
                x2 = int(max(0, min(W - 1, int(bbox.get("x2", 0)))))
                y2 = int(max(0, min(H - 1, int(bbox.get("y2", 0)))))
            except Exception:
                continue
            if x2 <= x1 or y2 <= y1:
                continue

            track_id = int(track.obs_id)
            published = track_id in outgoing_ids
            color = self._paper_class_color(str(track.class_name), published=published)
            state = self._paper_track_state(track, outgoing_ids, seen_ids, float(now_s))
            cv2.rectangle(image_bgr, (x1, y1), (x2, y2), color, line_thickness + (1 if published else 0), cv2.LINE_AA)
            label = f"{str(track.class_name)} #{track_id} {float(track.conf):.2f} {float(track.dist):.1f}m {state}"
            label_y = max(top_h + 18, y1 - 8)
            if label_y >= y1 and y2 + 18 < H - bottom_h:
                label_y = y2 + 18
            label_x = max(6, x1)
            try:
                label_w = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, label_scale, 1)[0][0]
                if label_x + label_w + 8 > W:
                    label_x = max(6, min(label_x, W - label_w - 8))
            except Exception:
                pass
            label_fit = self._fit_text_to_width(
                label,
                int(W - label_x - 8),
                scale=label_scale,
                thickness=1,
            )
            self._draw_text_with_outline(
                image_bgr,
                label_fit,
                (label_x, min(H - bottom_h - 6, label_y)),
                scale=label_scale,
                color=color,
                thickness=1,
            )

        if bottom_h > 0:
            y0 = max(0, H - bottom_h)
            self._draw_paper_bar(image_bgr, y0, H)
            planner = self._paper_planner_label(telemetry)
            if tracks_sorted:
                nearest = tracks_sorted[0]
                nearest_text = f"nearest: {nearest.class_name} #{int(nearest.obs_id)} {float(nearest.dist):.1f} m"
            else:
                nearest_text = "nearest: none"
            path_len = telemetry.get("evasion_path_len", None)
            path_text = ""
            try:
                if path_len is not None and int(path_len) > 0:
                    path_text = f" | path {int(path_len)} pts"
            except Exception:
                path_text = ""
            bottom_text = f"{nearest_text} | planner: {planner}{path_text}"
            bottom_text = self._fit_text_to_width(
                bottom_text,
                int(W - 20),
                scale=text_scale,
                thickness=1,
            )
            self._draw_text_with_outline(
                image_bgr,
                bottom_text,
                (10, min(H - 10, y0 + max(22, int(bottom_h * 0.62)))),
                scale=text_scale,
                color=(235, 245, 245),
                thickness=1,
            )

    def run(self):
        log("Sistema listo. Esperando visualizacion...")

        hb_every_s = float(HEARTBEAT_S)
        hb_last_ts = time.time()
        detections_log_every_s = float(VISION_DETECTIONS_LOG_INTERVAL_S)
        detections_log_last_ts = 0.0
        frame_count = 0
        last_dets = 0
        last_send = 0
        
        while True:
            frame_now = time.perf_counter()
            if self._last_frame_ts is not None:
                dt = float(frame_now) - float(self._last_frame_ts)
                if math.isfinite(dt) and dt > float(VISION_MIN_DT_S_FOR_FPS):
                    fps_inst = 1.0 / dt
                    alpha = float(VISION_FPS_EMA_ALPHA)
                    self._fps_ema = float(fps_inst) if self._fps_ema <= 0.0 else float(
                        (1.0 - alpha) * self._fps_ema + alpha * fps_inst
                    )
            self._last_frame_ts = float(frame_now)
             
            # 1. Obtener Telemetria (Necesaria para proyeccion)
            # En VIDEO_LINK primero llega el frame por el enlace: su indice
            # selecciona la fila de pose exacta del CSV (sincronia frame<->pose).
            pending_link_frame = self._fetch_link_frame() if self._video_link else None
            telemetry_idx = self._video_link_frame_idx if self._video_link else frame_count
            telemetry = self.get_telemetry(frame_idx=telemetry_idx)
            if not telemetry:
                # Si no hay telemetria, esperamos
                if self._pump_debug_status("Waiting for Brain telemetry..."):
                    break
                time.sleep(float(VISION_SLEEP_NO_TELEMETRY_S))
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
            telemetry_source = str(telemetry.get("telemetry_source", "mavlink") or "mavlink").strip().lower()
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

            # 2. Captura de imagen (pantalla o video).
            if self._capture_mode == "video":
                img_bgr = self._postprocess_video_frame(pending_link_frame) if self._video_link else self._read_video_frame()
                if img_bgr is None:
                    if self._pump_debug_status("Waiting for video frame..."):
                        break
                    if self._video_loop:
                        time.sleep(float(self._video_reopen_sleep_s))
                    else:
                        time.sleep(float(VISION_SLEEP_NO_MONITOR_S))
                    continue
            else:
                if self._capture_mode == "window":
                    if not self._capture_hwnd:
                        self._capture_hwnd = self._win32_find_window()
                        if self._capture_hwnd:
                            self._win32_prepare_window(self._capture_hwnd)
                    if not self._capture_hwnd:
                        # No window yet (Unreal PIE not started?)
                        if self._pump_debug_status("Waiting for capture window..."):
                            break
                        time.sleep(float(VISION_SLEEP_NO_WINDOW_S))
                        continue

                    self.monitor = self._win32_client_region(self._capture_hwnd)
                    if not self.monitor:
                        if self._pump_debug_status("Waiting for valid capture region..."):
                            break
                        time.sleep(float(VISION_SLEEP_INVALID_MONITOR_S))
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

                    # Keep on top if requested (helps if the window gets covered).
                    self._win32_prepare_window(self._capture_hwnd)
                    self._maybe_dock_debug_window()

                if not self.monitor:
                    if self._pump_debug_status("Waiting for monitor capture region..."):
                        break
                    time.sleep(float(VISION_SLEEP_NO_MONITOR_S))
                    continue

                img_bgr = None
                if self._capture_mode == "window" and self._capture_window_method == "printwindow":
                    img_bgr = self._printwindow_grab(self._capture_hwnd)
                    if img_bgr is None and not self._printwindow_warned:
                        self._printwindow_warned = True
                        log("[WARN] PrintWindow capture failed; falling back to MSS screen region.")
                if img_bgr is None:
                    capture_region = self.monitor
                    if self._capture_mode == "window":
                        region = self._window_capture_region()
                        if region:
                            capture_region = region
                    screenshot = np.array(self.sct.grab(capture_region))
                    # Convertir BGRA a BGR
                    img_bgr = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            frame_count += 1

            # Pristine copy for the audit archive BEFORE any debug annotation is
            # drawn onto img_bgr (bbox/labels below write into the same buffer).
            audit_frame_bgr = None
            if self._audit.enabled and int(frame_count) % int(AUDIT_VISION_FRAME_EVERY_N) == 0:
                try:
                    audit_frame_bgr = img_bgr.copy()
                except Exception:
                    audit_frame_bgr = None

            H, W = img_bgr.shape[:2]
            ignore_top_px = self._header_ignore_px(int(H))
            ignore_bottom_px = self._footer_ignore_px(int(H))
            ignore_top_y = int(H - ignore_bottom_px)
            infer_bgr = img_bgr
            if ignore_top_px > 0 or ignore_bottom_px > 0:
                # Mask persistent UI (header/footer) so YOLO does not learn/detect them.
                infer_bgr = img_bgr.copy()
                if ignore_top_px > 0:
                    infer_bgr[0:int(ignore_top_px), :] = 0
                if ignore_bottom_px > 0:
                    infer_bgr[ignore_top_y:int(H), :] = 0

            # 3. Inferencia YOLO
            # Filter by class IDs when available (reduces spurious detections on COCO weights).
            class_filter = getattr(self, "_target_class_ids", None)
            if not class_filter:
                results = self.model.predict(infer_bgr, conf=DETECTION_CONFIDENCE_THRESHOLD, imgsz=int(VISION_IMGSZ), verbose=False)
            else:
                results = self.model.predict(
                    infer_bgr,
                    conf=DETECTION_CONFIDENCE_THRESHOLD,
                    imgsz=int(VISION_IMGSZ),
                    classes=class_filter,
                    verbose=False,
                )
            
            now_s = time.time()
            self._purge_tracks(now_s)
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
            frame_dets: list[dict] = []
            raw_boxes_total = 0
            reject_counts: dict[str, int] = defaultdict(int)
            reject_box_color = (0, 165, 255)
              
            # 4. Procesar Detecciones
            for r in results:
                boxes = r.boxes
                masks_xy = []
                try:
                    if getattr(r, "masks", None) is not None and getattr(r.masks, "xy", None) is not None:
                        masks_xy = list(r.masks.xy)
                except Exception:
                    masks_xy = []
                for box_idx, box in enumerate(boxes):
                    raw_boxes_total += 1
                    # Bounding Box
                    x1, y1, x2, y2 = box.xyxy[0]
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    raw_class_name = str(self.model.names[cls])
                    canonical_class_name = self._canonical_class_name(raw_class_name)
                    mask_polygon_px = None
                    if box_idx < len(masks_xy):
                        mask_polygon_px = self._sample_mask_polygon(masks_xy[box_idx], int(VISION_SPPA_MASK_MAX_POINTS))
                    sppa_norm = normalize_runtime_detection(
                        {"class_name": raw_class_name, "confidence": conf},
                        canonical_class_name,
                    )
                    class_name = str(sppa_norm.get("runtime_label") or canonical_class_name)
                    reject_reason = ""
                    
                    # Filtros basicos:
                    # - La proyeccion pixel->suelo es extremadamente sensible para bboxes pequenas (cerca del horizonte).
                    bw = x2 - x1
                    bh = y2 - y1
                    min_side = max(1, int(VISION_BBOX_MIN_SIDE_PX))
                    if bw <= min_side or bh <= min_side:
                        reject_counts["degenerate_box"] += 1
                        reject_reason = "degenerate_box"
                    elif bh < float(MIN_BOX_HEIGHT_PX):
                        reject_counts["min_box_height_px"] += 1
                        reject_reason = "min_box_height_px"
                    else:
                        box_area_px = float(bw * bh)
                        box_area_frac = box_area_px / max(float(GEOMETRY_PIXEL_EPS), float(H) * float(W))
                        if box_area_frac < float(MIN_BOX_AREA_FRAC):
                            reject_counts["min_box_area_frac"] += 1
                            reject_reason = "min_box_area_frac"
                        elif box_area_frac > float(MAX_BOX_AREA_FRAC):
                            reject_counts["max_box_area_frac_global"] += 1
                            reject_reason = "max_box_area_frac_global"
                        elif box_area_frac > float(self._max_box_area_frac_for_class(class_name)):
                            reject_counts["max_box_area_frac_class"] += 1
                            reject_reason = "max_box_area_frac_class"
                    if not reject_reason and ignore_bottom_px > 0 and y2 >= int(ignore_top_y):
                        # Do not project/send detections whose contact point falls inside ignored footer strip.
                        reject_counts["ignored_footer_strip"] += 1
                        reject_reason = "ignored_footer_strip"
                    if not reject_reason and ignore_top_px > 0 and y1 < int(ignore_top_px):
                        # Ignore detections that overlap the top toolbar strip.
                        reject_counts["ignored_header_strip"] += 1
                        reject_reason = "ignored_header_strip"
                    if reject_reason:
                        if (self._debug_enabled or self._record_enabled) and self._overlay_mode == "debug":
                            try:
                                cv2.rectangle(
                                    img_bgr,
                                    (x1, y1),
                                    (x2, y2),
                                    reject_box_color,
                                    1,
                                )
                                cv2.putText(
                                    img_bgr,
                                    f"{class_name} {conf:.2f} rej:{reject_reason}",
                                    (x1, max(12, y1 - 6)),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    max(0.35, float(VISION_DEBUG_BBOX_LABEL_SCALE) * 0.8),
                                    reject_box_color,
                                    1,
                                )
                            except Exception:
                                pass
                        continue

                    # Centro del objeto (base del bbox = "pies" en el suelo)
                    cx = float((x1 + x2) / 2.0)
                    cy = float(y2)  # Base del bbox. Antes era y1+y2 (bug) => fuera de frame.
                    cx = float(min(max(cx, 0.0), float(W - 1)))
                    cy = float(min(max(cy, 0.0), float(H - 1)))
                    
                    # Proyeccion GPS
                    projected = self.projector.pixel_to_gps_detailed(
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
                        clamp_to_max_range=bool(PROJECT_CLAMP_TO_MAX_RANGE),
                        max_range_margin_m=float(PROJECT_MAX_RANGE_MARGIN_M),
                    )
                    if not projected:
                        reject_counts["projection_failed"] += 1
                        if (self._debug_enabled or self._record_enabled) and self._overlay_mode == "debug":
                            try:
                                cv2.rectangle(
                                    img_bgr,
                                    (x1, y1),
                                    (x2, y2),
                                    reject_box_color,
                                    1,
                                )
                                cv2.putText(
                                    img_bgr,
                                    f"{class_name} {conf:.2f} rej:projection",
                                    (x1, max(12, y1 - 6)),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    max(0.35, float(VISION_DEBUG_BBOX_LABEL_SCALE) * 0.8),
                                    reject_box_color,
                                    1,
                                )
                            except Exception:
                                pass
                        continue
                    obj_lat = float(projected["lat"])
                    obj_lon = float(projected["lon"])
                    dist = float(projected["distance_m"])
                    range_clamped = bool(projected.get("range_clamped", False))

                    # Local ENU coordinates for overlay/debug (meters).
                    obj_x_m = obj_y_m = 0.0
                    if self._origin_lat is not None and self._origin_lon is not None:
                        obj_x_m, obj_y_m = self._enu_xy_m(self._origin_lat, self._origin_lon, float(obj_lat), float(obj_lon))

                    # Estimate object "height" (z, meters up) from bbox top vs base intersection.
                    obj_z_m = 0.0
                    obj_alt_msl_est = float(ground_msl)
                    try:
                        if not bool(projected.get("monocular_height_allowed", not range_clamped)):
                            raise ValueError("monocular height suppressed because range was clamped")
                        # Base offsets relative to drone, reconstructed from projected lat/lon.
                        R = float(EARTH_RADIUS_M)
                        dlat = math.radians(float(obj_lat) - float(dron_lat))
                        dlon = math.radians(float(obj_lon) - float(dron_lon))
                        base_north_m = dlat * R
                        base_east_m = dlon * R * (math.cos(math.radians(float(dron_lat))) or float(GEOMETRY_COS_LAT_EPS))
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

                    bbox_payload = {'x1': int(x1), 'y1': int(y1), 'x2': int(x2), 'y2': int(y2)}
                    world_m_payload = None
                    if self._origin_lat is not None and self._origin_lon is not None:
                        world_m_payload = {
                            "north": float(obj_y_m),
                            "east": float(obj_x_m),
                            "up": float(obj_z_m),
                        }

                    sppa_metric_extra: dict = {}
                    footprint_m = None
                    metric_dims_m = None
                    footprint_yaw_deg = None
                    if bool(VISION_SPPA_METRIC_FOOTPRINT_ENABLE):
                        try:
                            if mask_polygon_px:
                                footprint_m = self.projector.points_to_ground_footprint_m(
                                    mask_polygon_px,
                                    image_height=int(H),
                                    image_width=int(W),
                                    drone_yaw_deg=float(dron_yaw),
                                    drone_pitch_deg=float(dron_pitch),
                                    drone_roll_deg=float(dron_roll),
                                    alt_agl_m=float(dron_alt_agl),
                                    camera_vfov_deg=float(self._camera_vfov_deg),
                                    mount_roll_deg=float(self._mount_roll_deg),
                                    mount_pitch_deg=float(self._mount_pitch_deg),
                                    mount_yaw_deg=float(self._mount_yaw_deg),
                                    max_range_m=float(DETECTION_RANGE_M),
                                    clamp_to_max_range=bool(PROJECT_CLAMP_TO_MAX_RANGE),
                                    max_range_margin_m=float(PROJECT_MAX_RANGE_MARGIN_M),
                                    max_points=int(VISION_SPPA_MASK_MAX_POINTS),
                                    source="mask_ground_projected_polygon",
                                )
                            if footprint_m is None:
                                footprint_m = self.projector.bbox_to_ground_footprint_m(
                                    bbox_payload,
                                    image_height=int(H),
                                    image_width=int(W),
                                    drone_yaw_deg=float(dron_yaw),
                                    drone_pitch_deg=float(dron_pitch),
                                    drone_roll_deg=float(dron_roll),
                                    alt_agl_m=float(dron_alt_agl),
                                    camera_vfov_deg=float(self._camera_vfov_deg),
                                    mount_roll_deg=float(self._mount_roll_deg),
                                    mount_pitch_deg=float(self._mount_pitch_deg),
                                    mount_yaw_deg=float(self._mount_yaw_deg),
                                    max_range_m=float(DETECTION_RANGE_M),
                                    clamp_to_max_range=bool(PROJECT_CLAMP_TO_MAX_RANGE),
                                    max_range_margin_m=float(PROJECT_MAX_RANGE_MARGIN_M),
                                )
                        except Exception:
                            footprint_m = None

                    if footprint_m:
                        length_m = float(max(footprint_m.get("length_m", 0.0), footprint_m.get("width_m", 0.0)))
                        width_m = float(min(footprint_m.get("length_m", 0.0), footprint_m.get("width_m", 0.0)))
                        if math.isfinite(length_m) and math.isfinite(width_m) and length_m > 0.0:
                            metric_dims_m = {
                                "length": max(0.15, float(length_m)),
                                "width": max(0.15, float(width_m)),
                            }
                            if math.isfinite(float(obj_z_m)) and float(obj_z_m) > 0.05:
                                metric_dims_m["height"] = float(obj_z_m)
                        footprint_yaw_deg = float(footprint_m.get("orientation_deg_axial"))
                        sppa_metric_extra.update({
                            "sppa_footprint_m": footprint_m,
                            "sppa_footprint_source": str(footprint_m.get("source") or ""),
                            "sppa_yaw_source": str(footprint_m.get("source") or "ground_projected_footprint"),
                            "sppa_yaw_ambiguous": bool(footprint_m.get("yaw_ambiguous", True)),
                        })
                        if metric_dims_m:
                            sppa_metric_extra["sppa_metric_dims_m"] = metric_dims_m
                        if math.isfinite(float(footprint_yaw_deg)):
                            sppa_metric_extra["yaw_deg"] = float(footprint_yaw_deg)
                            sppa_metric_extra["heading_deg"] = float(footprint_yaw_deg)

                    if world_m_payload is not None:
                        sppa_metric_extra.update({
                            "world_m": world_m_payload,
                            "world_north_m": float(world_m_payload["north"]),
                            "world_east_m": float(world_m_payload["east"]),
                            "world_up_m": float(world_m_payload["up"]),
                        })

                    if bool(VISION_SPPA_DESCRIPTOR_ENABLE):
                        try:
                            descriptor_payload = build_sppa_descriptor_payload(
                                label=str(class_name),
                                confidence=float(conf),
                                bbox=bbox_payload,
                                mask=mask_polygon_px,
                                image_width=int(W),
                                image_height=int(H),
                                world_m=world_m_payload,
                                metric_dims_m=metric_dims_m,
                                metric_dims_source=str(sppa_metric_extra.get("sppa_footprint_source") or "uav_pose_bbox_ground_footprint"),
                                footprint_m=footprint_m,
                                yaw_deg=footprint_yaw_deg,
                                frame_id=int(frame_count),
                                timestamp=datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
                                max_descriptor_bytes=int(VISION_SPPA_DESCRIPTOR_MAX_BYTES),
                            )
                            sppa_metric_extra.update(descriptor_payload)
                        except Exception as exc:
                            sppa_metric_extra["sppa_descriptor_error"] = str(exc)[:160]
                     
                    label_main = f"{class_name} c={conf:.2f} d={dist:.1f}m z={obj_z_m:.1f}m"
                    label_geo = (
                        f"px=({int(cx)},{int(cy)}) "
                        f"gps=({float(obj_lat):.6f},{float(obj_lon):.6f}) "
                        f"enu=({float(obj_x_m):.1f},{float(obj_y_m):.1f})"
                    )
                     
                    # Draw only the paper-safe evidence layer during final captures.
                    # The verbose geometry remains in JSONL audit and debug mode.
                    if (self._debug_enabled or self._record_enabled) and self._overlay_mode != "off":
                        if self._overlay_mode == "debug":
                            cv2.rectangle(
                                img_bgr,
                                (x1, y1),
                                (x2, y2),
                                tuple(VISION_DEBUG_BBOX_COLOR),
                                int(VISION_DEBUG_BBOX_THICKNESS),
                            )
                            label_x = int(max(0, x1))
                            label_y_main = int(max(14, y1 - 10))
                            label_y_geo = int(min(int(H - 4), label_y_main + 14))
                            for text, y in ((label_main, label_y_main), (label_geo, label_y_geo)):
                                cv2.putText(
                                    img_bgr,
                                    text,
                                    (label_x, y),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    float(VISION_DEBUG_BBOX_LABEL_SCALE),
                                    tuple(VISION_DEBUG_BBOX_BASE_OUTLINE_COLOR),
                                    int(VISION_DEBUG_BBOX_BASE_OUTLINE_THICKNESS),
                                )
                                cv2.putText(
                                    img_bgr,
                                    text,
                                    (label_x, y),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    float(VISION_DEBUG_BBOX_LABEL_SCALE),
                                    tuple(VISION_DEBUG_BBOX_LABEL_COLOR),
                                    int(VISION_DEBUG_BBOX_LABEL_THICKNESS),
                                )
                        elif self._overlay_mode == "paper":
                            cv2.rectangle(
                                img_bgr,
                                (x1, y1),
                                (x2, y2),
                                self._paper_class_color(class_name, published=False),
                                max(1, int(VISION_PAPER_OVERLAY_LINE_THICKNESS) - 1),
                                cv2.LINE_AA,
                            )
                    
                    # Agregar a lista de detecciones candidatas; el ID estable se asigna por asociacion a tracks.
                    det_payload = {
                        'lat': float(obj_lat),
                        'lon': float(obj_lon),
                        'alt_msl': float(obj_alt_msl_est),
                        'distance': float(dist),
                        'type': str(class_name),
                        'detector_type': str(raw_class_name),
                        'canonical_type': str(canonical_class_name),
                        'sppa_tag': str(sppa_norm.get("sppa_tag") or ""),
                        'sppa_archetype': str(sppa_norm.get("runtime_archetype_id") or ""),
                        'sppa_match': str(sppa_norm.get("normalization_rule") or ""),
                        'sppa_claim_status': str(sppa_norm.get("claim_status") or ""),
                        'sppa_conservative': bool(sppa_norm.get("conservative", False)),
                        'confidence': float(conf),
                        'source': 'vision',
                        'range_clamped': bool(range_clamped),
                        'bbox': bbox_payload,
                        'cx': float(cx),
                        'cy': float(cy),
                        # Debug-only local frame (ENU meters, z=up/height).
                        'x_m': float(obj_x_m),
                        'y_m': float(obj_y_m),
                        'z_m': float(obj_z_m),
                    }
                    if sppa_metric_extra:
                        det_payload.update(sppa_metric_extra)
                    frame_dets.append(det_payload)

            # Visual hint of ignored footer area (zero-trust auditability in debug view).
            if self._debug_enabled and self._overlay_mode == "debug" and ignore_bottom_px > 0:
                try:
                    y0 = int(max(0, min(int(H - 1), int(ignore_top_y))))
                    overlay_img = img_bgr.copy()
                    cv2.rectangle(
                        overlay_img,
                        (0, y0),
                        (int(W - 1), int(H - 1)),
                        tuple(VISION_DEBUG_FOOTER_OVERLAY_COLOR),
                        thickness=-1,
                    )
                    cv2.addWeighted(
                        overlay_img,
                        float(VISION_DEBUG_FOOTER_OVERLAY_ALPHA),
                        img_bgr,
                        1.0 - float(VISION_DEBUG_FOOTER_OVERLAY_ALPHA),
                        0.0,
                        img_bgr,
                    )
                    cv2.line(
                        img_bgr,
                        (0, y0),
                        (int(W - 1), y0),
                        tuple(VISION_DEBUG_FOOTER_LINE_COLOR),
                        int(VISION_DEBUG_FOOTER_LINE_THICKNESS),
                    )
                    cv2.putText(
                        img_bgr,
                        f"IGNORED FOOTER: {ignore_bottom_px}px",
                        (int(VISION_DEBUG_FOOTER_LABEL_X0), max(18, y0 - int(VISION_DEBUG_FOOTER_LABEL_Y_OFFSET))),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        float(VISION_DEBUG_FOOTER_LABEL_SCALE),
                        tuple(VISION_DEBUG_FOOTER_LINE_COLOR),
                        int(VISION_DEBUG_FOOTER_LABEL_THICKNESS),
                    )
                except Exception:
                    pass

            # Visual hint of ignored header area (toolbar strip).
            if self._debug_enabled and self._overlay_mode == "debug" and ignore_top_px > 0:
                try:
                    y1h = int(max(0, min(int(H - 1), int(ignore_top_px))))
                    overlay_img = img_bgr.copy()
                    cv2.rectangle(
                        overlay_img,
                        (0, 0),
                        (int(W - 1), y1h),
                        tuple(VISION_DEBUG_FOOTER_OVERLAY_COLOR),
                        thickness=-1,
                    )
                    cv2.addWeighted(
                        overlay_img,
                        float(VISION_DEBUG_FOOTER_OVERLAY_ALPHA),
                        img_bgr,
                        1.0 - float(VISION_DEBUG_FOOTER_OVERLAY_ALPHA),
                        0.0,
                        img_bgr,
                    )
                    cv2.line(
                        img_bgr,
                        (0, y1h),
                        (int(W - 1), y1h),
                        tuple(VISION_DEBUG_FOOTER_LINE_COLOR),
                        int(VISION_DEBUG_FOOTER_LINE_THICKNESS),
                    )
                    cv2.putText(
                        img_bgr,
                        f"IGNORED HEADER: {ignore_top_px}px",
                        (int(VISION_DEBUG_FOOTER_LABEL_X0), 22),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        float(VISION_DEBUG_FOOTER_LABEL_SCALE),
                        tuple(VISION_DEBUG_FOOTER_LINE_COLOR),
                        int(VISION_DEBUG_FOOTER_LABEL_THICKNESS),
                    )
                except Exception:
                    pass

            # 5. Enviar al Brain
            frame_dets = self._dedupe_frame_detections(frame_dets)
            publish_geometry_ready = (
                math.isfinite(float(dron_alt_agl))
                and float(dron_alt_agl) >= float(MIN_AGL_TO_PUBLISH_M)
            )
            if publish_geometry_ready:
                seen_ids = self._update_tracks_from_detections(frame_dets, float(now_s))
            else:
                seen_ids = set()
                if self._tracks:
                    self._tracks.clear()

            self._source_sequence += 1
            frame_source_sequence = int(self._source_sequence)
            outgoing = []
            hold_s = float(TRACK_HOLD_S)
            if publish_geometry_ready:
                for obs_id, t in self._tracks.items():
                    seen_req = int(self._min_seen_to_publish_for_class(str(t.class_name)))
                    conf_ok = float(t.conf) >= float(PUBLISH_CONFIDENCE_THRESHOLD)
                    if obs_id in seen_ids:
                        ok = conf_ok and int(t.seen_count) >= seen_req
                    else:
                        age_s = float(now_s) - float(t.last_seen_ts)
                        ok = (
                            conf_ok
                            and math.isfinite(hold_s)
                            and hold_s > 0.0
                            and age_s <= hold_s
                            and int(t.seen_count) >= seen_req
                        )
                    if not ok:
                        continue

                    item = {
                        'id': int(t.obs_id),
                        'source_id': int(t.obs_id),
                        'lat': float(t.lat),
                        'lon': float(t.lon),
                        'distance': float(t.dist),
                        'type': str(t.class_name),
                        'confidence': float(t.conf),
                        'source': 'vision',
                        'bbox': t.bbox,
                        # Preserve observation time even while a held track is republished.
                        'source_timestamp_s': float(t.last_seen_ts),
                        'source_sequence': int(frame_source_sequence),
                        'source_session_id': str(self._source_session_id),
                        'clock_domain': 'unix_epoch_s',
                        'information_role': 'live_observation',
                    }
                    if isinstance(t.semantic_meta, dict):
                        item.update(t.semantic_meta)
                    outgoing.append(item)

            outgoing = self._collapse_dynamic_outgoing(outgoing)
            outgoing = self._collapse_static_outgoing(outgoing)
            outgoing.sort(key=lambda o: float(o.get("distance", float(MAVLINK_UNKNOWN_DISTANCE_M))))
            max_out = int(MAX_OBS_PER_FRAME) if int(MAX_OBS_PER_FRAME) > 0 else len(outgoing)
            outgoing = outgoing[:max_out]
            last_dets = int(len(frame_dets))
            last_send = int(len(outgoing))
            post_attempted = False
            post_ok = False
            post_status = None
            post_error = ""

            if outgoing:
                if detections_log_every_s <= 0.0 or now_s - detections_log_last_ts >= detections_log_every_s:
                    detections_log_last_ts = now_s
                    log(f"Dets frame={len(frame_dets)} tracks={len(self._tracks)} send={len(outgoing)}")
                post_attempted = True
                try:
                    headers = {}
                    if self._obstacle_token:
                        headers["X-PORCE-Token"] = self._obstacle_token
                    r_post = self.session.post(
                        OBSTACLES_URL,
                        json={
                            "contract_version": "1.1",
                            "source_sequence": int(frame_source_sequence),
                            "source_session_id": str(self._source_session_id),
                            "clock_domain": "unix_epoch_s",
                            "obstacles": outgoing,
                        },
                        headers=headers,
                        timeout=float(VISION_POST_TIMEOUT_S),
                    )
                    post_status = int(r_post.status_code)
                    post_ok = bool(200 <= post_status < 300)
                except Exception as e:
                    post_error = str(e)

            # Overlay for live debugging/recording. Paper mode keeps only visual evidence;
            # full forensics remain in JSONL audit and debug mode.
            if (self._debug_enabled or self._record_enabled) and self._overlay_mode != "off":
                try:
                    outgoing_ids = {int(o.get("id")) for o in outgoing if o.get("id") is not None}
                    tracks_sorted = sorted(
                        self._tracks.values(),
                        key=lambda t: float(getattr(t, "dist", float(MAVLINK_UNKNOWN_DISTANCE_M))),
                    )

                    if self._overlay_mode == "paper":
                        self._draw_paper_overlay(
                            img_bgr,
                            tracks_sorted=tracks_sorted,
                            outgoing_ids=outgoing_ids,
                            seen_ids=seen_ids,
                            telemetry=telemetry,
                            now_s=float(now_s),
                            outgoing_count=int(len(outgoing)),
                        )
                    else:
                        overlay = []
                        rej_total = int(sum(reject_counts.values()))
                        overlay.append(
                            f"FPS {self._fps_ema:.1f} | RAW {int(raw_boxes_total)} ACC {int(len(frame_dets))} "
                            f"TRK {int(len(self._tracks))} OUT {int(len(outgoing))} REJ {rej_total}"
                        )
                        post_label = "IDLE"
                        if not publish_geometry_ready:
                            post_label = "AGL_GATE"
                        if post_attempted:
                            if post_ok:
                                post_label = f"OK:{int(post_status) if post_status is not None else 200}"
                            elif post_status is not None:
                                post_label = f"HTTP:{int(post_status)}"
                            else:
                                post_label = "ERR"
                        overlay.append(
                            f"POST {post_label} | TEL {telemetry_source} | AGL {float(dron_alt_agl):.1f}m | YAW {float(dron_yaw):.1f}deg"
                        )
                        overlay.append(f"MASK top={int(ignore_top_px)}px bottom={int(ignore_bottom_px)}px")
                        if post_error:
                            msg = str(post_error).replace("\n", " ").strip()
                            overlay.append(f"POST_ERR {msg[:96]}")

                        max_n = max(0, min(3, int(self._overlay_max_obs)))
                        debug_tracks = tracks_sorted[:max_n] if max_n > 0 else []
                        hold_s = float(TRACK_HOLD_S)
                        for i, track in enumerate(debug_tracks, 1):
                            track_id = int(track.obs_id)
                            seen_req = int(self._min_seen_to_publish_for_class(str(track.class_name)))
                            seen_now = track_id in seen_ids
                            conf_ok = float(track.conf) >= float(PUBLISH_CONFIDENCE_THRESHOLD)
                            age_s = max(0.0, float(now_s) - float(track.last_seen_ts))
                            if track_id in outgoing_ids:
                                state = "pub" if seen_now else "hold"
                            elif not conf_ok:
                                state = "lowconf"
                            elif int(track.seen_count) < seen_req:
                                state = "warmup"
                            elif (not seen_now) and (age_s > hold_s):
                                state = "drop"
                            else:
                                state = "ready"
                            overlay.append(
                                f"{i}) id={track_id} {str(track.class_name)} d={float(track.dist):.1f}m "
                                f"c={float(track.conf):.2f} seen={int(track.seen_count)}/{seen_req} age={age_s:.1f}s {state}"
                            )
                            overlay.append(
                                f"   px=({int(track.cx)},{int(track.cy)}) "
                                f"gps=({float(track.lat):.6f},{float(track.lon):.6f})"
                            )

                        x0, y0 = int(VISION_DEBUG_OVERLAY_X0), int(VISION_DEBUG_OVERLAY_Y0)
                        dy = int(VISION_DEBUG_OVERLAY_LINE_STEP)
                        for idx, text in enumerate(overlay):
                            y = y0 + idx * dy
                            cv2.putText(
                                img_bgr,
                                text,
                                (x0, y),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                float(VISION_DEBUG_OVERLAY_TEXT_SCALE),
                                tuple(VISION_DEBUG_OVERLAY_OUTLINE_COLOR),
                                int(VISION_DEBUG_OVERLAY_OUTLINE_THICKNESS),
                            )
                            cv2.putText(
                                img_bgr,
                                text,
                                (x0, y),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                float(VISION_DEBUG_OVERLAY_TEXT_SCALE),
                                tuple(VISION_DEBUG_OVERLAY_TEXT_COLOR),
                                int(VISION_DEBUG_OVERLAY_TEXT_THICKNESS),
                            )
                except Exception:
                    pass

            self._record_overlay_frame(img_bgr)

            # Visualizacion (Ventana Debug) after the full overlay has been drawn.
            debug_waitkey_done = False
            if self._debug_enabled:
                try:
                    scale = float(self._debug_scale) if math.isfinite(self._debug_scale) and self._debug_scale > 0.0 else 1.0
                    if abs(scale - 1.0) > float(VISION_DEBUG_SCALE_EPS):
                        disp = cv2.resize(img_bgr, (int(W * scale), int(H * scale)), interpolation=cv2.INTER_LINEAR)
                    else:
                        disp = img_bgr
                    cv2.imshow(self._debug_title, disp)
                    debug_waitkey_done = True
                    if cv2.waitKey(max(1, int(VISION_GUI_WAITKEY_MS))) & 0xFF == ord("q"):
                        break
                except Exception:
                    pass

            # Zero-trust audit stream (frame-by-frame evidence + saved debug frames).
            if self._audit.enabled:
                try:
                    dets_for_log = sorted(frame_dets, key=lambda d: float(d.get("distance", float(MAVLINK_UNKNOWN_DISTANCE_M))))
                    max_det_n = int(AUDIT_VISION_MAX_DET_DETAILS)
                    if max_det_n > 0:
                        dets_for_log = dets_for_log[:max_det_n]
                    else:
                        dets_for_log = []
                    self._audit.log_event(
                        "vision_frame",
                        frame=int(frame_count),
                        fps=float(self._fps_ema),
                        capture={"w": int(W), "h": int(H), "mode": str(self._capture_mode)},
                        ignored_footer_px=int(ignore_bottom_px),
                        ignored_header_px=int(ignore_top_px),
                        telemetry={
                            "lat": float(dron_lat),
                            "lon": float(dron_lon),
                            "alt_msl": float(dron_alt_msl),
                            "alt_agl": float(dron_alt_agl),
                            "yaw": float(dron_yaw),
                            "pitch": float(dron_pitch),
                            "roll": float(dron_roll),
                            "drone_x_m": float(drone_x_m),
                            "drone_y_m": float(drone_y_m),
                            "drone_z_m": float(drone_z_m),
                            "source": str(telemetry_source),
                        },
                        counts={
                            "raw_boxes": int(raw_boxes_total),
                            "accepted_frame_dets": int(len(frame_dets)),
                            "tracks_active": int(len(self._tracks)),
                            "published_outgoing": int(len(outgoing)),
                        },
                        publish_gate={
                            "geometry_ready": bool(publish_geometry_ready),
                            "min_agl_to_publish_m": float(MIN_AGL_TO_PUBLISH_M),
                        },
                        reject_counts=dict(reject_counts),
                        detections=dets_for_log,
                        outgoing=outgoing,
                        post={
                            "attempted": bool(post_attempted),
                            "ok": bool(post_ok),
                            "status_code": post_status,
                            "error": post_error,
                        },
                    )
                except Exception:
                    pass

                should_save_frame = (int(frame_count) % int(AUDIT_VISION_FRAME_EVERY_N) == 0)
                if AUDIT_VISION_ONLY_WITH_DETS:
                    should_save_frame = bool(should_save_frame and (len(frame_dets) > 0 or len(outgoing) > 0))
                if should_save_frame:
                    saved = self._audit.save_frame(
                        frame_index=int(frame_count),
                        image_bgr=audit_frame_bgr if audit_frame_bgr is not None else img_bgr,
                        prefix="yolo",
                        jpeg_quality=int(AUDIT_VISION_JPEG_QUALITY),
                    )
                    if saved:
                        self._audit.log_event(
                            "vision_frame_saved",
                            frame=int(frame_count),
                            path=str(saved),
                            dets=int(len(frame_dets)),
                            outgoing=int(len(outgoing)),
                        )

            # Heartbeat for observability (also useful for E2E harnesses when detections are sparse).
            if math.isfinite(hb_every_s) and hb_every_s > 0.0:
                wall_now = time.time()
                if wall_now - hb_last_ts >= hb_every_s:
                    hb_last_ts = wall_now
                    try:
                        log(
                            f"[HB] fps={self._fps_ema:.1f} frame={frame_count} "
                            f"capture={W}x{H} dets={last_dets} tracks={len(self._tracks)} send={last_send} "
                            f"tel={telemetry_source}"
                        )
                    except Exception:
                        pass

            # Control de FPS (0 = as fast as possible). `cv2.waitKey` is required to refresh the debug window.
            if math.isfinite(self._target_fps) and self._target_fps > 0.0:
                min_period = 1.0 / float(self._target_fps)
                elapsed = time.perf_counter() - float(frame_now)
                if elapsed < min_period:
                    time.sleep(max(0.0, min_period - elapsed))

            if (not debug_waitkey_done) and cv2.waitKey(max(1, int(VISION_GUI_WAITKEY_MS))) & 0xFF == ord("q"):
                break
                 
            # log(f"Ciclo Vision: {time.perf_counter() - frame_now:.3f}s")

        cv2.destroyAllWindows()
        try:
            if self._video_capture is not None:
                self._video_capture.release()
        except Exception:
            pass
        try:
            if self._record_writer is not None:
                self._record_writer.release()
                log(f"[REC] YOLO overlay video closed: {self._record_path} frames={self._record_frame_count}")
        except Exception:
            pass
        self._record_writer = None
        try:
            self._audit.close()
        except Exception:
            pass

if __name__ == '__main__':
    VisionSystem().run()
