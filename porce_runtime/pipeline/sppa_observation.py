from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from geo_projector import GeoProjector


SPPA_OBSERVATION_SCHEMA = "SPPA-OBS-0.1"

DEFAULT_CAMERA = {
    "drone_yaw_deg": 0.0,
    "drone_pitch_deg": 0.0,
    "drone_roll_deg": 0.0,
    "camera_vfov_deg": 70.0,
    "mount_roll_deg": 0.0,
    "mount_pitch_deg": -90.0,
    "mount_yaw_deg": 0.0,
    "max_range_m": 250.0,
    "alt_agl_m": 30.0,
}

REQUIRED_CAMERA_KEYS = (
    "drone_yaw_deg",
    "drone_pitch_deg",
    "drone_roll_deg",
    "camera_vfov_deg",
    "mount_roll_deg",
    "mount_pitch_deg",
    "mount_yaw_deg",
    "max_range_m",
    "alt_agl_m",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_hash(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def finite_int(value: Any) -> Optional[int]:
    try:
        out = int(value)
    except Exception:
        return None
    return out if out > 0 else None


def normalize_bbox_xyxy(bbox: Any) -> Optional[dict[str, float]]:
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

    x1_base = finite_float(x1)
    y1_base = finite_float(y1)
    vals = [finite_float(v) for v in (x1, y1, x2, y2)]
    if x2 is None and bbox is not None and isinstance(bbox, dict) and bbox.get("w") is not None and x1_base is not None:
        vals[2] = x1_base + float(finite_float(bbox.get("w")) or 0.0)
    if y2 is None and bbox is not None and isinstance(bbox, dict) and bbox.get("h") is not None and y1_base is not None:
        vals[3] = y1_base + float(finite_float(bbox.get("h")) or 0.0)
    if any(v is None for v in vals):
        return None
    x1f, y1f, x2f, y2f = [float(v) for v in vals]
    if x2f <= x1f or y2f <= y1f:
        return None
    return {
        "x1": x1f,
        "y1": y1f,
        "x2": x2f,
        "y2": y2f,
        "w": x2f - x1f,
        "h": y2f - y1f,
        "cx": (x1f + x2f) * 0.5,
        "cy": (y1f + y2f) * 0.5,
    }


def normalize_mask_points(mask: Any) -> list[tuple[float, float]]:
    if not mask:
        return []
    if isinstance(mask, dict):
        raw = (
            mask.get("polygon")
            or mask.get("points")
            or mask.get("vertices")
            or mask.get("mask_polygon_px")
            or []
        )
    else:
        raw = mask
    if not isinstance(raw, Iterable):
        return []
    points: list[tuple[float, float]] = []
    for item in raw:
        if isinstance(item, dict):
            x = item.get("x", item.get("u", item.get("px_x")))
            y = item.get("y", item.get("v", item.get("px_y")))
        else:
            try:
                x, y = item[:2]
            except Exception:
                continue
        xf = finite_float(x)
        yf = finite_float(y)
        if xf is not None and yf is not None:
            points.append((xf, yf))
    return points


def polygon_area_px2(points: list[tuple[float, float]]) -> Optional[float]:
    if len(points) < 3:
        return None
    area = 0.0
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def _mask_evidence_metadata(mask: Any, points: list[tuple[float, float]]) -> dict[str, Any]:
    if len(points) < 3:
        return {}
    source = None
    method = None
    status = None
    quality = None
    area_px2 = polygon_area_px2(points)
    if isinstance(mask, dict):
        source = mask.get("source") or mask.get("mask_source")
        method = mask.get("method")
        status = mask.get("status")
        quality = finite_float(mask.get("quality_score", mask.get("quality")))
        provided_area = finite_float(mask.get("area_px2", mask.get("mask_area_px2", mask.get("mask_area_px"))))
        if provided_area is not None:
            area_px2 = provided_area
    return {
        "source": str(source or "supplied_mask_polygon"),
        "method": None if method is None else str(method),
        "status": None if status is None else str(status),
        "quality_score": quality,
        "area_px2": area_px2,
        "point_count": len(points),
    }


def normalize_camera(flight: Optional[dict[str, Any]]) -> dict[str, float]:
    out = dict(DEFAULT_CAMERA)
    if isinstance(flight, dict):
        for key in REQUIRED_CAMERA_KEYS:
            value = finite_float(flight.get(key))
            if value is not None:
                out[key] = value
    return out


def _pixel_center_from_evidence(bbox: Optional[dict[str, float]], mask_points: list[tuple[float, float]]) -> Optional[tuple[float, float]]:
    if mask_points:
        return (
            sum(x for x, _ in mask_points) / float(len(mask_points)),
            sum(y for _, y in mask_points) / float(len(mask_points)),
        )
    if bbox:
        return bbox["cx"], bbox["cy"]
    return None


def _project_world_center(
    center_px: Optional[tuple[float, float]],
    *,
    image_width: int,
    image_height: int,
    camera: dict[str, float],
) -> Optional[dict[str, float]]:
    if center_px is None:
        return None
    cx, cy = center_px
    projected = GeoProjector.pixel_to_ground_offset_m(
        cy,
        cx,
        image_width=image_width,
        image_height=image_height,
        **camera,
    )
    if projected is None:
        return None
    return {
        "north": float(projected["north_m"]),
        "east": float(projected["east_m"]),
        "up": 0.0,
        "distance": float(projected["distance_m"]),
    }


def _metric_footprint(
    bbox: Optional[dict[str, float]],
    mask_points: list[tuple[float, float]],
    *,
    image_width: int,
    image_height: int,
    camera: dict[str, float],
    mask_source: Optional[str] = None,
) -> tuple[Optional[dict[str, Any]], str]:
    if len(mask_points) >= 3:
        source = "mask_ground_projected_oriented_footprint"
        source_text = str(mask_source or "").lower()
        if "image_derived" in source_text or "grabcut" in source_text or "cv" in source_text:
            source = "image_derived_silhouette_ground_projected_oriented_footprint"
        elif "proxy" in source_text:
            source = "silhouette_proxy_ground_projected_oriented_footprint"
        elif "real" in source_text or "detector_mask" in source_text:
            source = "real_mask_ground_projected_oriented_footprint"
        footprint = GeoProjector.points_to_ground_footprint_m(
            mask_points,
            image_width=image_width,
            image_height=image_height,
            source=source,
            **camera,
        )
        if footprint is not None:
            return footprint, source

    if bbox is not None:
        footprint = GeoProjector.bbox_to_ground_footprint_m(
            bbox,
            image_width=image_width,
            image_height=image_height,
            **camera,
        )
        if footprint is not None:
            return footprint, "bbox_ground_projected_quad"

    return None, "no_metric_footprint"


def _covariance_matrix(position_sigma_m: float, z_sigma_m: float) -> list[list[float]]:
    p2 = float(position_sigma_m) ** 2
    z2 = float(z_sigma_m) ** 2
    return [[p2, 0.0, 0.0], [0.0, p2, 0.0], [0.0, 0.0, z2]]


def estimate_uncertainty(
    *,
    confidence: float,
    footprint: Optional[dict[str, Any]],
    world_m: Optional[dict[str, Any]],
    telemetry_measured: bool,
    used_mask: bool,
    used_bbox: bool,
    height_source: Optional[str],
    mask_source: Optional[str] = None,
    mask_quality_score: Optional[float] = None,
) -> dict[str, Any]:
    conf = max(0.0, min(1.0, float(confidence)))
    distance_m = finite_float((world_m or {}).get("distance")) or 0.0
    length_m = finite_float((footprint or {}).get("length_m")) or 0.0
    width_m = finite_float((footprint or {}).get("width_m")) or 0.0

    evidence_factor = 1.0
    yaw_sigma_deg = 60.0
    if used_mask:
        source_text = str(mask_source or "").lower()
        if "real" in source_text or "detector_mask" in source_text or "manual" in source_text:
            evidence_factor *= 0.75
            yaw_sigma_deg = 8.0
        elif "image_derived" in source_text or "grabcut" in source_text or "cv" in source_text:
            evidence_factor *= 0.95
            yaw_sigma_deg = 14.0
        elif "proxy" in source_text:
            evidence_factor *= 1.05
            yaw_sigma_deg = 18.0
        else:
            evidence_factor *= 0.85
            yaw_sigma_deg = 12.0
        q = finite_float(mask_quality_score)
        if q is not None:
            q = max(0.0, min(1.0, q))
            if q < 0.75:
                evidence_factor *= 1.0 + (0.75 - q)
                yaw_sigma_deg *= 1.0 + 0.5 * (0.75 - q)
    elif used_bbox:
        evidence_factor *= 1.15
        yaw_sigma_deg = 18.0
    else:
        evidence_factor *= 2.5
        yaw_sigma_deg = 60.0
    if not telemetry_measured:
        evidence_factor *= 1.55
    confidence_factor = 1.0 + (1.0 - conf)

    position_sigma_m = max(0.20, (0.015 * distance_m + 0.10) * evidence_factor * confidence_factor)
    scale_sigma_m = max(0.10, (0.06 * max(length_m, width_m, 1.0)) * evidence_factor * confidence_factor)
    if height_source and "prior" in height_source:
        scale_sigma_m = max(scale_sigma_m, 0.25)
    if conf < 0.5:
        yaw_sigma_deg *= 1.5

    fallback_inflation_m = max(0.5, 2.0 * position_sigma_m + scale_sigma_m)
    z_sigma_m = max(0.15, scale_sigma_m)
    visual_policy = (
        "covariance_envelope_from_metric_observation"
        if footprint is not None and world_m is not None
        else "tag_only_conservative_uncertainty_envelope"
    )
    return {
        "uncertainty_schema": "SPPA-UNCERTAINTY-0.1",
        "confidence": conf,
        "telemetry_measured": bool(telemetry_measured),
        "position_sigma_m": round(position_sigma_m, 6),
        "scale_sigma_m": round(scale_sigma_m, 6),
        "yaw_sigma_deg": round(yaw_sigma_deg, 6),
        "fallback_inflation_m": round(fallback_inflation_m, 6),
        "covariance_local_enu_m2": _covariance_matrix(position_sigma_m, z_sigma_m),
        "visual_policy": visual_policy,
        "quality_flags": {
            "used_mask": bool(used_mask),
            "used_bbox": bool(used_bbox),
            "mask_source": mask_source,
            "mask_quality_score": mask_quality_score,
            "used_metric_footprint": footprint is not None,
            "used_world_projection": world_m is not None,
            "height_from_prior": bool(height_source and "prior" in height_source),
            "telemetry_measured": bool(telemetry_measured),
        },
    }


def build_sppa_observation_contract(
    *,
    label: str,
    confidence: float,
    bbox: Any = None,
    mask: Any = None,
    image_width: Any = None,
    image_height: Any = None,
    flight: Optional[dict[str, Any]] = None,
    height_prior_m: Optional[float] = None,
    height_source: Optional[str] = None,
    track_id: Optional[str] = None,
    frame_id: Optional[int | str] = None,
    timestamp: Optional[str] = None,
    telemetry_measured: bool = False,
    metric_ground_truth: bool = False,
    source: str = "declared_assumed_flight_replay",
) -> dict[str, Any]:
    """Build the SPPA observation contract from detector evidence and UAV pose.

    This is deliberately a conservative estimator. It does not claim ground truth
    metric localization unless the caller explicitly marks the telemetry as
    measured and provides a ground-truth flag.
    """
    label_text = str(label or "unknown").strip() or "unknown"
    conf = max(0.0, min(1.0, float(confidence)))
    width = finite_int(image_width)
    height = finite_int(image_height)
    bbox_xyxy = normalize_bbox_xyxy(bbox)
    mask_points = normalize_mask_points(mask)
    mask_meta = _mask_evidence_metadata(mask, mask_points)
    camera = normalize_camera(flight)
    failures: list[str] = []

    footprint = None
    footprint_source = "no_metric_footprint"
    world_m = None
    dims_m = None
    yaw_deg = None
    yaw_ambiguous = True
    if width is None or height is None:
        failures.append("missing_image_size")
    else:
        footprint, footprint_source = _metric_footprint(
            bbox_xyxy,
            mask_points,
            image_width=width,
            image_height=height,
            camera=camera,
            mask_source=mask_meta.get("source"),
        )
        world_m = _project_world_center(
            _pixel_center_from_evidence(bbox_xyxy, mask_points),
            image_width=width,
            image_height=height,
            camera=camera,
        )
        if footprint is None:
            failures.append("metric_footprint_projection_failed")
        if world_m is None:
            failures.append("world_position_projection_failed")

    if footprint is not None:
        dims_m = {
            "length": float(footprint["length_m"]),
            "width": float(footprint["width_m"]),
        }
        hp = finite_float(height_prior_m)
        if hp is not None:
            dims_m["height"] = hp
            height_source = height_source or "declared_family_height_prior"
        yaw_deg = footprint.get("orientation_deg_axial")
        yaw_ambiguous = bool(footprint.get("yaw_ambiguous", True))

    uncertainty = estimate_uncertainty(
        confidence=conf,
        footprint=footprint,
        world_m=world_m,
        telemetry_measured=telemetry_measured,
        used_mask=len(mask_points) >= 3 and footprint_source != "bbox_ground_projected_quad",
        used_bbox=bbox_xyxy is not None,
        height_source=height_source,
        mask_source=mask_meta.get("source"),
        mask_quality_score=mask_meta.get("quality_score"),
    )
    status = "metric_observation_ready" if not failures else "tag_or_partial_observation"
    contract_core = {
        "schema": SPPA_OBSERVATION_SCHEMA,
        "label": label_text,
        "confidence": conf,
        "track_id": track_id,
        "frame_id": frame_id,
        "timestamp": timestamp,
        "bbox": bbox_xyxy,
        "mask_point_count": len(mask_points),
        "mask_source": mask_meta.get("source"),
        "image_width": width,
        "image_height": height,
        "metric_evidence_source": footprint_source,
        "telemetry_measured": bool(telemetry_measured),
        "metric_ground_truth": bool(metric_ground_truth),
        "source": source,
    }
    observation_id = f"sppa-obs-{stable_hash(contract_core)}"
    return {
        "schema": SPPA_OBSERVATION_SCHEMA,
        "observation_id": observation_id,
        "created_utc": utc_now(),
        "status": status,
        "failures": failures,
        "label": label_text,
        "confidence": conf,
        "track_id": track_id,
        "frame_id": frame_id,
        "timestamp": timestamp,
        "image_size_px": {"width": width, "height": height},
        "detector_evidence": {
            "bbox_xyxy": bbox_xyxy,
            "mask_polygon_px": [[round(x, 6), round(y, 6)] for x, y in mask_points] if mask_points else None,
            "mask_point_count": len(mask_points),
            "has_mask": bool(mask_points),
            "mask_source": mask_meta.get("source"),
            "mask_method": mask_meta.get("method"),
            "mask_status": mask_meta.get("status"),
            "mask_quality_score": mask_meta.get("quality_score"),
            "mask_area_px2": mask_meta.get("area_px2"),
        },
        "flight": {
            **camera,
            "telemetry_measured": bool(telemetry_measured),
            "source": source,
        },
        "metric": {
            "world_m": world_m,
            "footprint_m": footprint,
            "metric_dims_m": dims_m,
            "metric_evidence_source": footprint_source,
            "yaw_deg": yaw_deg,
            "yaw_ambiguous": yaw_ambiguous,
            "height_source": height_source,
            "metric_ground_truth": bool(metric_ground_truth),
        },
        "uncertainty": uncertainty,
        "claim_boundary": (
            "SPPA-OBS records detector evidence plus camera/flight geometry. Metric pose/scale are measured "
            "only when telemetry_measured and metric_ground_truth are true; otherwise they are scenario-relative "
            "runtime evidence for a verifier-gated proxy, not ground-truth reconstruction."
        ),
    }


def descriptor_kwargs_from_observation(observation: dict[str, Any]) -> dict[str, Any]:
    metric = observation.get("metric") or {}
    detector = observation.get("detector_evidence") or {}
    image_size = observation.get("image_size_px") or {}
    world_m = metric.get("world_m")
    if isinstance(world_m, dict):
        world_m = {
            "north": world_m.get("north"),
            "east": world_m.get("east"),
            "up": world_m.get("up", 0.0),
        }
    return {
        "bbox": detector.get("bbox_xyxy"),
        "mask": detector.get("mask_polygon_px"),
        "image_width": image_size.get("width"),
        "image_height": image_size.get("height"),
        "world_m": world_m,
        "metric_dims_m": metric.get("metric_dims_m"),
        "metric_dims_source": metric.get("metric_evidence_source") or "sppa_observation",
        "footprint_m": metric.get("footprint_m"),
        "yaw_deg": metric.get("yaw_deg"),
        "track_id": observation.get("track_id"),
        "frame_id": observation.get("frame_id"),
        "timestamp": observation.get("timestamp"),
        "observation_contract": observation,
        "observation_uncertainty": observation.get("uncertainty"),
    }
