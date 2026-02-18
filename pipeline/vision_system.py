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
    VISION_CAPTURE_WINDOW_TOPMOST,
    VISION_CAPTURE_MONITOR,
    VISION_CAPTURE_LEFT,
    VISION_CAPTURE_TOP,
    VISION_CAPTURE_WIDTH,
    VISION_CAPTURE_HEIGHT,
    VISION_DEBUG_TITLE,
    VISION_DEBUG_WINDOW,
    VISION_DEBUG_SCALE,
    VISION_DEBUG_DOCK,
    VISION_DEBUG_DOCK_GAP_PX,
    VISION_DEBUG_TOPMOST,
    VISION_TARGET_FPS,
    VISION_OVERLAY_MAX_OBS,
    VISION_DET_CONF,
    VISION_PUBLISH_CONF,
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
    VISION_YOLO_MODEL,
    VISION_MODEL_FALLBACK_COCO,
    VISION_MODEL_FALLBACK_SYNTH,
    OBSTACLE_TOKEN,
    VISION_TRACK_TTL_S,
    VISION_TRACK_HOLD_S,
    VISION_SMOOTH_TAU_S,
    VISION_TRACK_DENOM_EPS,
    VISION_TRACK_SMOOTH_DENOM_EPS,
    VISION_TRACK_COS_DENOM_EPS,
    VISION_ID_BUCKET_PX,
    VISION_ID_CLASS_OFFSET,
    VISION_ID_COORD_SCALE,
    VISION_MAX_OBS_PER_FRAME,
    VISION_HEARTBEAT_S,
    OBSTACLE_TOKEN_REQUIRED,
    VISION_IGNORE_BOTTOM_PX,
    VISION_IGNORE_BOTTOM_FRAC,
    AUDIT_VISION_FRAME_EVERY_N,
    AUDIT_VISION_ONLY_WITH_DETS,
    AUDIT_VISION_MAX_DET_DETAILS,
    AUDIT_VISION_JPEG_QUALITY,
    VISION_TELEMETRY_TIMEOUT_S,
    VISION_SLEEP_NO_TELEMETRY_S,
    VISION_SLEEP_NO_WINDOW_S,
    VISION_SLEEP_INVALID_MONITOR_S,
    VISION_SLEEP_NO_MONITOR_S,
    VISION_POST_TIMEOUT_S,
    VISION_GUI_WAITKEY_MS,
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
    VISION_DEBUG_SCALE_EPS,
    GEOMETRY_COS_LAT_EPS,
    GEOMETRY_EPS,
    GEOMETRY_UNIT_EPS,
    GEOMETRY_PIXEL_EPS,
    VISION_HEIGHT_DIST_FLOOR_M,
)
from zero_trust_audit import ZeroTrustAudit

# --- CONSTANTES DE VISION ---
TARGET_CLASS_NAMES = list(VISION_TARGET_CLASS_NAMES)

# Split detection threshold (model output) and publish threshold (what is sent to Brain).
DETECTION_CONFIDENCE_THRESHOLD = float(VISION_DET_CONF)
PUBLISH_CONFIDENCE_THRESHOLD = float(VISION_PUBLISH_CONF)

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
ID_BUCKET_PX = int(VISION_ID_BUCKET_PX)
MAX_OBS_PER_FRAME = int(VISION_MAX_OBS_PER_FRAME)
HEARTBEAT_S = float(VISION_HEARTBEAT_S)
IGNORE_BOTTOM_PX = int(VISION_IGNORE_BOTTOM_PX)
IGNORE_BOTTOM_FRAC = float(VISION_IGNORE_BOTTOM_FRAC)
AUDIT_VISION_FRAME_EVERY_N = int(AUDIT_VISION_FRAME_EVERY_N)
AUDIT_VISION_ONLY_WITH_DETS = bool(AUDIT_VISION_ONLY_WITH_DETS)
AUDIT_VISION_MAX_DET_DETAILS = int(AUDIT_VISION_MAX_DET_DETAILS)
AUDIT_VISION_JPEG_QUALITY = int(AUDIT_VISION_JPEG_QUALITY)

MODEL_PATH = str(VISION_YOLO_MODEL)

# Back-compat fallbacks (older docs referenced COCO weights).
if not os.path.exists(MODEL_PATH):
    if os.path.exists(str(VISION_MODEL_FALLBACK_COCO)):
        MODEL_PATH = str(VISION_MODEL_FALLBACK_COCO)
    elif os.path.exists(str(VISION_MODEL_FALLBACK_SYNTH)):
        MODEL_PATH = str(VISION_MODEL_FALLBACK_SYNTH)

BRAIN_URL = f"http://{BRAIN_HTTP_HOST}:{MAVLINK_HUB_HTTP_PORT}"
TELEMETRY_URL = f"{BRAIN_URL}/api/state/latest"
OBSTACLES_URL = f"{BRAIN_URL}/api/obstacles"

def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] [VISION-YOLO] {msg}", flush=True)


def _truthy(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


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
            # If the custom names are missing, fall back to known COCO labels.
            if not any(n in id_by_name for n in target_names):
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
                f"min_h={MIN_BOX_HEIGHT_PX:.1f}px "
                f"min_area={MIN_BOX_AREA_FRAC:.6f} "
                f"max_area_global={MAX_BOX_AREA_FRAC:.3f} "
                f"max_area[biker]={MAX_BOX_AREA_FRAC_BIKER:.3f} "
                f"max_area[cow]={MAX_BOX_AREA_FRAC_COW:.3f} "
                f"max_area[tower]={MAX_BOX_AREA_FRAC_TOWER:.3f} "
                f"min_seen_default={MIN_SEEN_TO_PUBLISH} "
                f"ignore_bottom_px={IGNORE_BOTTOM_PX} "
                f"ignore_bottom_frac={IGNORE_BOTTOM_FRAC:.3f}"
            )
        except Exception as e:
            log(f"ERROR CRITICO cargando modelo: {e}")
            sys.exit(1)

        # Projection config (defaults tuned for Pipeline A SIM).
        # Camera tilt: 30deg down from horizon => mount_pitch=-30deg unless overridden.
        self._camera_vfov_deg = float(VISION_CAMERA_VFOV_DEG)
        self._mount_roll_deg = float(VISION_CAMERA_MOUNT_ROLL_DEG)
        self._mount_pitch_deg = float(VISION_CAMERA_MOUNT_PITCH_DEG)
        self._mount_yaw_deg = float(VISION_CAMERA_MOUNT_YAW_DEG)
        self.projector = GeoProjector()
        self.sct = mss.mss()
        self.session = requests.Session()
        self._obstacle_token = str(OBSTACLE_TOKEN)
        if OBSTACLE_TOKEN_REQUIRED and not self._obstacle_token:
            log("[WARN] PORCE_OBSTACLE_TOKEN_REQUIRED=1 pero PORCE_OBSTACLE_TOKEN no esta definido; Brain rechazara /api/obstacles.")

        # --- Capture configuration ---
        # Pipeline A expectation: Unreal "Play In New Window" renders the drone camera at 640x640.
        self._expect_w = int(VISION_CAPTURE_EXPECT_WIDTH)
        self._expect_h = int(VISION_CAPTURE_EXPECT_HEIGHT)

        # Preferred: capture by window title (robust against being behind other windows).
        self._capture_window_title = str(VISION_CAPTURE_WINDOW_TITLE).strip()
        self._capture_window_class = str(VISION_CAPTURE_WINDOW_CLASS).strip()
        self._capture_window_exact = _truthy(VISION_CAPTURE_WINDOW_EXACT)
        self._capture_window_focus = _truthy(VISION_CAPTURE_WINDOW_FOCUS)
        self._capture_window_topmost = _truthy(VISION_CAPTURE_WINDOW_TOPMOST)
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

        # FPS measurement (EMA).
        self._last_frame_ts = None
        self._fps_ema = 0.0

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

        # Simple temporal stabilizer (reduces bbox/telemetry jitter in the projected lat/lon).
        self._tracks: dict[int, VisionTrack] = {}
        # Ensure we log once when the PIE window becomes available.
        self._capture_found_logged = bool(self._capture_hwnd and self.monitor)
        self._capture_size_warned: Optional[Tuple[int, int]] = None

        # Zero-trust audit sink (shared session root via PORCE_AUDIT_ROOT).
        self._audit = ZeroTrustAudit(component="vision")
        if self._audit.enabled:
            self._audit.log_event(
                "vision_config",
                det_conf=float(DETECTION_CONFIDENCE_THRESHOLD),
                publish_conf=float(PUBLISH_CONFIDENCE_THRESHOLD),
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
                ignore_bottom_px=int(IGNORE_BOTTOM_PX),
                ignore_bottom_frac=float(IGNORE_BOTTOM_FRAC),
                capture_mode=str(self._capture_mode),
                capture_title=str(self._capture_window_title),
                capture_class=str(self._capture_window_class),
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

    def get_telemetry(self):
        try:
            r = self.session.get(TELEMETRY_URL, timeout=float(VISION_TELEMETRY_TIMEOUT_S))
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
        alpha = 1.0 - math.exp(-dt / tau)
        return max(0.0, min(1.0, float(alpha)))

    @staticmethod
    def _make_obs_id(cls: int, cx: float, cy: float) -> int:
        bucket = int(ID_BUCKET_PX) if int(ID_BUCKET_PX) > 0 else 64
        coord_scale = max(1, int(VISION_ID_COORD_SCALE))
        class_offset = max(1, int(VISION_ID_CLASS_OFFSET))
        bx = int(max(0.0, float(cx)) // bucket)
        by = int(max(0.0, float(cy)) // bucket)
        return int((int(cls) + 1) * int(class_offset) + by * int(coord_scale) + bx)

    def _footer_ignore_px(self, image_h: int) -> int:
        if int(image_h) <= int(GEOMETRY_PIXEL_EPS):
            return 0
        by_frac = int(round(float(IGNORE_BOTTOM_FRAC) * float(image_h)))
        px = max(int(IGNORE_BOTTOM_PX), int(by_frac))
        return max(0, min(int(image_h - 1), int(px)))

    @staticmethod
    def _class_name_key(class_name: str) -> str:
        return str(class_name or "").strip().lower()

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

    def run(self):
        log("Sistema listo. Esperando visualizacion...")

        hb_every_s = float(HEARTBEAT_S)
        hb_last_ts = time.time()
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
            telemetry = self.get_telemetry()
            if not telemetry:
                # Si no hay telemetria, esperamos
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

            # 2. Captura de Pantalla
            if self._capture_mode == "window":
                if not self._capture_hwnd:
                    self._capture_hwnd = self._win32_find_window()
                    if self._capture_hwnd:
                        self._win32_prepare_window(self._capture_hwnd)
                if not self._capture_hwnd:
                    # No window yet (Unreal PIE not started?)
                    time.sleep(float(VISION_SLEEP_NO_WINDOW_S))
                    continue

                self.monitor = self._win32_client_region(self._capture_hwnd)
                if not self.monitor:
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

                cur_w = int(self.monitor.get("width", 0) or 0)
                cur_h = int(self.monitor.get("height", 0) or 0)
                if (cur_w != int(self._expect_w)) or (cur_h != int(self._expect_h)):
                    if self._capture_size_warned != (cur_w, cur_h):
                        log(f"[WARN] Client area is {cur_w}x{cur_h} (expected {self._expect_w}x{self._expect_h}). Projection assumes the true camera viewport.")
                        self._capture_size_warned = (cur_w, cur_h)

                # Keep on top if requested (helps if the window gets covered).
                self._win32_prepare_window(self._capture_hwnd)
                self._maybe_dock_debug_window()

            if not self.monitor:
                time.sleep(float(VISION_SLEEP_NO_MONITOR_S))
                continue

            screenshot = np.array(self.sct.grab(self.monitor))
            # Convertir BGRA a BGR
            img_bgr = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            frame_count += 1

            H, W = img_bgr.shape[:2]
            ignore_bottom_px = self._footer_ignore_px(int(H))
            ignore_top_y = int(H - ignore_bottom_px)
            infer_bgr = img_bgr
            if ignore_bottom_px > 0:
                # Mask persistent footer UI/logos so YOLO does not learn/detect them.
                infer_bgr = img_bgr.copy()
                infer_bgr[ignore_top_y:int(H), :] = 0

            # 3. Inferencia YOLO
            # Filter by class IDs when available (reduces spurious detections on COCO weights).
            class_filter = getattr(self, "_target_class_ids", None)
            if not class_filter:
                results = self.model.predict(infer_bgr, conf=DETECTION_CONFIDENCE_THRESHOLD, verbose=False)
            else:
                results = self.model.predict(
                    infer_bgr,
                    conf=DETECTION_CONFIDENCE_THRESHOLD,
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
            frame_dets: dict[int, dict] = {}
            raw_boxes_total = 0
            reject_counts: dict[str, int] = defaultdict(int)
            reject_box_color = (0, 165, 255)
              
            # 4. Procesar Detecciones
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    raw_boxes_total += 1
                    # Bounding Box
                    x1, y1, x2, y2 = box.xyxy[0]
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    class_name = str(self.model.names[cls])
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
                    if reject_reason:
                        if self._debug_enabled:
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
                        reject_counts["projection_failed"] += 1
                        if self._debug_enabled:
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
                    obj_lat, obj_lon, dist = projected

                    # Local ENU coordinates for overlay/debug (meters).
                    obj_x_m = obj_y_m = 0.0
                    if self._origin_lat is not None and self._origin_lon is not None:
                        obj_x_m, obj_y_m = self._enu_xy_m(self._origin_lat, self._origin_lon, float(obj_lat), float(obj_lon))

                    # Estimate object "height" (z, meters up) from bbox top vs base intersection.
                    obj_z_m = 0.0
                    obj_alt_msl_est = float(ground_msl)
                    try:
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
                     
                    label = f"{class_name} {conf:.2f} | {dist:.1f}m z={obj_z_m:.1f}m"
                     
                    # Dibujar en Debug
                    cv2.rectangle(
                        img_bgr,
                        (x1, y1),
                        (x2, y2),
                        tuple(VISION_DEBUG_BBOX_COLOR),
                        int(VISION_DEBUG_BBOX_THICKNESS),
                    )
                    cv2.putText(
                        img_bgr,
                        label,
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        float(VISION_DEBUG_BBOX_LABEL_SCALE),
                        tuple(VISION_DEBUG_BBOX_LABEL_COLOR),
                        int(VISION_DEBUG_BBOX_LABEL_THICKNESS),
                    )
                    
                    # Agregar a lista para enviar al Brain (con ID estable por bucket de pixeles)
                    obs_id = self._make_obs_id(cls, cx, cy)
                    prev = frame_dets.get(obs_id)
                    if (prev is None) or (conf > float(prev.get("confidence", 0.0))):
                        frame_dets[obs_id] = {
                            'id': int(obs_id),
                            'lat': float(obj_lat),
                            'lon': float(obj_lon),
                            'alt_msl': float(obj_alt_msl_est),
                            'distance': float(dist),
                            'type': str(class_name),
                            'confidence': float(conf),
                            'source': 'vision',
                            'bbox': {'x1': int(x1), 'y1': int(y1), 'x2': int(x2), 'y2': int(y2)},
                            'cx': float(cx),
                            'cy': float(cy),
                            # Debug-only local frame (ENU meters, z=up/height).
                            'x_m': float(obj_x_m),
                            'y_m': float(obj_y_m),
                            'z_m': float(obj_z_m),
                        }

            # Overlay debug telemetry in the YOLO window (zero-trust: this is the current estimate).
            if self._debug_enabled:
                try:
                    overlay = []
                    overlay.append(f"FPS: {self._fps_ema:.1f}  Dets: {len(frame_dets)}  Tracks: {len(self._tracks)}")
                    overlay.append(f"Raw boxes: {int(raw_boxes_total)}  Rej: {int(sum(reject_counts.values()))}")
                    overlay.append("XYZ frame: ENU meters (x=East, y=North, z=Up/height)")
                    overlay.append(
                        f"DRONE lat={float(dron_lat):.6f} lon={float(dron_lon):.6f} alt_msl={float(dron_alt_msl):.1f}m agl={float(dron_alt_agl):.1f}m"
                    )
                    overlay.append(
                        f"DRONE RPY deg: roll={float(dron_roll):.1f} pitch={float(dron_pitch):.1f} yaw={float(dron_yaw):.1f}"
                    )
                    overlay.append(f"DRONE XYZ[m]: x={float(drone_x_m):.1f} y={float(drone_y_m):.1f} z={float(drone_z_m):.1f}")
                    if self._origin_lat is None:
                        overlay.append("(waiting for GPS to set local origin...)")

                    dets_sorted = sorted(frame_dets.values(), key=lambda d: float(d.get("distance", float(MAVLINK_UNKNOWN_DISTANCE_M))))
                    max_n = max(0, int(self._overlay_max_obs))
                    if max_n > 0:
                        dets_sorted = dets_sorted[:max_n]
                    for i, d in enumerate(dets_sorted, 1):
                        overlay.append(
                            f"{i}) {d.get('type')} conf={float(d.get('confidence', 0.0)):.2f} d={float(d.get('distance', 0.0)):.1f}m "
                            f"XYZ=({float(d.get('x_m', 0.0)):.1f},{float(d.get('y_m', 0.0)):.1f},{float(d.get('z_m', 0.0)):.1f}) "
                            f"lat={float(d.get('lat', 0.0)):.6f} lon={float(d.get('lon', 0.0)):.6f} alt~{float(d.get('alt_msl', 0.0)):.1f}m"
                        )

                    x0, y0 = int(VISION_DEBUG_OVERLAY_X0), int(VISION_DEBUG_OVERLAY_Y0)
                    dy = int(VISION_DEBUG_OVERLAY_LINE_STEP)
                    for idx, text in enumerate(overlay):
                        y = y0 + idx * dy
                        # Outline for readability
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

            # Visual hint of ignored footer area (zero-trust auditability in debug view).
            if self._debug_enabled and ignore_bottom_px > 0:
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

            # 5. Visualizacion (Ventana Debug)
            if self._debug_enabled:
                try:
                    scale = float(self._debug_scale) if math.isfinite(self._debug_scale) and self._debug_scale > 0.0 else 1.0
                    if abs(scale - 1.0) > float(VISION_DEBUG_SCALE_EPS):
                        disp = cv2.resize(img_bgr, (int(W * scale), int(H * scale)), interpolation=cv2.INTER_LINEAR)
                    else:
                        disp = img_bgr
                    cv2.imshow(self._debug_title, disp)
                except Exception:
                    pass
            
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
                log(f"Dets frame={len(frame_dets)} tracks={len(self._tracks)} send={len(outgoing)}")
                post_attempted = True
                try:
                    headers = {}
                    if self._obstacle_token:
                        headers["X-PORCE-Token"] = self._obstacle_token
                    r_post = self.session.post(OBSTACLES_URL, json={"obstacles": outgoing}, headers=headers, timeout=float(VISION_POST_TIMEOUT_S))
                    post_status = int(r_post.status_code)
                    post_ok = bool(200 <= post_status < 300)
                except Exception as e:
                    post_error = str(e)

            # Zero-trust audit stream (frame-by-frame evidence + saved debug frames).
            if self._audit.enabled:
                try:
                    dets_for_log = sorted(frame_dets.values(), key=lambda d: float(d.get("distance", float(MAVLINK_UNKNOWN_DISTANCE_M))))
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
                        },
                        counts={
                            "raw_boxes": int(raw_boxes_total),
                            "accepted_frame_dets": int(len(frame_dets)),
                            "tracks_active": int(len(self._tracks)),
                            "published_outgoing": int(len(outgoing)),
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
                        image_bgr=img_bgr,
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
                            f"capture={W}x{H} dets={last_dets} tracks={len(self._tracks)} send={last_send}"
                        )
                    except Exception:
                        pass

            # Control de FPS (0 = as fast as possible). `cv2.waitKey` is required to refresh the debug window.
            if math.isfinite(self._target_fps) and self._target_fps > 0.0:
                min_period = 1.0 / float(self._target_fps)
                elapsed = time.perf_counter() - float(frame_now)
                if elapsed < min_period:
                    time.sleep(max(0.0, min_period - elapsed))

            if cv2.waitKey(max(1, int(VISION_GUI_WAITKEY_MS))) & 0xFF == ord("q"):
                break
                 
            # log(f"Ciclo Vision: {time.perf_counter() - frame_now:.3f}s")

        cv2.destroyAllWindows()
        try:
            self._audit.close()
        except Exception:
            pass

if __name__ == '__main__':
    VisionSystem().run()

