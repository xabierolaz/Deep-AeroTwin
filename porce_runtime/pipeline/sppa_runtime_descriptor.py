from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from typing import Any, Optional


_GENERATOR_MODULE = None


def _load_generator():
    global _GENERATOR_MODULE
    if _GENERATOR_MODULE is not None:
        return _GENERATOR_MODULE

    root = Path(__file__).resolve().parents[1]
    generator_path = root / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"
    if not generator_path.exists():
        return None

    spec = importlib.util.spec_from_file_location("sppa_xyt_generate_3d_runtime", generator_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _GENERATOR_MODULE = module
    return _GENERATOR_MODULE


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


VERTICAL_STRUCTURE_LABELS = {
    "tower",
    "vertical_structure",
    "power_tower",
    "electric_pylon",
    "pylon",
    "pole",
    "mast",
}


def _dim_limits(name: str, label: Optional[str], archetype: Optional[str]) -> tuple[float, float]:
    limits = {
        "length": (0.15, 50.0),
        "width": (0.15, 12.0),
        "height": (0.15, 20.0),
    }
    low, high = limits[name]
    family = {str(label or "").strip().lower(), str(archetype or "").strip().lower()}
    if name == "height" and family & VERTICAL_STRUCTURE_LABELS:
        high = 80.0
    return low, high


def _clamp_dim(name: str, value: float, label: Optional[str], archetype: Optional[str]) -> float:
    low, high = _dim_limits(name, label, archetype)
    return max(low, min(high, float(value)))


def _normalize_dims(
    metric_dims_m: Optional[dict],
    default_height_m: Optional[float],
    label: Optional[str] = None,
    archetype: Optional[str] = None,
) -> Optional[dict]:
    if not isinstance(metric_dims_m, dict):
        return None
    length = _finite_float(metric_dims_m.get("length", metric_dims_m.get("length_m")))
    width = _finite_float(metric_dims_m.get("width", metric_dims_m.get("width_m")))
    height = _finite_float(metric_dims_m.get("height", metric_dims_m.get("height_m")))
    if height is None:
        height = _finite_float(default_height_m)
    if length is None or width is None or height is None:
        return None
    length = _clamp_dim("length", float(length), label, archetype)
    width = _clamp_dim("width", float(width), label, archetype)
    height = _clamp_dim("height", float(height), label, archetype)
    if width > length:
        length, width = width, length
    return {"length": length, "width": width, "height": height}


def _descriptor_json(descriptor: dict, max_bytes: int) -> Optional[str]:
    text = json.dumps(descriptor, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    if int(max_bytes) > 0 and len(text.encode("utf-8")) > int(max_bytes):
        return None
    return text


def _compact_observation_contract(observation_contract: Optional[dict]) -> Optional[dict]:
    if not isinstance(observation_contract, dict):
        return None
    compact = {
        "schema": observation_contract.get("schema"),
        "observation_id": observation_contract.get("observation_id"),
        "status": observation_contract.get("status"),
        "failures": observation_contract.get("failures"),
        "label": observation_contract.get("label"),
        "confidence": observation_contract.get("confidence"),
        "track_id": observation_contract.get("track_id"),
        "frame_id": observation_contract.get("frame_id"),
        "timestamp": observation_contract.get("timestamp"),
        "image_size_px": observation_contract.get("image_size_px"),
        "claim_boundary": observation_contract.get("claim_boundary"),
    }
    detector = observation_contract.get("detector_evidence") or {}
    compact["detector_evidence"] = {
        "bbox_xyxy": detector.get("bbox_xyxy"),
        "has_mask": detector.get("has_mask"),
        "mask_point_count": detector.get("mask_point_count"),
        "mask_source": detector.get("mask_source"),
        "mask_method": detector.get("mask_method"),
        "mask_status": detector.get("mask_status"),
        "mask_quality_score": detector.get("mask_quality_score"),
        "mask_area_px2": detector.get("mask_area_px2"),
        "mask_polygon_px": "omitted_duplicate_descriptor_mask_polygon"
        if detector.get("mask_polygon_px")
        else None,
    }
    metric = observation_contract.get("metric") or {}
    footprint = metric.get("footprint_m") or {}
    compact["metric"] = {
        "world_m": metric.get("world_m"),
        "metric_dims_m": metric.get("metric_dims_m"),
        "metric_evidence_source": metric.get("metric_evidence_source"),
        "yaw_deg": metric.get("yaw_deg"),
        "yaw_ambiguous": metric.get("yaw_ambiguous"),
        "height_source": metric.get("height_source"),
        "metric_ground_truth": metric.get("metric_ground_truth"),
        "footprint_m": {
            key: value
            for key, value in footprint.items()
            if key != "points_ned_m"
        }
        if isinstance(footprint, dict)
        else footprint,
    }
    compact["uncertainty"] = observation_contract.get("uncertainty")
    return compact


def build_sppa_descriptor_payload(
    *,
    label: str,
    confidence: float,
    bbox: Optional[dict] = None,
    mask: Optional[list] = None,
    image_width: Optional[int] = None,
    image_height: Optional[int] = None,
    world_m: Optional[dict] = None,
    metric_dims_m: Optional[dict] = None,
    metric_dims_source: str = "uav_pose_bbox_ground_footprint",
    footprint_m: Optional[dict] = None,
    yaw_deg: Optional[float] = None,
    track_id: Optional[str] = None,
    frame_id: Optional[int] = None,
    timestamp: Optional[str] = None,
    observation_contract: Optional[dict] = None,
    observation_uncertainty: Optional[dict] = None,
    max_descriptor_bytes: int = 30000,
) -> dict:
    """Build a compact SPPA descriptor payload for live vision detections.

    The descriptor is optional. If the offline generator cannot be imported or
    the descriptor exceeds the configured byte budget, this returns structured
    metadata without `sppa_descriptor_json` so the legacy pipeline can continue.
    """
    module = _load_generator()
    if module is None:
        return {"sppa_descriptor_error": "generator_not_available"}

    label_text = str(label or "unknown").strip() or "unknown"
    mesh = module.Mesh()
    builder, archetype, _status = module.resolve_builder(label_text)
    default_dims = module.archetype_default_dims(label_text, archetype)
    dims = _normalize_dims(metric_dims_m, default_dims.get("height"), label_text, archetype)
    observation_fusion = None
    if dims and isinstance(observation_uncertainty, dict) and hasattr(module, "fuse_observed_dims_with_prior"):
        observation_fusion = module.fuse_observed_dims_with_prior(
            label_text,
            archetype,
            dims,
            uncertainty=observation_uncertainty,
            confidence=confidence,
        )
        if observation_fusion.get("applied") and isinstance(observation_fusion.get("dims_m"), dict):
            dims = observation_fusion["dims_m"]
            metric_dims_source = str(observation_fusion.get("source") or metric_dims_source)
    meta = module.build_label_observed(
        mesh,
        label_text,
        dims_m=dims,
        bbox=bbox,
        mask=mask,
        height_m=dims.get("height") if dims else None,
    )
    if dims:
        meta["metric_dims_source"] = str(metric_dims_source or "uav_pose_bbox_ground_footprint")
        meta["effective_dims_m"] = dims
        meta["shape_evidence"] = {
            "source": str(metric_dims_source or "uav_pose_bbox_ground_footprint"),
            "footprint_m": footprint_m,
            "policy": "uav_pose_camera_projection_metric_footprint_with_reviewed_height_prior_if_needed",
        }

    world_pose = None
    if isinstance(world_m, dict):
        # The SPPA descriptor stores pose as metadata; Unreal root placement
        # still uses the explicit `world_m` obstacle field.
        north = _finite_float(world_m.get("north"))
        east = _finite_float(world_m.get("east"))
        up = _finite_float(world_m.get("up", world_m.get("z", 0.0)))
        if north is not None and east is not None:
            world_pose = {
                "x": east,
                "y": north,
                "z": 0.0 if up is None else up,
                "coordinate_frame": "local_enu_m_metadata",
            }

    compact_observation_contract = _compact_observation_contract(observation_contract)
    descriptor = module.build_sppa_descriptor(
        mesh,
        meta,
        confidence=confidence,
        bbox=bbox,
        mask=mask,
        world_pose=world_pose,
        image_width=image_width,
        image_height=image_height,
        dims_m=dims,
        yaw_deg=yaw_deg,
        track_id=track_id,
        timestamp=timestamp,
        frame_id=frame_id,
        observation_contract=compact_observation_contract,
        observation_uncertainty=observation_uncertainty,
    )
    text = _descriptor_json(descriptor, int(max_descriptor_bytes))
    payload = {
        "sppa_descriptor_id": descriptor.get("descriptor_id"),
        "sppa_metric_dims_m": descriptor.get("scale", {}).get("effective_dims_m") or dims,
        "sppa_scale_source": descriptor.get("scale", {}).get("scale_source"),
        "sppa_shape_policy": descriptor.get("scale", {}).get("shape_policy"),
        "sppa_observation_id": (observation_contract or {}).get("observation_id") if isinstance(observation_contract, dict) else None,
        "sppa_uncertainty": descriptor.get("uncertainty"),
        "sppa_observation_fusion": observation_fusion,
    }
    if text is not None:
        payload["sppa_descriptor_json"] = text
    else:
        payload["sppa_descriptor_error"] = "descriptor_byte_budget_exceeded"
    return payload
