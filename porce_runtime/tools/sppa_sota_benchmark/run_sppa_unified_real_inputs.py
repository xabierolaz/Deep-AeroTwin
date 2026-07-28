from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from bench_common import ROOT, emit, gpu_snapshot, mesh_stats, write_csv
from sppa_semantic_normalizer import refine_normalized_with_observation

sys.path.insert(0, str(ROOT / "pipeline"))
from geo_projector import GeoProjector  # noqa: E402


DEFAULT_REPLAY_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "benchmarks"
    / "results"
    / "real_image_assumed_flight_replay.json"
)
DEFAULT_ANNOTATIONS_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_detection_reference"
    / "20260703_real_input_annotations"
    / "real_input_2d_annotations.json"
)
DEFAULT_IMAGE_CUES_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "benchmarks"
    / "results"
    / "sppa_agnostic_image_space_parts_probe.json"
)
DEFAULT_OUT_DIR = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_sota_benchmark"
    / "runs"
    / "20260704_real_all_sppa_unified"
)

VERTICAL_STRUCTURE_LABELS = {
    "tower",
    "power_tower",
    "vertical_structure",
    "electric pylon",
    "pylon",
    "utility pole",
    "antenna tower",
}

VEHICLE_FOOTPRINT_LABELS = {
    "tractor",
    "farm_vehicle",
    "agricultural vehicle",
    "tractor_trailer",
    "vehicle",
    "generic_vehicle",
    "heavy_vehicle",
    "truck",
    "car",
    "bus",
    "van",
    "pickup",
    "pickup truck",
}


def load_generator(generator_path: Path):
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", generator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {generator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def annotation_index(path: Path) -> dict[str, dict[str, Any]]:
    data = read_json(path)
    return {str(item.get("label")): item for item in data.get("items", [])}


def image_cues_index(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    data = read_json(path)
    return {str(item.get("case_id")): item for item in data.get("rows", []) if item.get("case_id")}


def bbox_dict(raw: Any) -> dict[str, float] | None:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, list | tuple) or len(raw) != 4:
        return None
    x1, y1, x2, y2 = [float(value) for value in raw]
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def world_pose(row: dict[str, Any]) -> dict[str, Any] | None:
    world = row.get("world_m")
    if not isinstance(world, dict):
        return None
    east = world.get("east")
    north = world.get("north")
    if east is None or north is None:
        return None
    return {
        "east_m": float(east),
        "north_m": float(north),
        "up_m": float(world.get("up") or 0.0),
        "coordinate_frame": "declared_assumed_flight_replay_local_ned",
    }


def semantic_label_for(row: dict[str, Any], ann: dict[str, Any] | None) -> tuple[str, str]:
    reviewed = str((ann or {}).get("reviewed_semantic_tag") or "").strip()
    if reviewed:
        return reviewed, "reviewed_semantic_tag"
    runtime = str(row.get("runtime_archetype_id") or row.get("sppa_tag") or "").strip()
    if runtime:
        return runtime, "detector_normalizer_tag"
    return str(row.get("case_id") or "unknown"), "case_id"


def detector_normalized_for(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "detector_label": row.get("detector_label"),
        "confidence": float(row.get("detector_confidence") or 0.0),
        "sppa_tag": row.get("sppa_tag"),
        "runtime_archetype_id": row.get("detector_runtime_archetype_id") or row.get("sppa_tag"),
        "runtime_archetypes": [],
        "normalization_rule": row.get("normalization_rule"),
        "claim_status": row.get("claim_status"),
        "conservative": bool(row.get("conservative", False)),
        "score": 0.0,
    }


def detector_refined_semantic_label_for(row: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    base = detector_normalized_for(row)
    refined = refine_normalized_with_observation(
        base,
        row.get("sppa_metric_dims_m"),
        row.get("sppa_uncertainty") if isinstance(row.get("sppa_uncertainty"), dict) else None,
    )
    refined = refined or base
    label = str(refined.get("runtime_archetype_id") or refined.get("sppa_tag") or row.get("case_id") or "unknown")
    return label, "detector_observation_refined_tag", refined


def image_size(ann: dict[str, Any] | None) -> tuple[int | None, int | None]:
    size = (ann or {}).get("image_size")
    if not isinstance(size, dict):
        return None, None
    width = size.get("width")
    height = size.get("height")
    return (int(width) if width else None, int(height) if height else None)


def root_path(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else ROOT / path


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (float(ordered[mid - 1]) + float(ordered[mid])) * 0.5


def _bbox_xyxy(row: dict[str, Any], ann: dict[str, Any] | None) -> list[float] | None:
    raw = row.get("bbox_xyxy") or (ann or {}).get("manual_bbox_xyxy") or (ann or {}).get("crop_bbox_xyxy")
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(value) for value in raw]
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]


def _polygon_points(row: dict[str, Any]) -> list[tuple[float, float]]:
    mask = row.get("native_detector_mask") if isinstance(row.get("native_detector_mask"), dict) else {}
    polygon = mask.get("polygon") if isinstance(mask.get("polygon"), list) else []
    points: list[tuple[float, float]] = []
    for point in polygon:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            try:
                points.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError):
                pass
    return points


def _observable_color_family(label: str, row: dict[str, Any]) -> bool:
    keys = {
        str(label or "").strip().lower().replace("_", " "),
        str(row.get("case_id") or "").strip().lower().replace("_", " "),
        str(row.get("runtime_archetype_id") or "").strip().lower().replace("_", " "),
        str(row.get("sppa_tag") or "").strip().lower().replace("_", " "),
        str(row.get("detector_label") or "").strip().lower().replace("_", " "),
    }
    joined = " ".join(sorted(keys))
    vehicle_terms = (
        "vehicle",
        "tractor",
        "truck",
        "car",
        "bus",
        "van",
        "pickup",
        "biker",
        "bicycle",
        "motorcycle",
        "rider",
    )
    return any(term in joined for term in vehicle_terms)


def observed_color_for(row: dict[str, Any], ann: dict[str, Any] | None, semantic_label: str) -> dict[str, Any] | None:
    if not _observable_color_family(semantic_label, row):
        return None
    image_path = root_path(row.get("image") or (ann or {}).get("image"))
    if image_path is None or not image_path.exists():
        return None
    bbox = _bbox_xyxy(row, ann)
    if bbox is None:
        return None
    try:
        image = Image.open(image_path).convert("RGB")
    except OSError:
        return None

    width, height = image.size
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    polygon = _polygon_points(row)
    source = "detector_mask_chromatic_median"
    if len(polygon) >= 3:
        draw.polygon(polygon, fill=255)
    else:
        x1, y1, x2, y2 = bbox
        draw.rectangle((x1, y1, x2, y2), fill=255)
        source = "detector_bbox_chromatic_median"

    x1, y1, x2, y2 = bbox
    left = max(0, int(round(x1)))
    top = max(0, int(round(y1)))
    right = min(width, int(round(x2)) + 1)
    bottom = min(height, int(round(y2)) + 1)
    if right <= left or bottom <= top:
        return None

    mask_px = mask.load()
    image_px = image.load()
    reds: list[int] = []
    greens: list[int] = []
    blues: list[int] = []
    tested = 0
    for y in range(top, bottom):
        for x in range(left, right):
            if mask_px[x, y] <= 0:
                continue
            tested += 1
            r, g, b = image_px[x, y]
            maxc = max(r, g, b) / 255.0
            minc = min(r, g, b) / 255.0
            saturation = maxc - minc
            luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
            if saturation < 0.10 or luminance < 0.08 or luminance > 0.88:
                continue
            reds.append(r)
            greens.append(g)
            blues.append(b)

    if len(reds) < 24 or tested <= 0:
        return None
    rgb255 = [
        int(round(_median(reds))),
        int(round(_median(greens))),
        int(round(_median(blues))),
    ]
    chromatic_fraction = len(reds) / float(max(1, tested))
    if chromatic_fraction < 0.015:
        return None
    semantic_key = " ".join(
        str(value or "").strip().lower().replace("_", " ")
        for value in (
            semantic_label,
            row.get("case_id"),
            row.get("runtime_archetype_id"),
            row.get("sppa_tag"),
            row.get("detector_label"),
        )
    )
    if any(term in semantic_key for term in ("trailer", "articulated")) and chromatic_fraction < 0.20:
        return None
    return {
        "rgb": [round(channel / 255.0, 6) for channel in rgb255],
        "rgb255": rgb255,
        "confidence": round(min(0.85, max(0.25, chromatic_fraction * 2.0)), 4),
        "source": source,
        "sampled_pixel_count": len(reds),
        "candidate_pixel_count": tested,
        "chromatic_fraction": round(chromatic_fraction, 5),
        "claim_boundary": (
            "Observed material color is a robust chromatic median inside detector evidence. "
            "It is not texture reconstruction and is applied only to observable semantic roles."
        ),
    }


def visual_part_evidence_for(case_label: str, cues: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    row = cues.get(case_label)
    if not isinstance(row, dict):
        return None
    image_space_cues = row.get("image_space_cues")
    if not isinstance(image_space_cues, dict):
        return None
    return {
        "source": "real_image_agnostic_image_space_cues",
        "case_id": case_label,
        "crop_xyxy": row.get("crop_xyxy"),
        "image_space_cues": image_space_cues,
        "claim_boundary": row.get("claim_boundary"),
    }

def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def axial_delta_deg(a: float, b: float) -> float:
    diff = abs((float(a) - float(b)) % 180.0)
    return min(diff, 180.0 - diff)


def agreement_class(delta: float | None) -> str:
    if delta is None:
        return "missing"
    if delta <= 25.0:
        return "aligned"
    if delta <= 45.0:
        return "weakly_aligned"
    return "divergent_declared"


def visual_axis_points_from_evidence(visual_part_evidence: dict[str, Any] | None) -> tuple[str | None, list[tuple[float, float]]]:
    if not isinstance(visual_part_evidence, dict):
        return None, []
    cues = visual_part_evidence.get("image_space_cues") if isinstance(visual_part_evidence.get("image_space_cues"), dict) else {}
    pairs = cues.get("validated_round_part_pairs") if isinstance(cues.get("validated_round_part_pairs"), list) else []
    if pairs:
        strongest = sorted(
            (pair for pair in pairs if isinstance(pair, dict)),
            key=lambda pair: float(pair.get("score") or 0.0),
            reverse=True,
        )
        centers = strongest[0].get("centers_xy") if strongest else None
        if isinstance(centers, list) and len(centers) >= 2:
            return "round_pair_centers_projected_to_ground", [
                (float(centers[0][0]), float(centers[0][1])),
                (float(centers[1][0]), float(centers[1][1])),
            ]
    lines = cues.get("line_primitive_candidates") if isinstance(cues.get("line_primitive_candidates"), list) else []
    if lines:
        longest = sorted(
            (line for line in lines if isinstance(line, dict)),
            key=lambda line: float(line.get("length_px") or 0.0),
            reverse=True,
        )
        xyxy = longest[0].get("xyxy") if longest else None
        if isinstance(xyxy, list) and len(xyxy) >= 4:
            return "longest_line_projected_to_ground", [
                (float(xyxy[0]), float(xyxy[1])),
                (float(xyxy[2]), float(xyxy[3])),
            ]
    return None, []


def visual_metric_yaw_consistency_for(
    row: dict[str, Any],
    ann: dict[str, Any] | None,
    visual_part_evidence: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(visual_part_evidence, dict):
        return None
    crop = visual_part_evidence.get("crop_xyxy")
    size = (ann or {}).get("image_size") if isinstance((ann or {}).get("image_size"), dict) else {}
    width = as_float(size.get("width"))
    height = as_float(size.get("height"))
    flight = row.get("flight_replay") if isinstance(row.get("flight_replay"), dict) else {}
    metric_yaw = as_float(row.get("yaw_deg"))
    axis_source, local_points = visual_axis_points_from_evidence(visual_part_evidence)
    if (
        not axis_source
        or len(local_points) < 2
        or not isinstance(crop, list)
        or len(crop) < 4
        or width is None
        or height is None
        or metric_yaw is None
    ):
        return None
    params = {
        "image_height": int(height),
        "image_width": int(width),
        "drone_yaw_deg": flight.get("drone_yaw_deg"),
        "drone_pitch_deg": flight.get("drone_pitch_deg"),
        "drone_roll_deg": flight.get("drone_roll_deg"),
        "alt_agl_m": flight.get("alt_agl_m"),
        "camera_vfov_deg": flight.get("camera_vfov_deg"),
        "mount_roll_deg": flight.get("mount_roll_deg"),
        "mount_pitch_deg": flight.get("mount_pitch_deg"),
        "mount_yaw_deg": flight.get("mount_yaw_deg"),
        "max_range_m": flight.get("max_range_m"),
    }
    if any(value is None for value in params.values()):
        return None
    projected = []
    for x_local, y_local in local_points[:2]:
        x_full = float(crop[0]) + float(x_local)
        y_full = float(crop[1]) + float(y_local)
        point = GeoProjector.pixel_to_ground_offset_m(y_full, x_full, **params)
        if point is None:
            return None
        projected.append(point)
    dn = float(projected[1]["north_m"]) - float(projected[0]["north_m"])
    de = float(projected[1]["east_m"]) - float(projected[0]["east_m"])
    if math.hypot(dn, de) <= 1e-6:
        return None
    visual_axis_yaw = math.degrees(math.atan2(de, dn)) % 180.0
    delta = axial_delta_deg(metric_yaw, visual_axis_yaw)
    return {
        "applied": True,
        "source": "real_image_visual_axis_projected_through_declared_uav_replay",
        "visual_axis_source": axis_source,
        "projected_visual_axis_yaw_deg": round(float(visual_axis_yaw), 3),
        "projected_metric_yaw_deg": round(float(metric_yaw), 3),
        "projected_visual_metric_delta_deg": round(float(delta), 3),
        "agreement": agreement_class(delta),
        "telemetry_measured": row.get("telemetry_is_measured"),
        "metric_ground_truth": row.get("metric_ground_truth"),
    }

def is_vertical_structure(label: str) -> bool:
    key = str(label or "").strip().lower().replace("_", " ")
    return key in VERTICAL_STRUCTURE_LABELS or "tower" in key or "pylon" in key

def is_vehicle_footprint(label: str) -> bool:
    key = str(label or "").strip().lower().replace("_", " ")
    return key in VEHICLE_FOOTPRINT_LABELS or "vehicle" in key or "tractor" in key or "truck" in key

def vertical_height_dims(module: Any, semantic_label: str, dims: dict[str, Any]) -> dict[str, float]:
    height = as_float(dims.get("height")) or as_float(dims.get("height_m")) or 1.0
    defaults = getattr(module, "DEFAULT_ARCHETYPE_DIMS_M", {})
    prior = defaults.get("vertical_structure", {"length": 1.2, "width": 1.2, "height": 6.0})
    prior_h = max(0.1, float(prior.get("height") or 6.0))
    scale = max(1.0, height / prior_h)
    prior_length = float(prior.get("length") or 1.2) * scale
    prior_width = float(prior.get("width") or 1.2) * scale
    observed_length = as_float(dims.get("length")) or as_float(dims.get("length_m"))
    observed_width = as_float(dims.get("width")) or as_float(dims.get("width_m"))
    length = min(observed_length, prior_length) if observed_length else prior_length
    width = min(observed_width, prior_width) if observed_width else prior_width
    return {"length": max(0.2, length), "width": max(0.2, width), "height": height}


def observation_decision(module: Any, row: dict[str, Any], semantic_label: str) -> dict[str, Any]:
    dims = row.get("sppa_metric_dims_m")
    if not isinstance(dims, dict):
        return {
            "applied": False,
            "gate": "missing_metric_dims",
            "dims_m": None,
            "source": "missing_observed_dims",
            "policy": "no_observation_dims_available",
            "image_geometry_reliable": False,
        }
    uncertainty = row.get("sppa_uncertainty") if isinstance(row.get("sppa_uncertainty"), dict) else {}
    fusion = module.fuse_observed_dims_with_prior(
        semantic_label,
        row.get("runtime_archetype_id") or semantic_label,
        dims,
        uncertainty=uncertainty,
        confidence=row.get("detector_confidence"),
    )
    if not fusion.get("applied") or not isinstance(fusion.get("dims_m"), dict):
        return {
            **fusion,
            "applied": False,
            "gate": str(fusion.get("source") or "observation_not_applied"),
            "dims_m": None,
            "image_geometry_reliable": False,
        }
    source = str(fusion.get("source") or "accepted_observation")
    gate = source
    if source == "constraint_fused_vertical_height":
        gate = "vertical_height_only_low_confidence_shape" if bool(uncertainty.get("shape_low_confidence")) else "vertical_constraint_fused"
    elif source == "constraint_fused_vehicle_observation":
        reasons = fusion.get("fusion_reasons") if isinstance(fusion.get("fusion_reasons"), list) else []
        if "aspect_implausible" in reasons:
            gate = "vehicle_soft_aspect_fusion"
        elif "low_confidence" in reasons:
            gate = "vehicle_soft_low_confidence_fusion"
        else:
            gate = "vehicle_soft_constraint_fusion"
    elif source == "accepted_vehicle_observation":
        gate = "accepted"

    quality_flags = uncertainty.get("quality_flags") if isinstance(uncertainty.get("quality_flags"), dict) else {}
    mask_quality = quality_flags.get("mask_quality_score")
    image_geometry_reliable = bool(fusion.get("image_geometry_reliable"))
    if mask_quality is not None and float(mask_quality) < 0.50 and gate == "accepted":
        gate = "accepted_dims_low_mask_quality"
        image_geometry_reliable = False
    if bool(uncertainty.get("yaw_ambiguous")):
        image_geometry_reliable = False
    return {
        **fusion,
        "applied": True,
        "gate": gate,
        "dims_m": fusion["dims_m"],
        "image_geometry_reliable": image_geometry_reliable,
    }


def emit_mesh(
    *,
    module: Any,
    model_name: str,
    case_label: str,
    semantic_label: str,
    semantic_text_source: str,
    prompt: str,
    out_root: Path,
    confidence: float,
    dims_m: dict[str, float] | None = None,
    bbox: dict[str, float] | None = None,
    mask: dict[str, Any] | None = None,
    world: dict[str, Any] | None = None,
    yaw_deg: float | None = None,
    image_width: int | None = None,
    image_height: int | None = None,
    observation_uncertainty: dict[str, Any] | None = None,
    metric_dims_source_override: str | None = None,
    observation_fusion: dict[str, Any] | None = None,
    visual_part_evidence: dict[str, Any] | None = None,
    visual_metric_yaw_consistency: dict[str, Any] | None = None,
    observed_color: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = out_root / "outputs" / model_name / case_label
    out.mkdir(parents=True, exist_ok=True)
    mesh = module.Mesh()
    start = time.perf_counter()
    resolution = module.build_label_observed(
        mesh,
        semantic_label,
        dims_m=dims_m,
        bbox=bbox,
        mask=mask,
        height_m=None if not dims_m else dims_m.get("height"),
        visual_part_evidence=visual_part_evidence,
    )
    if metric_dims_source_override and dims_m:
        resolution["metric_dims_source"] = metric_dims_source_override
        resolution["shape_evidence"] = {
            "source": metric_dims_source_override,
            "policy": (observation_fusion or {}).get("policy"),
            "fusion": observation_fusion,
        }
    build_sec = time.perf_counter() - start

    mtl_path = out / f"{case_label}.mtl"
    obj_path = out / f"{case_label}.obj"
    manifest_path = out / f"{case_label}.materials.json"
    descriptor_path = out / f"{case_label}.descriptor.json"
    start = time.perf_counter()
    material_manifest = module.write_material_manifest(str(manifest_path), mesh, resolution, confidence, observed_color)
    module.write_mtl(str(mtl_path), material_manifest)
    module.write_obj(mesh, str(obj_path), mtl_path.name)
    export_sec = time.perf_counter() - start

    descriptor = module.write_sppa_descriptor(
        str(descriptor_path),
        mesh,
        resolution,
        confidence,
        bbox=bbox,
        mask=mask,
        world_pose=world,
        image_width=image_width,
        image_height=image_height,
        dims_m=resolution.get("effective_dims_m") or dims_m,
        yaw_deg=yaw_deg,
        track_id=f"{case_label}:{model_name}",
        timestamp="2026-07-04T00:00:00Z",
        source_log="real_input_probe_sppa_unified",
        source_event_index=0,
        observation_uncertainty=observation_uncertainty,
        visual_metric_yaw_consistency=visual_metric_yaw_consistency,
        observed_color=observed_color,
        create_cpu_us=build_sec * 1_000_000.0,
        export_cpu_us_if_any=export_sec * 1_000_000.0,
    )
    descriptor_visual = descriptor.get("evidence", {}).get("visual_part_evidence") or {}
    descriptor_visual_shape = descriptor.get("evidence", {}).get("visual_shape_conditioning") or {}
    descriptor_visual_metric = descriptor.get("evidence", {}).get("visual_metric_yaw_consistency") or {}
    descriptor_material = descriptor.get("material", {}) if isinstance(descriptor.get("material"), dict) else {}
    descriptor_observed_color = descriptor_material.get("observed_color") if isinstance(descriptor_material.get("observed_color"), dict) else {}
    visual_geometry = descriptor_visual.get("geometry_profile") or {}
    visual_features = []
    if visual_geometry.get("round_pair"):
        visual_features.append("round_pair")
    if visual_geometry.get("line_structure"):
        visual_features.append("line_structure")
    round_pair = visual_geometry.get("round_pair") or {}
    line_structure = visual_geometry.get("line_structure") or {}
    payload = {
        "event": "SPPA_OBJECT",
        "model": model_name,
        "label": case_label,
        "semantic_label": semantic_label,
        "semantic_text_source": semantic_text_source,
        "prompt": prompt,
        "archetype": resolution.get("archetype"),
        "resolution_status": resolution.get("resolution_status"),
        "shape_policy": resolution.get("shape_policy"),
        "metric_dims_source": resolution.get("metric_dims_source"),
        "status": "ok",
        "build_sec": build_sec,
        "export_sec": export_sec,
        "wall_sec": build_sec + export_sec,
        "gpu_after": gpu_snapshot(),
        "material_manifest_path": str(manifest_path).replace("\\", "/"),
        "material_descriptor_schema": material_manifest.get("descriptor_schema"),
        "material_policy": material_manifest.get("material_policy"),
        "material_count": len(material_manifest.get("materials", [])),
        "fallback_material_count": sum(
            1
            for material in material_manifest.get("materials", [])
            if material.get("evidence_source") == "fallback_unknown"
        ),
        "descriptor_path": str(descriptor_path).replace("\\", "/"),
        "descriptor_schema": descriptor.get("descriptor_schema"),
        "descriptor_bytes": descriptor.get("cost", {}).get("descriptor_bytes"),
        "descriptor_yaw_source": descriptor.get("pose", {}).get("yaw_source"),
        "descriptor_yaw_deg": descriptor.get("pose", {}).get("yaw_deg"),
        "descriptor_yaw_coordinate_frame": descriptor.get("pose", {}).get("yaw_coordinate_frame"),
        "descriptor_yaw_policy": descriptor.get("pose", {}).get("yaw_policy"),
        "descriptor_scale_source": descriptor.get("scale", {}).get("scale_source"),
        "effective_dims_m": resolution.get("effective_dims_m") or dims_m,
        "observation_fusion_source": (observation_fusion or {}).get("source"),
        "observation_fusion_policy": (observation_fusion or {}).get("policy"),
        "observation_fusion_version": (observation_fusion or {}).get("version"),
        "visual_part_evidence_applied": bool(descriptor_visual.get("applied")),
        "visual_part_evidence_scope": descriptor_visual.get("scope"),
        "visual_part_evidence_roles": descriptor_visual.get("supported_roles"),
        "visual_part_evidence_policy": descriptor_visual.get("role_support_policy"),
        "visual_part_evidence_version": descriptor_visual.get("version"),
        "visual_part_geometry_profile_applied": bool(visual_geometry.get("applied")),
        "visual_part_geometry_profile_version": visual_geometry.get("version"),
        "visual_part_geometry_features": visual_features,
        "visual_shape_conditioning_applied": bool(descriptor_visual_shape.get("applied")),
        "visual_shape_conditioning_version": descriptor_visual_shape.get("version"),
        "visual_shape_conditioning_policy": descriptor_visual_shape.get("policy"),
        "visual_shape_conditioning_additions": descriptor_visual_shape.get("additions"),
        "visual_shape_conditioning_added_parts": descriptor_visual_shape.get("added_parts"),
        "visual_shape_conditioning_added_triangles": descriptor_visual_shape.get("added_triangles"),
        "visual_round_pair_axis_angle_deg": round_pair.get("axis_angle_deg"),
        "visual_round_pair_radius_ratio": round_pair.get("radius_ratio"),
        "visual_round_pair_separation_radius_ratio": round_pair.get("separation_radius_ratio"),
        "visual_line_dominant_angle_deg": line_structure.get("dominant_angle_deg"),
        "visual_line_max_length_px": line_structure.get("max_line_length_px"),
        "visual_metric_yaw_consistency_applied": bool(descriptor_visual_metric.get("applied")),
        "visual_metric_yaw_consistency_version": descriptor_visual_metric.get("version"),
        "visual_metric_yaw_axis_source": descriptor_visual_metric.get("visual_axis_source"),
        "visual_metric_yaw_projected_axis_deg": descriptor_visual_metric.get("projected_visual_axis_yaw_deg"),
        "visual_metric_yaw_footprint_deg": descriptor_visual_metric.get("footprint_yaw_deg"),
        "visual_metric_yaw_delta_deg": descriptor_visual_metric.get("axial_delta_deg"),
        "visual_metric_yaw_agreement": descriptor_visual_metric.get("agreement"),
        "observed_color_applied": bool(descriptor_material.get("observed_color_applied")),
        "observed_color_rgb": descriptor_observed_color.get("rgb"),
        "observed_color_source": descriptor_observed_color.get("source"),
        "observed_color_confidence": descriptor_observed_color.get("confidence"),
    }
    payload.update(mesh_stats(obj_path))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate unified SPPA real-input meshes.")
    parser.add_argument("--replay-json", type=Path, default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--annotations-json", type=Path, default=DEFAULT_ANNOTATIONS_JSON)
    parser.add_argument("--image-cues-json", type=Path, default=DEFAULT_IMAGE_CUES_JSON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--semantic-source",
        choices=["reviewed", "detector_refined"],
        default="reviewed",
        help="Use reviewed text tags or detector-only observation-refined tags.",
    )
    parser.add_argument(
        "--generator",
        type=Path,
        default=ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py",
    )
    args = parser.parse_args()

    replay_json = args.replay_json if args.replay_json.is_absolute() else ROOT / args.replay_json
    annotations_json = args.annotations_json if args.annotations_json.is_absolute() else ROOT / args.annotations_json
    image_cues_json = args.image_cues_json if args.image_cues_json.is_absolute() else ROOT / args.image_cues_json
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    generator = args.generator if args.generator.is_absolute() else ROOT / args.generator
    output_dir.mkdir(parents=True, exist_ok=True)

    replay = read_json(replay_json)
    annotations = annotation_index(annotations_json)
    image_cues = image_cues_index(image_cues_json)
    module = load_generator(generator)
    rows: list[dict[str, Any]] = []
    emit("SPPA_RUN", {"models": ["sppa"], "gpu_before": gpu_snapshot()})
    for row in replay.get("rows", []):
        case_label = str(row.get("case_id") or "unknown")
        ann = annotations.get(case_label)
        detector_refined: dict[str, Any] | None = None
        if args.semantic_source == "detector_refined":
            semantic_label, semantic_source, detector_refined = detector_refined_semantic_label_for(row)
        else:
            semantic_label, semantic_source = semantic_label_for(row, ann)
        width, height = image_size(ann)
        confidence = float(row.get("detector_confidence") or 1.0)
        decision = observation_decision(module, row, semantic_label)
        use_observation = bool(decision.get("applied"))
        gate_reason = str(decision.get("gate") or "observation_not_applied")
        dims = decision.get("dims_m") if use_observation and isinstance(decision.get("dims_m"), dict) else None
        prompt = (
            f"{semantic_label} semantic tag plus constraint-fused YOLOE/assumed-flight observation"
            if use_observation
            else f"{semantic_label} semantic tag with low-confidence observation audited but not applied"
        )
        semantic_text_source = f"{semantic_source}+constraint_fused_real_yoloe_observation" if use_observation else semantic_source
        apply_image_geometry = use_observation and bool(decision.get("image_geometry_reliable"))
        uncertainty = row.get("sppa_uncertainty") if isinstance(row.get("sppa_uncertainty"), dict) else None
        visual_part_evidence = visual_part_evidence_for(case_label, image_cues)
        visual_metric_yaw_consistency = visual_metric_yaw_consistency_for(row, ann, visual_part_evidence)
        observed_color = observed_color_for(row, ann, semantic_label) if use_observation else None
        if uncertainty is not None and use_observation:
            uncertainty = dict(uncertainty)
            uncertainty["observation_fusion"] = {
                key: value
                for key, value in decision.items()
                if key
                in {
                    "version",
                    "source",
                    "policy",
                    "quality",
                    "shape_low_confidence",
                    "raw_aspect",
                    "target_aspect_range",
                    "fusion_weight",
                    "fusion_reasons",
                    "image_geometry_reliable",
                }
            }
        sppa_row = emit_mesh(
            module=module,
            model_name="sppa",
            case_label=case_label,
            semantic_label=semantic_label,
            semantic_text_source=semantic_text_source,
            prompt=prompt,
            out_root=output_dir,
            confidence=confidence,
            dims_m=dims,
            bbox=bbox_dict(row.get("bbox_xyxy")) if use_observation else None,
            mask=row.get("native_detector_mask") if apply_image_geometry else None,
            world=world_pose(row) if use_observation else None,
            yaw_deg=row.get("yaw_deg") if apply_image_geometry else None,
            image_width=width,
            image_height=height,
            observation_uncertainty=uncertainty,
            metric_dims_source_override=str(decision.get("source") or "") if use_observation else None,
            observation_fusion=decision if use_observation else None,
            visual_part_evidence=visual_part_evidence,
            visual_metric_yaw_consistency=visual_metric_yaw_consistency,
            observed_color=observed_color,
        )
        sppa_row["observation_gate"] = gate_reason
        sppa_row["observation_applied"] = use_observation
        sppa_row["observation_image_geometry_applied"] = apply_image_geometry
        sppa_row["raw_metric_dims_m"] = row.get("sppa_metric_dims_m")
        sppa_row["fused_metric_dims_m"] = dims
        sppa_row["semantic_selection_mode"] = args.semantic_source
        if detector_refined is not None:
            sppa_row["detector_refined_sppa_tag"] = detector_refined.get("sppa_tag")
            sppa_row["detector_refined_runtime_archetype"] = detector_refined.get("runtime_archetype_id")
            sppa_row["detector_refined_rule"] = detector_refined.get("normalization_rule")
            sppa_row["detector_refinement_applied"] = (detector_refined.get("observation_refinement") or {}).get("applied")
        rows.append(sppa_row)
        emit("SPPA_OBJECT", sppa_row)

    write_csv(output_dir / "objects.csv", rows)
    with (output_dir / "SPPA_README.md").open("w", encoding="utf-8") as f:
        f.write("# SPPA Unified Real-Input Run\n\n")
        f.write("One final SPPA proxy is generated per real input. Detector masks and bboxes are consumed through a semantic observation-fusion gate: reliable cues can set metric scale/pose, noisy footprints are softly constrained by the selected archetype, and unsafe image geometry is kept out of pose.\n\n")
        f.write("| Model | Input evidence | Runtime meaning |\n")
        f.write("|---|---|---|\n")
        f.write(
            "| `sppa` | reviewed semantic text plus gated YOLOE mask/bbox and declared replay geometry when accepted | "
            "single selected proxy with constraint-fused scale and conservative pose rejection for unreliable shape evidence |\n"
        )


if __name__ == "__main__":
    main()
