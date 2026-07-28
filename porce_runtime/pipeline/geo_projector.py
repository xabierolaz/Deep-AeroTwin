from __future__ import annotations

import math
from typing import Iterable, Optional, Tuple

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
    def pixel_to_ground_offset_m(
        px_y: float,
        px_x: float,
        *,
        image_height: int,
        image_width: int,
        drone_yaw_deg: float,
        drone_pitch_deg: float,
        drone_roll_deg: float,
        alt_agl_m: float,
        camera_vfov_deg: float,
        mount_roll_deg: float,
        mount_pitch_deg: float,
        mount_yaw_deg: float,
        max_range_m: float,
        clamp_to_max_range: bool = False,
        max_range_margin_m: float = 0.0,
    ) -> Optional[dict]:
        """Project one pixel to the local ground plane.

        Returns a local NED offset from the UAV origin. This is the metric core
        used by the legacy GPS projection and by SPPA footprint estimation.
        """
        h = float(alt_agl_m)
        if not math.isfinite(h) or h < float(GEOMETRY_MIN_AGL_M):
            return None

        ray_ned = GeoProjector.pixel_to_ray_ned(
            px_y,
            px_x,
            image_height=image_height,
            image_width=image_width,
            drone_yaw_deg=drone_yaw_deg,
            drone_pitch_deg=drone_pitch_deg,
            drone_roll_deg=drone_roll_deg,
            camera_vfov_deg=camera_vfov_deg,
            mount_roll_deg=mount_roll_deg,
            mount_pitch_deg=mount_pitch_deg,
            mount_yaw_deg=mount_yaw_deg,
        )
        if ray_ned is None:
            return None

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

        max_r = float(max_range_m)
        margin_m = max(0.0, float(max_range_margin_m))
        clamped = False
        if math.isfinite(max_r) and max_r > 0.0 and dist_h > (max_r + margin_m):
            if not bool(clamp_to_max_range):
                return None
            scale = max_r / (dist_h + float(GEOMETRY_EPS))
            north_m *= scale
            east_m *= scale
            dist_h = max_r
            clamped = True

        return {
            "north_m": float(north_m),
            "east_m": float(east_m),
            "distance_m": float(dist_h),
            "ray_down": float(down),
            "range_clamped": bool(clamped),
        }

    @staticmethod
    def _point_xy(point) -> Optional[tuple[float, float]]:
        if isinstance(point, dict):
            x = point.get("x", point.get("px_x", point.get("u")))
            y = point.get("y", point.get("px_y", point.get("v")))
        else:
            try:
                x = point[0]
                y = point[1]
            except Exception:
                return None
        try:
            xf = float(x)
            yf = float(y)
        except Exception:
            return None
        if not (math.isfinite(xf) and math.isfinite(yf)):
            return None
        return xf, yf

    @staticmethod
    def _ground_footprint_from_offsets(points: list[dict], source: str) -> Optional[dict]:
        if len(points) < 2:
            return None
        arr = np.array([[float(p["north_m"]), float(p["east_m"])] for p in points], dtype=float)
        if arr.ndim != 2 or arr.shape[0] < 2:
            return None
        center = np.mean(arr, axis=0)

        if arr.shape[0] == 2:
            major = arr[1] - arr[0]
            norm = float(np.linalg.norm(major))
            if norm <= float(GEOMETRY_EPS):
                return None
            major = major / norm
            minor = np.array([-major[1], major[0]], dtype=float)
        else:
            centered = arr - center
            cov = np.cov(centered.T)
            if not np.all(np.isfinite(cov)):
                return None
            eigvals, eigvecs = np.linalg.eigh(cov)
            order = np.argsort(eigvals)[::-1]
            major = eigvecs[:, order[0]]
            minor = eigvecs[:, order[1]]
            if float(np.linalg.norm(major)) <= float(GEOMETRY_EPS):
                return None

        proj_major = arr @ major
        proj_minor = arr @ minor
        length_m = float(np.max(proj_major) - np.min(proj_major))
        width_m = float(np.max(proj_minor) - np.min(proj_minor))
        if width_m > length_m:
            length_m, width_m = width_m, length_m
            major, minor = minor, major

        yaw_deg = math.degrees(math.atan2(float(major[1]), float(major[0]))) % 180.0
        yaw_rad = math.radians(yaw_deg)
        return {
            "source": str(source),
            "point_count": int(arr.shape[0]),
            "center_north_m": float(center[0]),
            "center_east_m": float(center[1]),
            "length_m": max(0.0, float(length_m)),
            "width_m": max(0.0, float(width_m)),
            "orientation_deg_axial": float(yaw_deg),
            "orientation_rad_axial": float(yaw_rad),
            "orientation_modulo": "pi",
            "yaw_ambiguous": True,
            "points_ned_m": [
                {
                    "north_m": float(p["north_m"]),
                    "east_m": float(p["east_m"]),
                    "distance_m": float(p["distance_m"]),
                }
                for p in points
            ],
        }

    @staticmethod
    def points_to_ground_footprint_m(
        points_px: Iterable,
        *,
        image_height: int,
        image_width: int,
        drone_yaw_deg: float,
        drone_pitch_deg: float,
        drone_roll_deg: float,
        alt_agl_m: float,
        camera_vfov_deg: float,
        mount_roll_deg: float,
        mount_pitch_deg: float,
        mount_yaw_deg: float,
        max_range_m: float,
        source: str,
        clamp_to_max_range: bool = False,
        max_range_margin_m: float = 0.0,
        max_points: int = 64,
    ) -> Optional[dict]:
        raw_points = [p for p in points_px or []]
        if len(raw_points) > max(2, int(max_points)):
            step = max(1, int(math.ceil(len(raw_points) / float(max_points))))
            raw_points = raw_points[::step]

        ground_points: list[dict] = []
        for point in raw_points:
            xy = GeoProjector._point_xy(point)
            if xy is None:
                continue
            x, y = xy
            ground = GeoProjector.pixel_to_ground_offset_m(
                y,
                x,
                image_height=image_height,
                image_width=image_width,
                drone_yaw_deg=drone_yaw_deg,
                drone_pitch_deg=drone_pitch_deg,
                drone_roll_deg=drone_roll_deg,
                alt_agl_m=alt_agl_m,
                camera_vfov_deg=camera_vfov_deg,
                mount_roll_deg=mount_roll_deg,
                mount_pitch_deg=mount_pitch_deg,
                mount_yaw_deg=mount_yaw_deg,
                max_range_m=max_range_m,
                clamp_to_max_range=clamp_to_max_range,
                max_range_margin_m=max_range_margin_m,
            )
            if ground is not None:
                ground_points.append(ground)

        return GeoProjector._ground_footprint_from_offsets(ground_points, source)

    @staticmethod
    def bbox_to_ground_footprint_m(
        bbox,
        *,
        image_height: int,
        image_width: int,
        drone_yaw_deg: float,
        drone_pitch_deg: float,
        drone_roll_deg: float,
        alt_agl_m: float,
        camera_vfov_deg: float,
        mount_roll_deg: float,
        mount_pitch_deg: float,
        mount_yaw_deg: float,
        max_range_m: float,
        clamp_to_max_range: bool = False,
        max_range_margin_m: float = 0.0,
    ) -> Optional[dict]:
        if isinstance(bbox, dict):
            x1 = bbox.get("x1", bbox.get("left"))
            y1 = bbox.get("y1", bbox.get("top"))
            x2 = bbox.get("x2", bbox.get("right"))
            y2 = bbox.get("y2", bbox.get("bottom"))
        else:
            try:
                x1, y1, x2, y2 = bbox
            except Exception:
                return None
        try:
            x1f, y1f, x2f, y2f = float(x1), float(y1), float(x2), float(y2)
        except Exception:
            return None
        if not all(math.isfinite(v) for v in (x1f, y1f, x2f, y2f)):
            return None
        if x2f <= x1f or y2f <= y1f:
            return None

        points = [
            (x1f, y1f),
            (x2f, y1f),
            (x2f, y2f),
            (x1f, y2f),
            ((x1f + x2f) / 2.0, y1f),
            ((x1f + x2f) / 2.0, y2f),
            (x1f, (y1f + y2f) / 2.0),
            (x2f, (y1f + y2f) / 2.0),
        ]
        footprint = GeoProjector.points_to_ground_footprint_m(
            points,
            image_height=image_height,
            image_width=image_width,
            drone_yaw_deg=drone_yaw_deg,
            drone_pitch_deg=drone_pitch_deg,
            drone_roll_deg=drone_roll_deg,
            alt_agl_m=alt_agl_m,
            camera_vfov_deg=camera_vfov_deg,
            mount_roll_deg=mount_roll_deg,
            mount_pitch_deg=mount_pitch_deg,
            mount_yaw_deg=mount_yaw_deg,
            max_range_m=max_range_m,
            clamp_to_max_range=clamp_to_max_range,
            max_range_margin_m=max_range_margin_m,
            source="bbox_ground_projected_quad",
        )
        if footprint is not None:
            footprint["bbox_px"] = {"x1": x1f, "y1": y1f, "x2": x2f, "y2": y2f}
        return footprint

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
        clamp_to_max_range: bool = False,
        max_range_margin_m: float = 0.0,
    ) -> Optional[Tuple[float, float, float]]:
        """Backward-compatible three-value GPS projection.

        New producers that need degradation metadata should call
        :meth:`pixel_to_gps_detailed`; this wrapper intentionally preserves the
        historical ``(lat, lon, distance_m)`` result.
        """
        detailed = GeoProjector.pixel_to_gps_detailed(
            px_y,
            px_x,
            image_height=image_height,
            image_width=image_width,
            drone_lat=drone_lat,
            drone_lon=drone_lon,
            drone_yaw_deg=drone_yaw_deg,
            drone_pitch_deg=drone_pitch_deg,
            drone_roll_deg=drone_roll_deg,
            alt_agl_m=alt_agl_m,
            camera_vfov_deg=camera_vfov_deg,
            mount_roll_deg=mount_roll_deg,
            mount_pitch_deg=mount_pitch_deg,
            mount_yaw_deg=mount_yaw_deg,
            max_range_m=max_range_m,
            clamp_to_max_range=clamp_to_max_range,
            max_range_margin_m=max_range_margin_m,
        )
        if detailed is None:
            return None
        return (
            float(detailed["lat"]),
            float(detailed["lon"]),
            float(detailed["distance_m"]),
        )

    @staticmethod
    def pixel_to_gps_detailed(
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
        clamp_to_max_range: bool = False,
        max_range_margin_m: float = 0.0,
    ) -> Optional[dict]:
        """Project a pixel and retain range-clamp provenance for consumers."""
        offset = GeoProjector.pixel_to_ground_offset_m(
            px_y,
            px_x,
            image_height=image_height,
            image_width=image_width,
            drone_yaw_deg=drone_yaw_deg,
            drone_pitch_deg=drone_pitch_deg,
            drone_roll_deg=drone_roll_deg,
            alt_agl_m=alt_agl_m,
            camera_vfov_deg=camera_vfov_deg,
            mount_roll_deg=mount_roll_deg,
            mount_pitch_deg=mount_pitch_deg,
            mount_yaw_deg=mount_yaw_deg,
            max_range_m=max_range_m,
            clamp_to_max_range=clamp_to_max_range,
            max_range_margin_m=max_range_margin_m,
        )
        if offset is None:
            return None
        obj_lat, obj_lon = GeoProjector._offset_latlon(
            float(drone_lat),
            float(drone_lon),
            float(offset["north_m"]),
            float(offset["east_m"]),
        )
        range_clamped = bool(offset.get("range_clamped", False))
        return {
            "lat": float(obj_lat),
            "lon": float(obj_lon),
            "north_m": float(offset["north_m"]),
            "east_m": float(offset["east_m"]),
            "distance_m": float(offset["distance_m"]),
            "ray_down": float(offset["ray_down"]),
            "range_clamped": range_clamped,
            "monocular_height_allowed": not range_clamped,
        }

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
