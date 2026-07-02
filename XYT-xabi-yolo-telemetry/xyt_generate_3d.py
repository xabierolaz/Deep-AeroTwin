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
    "unknown_volume_fallback": (0.55, 0.55, 0.58),
    "unknown_footprint_fallback": (0.38, 0.38, 0.40),
    "uncertainty_marker_fallback": (0.95, 0.72, 0.06),
}

MATERIAL_DESCRIPTOR_VERSION = "SPPA-MAT-0.1"
SPPA_DESCRIPTOR_VERSION = "SPPA-DESC-0.2"
SPPA_UPDATE_PACKET_VERSION = "SPPA-UPD-0.2"
GENERATOR_VERSION = "XYT-SPPA-GEN-0.2"
ONTOLOGY_VERSION = "SPPA-ONTOLOGY-0.2"
ARCHETYPE_VERSION = "SPPA-ARCHETYPE-0.2"
POLICY_VERSION = "SPPA-POLICY-0.2"
DEFAULT_SCHEDULER_THRESHOLDS = {
    "shape_ratio": 0.20,
    "confidence_bucket_step": 0.05,
    "velocity_min_delta_m": 0.05,
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
    "unknown_volume_fallback": _meta("unknown_conservative_volume", "fallback_unknown", "desaturated_unknown", 0.72),
    "unknown_footprint_fallback": _meta("unknown_footprint", "fallback_unknown", "desaturated_unknown", 0.65),
    "uncertainty_marker_fallback": _meta("uncertainty_marker", "fallback_unknown", "warning_marker", 0.85),
}



class Mesh:
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.parts = []

    def add_vertex(self, x, y, z):
        self.vertices.append((x, y, z))
        return len(self.vertices)

    def add_face(self, indices, material):
        self.faces.append((indices, material))

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
        }
        if "segments" in kwargs:
            part["segments"] = int(kwargs["segments"])
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

    def sphere(self, center, scale, material, rings=6, segments=10):
        face_start = len(self.faces)
        cx, cy, cz = center
        sx, sy, sz = scale
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

    def cylinder(self, center, radius, depth, material, axis="z", segments=10):
        face_start = len(self.faces)
        cx, cy, cz = center
        half = depth / 2
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

    def torus(self, center, major, minor, material, axis="x", major_steps=14, minor_steps=6):
        face_start = len(self.faces)
        cx, cy, cz = center
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


def cow(mesh):
    mesh.sphere((0, 0, 1.3), (1.35, 0.55, 0.55), "animal_body_prior")
    mesh.sphere((-0.35, -0.15, 1.45), (0.35, 0.18, 0.18), "animal_marking_prior")
    mesh.sphere((0.45, 0.18, 1.2), (0.32, 0.16, 0.16), "animal_marking_prior")
    mesh.sphere((-0.75, 0.18, 1.55), (0.28, 0.14, 0.16), "animal_marking_prior")
    mesh.sphere((0.15, -0.32, 1.42), (0.30, 0.12, 0.18), "animal_marking_prior")
    mesh.sphere((1.55, 0, 1.35), (0.45, 0.35, 0.32), "animal_body_prior")
    mesh.sphere((1.95, 0, 1.25), (0.25, 0.25, 0.18), "animal_skin_prior")
    for y in (-0.36, 0.36):
        mesh.cone((1.45, y, 1.75), 0.08, 0.35, "animal_skin_prior", axis="y")
    for x in (-0.75, 0.75):
        for y in (-0.34, 0.34):
            mesh.cylinder((x, y, 0.65), 0.10, 1.05, "animal_limb_prior", axis="z")
    mesh.cylinder((-1.45, 0, 1.25), 0.035, 0.8, "animal_limb_prior", axis="x")

def tree(mesh):
    mesh.cylinder((0, 0, 0.75), 0.20, 1.5, "vegetation_trunk_prior", segments=12)
    mesh.sphere((0, 0, 2.05), (0.85, 0.75, 0.65), "vegetation_canopy_dark_prior", rings=6, segments=12)
    mesh.sphere((-0.42, 0.10, 2.32), (0.52, 0.45, 0.42), "vegetation_canopy_light_prior", rings=5, segments=10)
    mesh.sphere((0.42, -0.10, 2.30), (0.52, 0.45, 0.42), "vegetation_canopy_light_prior", rings=5, segments=10)
    mesh.sphere((0, 0, 2.72), (0.48, 0.42, 0.40), "vegetation_canopy_dark_prior", rings=5, segments=10)

def bush(mesh):
    mesh.sphere((0, 0, 0.65), (0.85, 0.65, 0.45), 'vegetation_canopy_dark_prior', rings=5, segments=10)
    mesh.sphere((-0.55, 0.05, 0.72), (0.55, 0.45, 0.38), 'vegetation_canopy_light_prior', rings=5, segments=10)
    mesh.sphere((0.55, -0.05, 0.72), (0.55, 0.45, 0.38), 'vegetation_canopy_light_prior', rings=5, segments=10)
    mesh.sphere((0.0, 0.28, 0.92), (0.55, 0.42, 0.36), 'vegetation_canopy_dark_prior', rings=5, segments=10)
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


def tractor(mesh):
    mesh.box((-0.15, 0, 0.85), (1.45, 1.0, 0.65), 'vehicle_farm_body_prior')
    mesh.box((0.85, 0, 1.18), (0.72, 0.85, 0.8), 'vehicle_farm_body_prior')
    mesh.box((0.92, -0.43, 1.28), (0.42, 0.04, 0.32), 'vehicle_window_prior')
    mesh.box((0.92, 0.43, 1.28), (0.42, 0.04, 0.32), 'vehicle_window_prior')
    mesh.box((-1.05, 0, 1.05), (0.65, 0.75, 0.45), 'vehicle_attachment_prior')
    for y in (-0.58, 0.58):
        mesh.torus((-0.75, y, 0.58), 0.40, 0.10, 'vehicle_tire_prior', axis='y', major_steps=16, minor_steps=6)
        mesh.cylinder((-0.75, y, 0.58), 0.18, 0.10, 'vehicle_attachment_prior', axis='y')
        mesh.torus((0.85, y, 0.48), 0.28, 0.08, 'vehicle_tire_prior', axis='y', major_steps=14, minor_steps=6)
        mesh.cylinder((0.85, y, 0.48), 0.12, 0.08, 'vehicle_attachment_prior', axis='y')
    mesh.cylinder((-0.2, 0, 1.45), 0.07, 0.75, 'vehicle_tire_prior', axis='z')

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
    'biker': biker,
    'cyclist': biker,
    'ciclista': biker,
    'person': biker,
    'pedestrian': biker,
    'bicycle': biker,
    'tree': tree,
    'arbol': tree,
    'bush': bush,
    'arbusto': bush,
    'car': car,
    'coche': car,
    'truck': truck,
    'camion': truck,
    'tractor': tractor,
    'tower': tower,
    'pole': tower,
    'mast': tower,
    'pylon': tower,
    'unknown': unknown_proxy,
}

PARAMETRIC_BUILDERS = {
    'car': car_parametric,
    'coche': car_parametric,
    'light_vehicle': car_parametric,
    'truck': truck_parametric,
    'camion': truck_parametric,
    'heavy_vehicle': truck_parametric,
}

ARCHETYPE_RULES = [
    ('biker', biker, ('biker', 'bike', 'bicycle', 'cyclist', 'rider', 'person', 'pedestrian', 'motorcycle')),
    ('quadruped', cow, ('cow', 'animal', 'dog', 'horse', 'sheep', 'goat', 'deer', 'bull', 'cattle')),
    ('vegetation', tree, ('tree', 'plant', 'vegetation', 'canopy', 'trunk')),
    ('bush', bush, ('bush', 'shrub', 'hedge')),
    ('light_vehicle', car, ('car', 'vehicle', 'van', 'pickup', 'suv', 'taxi', 'ambulance')),
    ('heavy_vehicle', truck, ('truck', 'lorry', 'bus', 'trailer', 'semi')),
    ('farm_vehicle', tractor, ('tractor', 'harvester', 'farm')),
    ('vertical_structure', tower, ('tower', 'pole', 'mast', 'pylon', 'post', 'sign', 'antenna')),
]


def _tokens(label):
    return set(re.findall(r'[a-z0-9]+', label.lower()))


def resolve_builder(label):
    key = str(label or 'unknown').strip().lower()
    if not key:
        return unknown_proxy, 'unknown', 'fallback_empty_label'
    exact = BUILDERS.get(key)
    if exact is not None and exact is not unknown_proxy:
        return exact, key, 'exact_class'
    tokens = _tokens(key)
    for archetype, builder, keywords in ARCHETYPE_RULES:
        for keyword in keywords:
            if keyword in tokens or (' ' in keyword and keyword in key):
                return builder, archetype, 'keyword_archetype'
    return unknown_proxy, 'unknown', 'fallback_unknown_label'


def resolver_match_type(resolution_status):
    if resolution_status == "exact_class":
        return "exact"
    if resolution_status == "keyword_archetype":
        return "keyword"
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
    builder, archetype, status = resolve_builder(label)
    builder(mesh)
    return {'input_label': str(label or ''), 'archetype': archetype, 'resolution_status': status}


def build_label_parametric(mesh, label, dims_m=None):
    builder, archetype, status = resolve_builder(label)
    dims = parse_dims_arg(dims_m)
    parametric_builder = None
    key = str(label or '').strip().lower()
    if dims:
        parametric_builder = PARAMETRIC_BUILDERS.get(key) or PARAMETRIC_BUILDERS.get(archetype)
    if parametric_builder is not None:
        parametric_builder(mesh, dims)
        shape_policy = "semantic_part_layout_from_metric_dims"
    else:
        builder(mesh)
        shape_policy = "template_prior"
    return {
        'input_label': str(label or ''),
        'archetype': archetype,
        'resolution_status': status,
        'shape_policy': shape_policy,
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


def build_material_manifest(mesh, build_meta, confidence=1.0):
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
        materials.append({
            "name": name,
            "rgb": MATERIALS.get(name, (0.45, 0.45, 0.45)),
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
        "material_policy": "evidence_calibrated_procedural_roles",
        "observed_material_policy": "not_used_unless_explicit_sensor_or_operator_evidence_is_provided",
        "materials": materials,
    }


def write_material_manifest(manifest_path, mesh, build_meta, confidence=1.0):
    manifest = build_material_manifest(mesh, build_meta, confidence)
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
    payload = {"points": [[round(x, 6), round(y, 6)] for x, y in points]}
    return {
        "polygon": payload["points"],
        "point_count": len(points),
        "hash": stable_hash(payload),
        "bbox_px": bbox,
        "area_px2": area,
        "pca_yaw_rad_axial": yaw,
        "pca_yaw_deg_axial": math.degrees(yaw) if yaw is not None else None,
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


def velocity_yaw(prev_world_pose, world_pose, thresholds=None):
    thresholds = thresholds or DEFAULT_SCHEDULER_THRESHOLDS
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


def schedule_descriptor_update(prev_descriptor, curr_descriptor, thresholds=None, min_confidence=0.0):
    thresholds = dict(DEFAULT_SCHEDULER_THRESHOLDS, **(thresholds or {}))
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
    create_cpu_us=None,
    export_cpu_us_if_any=None,
):
    start_ns = time.perf_counter_ns()
    thresholds = dict(DEFAULT_SCHEDULER_THRESHOLDS, **(thresholds or {}))
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
        evidence_sources.append("metric_dims_input")

    footprint_px = None
    if mask_meta:
        mb = mask_meta["bbox_px"]
        footprint_px = {"length": mb["w"], "width": mb["h"], "source": "mask_bbox"}
    elif bbox_px:
        footprint_px = {"length": bbox_px["w"], "width": bbox_px["h"], "source": "bbox_px"}

    if metric_dims:
        scale_source = "metric_dims_input"
        scale_uncertainty = "external_metric_input_not_verified_by_sppa"
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
        "yaw": yaw,
        "source_log": source_log,
        "source_event_index": source_event_index,
    }
    input_hash = stable_hash(source_payload)
    descriptor_id = f"sppa-{input_hash}"
    cache_key = str(track_id or f"{normalized_label}:{input_hash}")

    descriptor = {
        "descriptor_schema": SPPA_DESCRIPTOR_VERSION,
        "descriptor_id": descriptor_id,
        "generator_version": GENERATOR_VERSION,
        "ontology_version": ONTOLOGY_VERSION,
        "archetype_version": ARCHETYPE_VERSION,
        "policy_version": POLICY_VERSION,
        "created_utc": utc_now(),
        "input_hash": input_hash,
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
        },
        "pose": {
            "position_world": pose_world.get("position") if pose_world else None,
            "coordinate_frame": pose_world.get("coordinate_frame") if pose_world else None,
            "yaw_rad": yaw.get("yaw_rad"),
            "yaw_deg": yaw.get("yaw_deg"),
            "yaw_source": yaw.get("yaw_source"),
            "yaw_modulo": yaw.get("yaw_modulo"),
            "yaw_ambiguous": yaw.get("yaw_ambiguous"),
            "pose_uncertainty": "unvalidated_input" if pose_world else "missing_world_pose",
        },
        "scale": {
            "dims_m": metric_dims,
            "footprint_m": {"length": metric_dims["length"], "width": metric_dims["width"]} if metric_dims else None,
            "footprint_px": footprint_px,
            "bbox_px": bbox_px,
            "bbox_aspect": bbox_px.get("aspect") if bbox_px else None,
            "mask_area_px2": mask_meta.get("area_px2") if mask_meta else None,
            "scale_source": scale_source,
            "scale_uncertainty": scale_uncertainty,
            "shape_policy": build_meta.get("shape_policy", "template_prior"),
            "part_layout_from_dims": build_meta.get("shape_policy") == "semantic_part_layout_from_metric_dims",
        },
        "uncertainty": {
            "shape_low_confidence": confidence < 0.50,
            "yaw_ambiguous": yaw.get("yaw_ambiguous"),
            "fallback_unknown": unknown_label,
            "scale_from_bbox": scale_source == "bbox_px",
            "scale_from_mask": scale_source == "mask_footprint_px",
            "scale_from_dims": scale_source == "metric_dims_input",
            "shape_source": scale_source,
            "material_source": "semantic_prior" if not unknown_label else "fallback_unknown",
            "material_from_prior": True,
            "material_from_observation": False,
            "confidence": confidence,
        },
        "parts": list(mesh.parts),
        "runtime_policy": {
            "cache_key": cache_key,
            "action": "unapplied",
            "action_reason": "schedule_descriptor_update_not_called",
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
    descriptor["runtime_policy"]["thresholds"] = decision["thresholds"]
    descriptor["cost"]["descriptor_bytes"] = len(canonical_json_bytes(descriptor))
    return descriptor


def build_runtime_update_packet(descriptor, decision=None):
    decision = decision or {
        "action": descriptor.get("runtime_policy", {}).get("action", "unapplied"),
        "reason": descriptor.get("runtime_policy", {}).get("action_reason", "unknown"),
        "thresholds": descriptor.get("runtime_policy", {}).get("thresholds", DEFAULT_SCHEDULER_THRESHOLDS),
    }
    action = decision["action"]
    packet = {
        "packet_schema": SPPA_UPDATE_PACKET_VERSION,
        "descriptor_schema": descriptor.get("descriptor_schema"),
        "descriptor_id": descriptor.get("descriptor_id"),
        "cache_key": descriptor.get("runtime_policy", {}).get("cache_key"),
        "action": action,
        "reason": decision.get("reason"),
        "thresholds": decision.get("thresholds"),
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


def write_mtl(mtl_path):
    with open(mtl_path, "w", encoding="ascii") as f:
        f.write(f"# SPPA material descriptor schema: {MATERIAL_DESCRIPTOR_VERSION}\n")
        f.write("# Materials are procedural semantic priors or explicit unknown fallbacks, not observed texture evidence.\n")
        for name, rgb in MATERIALS.items():
            meta = get_material_metadata(name)
            f.write(f"newmtl {name}\n")
            f.write(f"# sppa_material_role {meta['material_role']}\n")
            f.write(f"# sppa_evidence_source {meta['evidence_source']}\n")
            f.write(f"# sppa_uncertainty_visual_style {meta['uncertainty_visual_style']}\n")
            f.write(f"Kd {rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f}\n")
            f.write("Ka 0.050 0.050 0.050\n")
            f.write("Ks 0.120 0.120 0.120\n")
            f.write(f"d {float(meta.get('alpha', 1.0)):.3f}\n\n")


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
    parser.add_argument("--calibration-ref", default=None, help="Opaque calibration reference; no metric scale is inferred without explicit dims")
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
    parser.add_argument("--threshold-json", default=None, help="Scheduler threshold override JSON literal or file path")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    name = safe_name(args.word)
    obj_path = os.path.join(args.out_dir, f'{name}.obj')
    mtl_path = os.path.join(args.out_dir, f'{name}.mtl')
    manifest_path = os.path.join(args.out_dir, f'{name}.materials.json')
    descriptor_path = args.descriptor_out or os.path.join(args.out_dir, f'{name}.descriptor.json')
    dims_arg = parse_dims_cli(args.dims_m)

    mesh = Mesh()
    create_start = time.perf_counter_ns()
    meta = build_label_parametric(mesh, args.word, dims_arg)
    create_cpu_us = (time.perf_counter_ns() - create_start) / 1000.0

    export_start = time.perf_counter_ns()
    manifest = write_material_manifest(manifest_path, mesh, meta, args.confidence)
    write_mtl(mtl_path)
    write_obj(mesh, obj_path, os.path.basename(mtl_path))
    export_cpu_us = (time.perf_counter_ns() - export_start) / 1000.0

    thresholds = load_json_arg(args.threshold_json) or {}
    descriptor = write_sppa_descriptor(
        descriptor_path,
        mesh,
        meta,
        args.confidence,
        bbox=load_json_arg(args.bbox_json),
        mask=load_json_arg(args.mask_json),
        world_pose=load_json_arg(args.world_json),
        prev_world_pose=load_json_arg(args.prev_world_json),
        camera_pose=load_json_arg(args.camera_json),
        calibration_ref=args.calibration_ref,
        image_width=args.image_width,
        image_height=args.image_height,
        dims_m=dims_arg,
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
