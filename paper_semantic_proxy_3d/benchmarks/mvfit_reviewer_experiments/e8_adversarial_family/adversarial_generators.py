"""E8 adversarial actor generators (transformations of the sealed csg_id actors).

Each function takes the base actor's component list (csg_id construction
order, see e6_role_aware/ROLE_MAPPING_FROZEN.md) plus the actor's e8 rng and
returns (components, violation_info). Only box/cylinder/ellipsoid components
are produced, so the sealed analytic projection path applies unchanged.

The 12 violation types are frozen in ADVERSARIAL_DESIGN_FROZEN.md; the
predicate battery at the bottom enforces them before any fit.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

TAN25 = math.tan(math.radians(25.0))


def _f(value: float) -> float:
    return round(float(value), 8)


def _prim(kind: str, center: tuple[float, float, float], size: tuple[float, float, float], axis: str = "z") -> dict[str, Any]:
    return {"kind": kind, "center": [_f(v) for v in center], "size": [_f(v) for v in size], "axis": axis}


def _clone(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(kind=c["kind"], center=list(c["center"]), size=list(c["size"]), axis=c.get("axis", "z")) for c in components]


def _lean_direction(rng: np.random.Generator) -> tuple[float, float, float]:
    """Azimuth in x-dominant cones (frozen): phi = choice(0, pi) + U(-0.55, 0.55)."""
    phi = float(rng.choice([0.0, math.pi])) + float(rng.uniform(-0.55, 0.55))
    return phi, math.cos(phi), math.sin(phi)


# ---------------------------------------------------------------- compact_vehicle
def compact_roof_cargo_250(comps: list[dict[str, Any]], rng: np.random.Generator):
    c = _clone(comps)
    body, cabin = c[0], c[1]
    length = body["size"][0]
    cabin_vol = cabin["size"][0] * cabin["size"][1] * cabin["size"][2]
    footprint = (0.50 * length, 0.95 * cabin["size"][1])
    height = min(2.5 * cabin_vol / (footprint[0] * footprint[1]), 2.5)
    cabin_top = cabin["center"][2] + cabin["size"][2] / 2
    cargo = _prim("box", (cabin["center"][0], 0.0, cabin_top + height / 2), (footprint[0], footprint[1], height))
    c.append(cargo)
    return c, {"violation": "roof_cargo_250", "cargo_volume_ratio": _f(footprint[0] * footprint[1] * height / cabin_vol)}


def compact_cab_rearward(comps: list[dict[str, Any]], rng: np.random.Generator):
    c = _clone(comps)
    body, cabin = c[0], c[1]
    length, width, body_h = body["size"]
    body_z = body["center"][2]
    shift = float(rng.uniform(0.34, 0.40))
    cabin["center"][0] = _f(-shift * length)
    hood = _prim("box", (0.30 * length, 0.0, body_z), (0.42 * length, 0.88 * width, 0.85 * body_h))
    c[6] = hood  # replaces the small front box
    return c, {"violation": "cab_rearward", "cabin_x_over_L": _f(-shift)}


# ---------------------------------------------------------------- articulated_vehicle
def articulated_centered_cab_split_cargo(comps: list[dict[str, Any]], rng: np.random.Generator):
    c = _clone(comps)
    tractor, cabin, trailer = c[0], c[1], c[2]
    trailer_l = trailer["size"][0]
    cabin["center"][0] = _f(0.5 * (tractor["center"][0] + trailer["center"][0]))
    gap = 0.45
    new_len = (trailer_l - gap) / 2
    half_span = (new_len + gap) / 2
    box_a = _prim("box", (trailer["center"][0] - half_span, trailer["center"][1], trailer["center"][2]),
                  (new_len, trailer["size"][1], trailer["size"][2]))
    box_b = _prim("box", (trailer["center"][0] + half_span, trailer["center"][1], trailer["center"][2]),
                  (new_len, trailer["size"][1], trailer["size"][2]))
    c[2] = box_a
    c.insert(3, box_b)
    return c, {"violation": "centered_cab_split_cargo", "split_gap_m": gap}


def articulated_double_trailer(comps: list[dict[str, Any]], rng: np.random.Generator):
    c = _clone(comps)
    trailer = c[2]
    wheel = c[4]
    trailer_l = trailer["size"][0]
    wheel_r = wheel["size"][2] / 2
    tx = trailer["center"][0]
    t_a = _prim("box", (tx - 0.25 * trailer_l, trailer["center"][1], trailer["center"][2]),
                (0.44 * trailer_l, trailer["size"][1], trailer["size"][2]))
    t_b = _prim("box", (tx + 0.25 * trailer_l, trailer["center"][1], trailer["center"][2]),
                (0.44 * trailer_l, trailer["size"][1], trailer["size"][2]))
    drawbar = _prim("box", (tx, 0.0, wheel_r + 0.38), (0.12 * trailer_l + 0.20, 0.26, 0.22))
    fifth_wheel = _prim("cylinder", (tx, 0.0, wheel_r), (2 * wheel_r, wheel["size"][1], 2 * wheel_r), "y")
    c[2] = t_a
    c.insert(3, t_b)
    c.append(drawbar)
    c.append(fifth_wheel)
    return c, {"violation": "double_trailer", "axle_count": 5}


# ---------------------------------------------------------------- quadruped
def quadruped_asymmetric_legs(comps: list[dict[str, Any]], rng: np.random.Generator):
    c = _clone(comps)
    body = c[0]
    body_h = body["size"][2]
    leg_h = c[2]["size"][2]
    tall_front = bool(rng.integers(0, 2))
    f_t = float(rng.uniform(1.35, 1.70))
    f_s = float(rng.uniform(0.55, 0.72))
    f_front, f_rear = (f_t, f_s) if tall_front else (f_s, f_t)
    for idx in (2, 3):  # rear legs (-x)
        h = leg_h * f_rear
        c[idx]["size"][2] = _f(h)
        c[idx]["center"][2] = _f(h / 2)
    for idx in (4, 5):  # front legs (+x)
        h = leg_h * f_front
        c[idx]["size"][2] = _f(h)
        c[idx]["center"][2] = _f(h / 2)
    new_body_z = leg_h * f_t + 0.46 * body_h
    dz = new_body_z - body["center"][2]
    c[0]["center"][2] = _f(new_body_z)
    for idx in (1, 6, 7):  # head, neck, tail ride with the body
        c[idx]["center"][2] = _f(c[idx]["center"][2] + dz)
    return c, {"violation": "asymmetric_legs", "tall_end": "front" if tall_front else "rear",
               "f_tall": _f(f_t), "f_short": _f(f_s)}


def quadruped_giraffe_neck(comps: list[dict[str, Any]], rng: np.random.Generator):
    c = _clone(comps)
    body, head, neck = c[0], c[1], c[6]
    body_h = body["size"][2]
    neck_h = float(rng.uniform(1.6, 2.1)) * body_h
    neck_x = neck["center"][0]
    neck_base = body["center"][2] + body_h * 0.05 - 0.10
    c[6] = _prim("cylinder", (neck_x, 0.0, neck_base + neck_h / 2),
                 (body["size"][1] * 0.32, body["size"][1] * 0.32, neck_h), "z")
    neck_top = neck_base + neck_h
    head["center"][0] = _f(neck_x + 0.15)
    head["center"][2] = _f(neck_top + head["size"][2] * 0.25)
    return c, {"violation": "giraffe_neck", "neck_h_over_body_h": _f(neck_h / body_h)}


# ---------------------------------------------------------------- branching_vertical
def branching_leaning_25(comps: list[dict[str, Any]], rng: np.random.Generator):
    c = _clone(comps)
    trunk = c[0]
    trunk_h = trunk["size"][2]
    phi, dx, dy = _lean_direction(rng)
    tiers = []
    for i in range(3):
        z_mid = (i + 0.5) * trunk_h / 3
        tiers.append(_prim("cylinder", (TAN25 * z_mid * dx, TAN25 * z_mid * dy, z_mid),
                           (trunk["size"][0], trunk["size"][1], trunk_h / 3), "z"))
    out = tiers
    for comp in c[1:]:
        z = comp["center"][2]
        comp["center"][0] = _f(comp["center"][0] + TAN25 * z * dx)
        comp["center"][1] = _f(comp["center"][1] + TAN25 * z * dy)
        out.append(comp)
    return out, {"violation": "leaning_25", "lean_phi_rad": _f(phi)}


def branching_cascade_crown(comps: list[dict[str, Any]], rng: np.random.Generator):
    c = _clone(comps)
    trunk = c[0]
    trunk_h = trunk["size"][2]
    k = len(c) - 3  # crowns = comps 1..K
    phi0 = float(rng.uniform(0.0, 2 * math.pi))
    for i in range(k):
        crown = c[1 + i]
        phi = phi0 + float(rng.uniform(-0.3, 0.3))
        radial = float(rng.uniform(0.35, 0.75))
        crown["center"][0] = _f(math.cos(phi) * radial)
        crown["center"][1] = _f(math.sin(phi) * radial)
        crown["center"][2] = _f(trunk_h * (0.42 + 0.55 * (i / max(k - 1, 1))))
    return c, {"violation": "cascade_crown", "phi0_rad": _f(phi0), "crown_count": k}


# ---------------------------------------------------------------- lattice_tower
def lattice_leaning_25(comps: list[dict[str, Any]], rng: np.random.Generator):
    c = _clone(comps)
    core = c[0]
    core_z0 = core["center"][2] - core["size"][2] / 2
    core_h = core["size"][2]
    phi, dx, dy = _lean_direction(rng)
    out = []
    for i in range(3):
        z_mid = core_z0 + (i + 0.5) * core_h / 3
        out.append(_prim("box", (TAN25 * z_mid * dx, TAN25 * z_mid * dy, z_mid),
                         (core["size"][0], core["size"][1], core_h / 3)))
    for leg in c[1:5]:
        leg_z0 = leg["center"][2] - leg["size"][2] / 2
        leg_h = leg["size"][2]
        for i in range(3):
            z_mid = leg_z0 + (i + 0.5) * leg_h / 3
            out.append(_prim("cylinder", (leg["center"][0] + TAN25 * z_mid * dx,
                                          leg["center"][1] + TAN25 * z_mid * dy, z_mid),
                             (leg["size"][0], leg["size"][1], leg_h / 3), "z"))
    for platform in c[5:]:
        z = platform["center"][2]
        platform["center"][0] = _f(platform["center"][0] + TAN25 * z * dx)
        platform["center"][1] = _f(platform["center"][1] + TAN25 * z * dy)
        out.append(platform)
    return out, {"violation": "leaning_25", "lean_phi_rad": _f(phi)}


def lattice_platforms_out_of_order(comps: list[dict[str, Any]], rng: np.random.Generator):
    c = _clone(comps)
    platforms = c[5:]
    sizes = [(p["size"][0], p["size"][1]) for p in platforms]
    bottom_size = sizes[0]
    for i, platform in enumerate(platforms):
        sx, sy = sizes[len(sizes) - 1 - i]
        if i == len(sizes) - 1:  # top platform gets the bottom (largest) size, plus 1.25x
            sx, sy = sx * 1.25, sy * 1.25
        platform["size"][0] = _f(sx)
        platform["size"][1] = _f(sy)
    return c, {"violation": "platforms_out_of_order",
               "top_over_bottom_size_x": _f(platforms[-1]["size"][0] / bottom_size[0])}


# ---------------------------------------------------------------- rider_cycle
def rider_sidecar(comps: list[dict[str, Any]], rng: np.random.Generator):
    c = _clone(comps)
    sep = c[1]["center"][0] - c[0]["center"][0]
    x = -0.25 * sep + float(rng.uniform(-0.1, 0.1)) * sep
    sidecar = _prim("box", (x, 0.72, 0.52), (0.72, 0.62, 0.38))
    third_wheel = _prim("cylinder", (x, 0.95, 0.34), (0.68, 0.14, 0.68), "y")
    c.append(sidecar)
    c.append(third_wheel)
    return c, {"violation": "sidecar", "sidecar_y": 0.72}


def rider_recumbent(comps: list[dict[str, Any]], rng: np.random.Generator):
    c = _clone(comps)
    frame_z = c[2]["center"][2]
    torso, head = c[5], c[6]
    torso_h = torso["size"][2]
    sep = c[1]["center"][0] - c[0]["center"][0]
    torso_len = max(0.8, 0.9 * torso_h)
    torso_x = -0.05 * sep
    c[5] = _prim("ellipsoid", (torso_x, 0.0, frame_z + 0.28), (torso_len, 0.36, 0.44))
    head_r = head["size"][0] / 2
    c[6]["center"][0] = _f(torso_x + torso_len / 2 + 0.4 * head_r)
    c[6]["center"][2] = _f(frame_z + 0.52)
    return c, {"violation": "recumbent", "torso_len": _f(torso_len)}


VIOLATIONS: dict[str, dict[int, tuple[str, Any]]] = {
    "compact_vehicle": {1: ("roof_cargo_250", compact_roof_cargo_250), 2: ("cab_rearward", compact_cab_rearward)},
    "articulated_vehicle": {1: ("centered_cab_split_cargo", articulated_centered_cab_split_cargo),
                            2: ("double_trailer", articulated_double_trailer)},
    "quadruped": {1: ("asymmetric_legs", quadruped_asymmetric_legs), 2: ("giraffe_neck", quadruped_giraffe_neck)},
    "branching_vertical": {1: ("leaning_25", branching_leaning_25), 2: ("cascade_crown", branching_cascade_crown)},
    "lattice_tower": {1: ("leaning_25", lattice_leaning_25), 2: ("platforms_out_of_order", lattice_platforms_out_of_order)},
    "rider_cycle": {1: ("sidecar", rider_sidecar), 2: ("recumbent", rider_recumbent)},
}


def violation_for_index(actor_index: int) -> int:
    """Base actors 0-9 -> V1, 10-19 -> V2 (frozen)."""
    return 1 if actor_index < 10 else 2


# ---------------------------------------------------------------- predicate battery
def _circ_dist(a: float, b: float) -> float:
    d = abs(a - b) % (2 * math.pi)
    return min(d, 2 * math.pi - d)


def check_violation(family: str, violation: str, base: list[dict[str, Any]], adv: list[dict[str, Any]]) -> None:
    """Frozen predicate battery; raises AssertionError on failure."""
    if family == "compact_vehicle" and violation == "roof_cargo_250":
        cabin = base[1]
        cabin_vol = cabin["size"][0] * cabin["size"][1] * cabin["size"][2]
        boxes = [p for p in adv if p["kind"] == "box" and p["center"][2] > cabin["center"][2]]
        assert any(p["size"][0] * p["size"][1] * p["size"][2] >= 2.4 * cabin_vol for p in boxes), "cargo volume ratio"
    elif family == "compact_vehicle" and violation == "cab_rearward":
        length = base[0]["size"][0]
        assert adv[1]["center"][0] < -0.30 * length, "cabin not rearward"
        assert any(p["kind"] == "box" and p["size"][0] >= 0.35 * length and p["center"][0] > 0 for p in adv), "hood missing"
    elif family == "articulated_vehicle" and violation == "centered_cab_split_cargo":
        tractor, trailer = base[0], base[2]
        assert abs(adv[1]["center"][0] - 0.5 * (tractor["center"][0] + trailer["center"][0])) < 1e-6, "cabin not centered"
        expected = (trailer["size"][0] - 0.45) / 2
        halves = [p for p in adv if p["kind"] == "box" and abs(p["size"][0] - expected) < 1e-6]
        assert len(halves) == 2, "split cargo count"
    elif family == "articulated_vehicle" and violation == "double_trailer":
        wheels = [p for p in adv if p["kind"] == "cylinder" and p.get("axis") == "y"]
        assert len(wheels) == 5, "axle count"
        assert sum(1 for p in adv if p["kind"] == "box" and abs(p["size"][0] - 0.44 * base[2]["size"][0]) < 1e-6) == 2, "trailer count"
    elif family == "quadruped" and violation == "asymmetric_legs":
        rear_h = adv[2]["size"][2]
        front_h = adv[4]["size"][2]
        ratio = max(rear_h, front_h) / min(rear_h, front_h)
        assert ratio >= 1.8, "leg ratio"
        short_top = min(rear_h, front_h)
        body_bottom = adv[0]["center"][2] - adv[0]["size"][2] / 2
        assert short_top < body_bottom - 0.2, "short legs still reach body"
    elif family == "quadruped" and violation == "giraffe_neck":
        neck = adv[6]
        assert neck["kind"] == "cylinder" and neck.get("axis") == "z", "neck not vertical"
        assert neck["size"][2] >= 1.5 * adv[0]["size"][2], "neck height"
        assert adv[1]["center"][2] > neck["center"][2] - neck["size"][2] / 2, "head not on neck"
    elif family == "branching_vertical" and violation == "leaning_25":
        trunk_tiers = [p for p in adv[:3] if p["kind"] == "cylinder"]
        assert len(trunk_tiers) == 3, "trunk tier count"
        offsets = [math.hypot(p["center"][0], p["center"][1]) for p in trunk_tiers]
        z_mids = [p["center"][2] for p in trunk_tiers]
        assert all(abs(o - TAN25 * z) < 1e-6 for o, z in zip(offsets, z_mids)), "tier offsets"
        assert all(abs(o - TAN25 * z) < 1e-6 for o, z in
                   [(math.hypot(p["center"][0] - b["center"][0], p["center"][1] - b["center"][1]), p["center"][2])
                    for p, b in zip(adv[3:], base[1:])]), "crown offsets"
    elif family == "branching_vertical" and violation == "cascade_crown":
        trunk_h = base[0]["size"][2]
        k = len(base) - 3
        phis = [math.atan2(adv[1 + i]["center"][1], adv[1 + i]["center"][0]) for i in range(k)]
        phi_ref = phis[0]
        assert all(_circ_dist(p, phi_ref) <= 0.65 for p in phis), "azimuth spread"
        zs = [adv[1 + i]["center"][2] for i in range(k)]
        assert max(zs) - min(zs) >= 0.4 * trunk_h, "cascade z-span"
    elif family == "lattice_tower" and violation == "leaning_25":
        core_tiers = [p for p in adv[:3] if p["kind"] == "box"]
        legs = [p for p in adv[3:15] if p["kind"] == "cylinder"]
        assert len(core_tiers) == 3 and len(legs) == 12, "segmentation count"
        assert all(abs(math.hypot(p["center"][0], p["center"][1]) - TAN25 * p["center"][2]) < 1e-6 for p in core_tiers), "core offsets"
        base_platform_z = [p["center"][2] for p in base[5:]]
        adv_platform_z = sorted(p["center"][2] for p in adv[15:])
        assert all(abs(a - b) < 1e-6 for a, b in zip(adv_platform_z, sorted(base_platform_z))), "platform z changed"
    elif family == "lattice_tower" and violation == "platforms_out_of_order":
        xs = [p["size"][0] for p in adv[5:]]
        assert all(b > a for a, b in zip(xs, xs[1:])), "size order not reversed"
        assert xs[-1] >= 1.2 * base[5]["size"][0], "top platform scale"
    elif family == "rider_cycle" and violation == "sidecar":
        assert any(p["center"][1] > 0.4 for p in adv), "sidecar y"
        wheel_like = [p for p in adv if p["kind"] == "cylinder" and p.get("axis") == "y"
                      and p["size"][0] >= 0.5 and abs(p["size"][0] - p["size"][2]) < 1e-6]
        assert len(wheel_like) == 3, "wheel count"
    elif family == "rider_cycle" and violation == "recumbent":
        torso = adv[5]
        frame_z = adv[2]["center"][2]
        assert torso["size"][0] > torso["size"][2], "torso not horizontal"
        assert torso["center"][2] < frame_z + 0.45, "torso too high"
    else:
        raise ValueError(f"no predicate for {family}/{violation}")
