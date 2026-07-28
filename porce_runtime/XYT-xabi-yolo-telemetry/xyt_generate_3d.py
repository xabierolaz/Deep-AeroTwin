import argparse
import hashlib
import json
import math
import os
import re
import time
from datetime import datetime, timezone


MATERIALS = {
    "brown": (0.45, 0.25, 0.10),
    "dark_brown": (0.20, 0.10, 0.04),
    "cream": (0.85, 0.75, 0.55),
    "black": (0.02, 0.02, 0.02),
    "white": (0.92, 0.92, 0.86),
    "green": (0.10, 0.55, 0.16),
    "dark_green": (0.03, 0.35, 0.09),
    "red": (0.70, 0.05, 0.04),
    "blue": (0.05, 0.18, 0.75),
    "gray": (0.45, 0.45, 0.45),
    "metal": (0.62, 0.62, 0.60),
    "glass": (0.35, 0.70, 0.95),
    "yellow": (0.95, 0.72, 0.06),
    "animal_body_prior": (0.92, 0.92, 0.86),
    "animal_marking_prior": (0.02, 0.02, 0.02),
    "animal_skin_prior": (0.85, 0.75, 0.55),
    "animal_limb_prior": (0.20, 0.10, 0.04),
    "vegetation_trunk_prior": (0.45, 0.25, 0.10),
    "vegetation_canopy_dark_prior": (0.03, 0.35, 0.09),
    "vegetation_canopy_light_prior": (0.10, 0.55, 0.16),
    "vehicle_body_prior": (0.70, 0.05, 0.04),
    "vehicle_cab_prior": (0.05, 0.18, 0.75),
    "vehicle_neutral_body_prior": (0.45, 0.45, 0.45),
    "vehicle_farm_body_prior": (0.10, 0.55, 0.16),
    "vehicle_attachment_prior": (0.95, 0.72, 0.06),
    "vehicle_window_prior": (0.35, 0.70, 0.95),
    "vehicle_tire_prior": (0.02, 0.02, 0.02),
    "vehicle_metal_prior": (0.62, 0.62, 0.60),
    "bike_frame_prior": (0.95, 0.72, 0.06),
    "rider_clothing_prior": (0.05, 0.18, 0.75),
    "rider_skin_prior": (0.85, 0.75, 0.55),
    "structure_metal_prior": (0.62, 0.62, 0.60),
    "built_structure_body_prior": (0.62, 0.58, 0.52),
    "built_structure_roof_prior": (0.32, 0.20, 0.16),
    "built_structure_window_prior": (0.35, 0.70, 0.95),
    "container_body_prior": (0.48, 0.50, 0.50),
    "container_detail_prior": (0.26, 0.28, 0.30),
    "safety_marker_prior": (0.95, 0.42, 0.04),
    "aircraft_body_prior": (0.36, 0.38, 0.40),
    "aircraft_rotor_prior": (0.05, 0.05, 0.05),
    "agricultural_bale_prior": (0.78, 0.62, 0.26),
    "agricultural_binding_prior": (0.28, 0.20, 0.12),
    "unknown_volume_fallback": (0.55, 0.55, 0.58),
    "unknown_footprint_fallback": (0.38, 0.38, 0.40),
    "uncertainty_marker_fallback": (0.95, 0.72, 0.06),
}

MATERIAL_DESCRIPTOR_VERSION = "SPPA-MAT-0.1"
SPPA_DESCRIPTOR_VERSION = "SPPA-DESC-0.2"
SPPA_UPDATE_PACKET_VERSION = "SPPA-UPD-0.2"
GENERATOR_VERSION = "XYT-SPPA-GEN-0.4"
ONTOLOGY_VERSION = "SPPA-ONTOLOGY-0.4"  # 0.4: wild quadrupeds giraffe/zebra/elephant -> quadruped family (open-set coverage probe 2026-07-25)
ARCHETYPE_VERSION = "SPPA-ARCHETYPE-0.3"
POLICY_VERSION = "SPPA-POLICY-0.2"
SCHEDULER_POLICY_ID = "SPPA-SCHED-0.2"
DEFAULT_SCHEDULER_THRESHOLDS = {
    "shape_ratio": 0.20,
    "confidence_bucket_step": 0.05,
    "velocity_min_delta_m": 0.05,
}
SCHEDULER_THRESHOLD_LIMITS = {
    "shape_ratio": (0.01, 1.00),
    "confidence_bucket_step": (0.01, 0.50),
    "velocity_min_delta_m": (0.00, 10.00),
}
DEFAULT_GEOMETRY_FITTING_WEIGHTS = {
    "bev_footprint_iou": 1.00,
    "mask_projection_iou": 0.50,
    "temporal_jitter": 0.20,
    "archetype_prior": 0.30,
}
DEFAULT_GEOMETRY_FITTING_LIMITS = {
    "max_candidates": 32,
    "triangle_budget_soft": 5000,
    "triangle_budget_hard": 20000,
}
# Mesh LOD for proxy fidelity vs triangle cost.
# "balanced" (default): readable structure, cheap wheels, low tessellation.
# "high": denser wheels/spheres for offline inspection.
# "ultra_light": maximum speed / minimum polygons for dense UAV scenes.
SPPA_MESH_LOD = os.environ.get("SPPA_MESH_LOD", "balanced").strip().lower()
_MESH_LOD_TABLE = {
    "ultra_light": {
        "cylinder_segments": 5,
        "sphere_rings": 3,
        "sphere_segments": 5,
        "torus_major": 6,
        "torus_minor": 3,
        "connector_segments": 5,
        "cheap_wheels": True,
        "skip_optional_connectors": True,
        "skip_visual_detail": True,
    },
    "balanced": {
        "cylinder_segments": 6,
        "sphere_rings": 3,
        "sphere_segments": 6,
        "torus_major": 8,
        "torus_minor": 3,
        "connector_segments": 5,
        "cheap_wheels": True,
        "skip_optional_connectors": False,
        "skip_visual_detail": False,
    },
    "high": {
        "cylinder_segments": 10,
        "sphere_rings": 5,
        "sphere_segments": 10,
        "torus_major": 12,
        "torus_minor": 5,
        "connector_segments": 8,
        "cheap_wheels": False,
        "skip_optional_connectors": False,
        "skip_visual_detail": False,
    },
}


def mesh_lod_params(level: str | None = None) -> dict:
    key = (level or SPPA_MESH_LOD or "balanced").lower()
    if key not in _MESH_LOD_TABLE:
        key = "balanced"
    return dict(_MESH_LOD_TABLE[key])


def select_use_case_mesh_lod(
    confidence=1.0,
    distance_m=None,
    budget_mode=None,
    explicit_lod=None,
    class_confidence=None,
):
    """Choose mesh LOD for the UAV digital-twin use case.

    SOTA for this system is not densest mesh: it is readable semantic structure
    under shared GPU/CPU budget with imperfect detector evidence.
    """
    if explicit_lod:
        key = str(explicit_lod).strip().lower()
        if key in _MESH_LOD_TABLE:
            return key
    mode = str(budget_mode or os.environ.get("SPPA_BUDGET_MODE") or "auto").strip().lower()
    if mode in _MESH_LOD_TABLE:
        return mode
    conf = clamp01(class_confidence if class_confidence is not None else confidence, 1.0)
    distance = as_float(distance_m)
    # Bias toward ultra-fast generation: only quality mode pays for high tessellation.
    if mode == "quality" and conf >= 0.85 and (distance is None or distance < 15.0):
        return "high"
    if distance is not None and distance >= 40.0:
        return "ultra_light"
    if conf < 0.45:
        return "ultra_light"
    if distance is not None and distance >= 18.0:
        return "ultra_light"
    if mode in {"speed", "dense", "flight"}:
        return "ultra_light"
    return "balanced"


def score_use_case_sota(
    *,
    triangles: int,
    build_ms: float,
    parts: int,
    evidence_channels: int,
    has_update_contract: bool = True,
    has_fallback: bool = True,
    neural_triangles: int | None = None,
    neural_build_ms: float | None = None,
    triangle_budget: int = 2500,
    build_budget_ms: float = 5.0,
) -> dict:
    """Operational score in [0,1]: fidelity-of-use under runtime constraints.

    This is intentionally NOT a photoreal reconstruction score.
    """
    tri = max(0, int(triangles))
    parts = max(0, int(parts))
    channels = max(0, int(evidence_channels))
    tri_eff = 1.0 if tri <= 0 else min(1.0, float(triangle_budget) / float(max(tri, 1)))
    # Prefer having structure (parts) without exploding triangles.
    structure = min(1.0, parts / 12.0) * (0.55 + 0.45 * tri_eff)
    speed = 1.0 if build_ms <= 0 else min(1.0, float(build_budget_ms) / float(max(build_ms, 1e-6)))
    evidence = min(1.0, channels / 4.0)
    contract = 1.0 if has_update_contract else 0.4
    fallback = 1.0 if has_fallback else 0.7
    vs_neural = 0.5
    if neural_triangles and neural_triangles > 0:
        vs_neural = min(1.0, float(neural_triangles) / float(max(tri, 1)))
        # Cap: being 10x lighter is enough for full credit.
        vs_neural = min(1.0, math.log10(1.0 + vs_neural) / math.log10(11.0))
    if neural_build_ms and neural_build_ms > 0 and build_ms > 0:
        speed_vs = min(1.0, float(neural_build_ms) / float(max(build_ms, 1e-6)))
        speed = 0.5 * speed + 0.5 * min(1.0, math.log10(1.0 + speed_vs) / math.log10(11.0))
    score = (
        0.30 * structure
        + 0.25 * speed
        + 0.20 * evidence
        + 0.15 * contract
        + 0.10 * fallback
    )
    # Small bonus when dramatically lighter than neural generators.
    score = min(1.0, score + 0.08 * vs_neural)
    return {
        "use_case_sota_score": round(float(score), 4),
        "components": {
            "structure_efficiency": round(structure, 4),
            "build_speed": round(speed, 4),
            "evidence_use": round(evidence, 4),
            "update_contract": round(contract, 4),
            "fallback_safety": round(fallback, 4),
            "lightness_vs_neural": round(vs_neural, 4),
        },
        "claim_boundary": "Operational UAV digital-twin proxy score, not photoreal image-to-3D SOTA.",
    }
DEFAULT_ARCHETYPE_DIMS_M = {
    "car": {"length": 4.30, "width": 1.80, "height": 1.55},
    "truck": {"length": 6.50, "width": 2.35, "height": 2.80},
    "bus": {"length": 9.80, "width": 2.55, "height": 3.20},
    "van": {"length": 5.20, "width": 2.05, "height": 2.25},
    "pickup": {"length": 5.40, "width": 2.05, "height": 1.90},
    "tractor": {"length": 3.80, "width": 2.00, "height": 2.40},
    "tractor_trailer": {"length": 7.60, "width": 2.15, "height": 2.70},
    "articulated_vehicle": {"length": 11.50, "width": 2.45, "height": 3.20},
    "vehicle_with_trailer": {"length": 11.50, "width": 2.45, "height": 3.20},
    "person": {"length": 0.55, "width": 0.55, "height": 1.75},
    "bicycle": {"length": 1.70, "width": 0.45, "height": 1.15},
    "motorcycle": {"length": 2.05, "width": 0.72, "height": 1.25},
    "biker": {"length": 1.70, "width": 0.60, "height": 1.85},
    "cow": {"length": 2.30, "width": 0.95, "height": 1.48},
    "cattle": {"length": 2.30, "width": 0.95, "height": 1.48},
    "vaca": {"length": 2.30, "width": 0.95, "height": 1.48},
    "bull": {"length": 2.45, "width": 1.05, "height": 1.60},
    "horse": {"length": 2.60, "width": 0.85, "height": 1.70},
    "dog": {"length": 1.05, "width": 0.35, "height": 0.70},
    "sheep": {"length": 1.35, "width": 0.60, "height": 0.90},
    "goat": {"length": 1.25, "width": 0.48, "height": 0.95},
    "deer": {"length": 1.75, "width": 0.55, "height": 1.25},
    "quadruped": {"length": 2.20, "width": 0.80, "height": 1.40},
    "tree": {"length": 1.80, "width": 1.80, "height": 4.20},
    "bush": {"length": 1.20, "width": 1.20, "height": 0.90},
    "tower": {"length": 1.20, "width": 1.20, "height": 6.00},
    "power_tower": {"length": 1.20, "width": 1.20, "height": 6.00},
    "pylon": {"length": 1.20, "width": 1.20, "height": 6.00},
    "pole": {"length": 0.60, "width": 0.60, "height": 6.00},
    "mast": {"length": 0.80, "width": 0.80, "height": 6.00},
    "vertical_structure": {"length": 1.20, "width": 1.20, "height": 6.00},
    "built_structure": {"length": 8.00, "width": 6.00, "height": 4.50},
    "building": {"length": 8.00, "width": 6.00, "height": 4.50},
    "house": {"length": 7.00, "width": 5.50, "height": 4.00},
    "shed": {"length": 4.00, "width": 3.00, "height": 2.80},
    "barn": {"length": 10.00, "width": 7.00, "height": 5.20},
    "warehouse": {"length": 18.00, "width": 12.00, "height": 7.00},
    "bridge": {"length": 18.00, "width": 5.00, "height": 2.20},
    "wall": {"length": 6.00, "width": 0.45, "height": 2.20},
    "fence": {"length": 6.00, "width": 0.30, "height": 1.80},
    "forklift": {"length": 3.20, "width": 1.35, "height": 2.20},
    "traffic_cone": {"length": 0.55, "width": 0.55, "height": 0.75},
    "water_tank": {"length": 3.00, "width": 1.40, "height": 1.60},
    "barrel": {"length": 0.70, "width": 0.70, "height": 1.00},
    "shipping_container": {"length": 12.20, "width": 2.45, "height": 2.60},
    "quadcopter": {"length": 0.90, "width": 0.90, "height": 0.22},
    "drone": {"length": 0.90, "width": 0.90, "height": 0.22},
    "hay_bale": {"length": 1.50, "width": 1.50, "height": 1.20},
    "unknown": {"length": 1.00, "width": 1.00, "height": 1.00},
}
GENERIC_DIM_LIMITS_M = {
    "length": (0.15, 50.0),
    "width": (0.15, 12.0),
    "height": (0.15, 20.0),
}
VERTICAL_STRUCTURE_LABELS = {
    "tower",
    "vertical_structure",
    "power_tower",
    "electric_pylon",
    "pylon",
    "pole",
    "mast",
}
OBSERVATION_FUSION_VERSION = "SPPA-OBS-FUSE-0.1"
VISUAL_PART_EVIDENCE_VERSION = "SPPA-VISUAL-PART-EVIDENCE-0.1"
VISUAL_PART_GEOMETRY_PROFILE_VERSION = "SPPA-VISUAL-GEOMETRY-PROFILE-0.1"
VISUAL_SHAPE_CONDITIONING_VERSION = "SPPA-VISUAL-SHAPE-CONDITIONING-0.1"
VISUAL_ORIENTATION_VERSION = "SPPA-VISUAL-ORIENTATION-0.1"
VISUAL_METRIC_YAW_CONSISTENCY_VERSION = "SPPA-VISUAL-METRIC-YAW-CONSISTENCY-0.1"
VEHICLE_OBSERVATION_LABELS = {
    "car",
    "truck",
    "bus",
    "van",
    "pickup",
    "tractor",
    "tractor_trailer",
    "tractor+trailer",
    "tractor trailer",
    "tractor_with_trailer",
    "articulated_vehicle",
    "vehicle_with_trailer",
    "farm_vehicle",
    "light_vehicle",
    "heavy_vehicle",
    "generic_vehicle",
}
TWO_WHEEL_OBSERVATION_LABELS = {
    "biker",
    "cyclist",
    "two_wheeled_rider",
    "motorcycle",
    "bicycle",
}
VERTICAL_STRUCTURE_HEIGHT_LIMIT_M = 80.0
OBSERVED_COLOR_TARGET_ROLES = {
    "vehicle_body",
    "vehicle_cab",
    "vehicle_attachment",
    "bike_frame",
    "rider_clothing",
    "animal_body",
    "animal_marking",
    "animal_skin_or_horn",
    "vegetation_canopy",
    "vegetation_trunk",
    "vertical_structure_metal",
    "built_structure_body",
    "built_structure_roof",
    "built_structure_window",
    "container_body",
    "container_detail",
    "safety_marker",
    "aircraft_body",
    "aircraft_rotor",
    "agricultural_bale",
    "agricultural_binding",
}


def _meta(role, evidence_source="semantic_prior", uncertainty_visual_style="none", alpha=1.0):
    return {
        "material_role": role,
        "evidence_source": evidence_source,
        "uncertainty_visual_style": uncertainty_visual_style,
        "alpha": alpha,
    }


MATERIAL_METADATA = {
    "brown": _meta("generic_brown_prior"),
    "dark_brown": _meta("generic_dark_brown_prior"),
    "cream": _meta("generic_skin_or_horn_prior"),
    "black": _meta("generic_dark_part_prior"),
    "white": _meta("generic_light_part_prior"),
    "green": _meta("generic_green_prior"),
    "dark_green": _meta("generic_dark_green_prior"),
    "red": _meta("generic_red_prior"),
    "blue": _meta("generic_blue_prior"),
    "gray": _meta("generic_gray_prior"),
    "metal": _meta("generic_metal_prior"),
    "glass": _meta("generic_window_prior"),
    "yellow": _meta("generic_yellow_prior"),
    "animal_body_prior": _meta("animal_body"),
    "animal_marking_prior": _meta("animal_marking"),
    "animal_skin_prior": _meta("animal_skin_or_horn"),
    "animal_limb_prior": _meta("animal_limb"),
    "vegetation_trunk_prior": _meta("vegetation_trunk"),
    "vegetation_canopy_dark_prior": _meta("vegetation_canopy"),
    "vegetation_canopy_light_prior": _meta("vegetation_canopy"),
    "vehicle_body_prior": _meta("vehicle_body"),
    "vehicle_cab_prior": _meta("vehicle_cab"),
    "vehicle_neutral_body_prior": _meta("vehicle_body"),
    "vehicle_farm_body_prior": _meta("vehicle_body"),
    "vehicle_attachment_prior": _meta("vehicle_attachment"),
    "vehicle_window_prior": _meta("vehicle_window"),
    "vehicle_tire_prior": _meta("vehicle_tire"),
    "vehicle_metal_prior": _meta("vehicle_metal_or_hub"),
    "bike_frame_prior": _meta("bike_frame"),
    "rider_clothing_prior": _meta("rider_clothing"),
    "rider_skin_prior": _meta("rider_skin"),
    "structure_metal_prior": _meta("vertical_structure_metal"),
    "built_structure_body_prior": _meta("built_structure_body"),
    "built_structure_roof_prior": _meta("built_structure_roof"),
    "built_structure_window_prior": _meta("built_structure_window"),
    "container_body_prior": _meta("container_body"),
    "container_detail_prior": _meta("container_detail"),
    "safety_marker_prior": _meta("safety_marker"),
    "aircraft_body_prior": _meta("aircraft_body"),
    "aircraft_rotor_prior": _meta("aircraft_rotor"),
    "agricultural_bale_prior": _meta("agricultural_bale"),
    "agricultural_binding_prior": _meta("agricultural_binding"),
    "unknown_volume_fallback": _meta("unknown_conservative_volume", "fallback_unknown", "desaturated_unknown", 0.72),
    "unknown_footprint_fallback": _meta("unknown_footprint", "fallback_unknown", "desaturated_unknown", 0.65),
    "uncertainty_marker_fallback": _meta("uncertainty_marker", "fallback_unknown", "warning_marker", 0.85),
}



class Mesh:
    def __init__(self, lod: str | None = None):
        self.vertices = []
        self.faces = []
        self.parts = []
        self.lod = (lod or SPPA_MESH_LOD or "balanced").lower()
        self.lod_params = mesh_lod_params(self.lod)

    def add_vertex(self, x, y, z):
        self.vertices.append((x, y, z))
        return len(self.vertices)

    def add_face(self, indices, material):
        self.faces.append((indices, material))

    def triangle_count(self) -> int:
        return sum(max(0, len(indices) - 2) for indices, _ in self.faces)

    def _record_part(self, primitive, center, scale, material, face_start, **kwargs):
        faces = self.faces[face_start:]
        triangles = sum(max(0, len(indices) - 2) for indices, _ in faces)
        meta = get_material_metadata(material)
        part = {
            "role": meta["material_role"],
            "primitive": primitive,
            "local_pose": {
                "center": [round(float(v), 6) for v in center],
                "axis": kwargs.get("axis", "z"),
            },
            "scale": [round(float(v), 6) for v in scale],
            "material": material,
            "material_role": meta["material_role"],
            "triangle_budget": triangles,
            "evidence_source": meta["evidence_source"],
            "mesh_lod": self.lod,
        }
        if "segments" in kwargs:
            part["segments"] = int(kwargs["segments"])
        if "endpoints" in kwargs:
            part["connector_endpoints"] = [
                [round(float(v), 6) for v in endpoint]
                for endpoint in kwargs["endpoints"]
            ]
        self.parts.append(part)

    def box(self, center, size, material):
        face_start = len(self.faces)
        cx, cy, cz = center
        sx, sy, sz = (v / 2 for v in size)
        corners = [
            (cx - sx, cy - sy, cz - sz), (cx + sx, cy - sy, cz - sz),
            (cx + sx, cy + sy, cz - sz), (cx - sx, cy + sy, cz - sz),
            (cx - sx, cy - sy, cz + sz), (cx + sx, cy - sy, cz + sz),
            (cx + sx, cy + sy, cz + sz), (cx - sx, cy + sy, cz + sz),
        ]
        ids = [self.add_vertex(*p) for p in corners]
        for face in [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
                     (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]:
            self.add_face([ids[i] for i in face], material)
        self._record_part("box", center, size, material, face_start)

    def sphere(self, center, scale, material, rings=None, segments=None):
        face_start = len(self.faces)
        cx, cy, cz = center
        sx, sy, sz = scale
        # Adaptive tessellation: small blobs stay cheap; large bodies keep more rings.
        radius_hint = max(float(sx), float(sy), float(sz))
        lod = self.lod_params
        if rings is None:
            # Prefer fewer triangles on large organic blobs; silhouette still reads at LOD.
            rings = lod["sphere_rings"] - (1 if radius_hint >= 0.70 and self.lod != "high" else 0)
        if segments is None:
            segments = lod["sphere_segments"] - (0 if radius_hint < 0.70 or self.lod == "high" else 0)
        rings = max(3, int(rings))
        segments = max(5, int(segments))
        grid = []
        for r in range(rings + 1):
            phi = math.pi * r / rings
            row = []
            for s in range(segments):
                theta = 2 * math.pi * s / segments
                x = cx + sx * math.sin(phi) * math.cos(theta)
                y = cy + sy * math.sin(phi) * math.sin(theta)
                z = cz + sz * math.cos(phi)
                row.append(self.add_vertex(x, y, z))
            grid.append(row)
        for r in range(rings):
            for s in range(segments):
                a = grid[r][s]
                b = grid[r][(s + 1) % segments]
                c = grid[r + 1][(s + 1) % segments]
                d = grid[r + 1][s]
                self.add_face([a, b, c, d], material)
        self._record_part("sphere", center, scale, material, face_start, segments=segments)

    def cylinder(self, center, radius, depth, material, axis="z", segments=None):
        face_start = len(self.faces)
        cx, cy, cz = center
        half = depth / 2
        if segments is None:
            # Larger radii keep more segments for round silhouette fidelity.
            base = self.lod_params["cylinder_segments"]
            segments = base + (2 if float(radius) >= 0.35 else 0)
        segments = max(5, int(segments))
        a_ring, b_ring = [], []
        for s in range(segments):
            theta = 2 * math.pi * s / segments
            u = radius * math.cos(theta)
            v = radius * math.sin(theta)
            if axis == "x":
                a = (cx - half, cy + u, cz + v)
                b = (cx + half, cy + u, cz + v)
            elif axis == "y":
                a = (cx + u, cy - half, cz + v)
                b = (cx + u, cy + half, cz + v)
            else:
                a = (cx + u, cy + v, cz - half)
                b = (cx + u, cy + v, cz + half)
            a_ring.append(self.add_vertex(*a))
            b_ring.append(self.add_vertex(*b))
        for s in range(segments):
            self.add_face(
                [a_ring[s], a_ring[(s + 1) % segments],
                 b_ring[(s + 1) % segments], b_ring[s]],
                material,
            )
        self.add_face(list(reversed(a_ring)), material)
        self.add_face(b_ring, material)
        self._record_part("cylinder", center, (radius, radius, depth), material, face_start, axis=axis, segments=segments)

    def cylinder_between(self, start, end, radius, material, segments=None, optional=False):
        """Structural connector. optional=True is dropped under ultra-light budgets."""
        if optional and self.lod_params.get("skip_optional_connectors"):
            return
        face_start = len(self.faces)
        sx, sy, sz = (float(v) for v in start)
        ex, ey, ez = (float(v) for v in end)
        dx, dy, dz = ex - sx, ey - sy, ez - sz
        depth = math.sqrt(dx * dx + dy * dy + dz * dz)
        if depth <= 1e-6:
            return
        if segments is None:
            segments = self.lod_params["connector_segments"]
        segments = max(5, int(segments))

        wx, wy, wz = dx / depth, dy / depth, dz / depth
        tx, ty, tz = (0.0, 0.0, 1.0)
        if abs(wx * tx + wy * ty + wz * tz) > 0.92:
            tx, ty, tz = (0.0, 1.0, 0.0)

        ux, uy, uz = ty * wz - tz * wy, tz * wx - tx * wz, tx * wy - ty * wx
        u_len = math.sqrt(ux * ux + uy * uy + uz * uz)
        ux, uy, uz = ux / u_len, uy / u_len, uz / u_len
        vx, vy, vz = wy * uz - wz * uy, wz * ux - wx * uz, wx * uy - wy * ux

        a_ring, b_ring = [], []
        for s in range(segments):
            theta = 2 * math.pi * s / segments
            c = radius * math.cos(theta)
            r = radius * math.sin(theta)
            ox = c * ux + r * vx
            oy = c * uy + r * vy
            oz = c * uz + r * vz
            a_ring.append(self.add_vertex(sx + ox, sy + oy, sz + oz))
            b_ring.append(self.add_vertex(ex + ox, ey + oy, ez + oz))
        for s in range(segments):
            self.add_face(
                [a_ring[s], a_ring[(s + 1) % segments],
                 b_ring[(s + 1) % segments], b_ring[s]],
                material,
            )
        self.add_face(list(reversed(a_ring)), material)
        self.add_face(b_ring, material)
        center = ((sx + ex) / 2.0, (sy + ey) / 2.0, (sz + ez) / 2.0)
        self._record_part(
            "cylinder_connector",
            center,
            (radius, radius, depth),
            material,
            face_start,
            axis="free",
            segments=segments,
            endpoints=((sx, sy, sz), (ex, ey, ez)),
        )

    def cone(self, center, radius, depth, material, axis="z", segments=10):
        face_start = len(self.faces)
        cx, cy, cz = center
        half = depth / 2
        base = []
        for s in range(segments):
            theta = 2 * math.pi * s / segments
            u = radius * math.cos(theta)
            v = radius * math.sin(theta)
            if axis == "x":
                p = (cx - half, cy + u, cz + v)
                tip = (cx + half, cy, cz)
            elif axis == "y":
                p = (cx + u, cy - half, cz + v)
                tip = (cx, cy + half, cz)
            else:
                p = (cx + u, cy + v, cz - half)
                tip = (cx, cy, cz + half)
            base.append(self.add_vertex(*p))
        tip_id = self.add_vertex(*tip)
        self.add_face(list(reversed(base)), material)
        for s in range(segments):
            self.add_face([base[s], base[(s + 1) % segments], tip_id], material)
        self._record_part("cone", center, (radius, radius, depth), material, face_start, axis=axis, segments=segments)

    def torus(self, center, major, minor, material, axis="x", major_steps=None, minor_steps=None):
        # Cheap wheels: a short cylinder reads as a tire in aerial/side views
        # at a fraction of torus triangles (dominant cost on vehicles).
        mat = str(material or "")
        if self.lod_params.get("cheap_wheels") and ("tire" in mat or "rotor" in mat):
            # Disk wheel: outer tire ring + inner hub keeps top/side circular
            # silhouette much better than a single solid slab, at ~2 cylinders.
            outer = float(major) + float(minor)
            depth = max(float(minor) * 2.2, 0.05)
            segs = max(5, int(self.lod_params.get("cylinder_segments", 6)))
            self.cylinder(center, outer, depth, material, axis=axis, segments=segs)
            if "tire" in mat:
                # hollow-ish look: slightly inset rim + hub (still cheap)
                rim_r = max(float(major) * 0.78, outer * 0.55)
                hub_r = max(float(major) * 0.36, float(minor) * 0.9)
                self.cylinder(center, rim_r, depth * 0.92, material, axis=axis, segments=segs)
                if self.lod != "ultra_light":
                    self.cylinder(center, hub_r, depth * 0.80, "vehicle_metal_prior", axis=axis, segments=segs)
            return
        face_start = len(self.faces)
        cx, cy, cz = center
        # Tire fidelity is mostly silhouette of the major ring; minor tube can stay coarse.
        if major_steps is None:
            major_steps = self.lod_params["torus_major"] + (1 if float(major) >= 0.45 else 0)
        if minor_steps is None:
            minor_steps = self.lod_params["torus_minor"]
        major_steps = max(6, int(major_steps))
        minor_steps = max(3, int(minor_steps))
        grid = []
        for i in range(major_steps):
            theta = 2 * math.pi * i / major_steps
            row = []
            for j in range(minor_steps):
                phi = 2 * math.pi * j / minor_steps
                r = major + minor * math.cos(phi)
                if axis == "x":
                    x = cx + minor * math.sin(phi)
                    y = cy + r * math.cos(theta)
                    z = cz + r * math.sin(theta)
                else:
                    x = cx + r * math.cos(theta)
                    y = cy + minor * math.sin(phi)
                    z = cz + r * math.sin(theta)
                row.append(self.add_vertex(x, y, z))
            grid.append(row)
        for i in range(major_steps):
            for j in range(minor_steps):
                self.add_face([
                    grid[i][j],
                    grid[(i + 1) % major_steps][j],
                    grid[(i + 1) % major_steps][(j + 1) % minor_steps],
                    grid[i][(j + 1) % minor_steps],
                ], material)
        self._record_part(
            "torus",
            center,
            (major, minor, major_steps, minor_steps),
            material,
            face_start,
            axis=axis,
            segments=major_steps,
        )

    def tire(self, center, major, minor, material, axis="y"):
        """Wheel proxy: cheap disk by default; full torus only on high LOD."""
        self.torus(center, major, minor, material, axis=axis)


def cow(mesh):
    cow_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["cow"])

def tree(mesh):
    mesh.cylinder((0, 0, 0.75), 0.20, 1.5, "vegetation_trunk_prior", segments=12)
    mesh.sphere((0, 0, 2.05), (0.85, 0.75, 0.65), "vegetation_canopy_dark_prior")
    mesh.sphere((-0.42, 0.10, 2.32), (0.52, 0.45, 0.42), "vegetation_canopy_light_prior")
    mesh.sphere((0.42, -0.10, 2.30), (0.52, 0.45, 0.42), "vegetation_canopy_light_prior")
    mesh.sphere((0, 0, 2.72), (0.48, 0.42, 0.40), "vegetation_canopy_dark_prior")

def bush(mesh):
    mesh.sphere((0, 0, 0.65), (0.85, 0.65, 0.45), 'vegetation_canopy_dark_prior')
    mesh.sphere((-0.55, 0.05, 0.72), (0.55, 0.45, 0.38), 'vegetation_canopy_light_prior')
    mesh.sphere((0.55, -0.05, 0.72), (0.55, 0.45, 0.38), 'vegetation_canopy_light_prior')
    mesh.sphere((0.0, 0.28, 0.92), (0.55, 0.42, 0.36), 'vegetation_canopy_dark_prior')
    mesh.cylinder((0, 0, 0.25), 0.12, 0.5, 'vegetation_trunk_prior', segments=8)

def car(mesh):
    mesh.box((0, 0, 0.75), (2.4, 1.05, 0.55), "vehicle_body_prior")
    mesh.box((-0.25, 0, 1.18), (1.1, 0.85, 0.48), "vehicle_body_prior")
    mesh.box((-0.25, -0.43, 1.22), (0.78, 0.04, 0.25), "vehicle_window_prior")
    mesh.box((-0.25, 0.43, 1.22), (0.78, 0.04, 0.25), "vehicle_window_prior")
    for x in (-0.75, 0.75):
        for y in (-0.58, 0.58):
            mesh.torus((x, y, 0.45), 0.24, 0.07, "vehicle_tire_prior", axis="y")
            mesh.cylinder((x, y, 0.45), 0.13, 0.08, "vehicle_metal_prior", axis="y")

def truck(mesh):
    mesh.box((-0.55, 0, 0.95), (2.5, 1.1, 0.9), "vehicle_neutral_body_prior")
    mesh.box((1.15, 0, 0.85), (1.0, 1.05, 0.75), "vehicle_cab_prior")
    mesh.box((1.33, -0.53, 1.1), (0.42, 0.04, 0.28), "vehicle_window_prior")
    for x in (-1.35, -0.35, 0.85, 1.45):
        for y in (-0.62, 0.62):
            mesh.torus((x, y, 0.42), 0.24, 0.07, "vehicle_tire_prior", axis="y")
            mesh.cylinder((x, y, 0.42), 0.13, 0.08, "vehicle_metal_prior", axis="y")

def person(mesh):
    person_parametric(mesh, {"length": 0.55, "width": 0.55, "height": 1.75})


def bicycle(mesh):
    bicycle_parametric(mesh, {"length": 1.70, "width": 0.45, "height": 1.15})


def motorcycle(mesh):
    motorcycle_parametric(mesh, {"length": 2.05, "width": 0.72, "height": 1.25})


def bus(mesh):
    bus_parametric(mesh, {"length": 9.8, "width": 2.55, "height": 3.2})


def van(mesh):
    van_parametric(mesh, {"length": 5.2, "width": 2.05, "height": 2.25})


def pickup(mesh):
    pickup_parametric(mesh, {"length": 5.4, "width": 2.05, "height": 1.9})


def quadruped_generic(mesh):
    quadruped_parametric(mesh, {"length": 2.2, "width": 0.8, "height": 1.4})


def bull(mesh):
    cow_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["bull"])


def cattle(mesh):
    cow_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["cattle"])


def horse(mesh):
    horse_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["horse"])


def dog(mesh):
    dog_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["dog"])


def sheep(mesh):
    sheep_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["sheep"])


def goat(mesh):
    goat_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["goat"])


def deer(mesh):
    deer_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["deer"])


def clamp(value, low, high):
    return max(low, min(high, value))


def dims_tuple(dims_m):
    parsed = parse_dims_arg(dims_m)
    if not parsed:
        return None
    length = parsed["length"]
    width = parsed["width"]
    height = parsed["height"]
    if length <= 0 or width <= 0 or height <= 0:
        return None
    return length, width, height


def car_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m)
    if not dims:
        return car(mesh)
    length, width, height = dims
    half_l = length / 2.0
    wheel_radius = clamp(height * 0.155, 0.22, 0.34)
    tire_minor = clamp(wheel_radius * 0.28, 0.055, 0.085)
    wheel_y = max(0.0, width / 2.0 - tire_minor)
    wheel_z = wheel_radius + tire_minor
    wheel_x = clamp(length * 0.31, wheel_radius * 2.0 + 0.25, half_l - wheel_radius - 0.15)

    body_height = clamp(height * 0.34, 0.45, 0.68)
    body_bottom = wheel_z + tire_minor * 0.70
    body_center_z = body_bottom + body_height / 2.0
    body_length = max(length - 2.0 * tire_minor, length * 0.78)
    body_width = max(0.1, width - 2.0 * tire_minor)

    cabin_length = clamp(width * 0.70, 1.05, 1.42)
    cabin_width = max(0.1, width * 0.72)
    cabin_height = clamp(height - (body_center_z + body_height / 2.0), 0.36, 0.62)
    cabin_center_x = clamp(-length * 0.05, -half_l + cabin_length / 2.0, half_l - cabin_length / 2.0)
    cabin_center_z = body_center_z + body_height / 2.0 + cabin_height / 2.0

    mesh.box((0, 0, body_center_z), (body_length, body_width, body_height), "vehicle_body_prior")
    mesh.box((cabin_center_x, 0, cabin_center_z), (cabin_length, cabin_width, cabin_height), "vehicle_cab_prior")
    for side_y in (-cabin_width / 2.0 - 0.01, cabin_width / 2.0 + 0.01):
        mesh.box((cabin_center_x, side_y, cabin_center_z + cabin_height * 0.08), (cabin_length * 0.62, 0.035, cabin_height * 0.50), "vehicle_window_prior")
    for x in (-wheel_x, wheel_x):
        for y in (-wheel_y, wheel_y):
            mesh.torus((x, y, wheel_z), wheel_radius, tire_minor, "vehicle_tire_prior", axis="y")
            mesh.cylinder((x, y, wheel_z), wheel_radius * 0.48, tire_minor * 1.30, "vehicle_metal_prior", axis="y")


def truck_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m)
    if not dims:
        return truck(mesh)
    length, width, height = dims
    half_l = length / 2.0
    wheel_radius = clamp(height * 0.145, 0.32, 0.46)
    tire_minor = clamp(wheel_radius * 0.24, 0.075, 0.11)
    wheel_y = max(0.0, width / 2.0 - tire_minor)
    wheel_z = wheel_radius + tire_minor

    cab_length = clamp(width * 0.72, 1.45, 1.85)
    gap = clamp(length * 0.025, 0.12, 0.28)
    rear_margin = max(wheel_radius + tire_minor + 0.10, length * 0.035)
    front_margin = max(wheel_radius + tire_minor + 0.08, length * 0.025)
    cab_front = half_l - front_margin
    cab_rear = cab_front - cab_length
    cargo_front = cab_rear - gap
    cargo_rear = -half_l + rear_margin
    cargo_length = max(0.6, cargo_front - cargo_rear)
    cargo_center_x = cargo_rear + cargo_length / 2.0
    cab_center_x = cab_rear + cab_length / 2.0

    chassis_height = clamp(height * 0.09, 0.16, 0.28)
    chassis_center_z = wheel_z + wheel_radius * 0.36
    cargo_height = clamp(height * 0.48, 1.05, max(1.10, height * 0.58))
    cargo_bottom = chassis_center_z + chassis_height / 2.0
    cargo_center_z = cargo_bottom + cargo_height / 2.0
    cab_height = max(0.75, height - cargo_bottom)
    cab_center_z = cargo_bottom + cab_height / 2.0

    mesh.box((cargo_center_x, 0, chassis_center_z), (max(0.2, length - front_margin - rear_margin), width * 0.78, chassis_height), "vehicle_metal_prior")
    mesh.box((cargo_center_x, 0, cargo_center_z), (cargo_length, width * 0.92, cargo_height), "vehicle_neutral_body_prior")
    mesh.box((cab_center_x, 0, cab_center_z), (cab_length, width * 0.90, cab_height), "vehicle_cab_prior")
    mesh.box((cab_center_x + cab_length * 0.18, -width * 0.45 - 0.01, cab_center_z + cab_height * 0.12), (cab_length * 0.42, 0.04, cab_height * 0.34), "vehicle_window_prior")
    mesh.box((cab_center_x + cab_length * 0.18, width * 0.45 + 0.01, cab_center_z + cab_height * 0.12), (cab_length * 0.42, 0.04, cab_height * 0.34), "vehicle_window_prior")

    front_axle = clamp(cab_center_x + cab_length * 0.18, -half_l + wheel_radius, half_l - wheel_radius)
    rear_axle_min = cargo_rear + wheel_radius + tire_minor
    rear_axle_max = cargo_front - wheel_radius - tire_minor
    rear_axles = 2 if length < 6.2 else 3
    axle_positions = [front_axle]
    if rear_axle_max > rear_axle_min:
        if rear_axles == 2:
            axle_positions.extend([rear_axle_min, rear_axle_max])
        else:
            axle_positions.extend([rear_axle_min, (rear_axle_min + rear_axle_max) / 2.0, rear_axle_max])
    for x in sorted(axle_positions):
        for y in (-wheel_y, wheel_y):
            mesh.torus((x, y, wheel_z), wheel_radius, tire_minor, "vehicle_tire_prior", axis="y")
            mesh.cylinder((x, y, wheel_z), wheel_radius * 0.48, tire_minor * 1.35, "vehicle_metal_prior", axis="y")


def person_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m) or (0.55, 0.55, 1.75)
    length, width, height = dims
    shoulder = clamp(width * 0.55, 0.22, 0.48)
    depth = clamp(length * 0.42, 0.14, 0.32)
    head_r = clamp(height * 0.075, 0.09, 0.15)
    leg_h = clamp(height * 0.42, 0.55, 0.92)
    torso_h = clamp(height * 0.32, 0.42, 0.68)
    torso_z = leg_h + torso_h / 2.0
    head_z = height - head_r
    leg_r = clamp(width * 0.055, 0.035, 0.065)
    arm_r = clamp(width * 0.045, 0.028, 0.055)

    mesh.sphere((0, 0, torso_z), (depth, shoulder, torso_h / 2.0), "rider_clothing_prior")
    mesh.sphere((0, 0, head_z), (head_r, head_r, head_r), "rider_skin_prior")
    for y in (-shoulder * 0.55, shoulder * 0.55):
        mesh.cylinder((0, y, leg_h / 2.0), leg_r, leg_h, "rider_skin_prior", axis="z", segments=8)
        mesh.cylinder((0, y * 1.28, torso_z), arm_r, torso_h * 0.95, "rider_skin_prior", axis="z", segments=8)


def bicycle_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m) or (1.70, 0.45, 1.15)
    length, width, height = dims
    half_l = length / 2.0
    wheel_radius = clamp(height * 0.30, 0.24, 0.42)
    tire_minor = clamp(wheel_radius * 0.10, 0.030, 0.055)
    wheel_z = wheel_radius + tire_minor
    wheel_x = max(wheel_radius + tire_minor, half_l - wheel_radius - tire_minor)
    frame_z = clamp(height * 0.55, wheel_z + 0.16, height * 0.72)
    frame_r = clamp(width * 0.055, 0.020, 0.040)
    rear_hub = (-wheel_x, 0.0, wheel_z)
    front_hub = (wheel_x, 0.0, wheel_z)
    bottom_bracket = (0.0, 0.0, wheel_z + wheel_radius * 0.22)
    seat_cluster = (-wheel_x * 0.26, 0.0, frame_z + height * 0.22)
    head_cluster = (wheel_x * 0.58, 0.0, frame_z + height * 0.20)
    handlebar = (wheel_x * 0.64, 0.0, clamp(height * 0.92, head_cluster[2] + 0.10, height))

    for x in (-wheel_x, wheel_x):
        mesh.torus((x, 0, wheel_z), wheel_radius, tire_minor, "vehicle_tire_prior", axis="y")
        mesh.cylinder((x, 0, wheel_z), wheel_radius * 0.32, tire_minor * 1.35, "vehicle_metal_prior", axis="y", segments=8)
    for start, end in (
        (rear_hub, bottom_bracket),
        (front_hub, bottom_bracket),
        (bottom_bracket, seat_cluster),
        (seat_cluster, rear_hub),
        (seat_cluster, head_cluster),
        (head_cluster, front_hub),
        (bottom_bracket, head_cluster),
    ):
        mesh.cylinder_between(start, end, frame_r, "bike_frame_prior", segments=8)
    mesh.box((seat_cluster[0], 0, seat_cluster[2] + 0.03), (clamp(length * 0.18, 0.22, 0.36), clamp(width * 0.42, 0.12, 0.24), 0.045), "vehicle_tire_prior")
    mesh.cylinder_between(head_cluster, handlebar, frame_r, "bike_frame_prior", segments=8)
    mesh.box((handlebar[0], 0, handlebar[2]), (0.06, width, 0.035), "bike_frame_prior")


def biker_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m)
    if not dims:
        return biker(mesh)
    length, width, height = dims
    bike_h = clamp(height * 0.56, 0.90, 1.30)
    bicycle_parametric(mesh, {"length": length, "width": width, "height": bike_h})
    wheel_radius = clamp(bike_h * 0.30, 0.24, 0.42)
    tire_minor = clamp(wheel_radius * 0.10, 0.030, 0.055)
    wheel_z = wheel_radius + tire_minor
    wheel_x = max(wheel_radius + tire_minor, length / 2.0 - wheel_radius - tire_minor)
    frame_z = clamp(bike_h * 0.55, wheel_z + 0.16, bike_h * 0.72)
    seat_cluster = (-wheel_x * 0.26, 0.0, frame_z + bike_h * 0.22)
    head_cluster = (wheel_x * 0.58, 0.0, frame_z + bike_h * 0.20)
    handlebar_z = clamp(bike_h * 0.92, head_cluster[2] + 0.10, bike_h)
    rider_height = max(0.8, height - bike_h * 0.22)
    torso_center = (-length * 0.02, 0.0, bike_h * 0.72 + rider_height * 0.18)
    pelvis = (seat_cluster[0] + length * 0.05, 0.0, seat_cluster[2] + rider_height * 0.10)
    head_center = (length * 0.04, 0.0, min(height, torso_center[2] + rider_height * 0.30))
    mesh.sphere(torso_center, (width * 0.18, width * 0.24, rider_height * 0.16), "rider_clothing_prior")
    mesh.sphere(head_center, (width * 0.11, width * 0.11, width * 0.11), "rider_skin_prior")
    limb_r = clamp(width * 0.035, 0.025, 0.055)
    mesh.cylinder_between(pelvis, seat_cluster, limb_r * 0.95, "rider_clothing_prior", segments=8)
    for y in (-width * 0.12, width * 0.12):
        shoulder = (torso_center[0] + length * 0.05, y * 0.55, torso_center[2] + rider_height * 0.08)
        grip = (wheel_x * 0.64, y, handlebar_z)
        knee = (length * 0.03, y * 0.45, wheel_z + wheel_radius * 0.52)
        pedal = (length * 0.08, y * 0.35, wheel_z + wheel_radius * 0.12)
        mesh.cylinder_between(shoulder, grip, limb_r, "rider_skin_prior", segments=8)
        mesh.cylinder_between(pelvis, knee, limb_r, "rider_skin_prior", segments=8)
        mesh.cylinder_between(knee, pedal, limb_r, "rider_skin_prior", segments=8)


def motorcycle_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m) or (2.05, 0.72, 1.25)
    length, width, height = dims
    half_l = length / 2.0
    wheel_radius = clamp(height * 0.25, 0.26, 0.42)
    tire_minor = clamp(wheel_radius * 0.17, 0.045, 0.080)
    wheel_z = wheel_radius + tire_minor
    wheel_x = max(wheel_radius + tire_minor, half_l - wheel_radius - tire_minor)
    body_z = wheel_z + clamp(height * 0.20, 0.20, 0.34)

    for x in (-wheel_x, wheel_x):
        mesh.torus((x, 0, wheel_z), wheel_radius, tire_minor, "vehicle_tire_prior", axis="y")
        mesh.cylinder((x, 0, wheel_z), wheel_radius * 0.44, tire_minor * 1.40, "vehicle_metal_prior", axis="y", segments=8)
    mesh.box((0, 0, body_z), (max(0.45, length * 0.46), max(0.18, width * 0.45), max(0.16, height * 0.18)), "vehicle_body_prior")
    mesh.box((-length * 0.10, 0, body_z + height * 0.15), (length * 0.42, width * 0.34, height * 0.10), "vehicle_tire_prior")
    mesh.cylinder((wheel_x * 0.70, 0, body_z + height * 0.22), clamp(width * 0.035, 0.025, 0.05), clamp(height * 0.45, 0.36, 0.62), "vehicle_metal_prior", axis="z", segments=8)
    mesh.box((wheel_x * 0.78, 0, body_z + height * 0.46), (0.10, width, 0.04), "vehicle_metal_prior")


def bus_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m) or (9.8, 2.55, 3.2)
    length, width, height = dims
    half_l = length / 2.0
    wheel_radius = clamp(height * 0.11, 0.34, 0.50)
    tire_minor = clamp(wheel_radius * 0.22, 0.070, 0.11)
    wheel_y = max(0.0, width / 2.0 - tire_minor)
    wheel_z = wheel_radius + tire_minor
    body_bottom = wheel_z + tire_minor * 0.70
    body_height = max(0.8, height - body_bottom)
    body_length = max(1.0, length * 0.94)
    body_width = max(0.4, width * 0.92)
    body_z = body_bottom + body_height / 2.0
    window_z = body_z + body_height * 0.18

    mesh.box((0, 0, body_z), (body_length, body_width, body_height), "vehicle_neutral_body_prior")
    mesh.box((0, -body_width / 2.0 - 0.01, window_z), (body_length * 0.78, 0.04, body_height * 0.24), "vehicle_window_prior")
    mesh.box((0, body_width / 2.0 + 0.01, window_z), (body_length * 0.78, 0.04, body_height * 0.24), "vehicle_window_prior")
    mesh.box((half_l - body_length * 0.10, 0, window_z), (0.04, body_width * 0.64, body_height * 0.28), "vehicle_window_prior")
    axle_positions = [-half_l + length * 0.18, half_l - length * 0.18]
    if length > 8.0:
        axle_positions.insert(1, -half_l + length * 0.44)
    for x in axle_positions:
        for y in (-wheel_y, wheel_y):
            mesh.torus((x, y, wheel_z), wheel_radius, tire_minor, "vehicle_tire_prior", axis="y")
            mesh.cylinder((x, y, wheel_z), wheel_radius * 0.48, tire_minor * 1.35, "vehicle_metal_prior", axis="y", segments=8)


def van_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m) or (5.2, 2.05, 2.25)
    length, width, height = dims
    half_l = length / 2.0
    wheel_radius = clamp(height * 0.13, 0.25, 0.36)
    tire_minor = clamp(wheel_radius * 0.24, 0.055, 0.085)
    wheel_y = max(0.0, width / 2.0 - tire_minor)
    wheel_z = wheel_radius + tire_minor
    body_bottom = wheel_z + tire_minor * 0.75
    body_height = max(0.65, height - body_bottom)
    body_width = max(0.4, width * 0.88)
    cab_length = clamp(length * 0.28, 1.20, 1.70)
    front_margin = max(wheel_radius + tire_minor + 0.08, length * 0.035)
    rear_margin = max(wheel_radius + tire_minor + 0.10, length * 0.04)
    cab_front = half_l - front_margin
    cab_rear = cab_front - cab_length
    cargo_rear = -half_l + rear_margin
    cargo_front = cab_rear
    cargo_length = max(0.75, cargo_front - cargo_rear)
    cargo_center_x = cargo_rear + cargo_length / 2.0
    cab_center_x = cab_rear + cab_length / 2.0

    cargo_height = body_height
    cab_height = clamp(body_height * 0.92, 0.75, body_height)
    cargo_z = body_bottom + cargo_height / 2.0
    cab_z = body_bottom + cab_height / 2.0

    mesh.box((cargo_center_x, 0, cargo_z), (cargo_length, body_width, cargo_height), "vehicle_body_prior")
    mesh.box((cab_center_x, 0, cab_z), (cab_length, body_width * 0.96, cab_height), "vehicle_cab_prior")
    mesh.box((cab_center_x + cab_length * 0.12, -body_width * 0.48 - 0.01, cab_z + cab_height * 0.14), (cab_length * 0.54, 0.04, cab_height * 0.30), "vehicle_window_prior")
    mesh.box((cab_center_x + cab_length * 0.12, body_width * 0.48 + 0.01, cab_z + cab_height * 0.14), (cab_length * 0.54, 0.04, cab_height * 0.30), "vehicle_window_prior")
    mesh.box((cab_front + 0.01, 0, cab_z + cab_height * 0.14), (0.04, body_width * 0.62, cab_height * 0.30), "vehicle_window_prior")
    front_axle = clamp(cab_center_x + cab_length * 0.20, -half_l + wheel_radius, half_l - wheel_radius)
    rear_axle = clamp(cargo_rear + cargo_length * 0.22, -half_l + wheel_radius, half_l - wheel_radius)
    for x in (rear_axle, front_axle):
        for y in (-wheel_y, wheel_y):
            mesh.torus((x, y, wheel_z), wheel_radius, tire_minor, "vehicle_tire_prior", axis="y")
            mesh.cylinder((x, y, wheel_z), wheel_radius * 0.48, tire_minor * 1.35, "vehicle_metal_prior", axis="y", segments=8)


def pickup_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m) or (5.4, 2.05, 1.9)
    length, width, height = dims
    half_l = length / 2.0
    wheel_radius = clamp(height * 0.16, 0.28, 0.40)
    tire_minor = clamp(wheel_radius * 0.24, 0.060, 0.095)
    wheel_y = max(0.0, width / 2.0 - tire_minor)
    wheel_z = wheel_radius + tire_minor
    bed_length = clamp(length * 0.44, 1.35, length * 0.56)
    cab_length = clamp(length * 0.30, 1.15, 1.75)
    body_bottom = wheel_z + tire_minor * 0.70
    bed_height = clamp(height * 0.34, 0.45, 0.72)
    cab_height = max(0.75, height - body_bottom)
    bed_center_x = -half_l + bed_length / 2.0 + length * 0.06
    cab_center_x = bed_center_x + bed_length / 2.0 + cab_length / 2.0 + length * 0.035
    bed_center_z = body_bottom + bed_height / 2.0
    cab_center_z = body_bottom + cab_height / 2.0

    mesh.box((bed_center_x, 0, bed_center_z), (bed_length, width * 0.90, bed_height), "vehicle_neutral_body_prior")
    mesh.box((cab_center_x, 0, cab_center_z), (cab_length, width * 0.88, cab_height), "vehicle_cab_prior")
    mesh.box((cab_center_x + cab_length * 0.18, -width * 0.44 - 0.01, cab_center_z + cab_height * 0.12), (cab_length * 0.42, 0.04, cab_height * 0.32), "vehicle_window_prior")
    mesh.box((cab_center_x + cab_length * 0.18, width * 0.44 + 0.01, cab_center_z + cab_height * 0.12), (cab_length * 0.42, 0.04, cab_height * 0.32), "vehicle_window_prior")
    for x in (-half_l + length * 0.20, half_l - length * 0.22):
        for y in (-wheel_y, wheel_y):
            mesh.torus((x, y, wheel_z), wheel_radius, tire_minor, "vehicle_tire_prior", axis="y")
            mesh.cylinder((x, y, wheel_z), wheel_radius * 0.48, tire_minor * 1.35, "vehicle_metal_prior", axis="y", segments=8)


def tractor_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m)
    if not dims:
        return tractor(mesh)
    length, width, height = dims
    half_l = length / 2.0
    rear_r = clamp(height * 0.20, 0.36, 0.62)
    front_r = clamp(height * 0.13, 0.24, 0.40)
    tire_minor = clamp(rear_r * 0.22, 0.08, 0.13)
    wheel_y = max(0.0, width / 2.0 - tire_minor)
    body_z = rear_r + tire_minor + height * 0.18
    body_h = clamp(height * 0.25, 0.42, 0.72)
    cab_h = clamp(height * 0.36, 0.65, 1.05)

    mesh.box((-length * 0.08, 0, body_z), (length * 0.42, width * 0.62, body_h), "vehicle_farm_body_prior")
    mesh.box((length * 0.22, 0, body_z + body_h / 2.0 + cab_h / 2.0), (length * 0.22, width * 0.58, cab_h), "vehicle_farm_body_prior")
    mesh.box((length * 0.22, 0, body_z + body_h + cab_h + clamp(height * 0.025, 0.05, 0.10)), (length * 0.26, width * 0.66, clamp(height * 0.05, 0.08, 0.14)), "vehicle_metal_prior")
    mesh.box((length * 0.24, -width * 0.30 - 0.01, body_z + body_h + cab_h * 0.54), (length * 0.12, 0.04, cab_h * 0.38), "vehicle_window_prior")
    mesh.box((length * 0.24, width * 0.30 + 0.01, body_z + body_h + cab_h * 0.54), (length * 0.12, 0.04, cab_h * 0.38), "vehicle_window_prior")
    mesh.box((-half_l + length * 0.12, 0, body_z + body_h * 0.15), (length * 0.22, width * 0.48, body_h * 0.62), "vehicle_attachment_prior")
    rail_z = rear_r + tire_minor + rear_r * 0.30
    mesh.box((length * 0.02, 0, rail_z), (length * 0.76, clamp(width * 0.12, 0.14, 0.30), clamp(height * 0.045, 0.08, 0.16)), "vehicle_metal_prior")
    mesh.cylinder((length * 0.04, width * 0.24, body_z + body_h + cab_h * 0.33), clamp(width * 0.025, 0.035, 0.060), clamp(cab_h * 0.74, 0.45, 0.90), "vehicle_metal_prior", axis="z", segments=8)
    axle_r = clamp(width * 0.020, 0.035, 0.065)
    rear_axle = (-length * 0.24, rear_r + tire_minor)
    front_axle = (length * 0.30, front_r + tire_minor * 0.75)
    mesh.cylinder_between((rear_axle[0], -wheel_y, rear_axle[1]), (rear_axle[0], wheel_y, rear_axle[1]), axle_r, "vehicle_metal_prior", segments=8)
    mesh.cylinder_between((front_axle[0], -wheel_y, front_axle[1]), (front_axle[0], wheel_y, front_axle[1]), axle_r * 0.85, "vehicle_metal_prior", segments=8)
    mesh.cylinder_between((rear_axle[0], -wheel_y * 0.82, rear_axle[1] + rear_r * 0.50), (front_axle[0], -wheel_y * 0.72, front_axle[1] + front_r * 0.48), axle_r * 0.70, "vehicle_metal_prior", segments=8)
    mesh.cylinder_between((rear_axle[0], wheel_y * 0.82, rear_axle[1] + rear_r * 0.50), (front_axle[0], wheel_y * 0.72, front_axle[1] + front_r * 0.48), axle_r * 0.70, "vehicle_metal_prior", segments=8)
    for y in (-wheel_y, wheel_y):
        mesh.torus((-length * 0.24, y, rear_r + tire_minor), rear_r, tire_minor, "vehicle_tire_prior", axis="y")
        mesh.cylinder((-length * 0.24, y, rear_r + tire_minor), rear_r * 0.45, tire_minor * 1.25, "vehicle_attachment_prior", axis="y", segments=8)
        mesh.torus((length * 0.30, y, front_r + tire_minor * 0.75), front_r, tire_minor * 0.78, "vehicle_tire_prior", axis="y")
        mesh.cylinder((length * 0.30, y, front_r + tire_minor * 0.75), front_r * 0.45, tire_minor, "vehicle_attachment_prior", axis="y", segments=8)


def tractor_trailer_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m)
    if not dims:
        dims = dims_tuple(DEFAULT_ARCHETYPE_DIMS_M["tractor_trailer"])
    length, width, height = dims
    half_l = length / 2.0
    front_margin = clamp(length * 0.025, 0.12, 0.28)
    rear_margin = clamp(length * 0.025, 0.12, 0.28)
    gap = clamp(length * 0.035, 0.18, 0.42)
    tractor_l = clamp(length * 0.42, 2.60, min(4.60, length * 0.58))
    tractor_front = half_l - front_margin
    tractor_rear = tractor_front - tractor_l
    trailer_front = tractor_rear - gap
    trailer_rear = -half_l + rear_margin
    trailer_l = max(0.75, trailer_front - trailer_rear)
    trailer_center_x = trailer_rear + trailer_l / 2.0

    rear_r = clamp(height * 0.17, 0.34, 0.58)
    front_r = clamp(height * 0.11, 0.22, 0.38)
    tire_minor = clamp(rear_r * 0.22, 0.075, 0.13)
    wheel_y = max(0.0, width / 2.0 - tire_minor)
    rear_wheel_z = rear_r + tire_minor
    front_wheel_z = front_r + tire_minor * 0.75
    chassis_z = rear_wheel_z + rear_r * 0.36
    chassis_h = clamp(height * 0.08, 0.14, 0.24)
    body_h = clamp(height * 0.22, 0.40, 0.68)
    body_z = chassis_z + chassis_h / 2.0 + body_h / 2.0
    cab_h = clamp(height * 0.34, 0.62, 1.05)
    cab_w = width * 0.58
    body_w = width * 0.58

    engine_l = tractor_l * 0.42
    engine_x = tractor_rear + tractor_l * 0.42
    cab_l = tractor_l * 0.24
    cab_x = tractor_rear + tractor_l * 0.72
    nose_l = tractor_l * 0.20
    nose_x = tractor_rear + tractor_l * 0.16
    mesh.box((engine_x, 0, body_z), (engine_l, body_w, body_h), "vehicle_farm_body_prior")
    mesh.box((cab_x, 0, body_z + body_h / 2.0 + cab_h / 2.0), (cab_l, cab_w, cab_h), "vehicle_farm_body_prior")
    mesh.box((cab_x + cab_l * 0.08, -cab_w / 2.0 - 0.01, body_z + body_h / 2.0 + cab_h * 0.55), (cab_l * 0.58, 0.04, cab_h * 0.34), "vehicle_window_prior")
    mesh.box((cab_x + cab_l * 0.08, cab_w / 2.0 + 0.01, body_z + body_h / 2.0 + cab_h * 0.55), (cab_l * 0.58, 0.04, cab_h * 0.34), "vehicle_window_prior")
    mesh.box((nose_x, 0, body_z + body_h * 0.03), (nose_l, width * 0.46, body_h * 0.62), "vehicle_attachment_prior")

    rear_axle = tractor_rear + tractor_l * 0.28
    front_axle = tractor_rear + tractor_l * 0.82
    axle_r = clamp(width * 0.018, 0.035, 0.065)
    mesh.cylinder_between((rear_axle, -wheel_y, rear_wheel_z), (rear_axle, wheel_y, rear_wheel_z), axle_r, "vehicle_metal_prior", segments=8)
    mesh.cylinder_between((front_axle, -wheel_y, front_wheel_z), (front_axle, wheel_y, front_wheel_z), axle_r * 0.85, "vehicle_metal_prior", segments=8)
    for y in (-wheel_y, wheel_y):
        mesh.torus((rear_axle, y, rear_wheel_z), rear_r, tire_minor, "vehicle_tire_prior", axis="y")
        mesh.cylinder((rear_axle, y, rear_wheel_z), rear_r * 0.45, tire_minor * 1.25, "vehicle_attachment_prior", axis="y", segments=8)
        mesh.torus((front_axle, y, front_wheel_z), front_r, tire_minor * 0.78, "vehicle_tire_prior", axis="y")
        mesh.cylinder((front_axle, y, front_wheel_z), front_r * 0.45, tire_minor, "vehicle_attachment_prior", axis="y", segments=8)

    hitch_r = clamp(width * 0.030, 0.035, 0.07)
    tractor_hitch = (tractor_rear + tractor_l * 0.03, 0.0, chassis_z)
    trailer_hitch = (trailer_front - trailer_l * 0.04, 0.0, chassis_z)
    mesh.cylinder_between(tractor_hitch, trailer_hitch, hitch_r, "vehicle_metal_prior", segments=8)
    for y in (-width * 0.18, width * 0.18):
        mesh.cylinder_between(
            (tractor_hitch[0] - gap * 0.10, y, chassis_z - chassis_h * 0.20),
            (trailer_hitch[0] + gap * 0.18, 0.0, chassis_z),
            hitch_r * 0.72,
            "vehicle_metal_prior",
            segments=8,
        )
    mesh.box((tractor_rear + tractor_l * 0.04, 0, chassis_z), (clamp(length * 0.025, 0.14, 0.28), width * 0.34, chassis_h * 0.70), "vehicle_metal_prior")
    mesh.box((trailer_front - trailer_l * 0.02, 0, chassis_z), (clamp(length * 0.030, 0.16, 0.34), width * 0.40, chassis_h * 0.72), "vehicle_metal_prior")
    mesh.box((trailer_center_x, 0, chassis_z), (trailer_l * 0.88, width * 0.78, chassis_h), "vehicle_metal_prior")

    tank_radius = clamp(min(width, height) * 0.28, 0.42, max(0.48, width * 0.44))
    tank_z = chassis_z + chassis_h / 2.0 + tank_radius
    tank_len = max(0.55, trailer_l * 0.82)
    mesh.cylinder((trailer_center_x, 0, tank_z), tank_radius, tank_len, "container_body_prior", axis="x", segments=18)
    mesh.cylinder((trailer_center_x - tank_len * 0.36, 0, tank_z + tank_radius * 0.68), clamp(tank_radius * 0.08, 0.04, 0.09), tank_len * 0.20, "container_detail_prior", axis="x", segments=8)
    mesh.box((trailer_center_x, 0, tank_z + tank_radius * 0.88), (tank_len * 0.70, clamp(width * 0.08, 0.10, 0.22), clamp(height * 0.04, 0.06, 0.14)), "container_detail_prior")

    trailer_wheel_r = clamp(height * 0.12, 0.26, 0.42)
    trailer_minor = clamp(trailer_wheel_r * 0.24, 0.060, 0.10)
    trailer_wheel_z = trailer_wheel_r + trailer_minor
    trailer_axles = [
        trailer_center_x - trailer_l * 0.23,
        trailer_center_x + trailer_l * 0.21,
    ]
    for axle_index, axle_x in enumerate(trailer_axles):
        if axle_index == 0:
            mesh.cylinder_between((axle_x, -wheel_y, trailer_wheel_z), (axle_x, wheel_y, trailer_wheel_z), axle_r * 0.85, "vehicle_metal_prior", segments=8)
        for y in (-wheel_y, wheel_y):
            mesh.torus((axle_x, y, trailer_wheel_z), trailer_wheel_r, trailer_minor, "vehicle_tire_prior", axis="y")
            mesh.cylinder((axle_x, y, trailer_wheel_z), trailer_wheel_r * 0.45, trailer_minor * 1.25, "vehicle_metal_prior", axis="y", segments=8)


def articulated_vehicle_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m)
    if not dims:
        dims = dims_tuple(DEFAULT_ARCHETYPE_DIMS_M["articulated_vehicle"])
    length, width, height = dims
    half_l = length / 2.0
    front_margin = clamp(length * 0.030, 0.16, 0.35)
    rear_margin = clamp(length * 0.025, 0.14, 0.32)
    gap = clamp(length * 0.035, 0.22, 0.55)
    cab_l = clamp(length * 0.20, 1.55, min(2.60, length * 0.30))
    cab_front = half_l - front_margin
    cab_rear = cab_front - cab_l
    trailer_front = cab_rear - gap
    trailer_rear = -half_l + rear_margin
    trailer_l = max(1.0, trailer_front - trailer_rear)
    trailer_center_x = trailer_rear + trailer_l / 2.0

    wheel_r = clamp(height * 0.105, 0.30, 0.48)
    tire_minor = clamp(wheel_r * 0.23, 0.065, 0.11)
    wheel_y = max(0.0, width / 2.0 - tire_minor)
    wheel_z = wheel_r + tire_minor
    chassis_z = wheel_z + wheel_r * 0.35
    chassis_h = clamp(height * 0.075, 0.13, 0.25)
    cab_h = clamp(height * 0.52, 1.20, height * 0.70)
    cab_w = width * 0.86
    cab_center_x = cab_rear + cab_l / 2.0
    cab_center_z = chassis_z + chassis_h / 2.0 + cab_h / 2.0

    mesh.box((cab_center_x, 0, chassis_z), (cab_l * 1.05, width * 0.72, chassis_h), "vehicle_metal_prior")
    mesh.box((cab_center_x, 0, cab_center_z), (cab_l, cab_w, cab_h), "vehicle_cab_prior")
    mesh.box((cab_center_x + cab_l * 0.18, -cab_w / 2.0 - 0.01, cab_center_z + cab_h * 0.10), (cab_l * 0.48, 0.04, cab_h * 0.30), "vehicle_window_prior")
    mesh.box((cab_center_x + cab_l * 0.18, cab_w / 2.0 + 0.01, cab_center_z + cab_h * 0.10), (cab_l * 0.48, 0.04, cab_h * 0.30), "vehicle_window_prior")

    hitch_r = clamp(width * 0.026, 0.035, 0.07)
    cab_hitch = (cab_rear + cab_l * 0.08, 0.0, chassis_z)
    trailer_hitch = (trailer_front - trailer_l * 0.035, 0.0, chassis_z)
    mesh.cylinder_between(cab_hitch, trailer_hitch, hitch_r, "vehicle_metal_prior", segments=8)
    mesh.box((trailer_center_x, 0, chassis_z), (trailer_l * 0.92, width * 0.78, chassis_h), "vehicle_metal_prior")

    tank_radius = clamp(min(width, height) * 0.30, 0.48, max(0.55, width * 0.44))
    tank_z = chassis_z + chassis_h / 2.0 + tank_radius
    tank_l = max(1.0, trailer_l * 0.84)
    mesh.cylinder((trailer_center_x, 0, tank_z), tank_radius, tank_l, "container_body_prior", axis="x", segments=18)
    mesh.cylinder((trailer_center_x - tank_l * 0.36, 0, tank_z + tank_radius * 0.66), clamp(tank_radius * 0.08, 0.04, 0.09), tank_l * 0.18, "container_detail_prior", axis="x", segments=8)
    mesh.box((trailer_center_x, 0, tank_z + tank_radius * 0.90), (tank_l * 0.64, clamp(width * 0.075, 0.10, 0.22), clamp(height * 0.035, 0.06, 0.13)), "container_detail_prior")

    cab_axles = [
        cab_center_x - cab_l * 0.28,
        cab_center_x + cab_l * 0.28,
    ]
    trailer_axles = [
        trailer_center_x - trailer_l * 0.24,
        trailer_center_x + trailer_l * 0.20,
    ]
    axle_r = clamp(width * 0.018, 0.035, 0.065)
    connector_axles = cab_axles + trailer_axles[:1]
    for axle_x in cab_axles + trailer_axles:
        if axle_x in connector_axles:
            mesh.cylinder_between((axle_x, -wheel_y, wheel_z), (axle_x, wheel_y, wheel_z), axle_r, "vehicle_metal_prior", segments=8)
        for y in (-wheel_y, wheel_y):
            mesh.torus((axle_x, y, wheel_z), wheel_r, tire_minor, "vehicle_tire_prior", axis="y")
            mesh.cylinder((axle_x, y, wheel_z), wheel_r * 0.45, tire_minor * 1.25, "vehicle_metal_prior", axis="y", segments=8)


ANIMAL_MORPHOLOGY_PROFILES = {
    "generic_quadruped": {
        "body_l": 0.60,
        "body_w": 0.80,
        "body_h": 0.34,
        "body_x": -0.08,
        "leg_h": 0.42,
        "leg_r": 0.060,
        "head": 0.19,
        "head_forward": 0.62,
        "head_z": 0.24,
        "neck_r": 0.32,
        "muzzle": 0.46,
        "tail": 0.18,
        "hoof": False,
        "horns": "none",
        "markings": "none",
    },
    "bovine": {
        "body_l": 0.58,
        "body_w": 0.86,
        "body_h": 0.43,
        "body_x": -0.10,
        "leg_h": 0.37,
        "leg_r": 0.078,
        "head": 0.27,
        "head_forward": 0.28,
        "head_z": 0.27,
        "neck_r": 0.42,
        "muzzle": 0.58,
        "tail": 0.22,
        "hoof": True,
        "horns": "short_lateral",
        "markings": "patches",
    },
    "equine": {
        "body_l": 0.64,
        "body_w": 0.64,
        "body_h": 0.36,
        "body_x": -0.08,
        "leg_h": 0.50,
        "leg_r": 0.052,
        "head": 0.20,
        "head_forward": 0.52,
        "head_z": 0.34,
        "neck_r": 0.30,
        "muzzle": 0.54,
        "tail": 0.24,
        "hoof": True,
        "horns": "none",
        "markings": "none",
    },
    "canine": {
        "body_l": 0.58,
        "body_w": 0.62,
        "body_h": 0.32,
        "body_x": -0.08,
        "leg_h": 0.43,
        "leg_r": 0.050,
        "head": 0.22,
        "head_forward": 0.50,
        "head_z": 0.25,
        "neck_r": 0.30,
        "muzzle": 0.66,
        "tail": 0.26,
        "hoof": False,
        "horns": "none",
        "markings": "none",
    },
    "ovine": {
        "body_l": 0.56,
        "body_w": 0.82,
        "body_h": 0.42,
        "body_x": -0.08,
        "leg_h": 0.38,
        "leg_r": 0.055,
        "head": 0.21,
        "head_forward": 0.36,
        "head_z": 0.25,
        "neck_r": 0.36,
        "muzzle": 0.46,
        "tail": 0.08,
        "hoof": True,
        "horns": "none",
        "markings": "none",
    },
    "caprine": {
        "body_l": 0.57,
        "body_w": 0.68,
        "body_h": 0.36,
        "body_x": -0.08,
        "leg_h": 0.44,
        "leg_r": 0.050,
        "head": 0.20,
        "head_forward": 0.42,
        "head_z": 0.30,
        "neck_r": 0.30,
        "muzzle": 0.50,
        "tail": 0.12,
        "hoof": True,
        "horns": "short_upright",
        "markings": "none",
    },
    "cervid": {
        "body_l": 0.60,
        "body_w": 0.58,
        "body_h": 0.34,
        "body_x": -0.08,
        "leg_h": 0.52,
        "leg_r": 0.044,
        "head": 0.19,
        "head_forward": 0.44,
        "head_z": 0.32,
        "neck_r": 0.28,
        "muzzle": 0.48,
        "tail": 0.10,
        "hoof": True,
        "horns": "branch_hint",
        "markings": "none",
    },
}


def animal_quadruped_parametric(mesh, dims_m, profile_name="generic_quadruped"):
    profile = ANIMAL_MORPHOLOGY_PROFILES.get(profile_name, ANIMAL_MORPHOLOGY_PROFILES["generic_quadruped"])
    dims = dims_tuple(dims_m) or (2.2, 0.8, 1.4)
    length, width, height = dims
    half_l = length / 2.0

    body_l = clamp(length * profile["body_l"], length * 0.46, length * 0.72)
    body_w = clamp(width * profile["body_w"], width * 0.54, width * 0.96)
    body_h = clamp(height * profile["body_h"], height * 0.24, height * 0.54)
    leg_h = clamp(height * profile["leg_h"], height * 0.30, height * 0.60)
    body_x = length * profile["body_x"]
    body_z = leg_h + body_h * 0.52
    body_front = body_x + body_l / 2.0
    body_back = body_x - body_l / 2.0
    head_r = clamp(min(width, height) * profile["head"], 0.11, 0.40)
    head_x = min(half_l - head_r * 0.42, body_front + head_r * profile["head_forward"])
    head_z = min(height - head_r * 0.70, body_z + body_h * profile["head_z"])
    leg_r = clamp(width * profile["leg_r"], 0.030, 0.120)

    mesh.sphere((body_x, 0.0, body_z), (body_l / 2.0, body_w / 2.0, body_h / 2.0), "animal_body_prior")
    mesh.sphere((body_x - body_l * 0.02, 0.0, body_z - body_h * 0.30), (body_l * 0.36, body_w * 0.34, body_h * 0.18), "animal_body_prior")

    neck_start = (body_front - head_r * 0.34, 0.0, body_z + body_h * 0.14)
    neck_end = (head_x - head_r * 0.42, 0.0, head_z - head_r * 0.10)
    mesh.cylinder_between(neck_start, neck_end, head_r * profile["neck_r"], "animal_body_prior", segments=10)
    mesh.sphere((body_front - head_r * 0.08, 0.0, body_z + body_h * 0.10), (head_r * 0.58, head_r * 0.58, head_r * 0.48), "animal_body_prior")
    mesh.sphere((head_x, 0.0, head_z), (head_r * 1.05, head_r * 0.84, head_r * 0.80), "animal_body_prior")

    muzzle_x = min(half_l - head_r * 0.18, head_x + head_r * profile["muzzle"])
    muzzle_z = head_z - head_r * 0.23
    mesh.sphere((muzzle_x, 0.0, muzzle_z), (head_r * 0.50, head_r * 0.46, head_r * 0.32), "animal_skin_prior")

    leg_xs = (body_back + body_l * 0.18, body_front - body_l * 0.18)
    leg_ys = (-body_w * 0.40, body_w * 0.40)
    leg_top_z = min(body_z - body_h * 0.05, leg_h + body_h * 0.22)
    leg_len = max(leg_h, leg_top_z)
    socket_z = leg_top_z - leg_r * 0.12
    socket_scale = (leg_r * 1.65, leg_r * 1.45, max(leg_r * 1.18, body_h * 0.075))
    shoulder_z = body_z - body_h * 0.22
    for x in leg_xs:
        for y in leg_ys:
            mesh.cylinder((x, y, leg_len / 2.0), leg_r, leg_len, "animal_limb_prior", axis="z", segments=8)
            mesh.sphere((x, y, socket_z), socket_scale, "animal_limb_prior")
            mesh.cylinder_between(
                (x, y, leg_top_z - leg_r * 0.20),
                (x, y * 0.68, shoulder_z),
                leg_r * 0.72,
                "animal_limb_prior",
                segments=6,
            )
            if profile.get("hoof"):
                mesh.box((x, y, 0.045), (leg_r * 2.30, leg_r * 2.10, 0.09), "animal_limb_prior")

    tail_len = clamp(length * profile["tail"], 0.10, length * 0.32)
    if tail_len > 0.11:
        tail_start = (body_back + length * 0.04, 0.0, body_z + body_h * 0.04)
        tail_end = (body_back - tail_len, 0.0, body_z - body_h * 0.18)
        mesh.cylinder_between(tail_start, tail_end, clamp(width * 0.022, 0.016, 0.038), "animal_limb_prior", segments=8)

    if profile.get("markings") == "patches":
        for x, y, z, sx, sy, sz in (
            (body_x - body_l * 0.24, -body_w * 0.25, body_z + body_h * 0.24, body_l * 0.14, body_w * 0.18, body_h * 0.16),
            (body_x + body_l * 0.12, body_w * 0.29, body_z + body_h * 0.02, body_l * 0.12, body_w * 0.15, body_h * 0.14),
            (body_x - body_l * 0.34, body_w * 0.16, body_z + body_h * 0.30, body_l * 0.10, body_w * 0.13, body_h * 0.14),
            (body_x + body_l * 0.30, -body_w * 0.34, body_z + body_h * 0.16, body_l * 0.10, body_w * 0.12, body_h * 0.15),
        ):
            mesh.sphere((x, y, z), (sx, sy, sz), "animal_marking_prior")

    horns = profile.get("horns")
    if horns and horns != "none":
        horn_z = min(height, head_z + head_r * 0.86)
        for side in (-1.0, 1.0):
            if horns == "short_lateral":
                base = (head_x - head_r * 0.06, side * head_r * 0.46, horn_z - head_r * 0.10)
                tip = (head_x + head_r * 0.08, side * head_r * 0.96, horn_z + head_r * 0.04)
                radius = clamp(head_r * 0.09, 0.016, 0.034)
            elif horns == "short_upright":
                base = (head_x - head_r * 0.10, side * head_r * 0.38, horn_z - head_r * 0.14)
                tip = (head_x - head_r * 0.04, side * head_r * 0.50, horn_z + head_r * 0.30)
                radius = clamp(head_r * 0.075, 0.014, 0.030)
            else:
                base = (head_x - head_r * 0.08, side * head_r * 0.38, horn_z - head_r * 0.12)
                tip = (head_x - head_r * 0.15, side * head_r * 0.68, horn_z + head_r * 0.36)
                radius = clamp(head_r * 0.060, 0.012, 0.025)
            mesh.cylinder_between(base, tip, radius, "animal_skin_prior", segments=6)


def quadruped_parametric(mesh, dims_m):
    animal_quadruped_parametric(mesh, dims_m, "generic_quadruped")


def cow_parametric(mesh, dims_m):
    animal_quadruped_parametric(mesh, dims_m, "bovine")


def horse_parametric(mesh, dims_m):
    animal_quadruped_parametric(mesh, dims_m, "equine")


def dog_parametric(mesh, dims_m):
    animal_quadruped_parametric(mesh, dims_m, "canine")


def sheep_parametric(mesh, dims_m):
    animal_quadruped_parametric(mesh, dims_m, "ovine")


def goat_parametric(mesh, dims_m):
    animal_quadruped_parametric(mesh, dims_m, "caprine")


def deer_parametric(mesh, dims_m):
    animal_quadruped_parametric(mesh, dims_m, "cervid")


def tree_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m)
    if not dims:
        return tree(mesh)
    length, width, height = dims
    canopy_w = max(length, width)
    trunk_h = clamp(height * 0.48, 0.65, height * 0.70)
    trunk_r = clamp(canopy_w * 0.08, 0.08, 0.28)
    canopy_z = trunk_h + (height - trunk_h) * 0.46
    canopy_h = max(0.35, height - trunk_h * 0.70)
    mesh.cylinder((0, 0, trunk_h / 2.0), trunk_r, trunk_h, "vegetation_trunk_prior", segments=12)
    mesh.sphere((0, 0, canopy_z), (length * 0.44, width * 0.44, canopy_h * 0.38), "vegetation_canopy_dark_prior")
    mesh.sphere((-length * 0.18, width * 0.08, canopy_z + canopy_h * 0.18), (length * 0.30, width * 0.28, canopy_h * 0.28), "vegetation_canopy_light_prior")
    mesh.sphere((length * 0.18, -width * 0.08, canopy_z + canopy_h * 0.16), (length * 0.30, width * 0.28, canopy_h * 0.28), "vegetation_canopy_light_prior")


def bush_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m)
    if not dims:
        return bush(mesh)
    length, width, height = dims
    z = height * 0.45
    mesh.sphere((0, 0, z), (length * 0.42, width * 0.40, height * 0.36), "vegetation_canopy_dark_prior")
    mesh.sphere((-length * 0.24, width * 0.06, z + height * 0.05), (length * 0.30, width * 0.30, height * 0.28), "vegetation_canopy_light_prior")
    mesh.sphere((length * 0.24, -width * 0.06, z + height * 0.04), (length * 0.30, width * 0.30, height * 0.28), "vegetation_canopy_light_prior")
    mesh.cylinder((0, 0, height * 0.18), clamp(min(length, width) * 0.06, 0.04, 0.16), height * 0.36, "vegetation_trunk_prior", segments=8)


def tower_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m)
    if not dims:
        return tower(mesh)
    length, width, height = dims
    mast_r = clamp(min(length, width) * 0.026, 0.035, 0.12)
    brace_r = clamp(mast_r * 0.55, 0.020, 0.070)
    arm_r = clamp(mast_r * 0.72, 0.026, 0.085)
    base_x = max(length * 0.28, mast_r * 4.0)
    base_y = max(width * 0.24, mast_r * 3.0)
    waist_x = max(length * 0.16, mast_r * 2.7)
    waist_y = max(width * 0.15, mast_r * 2.2)
    top_x = max(length * 0.050, mast_r * 1.25)
    top_y = max(width * 0.045, mast_r * 1.10)
    leg_top_z = height * 0.88

    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            mesh.cylinder_between(
                (sx * base_x, sy * base_y, 0.0),
                (sx * top_x, sy * top_y, leg_top_z),
                mast_r,
                "structure_metal_prior",
                segments=8,
            )

    levels = [0.20, 0.55, 0.88]
    for index in range(len(levels) - 1):
        z0 = height * levels[index]
        z1 = height * levels[index + 1]
        x0 = base_x + (top_x - base_x) * levels[index] / 0.88
        y0 = base_y + (top_y - base_y) * levels[index] / 0.88
        x1 = base_x + (top_x - base_x) * levels[index + 1] / 0.88
        y1 = base_y + (top_y - base_y) * levels[index + 1] / 0.88
        for sy in (-1.0, 1.0):
            mesh.cylinder_between((-x0, sy * y0, z0), (x1, sy * y1, z1), brace_r, "structure_metal_prior", segments=6)
            mesh.cylinder_between((x0, sy * y0, z0), (-x1, sy * y1, z1), brace_r, "structure_metal_prior", segments=6)

    top_arm_l = max(length, 0.45)
    mid_arm_l = max(length * 0.72, 0.35)
    side_arm_l = max(width, 0.45)
    top_z = height * 0.86
    mid_z = height * 0.68
    side_z = height * 0.78
    mesh.cylinder_between((-top_arm_l * 0.55, 0.0, top_z), (top_arm_l * 0.55, 0.0, top_z), arm_r, "structure_metal_prior", segments=8)
    mesh.cylinder_between((-mid_arm_l * 0.50, 0.0, mid_z), (mid_arm_l * 0.50, 0.0, mid_z), arm_r * 0.85, "structure_metal_prior", segments=8)
    mesh.cylinder_between((0.0, -side_arm_l * 0.48, side_z), (0.0, side_arm_l * 0.48, side_z), arm_r * 0.85, "structure_metal_prior", segments=8)
    for sx in (-1.0, 1.0):
        mesh.cylinder_between((0.0, 0.0, mid_z), (sx * top_arm_l * 0.48, 0.0, top_z), brace_r, "structure_metal_prior", segments=6)


def unknown_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m)
    if not dims:
        return unknown_proxy(mesh)
    length, width, height = dims
    footprint_h = clamp(height * 0.05, 0.08, 0.22)
    volume_h = max(0.10, height - footprint_h)
    marker_h = clamp(height * 0.18, 0.22, 0.55)
    mesh.box((0, 0, footprint_h / 2.0), (length, width, footprint_h), "unknown_footprint_fallback")
    mesh.box((0, 0, footprint_h + volume_h / 2.0), (length, width, volume_h), "unknown_volume_fallback")
    mesh.cone((0, 0, height - marker_h / 2.0), min(length, width) * 0.18, marker_h, "uncertainty_marker_fallback", segments=12)


def built_structure_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m)
    if not dims:
        dims = (8.0, 6.0, 4.5)
    length, width, height = dims
    low_profile = height < 2.6 or min(length, width) < 0.7

    if low_profile:
        deck_h = clamp(height * 0.32, 0.18, max(0.2, height * 0.75))
        mesh.box((0, 0, deck_h / 2.0), (length, width, deck_h), "built_structure_body_prior")
        rail_h = clamp(height * 0.22, 0.12, 0.45)
        rail_z = deck_h + rail_h / 2.0
        rail_w = clamp(min(width, length) * 0.06, 0.04, 0.18)
        mesh.box((0, -width / 2.0 + rail_w / 2.0, rail_z), (length, rail_w, rail_h), "built_structure_roof_prior")
        mesh.box((0, width / 2.0 - rail_w / 2.0, rail_z), (length, rail_w, rail_h), "built_structure_roof_prior")
        return

    body_h = clamp(height * 0.78, 1.0, height)
    roof_h = max(0.0, height - body_h)
    mesh.box((0, 0, body_h / 2.0), (length, width, body_h), "built_structure_body_prior")
    if roof_h > 0.05:
        mesh.box((0, 0, body_h + roof_h / 2.0), (length * 1.06, width * 1.06, roof_h), "built_structure_roof_prior")

    window_h = clamp(body_h * 0.16, 0.25, 0.65)
    window_w = clamp(length * 0.12, 0.35, 1.2)
    z = clamp(body_h * 0.55, window_h, body_h - window_h * 0.5)
    for x_frac in (-0.28, 0.0, 0.28):
        x = length * x_frac
        mesh.box((x, -width / 2.0 - 0.01, z), (window_w, 0.035, window_h), "built_structure_window_prior")
        mesh.box((x, width / 2.0 + 0.01, z), (window_w, 0.035, window_h), "built_structure_window_prior")


def forklift_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m) or (3.2, 1.35, 2.2)
    length, width, height = dims
    half_l = length / 2.0
    wheel_r = clamp(height * 0.12, 0.16, 0.28)
    tire_minor = clamp(wheel_r * 0.24, 0.04, 0.07)
    wheel_y = max(0.0, width / 2.0 - tire_minor)
    wheel_z = wheel_r + tire_minor
    body_h = clamp(height * 0.26, 0.36, 0.62)
    body_z = wheel_z + body_h / 2.0
    body_l = length * 0.46
    body_x = -length * 0.12
    cab_h = clamp(height * 0.44, 0.70, 1.10)
    cab_z = body_z + body_h / 2.0 + cab_h / 2.0
    cab_l = length * 0.24
    cab_x = body_x + body_l * 0.18
    mast_x = half_l - length * 0.16
    mast_h = max(height * 0.78, 1.25)
    mast_r = clamp(width * 0.025, 0.025, 0.05)
    fork_z = clamp(height * 0.18, 0.18, 0.35)

    mesh.box((body_x, 0, body_z), (body_l, width * 0.74, body_h), "vehicle_body_prior")
    mesh.box((cab_x, 0, cab_z), (cab_l, width * 0.68, cab_h), "vehicle_cab_prior")
    mesh.box((cab_x, -width * 0.34 - 0.01, cab_z + cab_h * 0.08), (cab_l * 0.72, 0.035, cab_h * 0.46), "vehicle_window_prior")
    mesh.box((cab_x, width * 0.34 + 0.01, cab_z + cab_h * 0.08), (cab_l * 0.72, 0.035, cab_h * 0.46), "vehicle_window_prior")
    for y in (-width * 0.25, width * 0.25):
        mesh.cylinder((mast_x, y, mast_h / 2.0), mast_r, mast_h, "vehicle_attachment_prior", axis="z", segments=8)
        mesh.box((mast_x + length * 0.18, y, fork_z), (length * 0.36, width * 0.045, height * 0.045), "vehicle_attachment_prior")
    for x in (-length * 0.33, length * 0.22):
        for y in (-wheel_y, wheel_y):
            mesh.torus((x, y, wheel_z), wheel_r, tire_minor, "vehicle_tire_prior", axis="y")
            mesh.cylinder((x, y, wheel_z), wheel_r * 0.44, tire_minor * 1.25, "vehicle_metal_prior", axis="y", segments=8)


def traffic_cone_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m) or (0.55, 0.55, 0.75)
    length, width, height = dims
    base_h = clamp(height * 0.10, 0.045, 0.11)
    cone_h = max(0.12, height - base_h)
    radius = max(min(length, width) * 0.34, 0.07)
    mesh.box((0, 0, base_h / 2.0), (length, width, base_h), "container_detail_prior")
    mesh.cone((0, 0, base_h + cone_h / 2.0), radius, cone_h, "safety_marker_prior", segments=18)
    band_h = clamp(height * 0.055, 0.035, 0.07)
    mesh.cylinder((0, 0, base_h + cone_h * 0.48), radius * 0.46, band_h, "white", axis="z", segments=18)


def water_tank_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m) or (3.0, 1.4, 1.6)
    length, width, height = dims
    radius = clamp(min(width, height) * 0.38, 0.18, max(0.20, min(width, height) * 0.48))
    center_z = max(radius + height * 0.12, height * 0.52)
    mesh.cylinder((0, 0, center_z), radius, max(0.2, length * 0.84), "container_body_prior", axis="x", segments=18)
    for x in (-length * 0.26, length * 0.26):
        mesh.box((x, -width * 0.23, center_z - radius * 0.85), (length * 0.05, width * 0.08, max(0.08, height * 0.34)), "container_detail_prior")
        mesh.box((x, width * 0.23, center_z - radius * 0.85), (length * 0.05, width * 0.08, max(0.08, height * 0.34)), "container_detail_prior")
    mesh.cylinder((length * 0.12, 0, min(height, center_z + radius * 0.78)), radius * 0.14, height * 0.12, "container_detail_prior", axis="z", segments=12)


def barrel_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m) or (0.70, 0.70, 1.0)
    length, width, height = dims
    radius = max(min(length, width) * 0.42, 0.12)
    mesh.cylinder((0, 0, height / 2.0), radius, height, "container_body_prior", axis="z", segments=18)
    band_h = clamp(height * 0.045, 0.035, 0.07)
    for z in (height * 0.22, height * 0.50, height * 0.78):
        mesh.cylinder((0, 0, z), radius * 1.03, band_h, "container_detail_prior", axis="z", segments=18)


def shipping_container_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m) or (12.2, 2.45, 2.6)
    length, width, height = dims
    mesh.box((0, 0, height / 2.0), (length, width, height), "container_body_prior")
    rib_w = clamp(length * 0.012, 0.05, 0.12)
    rib_count = max(5, min(12, int(length / max(width * 0.45, 0.5))))
    for i in range(rib_count):
        x = -length * 0.44 + i * (length * 0.88 / max(1, rib_count - 1))
        mesh.box((x, -width / 2.0 - 0.01, height / 2.0), (rib_w, 0.035, height * 0.88), "container_detail_prior")
        mesh.box((x, width / 2.0 + 0.01, height / 2.0), (rib_w, 0.035, height * 0.88), "container_detail_prior")
    mesh.box((length * 0.47, 0, height * 0.52), (0.04, width * 0.86, height * 0.84), "container_detail_prior")


def quadcopter_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m) or (0.90, 0.90, 0.22)
    length, width, height = dims
    body_l = clamp(length * 0.26, 0.16, 0.34)
    body_w = clamp(width * 0.20, 0.12, 0.30)
    body_h = clamp(height * 0.42, 0.07, 0.16)
    z = max(height * 0.52, body_h)
    arm_r = clamp(min(length, width) * 0.018, 0.012, 0.030)
    rotor_r = clamp(min(length, width) * 0.12, 0.07, 0.18)
    rotor_z = z + body_h * 0.32
    mesh.box((0, 0, z), (body_l, body_w, body_h), "aircraft_body_prior")
    mesh.cylinder((0, 0, z), arm_r, max(0.12, length * 0.76), "aircraft_body_prior", axis="x", segments=8)
    mesh.cylinder((0, 0, z), arm_r, max(0.12, width * 0.76), "aircraft_body_prior", axis="y", segments=8)
    for y in (-width * 0.38, width * 0.38):
        mesh.cylinder((0, y, z), arm_r, max(0.12, length * 0.76), "aircraft_body_prior", axis="x", segments=8)
    for x in (-length * 0.38, length * 0.38):
        mesh.cylinder((x, 0, z), arm_r, max(0.12, width * 0.76), "aircraft_body_prior", axis="y", segments=8)
    for x in (-length * 0.38, length * 0.38):
        for y in (-width * 0.38, width * 0.38):
            mesh.torus((x, y, rotor_z), rotor_r, max(rotor_r * 0.07, 0.008), "aircraft_rotor_prior", axis="z")
            mesh.box((x, y, rotor_z), (rotor_r * 1.75, max(rotor_r * 0.08, 0.012), max(height * 0.025, 0.006)), "aircraft_rotor_prior")


def hay_bale_parametric(mesh, dims_m):
    dims = dims_tuple(dims_m) or (1.50, 1.50, 1.20)
    length, width, height = dims
    radius = max(min(width, height) * 0.42, 0.18)
    mesh.cylinder((0, 0, height * 0.50), radius, max(0.2, length * 0.92), "agricultural_bale_prior", axis="x", segments=18)
    for x in (-length * 0.24, length * 0.24):
        mesh.cylinder((x, 0, height * 0.50), radius * 1.01, clamp(length * 0.025, 0.025, 0.06), "agricultural_binding_prior", axis="x", segments=18)


def forklift(mesh):
    forklift_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["forklift"])


def traffic_cone(mesh):
    traffic_cone_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["traffic_cone"])


def water_tank(mesh):
    water_tank_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["water_tank"])


def barrel(mesh):
    barrel_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["barrel"])


def shipping_container(mesh):
    shipping_container_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["shipping_container"])


def quadcopter(mesh):
    quadcopter_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["quadcopter"])


def hay_bale(mesh):
    hay_bale_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["hay_bale"])


def built_structure(mesh):
    built_structure_parametric(mesh, {"length": 8.0, "width": 6.0, "height": 4.5})


def tractor(mesh):
    mesh.box((-0.15, 0, 0.85), (1.45, 1.0, 0.65), 'vehicle_farm_body_prior')
    mesh.box((0.85, 0, 1.18), (0.72, 0.85, 0.8), 'vehicle_farm_body_prior')
    mesh.box((0.92, -0.43, 1.28), (0.42, 0.04, 0.32), 'vehicle_window_prior')
    mesh.box((0.92, 0.43, 1.28), (0.42, 0.04, 0.32), 'vehicle_window_prior')
    mesh.box((-1.05, 0, 1.05), (0.65, 0.75, 0.45), 'vehicle_attachment_prior')
    mesh.cylinder_between((-0.75, -0.58, 0.58), (-0.75, 0.58, 0.58), 0.04, 'vehicle_metal_prior', segments=8)
    mesh.cylinder_between((0.85, -0.58, 0.48), (0.85, 0.58, 0.48), 0.035, 'vehicle_metal_prior', segments=8)
    for y in (-0.58, 0.58):
        mesh.torus((-0.75, y, 0.58), 0.40, 0.10, 'vehicle_tire_prior', axis='y')
        mesh.cylinder((-0.75, y, 0.58), 0.18, 0.10, 'vehicle_attachment_prior', axis='y')
        mesh.torus((0.85, y, 0.48), 0.28, 0.08, 'vehicle_tire_prior', axis='y')
        mesh.cylinder((0.85, y, 0.48), 0.12, 0.08, 'vehicle_attachment_prior', axis='y')
    mesh.cylinder((-0.2, 0, 1.45), 0.07, 0.75, 'vehicle_tire_prior', axis='z')


def tractor_trailer(mesh):
    tractor_trailer_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["tractor_trailer"])


def articulated_vehicle(mesh):
    articulated_vehicle_parametric(mesh, DEFAULT_ARCHETYPE_DIMS_M["articulated_vehicle"])


def biker(mesh):
    for x in (-0.85, 0.85):
        mesh.torus((x, 0, 0.55), 0.38, 0.045, "vehicle_tire_prior", axis="y")
        mesh.cylinder((x, 0, 0.55), 0.08, 0.08, "vehicle_metal_prior", axis="y")
    mesh.cylinder((0, 0, 0.78), 0.035, 1.25, "bike_frame_prior", axis="x")
    mesh.cylinder((-0.45, 0, 0.95), 0.035, 0.95, "bike_frame_prior", axis="x")
    mesh.cylinder((0.45, 0, 0.95), 0.035, 0.95, "bike_frame_prior", axis="x")
    mesh.cylinder((0.0, 0, 1.0), 0.04, 0.75, "vehicle_metal_prior", axis="z")
    mesh.sphere((0.0, 0, 1.65), (0.28, 0.20, 0.45), "rider_clothing_prior")
    mesh.sphere((0.12, 0, 2.12), (0.18, 0.18, 0.18), "rider_skin_prior")
    mesh.cylinder((-0.18, 0, 1.28), 0.045, 0.82, "rider_skin_prior", axis="z")
    mesh.cylinder((0.35, 0, 1.25), 0.045, 0.82, "rider_skin_prior", axis="z")
    mesh.cylinder((0.35, 0, 1.72), 0.04, 0.72, "rider_skin_prior", axis="x")

def tower(mesh):
    mesh.cylinder((0, 0, 2.0), 0.16, 4.0, 'structure_metal_prior', segments=12)
    mesh.box((0, 0, 3.8), (1.7, 0.12, 0.12), 'structure_metal_prior')
    mesh.box((0, 0, 2.8), (1.2, 0.10, 0.10), 'structure_metal_prior')
    mesh.cone((0, 0, 4.35), 0.35, 0.55, 'structure_metal_prior', segments=12)

def unknown_proxy(mesh):
    mesh.cylinder((0, 0, 0.08), 0.70, 0.16, 'unknown_footprint_fallback', segments=16)
    mesh.box((0, 0, 0.82), (1.15, 1.15, 1.30), 'unknown_volume_fallback')
    mesh.cone((0, 0, 1.62), 0.42, 0.55, 'uncertainty_marker_fallback', segments=12)

BUILDERS = {
    'cow': cow,
    'vaca': cow,
    'animal': quadruped_generic,
    'dog': dog,
    'horse': horse,
    'sheep': sheep,
    'goat': goat,
    'deer': deer,
    'bull': bull,
    'cattle': cattle,
    'person': person,
    'pedestrian': person,
    'human': person,
    'bicycle': bicycle,
    'bike': bicycle,
    'biker': biker,
    'two_wheeled_rider': biker,
    'cyclist': biker,
    'ciclista': biker,
    'rider': biker,
    'motorcycle': motorcycle,
    'motorbike': motorcycle,
    'tree': tree,
    'arbol': tree,
    'bush': bush,
    'arbusto': bush,
    'car': car,
    'coche': car,
    'van': van,
    'furgoneta': van,
    'pickup': pickup,
    'suv': car,
    'light_vehicle': car,
    'bus': bus,
    'truck': truck,
    'camion': truck,
    'heavy_vehicle': truck,
    'generic_vehicle': truck,
    'tractor': tractor,
    'tractor_trailer': tractor_trailer,
    'tractor+trailer': tractor_trailer,
    'tractor trailer': tractor_trailer,
    'tractor_with_trailer': tractor_trailer,
    'articulated_vehicle': articulated_vehicle,
    'vehicle_with_trailer': articulated_vehicle,
    'farm_vehicle': tractor,
    'quadruped': quadruped_generic,
    'tower': tower,
    'vertical_structure': tower,
    'power_tower': tower,
    'pole': tower,
    'mast': tower,
    'pylon': tower,
    'vegetation': tree,
    'building': built_structure,
    'house': built_structure,
    'shed': built_structure,
    'barn': built_structure,
    'warehouse': built_structure,
    'bridge': built_structure,
    'wall': built_structure,
    'fence': built_structure,
    'built_structure': built_structure,
    'unknown': unknown_proxy,
}

CANONICAL_ARCHETYPES = {
    'vaca': 'cow',
    'animal': 'quadruped',
    'dog': 'dog',
    'horse': 'horse',
    'sheep': 'sheep',
    'goat': 'goat',
    'deer': 'deer',
    'bull': 'bull',
    'cattle': 'cow',
    'pedestrian': 'person',
    'human': 'person',
    'bike': 'bicycle',
    'two_wheeled_rider': 'biker',
    'cyclist': 'biker',
    'ciclista': 'biker',
    'rider': 'biker',
    'motorbike': 'motorcycle',
    'arbol': 'tree',
    'arbusto': 'bush',
    'coche': 'car',
    'furgoneta': 'van',
    'suv': 'light_vehicle',
    'camion': 'truck',
    'light_vehicle': 'light_vehicle',
    'heavy_vehicle': 'heavy_vehicle',
    'generic_vehicle': 'heavy_vehicle',
    'tractor_trailer': 'tractor_trailer',
    'tractor+trailer': 'tractor_trailer',
    'tractor trailer': 'tractor_trailer',
    'tractor_with_trailer': 'tractor_trailer',
    'articulated_vehicle': 'articulated_vehicle',
    'vehicle_with_trailer': 'articulated_vehicle',
    'articulated vehicle': 'articulated_vehicle',
    'vehicle with trailer': 'articulated_vehicle',
    'farm_vehicle': 'farm_vehicle',
    'quadruped': 'quadruped',
    'vegetation': 'vegetation',
    'vertical_structure': 'vertical_structure',
    'power_tower': 'vertical_structure',
    'pole': 'vertical_structure',
    'mast': 'vertical_structure',
    'pylon': 'vertical_structure',
    'building': 'built_structure',
    'house': 'built_structure',
    'shed': 'built_structure',
    'barn': 'built_structure',
    'warehouse': 'built_structure',
    'bridge': 'built_structure',
    'wall': 'built_structure',
    'fence': 'built_structure',
    'built_structure': 'built_structure',
}

PARAMETRIC_BUILDERS = {
    'unknown': unknown_parametric,
    'person': person_parametric,
    'pedestrian': person_parametric,
    'human': person_parametric,
    'bicycle': bicycle_parametric,
    'bike': bicycle_parametric,
    'biker': biker_parametric,
    'two_wheeled_rider': biker_parametric,
    'cyclist': biker_parametric,
    'rider': biker_parametric,
    'motorcycle': motorcycle_parametric,
    'motorbike': motorcycle_parametric,
    'car': car_parametric,
    'coche': car_parametric,
    'light_vehicle': car_parametric,
    'van': van_parametric,
    'pickup': pickup_parametric,
    'bus': bus_parametric,
    'truck': truck_parametric,
    'camion': truck_parametric,
    'heavy_vehicle': truck_parametric,
    'generic_vehicle': truck_parametric,
    'tractor': tractor_parametric,
    'tractor_trailer': tractor_trailer_parametric,
    'tractor+trailer': tractor_trailer_parametric,
    'tractor trailer': tractor_trailer_parametric,
    'tractor_with_trailer': tractor_trailer_parametric,
    'articulated_vehicle': articulated_vehicle_parametric,
    'vehicle_with_trailer': articulated_vehicle_parametric,
    'articulated vehicle': articulated_vehicle_parametric,
    'vehicle with trailer': articulated_vehicle_parametric,
    'farm_vehicle': tractor_parametric,
    'cow': cow_parametric,
    'quadruped': quadruped_parametric,
    'animal': quadruped_parametric,
    'dog': dog_parametric,
    'horse': horse_parametric,
    'sheep': sheep_parametric,
    'goat': goat_parametric,
    'deer': deer_parametric,
    'bull': cow_parametric,
    'cattle': cow_parametric,
    'vaca': cow_parametric,
    'tree': tree_parametric,
    'vegetation': tree_parametric,
    'bush': bush_parametric,
    'tower': tower_parametric,
    'power_tower': tower_parametric,
    'pole': tower_parametric,
    'mast': tower_parametric,
    'pylon': tower_parametric,
    'vertical_structure': tower_parametric,
    'building': built_structure_parametric,
    'house': built_structure_parametric,
    'shed': built_structure_parametric,
    'barn': built_structure_parametric,
    'warehouse': built_structure_parametric,
    'bridge': built_structure_parametric,
    'wall': built_structure_parametric,
    'fence': built_structure_parametric,
    'built_structure': built_structure_parametric,
}

ARCHETYPE_RULES = [
    ('pickup', pickup, ('pickup', 'ute')),
    ('articulated_vehicle', articulated_vehicle, ('articulated vehicle', 'vehicle with trailer', 'tanker truck', 'semi trailer')),
    ('tractor_trailer', tractor_trailer, ('tractor trailer', 'tractor with trailer', 'tractor pulling trailer', 'tractor+trailer')),
    ('heavy_vehicle', truck, ('truck', 'lorry', 'trailer', 'semi', 'excavator', 'bulldozer', 'loader')),
    ('bus', bus, ('bus', 'coach', 'minibus')),
    ('van', van, ('van', 'furgoneta', 'ambulance')),
    ('farm_vehicle', tractor, ('tractor', 'harvester', 'farm', 'agricultural')),
    ('light_vehicle', car, ('car', 'vehicle', 'suv', 'taxi')),
    ('built_structure', built_structure, ('building', 'house', 'shed', 'barn', 'warehouse', 'bridge', 'wall', 'fence', 'roof', 'structure')),
    ('vertical_structure', tower, ('tower', 'pole', 'mast', 'pylon', 'post', 'sign', 'antenna', 'crane')),
    ('motorcycle', motorcycle, ('motorcycle', 'motorbike', 'moped', 'scooter')),
    ('biker', biker, ('biker', 'cyclist', 'rider')),
    ('bicycle', bicycle, ('bicycle', 'bike', 'cycle')),
    ('person', person, ('person', 'pedestrian', 'human', 'worker')),
    ('cow', cow, ('cow', 'cattle', 'bovine')),
    ('bull', bull, ('bull',)),
    ('horse', horse, ('horse', 'equine')),
    ('dog', dog, ('dog', 'canine')),
    ('sheep', sheep, ('sheep', 'ovine')),
    ('goat', goat, ('goat', 'caprine')),
    ('deer', deer, ('deer', 'cervid')),
    ('quadruped', quadruped_generic, ('animal', 'quadruped', 'livestock', 'mammal', 'giraffe', 'zebra', 'elephant')),
    ('vegetation', tree, ('tree', 'plant', 'vegetation', 'canopy', 'trunk')),
    ('bush', bush, ('bush', 'shrub', 'hedge')),
]

OPEN_LABEL_RECIPE_VERSION = "SPPA-OPEN-LABEL-RECIPES-0.1"
OPEN_LABEL_VERIFIER_VERSION = "SPPA-OPEN-LABEL-VERIFY-0.1"
OPEN_LABEL_RECIPE_STATUS = "open_label_candidate_recipe"
OPEN_LABEL_VERIFIED_STATUS = "open_label_verified_recipe"
OPEN_LABEL_REJECTED_STATUS = "fallback_open_label_recipe_rejected"

OPEN_LABEL_BUILDERS = {
    "forklift": forklift,
    "traffic_cone": traffic_cone,
    "water_tank": water_tank,
    "barrel": barrel,
    "shipping_container": shipping_container,
    "quadcopter": quadcopter,
    "hay_bale": hay_bale,
}

OPEN_LABEL_PARAMETRIC_BUILDERS = {
    "forklift": forklift_parametric,
    "traffic_cone": traffic_cone_parametric,
    "water_tank": water_tank_parametric,
    "barrel": barrel_parametric,
    "shipping_container": shipping_container_parametric,
    "quadcopter": quadcopter_parametric,
    "drone": quadcopter_parametric,
    "hay_bale": hay_bale_parametric,
}

OPEN_LABEL_RULES = [
    ("forklift", forklift, ("forklift", "fork lift")),
    ("traffic_cone", traffic_cone, ("traffic cone", "road cone")),
    ("water_tank", water_tank, ("water tank", "storage tank")),
    ("barrel", barrel, ("barrel", "drum")),
    ("shipping_container", shipping_container, ("shipping container", "cargo container", "freight container")),
    ("quadcopter", quadcopter, ("quadcopter", "drone", "uav")),
    ("hay_bale", hay_bale, ("hay bale", "bale of hay")),
]

OPEN_LABEL_RECIPE_CONTRACTS = {
    "forklift": {
        "required_roles": {"vehicle_body", "vehicle_cab", "vehicle_tire", "vehicle_attachment"},
        "max_triangles": 1800,
        "min_parts": 8,
    },
    "traffic_cone": {
        "required_roles": {"safety_marker", "container_detail"},
        "max_triangles": 350,
        "min_parts": 2,
    },
    "water_tank": {
        "required_roles": {"container_body", "container_detail"},
        "max_triangles": 600,
        "min_parts": 3,
    },
    "barrel": {
        "required_roles": {"container_body", "container_detail"},
        "max_triangles": 700,
        "min_parts": 3,
    },
    "shipping_container": {
        "required_roles": {"container_body", "container_detail"},
        "max_triangles": 600,
        "min_parts": 5,
    },
    "quadcopter": {
        "required_roles": {"aircraft_body", "aircraft_rotor"},
        "max_triangles": 1800,
        "min_parts": 7,
    },
    "hay_bale": {
        "required_roles": {"agricultural_bale", "agricultural_binding"},
        "max_triangles": 700,
        "min_parts": 2,
    },
}

VISUAL_ARTIFACT_CONTEXT_TOKENS = {
    "drawing",
    "icon",
    "image",
    "logo",
    "model",
    "painting",
    "photo",
    "picture",
    "poster",
    "print",
    "printed",
    "reflection",
    "shadow",
    "silhouette",
    "statue",
    "sticker",
    "toy",
}

NON_PERSON_EQUIPMENT_TOKENS = {
    "boot",
    "glove",
    "hardhat",
    "hat",
    "helmet",
    "shoe",
    "vest",
}


def _tokens(label):
    return set(re.findall(r'[a-z0-9]+', label.lower()))


def forced_fallback_reason(tokens):
    if tokens & VISUAL_ARTIFACT_CONTEXT_TOKENS:
        return "fallback_visual_artifact_context"
    if (tokens & NON_PERSON_EQUIPMENT_TOKENS) and not (tokens & {"person", "human", "pedestrian"}):
        return "fallback_object_part_or_equipment_context"
    return None


def _open_label_rule_matches(key, tokens, keywords):
    phrase_key = key.replace("_", " ").replace("-", " ")
    for keyword in keywords:
        if " " in keyword:
            if keyword in key or keyword in phrase_key:
                return True
        elif keyword in tokens:
            return True
    return False


def resolve_open_label_recipe(key, tokens):
    for archetype, builder, keywords in OPEN_LABEL_RULES:
        if _open_label_rule_matches(key, tokens, keywords):
            return builder, archetype, OPEN_LABEL_RECIPE_STATUS
    return None


def _mesh_roles(mesh):
    roles = set()
    for part in getattr(mesh, "parts", []):
        role = str(part.get("role") or part.get("material_role") or "")
        if role:
            roles.add(role)
    return roles


def replace_mesh(target, source):
    target.vertices = list(source.vertices)
    target.faces = list(source.faces)
    target.parts = [dict(part) for part in source.parts]


def verify_open_label_proxy(label, archetype, mesh, dims_m=None):
    contract = OPEN_LABEL_RECIPE_CONTRACTS.get(str(archetype or ""))
    roles = _mesh_roles(mesh)
    triangles = mesh_triangle_count(mesh)
    failures = []
    if not contract:
        failures.append("missing_recipe_contract")
        required_roles = set()
        max_triangles = DEFAULT_GEOMETRY_FITTING_LIMITS["triangle_budget_soft"]
        min_parts = 1
    else:
        required_roles = set(contract.get("required_roles", set()))
        max_triangles = int(contract.get("max_triangles", DEFAULT_GEOMETRY_FITTING_LIMITS["triangle_budget_soft"]))
        min_parts = int(contract.get("min_parts", 1))
    missing_roles = sorted(required_roles - roles)
    if missing_roles:
        failures.append("missing_required_roles:" + ",".join(missing_roles))
    forbidden_roles = {
        "unknown_conservative_volume",
        "unknown_footprint",
        "uncertainty_marker",
    }
    forbidden_present = sorted(roles & forbidden_roles)
    if forbidden_present:
        failures.append("fallback_roles_present:" + ",".join(forbidden_present))
    if triangles > max_triangles:
        failures.append(f"triangle_budget_exceeded:{triangles}>{max_triangles}")
    if len(getattr(mesh, "parts", [])) < min_parts:
        failures.append(f"too_few_parts:{len(getattr(mesh, 'parts', []))}<{min_parts}")
    dims = dims_tuple(dims_m)
    if dims:
        length, width, height = dims
        if length <= 0 or width <= 0 or height <= 0:
            failures.append("invalid_metric_dims")
        for name, value in (("length", length), ("width", width), ("height", height)):
            low, high = dim_limits_for(name, label, archetype)
            if value < low or value > high:
                failures.append(f"{name}_outside_generic_limits:{value}")
    return {
        "accepted": not failures,
        "label": str(label or ""),
        "recipe_id": str(archetype or "unknown"),
        "recipe_version": OPEN_LABEL_RECIPE_VERSION,
        "verifier_version": OPEN_LABEL_VERIFIER_VERSION,
        "required_roles": sorted(required_roles),
        "roles": sorted(roles),
        "triangles": triangles,
        "part_count": len(getattr(mesh, "parts", [])),
        "max_triangles": max_triangles,
        "failures": failures,
    }


def build_open_label_or_fallback(mesh, label, builder, archetype, dims_m=None):
    candidate = Mesh()
    dims = parse_dims_arg(dims_m)
    parametric_builder = None
    if dims:
        key = str(label or "").strip().lower()
        parametric_builder = OPEN_LABEL_PARAMETRIC_BUILDERS.get(key) or OPEN_LABEL_PARAMETRIC_BUILDERS.get(archetype)
    if parametric_builder is not None:
        parametric_builder(candidate, dims)
        shape_policy = "verified_open_label_part_layout_from_metric_dims"
    else:
        builder(candidate)
        shape_policy = "verified_open_label_template_prior"
    verification = verify_open_label_proxy(label, archetype, candidate, dims)
    if verification["accepted"]:
        replace_mesh(mesh, candidate)
        return archetype, OPEN_LABEL_VERIFIED_STATUS, shape_policy, verification

    fallback_dims = dims or DEFAULT_ARCHETYPE_DIMS_M["unknown"]
    unknown_parametric(mesh, fallback_dims)
    fallback_policy = "fallback_conservative_volume_from_metric_dims" if dims else "template_prior"
    return "unknown", OPEN_LABEL_REJECTED_STATUS, fallback_policy, verification


def resolve_builder(label):
    key = str(label or 'unknown').strip().lower()
    if not key:
        return unknown_proxy, 'unknown', 'fallback_empty_label'
    exact = BUILDERS.get(key)
    if exact is not None and exact is not unknown_proxy:
        return exact, CANONICAL_ARCHETYPES.get(key, key), 'exact_class'
    tokens = _tokens(key)
    fallback_reason = forced_fallback_reason(tokens)
    if fallback_reason:
        return unknown_proxy, 'unknown', fallback_reason
    if "trailer" in tokens and tokens & {"tractor", "farm", "agricultural"}:
        return tractor_trailer, "tractor_trailer", "keyword_archetype"
    for archetype, builder, keywords in ARCHETYPE_RULES:
        for keyword in keywords:
            if keyword in tokens or (' ' in keyword and keyword in key):
                return builder, archetype, 'keyword_archetype'
    open_label_recipe = resolve_open_label_recipe(key, tokens)
    if open_label_recipe is not None:
        return open_label_recipe
    return unknown_proxy, 'unknown', 'fallback_unknown_label'


def resolver_match_type(resolution_status):
    if resolution_status == "exact_class":
        return "exact"
    if resolution_status == "keyword_archetype":
        return "keyword"
    if resolution_status in {OPEN_LABEL_RECIPE_STATUS, OPEN_LABEL_VERIFIED_STATUS}:
        return "open_label_recipe"
    if str(resolution_status or "").startswith("fallback"):
        return "fallback_unknown"
    return "unknown"


def build_resolver_contract(raw_label, normalized_label, archetype, resolution_status):
    match_type = resolver_match_type(resolution_status)
    return {
        "input_label": str(raw_label or ""),
        "normalized_label": str(normalized_label or ""),
        "resolver_source": "static_keyword_ontology",
        "archetype_id": str(archetype or "unknown"),
        "match_type": match_type,
        "ontology_version": ONTOLOGY_VERSION,
        "fallback_reason": resolution_status if match_type == "fallback_unknown" else None,
        "runtime_llm_used": False,
    }


def build_label(mesh, label):
    return build_label_parametric(mesh, label, None)


def build_label_parametric(mesh, label, dims_m=None):
    builder, archetype, status = resolve_builder(label)
    dims = parse_dims_arg(dims_m)
    prior_dims_used = dims is None
    if dims is None:
        dims = archetype_default_dims(label, archetype)
    if status == OPEN_LABEL_RECIPE_STATUS:
        archetype, status, shape_policy, verification = build_open_label_or_fallback(mesh, label, builder, archetype, dims)
        if prior_dims_used and shape_policy == "verified_open_label_part_layout_from_metric_dims":
            shape_policy = "verified_open_label_part_layout_from_prior_dims"
        return {
            'input_label': str(label or ''),
            'archetype': archetype,
            'resolution_status': status,
            'shape_policy': shape_policy,
            'effective_dims_m': dims,
            'metric_dims_source': "semantic_prior_dims" if prior_dims_used else "metric_dims_input",
            'explicit_metric_dims': not prior_dims_used,
            'open_label_verification': verification,
        }
    key = str(label or '').strip().lower()
    parametric_builder = PARAMETRIC_BUILDERS.get(key) or PARAMETRIC_BUILDERS.get(archetype)
    if parametric_builder is not None:
        parametric_builder(mesh, dims)
        if archetype == "unknown":
            shape_policy = "fallback_conservative_volume_from_prior_dims" if prior_dims_used else "fallback_conservative_volume_from_metric_dims"
        else:
            shape_policy = "semantic_part_layout_from_prior_dims" if prior_dims_used else "semantic_part_layout_from_metric_dims"
    else:
        builder(mesh)
        shape_policy = "template_prior"
    return {
        'input_label': str(label or ''),
        'archetype': archetype,
        'resolution_status': status,
        'shape_policy': shape_policy,
        'effective_dims_m': dims,
        'metric_dims_source': "semantic_prior_dims" if prior_dims_used else "metric_dims_input",
        'explicit_metric_dims': not prior_dims_used,
    }

def safe_name(text):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", text.strip()).strip("_") or "model"


def write_obj(mesh, obj_path, mtl_name):
    with open(obj_path, "w", encoding="ascii") as f:
        f.write(f"mtllib {mtl_name}\n")
        f.write("o XYT_generated\n")
        for v in mesh.vertices:
            f.write(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}\n")
        current = None
        for indices, material in mesh.faces:
            if material != current:
                current = material
                f.write(f"usemtl {material}\n")
            f.write("f " + " ".join(str(i) for i in indices) + "\n")


def get_material_metadata(name):
    default = _meta("unclassified_material", "semantic_prior", "none", 1.0)
    return dict(MATERIAL_METADATA.get(name, default))


def material_usage(mesh):
    usage = {}
    for indices, material in mesh.faces:
        usage.setdefault(material, {"faces": 0, "triangles": 0})
        usage[material]["faces"] += 1
        usage[material]["triangles"] += max(0, len(indices) - 2)
    return usage


def material_observation_applies(role, observed_color):
    return observed_color is not None and role in OBSERVED_COLOR_TARGET_ROLES


def descriptor_parts_with_material_evidence(parts, observed_color=None):
    out = []
    for part in parts:
        enriched = dict(part)
        role = str(enriched.get("material_role") or enriched.get("role") or "")
        if material_observation_applies(role, observed_color):
            enriched["evidence_source"] = "observed_color_input"
            enriched["observed_color_ref"] = "material.observed_color"
            enriched["display_color_policy"] = "observed_color_for_semantic_role"
        else:
            enriched["display_color_policy"] = "semantic_role_prior_or_fallback"
        out.append(enriched)
    return out


def rounded_number(value, digits=3):
    number = as_float(value)
    if number is None:
        return None
    return round(float(number), digits)


def visual_part_geometry_profile(value):
    if not isinstance(value, dict):
        return None
    existing = value.get("geometry_profile") or value.get("visual_part_geometry_profile")
    if isinstance(existing, dict) and existing.get("version") == VISUAL_PART_GEOMETRY_PROFILE_VERSION:
        return existing
    cues = value.get("image_space_cues") if isinstance(value.get("image_space_cues"), dict) else value
    if not isinstance(cues, dict):
        return None

    round_pairs = cues.get("validated_round_part_pairs") or cues.get("round_part_pairs") or []
    best_pair = None
    if isinstance(round_pairs, list):
        candidates = [pair for pair in round_pairs if isinstance(pair, dict)]
        if candidates:
            best_pair = max(candidates, key=lambda pair: as_float(pair.get("score")) or 0.0)

    line_coherence = cues.get("line_coherence") if isinstance(cues.get("line_coherence"), dict) else {}
    line_candidates = cues.get("line_primitive_candidates") or []
    longest_line = None
    if isinstance(line_candidates, list):
        candidates = [line for line in line_candidates if isinstance(line, dict)]
        if candidates:
            longest_line = max(candidates, key=lambda line: as_float(line.get("length_px")) or 0.0)

    profile = {
        "version": VISUAL_PART_GEOMETRY_PROFILE_VERSION,
        "source": str(value.get("source") or "agnostic_image_space_cues"),
        "applied": False,
        "policy": (
            "image_space_geometry_profile_for_role_conditioning_only_no_metric_part_fit"
        ),
        "label_used": bool(cues.get("label_used", value.get("label_used", False))),
        "claim_boundary": (
            "The profile stores image-space primitive measurements for existing descriptor roles; "
            "it is not ground-truth 3D, metric scale, or semantic part segmentation."
        ),
    }

    if best_pair:
        centers = best_pair.get("centers_xy") or []
        radii = best_pair.get("radii_px") or []
        profile["round_pair"] = {
            "axis_angle_deg": rounded_number(best_pair.get("pair_axis_angle_deg"), 3),
            "distance_px": rounded_number(best_pair.get("distance_px"), 3),
            "radii_px": [rounded_number(radius, 3) for radius in radii[:2]] if isinstance(radii, list) else [],
            "radius_ratio": rounded_number(best_pair.get("radius_ratio"), 4),
            "separation_radius_ratio": rounded_number(best_pair.get("separation_radius_ratio"), 4),
            "score": rounded_number(best_pair.get("score"), 4),
            "strength": str(best_pair.get("strength") or ""),
            "vertical_pair_fraction": rounded_number(best_pair.get("vertical_pair_fraction"), 4),
            "centers_xy": [
                [rounded_number(coord, 3) for coord in center[:2]]
                for center in centers[:2]
                if isinstance(center, (list, tuple)) and len(center) >= 2
            ],
        }
        profile["applied"] = True

    line_count = as_int(cues.get("line_primitive_count")) or as_int(cues.get("line_count")) or 0
    if line_count > 0 or line_coherence:
        line_structure = {
            "line_count": int(line_count),
            "coherent": bool(line_coherence.get("coherent")),
            "multi_orientation_structure": bool(line_coherence.get("multi_orientation_structure")),
            "dominant_angle_deg": rounded_number(line_coherence.get("dominant_angle_deg"), 3),
            "dominant_weight_fraction": rounded_number(line_coherence.get("dominant_weight_fraction"), 4),
            "long_line_count": as_int(line_coherence.get("long_line_count")) or 0,
            "max_line_length_px": rounded_number(line_coherence.get("max_line_length_px"), 3),
            "orientation_order": rounded_number(line_coherence.get("orientation_order"), 4),
        }
        if longest_line:
            line_structure["longest_line_xyxy"] = [
                rounded_number(coord, 3)
                for coord in (longest_line.get("xyxy") or [])[:4]
            ]
            line_structure["longest_line_angle_deg"] = rounded_number(longest_line.get("angle_deg"), 3)
            line_structure["longest_line_length_px"] = rounded_number(longest_line.get("length_px"), 3)
        profile["line_structure"] = line_structure
        profile["applied"] = True

    if not profile["applied"]:
        return None
    return profile


def normalize_visual_part_evidence(value):
    if not isinstance(value, dict):
        return None
    cues = value.get("image_space_cues") if isinstance(value.get("image_space_cues"), dict) else value
    line_coherence = cues.get("line_coherence") if isinstance(cues.get("line_coherence"), dict) else {}
    scope = str(cues.get("scope") or value.get("scope") or "")
    grade = str(cues.get("grade") or value.get("grade") or "")
    round_pairs = as_int(cues.get("validated_round_part_pair_count")) or as_int(cues.get("round_pair_count")) or 0
    strong_round_pairs = (
        as_int(cues.get("validated_strong_round_part_pair_count"))
        or as_int(cues.get("strong_round_pair_count"))
        or 0
    )
    line_count = as_int(cues.get("line_primitive_count")) or as_int(cues.get("line_count")) or 0
    edge_density = as_float(cues.get("edge_density")) or 0.0
    coherent_lines = bool(line_coherence.get("coherent"))
    multi_orientation = bool(line_coherence.get("multi_orientation_structure"))
    usable = (
        scope
        in {
            "round_part_pair_candidate",
            "weak_round_pair_candidate",
            "multi_line_structure_candidate",
            "image_edge_axis_candidate",
        }
        or round_pairs > 0
        or line_count > 0
    )
    if not usable:
        return None
    return {
        "version": VISUAL_PART_EVIDENCE_VERSION,
        "source": str(value.get("source") or "agnostic_image_space_cues"),
        "scope": scope,
        "grade": grade,
        "edge_density": round(float(edge_density), 6),
        "round_pair_count": int(round_pairs),
        "strong_round_pair_count": int(strong_round_pairs),
        "line_count": int(line_count),
        "coherent_lines": coherent_lines,
        "multi_orientation_lines": multi_orientation,
        "raw_image_pixels_used": bool(cues.get("raw_image_pixels_used", value.get("raw_image_pixels_used", True))),
        "label_used": bool(cues.get("label_used", value.get("label_used", False))),
        "geometry_profile": visual_part_geometry_profile(value),
        "claim_boundary": (
            "Generic image-space cues can support existing SPPA role groups but cannot create a new object class, "
            "override semantic normalization, or claim ground-truth part segmentation."
        ),
    }


def visual_part_role_support(mesh, visual_part_evidence):
    evidence = normalize_visual_part_evidence(visual_part_evidence)
    if not evidence:
        return None
    roles = {
        str(part.get("role") or part.get("material_role") or "")
        for part in getattr(mesh, "parts", [])
    }
    supported_roles = []
    policies = []
    if evidence["round_pair_count"] > 0:
        for role in ("vehicle_tire", "vehicle_metal_or_hub"):
            if role in roles:
                supported_roles.append(role)
        if any(role in roles for role in ("vehicle_tire", "vehicle_metal_or_hub")):
            policies.append("round_pair_supports_existing_wheel_or_hub_roles")
    if evidence["line_count"] > 0 or evidence["coherent_lines"] or evidence["multi_orientation_lines"]:
        for role in ("vertical_structure_metal", "bike_frame", "container_detail", "vehicle_attachment"):
            if role in roles:
                supported_roles.append(role)
        if any(role in roles for role in ("vertical_structure_metal", "bike_frame", "container_detail", "vehicle_attachment")):
            policies.append("line_cues_support_existing_linear_or_connector_roles")
    supported_roles = sorted(set(supported_roles))
    if not supported_roles:
        return {
            **evidence,
            "applied": False,
            "supported_roles": [],
            "role_support_policy": "no_matching_existing_roles_for_visual_cues",
        }
    return {
        **evidence,
        "applied": True,
        "supported_roles": supported_roles,
        "role_support_policy": "+".join(policies) if policies else "generic_cue_supports_existing_roles",
    }


def apply_visual_shape_conditioning(mesh, label, archetype, dims_m, visual_part_evidence):
    evidence = normalize_visual_part_evidence(visual_part_evidence)
    if not evidence:
        return None
    # Skip extra rails/braces under ultra-light budgets (speed + triangle priority).
    if getattr(mesh, "lod_params", {}).get("skip_visual_detail"):
        return {
            "applied": False,
            "reason": "skipped_under_mesh_lod_budget",
            "mesh_lod": getattr(mesh, "lod", None),
        }
    dims = dims_tuple(dims_m) or dims_tuple(archetype_default_dims(label, archetype))
    if not dims:
        return None

    roles = {
        str(part.get("role") or part.get("material_role") or "")
        for part in getattr(mesh, "parts", [])
    }
    length, width, height = dims
    key = str(label or "").strip().lower()
    archetype_key = str(archetype or "").strip().lower()
    has_round_pair = int(evidence.get("round_pair_count") or 0) > 0
    has_line_cue = (
        int(evidence.get("line_count") or 0) > 0
        or bool(evidence.get("coherent_lines"))
        or bool(evidence.get("multi_orientation_lines"))
    )
    before_parts = len(mesh.parts)
    before_triangles = mesh_triangle_count(mesh)
    additions = []

    vehicle_like = (
        archetype_key in VEHICLE_OBSERVATION_LABELS
        or key in VEHICLE_OBSERVATION_LABELS
        or any(role in roles for role in ("vehicle_tire", "vehicle_metal_or_hub", "vehicle_attachment"))
    )
    two_wheel_like = (
        archetype_key in TWO_WHEEL_OBSERVATION_LABELS
        or key in TWO_WHEEL_OBSERVATION_LABELS
        or "bike_frame" in roles
    )
    if has_round_pair and (vehicle_like or two_wheel_like):
        rail_r = clamp(min(width, height) * 0.018, 0.018, 0.045)
        rail_z = clamp(height * 0.24, 0.16, max(0.18, height * 0.52))
        if two_wheel_like:
            rail_x = max(length * 0.36, 0.22)
            mesh.cylinder_between(
                (-rail_x, 0.0, rail_z),
                (rail_x, 0.0, rail_z),
                rail_r,
                "bike_frame_prior",
                optional=True,
            )
            additions.append("round_pair_conditioned_wheelbase_rails")
        else:
            rail_x = max(length * 0.38, 0.35)
            rail_y = max(width * 0.35, 0.12)
            for y in (-rail_y, rail_y):
                mesh.cylinder_between(
                    (-rail_x, y, rail_z),
                    (rail_x, y, rail_z),
                    rail_r,
                    "vehicle_metal_prior",
                    optional=True,
                )
            additions.append("round_pair_conditioned_vehicle_side_rails")

    if has_line_cue and (
        archetype_key in VERTICAL_STRUCTURE_LABELS
        or key in VERTICAL_STRUCTURE_LABELS
        or "vertical_structure_metal" in roles
    ):
        brace_r = clamp(min(length, width) * 0.014, 0.018, 0.055)
        x0 = max(length * 0.25, brace_r * 4.0)
        x1 = max(length * 0.08, brace_r * 1.8)
        y0 = max(width * 0.24, brace_r * 3.2)
        y1 = max(width * 0.07, brace_r * 1.6)
        for sx in (-1.0, 1.0):
            mesh.cylinder_between(
                (sx * x0, -y0, height * 0.18),
                (sx * x1, y1, height * 0.58),
                brace_r,
                "structure_metal_prior",
                optional=True,
            )
        additions.append("line_conditioned_lateral_tower_braces")

    container_or_trailer_like = (
        archetype_key in {"articulated_vehicle", "tractor_trailer", "vehicle_with_trailer", "heavy_vehicle", "generic_vehicle"}
        or key in {"articulated_vehicle", "tractor_trailer", "vehicle_with_trailer", "heavy_vehicle", "generic_vehicle"}
        or any(role in roles for role in ("container_detail", "vehicle_attachment"))
    )
    if has_line_cue and container_or_trailer_like and length >= 5.0:
        rib_w = clamp(length * 0.010, 0.035, 0.080)
        rib_d = clamp(width * 0.018, 0.025, 0.055)
        rib_h = clamp(height * 0.34, 0.45, max(0.50, height * 0.52))
        rib_z = clamp(height * 0.52, rib_h / 2.0, max(rib_h / 2.0, height - rib_h * 0.20))
        for y in (-width * 0.49, width * 0.49):
            mesh.box((0.0, y, rib_z), (rib_w, rib_d, rib_h), "container_detail_prior")
        additions.append("line_conditioned_side_ribs")

    if not additions:
        return {
            "version": VISUAL_SHAPE_CONDITIONING_VERSION,
            "applied": False,
            "reason": "visual_cues_do_not_match_existing_geometry_roles",
            "cue_scope": evidence.get("scope"),
            "claim_boundary": (
                "Visual cues can only condition roles that already exist in the selected SPPA family; "
                "they cannot create a new class or claim metric part segmentation."
            ),
        }
    return {
        "version": VISUAL_SHAPE_CONDITIONING_VERSION,
        "applied": True,
        "source": evidence.get("source"),
        "cue_scope": evidence.get("scope"),
        "additions": additions,
        "added_parts": len(mesh.parts) - before_parts,
        "added_triangles": mesh_triangle_count(mesh) - before_triangles,
        "policy": "budgeted_visual_cues_condition_existing_semantic_roles_only",
        "claim_boundary": (
            "The added primitives are low-cost role reinforcements from agnostic image-space cues. "
            "They are not ground-truth part boundaries, not manual fixes, and not a dense reconstruction."
        ),
    }


def descriptor_parts_with_visual_part_evidence(parts, visual_role_support):
    if not isinstance(visual_role_support, dict) or not visual_role_support.get("applied"):
        return [dict(part) for part in parts]
    supported_roles = set(visual_role_support.get("supported_roles") or [])
    out = []
    for part in parts:
        enriched = dict(part)
        role = str(enriched.get("material_role") or enriched.get("role") or "")
        if role in supported_roles:
            enriched["visual_part_evidence_source"] = visual_role_support.get("source")
            enriched["visual_part_evidence_scope"] = visual_role_support.get("scope")
            enriched["visual_part_evidence_version"] = visual_role_support.get("version")
            enriched["visual_part_support_policy"] = visual_role_support.get("role_support_policy")
            enriched["visual_part_support_confidence"] = {
                "round_pair_count": visual_role_support.get("round_pair_count"),
                "strong_round_pair_count": visual_role_support.get("strong_round_pair_count"),
                "line_count": visual_role_support.get("line_count"),
                "edge_density": visual_role_support.get("edge_density"),
            }
        out.append(enriched)
    return out


def normalize_visual_metric_yaw_consistency(value):
    if not isinstance(value, dict):
        return None
    applied = bool(value.get("applied", value.get("available", False)))
    agreement = str(value.get("agreement") or value.get("projected_visual_metric_agreement") or "")
    projected_yaw = rounded_number(
        value.get("projected_visual_axis_yaw_deg", value.get("visual_axis_yaw_deg")),
        3,
    )
    footprint_yaw = rounded_number(
        value.get("projected_metric_yaw_deg", value.get("footprint_yaw_deg")),
        3,
    )
    delta = rounded_number(
        value.get("projected_visual_metric_delta_deg", value.get("axial_delta_deg")),
        3,
    )
    if not applied and projected_yaw is None and footprint_yaw is None and delta is None:
        return None
    axis_source_raw = str(value.get("visual_axis_source") or value.get("axis_source") or "")
    axis_source = {
        "round_pair_centers_projected_to_ground": "round_pair",
        "longest_line_projected_to_ground": "longest_line",
    }.get(axis_source_raw, axis_source_raw or None)
    return {
        "version": VISUAL_METRIC_YAW_CONSISTENCY_VERSION,
        "applied": applied,
        "source": "projected_visual_axis",
        "visual_axis_source": axis_source,
        "projected_visual_axis_yaw_deg": projected_yaw,
        "footprint_yaw_deg": footprint_yaw,
        "axial_delta_deg": delta,
        "agreement": agreement or "unknown",
        "policy": "support_gate_only",
        "claim_boundary": "Declared UAV replay projection; not measured telemetry, GT yaw, or manual correction.",
    }


def yaw_from_visual_metric_consistency(visual_metric_yaw_consistency, pose_world):
    if not isinstance(visual_metric_yaw_consistency, dict):
        return None
    if not visual_metric_yaw_consistency.get("applied"):
        return None
    if str(visual_metric_yaw_consistency.get("agreement") or "") not in {"aligned", "weakly_aligned"}:
        return None
    yaw_deg = as_float(visual_metric_yaw_consistency.get("footprint_yaw_deg"))
    if yaw_deg is None:
        return None
    yaw_deg = yaw_deg % 180.0
    return {
        "version": VISUAL_METRIC_YAW_CONSISTENCY_VERSION,
        "yaw_rad": math.radians(yaw_deg),
        "yaw_deg": yaw_deg,
        "yaw_source": "projected_footprint_yaw_gate",
        "yaw_modulo": "pi",
        "yaw_ambiguous": True,
        "coordinate_frame": pose_world.get("coordinate_frame") if isinstance(pose_world, dict) else "declared_assumed_flight_replay_local_ned",
        "confidence": 0.70 if visual_metric_yaw_consistency.get("agreement") == "aligned" else 0.55,
        "policy": "visual_metric_gate_nondivergent",
        "claim_boundary": (
            "Declared replay axial yaw; not measured telemetry, GT yaw, or 2pi heading."
        ),
    }


def build_material_manifest(mesh, build_meta, confidence=1.0, observed_color=None):
    confidence = max(0.0, min(1.0, float(confidence)))
    resolution_status = build_meta.get("resolution_status", "unknown")
    fallback = resolution_status.startswith("fallback")
    materials = []
    for name, counts in sorted(material_usage(mesh).items()):
        meta = get_material_metadata(name)
        if fallback and meta["evidence_source"] == "semantic_prior":
            meta["evidence_source"] = "fallback_unknown"
            meta["uncertainty_visual_style"] = "desaturated_unknown"
            meta["alpha"] = min(float(meta.get("alpha", 1.0)), 0.72)
        elif confidence < 0.50 and meta["uncertainty_visual_style"] == "none":
            meta["uncertainty_visual_style"] = "low_confidence_desaturation"
        semantic_prior_rgb = MATERIALS.get(name, (0.45, 0.45, 0.45))
        display_rgb = semantic_prior_rgb
        if material_observation_applies(meta["material_role"], observed_color):
            meta["evidence_source"] = "observed_color_input"
            meta["semantic_prior_rgb"] = semantic_prior_rgb
            meta["observed_color_rgb"] = observed_color["rgb"]
            meta["observed_color_source"] = observed_color["source"]
            meta["observed_color_confidence"] = observed_color["confidence"]
            meta["display_color_policy"] = "observed_color_for_semantic_role"
            display_rgb = observed_color["rgb"]
        materials.append({
            "name": name,
            "rgb": display_rgb,
            "face_count": counts["faces"],
            "triangle_count": counts["triangles"],
            **meta,
        })
    return {
        "descriptor_schema": MATERIAL_DESCRIPTOR_VERSION,
        "input_label": build_meta.get("input_label", ""),
        "archetype": build_meta.get("archetype", "unknown"),
        "resolution_status": resolution_status,
        "confidence": confidence,
        "material_policy": "role_priors_with_optional_observed_color",
        "observed_material_policy": "applied_only_to_observable_semantic_roles_when_explicit_color_evidence_is_supplied",
        "observed_color": observed_color,
        "materials": materials,
    }


def write_material_manifest(manifest_path, mesh, build_meta, confidence=1.0, observed_color=None):
    manifest = build_material_manifest(mesh, build_meta, confidence, observed_color)
    with open(manifest_path, "w", encoding="ascii") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    return manifest


def clamp01(value, default=0.0):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def as_float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value):
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def first_present(mapping, keys, default=None):
    if not isinstance(mapping, dict):
        return default
    for key in keys:
        if key in mapping and mapping.get(key) is not None:
            return mapping.get(key)
    return default


def canonical_json_bytes(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def stable_hash(payload, length=16):
    return hashlib.sha1(canonical_json_bytes(payload)).hexdigest()[:length]


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json_arg(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if os.path.exists(text):
        with open(text, "r", encoding="utf-8") as f:
            return json.load(f)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # PowerShell commonly strips nested double quotes from inline JSON.
        # Accept only a flat object fallback such as {x:0,y:20,w:180,h:80}.
        if text.startswith("{") and text.endswith("}"):
            body = text[1:-1].strip()
            out = {}
            if not body:
                return out
            for chunk in body.split(","):
                if ":" not in chunk:
                    raise
                key, raw = chunk.split(":", 1)
                key = key.strip().strip("'\"")
                raw = raw.strip().strip("'\"")
                number = as_float(raw)
                out[key] = number if number is not None else raw
            return out
        raise


def parse_dims_arg(value):
    if value is None:
        return None
    if isinstance(value, dict):
        length = as_float(first_present(value, ("length_m", "length", "x")))
        width = as_float(first_present(value, ("width_m", "width", "y")))
        height = as_float(first_present(value, ("height_m", "height", "z")))
    elif isinstance(value, (list, tuple)) and len(value) >= 3:
        length, width, height = (as_float(value[0]), as_float(value[1]), as_float(value[2]))
    else:
        parts = [p.strip() for p in str(value).split(",")]
        if len(parts) < 3:
            return None
        length, width, height = (as_float(parts[0]), as_float(parts[1]), as_float(parts[2]))
    if length is None or width is None or height is None:
        return None
    return {"length": length, "width": width, "height": height}


def parse_dims_cli(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if os.path.exists(text) or text.startswith(("{", "[")):
        return parse_dims_arg(load_json_arg(text))
    return parse_dims_arg(text)


def normalize_metric_scale(value):
    if value is None:
        return None
    payload = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if os.path.exists(text) or text.startswith(("{", "[")):
            payload = load_json_arg(text)
        else:
            payload = {"meters_per_pixel": as_float(text)}
    if isinstance(payload, (int, float)):
        payload = {"meters_per_pixel": float(payload)}
    if not isinstance(payload, dict):
        return None
    meters_per_pixel = as_float(
        first_present(
            payload,
            (
                "meters_per_pixel",
                "meter_per_pixel",
                "m_per_px",
                "ground_sample_distance_m_per_px",
                "gsd_m_per_px",
            ),
        )
    )
    pixels_per_meter = as_float(first_present(payload, ("pixels_per_meter", "px_per_m")))
    if meters_per_pixel is None and pixels_per_meter is not None and pixels_per_meter > 0:
        meters_per_pixel = 1.0 / pixels_per_meter
    if meters_per_pixel is None or meters_per_pixel <= 0:
        return None
    confidence = clamp01(first_present(payload, ("confidence", "scale_confidence"), 1.0), 1.0)
    return {
        "meters_per_pixel": meters_per_pixel,
        "pixels_per_meter": 1.0 / meters_per_pixel,
        "source": str(first_present(payload, ("source", "scale_source"), "explicit_ground_sample_distance")),
        "confidence": confidence,
        "height_m": as_float(first_present(payload, ("height_m", "object_height_m"))),
        "default_height_m": as_float(first_present(payload, ("default_height_m", "fallback_height_m"))),
        "calibration_ref": first_present(payload, ("calibration_ref", "ref")),
    }


def parse_metric_scale_cli(value):
    return normalize_metric_scale(value)


def _parse_hex_color(text):
    if not isinstance(text, str):
        return None
    value = text.strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) != 6:
        return None
    try:
        return [int(value[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
    except ValueError:
        return None


def normalize_rgb_values(values):
    if not isinstance(values, (list, tuple)) or len(values) < 3:
        return None
    rgb = [as_float(values[0]), as_float(values[1]), as_float(values[2])]
    if any(v is None for v in rgb):
        return None
    if max(rgb) > 1.0:
        rgb = [v / 255.0 for v in rgb]
    return [round(clamp01(v), 6) for v in rgb]


def normalize_observed_color(value):
    if value is None:
        return None
    payload = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        hex_rgb = _parse_hex_color(text)
        if hex_rgb is not None:
            payload = {"rgb": hex_rgb, "source": "explicit_hex_input"}
        elif os.path.exists(text) or text.startswith(("{", "[")):
            payload = load_json_arg(text)
        else:
            payload = {"rgb": [p.strip() for p in text.split(",")], "source": "explicit_rgb_input"}
    if isinstance(payload, dict):
        raw_rgb = first_present(payload, ("rgb", "rgb01", "color", "mean_rgb", "median_rgb"))
        if raw_rgb is None:
            raw_rgb = first_present(payload, ("rgb255", "color_rgb255", "mean_rgb255", "median_rgb255"))
        if raw_rgb is None:
            raw_rgb = _parse_hex_color(str(first_present(payload, ("hex", "hex_color"), "")))
        rgb = normalize_rgb_values(raw_rgb)
        if rgb is None:
            return None
        confidence = clamp01(first_present(payload, ("confidence", "color_confidence"), 1.0), 1.0)
        return {
            "rgb": rgb,
            "source": str(first_present(payload, ("source", "evidence_source"), "explicit_observed_color")),
            "confidence": confidence,
            "color_space": str(first_present(payload, ("color_space", "space"), "srgb")),
            "policy": "applied_to_observable_semantic_roles_only",
        }
    rgb = normalize_rgb_values(payload)
    if rgb is None:
        return None
    return {
        "rgb": rgb,
        "source": "explicit_rgb_input",
        "confidence": 1.0,
        "color_space": "srgb",
        "policy": "applied_to_observable_semantic_roles_only",
    }


def parse_observed_color_cli(value):
    return normalize_observed_color(value)


def normalize_bbox(bbox):
    if not isinstance(bbox, dict):
        return None
    x = as_float(first_present(bbox, ("x", "left")))
    y = as_float(first_present(bbox, ("y", "top")))
    w = as_float(first_present(bbox, ("w", "width")))
    h = as_float(first_present(bbox, ("h", "height")))
    x1 = as_float(first_present(bbox, ("x1", "xmin")))
    y1 = as_float(first_present(bbox, ("y1", "ymin")))
    x2 = as_float(first_present(bbox, ("x2", "xmax")))
    y2 = as_float(first_present(bbox, ("y2", "ymax")))
    if w is None and x1 is not None and x2 is not None:
        w = abs(x2 - x1)
    if h is None and y1 is not None and y2 is not None:
        h = abs(y2 - y1)
    if x is None and x1 is not None:
        x = x1
    if y is None and y1 is not None:
        y = y1
    if x1 is None and x is not None:
        x1 = x
    if y1 is None and y is not None:
        y1 = y
    if x2 is None and x1 is not None and w is not None:
        x2 = x1 + w
    if y2 is None and y1 is not None and h is not None:
        y2 = y1 + h
    if w is None or h is None:
        return None
    out = {
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "aspect": w / h if h and abs(h) > 1e-9 else None,
    }
    return {k: v for k, v in out.items() if v is not None}


def mask_points(mask):
    if mask is None:
        return []
    source = mask
    if isinstance(mask, dict):
        source = mask.get("polygon") or mask.get("points") or mask.get("vertices") or []
    points = []
    for item in source:
        if isinstance(item, dict):
            x = as_float(item.get("x"))
            y = as_float(item.get("y"))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            x = as_float(item[0])
            y = as_float(item[1])
        else:
            continue
        if x is not None and y is not None:
            points.append((x, y))
    return points


def polygon_area(points):
    if len(points) < 3:
        return None
    area = 0.0
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def axial_pca_yaw(points):
    if len(points) < 2:
        return None
    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    cov_xx = sum((x - mean_x) * (x - mean_x) for x, _ in points) / len(points)
    cov_yy = sum((y - mean_y) * (y - mean_y) for _, y in points) / len(points)
    cov_xy = sum((x - mean_x) * (y - mean_y) for x, y in points) / len(points)
    angle = 0.5 * math.atan2(2.0 * cov_xy, cov_xx - cov_yy)
    while angle < 0:
        angle += math.pi
    while angle >= math.pi:
        angle -= math.pi
    return angle


def oriented_footprint(points):
    if len(points) < 3:
        return None
    yaw = axial_pca_yaw(points)
    if yaw is None:
        return None
    area = polygon_area(points)
    ux = (math.cos(yaw), math.sin(yaw))
    uy = (-math.sin(yaw), math.cos(yaw))
    proj_x = [x * ux[0] + y * ux[1] for x, y in points]
    proj_y = [x * uy[0] + y * uy[1] for x, y in points]
    length = max(proj_x) - min(proj_x)
    width = max(proj_y) - min(proj_y)
    if width > length:
        length, width = width, length
        yaw = (yaw + math.pi / 2.0) % math.pi
        ux = (math.cos(yaw), math.sin(yaw))
        uy = (-math.sin(yaw), math.cos(yaw))
    oriented_area = length * width
    return {
        "length": length,
        "width": width,
        "source": "mask_oriented_pca",
        "orientation_rad_axial": yaw,
        "orientation_deg_axial": math.degrees(yaw),
        "orientation_modulo": "pi",
        "axis_major_unit": [ux[0], ux[1]],
        "axis_minor_unit": [uy[0], uy[1]],
        "area_px2": area,
        "oriented_box_area_px2": oriented_area,
        "fill_ratio": area / oriented_area if area is not None and oriented_area > 1e-9 else None,
    }


def normalize_mask(mask):
    points = mask_points(mask)
    if not points:
        return None
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    bbox = {
        "x": min(xs),
        "y": min(ys),
        "w": max(xs) - min(xs),
        "h": max(ys) - min(ys),
        "x1": min(xs),
        "y1": min(ys),
        "x2": max(xs),
        "y2": max(ys),
    }
    area = polygon_area(points)
    yaw = axial_pca_yaw(points)
    oriented = oriented_footprint(points)
    payload = {"points": [[round(x, 6), round(y, 6)] for x, y in points]}
    return {
        "polygon": payload["points"],
        "point_count": len(points),
        "hash": stable_hash(payload),
        "bbox_px": bbox,
        "area_px2": area,
        "pca_yaw_rad_axial": yaw,
        "pca_yaw_deg_axial": math.degrees(yaw) if yaw is not None else None,
        "oriented_footprint_px": oriented,
    }


def archetype_default_dims(label, archetype):
    key = str(label or "").strip().lower()
    dims = DEFAULT_ARCHETYPE_DIMS_M.get(key) or DEFAULT_ARCHETYPE_DIMS_M.get(str(archetype or "").strip().lower())
    if dims is None:
        dims = DEFAULT_ARCHETYPE_DIMS_M["unknown"]
    return dict(dims)


def dim_limits_for(name, label=None, archetype=None):
    low, high = GENERIC_DIM_LIMITS_M[name]
    family = {str(label or "").strip().lower(), str(archetype or "").strip().lower()}
    if name == "height" and family & VERTICAL_STRUCTURE_LABELS:
        high = VERTICAL_STRUCTURE_HEIGHT_LIMIT_M
    return low, high


def clamp_dim(name, value, label=None, archetype=None):
    low, high = dim_limits_for(name, label, archetype)
    return clamp(float(value), low, high)


def _family_keys(label=None, archetype=None):
    keys = set()
    for raw in (label, archetype):
        text = str(raw or "").strip().lower()
        if not text:
            continue
        keys.add(text)
        keys.add(text.replace(" ", "_"))
        keys.add(text.replace("_", " "))
    return keys


def _family_contains(keys, values):
    for value in values:
        if value in keys or value.replace("_", " ") in keys:
            return True
    return False


def _uncertainty_quality(uncertainty, confidence=None):
    if isinstance(uncertainty, dict):
        quality_flags = uncertainty.get("quality_flags")
        if isinstance(quality_flags, dict):
            value = as_float(quality_flags.get("mask_quality_score"))
            if value is not None:
                return clamp01(value, 0.5)
        value = as_float(uncertainty.get("confidence"))
        if value is not None:
            return clamp01(value, 0.5)
    return clamp01(confidence, 0.5)


def _is_shape_low_confidence(uncertainty, quality):
    if isinstance(uncertainty, dict) and bool(uncertainty.get("shape_low_confidence")):
        return True
    return quality < 0.50


def _aspect_limits_for(keys, prior_aspect):
    if _family_contains(keys, {"tractor_trailer", "heavy_vehicle", "truck", "bus", "van"}):
        return 2.20, 5.80
    if _family_contains(keys, {"biker", "cyclist", "two_wheeled_rider", "motorcycle", "bicycle"}):
        return 1.90, 4.40
    if _family_contains(keys, {"tractor", "farm_vehicle"}):
        return 1.45, 2.85
    if _family_contains(keys, {"light_vehicle", "car", "pickup"}):
        return 1.45, 3.30
    return max(1.20, prior_aspect * 0.55), min(6.50, max(1.60, prior_aspect * 1.80))


def _vehicle_length_cap(keys):
    if _family_contains(keys, {"tractor_trailer", "heavy_vehicle", "truck", "bus"}):
        return 1.70
    if _family_contains(keys, {"biker", "cyclist", "two_wheeled_rider", "motorcycle", "bicycle"}):
        return 1.25
    return 1.40


def _vehicle_width_cap(keys):
    if _family_contains(keys, {"tractor_trailer", "heavy_vehicle", "truck", "bus"}):
        return 1.55
    if _family_contains(keys, {"biker", "cyclist", "two_wheeled_rider", "motorcycle", "bicycle"}):
        return 1.35
    return 1.35


def fuse_observed_dims_with_prior(label, archetype, observed_dims, uncertainty=None, confidence=None):
    """Constrain detector-derived metric dimensions with semantic family priors.

    The function does not infer new semantic parts and does not repair the image
    mask itself. It only turns noisy observation dimensions into a physically
    plausible size for the already selected SPPA archetype.
    """
    observed = parse_dims_arg(observed_dims)
    if not observed:
        return {
            "version": OBSERVATION_FUSION_VERSION,
            "applied": False,
            "source": "missing_observed_dims",
            "dims_m": None,
            "policy": "no_observation_dims_available",
        }

    keys = _family_keys(label, archetype)
    prior = archetype_default_dims(label, archetype)
    prior_h = max(0.10, float(prior.get("height") or observed["height"] or 1.0))
    height = clamp_dim("height", observed["height"], label, archetype)
    height_scale = clamp(height / prior_h, 0.45, 2.50)
    prior_scaled = {
        "length": clamp_dim("length", float(prior["length"]) * height_scale, label, archetype),
        "width": clamp_dim("width", float(prior["width"]) * height_scale, label, archetype),
        "height": height,
    }
    quality = _uncertainty_quality(uncertainty, confidence)
    low_confidence = _is_shape_low_confidence(uncertainty, quality)
    raw_length = clamp_dim("length", max(observed["length"], observed["width"]), label, archetype)
    raw_width = clamp_dim("width", min(observed["length"], observed["width"]), label, archetype)
    raw_aspect = raw_length / max(0.01, raw_width)

    if _family_contains(keys, VERTICAL_STRUCTURE_LABELS):
        scale = max(1.0, height / prior_h)
        prior_len = clamp_dim("length", float(prior["length"]) * scale, label, archetype)
        prior_w = clamp_dim("width", float(prior["width"]) * scale, label, archetype)
        dims = {
            "length": max(0.20, min(raw_length, prior_len)),
            "width": max(0.20, min(raw_width, prior_w)),
            "height": height,
        }
        return {
            "version": OBSERVATION_FUSION_VERSION,
            "applied": True,
            "source": "constraint_fused_vertical_height",
            "policy": "vertical_structure_keeps_observed_height_and_clamps_footprint_to_prior",
            "dims_m": dims,
            "raw_dims_m": observed,
            "prior_dims_m": prior,
            "quality": quality,
            "shape_low_confidence": low_confidence,
            "image_geometry_reliable": not low_confidence,
        }

    is_vehicle = _family_contains(keys, VEHICLE_OBSERVATION_LABELS)
    is_two_wheel = _family_contains(keys, TWO_WHEEL_OBSERVATION_LABELS)
    if is_vehicle or is_two_wheel:
        prior_aspect = prior_scaled["length"] / max(0.01, prior_scaled["width"])
        min_aspect, max_aspect = _aspect_limits_for(keys, prior_aspect)
        aspect_implausible = raw_aspect < min_aspect or raw_aspect > max_aspect
        width_implausible = raw_width > prior_scaled["width"] * _vehicle_width_cap(keys)
        must_fuse = low_confidence or aspect_implausible or width_implausible
        if must_fuse:
            weight = clamp(0.20 + quality * (0.55 if not low_confidence else 0.38), 0.18, 0.78)
            max_length = prior_scaled["length"] * _vehicle_length_cap(keys)
            min_length = max(0.20, prior_scaled["length"] * 0.72)
            observed_length = clamp(raw_length, min_length, max_length)
            fused_length = (1.0 - weight) * prior_scaled["length"] + weight * observed_length
            if aspect_implausible:
                target_aspect = prior_aspect
            else:
                target_aspect = clamp(raw_aspect, min_aspect, max_aspect)
                if low_confidence:
                    target_aspect = (1.0 - weight) * prior_aspect + weight * target_aspect
            fused_width = fused_length / max(0.01, target_aspect)
            max_width = prior_scaled["width"] * _vehicle_width_cap(keys)
            fused_width = clamp(fused_width, max(0.18, prior_scaled["width"] * 0.72), max_width)
            dims = {
                "length": clamp_dim("length", fused_length, label, archetype),
                "width": clamp_dim("width", fused_width, label, archetype),
                "height": height,
            }
            reasons = []
            if low_confidence:
                reasons.append("low_confidence")
            if aspect_implausible:
                reasons.append("aspect_implausible")
            if width_implausible:
                reasons.append("width_implausible")
            return {
                "version": OBSERVATION_FUSION_VERSION,
                "applied": True,
                "source": "constraint_fused_vehicle_observation",
                "policy": "vehicle_metric_dims_soft_fused_with_semantic_aspect_prior",
                "dims_m": dims,
                "raw_dims_m": observed,
                "prior_dims_m": prior,
                "quality": quality,
                "shape_low_confidence": low_confidence,
                "raw_aspect": raw_aspect,
                "target_aspect_range": [min_aspect, max_aspect],
                "fusion_weight": weight,
                "fusion_reasons": reasons,
                "image_geometry_reliable": not low_confidence and not aspect_implausible,
            }
        return {
            "version": OBSERVATION_FUSION_VERSION,
            "applied": True,
            "source": "accepted_vehicle_observation",
            "policy": "vehicle_metric_dims_pass_family_plausibility_checks",
            "dims_m": {
                "length": raw_length,
                "width": raw_width,
                "height": height,
            },
            "raw_dims_m": observed,
            "prior_dims_m": prior,
            "quality": quality,
            "shape_low_confidence": low_confidence,
            "raw_aspect": raw_aspect,
            "target_aspect_range": [min_aspect, max_aspect],
            "image_geometry_reliable": True,
        }

    return {
        "version": OBSERVATION_FUSION_VERSION,
        "applied": not low_confidence,
        "source": "accepted_generic_observation" if not low_confidence else "generic_low_confidence_not_applied",
        "policy": "generic_metric_dims_used_only_when_shape_confidence_is_not_low",
        "dims_m": {
            "length": raw_length,
            "width": raw_width,
            "height": height,
        }
        if not low_confidence
        else None,
        "raw_dims_m": observed,
        "prior_dims_m": prior,
        "quality": quality,
        "shape_low_confidence": low_confidence,
        "image_geometry_reliable": not low_confidence,
    }


def derive_metric_dims_from_evidence(label, archetype, bbox=None, mask=None, metric_scale=None, height_m=None):
    scale = normalize_metric_scale(metric_scale)
    if not scale:
        return None

    footprint = None
    mask_meta = normalize_mask(mask)
    if mask_meta:
        oriented = mask_meta.get("oriented_footprint_px")
        if oriented:
            footprint = {
                "length_px": float(oriented["length"]),
                "width_px": float(oriented["width"]),
                "source": "calibrated_mask_oriented_footprint",
                "image_space_source": oriented["source"],
                "orientation_deg_axial": oriented.get("orientation_deg_axial"),
                "orientation_modulo": oriented.get("orientation_modulo"),
                "fill_ratio": oriented.get("fill_ratio"),
            }
        else:
            mb = mask_meta.get("bbox_px")
            if mb:
                footprint = {
                    "length_px": max(float(mb["w"]), float(mb["h"])),
                    "width_px": min(float(mb["w"]), float(mb["h"])),
                    "source": "calibrated_mask_bbox",
                    "image_space_source": "mask_bbox",
                }
    if footprint is None:
        bbox_px = normalize_bbox(bbox)
        if bbox_px:
            footprint = {
                "length_px": max(float(bbox_px["w"]), float(bbox_px["h"])),
                "width_px": min(float(bbox_px["w"]), float(bbox_px["h"])),
                "source": "calibrated_bbox",
                "image_space_source": "bbox_px",
            }
    if footprint is None:
        return None

    meters_per_pixel = float(scale["meters_per_pixel"])
    length_m = clamp_dim("length", footprint["length_px"] * meters_per_pixel, label, archetype)
    width_m = clamp_dim("width", footprint["width_px"] * meters_per_pixel, label, archetype)
    if width_m > length_m:
        length_m, width_m = width_m, length_m

    default_dims = archetype_default_dims(label, archetype)
    explicit_height = as_float(height_m)
    if explicit_height is not None:
        height = explicit_height
        height_source = "explicit_height_m"
    elif scale.get("height_m") is not None:
        height = float(scale["height_m"])
        height_source = "metric_scale_height_m"
    elif scale.get("default_height_m") is not None:
        height = float(scale["default_height_m"])
        height_source = "metric_scale_default_height_m"
    else:
        height = float(default_dims["height"])
        height_source = "archetype_prior_height"
    height_m_value = clamp_dim("height", height, label, archetype)

    source = footprint["source"]
    return {
        "dims_m": {
            "length": length_m,
            "width": width_m,
            "height": height_m_value,
        },
        "source": source,
        "metric_scale": {
            "meters_per_pixel": meters_per_pixel,
            "pixels_per_meter": scale["pixels_per_meter"],
            "source": scale["source"],
            "confidence": scale["confidence"],
            "calibration_ref": scale.get("calibration_ref"),
        },
        "footprint": footprint,
        "height_source": height_source,
        "policy": "calibrated_footprint_sets_length_width_height_from_prior_or_explicit_input",
    }


def build_label_observed(mesh, label, dims_m=None, bbox=None, mask=None, metric_scale=None, height_m=None, visual_part_evidence=None):
    builder, archetype, status = resolve_builder(label)
    explicit_dims = parse_dims_arg(dims_m)
    derived = None
    effective_dims = explicit_dims
    metric_dims_source = "metric_dims_input" if explicit_dims else None
    prior_dims_used = False

    if effective_dims is None:
        derived = derive_metric_dims_from_evidence(
            label,
            archetype,
            bbox=bbox,
            mask=mask,
            metric_scale=metric_scale,
            height_m=height_m,
        )
        if derived:
            effective_dims = derived["dims_m"]
            metric_dims_source = derived["source"]
    if effective_dims is None:
        effective_dims = archetype_default_dims(label, archetype)
        metric_dims_source = "semantic_prior_dims"
        prior_dims_used = True

    parametric_builder = None
    key = str(label or "").strip().lower()
    open_label_verification = None
    if status == OPEN_LABEL_RECIPE_STATUS:
        archetype, status, shape_policy, open_label_verification = build_open_label_or_fallback(
            mesh,
            label,
            builder,
            archetype,
            effective_dims,
        )
        if prior_dims_used and shape_policy == "verified_open_label_part_layout_from_metric_dims":
            shape_policy = "verified_open_label_part_layout_from_prior_dims"
        return {
            "input_label": str(label or ""),
            "archetype": archetype,
            "resolution_status": status,
            "shape_policy": shape_policy,
            "metric_dims_source": metric_dims_source,
            "effective_dims_m": effective_dims,
            "shape_evidence": derived,
            "visual_part_evidence": normalize_visual_part_evidence(visual_part_evidence),
            "visual_shape_conditioning": None,
            "explicit_metric_dims": explicit_dims is not None,
            "semantic_prior_dims_used": prior_dims_used,
            "open_label_verification": open_label_verification,
            "open_label_recipe_version": OPEN_LABEL_RECIPE_VERSION,
        }
    parametric_builder = PARAMETRIC_BUILDERS.get(key) or PARAMETRIC_BUILDERS.get(archetype)
    if parametric_builder is not None:
        parametric_builder(mesh, effective_dims)
        visual_shape_conditioning = apply_visual_shape_conditioning(
            mesh,
            label,
            archetype,
            effective_dims,
            visual_part_evidence,
        )
        if archetype == "unknown":
            shape_policy = "fallback_conservative_volume_from_prior_dims" if prior_dims_used else "fallback_conservative_volume_from_metric_dims"
        else:
            shape_policy = "semantic_part_layout_from_prior_dims" if prior_dims_used else "semantic_part_layout_from_metric_dims"
    else:
        builder(mesh)
        visual_shape_conditioning = None
        shape_policy = "template_prior"

    return {
        "input_label": str(label or ""),
        "archetype": archetype,
        "resolution_status": status,
        "shape_policy": shape_policy,
        "metric_dims_source": metric_dims_source,
        "effective_dims_m": effective_dims,
        "shape_evidence": derived,
        "visual_part_evidence": normalize_visual_part_evidence(visual_part_evidence),
        "visual_shape_conditioning": visual_shape_conditioning,
        "explicit_metric_dims": explicit_dims is not None,
        "semantic_prior_dims_used": prior_dims_used,
    }


def normalize_world_pose(world_pose, coordinate_frame=None):
    if not isinstance(world_pose, dict):
        return None
    x = as_float(first_present(world_pose, ("x", "east_m", "e")))
    y = as_float(first_present(world_pose, ("y", "north_m", "n")))
    z = as_float(first_present(world_pose, ("z", "up_m", "u"), 0.0))
    if (x is None or y is None) and isinstance(world_pose.get("world_m"), (list, tuple)):
        values = world_pose.get("world_m")
        if len(values) >= 2:
            x = as_float(values[0])
            y = as_float(values[1])
            z = as_float(values[2]) if len(values) >= 3 else z
    if x is None or y is None:
        return None
    return {
        "position": {"x": x, "y": y, "z": z if z is not None else 0.0},
        "coordinate_frame": coordinate_frame or world_pose.get("coordinate_frame") or world_pose.get("frame") or "local_world_m",
    }


def normalize_observation_uncertainty(value):
    if not isinstance(value, dict):
        return None

    def finite_or_none(raw):
        out = as_float(raw)
        if out is None or not math.isfinite(out):
            return None
        return out

    covariance = value.get("covariance_local_enu_m2")
    covariance_out = None
    if isinstance(covariance, list) and len(covariance) == 3:
        rows = []
        valid = True
        for row in covariance:
            if not isinstance(row, list) or len(row) != 3:
                valid = False
                break
            vals = [finite_or_none(item) for item in row]
            if any(item is None for item in vals):
                valid = False
                break
            rows.append([float(item) for item in vals])
        if valid:
            covariance_out = rows

    return {
        "uncertainty_schema": str(value.get("uncertainty_schema") or "SPPA-UNCERTAINTY-0.1"),
        "position_sigma_m": finite_or_none(value.get("position_sigma_m")),
        "scale_sigma_m": finite_or_none(value.get("scale_sigma_m")),
        "yaw_sigma_deg": finite_or_none(value.get("yaw_sigma_deg")),
        "fallback_inflation_m": finite_or_none(value.get("fallback_inflation_m")),
        "covariance_local_enu_m2": covariance_out,
        "visual_policy": str(value.get("visual_policy") or "unspecified_uncertainty_visual_policy"),
        "telemetry_measured": bool(value.get("telemetry_measured", False)),
        "quality_flags": value.get("quality_flags") if isinstance(value.get("quality_flags"), dict) else {},
    }


def velocity_yaw(prev_world_pose, world_pose, thresholds=None):
    thresholds = normalize_scheduler_thresholds(thresholds)
    prev = normalize_world_pose(prev_world_pose)
    curr = normalize_world_pose(world_pose)
    if not prev or not curr:
        return None
    dx = curr["position"]["x"] - prev["position"]["x"]
    dy = curr["position"]["y"] - prev["position"]["y"]
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < float(thresholds.get("velocity_min_delta_m", 0.05)):
        return None
    yaw = math.atan2(dy, dx)
    if yaw < 0:
        yaw += 2.0 * math.pi
    return {"yaw_rad": yaw, "yaw_deg": math.degrees(yaw), "delta_m": dist}


def resolve_yaw(yaw_deg=None, heading_deg=None, mask=None, world_pose=None, prev_world_pose=None, thresholds=None):
    explicit_yaw = as_float(yaw_deg)
    if explicit_yaw is not None:
        yaw_rad = math.radians(explicit_yaw % 360.0)
        return {
            "yaw_rad": yaw_rad,
            "yaw_deg": explicit_yaw % 360.0,
            "yaw_source": "explicit_yaw_input",
            "yaw_modulo": "2pi",
            "yaw_ambiguous": False,
        }
    explicit_heading = as_float(heading_deg)
    if explicit_heading is not None:
        yaw_rad = math.radians(explicit_heading % 360.0)
        return {
            "yaw_rad": yaw_rad,
            "yaw_deg": explicit_heading % 360.0,
            "yaw_source": "telemetry_heading",
            "yaw_modulo": "2pi",
            "yaw_ambiguous": False,
        }
    vel = velocity_yaw(prev_world_pose, world_pose, thresholds)
    if vel is not None:
        return {
            "yaw_rad": vel["yaw_rad"],
            "yaw_deg": vel["yaw_deg"],
            "yaw_source": "track_velocity",
            "yaw_modulo": "2pi",
            "yaw_ambiguous": False,
            "velocity_delta_m": vel["delta_m"],
        }
    mask_meta = normalize_mask(mask)
    if mask_meta and mask_meta.get("pca_yaw_rad_axial") is not None:
        yaw_rad = mask_meta["pca_yaw_rad_axial"]
        return {
            "yaw_rad": yaw_rad,
            "yaw_deg": math.degrees(yaw_rad),
            "yaw_source": "mask_pca_axial",
            "yaw_modulo": "pi",
            "yaw_ambiguous": True,
        }
    return {
        "yaw_rad": None,
        "yaw_deg": None,
        "yaw_source": "none",
        "yaw_modulo": "none",
        "yaw_ambiguous": True,
    }


def visual_profile_orientation(visual_role_support):
    if not isinstance(visual_role_support, dict) or not visual_role_support.get("applied"):
        return None
    profile = visual_role_support.get("geometry_profile")
    if not isinstance(profile, dict) or not profile.get("applied"):
        return None
    round_pair = profile.get("round_pair") if isinstance(profile.get("round_pair"), dict) else None
    if round_pair:
        angle = as_float(round_pair.get("axis_angle_deg"))
        score = as_float(round_pair.get("score"))
        if angle is not None:
            angle = angle % 180.0
            return {
                "version": VISUAL_ORIENTATION_VERSION,
                "yaw_rad": math.radians(angle),
                "yaw_deg": angle,
                "yaw_source": "visual_round_pair_axis_image_space",
                "yaw_modulo": "pi",
                "yaw_ambiguous": True,
                "coordinate_frame": "image_space_px",
                "confidence": clamp01(score, 0.55),
                "policy": "used_only_when_no_metric_or_mask_yaw_is_available",
                "claim_boundary": "Image-space axial orientation from generic visual primitive cues; not world yaw without camera/ground projection.",
            }
    line_structure = profile.get("line_structure") if isinstance(profile.get("line_structure"), dict) else None
    if line_structure:
        angle = as_float(line_structure.get("dominant_angle_deg"))
        weight = as_float(line_structure.get("dominant_weight_fraction"))
        coherent = bool(line_structure.get("coherent") or line_structure.get("multi_orientation_structure"))
        if angle is not None and coherent:
            angle = angle % 180.0
            return {
                "version": VISUAL_ORIENTATION_VERSION,
                "yaw_rad": math.radians(angle),
                "yaw_deg": angle,
                "yaw_source": "visual_line_axis_image_space",
                "yaw_modulo": "pi",
                "yaw_ambiguous": True,
                "coordinate_frame": "image_space_px",
                "confidence": clamp01(weight, 0.50),
                "policy": "used_only_when_no_metric_or_mask_yaw_is_available",
                "claim_boundary": "Image-space axial orientation from generic visual primitive cues; not world yaw without camera/ground projection.",
            }
    return None


def fuse_yaw_with_visual_profile(yaw, visual_role_support):
    if isinstance(yaw, dict) and yaw.get("yaw_source") != "none":
        return yaw
    visual = visual_profile_orientation(visual_role_support)
    if visual:
        return visual
    return yaw


def mesh_triangle_count(mesh):
    return sum(max(0, len(indices) - 2) for indices, _ in mesh.faces)


def mesh_bounds(mesh):
    if not mesh.vertices:
        return None
    xs = [v[0] for v in mesh.vertices]
    ys = [v[1] for v in mesh.vertices]
    zs = [v[2] for v in mesh.vertices]
    return {
        "min": [min(xs), min(ys), min(zs)],
        "max": [max(xs), max(ys), max(zs)],
        "extent": [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)],
    }


def archetype_signature(mesh, build_meta):
    role_counts = {}
    primitive_counts = {}
    for part in mesh.parts:
        role = str(part.get("role") or part.get("material_role") or "unknown")
        primitive = str(part.get("primitive") or "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1
        primitive_counts[primitive] = primitive_counts.get(primitive, 0) + 1
    return {
        "archetype": build_meta.get("archetype", "unknown"),
        "resolution_status": build_meta.get("resolution_status", "unknown"),
        "shape_policy": build_meta.get("shape_policy", "template_prior"),
        "part_count": len(mesh.parts),
        "triangle_budget": mesh_triangle_count(mesh),
        "role_counts": dict(sorted(role_counts.items())),
        "primitive_counts": dict(sorted(primitive_counts.items())),
    }


def descriptor_topology_signature(mesh, build_meta):
    """Stable cache identity for the reviewed part layout, excluding per-frame state."""
    layout = []
    for part in mesh.parts:
        local_pose = part.get("local_pose") if isinstance(part.get("local_pose"), dict) else {}
        entry = {
            "role": str(part.get("role") or part.get("material_role") or "unknown"),
            "primitive": str(part.get("primitive") or "unknown"),
            "axis": str(local_pose.get("axis") or "z"),
            "material_role": str(part.get("material_role") or part.get("role") or "unknown"),
        }
        if part.get("segments") is not None:
            entry["segments"] = int(part.get("segments"))
        layout.append(entry)
    return {
        "archetype": build_meta.get("archetype", "unknown"),
        "resolution_status": build_meta.get("resolution_status", "unknown"),
        "shape_policy": build_meta.get("shape_policy", "template_prior"),
        "topology_version": ARCHETYPE_VERSION,
        "part_layout": layout,
    }


def descriptor_shape_vector(descriptor):
    scale = descriptor.get("scale", {})
    dims = scale.get("dims_m")
    if isinstance(dims, dict):
        return [dims.get("length"), dims.get("width"), dims.get("height")]
    footprint = scale.get("footprint_px")
    if isinstance(footprint, dict):
        return [footprint.get("length"), footprint.get("width")]
    bbox = scale.get("bbox_px")
    if isinstance(bbox, dict):
        return [bbox.get("w"), bbox.get("h")]
    return []


def shape_vector_changed(prev_descriptor, curr_descriptor, threshold_ratio):
    prev = descriptor_shape_vector(prev_descriptor)
    curr = descriptor_shape_vector(curr_descriptor)
    for a, b in zip(prev, curr):
        if a is None or b is None:
            continue
        denom = max(abs(float(a)), 1e-6)
        if abs(float(b) - float(a)) / denom >= threshold_ratio:
            return True
    return False


def confidence_bucket(confidence, step):
    step = max(float(step), 1e-6)
    return int(round(clamp01(confidence) / step))


def normalize_scheduler_thresholds(thresholds=None):
    merged = dict(DEFAULT_SCHEDULER_THRESHOLDS)
    if thresholds:
        for key, value in dict(thresholds).items():
            if key not in DEFAULT_SCHEDULER_THRESHOLDS:
                raise ValueError(f"Unknown SPPA scheduler threshold: {key}")
            numeric = float(value)
            low, high = SCHEDULER_THRESHOLD_LIMITS[key]
            if numeric < low or numeric > high:
                raise ValueError(f"SPPA scheduler threshold {key}={numeric} outside [{low}, {high}]")
            merged[key] = numeric
    return merged


def build_scheduler_policy(thresholds=None):
    normalized = normalize_scheduler_thresholds(thresholds)
    return {
        "policy_id": SCHEDULER_POLICY_ID,
        "policy_version": POLICY_VERSION,
        "thresholds": normalized,
        "threshold_limits": SCHEDULER_THRESHOLD_LIMITS,
        "threshold_rationale": {
            "shape_ratio": "shape_param_update when any metric shape dimension changes by this relative ratio",
            "confidence_bucket_step": "pose_update when confidence crosses this bucket size",
            "velocity_min_delta_m": "minimum displacement before track velocity is accepted as signed yaw evidence",
        },
        "geometry_fitting_objective": {
            "status": "specified_defaults_not_empirically_tuned",
            "weights": DEFAULT_GEOMETRY_FITTING_WEIGHTS,
            "limits": DEFAULT_GEOMETRY_FITTING_LIMITS,
        },
    }


def schedule_descriptor_update(prev_descriptor, curr_descriptor, thresholds=None, min_confidence=0.0):
    thresholds = normalize_scheduler_thresholds(thresholds)
    confidence = curr_descriptor.get("semantic", {}).get("class_confidence")
    if confidence is not None and float(confidence) < float(min_confidence):
        return {
            "action": "drop_low_confidence",
            "reason": f"class_confidence_lt_{float(min_confidence):.2f}",
            "thresholds": thresholds,
        }
    if prev_descriptor is None:
        return {"action": "create", "reason": "first_descriptor_for_track", "thresholds": thresholds}
    prev_sem = prev_descriptor.get("semantic", {})
    curr_sem = curr_descriptor.get("semantic", {})
    if curr_sem.get("archetype") != prev_sem.get("archetype"):
        return {"action": "regenerate_topology", "reason": "archetype_change", "thresholds": thresholds}
    if curr_sem.get("resolution_status") != prev_sem.get("resolution_status"):
        return {"action": "regenerate_topology", "reason": "resolution_status_change", "thresholds": thresholds}
    if shape_vector_changed(prev_descriptor, curr_descriptor, float(thresholds["shape_ratio"])):
        return {
            "action": "shape_param_update",
            "reason": f"shape_ratio_ge_{float(thresholds['shape_ratio']):.2f}",
            "thresholds": thresholds,
        }
    step = float(thresholds["confidence_bucket_step"])
    prev_bucket = confidence_bucket(prev_sem.get("class_confidence", 0.0), step)
    curr_bucket = confidence_bucket(curr_sem.get("class_confidence", 0.0), step)
    if prev_descriptor.get("pose") != curr_descriptor.get("pose") or prev_bucket != curr_bucket:
        return {"action": "pose_update", "reason": "pose_yaw_or_confidence_bucket_change", "thresholds": thresholds}
    return {"action": "no_op", "reason": "descriptor_equivalent_under_policy", "thresholds": thresholds}


def build_sppa_descriptor(
    mesh,
    build_meta,
    confidence=1.0,
    bbox=None,
    mask=None,
    world_pose=None,
    prev_world_pose=None,
    camera_pose=None,
    calibration_ref=None,
    image_width=None,
    image_height=None,
    dims_m=None,
    yaw_deg=None,
    heading_deg=None,
    track_id=None,
    timestamp=None,
    frame_id=None,
    track_age_s=None,
    track_seen_count=None,
    source_log=None,
    source_event_index=None,
    previous_descriptor_id=None,
    thresholds=None,
    observed_color=None,
    observation_contract=None,
    observation_uncertainty=None,
    visual_metric_yaw_consistency=None,
    create_cpu_us=None,
    export_cpu_us_if_any=None,
):
    start_ns = time.perf_counter_ns()
    thresholds = normalize_scheduler_thresholds(thresholds)
    scheduler_policy = build_scheduler_policy(thresholds)
    confidence = clamp01(confidence, 1.0)
    raw_label = build_meta.get("input_label", "")
    normalized_label = str(raw_label or "").strip().lower()
    resolution_status = build_meta.get("resolution_status", "unknown")
    resolver_contract = build_resolver_contract(raw_label, normalized_label, build_meta.get("archetype", "unknown"), resolution_status)
    unknown_label = resolution_status.startswith("fallback")
    bbox_px = normalize_bbox(bbox)
    mask_meta = normalize_mask(mask)
    pose_world = normalize_world_pose(world_pose)
    yaw = resolve_yaw(yaw_deg, heading_deg, mask, world_pose, prev_world_pose, thresholds)
    metric_dims = parse_dims_arg(dims_m)
    metric_dims_source = build_meta.get("metric_dims_source") or ("metric_dims_input" if metric_dims else None)
    observed_color_meta = normalize_observed_color(observed_color)
    observation_contract_meta = observation_contract if isinstance(observation_contract, dict) else None
    uncertainty_input = observation_uncertainty
    if uncertainty_input is None and observation_contract_meta:
        uncertainty_input = observation_contract_meta.get("uncertainty")
    observation_uncertainty_meta = normalize_observation_uncertainty(uncertainty_input)
    visual_role_support = visual_part_role_support(mesh, build_meta.get("visual_part_evidence"))
    visual_shape_conditioning = build_meta.get("visual_shape_conditioning")
    visual_metric_yaw_consistency_meta = normalize_visual_metric_yaw_consistency(visual_metric_yaw_consistency)
    visual_metric_yaw = yaw_from_visual_metric_consistency(visual_metric_yaw_consistency_meta, pose_world)
    if visual_metric_yaw is not None and yaw.get("yaw_source") == "none":
        yaw = visual_metric_yaw
    yaw = fuse_yaw_with_visual_profile(yaw, visual_role_support)
    image_width_value = as_int(image_width)
    image_height_value = as_int(image_height)

    evidence_sources = ["semantic_label"]
    if bbox_px:
        evidence_sources.append("bbox")
    if mask_meta:
        evidence_sources.append("mask_polygon")
    if pose_world:
        evidence_sources.append("world_pose")
    if yaw["yaw_source"] != "none":
        evidence_sources.append(yaw["yaw_source"])
    if metric_dims:
        evidence_sources.append(metric_dims_source or "metric_dims_input")
    if observed_color_meta:
        evidence_sources.append("observed_color_input")
    if visual_role_support and visual_role_support.get("applied"):
        evidence_sources.append("visual_part_evidence")
    if isinstance(visual_shape_conditioning, dict) and visual_shape_conditioning.get("applied"):
        evidence_sources.append("visual_shape_conditioning")
    if visual_metric_yaw_consistency_meta and visual_metric_yaw_consistency_meta.get("applied"):
        evidence_sources.append("visual_metric_yaw_consistency")

    footprint_px = None
    if mask_meta:
        oriented = mask_meta.get("oriented_footprint_px")
        if oriented:
            footprint_px = {
                "length": oriented["length"],
                "width": oriented["width"],
                "source": oriented["source"],
                "orientation_rad_axial": oriented["orientation_rad_axial"],
                "orientation_deg_axial": oriented["orientation_deg_axial"],
                "orientation_modulo": oriented["orientation_modulo"],
                "fill_ratio": oriented["fill_ratio"],
            }
        else:
            mb = mask_meta["bbox_px"]
            footprint_px = {"length": mb["w"], "width": mb["h"], "source": "mask_bbox"}
    elif bbox_px:
        footprint_px = {"length": bbox_px["w"], "width": bbox_px["h"], "source": "bbox_px"}

    if metric_dims:
        scale_source = metric_dims_source or "metric_dims_input"
        if scale_source == "metric_dims_input":
            scale_uncertainty = "external_metric_input_not_verified_by_sppa"
        elif scale_source == "semantic_prior_dims":
            scale_uncertainty = "semantic_archetype_prior_not_metric_measurement"
        elif str(scale_source).startswith("calibrated_"):
            scale_uncertainty = "derived_from_supplied_image_scale_height_may_be_prior"
        else:
            scale_uncertainty = "metric_dims_source_unvalidated_by_sppa"
    elif mask_meta:
        scale_source = "mask_footprint_px"
        scale_uncertainty = "image_space_only_no_metric_calibration"
    elif bbox_px:
        scale_source = "bbox_px"
        scale_uncertainty = "image_space_only_no_metric_calibration"
    else:
        scale_source = "template_prior"
        scale_uncertainty = "semantic_archetype_prior_only"

    source_payload = {
        "label": raw_label,
        "confidence": confidence,
        "track_id": track_id,
        "timestamp": timestamp,
        "bbox": bbox_px,
        "mask_hash": mask_meta.get("hash") if mask_meta else None,
        "world_pose": pose_world,
        "image_width": image_width_value,
        "image_height": image_height_value,
        "dims_m": metric_dims,
        "metric_dims_source": metric_dims_source,
        "shape_evidence": build_meta.get("shape_evidence"),
        "visual_part_evidence": visual_role_support,
        "visual_shape_conditioning": visual_shape_conditioning,
        "visual_metric_yaw_consistency": visual_metric_yaw_consistency_meta,
        "yaw": yaw,
        "observed_color": observed_color_meta,
        "observation_contract": observation_contract_meta,
        "observation_uncertainty": observation_uncertainty_meta,
        "source_log": source_log,
        "source_event_index": source_event_index,
    }
    input_hash = stable_hash(source_payload)
    material_source = (
        "fallback_unknown"
        if unknown_label
        else ("observed_color_input" if observed_color_meta else "semantic_prior")
    )
    descriptor_parts = descriptor_parts_with_material_evidence(mesh.parts, None if unknown_label else observed_color_meta)
    descriptor_parts = descriptor_parts_with_visual_part_evidence(descriptor_parts, visual_role_support)
    topology_signature = descriptor_topology_signature(mesh, build_meta)
    topology_hash = stable_hash(topology_signature)
    descriptor_id = f"sppa-{topology_hash}"
    cache_key = str(track_id or f"{normalized_label}:{topology_hash}")

    descriptor = {
        "descriptor_schema": SPPA_DESCRIPTOR_VERSION,
        "descriptor_id": descriptor_id,
        "generator_version": GENERATOR_VERSION,
        "ontology_version": ONTOLOGY_VERSION,
        "archetype_version": ARCHETYPE_VERSION,
        "policy_version": POLICY_VERSION,
        "created_utc": utc_now(),
        "input_hash": input_hash,
        "topology_hash": topology_hash,
        "source_log": source_log,
        "source_event_index": source_event_index,
        "input": {
            "raw_label": raw_label,
            "normalized_label": normalized_label,
            "confidence": confidence,
        },
        "resolver": resolver_contract,
        "track": {
            "track_id": track_id,
            "timestamp": timestamp,
            "frame_id": frame_id,
            "track_age_s": as_float(track_age_s),
            "track_seen_count": as_int(track_seen_count),
            "previous_descriptor_id": previous_descriptor_id,
        },
        "semantic": {
            "raw_label": raw_label,
            "normalized_label": normalized_label,
            "class_confidence": confidence,
            "archetype": build_meta.get("archetype", "unknown"),
            "resolution_status": resolution_status,
            "match_type": resolver_contract["match_type"],
            "fallback_reason": resolution_status if unknown_label else None,
            "unknown_label": unknown_label,
        },
        "archetype_signature": archetype_signature(mesh, build_meta),
        "topology_signature": topology_signature,
        "evidence": {
            "evidence_sources": evidence_sources,
            "bbox_px": bbox_px,
            "image_width": image_width_value,
            "image_height": image_height_value,
            "image_size_px": {
                "width": image_width_value,
                "height": image_height_value,
            },
            "mask_ref_or_polygon": mask_meta,
            "mask_hash": mask_meta.get("hash") if mask_meta else None,
            "world_pose": pose_world,
            "camera_pose": camera_pose,
            "calibration_ref": calibration_ref,
            "observed_color": observed_color_meta,
            "observation_contract": observation_contract_meta,
            "visual_part_evidence": visual_role_support,
            "visual_shape_conditioning": visual_shape_conditioning,
            "visual_metric_yaw_consistency": visual_metric_yaw_consistency_meta,
        },
        "material": {
            "material_policy": "role_priors_with_optional_observed_color",
            "texture_policy": "none_procedural_materials_only",
            "material_source": material_source,
            "observed_color": observed_color_meta,
            "observed_color_role_policy": "observable_semantic_roles_only",
            "observed_color_role_count": len(OBSERVED_COLOR_TARGET_ROLES),
            "observed_color_applied": bool(observed_color_meta and not unknown_label),
            "semantic_priors_retained_for_non_observable_roles": True,
        },
        "pose": {
            "position_world": pose_world.get("position") if pose_world else None,
            "coordinate_frame": pose_world.get("coordinate_frame") if pose_world else None,
            "yaw_rad": yaw.get("yaw_rad"),
            "yaw_deg": yaw.get("yaw_deg"),
            "yaw_source": yaw.get("yaw_source"),
            "yaw_modulo": yaw.get("yaw_modulo"),
            "yaw_ambiguous": yaw.get("yaw_ambiguous"),
            "yaw_coordinate_frame": yaw.get("coordinate_frame", pose_world.get("coordinate_frame") if pose_world else None),
            "yaw_confidence": yaw.get("confidence"),
            "yaw_policy": yaw.get("policy"),
            "yaw_claim_boundary": yaw.get("claim_boundary"),
            "yaw_version": yaw.get("version"),
            "pose_uncertainty": "unvalidated_input" if pose_world else "missing_world_pose",
        },
        "scale": {
            "dims_m": metric_dims,
            "effective_dims_m": build_meta.get("effective_dims_m"),
            "metric_dims_source": metric_dims_source,
            "footprint_m": {"length": metric_dims["length"], "width": metric_dims["width"]} if metric_dims else None,
            "footprint_px": footprint_px,
            "bbox_px": bbox_px,
            "bbox_aspect": bbox_px.get("aspect") if bbox_px else None,
            "mask_area_px2": mask_meta.get("area_px2") if mask_meta else None,
            "mask_oriented_footprint_px": mask_meta.get("oriented_footprint_px") if mask_meta else None,
            "scale_source": scale_source,
            "scale_uncertainty": scale_uncertainty,
            "shape_evidence": build_meta.get("shape_evidence"),
            "visual_part_evidence": visual_role_support,
            "visual_shape_conditioning": visual_shape_conditioning,
            "shape_policy": build_meta.get("shape_policy", "template_prior"),
            "part_layout_from_dims": build_meta.get("shape_policy") in {
                "semantic_part_layout_from_metric_dims",
                "semantic_part_layout_from_prior_dims",
                "verified_open_label_part_layout_from_metric_dims",
                "verified_open_label_part_layout_from_prior_dims",
            },
        },
        "uncertainty": {
            "shape_low_confidence": confidence < 0.50,
            "yaw_ambiguous": yaw.get("yaw_ambiguous"),
            "fallback_unknown": unknown_label,
            "scale_from_bbox": scale_source == "bbox_px",
            "scale_from_mask": scale_source == "mask_footprint_px",
            "scale_from_dims": metric_dims is not None,
            "scale_from_semantic_prior": scale_source == "semantic_prior_dims",
            "scale_from_calibrated_footprint": str(scale_source).startswith("calibrated_"),
            "shape_source": scale_source,
            "material_source": material_source,
            "material_from_prior": True,
            "material_from_observation": bool(observed_color_meta and not unknown_label),
            "material_uses_role_priors": True,
            "texture_from_observation": False,
            "confidence": confidence,
            "observation_schema": observation_uncertainty_meta.get("uncertainty_schema") if observation_uncertainty_meta else None,
            "position_sigma_m": observation_uncertainty_meta.get("position_sigma_m") if observation_uncertainty_meta else None,
            "scale_sigma_m": observation_uncertainty_meta.get("scale_sigma_m") if observation_uncertainty_meta else None,
            "yaw_sigma_deg": observation_uncertainty_meta.get("yaw_sigma_deg") if observation_uncertainty_meta else None,
            "fallback_inflation_m": observation_uncertainty_meta.get("fallback_inflation_m") if observation_uncertainty_meta else None,
            "covariance_local_enu_m2": observation_uncertainty_meta.get("covariance_local_enu_m2") if observation_uncertainty_meta else None,
            "visual_policy": observation_uncertainty_meta.get("visual_policy") if observation_uncertainty_meta else None,
            "visual_metric_yaw_agreement": visual_metric_yaw_consistency_meta.get("agreement")
            if visual_metric_yaw_consistency_meta
            else None,
            "telemetry_measured": observation_uncertainty_meta.get("telemetry_measured") if observation_uncertainty_meta else None,
            "quality_flags": observation_uncertainty_meta.get("quality_flags") if observation_uncertainty_meta else None,
        },
        "parts": descriptor_parts,
        "runtime_policy": {
            "cache_key": cache_key,
            "action": "unapplied",
            "action_reason": "schedule_descriptor_update_not_called",
            "scheduler_policy": scheduler_policy,
            "thresholds": thresholds,
            "regenerate_if": ["archetype_change", "resolution_status_change"],
            "param_update_if": [f"shape_ratio_ge_{float(thresholds['shape_ratio']):.2f}"],
            "per_frame_update_fields": ["position_world", "yaw", "confidence", "visibility"],
            "create_once_per_track": True,
            "confidence_bucket": confidence_bucket(confidence, thresholds["confidence_bucket_step"]),
        },
        "mesh": {
            "template_bounds": mesh_bounds(mesh),
            "vertices": len(mesh.vertices),
            "faces": len(mesh.faces),
            "triangles": mesh_triangle_count(mesh),
        },
        "cost": {
            "create_cpu_us": create_cpu_us,
            "descriptor_build_cpu_us": None,
            "update_cpu_us": None,
            "export_cpu_us_if_any": export_cpu_us_if_any,
            "triangles": mesh_triangle_count(mesh),
            "descriptor_bytes": None,
        },
    }
    elapsed_us = (time.perf_counter_ns() - start_ns) / 1000.0
    descriptor["cost"]["descriptor_build_cpu_us"] = elapsed_us
    descriptor["cost"]["descriptor_bytes"] = len(canonical_json_bytes(descriptor))
    return descriptor


def apply_schedule_to_descriptor(descriptor, decision):
    descriptor["runtime_policy"]["action"] = decision["action"]
    descriptor["runtime_policy"]["action_reason"] = decision["reason"]
    thresholds = normalize_scheduler_thresholds(decision["thresholds"])
    descriptor["runtime_policy"]["thresholds"] = thresholds
    descriptor["runtime_policy"]["scheduler_policy"] = build_scheduler_policy(thresholds)
    descriptor["cost"]["descriptor_bytes"] = len(canonical_json_bytes(descriptor))
    return descriptor


def build_runtime_update_packet(descriptor, decision=None):
    decision = decision or {
        "action": descriptor.get("runtime_policy", {}).get("action", "unapplied"),
        "reason": descriptor.get("runtime_policy", {}).get("action_reason", "unknown"),
        "thresholds": descriptor.get("runtime_policy", {}).get("thresholds", DEFAULT_SCHEDULER_THRESHOLDS),
    }
    action = decision["action"]
    thresholds = normalize_scheduler_thresholds(decision.get("thresholds"))
    packet = {
        "packet_schema": SPPA_UPDATE_PACKET_VERSION,
        "descriptor_schema": descriptor.get("descriptor_schema"),
        "descriptor_id": descriptor.get("descriptor_id"),
        "cache_key": descriptor.get("runtime_policy", {}).get("cache_key"),
        "action": action,
        "reason": decision.get("reason"),
        "thresholds": thresholds,
        "scheduler_policy": build_scheduler_policy(thresholds),
        "track": descriptor.get("track"),
        "semantic": {
            "archetype": descriptor.get("semantic", {}).get("archetype"),
            "resolution_status": descriptor.get("semantic", {}).get("resolution_status"),
            "class_confidence": descriptor.get("semantic", {}).get("class_confidence"),
            "unknown_label": descriptor.get("semantic", {}).get("unknown_label"),
        },
        "pose": descriptor.get("pose"),
        "uncertainty": descriptor.get("uncertainty"),
    }
    if action in ("create", "regenerate_topology", "shape_param_update"):
        packet["scale"] = descriptor.get("scale")
        packet["parts"] = descriptor.get("parts")
        packet["mesh"] = descriptor.get("mesh")
    packet["packet_bytes"] = len(canonical_json_bytes(packet))
    return packet


def write_sppa_descriptor(descriptor_path, mesh, build_meta, confidence=1.0, **kwargs):
    descriptor = build_sppa_descriptor(mesh, build_meta, confidence, **kwargs)
    with open(descriptor_path, "w", encoding="ascii") as f:
        json.dump(descriptor, f, indent=2, sort_keys=True)
        f.write("\n")
    return descriptor


def write_mtl(mtl_path, material_manifest=None):
    manifest_by_name = {}
    if isinstance(material_manifest, dict):
        manifest_by_name = {
            str(item.get("name", "")): item
            for item in material_manifest.get("materials", [])
            if item.get("name")
        }
    with open(mtl_path, "w", encoding="ascii") as f:
        f.write(f"# SPPA material descriptor schema: {MATERIAL_DESCRIPTOR_VERSION}\n")
        f.write("# Materials are procedural semantic priors or explicit unknown fallbacks, not observed texture evidence.\n")
        for name, rgb in MATERIALS.items():
            meta = get_material_metadata(name)
            manifest_item = manifest_by_name.get(name, {})
            if manifest_item:
                rgb = manifest_item.get("rgb", rgb)
            f.write(f"newmtl {name}\n")
            f.write(f"# sppa_material_role {meta['material_role']}\n")
            f.write(f"# sppa_evidence_source {manifest_item.get('evidence_source', meta['evidence_source'])}\n")
            f.write(f"# sppa_uncertainty_visual_style {manifest_item.get('uncertainty_visual_style', meta['uncertainty_visual_style'])}\n")
            if "semantic_prior_rgb" in manifest_item:
                prior = manifest_item["semantic_prior_rgb"]
                f.write(f"# sppa_semantic_prior_rgb {prior[0]:.6f} {prior[1]:.6f} {prior[2]:.6f}\n")
            if "observed_color_rgb" in manifest_item:
                observed = manifest_item["observed_color_rgb"]
                f.write(f"# sppa_observed_color_rgb {observed[0]:.6f} {observed[1]:.6f} {observed[2]:.6f}\n")
            f.write(f"Kd {rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f}\n")
            f.write("Ka 0.050 0.050 0.050\n")
            f.write("Ks 0.120 0.120 0.120\n")
            f.write(f"d {float(manifest_item.get('alpha', meta.get('alpha', 1.0))):.3f}\n\n")


def main():
    parser = argparse.ArgumentParser(description="XYT instant primitive 3D generator")
    parser.add_argument("word", help="cow, biker, tree, car, truck")
    parser.add_argument("--out-dir", default=".")
    parser.add_argument("--confidence", type=float, default=1.0, help="Detector confidence used only for material-evidence metadata")
    parser.add_argument("--descriptor-out", default=None, help="Optional explicit SPPA-DESC JSON output path")
    parser.add_argument("--bbox-json", default=None, help="BBox JSON literal or file path; supports x/y/w/h or x1/y1/x2/y2")
    parser.add_argument("--mask-json", default=None, help="Mask polygon JSON literal or file path; list of [x,y] points or {'polygon': ...}")
    parser.add_argument("--world-json", default=None, help="World pose JSON literal or file path; x/y/z or world_m")
    parser.add_argument("--prev-world-json", default=None, help="Previous world pose for velocity-derived yaw")
    parser.add_argument("--camera-json", default=None, help="Optional camera pose/calibration context JSON literal or file path")
    parser.add_argument("--calibration-ref", default=None, help="Opaque calibration reference; no metric scale is inferred without explicit dims or metric scale")
    parser.add_argument("--metric-scale-json", default=None, help="Metric image scale JSON/literal/file; supports meters_per_pixel or pixels_per_meter")
    parser.add_argument("--height-m", type=float, default=None, help="Optional object height for calibrated bbox/mask footprint adaptation")
    parser.add_argument("--image-width", type=int, default=None, help="Source image width in pixels for bbox/mask context")
    parser.add_argument("--image-height", type=int, default=None, help="Source image height in pixels for bbox/mask context")
    parser.add_argument("--dims-m", default=None, help="Explicit metric dims as length,width,height or JSON")
    parser.add_argument("--yaw-deg", type=float, default=None, help="Explicit object yaw in degrees; treated as signed 2pi evidence")
    parser.add_argument("--heading-deg", type=float, default=None, help="Telemetry heading in degrees; used if yaw is absent")
    parser.add_argument("--track-id", default=None)
    parser.add_argument("--timestamp", default=None)
    parser.add_argument("--frame-id", default=None)
    parser.add_argument("--track-age-s", default=None)
    parser.add_argument("--track-seen-count", default=None)
    parser.add_argument("--source-log", default=None)
    parser.add_argument("--source-event-index", default=None)
    parser.add_argument("--observed-color", default=None, help="Optional observed RGB evidence: #RRGGBB, r,g,b, JSON literal, or JSON file")
    parser.add_argument("--visual-part-evidence-json", default=None, help="Optional generic visual part evidence JSON/literal/file from an agnostic cue extractor")
    parser.add_argument("--threshold-json", default=None, help="Scheduler threshold override JSON literal or file path")
    parser.add_argument("--mesh-lod", default=None, help="Mesh LOD: high|balanced|ultra_light|auto (use-case policy)")
    parser.add_argument("--budget-mode", default=None, help="Budget mode for auto LOD: auto|quality|balanced|ultra_light")
    parser.add_argument("--distance-m", type=float, default=None, help="Optional viewer/object distance for use-case LOD policy")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    name = safe_name(args.word)
    obj_path = os.path.join(args.out_dir, f'{name}.obj')
    mtl_path = os.path.join(args.out_dir, f'{name}.mtl')
    manifest_path = os.path.join(args.out_dir, f'{name}.materials.json')
    descriptor_path = args.descriptor_out or os.path.join(args.out_dir, f'{name}.descriptor.json')
    dims_arg = parse_dims_cli(args.dims_m)
    bbox_arg = load_json_arg(args.bbox_json)
    mask_arg = load_json_arg(args.mask_json)
    world_arg = load_json_arg(args.world_json)
    prev_world_arg = load_json_arg(args.prev_world_json)
    camera_arg = load_json_arg(args.camera_json)
    metric_scale_arg = parse_metric_scale_cli(args.metric_scale_json) or normalize_metric_scale(camera_arg)
    observed_color = parse_observed_color_cli(args.observed_color)
    visual_part_evidence = load_json_arg(args.visual_part_evidence_json)
    lod = select_use_case_mesh_lod(
        confidence=args.confidence,
        distance_m=args.distance_m,
        budget_mode=args.budget_mode,
        explicit_lod=None if str(args.mesh_lod or "").lower() in {"", "auto", "none"} else args.mesh_lod,
        class_confidence=args.confidence,
    )

    mesh = Mesh(lod=lod)
    create_start = time.perf_counter_ns()
    meta = build_label_observed(
        mesh,
        args.word,
        dims_m=dims_arg,
        bbox=bbox_arg,
        mask=mask_arg,
        metric_scale=metric_scale_arg,
        height_m=args.height_m,
        visual_part_evidence=visual_part_evidence,
    )
    meta["mesh_lod"] = lod
    meta["mesh_lod_policy"] = "use_case_auto" if str(args.mesh_lod or "auto").lower() in {"", "auto", "none"} else "explicit"
    create_cpu_us = (time.perf_counter_ns() - create_start) / 1000.0

    export_start = time.perf_counter_ns()
    manifest = write_material_manifest(manifest_path, mesh, meta, args.confidence, observed_color)
    write_mtl(mtl_path, manifest)
    write_obj(mesh, obj_path, os.path.basename(mtl_path))
    export_cpu_us = (time.perf_counter_ns() - export_start) / 1000.0

    thresholds = load_json_arg(args.threshold_json) or {}
    descriptor = write_sppa_descriptor(
        descriptor_path,
        mesh,
        meta,
        args.confidence,
        bbox=bbox_arg,
        mask=mask_arg,
        world_pose=world_arg,
        prev_world_pose=prev_world_arg,
        camera_pose=camera_arg,
        calibration_ref=args.calibration_ref or (metric_scale_arg or {}).get("calibration_ref"),
        image_width=args.image_width,
        image_height=args.image_height,
        dims_m=meta.get("effective_dims_m") or dims_arg,
        yaw_deg=args.yaw_deg,
        heading_deg=args.heading_deg,
        track_id=args.track_id,
        timestamp=args.timestamp,
        frame_id=args.frame_id,
        track_age_s=args.track_age_s,
        track_seen_count=args.track_seen_count,
        source_log=args.source_log,
        source_event_index=as_int(args.source_event_index),
        thresholds=thresholds,
        observed_color=observed_color,
        create_cpu_us=create_cpu_us,
        export_cpu_us_if_any=export_cpu_us,
    )
    print(f'Generado: {obj_path}')
    print(f'Materiales: {mtl_path}')
    print(f'Material manifest: {manifest_path}')
    print(f'SPPA descriptor: {descriptor_path}')
    print(f'SPPA metadata: {meta}')
    print(f'SPPA material policy: {manifest["material_policy"]}')
    print(f'SPPA descriptor schema: {descriptor["descriptor_schema"]}')

if __name__ == "__main__":
    main()
