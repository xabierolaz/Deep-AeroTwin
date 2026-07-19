"""E7 "Real Stream Wave" - shared machinery (exploratory post-hoc, NOT sealed).

Benchmark of SPPA-MVFit and baselines on a REAL recorded UAV vision stream
(digital-twin flight over Ejea, Navarra; run 20260620_084932), under equal
conditions: ONE observation per detection, identical for every method.

Observation construction (documented, mirrors the operational pipeline):
  * Oriented ground footprint: GeoProjector.bbox_to_ground_footprint_m on the
    raw detector bbox (8 perimeter points -> ground plane via pinhole model,
    mavlink attitude, AGL; PCA oriented rect: center, length, width, yaw).
  * Height estimate: pipeline's own monocular estimator
    (vision_system._estimate_height_m_from_bbox logic): ray through the bbox
    top-center aligned in least squares to the vertical line over the
    projected bbox bottom-center base point; height = AGL - ray_down * t.
  * Family token from the REAL detector label (biker->rider_cycle,
    cow->quadruped, tower->lattice_tower). Detector errors are NOT cleaned.

The sealed fitter (method.sppa_mvfit) is reused read-only. Per case we set,
IN MEMORY ONLY (same monkeypatch style as e1..e6):
  * mv.WORLD  : per-case metric window centered on the footprint, x = footprint
                major axis, z = up from local ground.
  * mv.GRAPHS : meter-scaled copies of the frozen graphs. Frozen graphs are
                scale-normalized (a few "units"); a declared per-family nominal
                size maps units to meters (see FAMILY_NOMINAL_HEIGHT_M). The
                5-parameter theta and the frozen BOUNDS are untouched, so the
                reachable real sizes are nominal * [0.55, 1.80].

Nothing outside benchmarks/real_stream_wave/ is written.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
E7_ROOT = Path(__file__).resolve().parent
REPO_ROOT = E7_ROOT.parents[1]
PACKAGE_ROOT = REPO_ROOT / "reproducibility" / "sppa_mvfit"
PIPELINE_ROOT = Path(r"D:\Deep-AeroTwin-UE57-Test\pipeline")
STREAM_ROOT = PIPELINE_ROOT / "logs" / "zero_trust" / "20260620_084932" / "vision"
EVENTS_JSONL = STREAM_ROOT / "events.jsonl"
FRAMES_DIR = STREAM_ROOT / "frames"
GT_SPAWN_JSON = PIPELINE_ROOT / "logs" / "ejea_spawn_state_latest.json"

sys.path.insert(0, str(PACKAGE_ROOT))
sys.path.insert(0, str(PIPELINE_ROOT))

from method import sppa_mvfit as mv  # noqa: E402
from geo_projector import GeoProjector  # noqa: E402

EXPLORATORY_LABEL = "exploratory post-hoc analysis (not confirmatory)"

# ---------------------------------------------------------------------------
# Camera / geometry configuration of the RECORDED run.
# Values taken from the env files that were active for run 20260620_084932
# (pipeline/porce_defaults.env; the SPPA env does not override them) and from
# the vision_config event (capture 640x640, det_conf 0.10, SIMULATION mode
# -> DETECTION_RANGE_M = 80, clamp disabled).
# ---------------------------------------------------------------------------
CAMERA = {
    "image_width": 640,
    "image_height": 640,
    "vfov_deg": 70.0,        # PORCE_CAMERA_VFOV_DEG / PORCE_CAMERA_FOV_VERTICAL
    "mount_roll_deg": 0.0,   # PORCE_CAMERA_MOUNT_ROLL_DEG
    "mount_pitch_deg": -25.0,  # PORCE_CAMERA_MOUNT_PITCH_DEG
    "mount_yaw_deg": 0.0,    # PORCE_CAMERA_MOUNT_YAW_DEG
    "max_range_m": 80.0,     # DETECTION_RANGE_M (SIMULATION mode)
    "clamp_to_max_range": False,  # vision_config: project_clamp_to_max_range=false
    "min_agl_m": 0.5,        # GEOMETRY_MIN_AGL_M (porce default)
}
# Pipeline height-estimator constants (pipeline/constants.py defaults).
HEIGHT_ERR_MIN_M = 2.0       # VISION_HEIGHT_ERR_MIN_M
HEIGHT_ERR_SLOPE = 0.25      # VISION_HEIGHT_ERR_SLOPE
HEIGHT_DIST_FLOOR_M = 2.0    # VISION_HEIGHT_DIST_FLOOR_M
HEIGHT_CLAMP_M = 200.0       # VISION_HEIGHT_CLAMP_M
HEIGHT_MIN_VALID_M = 0.10    # E7 gate: non-informative estimates below this

# Operational AGL gate: the pipeline's own publish condition
# (vision_config: min_agl_to_publish_m = 10.0, geometry_ready). Observations
# below it are never published operationally, so they are not benchmark cases.
MIN_AGL_OPERATIONAL_M = 10.0

# Detector-label -> SPPA family token (declared mapping, fixed a priori).
CLASS_TO_FAMILY = {"biker": "rider_cycle", "cow": "quadruped", "tower": "lattice_tower"}

# Declared per-family nominal real-world height (m). Maps the frozen,
# scale-normalized graphs to meters. Fixed a priori from class semantics
# (transmission lattice tower ~25 m; cattle ~1.5 m at the shoulder;
# cyclist+bicycle ~1.8 m). NOT fitted to any GT.
FAMILY_NOMINAL_HEIGHT_M = {
    "lattice_tower": 25.0,
    "quadruped": 1.5,
    "rider_cycle": 1.8,
    "generic": 2.0,  # unused; generic graph uses the case family's scale
}

# Declared GT footprint assumptions (the spawn state gives anchor POINTS only;
# base dimensions are not in any log, so they are declared, not measured):
#   tower: square base 5.0 m x 5.0 m (rule of thumb base ~ height/5),
#          oriented by the anchor's world yaw;
#   cow:   rectangle 2.2 m x 0.9 m, oriented by the anchor's world yaw.
GT_FOOTPRINT_DIMS_M = {"tower": (5.0, 5.0), "cow": (2.2, 0.9)}
# GT association radii (declared): towers get a wide radius because the
# monocular footprint of a 25 m tower smears toward the drone; the cow is
# compact, so its center must be close. t0 <-> cow anchors are ~34 m apart,
# so these radii cannot create cross matches.
GT_MATCH_RADIUS_M = {"tower": 40.0, "cow": 10.0}

# Georeference origin of the twin (CesiumGeoreference actor in the spawn state).
ORIGIN = {"lat": 42.229695, "lon": -1.235085, "height": 500.0}
EARTH_RADIUS_M = 6371000.0

OBS_RES = int(mv.PROTOCOL["observation_resolution"])      # 96
EVAL_RES = 64                                             # sealed evaluation grid


# ---------------------------------------------------------------------------
# Frozen-graph metric scaling (in-memory copies; sealed graphs untouched)
# ---------------------------------------------------------------------------
# Pristine deep copy of the frozen graphs; mv.GRAPHS is monkeypatched per case
# and must never be used as the scaling source after the first patch.
import copy

ORIG_GRAPHS = copy.deepcopy(mv.GRAPHS)


def graph_extent_units(graph_name: str) -> tuple[float, float, float]:
    """Graph extents in GRAPH UNITS. Always reads the PRISTINE graphs
    (ORIG_GRAPHS); reading the per-case monkeypatched mv.GRAPHS here would
    double-apply the metric scale (bug fixed after the first E7 run)."""
    slots = ORIG_GRAPHS[graph_name]
    ext = []
    for axis in range(3):
        hi = max(float(s["center"][axis]) + float(s["size"][axis]) / 2 for s in slots)
        lo = min(float(s["center"][axis]) - float(s["size"][axis]) / 2 for s in slots)
        ext.append(hi - lo)
    return tuple(ext)  # type: ignore[return-value]


FAMILY_SCALE_M_PER_UNIT = {
    fam: FAMILY_NOMINAL_HEIGHT_M[fam] / graph_extent_units(fam)[2]
    for fam in CLASS_TO_FAMILY.values()
}


def scaled_graphs_for_family(family: str) -> dict[str, list[dict]]:
    """Meter-scaled copies of the case family graph AND the generic graph.

    The generic graph is scaled with the SAME factor (it must describe the
    same case in the same metric window; it just lacks the family prior).
    """
    k = FAMILY_SCALE_M_PER_UNIT[family]
    out: dict[str, list[dict]] = {}
    for name in (family, "generic"):
        slots = []
        for slot in ORIG_GRAPHS[name]:
            slots.append(
                {
                    "type": slot["type"],
                    "axis": slot.get("axis", "z"),
                    "secondary": bool(slot["secondary"]),
                    "center": [float(v) * k for v in slot["center"]],
                    "size": [float(v) * k for v in slot["size"]],
                }
            )
        out[name] = slots
    return out


# ---------------------------------------------------------------------------
# Stream parsing -> cases (one observation per accepted detection)
# ---------------------------------------------------------------------------
def llh_to_ne_m(lat: float, lon: float) -> tuple[float, float]:
    """Local NE offset (m) from the georeference origin."""
    dlat = math.radians(lat - ORIGIN["lat"])
    dlon = math.radians(lon - ORIGIN["lon"])
    return dlat * EARTH_RADIUS_M, dlon * EARTH_RADIUS_M * math.cos(math.radians(ORIGIN["lat"]))


def estimate_height_m(ray_top_ned: np.ndarray, base_north_m: float, base_east_m: float,
                      alt_agl_m: float, dist_h_m: float) -> float | None:
    """Line-by-line port of vision_system._estimate_height_m_from_bbox."""
    n, e, d = (float(v) for v in ray_top_ned)
    denom = n * n + e * e
    if denom <= 1e-12:
        return None
    t = (n * base_north_m + e * base_east_m) / denom
    if not math.isfinite(t) or t <= 0.0:
        return None
    err = math.hypot(n * t - base_north_m, e * t - base_east_m)
    if err > max(HEIGHT_ERR_MIN_M, HEIGHT_ERR_SLOPE * max(HEIGHT_DIST_FLOOR_M, dist_h_m)):
        return None
    height = alt_agl_m - d * t
    if not math.isfinite(height):
        return None
    return max(0.0, min(height, HEIGHT_CLAMP_M))


def build_observation(det: dict, tel: dict) -> dict | None:
    """One observation per detection: oriented footprint + height estimate."""
    bbox = det["bbox"]
    x1, y1, x2, y2 = (float(bbox[k]) for k in ("x1", "y1", "x2", "y2"))
    if x2 <= x1 or y2 <= y1:
        return None
    common = dict(
        image_height=CAMERA["image_height"],
        image_width=CAMERA["image_width"],
        drone_yaw_deg=float(tel["yaw"]),
        drone_pitch_deg=float(tel["pitch"]),
        drone_roll_deg=float(tel["roll"]),
        camera_vfov_deg=CAMERA["vfov_deg"],
        mount_roll_deg=CAMERA["mount_roll_deg"],
        mount_pitch_deg=CAMERA["mount_pitch_deg"],
        mount_yaw_deg=CAMERA["mount_yaw_deg"],
    )
    alt_agl = float(tel["alt_agl"])
    if not math.isfinite(alt_agl) or alt_agl < CAMERA["min_agl_m"]:
        return None

    footprint = GeoProjector.bbox_to_ground_footprint_m(
        (x1, y1, x2, y2),
        alt_agl_m=alt_agl,
        max_range_m=CAMERA["max_range_m"],
        clamp_to_max_range=CAMERA["clamp_to_max_range"],
        **common,
    )
    if footprint is None or footprint["length_m"] < 0.05 or footprint["width_m"] < 0.05:
        return None

    # Height: base = bbox bottom-center ground projection; top ray = bbox top-center.
    base = GeoProjector.pixel_to_ground_offset_m(
        y2, (x1 + x2) / 2.0, alt_agl_m=alt_agl, max_range_m=CAMERA["max_range_m"],
        clamp_to_max_range=CAMERA["clamp_to_max_range"], **common,
    )
    ray_top = GeoProjector.pixel_to_ray_ned(y1, (x1 + x2) / 2.0, **common)
    if base is None or ray_top is None:
        return None
    height = estimate_height_m(ray_top, base["north_m"], base["east_m"], alt_agl, base["distance_m"])
    if height is None or height < HEIGHT_MIN_VALID_M:
        return None

    return {
        "footprint": footprint,          # rel-drone NE, length/width/yaw
        "height_m": height,
        "base_north_m": base["north_m"],
        "base_east_m": base["east_m"],
        "base_distance_m": base["distance_m"],
        "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
    }


def iter_cases() -> tuple[list[dict], dict]:
    """Parse events.jsonl. Returns (cases, exclusion_counts)."""
    cases: list[dict] = []
    exclusions = {
        "telemetry_not_locked": 0,
        "below_operational_agl_10m": 0,
        "observation_failed": 0,
        "class_not_mapped": 0,
    }
    with EVENTS_JSONL.open("r", encoding="utf-8") as handle:
        for line in handle:
            event = json.loads(line)
            if event.get("kind") != "vision_frame":
                continue
            tel = event["telemetry"]
            frame = int(event["frame"])
            if float(tel["lat"]) == 0.0 and float(tel["lon"]) == 0.0:
                exclusions["telemetry_not_locked"] += len(event.get("detections") or [])
                continue
            for det_index, det in enumerate(event.get("detections") or []):
                det_class = str(det.get("type", ""))
                if det_class not in CLASS_TO_FAMILY:
                    exclusions["class_not_mapped"] += 1
                    continue
                if float(tel["alt_agl"]) < MIN_AGL_OPERATIONAL_M:
                    exclusions["below_operational_agl_10m"] += 1
                    continue
                obs = build_observation(det, tel)
                if obs is None:
                    exclusions["observation_failed"] += 1
                    continue
                drone_n, drone_e = llh_to_ne_m(float(tel["lat"]), float(tel["lon"]))
                cases.append(
                    {
                        "case_id": f"f{frame:05d}_d{det_index}",
                        "frame": frame,
                        "det_index": det_index,
                        "det_class": det_class,
                        "family": CLASS_TO_FAMILY[det_class],
                        "confidence": float(det["confidence"]),
                        "telemetry": {
                            "lat": float(tel["lat"]), "lon": float(tel["lon"]),
                            "alt_msl": float(tel["alt_msl"]), "alt_agl": float(tel["alt_agl"]),
                            "yaw": float(tel["yaw"]), "pitch": float(tel["pitch"]),
                            "roll": float(tel["roll"]),
                        },
                        "drone_north_m": drone_n,
                        "drone_east_m": drone_e,
                        "ground_msl_m": float(tel["alt_msl"]) - float(tel["alt_agl"]),
                        **obs,
                    }
                )
    return cases, exclusions


# ---------------------------------------------------------------------------
# Ground truth (static actors, exact simulator anchors)
# ---------------------------------------------------------------------------
def load_gt_static() -> list[dict]:
    payload = json.loads(GT_SPAWN_JSON.read_text(encoding="utf-8"))
    actors = []
    for actor in payload["actors"]:
        anchor = actor.get("globe_anchor_llh")
        label = str(actor.get("label") or "")
        if not anchor or not anchor.get("lat"):
            continue
        if label.startswith("t") and "tower" in label.lower() or label.startswith("t") and label[1:].isdigit():
            cls = "tower"
        elif "cow" in label.lower():
            cls = "cow"
        else:
            continue
        n, e = llh_to_ne_m(float(anchor["lat"]), float(anchor["lon"]))
        actors.append(
            {
                "label": label,
                "cls": cls,
                "lat": float(anchor["lat"]),
                "lon": float(anchor["lon"]),
                "height_msl": float(anchor["height"]),
                "north_m": n,
                "east_m": e,
                "yaw_deg": float(actor.get("world_rotation", {}).get("yaw", 0.0)),
            }
        )
    return actors


def match_gt(case: dict, gt_actors: list[dict]) -> dict | None:
    """Nearest static anchor within its class-specific radius (declared)."""
    fp = case["footprint"]
    cn = case["drone_north_m"] + fp["center_north_m"]
    ce = case["drone_east_m"] + fp["center_east_m"]
    best, best_d = None, math.inf
    for actor in gt_actors:
        d = math.hypot(actor["north_m"] - cn, actor["east_m"] - ce)
        if d <= GT_MATCH_RADIUS_M[actor["cls"]] and d < best_d:
            best, best_d = actor, d
    if best is None:
        return None
    return {**best, "match_distance_m": best_d}
