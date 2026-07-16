from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage

HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parent
PROTOCOL = json.loads((PACKAGE_ROOT / "protocol_config.json").read_text(encoding="utf-8"))
GRAPH_PAYLOAD = json.loads((HERE / "graphs.json").read_text(encoding="utf-8"))
GRAPHS: dict[str, list[dict[str, Any]]] = GRAPH_PAYLOAD["graphs"]
WORLD = {axis: tuple(float(v) for v in PROTOCOL["world"][axis]) for axis in ("x", "y", "z")}
PARAMETER_NAMES = ("log_scale_x", "log_scale_y", "log_scale_z", "secondary_scale", "secondary_offset_x")
BOUNDS = np.asarray(
    [
        (math.log(0.55), math.log(1.80)),
        (math.log(0.55), math.log(1.80)),
        (math.log(0.55), math.log(1.80)),
        (0.65, 1.35),
        (-0.35, 0.35),
    ],
    dtype=np.float64,
)
STEP_FRACTIONS = tuple(float(v) for v in PROTOCOL["fit_step_fractions"])


def _cell_centers(axis: str, resolution: int) -> np.ndarray:
    low, high = WORLD[axis]
    return np.linspace(low, high, resolution, endpoint=False, dtype=np.float64) + (high - low) / (2 * resolution)


def default_theta() -> np.ndarray:
    return np.asarray([0.0, 0.0, 0.0, 1.0, 0.0], dtype=np.float64)


def build_actor(graph_name: str, theta: np.ndarray | list[float] | tuple[float, ...]) -> list[dict[str, Any]]:
    """The only actor builder used by text-only, generic fit, and SPPA fit."""
    if graph_name not in GRAPHS:
        raise KeyError(graph_name)
    values = np.asarray(theta, dtype=np.float64)
    if values.shape != (5,):
        raise ValueError("theta must contain five parameters")
    if np.any(values < BOUNDS[:, 0] - 1e-12) or np.any(values > BOUNDS[:, 1] + 1e-12):
        raise ValueError("theta outside frozen bounds")
    sx, sy, sz = (math.exp(float(values[i])) for i in range(3))
    secondary_scale = float(values[3])
    secondary_offset = float(values[4])
    default_length = max(float(slot["center"][0]) + float(slot["size"][0]) / 2 for slot in GRAPHS[graph_name]) - min(
        float(slot["center"][0]) - float(slot["size"][0]) / 2 for slot in GRAPHS[graph_name]
    )
    actor: list[dict[str, Any]] = []
    for slot_index, slot in enumerate(GRAPHS[graph_name]):
        is_secondary = bool(slot["secondary"])
        local_scale = secondary_scale if is_secondary else 1.0
        cx, cy, cz = (float(v) for v in slot["center"])
        dx, dy, dz = (float(v) for v in slot["size"])
        transformed = {
            "slot_index": slot_index,
            "type": slot["type"],
            "axis": slot.get("axis", "z"),
            "secondary": is_secondary,
            "center": [
                cx * sx + (secondary_offset * default_length * sx if is_secondary else 0.0),
                cy * sy,
                cz * sz,
            ],
            "size": [
                max(1e-4, dx * sx * local_scale),
                max(1e-4, dy * sy * local_scale),
                max(1e-4, dz * sz * local_scale),
            ],
        }
        actor.append(transformed)
    return actor


def _capsule_2d(u: np.ndarray, v: np.ndarray, cu: float, cv: float, length: float, radius: float, along_u: bool) -> np.ndarray:
    if along_u:
        du = np.maximum(np.abs(u - cu) - max(0.0, length / 2 - radius), 0.0)
        return du * du + (v - cv) ** 2 <= radius * radius
    dv = np.maximum(np.abs(v - cv) - max(0.0, length / 2 - radius), 0.0)
    return (u - cu) ** 2 + dv * dv <= radius * radius


def _project_primitive(primitive: dict[str, Any], view: str, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    cx, cy, cz = (float(q) for q in primitive["center"])
    sx, sy, sz = (float(q) for q in primitive["size"])
    kind = primitive["type"]
    if view == "top":
        cu, cv, su, sv = cx, cy, sx, sy
        ray_axis = "z"
        plane_axes = ("x", "y")
    elif view == "side":
        cu, cv, su, sv = cx, cz, sx, sz
        ray_axis = "y"
        plane_axes = ("x", "z")
    else:
        raise ValueError(view)
    if kind == "box":
        return (np.abs(u - cu) <= su / 2) & (np.abs(v - cv) <= sv / 2)
    if kind == "ellipsoid":
        return ((u - cu) / (su / 2)) ** 2 + ((v - cv) / (sv / 2)) ** 2 <= 1
    axis = primitive.get("axis", "z")
    if axis == ray_axis:
        return ((u - cu) / (su / 2)) ** 2 + ((v - cv) / (sv / 2)) ** 2 <= 1
    if axis == plane_axes[0]:
        return _capsule_2d(u, v, cu, cv, su, sv / 2, True)
    return _capsule_2d(u, v, cu, cv, sv, su / 2, False)


def render_actor_masks(actor: list[dict[str, Any]], resolution: int = 96) -> tuple[np.ndarray, np.ndarray]:
    xs = _cell_centers("x", resolution)
    ys = _cell_centers("y", resolution)
    zs = _cell_centers("z", resolution)
    tx, ty = np.meshgrid(xs, ys, indexing="ij")
    sx, sz = np.meshgrid(xs, zs, indexing="ij")
    top = np.zeros((resolution, resolution), dtype=bool)
    side = np.zeros((resolution, resolution), dtype=bool)
    for primitive in actor:
        top |= _project_primitive(primitive, "top", tx, ty)
        side |= _project_primitive(primitive, "side", sx, sz)
    return top, side


def _primitive_occupancy(primitive: dict[str, Any], x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    cx, cy, cz = (float(q) for q in primitive["center"])
    sx, sy, sz = (float(q) for q in primitive["size"])
    dx, dy, dz = x - cx, y - cy, z - cz
    kind = primitive["type"]
    if kind == "box":
        return (np.abs(dx) <= sx / 2) & (np.abs(dy) <= sy / 2) & (np.abs(dz) <= sz / 2)
    if kind == "ellipsoid":
        return (dx / (sx / 2)) ** 2 + (dy / (sy / 2)) ** 2 + (dz / (sz / 2)) ** 2 <= 1
    axis = primitive.get("axis", "z")
    if axis == "x":
        return (np.abs(dx) <= sx / 2) & ((dy / (sy / 2)) ** 2 + (dz / (sz / 2)) ** 2 <= 1)
    if axis == "y":
        return (np.abs(dy) <= sy / 2) & ((dx / (sx / 2)) ** 2 + (dz / (sz / 2)) ** 2 <= 1)
    return (np.abs(dz) <= sz / 2) & ((dx / (sx / 2)) ** 2 + (dy / (sy / 2)) ** 2 <= 1)


def voxelize_actor(actor: list[dict[str, Any]], resolution: int = 64) -> np.ndarray:
    x, y, z = np.meshgrid(_cell_centers("x", resolution), _cell_centers("y", resolution), _cell_centers("z", resolution), indexing="ij", sparse=True)
    occupied = np.zeros((resolution, resolution, resolution), dtype=bool)
    for primitive in actor:
        occupied |= _primitive_occupancy(primitive, x, y, z)
    return occupied


def _largest_component(mask: np.ndarray) -> np.ndarray:
    labels, count = ndimage.label(mask.astype(bool), structure=np.ones((3, 3), dtype=np.uint8))
    if count == 0:
        return np.zeros_like(mask, dtype=bool)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    return labels == int(np.argmax(sizes))


def _mask_extent(mask: np.ndarray, axis_u: str, axis_v: str) -> tuple[float, float, float, float] | None:
    component = _largest_component(mask)
    points = np.argwhere(component)
    if not len(points):
        return None
    resolution = mask.shape[0]
    u0, u1 = int(points[:, 0].min()), int(points[:, 0].max()) + 1
    v0, v1 = int(points[:, 1].min()), int(points[:, 1].max()) + 1
    low_u, high_u = WORLD[axis_u]
    low_v, high_v = WORLD[axis_v]
    step_u, step_v = (high_u - low_u) / resolution, (high_v - low_v) / resolution
    center_u = low_u + (u0 + u1) * 0.5 * step_u
    center_v = low_v + (v0 + v1) * 0.5 * step_v
    return center_u, center_v, (u1 - u0) * step_u, (v1 - v0) * step_v


def observed_extent(top_mask: np.ndarray, side_mask: np.ndarray) -> dict[str, float] | None:
    top = _mask_extent(top_mask, "x", "y")
    side = _mask_extent(side_mask, "x", "z")
    if top is None or side is None:
        return None
    return {
        "center_x": 0.5 * (top[0] + side[0]),
        "center_y": top[1],
        "center_z": side[1],
        "size_x": 0.5 * (top[2] + side[2]),
        "size_y": top[3],
        "size_z": side[3],
    }


def _iou2d(a: np.ndarray, b: np.ndarray) -> float:
    union = int(np.count_nonzero(a | b))
    if union == 0:
        return 1.0
    return float(np.count_nonzero(a & b) / union)


def initialize_theta(graph_name: str, top_mask: np.ndarray, side_mask: np.ndarray) -> tuple[np.ndarray, bool]:
    extent = observed_extent(top_mask, side_mask)
    if extent is None:
        return default_theta(), True
    default_top, default_side = render_actor_masks(build_actor(graph_name, default_theta()), top_mask.shape[0])
    default_extent = observed_extent(default_top, default_side)
    if default_extent is None:
        raise RuntimeError("frozen graph has empty default projection")
    ratios = [
        extent["size_x"] / max(default_extent["size_x"], 1e-9),
        extent["size_y"] / max(default_extent["size_y"], 1e-9),
        extent["size_z"] / max(default_extent["size_z"], 1e-9),
    ]
    theta = default_theta()
    theta[:3] = np.log(np.clip(ratios, np.exp(BOUNDS[:3, 0]), np.exp(BOUNDS[:3, 1])))
    return theta, False


def objective(graph_name: str, theta: np.ndarray, top_mask: np.ndarray, side_mask: np.ndarray) -> tuple[float, dict[str, float]]:
    actor = build_actor(graph_name, theta)
    top_pred, side_pred = render_actor_masks(actor, top_mask.shape[0])
    top_iou, side_iou = _iou2d(top_pred, top_mask), _iou2d(side_pred, side_mask)
    regularizer = 0.01 * float(np.sum(theta[:3] ** 2)) + 0.005 * float((theta[3] - 1.0) ** 2) + 0.005 * float(theta[4] ** 2)
    value = 0.5 * (1.0 - top_iou) + 0.5 * (1.0 - side_iou) + regularizer
    return value, {"top_iou": top_iou, "side_iou": side_iou, "regularizer": regularizer}


def _candidate_key(value: float, details: dict[str, float], theta: np.ndarray) -> tuple[Any, ...]:
    return (round(value, 12), round(details["regularizer"], 12), *[round(float(v), 12) for v in theta])


def fit_graph(graph_name: str, top_mask: np.ndarray, side_mask: np.ndarray) -> dict[str, Any]:
    theta, empty = initialize_theta(graph_name, top_mask, side_mask)
    value, details = objective(graph_name, theta, top_mask, side_mask)
    evaluations = 1
    trace: list[dict[str, Any]] = [{"evaluation": 0, "theta": theta.tolist(), "objective": value, **details}]
    spans = BOUNDS[:, 1] - BOUNDS[:, 0]
    for fraction in STEP_FRACTIONS:
        for parameter_index, parameter_name in enumerate(PARAMETER_NAMES):
            candidates: list[tuple[float, dict[str, float], np.ndarray]] = [(value, details, theta.copy())]
            for direction in (-1.0, 1.0):
                proposal = theta.copy()
                proposal[parameter_index] = np.clip(proposal[parameter_index] + direction * fraction * spans[parameter_index], BOUNDS[parameter_index, 0], BOUNDS[parameter_index, 1])
                proposal_value, proposal_details = objective(graph_name, proposal, top_mask, side_mask)
                trace.append({"evaluation": evaluations, "step_fraction": fraction, "parameter": parameter_name, "direction": int(direction), "theta": proposal.tolist(), "objective": proposal_value, **proposal_details})
                evaluations += 1
                candidates.append((proposal_value, proposal_details, proposal))
            value, details, theta = min(candidates, key=lambda item: _candidate_key(item[0], item[1], item[2]))
    if evaluations != int(PROTOCOL["fit_candidate_budget"]):
        raise AssertionError(f"candidate budget drift: {evaluations}")
    return {
        "graph": graph_name,
        "theta": theta.tolist(),
        "objective": value,
        "top_iou": details["top_iou"],
        "side_iou": details["side_iou"],
        "regularizer": details["regularizer"],
        "empty_observation": empty,
        "evaluations": evaluations,
        "trace": trace,
        "actor": build_actor(graph_name, theta),
    }


def infer_method(method: str, family: str, top_mask: np.ndarray, side_mask: np.ndarray) -> dict[str, Any]:
    if method == "sppa_text_only":
        theta = default_theta()
        return {"method": method, "graph": family, "theta": theta.tolist(), "evaluations": 0, "actor": build_actor(family, theta)}
    if method == "sppa_mvfit":
        result = fit_graph(family, top_mask, side_mask)
        result["method"] = method
        return result
    if method == "generic_mvfit":
        result = fit_graph("generic", top_mask, side_mask)
        result["method"] = method
        return result
    raise ValueError(method)


def _primitive_from_extent(kind: str, extent: dict[str, float], axis: str = "z") -> list[dict[str, Any]]:
    return [{"slot_index": 0, "type": kind, "axis": axis, "secondary": False, "center": [extent["center_x"], extent["center_y"], extent["center_z"]], "size": [extent["size_x"], extent["size_y"], extent["size_z"]]}]


def _sample_mask(mask: np.ndarray, axis_u: str, axis_v: str, resolution: int) -> np.ndarray:
    us = _cell_centers(axis_u, resolution)
    vs = _cell_centers(axis_v, resolution)
    low_u, high_u = WORLD[axis_u]
    low_v, high_v = WORLD[axis_v]
    ui = np.clip(((us - low_u) / (high_u - low_u) * mask.shape[0]).astype(int), 0, mask.shape[0] - 1)
    vi = np.clip(((vs - low_v) / (high_v - low_v) * mask.shape[1]).astype(int), 0, mask.shape[1] - 1)
    return mask[np.ix_(ui, vi)]


def baseline_occupancy(method: str, top_mask: np.ndarray, side_mask: np.ndarray, resolution: int = 64) -> tuple[np.ndarray, dict[str, Any]]:
    extent = observed_extent(top_mask, side_mask)
    if extent is None:
        return np.zeros((resolution, resolution, resolution), dtype=bool), {"method": method, "empty_observation": True, "primitive_count": 0}
    if method == "bbox":
        actor = _primitive_from_extent("box", extent)
        return voxelize_actor(actor, resolution), {"method": method, "actor": actor, "primitive_count": 1}
    if method == "ellipsoid":
        actor = _primitive_from_extent("ellipsoid", extent)
        return voxelize_actor(actor, resolution), {"method": method, "actor": actor, "primitive_count": 1}
    if method == "capsule":
        radius_y = extent["size_y"] / 2
        radius_z = extent["size_z"] / 2
        cylinder_length = max(extent["size_x"] - 2 * min(radius_y, radius_z), 1e-4)
        central = {"slot_index": 0, "type": "cylinder", "axis": "x", "secondary": False, "center": [extent["center_x"], extent["center_y"], extent["center_z"]], "size": [cylinder_length, extent["size_y"], extent["size_z"]]}
        end_offset = cylinder_length / 2
        left = {"slot_index": 1, "type": "ellipsoid", "axis": "x", "secondary": False, "center": [extent["center_x"] - end_offset, extent["center_y"], extent["center_z"]], "size": [2 * min(radius_y, radius_z), extent["size_y"], extent["size_z"]]}
        right = {**left, "slot_index": 2, "center": [extent["center_x"] + end_offset, extent["center_y"], extent["center_z"]]}
        actor = [central, left, right]
        return voxelize_actor(actor, resolution), {"method": method, "actor": actor, "primitive_count": 3}
    top = _sample_mask(top_mask, "x", "y", resolution)
    side = _sample_mask(side_mask, "x", "z", resolution)
    if method == "nonsemantic_visual_hull":
        occupancy = top[:, :, None] & side[:, None, :]
        return occupancy, {"method": method, "primitive_count": int(np.count_nonzero(occupancy)), "voxel_representation": True}
    if method == "billboard":
        y_index = int(np.clip(round((extent["center_y"] - WORLD["y"][0]) / (WORLD["y"][1] - WORLD["y"][0]) * resolution - 0.5), 0, resolution - 1))
        z_index = int(np.clip(round((extent["center_z"] - WORLD["z"][0]) / (WORLD["z"][1] - WORLD["z"][0]) * resolution - 0.5), 0, resolution - 1))
        occupancy = np.zeros((resolution, resolution, resolution), dtype=bool)
        occupancy[:, :, z_index] |= top
        occupancy[:, y_index, :] |= side
        return occupancy, {"method": method, "primitive_count": 2, "voxel_representation": True}
    raise ValueError(method)


def complexity_metadata(method: str, actor: list[dict[str, Any]] | None = None, occupancy: np.ndarray | None = None) -> dict[str, int]:
    triangle_cost = {"box": 12, "ellipsoid": 160, "cylinder": 64}
    if actor is not None:
        primitive_count = len(actor)
        triangles = sum(triangle_cost[p["type"]] for p in actor)
        descriptor = json.dumps(actor, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {"primitive_count": primitive_count, "triangle_equiv": triangles, "descriptor_bytes": len(descriptor)}
    if occupancy is not None:
        count = int(np.count_nonzero(occupancy))
        return {"primitive_count": count, "triangle_equiv": count * 12, "descriptor_bytes": int(np.packbits(occupancy).nbytes)}
    return {"primitive_count": 0, "triangle_equiv": 0, "descriptor_bytes": 0}

