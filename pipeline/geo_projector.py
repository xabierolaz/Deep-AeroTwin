from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np
from constants import (
    EARTH_RADIUS_M,
    GEOMETRY_COS_LAT_EPS,
    GEOMETRY_EPS,
    GEOMETRY_UNIT_EPS,
    GEOMETRY_MIN_AGL_M,
    GEOMETRY_MIN_VFOV_DEG,
    GEOMETRY_MAX_VFOV_DEG,
)

# Keep this module lightweight so unit tests can import it without pulling in
# Ultralytics/OpenCV/MSS (which have heavier side effects and system deps).


class GeoProjector:
    """Project 2D pixels to a ground-plane GPS point (lat/lon) using pinhole + attitude.

    Zero-trust:
    - No heuristic distance-from-Y hacks.
    - If the ray does not intersect the ground plane (e.g. above horizon), returns None.

    Limitations:
    - Locally flat terrain under the vehicle (needs AGL).
    - Approx intrinsics from VFOV + aspect ratio (no full calibration model).
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
        # Local projection (good enough for offsets <~1km).
        R = float(EARTH_RADIUS_M)
        lat_rad = math.radians(float(drone_lat))
        dlat = float(north_m) / R
        cos_lat = float(math.cos(lat_rad)) if math.isfinite(float(math.cos(lat_rad))) else float(GEOMETRY_COS_LAT_EPS)
        denom = R * (cos_lat if cos_lat > 0 else float(GEOMETRY_COS_LAT_EPS))
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

        # Clamp (YOLO can produce bboxes slightly outside the frame).
        u = float(max(0.0, min(float(image_width - 1), float(px_x))))
        v = float(max(0.0, min(float(image_height - 1), float(px_y))))

        h = float(alt_agl_m)
        if not math.isfinite(h) or h < float(GEOMETRY_MIN_AGL_M):
            return None

        vfov_rad = math.radians(float(camera_vfov_deg))
        if not (float(GEOMETRY_MIN_VFOV_DEG) < vfov_rad < math.radians(float(GEOMETRY_MAX_VFOV_DEG))):
            return None

        # Camera intrinsics from VFOV + aspect ratio.
        H = float(image_height)
        W = float(image_width)
        fy = (H / 2.0) / math.tan(vfov_rad / 2.0)
        hfov_rad = 2.0 * math.atan(math.tan(vfov_rad / 2.0) * (W / H))
        fx = (W / 2.0) / math.tan(hfov_rad / 2.0)
        cx = W / 2.0
        cy = H / 2.0

        # OpenCV camera frame: x right, y down, z forward.
        x_cam = (u - cx) / fx
        y_cam = (v - cy) / fy
        z_cam = 1.0
        ray_cam = np.array([x_cam, y_cam, z_cam], dtype=float)
        ray_cam = ray_cam / (np.linalg.norm(ray_cam) + float(GEOMETRY_UNIT_EPS))

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
        R_mount = GeoProjector._rot_z(mount_yaw_deg) @ GeoProjector._rot_y(mount_pitch_deg) @ GeoProjector._rot_x(
            mount_roll_deg
        )
        ray_body = R_mount @ (R_body_cam_align @ ray_cam)

        # Body -> NED using vehicle attitude.
        R_ned_body = GeoProjector._ned_from_body(float(drone_yaw_deg), float(drone_pitch_deg), float(drone_roll_deg))
        ray_ned = R_ned_body @ ray_body

        # Intersect with ground plane at z = h (NED down positive).
        down = float(ray_ned[2])
        if not math.isfinite(down) or down <= float(GEOMETRY_COS_LAT_EPS):
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
            scale = max_r / (dist_h + float(GEOMETRY_EPS))
            north_m *= scale
            east_m *= scale
            dist_h = max_r

        obj_lat, obj_lon = GeoProjector._offset_latlon(float(drone_lat), float(drone_lon), north_m, east_m)
        return float(obj_lat), float(obj_lon), float(dist_h)

    @staticmethod
    def pixel_to_ray_ned(
        px_y: float,
        px_x: float,
        *,
        image_height: int,
        image_width: int,
        drone_yaw_deg: float,
        drone_pitch_deg: float,
        drone_roll_deg: float,
        camera_vfov_deg: float,
        mount_roll_deg: float,
        mount_pitch_deg: float,
        mount_yaw_deg: float,
    ) -> Optional[np.ndarray]:
        """Return a unit ray in NED coordinates for the given pixel.

        NED: x=north, y=east, z=down.
        """
        if image_height <= 0 or image_width <= 0:
            return None

        u = float(max(0.0, min(float(image_width - 1), float(px_x))))
        v = float(max(0.0, min(float(image_height - 1), float(px_y))))

        vfov_rad = math.radians(float(camera_vfov_deg))
        if not (0.01 < vfov_rad < math.radians(179.0)):
            return None

        H = float(image_height)
        W = float(image_width)
        fy = (H / 2.0) / math.tan(vfov_rad / 2.0)
        hfov_rad = 2.0 * math.atan(math.tan(vfov_rad / 2.0) * (W / H))
        fx = (W / 2.0) / math.tan(hfov_rad / 2.0)
        cx = W / 2.0
        cy = H / 2.0

        x_cam = (u - cx) / fx
        y_cam = (v - cy) / fy
        z_cam = 1.0
        ray_cam = np.array([x_cam, y_cam, z_cam], dtype=float)
        ray_cam = ray_cam / (np.linalg.norm(ray_cam) + float(GEOMETRY_UNIT_EPS))

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

        R_mount = GeoProjector._rot_z(mount_yaw_deg) @ GeoProjector._rot_y(mount_pitch_deg) @ GeoProjector._rot_x(
            mount_roll_deg
        )
        ray_body = R_mount @ (R_body_cam_align @ ray_cam)

        R_ned_body = GeoProjector._ned_from_body(float(drone_yaw_deg), float(drone_pitch_deg), float(drone_roll_deg))
        ray_ned = R_ned_body @ ray_body
        ray_ned = ray_ned / (np.linalg.norm(ray_ned) + float(GEOMETRY_UNIT_EPS))
        return ray_ned
