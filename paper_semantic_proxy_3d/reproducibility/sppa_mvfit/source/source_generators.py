from __future__ import annotations

import math
from typing import Any

import numpy as np

FAMILIES = (
    "compact_vehicle",
    "articulated_vehicle",
    "quadruped",
    "branching_vertical",
    "lattice_tower",
    "rider_cycle",
)

WORLD = {
    "x": (-4.8, 4.8),
    "y": (-3.2, 3.2),
    "z": (0.0, 6.4),
}


def _f(value: float) -> float:
    return round(float(value), 8)


def _primitive(kind: str, center: tuple[float, float, float], size: tuple[float, float, float], axis: str = "z") -> dict[str, Any]:
    return {
        "kind": kind,
        "center": [_f(v) for v in center],
        "size": [_f(v) for v in size],
        "axis": axis,
    }


def _tube(p0: tuple[float, float, float], p1: tuple[float, float, float], radius: float) -> dict[str, Any]:
    return {
        "kind": "tube",
        "p0": [_f(v) for v in p0],
        "p1": [_f(v) for v in p1],
        "radius": _f(radius),
    }


def _rng_value(rng: np.random.Generator, low: float, high: float) -> float:
    return float(rng.uniform(low, high))


def _generate_csg_id(family: str, rng: np.random.Generator) -> list[dict[str, Any]]:
    c: list[dict[str, Any]] = []
    if family == "compact_vehicle":
        length = _rng_value(rng, 2.65, 4.25)
        width = _rng_value(rng, 1.20, 1.95)
        wheel_r = _rng_value(rng, 0.25, 0.42)
        body_h = _rng_value(rng, 0.52, 0.88)
        body_z = wheel_r + 0.42 * body_h
        c.append(_primitive("box", (0, 0, body_z), (length, width, body_h)))
        cabin_l = length * _rng_value(rng, 0.34, 0.53)
        cabin_x = length * _rng_value(rng, -0.08, 0.17)
        cabin_h = _rng_value(rng, 0.48, 0.88)
        c.append(_primitive("ellipsoid", (cabin_x, 0, body_z + body_h * 0.48 + cabin_h * 0.38), (cabin_l, width * 0.86, cabin_h)))
        axle = length * _rng_value(rng, 0.29, 0.38)
        for x in (-axle, axle):
            for y in (-width * 0.48, width * 0.48):
                c.append(_primitive("cylinder", (x, y, wheel_r), (2 * wheel_r, width * 0.14, 2 * wheel_r), "y"))
        c.append(_primitive("box", (length * 0.51, 0, body_z), (length * 0.06, width * 0.88, body_h * 0.33)))
        return c

    if family == "articulated_vehicle":
        tractor_l = _rng_value(rng, 1.75, 2.55)
        trailer_l = _rng_value(rng, 2.45, 4.10)
        width = _rng_value(rng, 1.30, 2.05)
        gap = _rng_value(rng, 0.20, 0.48)
        wheel_r = _rng_value(rng, 0.28, 0.43)
        tractor_x = -(trailer_l + gap) * 0.30
        trailer_x = tractor_x + tractor_l * 0.5 + gap + trailer_l * 0.5
        c.append(_primitive("box", (tractor_x, 0, wheel_r + 0.42), (tractor_l, width * 0.94, 0.78)))
        c.append(_primitive("ellipsoid", (tractor_x - tractor_l * 0.15, 0, wheel_r + 1.03), (tractor_l * 0.55, width * 0.84, 0.80)))
        c.append(_primitive("box", (trailer_x, 0, wheel_r + 0.94), (trailer_l, width, _rng_value(rng, 1.05, 1.65))))
        c.append(_primitive("box", ((tractor_x + trailer_x) * 0.5, 0, wheel_r + 0.38), (gap + 0.38, 0.26, 0.22)))
        axle_positions = [tractor_x - tractor_l * 0.25, tractor_x + tractor_l * 0.27, trailer_x - trailer_l * 0.27, trailer_x + trailer_l * 0.30]
        for x in axle_positions:
            c.append(_primitive("cylinder", (x, 0, wheel_r), (2 * wheel_r, width * 1.08, 2 * wheel_r), "y"))
        return c

    if family == "quadruped":
        body_l = _rng_value(rng, 1.75, 3.45)
        body_w = _rng_value(rng, 0.58, 1.20)
        body_h = _rng_value(rng, 0.72, 1.42)
        leg_h = _rng_value(rng, 0.66, 1.25)
        body_z = leg_h + body_h * 0.46
        c.append(_primitive("ellipsoid", (0, 0, body_z), (body_l, body_w, body_h)))
        head_r = _rng_value(rng, 0.28, 0.52)
        c.append(_primitive("ellipsoid", (body_l * 0.58, 0, body_z + body_h * 0.18), (head_r * 1.55, head_r * 1.25, head_r * 1.45)))
        for x in (-body_l * 0.29, body_l * 0.29):
            for y in (-body_w * 0.31, body_w * 0.31):
                leg_w = _rng_value(rng, 0.14, 0.25)
                c.append(_primitive("cylinder", (x, y, leg_h * 0.5), (leg_w, leg_w, leg_h), "z"))
        c.append(_primitive("cylinder", (body_l * 0.43, 0, body_z + body_h * 0.05), (body_l * 0.38, body_w * 0.32, body_w * 0.32), "x"))
        c.append(_primitive("cylinder", (-body_l * 0.58, 0, body_z + body_h * 0.18), (body_l * 0.38, body_w * 0.13, body_w * 0.13), "x"))
        return c

    if family == "branching_vertical":
        trunk_h = _rng_value(rng, 2.10, 3.75)
        trunk_d = _rng_value(rng, 0.28, 0.68)
        c.append(_primitive("cylinder", (0, 0, trunk_h * 0.5), (trunk_d, trunk_d, trunk_h), "z"))
        crown_z = trunk_h * _rng_value(rng, 0.82, 1.02)
        count = int(rng.integers(4, 8))
        for idx in range(count):
            angle = 2 * math.pi * idx / count + _rng_value(rng, -0.22, 0.22)
            radial = _rng_value(rng, 0.15, 0.92)
            cx = math.cos(angle) * radial
            cy = math.sin(angle) * radial * _rng_value(rng, 0.65, 1.0)
            size = (_rng_value(rng, 0.85, 1.80), _rng_value(rng, 0.70, 1.55), _rng_value(rng, 0.72, 1.48))
            c.append(_primitive("ellipsoid", (cx, cy, crown_z + _rng_value(rng, -0.25, 0.55)), size))
        for angle in (-0.55, 0.65):
            z = trunk_h * _rng_value(rng, 0.55, 0.78)
            direction = 1 if angle > 0 else -1
            c.append(_primitive("cylinder", (direction * 0.48, 0, z), (0.96, trunk_d * 0.45, trunk_d * 0.45), "x"))
        return c

    if family == "lattice_tower":
        height = _rng_value(rng, 3.25, 5.75)
        base_x = _rng_value(rng, 0.85, 1.65)
        base_y = _rng_value(rng, 0.65, 1.35)
        leg_d = _rng_value(rng, 0.12, 0.24)
        c.append(_primitive("box", (0, 0, height * 0.52), (leg_d * 1.6, leg_d * 1.6, height * 0.96)))
        for x in (-base_x * 0.5, base_x * 0.5):
            for y in (-base_y * 0.5, base_y * 0.5):
                c.append(_primitive("cylinder", (x, y, height * 0.46), (leg_d, leg_d, height * 0.92), "z"))
        for frac in (0.22, 0.48, 0.74, 0.93):
            shrink = 1.0 - 0.45 * frac
            c.append(_primitive("box", (0, 0, height * frac), (base_x * shrink, base_y * shrink, leg_d * 0.75)))
        return c

    if family == "rider_cycle":
        wheel_r = _rng_value(rng, 0.43, 0.73)
        wheel_sep = _rng_value(rng, 1.35, 2.35)
        wheel_t = _rng_value(rng, 0.10, 0.20)
        for x in (-wheel_sep * 0.5, wheel_sep * 0.5):
            c.append(_primitive("cylinder", (x, 0, wheel_r), (2 * wheel_r, wheel_t, 2 * wheel_r), "y"))
        frame_z = wheel_r * _rng_value(rng, 1.05, 1.35)
        c.append(_primitive("cylinder", (0, 0, frame_z), (wheel_sep * 0.72, 0.13, 0.13), "x"))
        c.append(_primitive("cylinder", (-wheel_sep * 0.20, 0, frame_z + wheel_r * 0.42), (wheel_sep * 0.48, 0.13, 0.13), "x"))
        c.append(_primitive("cylinder", (wheel_sep * 0.25, 0, frame_z + wheel_r * 0.45), (wheel_sep * 0.38, 0.13, 0.13), "x"))
        torso_h = _rng_value(rng, 0.72, 1.25)
        c.append(_primitive("ellipsoid", (0, 0, frame_z + wheel_r * 0.62 + torso_h * 0.48), (0.48, 0.36, torso_h)))
        head = _rng_value(rng, 0.28, 0.42)
        c.append(_primitive("ellipsoid", (0.04, 0, frame_z + wheel_r * 0.62 + torso_h + head * 0.5), (head, head, head)))
        c.append(_primitive("cylinder", (wheel_sep * 0.36, 0, frame_z + wheel_r * 0.72), (0.16, _rng_value(rng, 0.55, 0.95), 0.16), "y"))
        return c

    raise ValueError(f"unknown family: {family}")


def _superellipsoid(center, size, p_xy, p_z) -> dict[str, Any]:
    return {"kind": "superellipsoid", "center": [_f(v) for v in center], "size": [_f(v) for v in size], "p_xy": _f(p_xy), "p_z": _f(p_z)}


def _tapered(center, height, bottom, top, exponent, twist) -> dict[str, Any]:
    return {
        "kind": "tapered_extrusion",
        "center": [_f(v) for v in center],
        "height": _f(height),
        "bottom": [_f(v) for v in bottom],
        "top": [_f(v) for v in top],
        "exponent": _f(exponent),
        "twist_rad": _f(twist),
    }


def _torus_y(center, major, minor) -> dict[str, Any]:
    return {"kind": "torus_y", "center": [_f(v) for v in center], "major": _f(major), "minor": _f(minor)}


def _generate_implicit_ood(family: str, rng: np.random.Generator) -> list[dict[str, Any]]:
    c: list[dict[str, Any]] = []
    if family == "compact_vehicle":
        length, width = _rng_value(rng, 2.7, 4.3), _rng_value(rng, 1.25, 1.95)
        c.append(_superellipsoid((0, 0, 0.78), (length, width, _rng_value(rng, 0.75, 1.10)), _rng_value(rng, 2.8, 5.5), _rng_value(rng, 2.2, 4.0)))
        c.append(_tapered((_rng_value(rng, -0.15, 0.28), 0, 1.24), _rng_value(rng, 0.55, 0.92), (length * 0.23, width * 0.40), (length * 0.17, width * 0.32), _rng_value(rng, 2.5, 5.0), _rng_value(rng, -0.25, 0.25)))
        wheel_r = _rng_value(rng, 0.28, 0.44)
        axle = length * _rng_value(rng, 0.28, 0.38)
        for x in (-axle, axle):
            c.append(_torus_y((x, 0, wheel_r), wheel_r * 0.72, wheel_r * 0.28))
        return c
    if family == "articulated_vehicle":
        front_l, rear_l = _rng_value(rng, 1.7, 2.6), _rng_value(rng, 2.4, 4.2)
        width = _rng_value(rng, 1.3, 2.0)
        c.append(_tapered((-1.35, 0, 0.88), 1.15, (front_l * 0.5, width * 0.5), (front_l * 0.40, width * 0.42), 3.5, 0.12))
        c.append(_superellipsoid((1.15, 0, 1.18), (rear_l, width, _rng_value(rng, 1.25, 1.85)), _rng_value(rng, 3.0, 6.0), _rng_value(rng, 3.0, 5.0)))
        c.append(_tube((-0.15, 0, 0.58), (0.28, 0, 0.62), 0.13))
        for x in (-1.65, -0.82, 0.58, 1.68):
            c.append(_torus_y((x, 0, 0.42), 0.31, 0.11))
        return c
    if family == "quadruped":
        body_l = _rng_value(rng, 1.8, 3.4)
        leg_h = _rng_value(rng, 0.65, 1.25)
        c.append(_superellipsoid((0, 0, leg_h + 0.48), (body_l, _rng_value(rng, 0.62, 1.15), _rng_value(rng, 0.82, 1.38)), _rng_value(rng, 1.4, 2.4), _rng_value(rng, 1.4, 2.5)))
        c.append(_superellipsoid((body_l * 0.58, 0, leg_h + 0.68), (_rng_value(rng, 0.50, 0.82), _rng_value(rng, 0.42, 0.72), _rng_value(rng, 0.52, 0.85)), 1.8, 1.8))
        for x in (-body_l * 0.28, body_l * 0.28):
            for y in (-0.25, 0.25):
                c.append(_tube((x, y, leg_h + 0.22), (x + _rng_value(rng, -0.10, 0.10), y, 0.05), _rng_value(rng, 0.09, 0.15)))
        c.append(_tube((-body_l * 0.48, 0, leg_h + 0.62), (-body_l * 0.76, 0, leg_h + _rng_value(rng, 0.55, 0.90)), 0.07))
        return c
    if family == "branching_vertical":
        height = _rng_value(rng, 2.4, 4.2)
        c.append(_tapered((0, 0, height * 0.48), height * 0.96, (_rng_value(rng, 0.22, 0.38), _rng_value(rng, 0.22, 0.38)), (_rng_value(rng, 0.10, 0.20), _rng_value(rng, 0.10, 0.20)), 2.8, _rng_value(rng, -0.4, 0.4)))
        for idx in range(4):
            angle = 2 * math.pi * idx / 4 + _rng_value(rng, -0.35, 0.35)
            center = (math.cos(angle) * _rng_value(rng, 0.25, 0.80), math.sin(angle) * _rng_value(rng, 0.25, 0.75), height * _rng_value(rng, 0.75, 1.05))
            c.append(_superellipsoid(center, (_rng_value(rng, 0.95, 1.75), _rng_value(rng, 0.80, 1.55), _rng_value(rng, 0.82, 1.55)), _rng_value(rng, 1.2, 2.4), _rng_value(rng, 1.2, 2.5)))
        c.append(_tube((0, 0, height * 0.58), (-0.88, 0.10, height * 0.74), 0.10))
        c.append(_tube((0, 0, height * 0.66), (0.80, -0.10, height * 0.82), 0.09))
        return c
    if family == "lattice_tower":
        height = _rng_value(rng, 3.3, 5.8)
        base = _rng_value(rng, 0.75, 1.45)
        c.append(_tapered((0, 0, height * 0.5), height, (base * 0.18, base * 0.18), (base * 0.08, base * 0.08), 3.5, _rng_value(rng, -0.35, 0.35)))
        for x, y in ((-base / 2, -base / 2), (-base / 2, base / 2), (base / 2, -base / 2), (base / 2, base / 2)):
            c.append(_tube((x, y, 0.05), (x * 0.45, y * 0.45, height * 0.94), _rng_value(rng, 0.07, 0.13)))
        for frac in (0.28, 0.55, 0.80):
            span = base * (1 - 0.48 * frac)
            c.append(_tube((-span / 2, 0, height * frac), (span / 2, 0, height * frac), _rng_value(rng, 0.06, 0.11)))
        return c
    if family == "rider_cycle":
        wheel_r = _rng_value(rng, 0.45, 0.72)
        sep = _rng_value(rng, 1.4, 2.3)
        c.append(_torus_y((-sep / 2, 0, wheel_r), wheel_r * 0.76, wheel_r * 0.20))
        c.append(_torus_y((sep / 2, 0, wheel_r), wheel_r * 0.76, wheel_r * 0.20))
        c.append(_tube((-sep / 2, 0, wheel_r), (0, 0, wheel_r * 1.52), 0.07))
        c.append(_tube((0, 0, wheel_r * 1.52), (sep / 2, 0, wheel_r), 0.07))
        c.append(_tube((-sep / 2, 0, wheel_r), (sep / 2, 0, wheel_r), 0.065))
        torso_h = _rng_value(rng, 0.75, 1.22)
        c.append(_superellipsoid((0, 0, wheel_r * 1.70 + torso_h * 0.45), (0.48, 0.36, torso_h), 1.8, 1.7))
        c.append(_superellipsoid((0.04, 0, wheel_r * 1.70 + torso_h + 0.18), (0.38, 0.38, 0.42), 1.7, 1.7))
        c.append(_tube((0.12, 0, wheel_r * 1.70 + torso_h * 0.60), (sep * 0.38, 0, wheel_r * 1.30), 0.06))
        return c
    raise ValueError(f"unknown family: {family}")


def generate_source_actor(family: str, stratum: str, seed: int) -> dict[str, Any]:
    if family not in FAMILIES:
        raise ValueError(f"unknown family: {family}")
    rng = np.random.default_rng(int(seed))
    if stratum == "csg_id":
        components = _generate_csg_id(family, rng)
        generator = "independent_csg_source_v1"
    elif stratum == "implicit_ood":
        components = _generate_implicit_ood(family, rng)
        generator = "independent_implicit_source_v1"
    else:
        raise ValueError(f"unknown stratum: {stratum}")
    return {
        "schema_version": "SPPA-MVFIT-SOURCE-ACTOR-1.0",
        "provenance": "synthetic_geometry",
        "family": family,
        "stratum": stratum,
        "seed": int(seed),
        "generator": generator,
        "components": components,
    }


def _component_occupancy(component: dict[str, Any], x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    kind = component["kind"]
    if kind in {"box", "ellipsoid", "cylinder"}:
        cx, cy, cz = component["center"]
        sx, sy, sz = component["size"]
        dx, dy, dz = x - cx, y - cy, z - cz
        if kind == "box":
            return (np.abs(dx) <= sx / 2) & (np.abs(dy) <= sy / 2) & (np.abs(dz) <= sz / 2)
        if kind == "ellipsoid":
            return (dx / (sx / 2)) ** 2 + (dy / (sy / 2)) ** 2 + (dz / (sz / 2)) ** 2 <= 1
        axis = component.get("axis", "z")
        if axis == "x":
            return (np.abs(dx) <= sx / 2) & ((dy / (sy / 2)) ** 2 + (dz / (sz / 2)) ** 2 <= 1)
        if axis == "y":
            return (np.abs(dy) <= sy / 2) & ((dx / (sx / 2)) ** 2 + (dz / (sz / 2)) ** 2 <= 1)
        return (np.abs(dz) <= sz / 2) & ((dx / (sx / 2)) ** 2 + (dy / (sy / 2)) ** 2 <= 1)
    if kind == "superellipsoid":
        cx, cy, cz = component["center"]
        sx, sy, sz = component["size"]
        p, q = float(component["p_xy"]), float(component["p_z"])
        xy = (np.abs((x - cx) / (sx / 2)) ** p + np.abs((y - cy) / (sy / 2)) ** p) ** (q / p)
        return xy + np.abs((z - cz) / (sz / 2)) ** q <= 1
    if kind == "tapered_extrusion":
        cx, cy, cz = component["center"]
        height = float(component["height"])
        t = (z - (cz - height / 2)) / height
        inside_z = (t >= 0) & (t <= 1)
        bx, by = component["bottom"]
        tx, ty = component["top"]
        rx = bx * (1 - t) + tx * t
        ry = by * (1 - t) + ty * t
        angle = float(component["twist_rad"]) * (t - 0.5)
        ca, sa = np.cos(angle), np.sin(angle)
        dx, dy = x - cx, y - cy
        u, v = ca * dx + sa * dy, -sa * dx + ca * dy
        exponent = float(component["exponent"])
        profile = np.abs(u / np.maximum(rx, 1e-6)) ** exponent + np.abs(v / np.maximum(ry, 1e-6)) ** exponent
        return inside_z & (profile <= 1)
    if kind == "torus_y":
        cx, cy, cz = component["center"]
        major, minor = float(component["major"]), float(component["minor"])
        radial = np.sqrt((x - cx) ** 2 + (z - cz) ** 2)
        return (radial - major) ** 2 + (y - cy) ** 2 <= minor**2
    if kind == "tube":
        p0 = np.asarray(component["p0"], dtype=np.float64)
        p1 = np.asarray(component["p1"], dtype=np.float64)
        vx, vy, vz = p1 - p0
        denom = max(float(vx * vx + vy * vy + vz * vz), 1e-12)
        t = ((x - p0[0]) * vx + (y - p0[1]) * vy + (z - p0[2]) * vz) / denom
        t = np.clip(t, 0.0, 1.0)
        dx = x - (p0[0] + t * vx)
        dy = y - (p0[1] + t * vy)
        dz = z - (p0[2] + t * vz)
        return dx * dx + dy * dy + dz * dz <= float(component["radius"]) ** 2
    raise ValueError(f"unknown component kind: {kind}")


def occupancy_at(actor: dict[str, Any], x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    occupied = np.zeros(np.broadcast_shapes(x.shape, y.shape, z.shape), dtype=bool)
    for component in actor["components"]:
        occupied |= _component_occupancy(component, x, y, z)
    return occupied


def voxelize_source(actor: dict[str, Any], resolution: int = 64) -> np.ndarray:
    xs = np.linspace(WORLD["x"][0], WORLD["x"][1], resolution, endpoint=False) + (WORLD["x"][1] - WORLD["x"][0]) / (2 * resolution)
    ys = np.linspace(WORLD["y"][0], WORLD["y"][1], resolution, endpoint=False) + (WORLD["y"][1] - WORLD["y"][0]) / (2 * resolution)
    zs = np.linspace(WORLD["z"][0], WORLD["z"][1], resolution, endpoint=False) + (WORLD["z"][1] - WORLD["z"][0]) / (2 * resolution)
    x, y, z = np.meshgrid(xs, ys, zs, indexing="ij", sparse=True)
    return occupancy_at(actor, x, y, z)


def _project_simple_component(component: dict[str, Any], view: str, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    kind = component["kind"]
    cx, cy, cz = component["center"]
    sx, sy, sz = component["size"]
    if view == "top":
        cu, cv, su, sv = cx, cy, sx, sy
        ray_axis = "z"
        plane_axes = ("x", "y")
    else:
        cu, cv, su, sv = cx, cz, sx, sz
        ray_axis = "y"
        plane_axes = ("x", "z")
    if kind == "box":
        return (np.abs(u - cu) <= su / 2) & (np.abs(v - cv) <= sv / 2)
    if kind == "ellipsoid":
        return ((u - cu) / (su / 2)) ** 2 + ((v - cv) / (sv / 2)) ** 2 <= 1
    axis = component.get("axis", "z")
    if axis == ray_axis:
        return ((u - cu) / (su / 2)) ** 2 + ((v - cv) / (sv / 2)) ** 2 <= 1
    along_u = axis == plane_axes[0]
    if along_u:
        half_len = su / 2
        radius = sv / 2
        du = np.maximum(np.abs(u - cu) - half_len, 0.0)
        return du * du + (v - cv) ** 2 <= radius * radius
    half_len = sv / 2
    radius = su / 2
    dv = np.maximum(np.abs(v - cv) - half_len, 0.0)
    return (u - cu) ** 2 + dv * dv <= radius * radius


def _project_id(actor: dict[str, Any], resolution: int) -> tuple[np.ndarray, np.ndarray]:
    xs = np.linspace(WORLD["x"][0], WORLD["x"][1], resolution, endpoint=False) + (WORLD["x"][1] - WORLD["x"][0]) / (2 * resolution)
    ys = np.linspace(WORLD["y"][0], WORLD["y"][1], resolution, endpoint=False) + (WORLD["y"][1] - WORLD["y"][0]) / (2 * resolution)
    zs = np.linspace(WORLD["z"][0], WORLD["z"][1], resolution, endpoint=False) + (WORLD["z"][1] - WORLD["z"][0]) / (2 * resolution)
    tx, ty = np.meshgrid(xs, ys, indexing="ij")
    sx, sz = np.meshgrid(xs, zs, indexing="ij")
    top = np.zeros((resolution, resolution), dtype=bool)
    side = np.zeros((resolution, resolution), dtype=bool)
    for component in actor["components"]:
        top |= _project_simple_component(component, "top", tx, ty)
        side |= _project_simple_component(component, "side", sx, sz)
    return top, side


def _project_implicit(actor: dict[str, Any], resolution: int, ray_samples: int = 80) -> tuple[np.ndarray, np.ndarray]:
    xs = np.linspace(WORLD["x"][0], WORLD["x"][1], resolution, endpoint=False) + (WORLD["x"][1] - WORLD["x"][0]) / (2 * resolution)
    ys = np.linspace(WORLD["y"][0], WORLD["y"][1], resolution, endpoint=False) + (WORLD["y"][1] - WORLD["y"][0]) / (2 * resolution)
    zs = np.linspace(WORLD["z"][0], WORLD["z"][1], ray_samples, endpoint=False) + (WORLD["z"][1] - WORLD["z"][0]) / (2 * ray_samples)
    tx, ty = np.meshgrid(xs, ys, indexing="ij")
    top = np.zeros((resolution, resolution), dtype=bool)
    for z_value in zs:
        top |= occupancy_at(actor, tx, ty, np.asarray(z_value))
    side_zs = np.linspace(WORLD["z"][0], WORLD["z"][1], resolution, endpoint=False) + (WORLD["z"][1] - WORLD["z"][0]) / (2 * resolution)
    sx, sz = np.meshgrid(xs, side_zs, indexing="ij")
    side = np.zeros((resolution, resolution), dtype=bool)
    for y_value in np.linspace(WORLD["y"][0], WORLD["y"][1], ray_samples, endpoint=False) + (WORLD["y"][1] - WORLD["y"][0]) / (2 * ray_samples):
        side |= occupancy_at(actor, sx, np.asarray(y_value), sz)
    return top, side


def _downsample_any(mask: np.ndarray, output_resolution: int) -> np.ndarray:
    input_resolution = int(mask.shape[0])
    integral = np.pad(mask.astype(np.int32), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    edges = np.linspace(0, input_resolution, output_resolution + 1)
    starts = np.floor(edges[:-1]).astype(int)
    ends = np.ceil(edges[1:]).astype(int)
    out = np.zeros((output_resolution, output_resolution), dtype=bool)
    for i, (x0, x1) in enumerate(zip(starts, ends)):
        y0 = starts
        y1 = ends
        sums = integral[x1, y1] - integral[x0, y1] - integral[x1, y0] + integral[x0, y0]
        out[i, :] = sums > 0
    return out


def render_source_masks(actor: dict[str, Any], source_resolution: int = 256, output_resolution: int = 96) -> tuple[np.ndarray, np.ndarray]:
    if actor["stratum"] == "csg_id":
        top, side = _project_id(actor, source_resolution)
    elif actor["stratum"] == "implicit_ood":
        top, side = _project_implicit(actor, source_resolution)
    else:
        raise ValueError(actor["stratum"])
    return _downsample_any(top, output_resolution), _downsample_any(side, output_resolution)


def validate_actor_inside_world(actor: dict[str, Any], resolution: int = 80) -> bool:
    voxels = voxelize_source(actor, resolution)
    boundary = np.zeros_like(voxels)
    boundary[[0, -1], :, :] = True
    boundary[:, [0, -1], :] = True
    # Occupancy on the lower z layer is expected for actors supported by the
    # declared ground plane z=0. Only the upper z boundary indicates clipping.
    boundary[:, :, -1] = True
    return not bool(np.any(voxels & boundary))
