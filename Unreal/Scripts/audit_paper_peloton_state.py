import json
import math
import os
import re
from pathlib import Path

import unreal

LEVEL_PATH = "/Game/Ejea"
REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
WAYPOINTS_FILE = REPO / "pipeline" / "ejea_default.waypoints"

PELOTON_LABEL_RE = re.compile(r"^Peloton_Route_WP(?P<segment>\d+)_T(?P<t>\d+)_Cross$")
MIN_EXPECTED_PELOTON_COUNT = 18
MAX_RIDERS_PER_PELOTON = 8
MAX_RIDERS_PER_ROW = 3
EXPECTED_PELOTON_GROUND_MSL = float(os.environ.get("PORCE_PAPER_PELOTON_GROUND_MSL", "500.0")) + 0.08
PELOTON_GROUND_TOLERANCE_M = 3.0
BAD_RIDER_MATERIAL_TOKENS = (
    "/game/redspawn",
    "worldgridmaterial",
    "m_papercyclist_jerseyblue",
    "m_papercyclist_helmetwhite",
    "m_papercyclist_figurenavy",
)
TEMP_ACTOR_PREFIXES = ("DAT_",)
EXPECT_COWS_VISIBLE = (
    os.environ.get("PORCE_PAPER_EXPECT_COWS_VISIBLE", "1").strip().lower()
    not in {"0", "false", "no", "off"}
)
FORBIDDEN_ARTIFACT_TOKENS = (
    "dat_",
    "ghost",
    "prediction",
    "predicted",
    "predict",
    "future",
    "history",
    "bbox",
    "trackvector",
    "redspawn",
)


def actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def safe_text(value):
    return "" if value is None else str(value)


def actor_label(actor):
    try:
        return safe_text(actor.get_actor_label())
    except Exception:
        return safe_text(actor.get_name())


def actor_class(actor):
    try:
        return safe_text(actor.get_class().get_name())
    except Exception:
        return ""


def actor_folder(actor):
    try:
        return safe_text(actor.get_folder_path())
    except Exception:
        return ""


def actor_text(actor):
    return " ".join([actor_label(actor), safe_text(actor.get_name()), actor_class(actor), actor_folder(actor)]).lower()

def is_temp_actor(actor):
    label = actor_label(actor)
    name = safe_text(actor.get_name())
    return any(label.startswith(prefix) or name.startswith(prefix) for prefix in TEMP_ACTOR_PREFIXES)


def is_peloton_actor(actor):
    return "peloton" in actor_text(actor)


def is_loose_biker(actor):
    if is_peloton_actor(actor):
        return False
    text = actor_text(actor)
    folder = actor_folder(actor).strip("/\\").lower()
    return folder == "bikers" or "ciclista" in text or "bp_biker" in text or "biker" in text


def is_cow(actor):
    text = actor_text(actor)
    return actor_folder(actor).strip("/\\").lower() == "cows" or "cow" in text


def is_tower(actor):
    label = actor_label(actor).lower()
    text = actor_text(actor)
    return actor_folder(actor).strip("/\\").lower() == "towers" or "tower" in text or re.fullmatch(r"t\d+", label)


def segment_start_seq_from_peloton_label(label):
    match = PELOTON_LABEL_RE.match(label)
    if not match:
        return None
    return int(match.group("segment"))


def path_of_asset(asset):
    if asset is None:
        return None
    try:
        return safe_text(asset.get_path_name())
    except Exception:
        return safe_text(asset)

def has_morph_target(asset, target_name):
    if asset is None:
        return False
    desired = safe_text(target_name).lower()
    for method_name in ("get_all_morph_target_names", "get_morph_target_names"):
        method = getattr(asset, method_name, None)
        if callable(method):
            try:
                return desired in [safe_text(name).lower() for name in method()]
            except Exception:
                pass
    try:
        morph_targets = asset.get_editor_property("morph_targets")
        return desired in [safe_text(target.get_name()).lower() for target in morph_targets]
    except Exception:
        return False

def actor_material_paths(actor):
    material_paths = []
    try:
        components = actor.get_components_by_class(unreal.ActorComponent)
    except Exception:
        components = []
    for component in components:
        if not hasattr(component, "get_num_materials"):
            continue
        try:
            count = int(component.get_num_materials())
        except Exception:
            count = 0
        for index in range(count):
            try:
                material_paths.append(path_of_asset(component.get_material(index)))
            except Exception:
                pass
    return [path for path in material_paths if path]

def forbidden_artifact_row(actor):
    if is_peloton_actor(actor) or is_loose_biker(actor):
        return None
    text = actor_text(actor)
    materials = actor_material_paths(actor)
    material_text = " ".join(materials).lower()
    token_hits = [
        token
        for token in FORBIDDEN_ARTIFACT_TOKENS
        if token in text or token in material_text
    ]
    if not token_hits:
        return None
    return {
        "label": actor_label(actor),
        "name": safe_text(actor.get_name()),
        "class": actor_class(actor),
        "folder": actor_folder(actor),
        "is_tower": is_tower(actor),
        "is_cow": is_cow(actor),
        "is_temp_actor": is_temp_actor(actor),
        "token_hits": sorted(set(token_hits)),
        "materials": materials,
        "visibility": actor_visibility(actor),
    }


def get_prop(actor, name):
    try:
        return actor.get_editor_property(name)
    except Exception:
        return None


def route_spline(actor):
    try:
        spline = actor.get_editor_property("RouteSpline")
        if spline:
            return spline
    except Exception:
        pass
    return actor.get_component_by_class(unreal.SplineComponent)


def load_waypoints(path):
    points = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("QGC"):
            continue
        parts = line.split()
        if len(parts) < 12:
            continue
        cmd = int(float(parts[3]))
        if cmd not in (16, 21, 22):
            continue
        points.append(
            {
                "seq": int(float(parts[0])),
                "cmd": cmd,
                "lat": float(parts[8]),
                "lon": float(parts[9]),
                "alt_msl": float(parts[10]),
            }
        )
    return points


def georeference():
    for actor in actor_subsystem().get_all_level_actors():
        if "cesiumgeoreference" in actor_text(actor):
            return actor
    raise RuntimeError("CesiumGeoreference actor not found")


def llh_to_world(geo, wp):
    return geo.transform_longitude_latitude_height_position_to_unreal(
        unreal.Vector(float(wp["lon"]), float(wp["lat"]), float(wp["alt_msl"]))
    )

def world_to_llh(geo, world):
    llh = geo.transform_unreal_position_to_longitude_latitude_height(world)
    return {"lon": float(llh.x), "lat": float(llh.y), "height": float(llh.z)}


def normalize_xy(vec):
    size = math.sqrt(float(vec.x) ** 2 + float(vec.y) ** 2)
    if size <= 1e-6:
        return unreal.Vector(1.0, 0.0, 0.0)
    return unreal.Vector(float(vec.x) / size, float(vec.y) / size, 0.0)


def dot_xy(a, b):
    return float(a.x) * float(b.x) + float(a.y) * float(b.y)


def cross_xy(a, b):
    return float(a.x) * float(b.y) - float(a.y) * float(b.x)


def distance_xy(a, b):
    return math.sqrt((float(b.x) - float(a.x)) ** 2 + (float(b.y) - float(a.y)) ** 2)


def path_length_xy(points):
    if len(points) < 2:
        return 0.0
    total = 0.0
    for index in range(len(points) - 1):
        total += distance_xy(points[index], points[index + 1])
    return total


def max_off_axis_m(points):
    if len(points) < 2:
        return None
    start = points[0]
    end = points[-1]
    axis = normalize_xy(end - start)
    max_offset_cm = 0.0
    for point in points:
        max_offset_cm = max(max_offset_cm, abs(cross_xy(axis, point - start)))
    return max_offset_cm / 100.0


def vector_length_xy(value):
    if value is None:
        return 0.0
    return math.sqrt(float(value.x) ** 2 + float(value.y) ** 2)


def find_segment(waypoints, seq):
    for index in range(len(waypoints) - 1):
        if int(waypoints[index]["seq"]) == int(seq):
            return waypoints[index], waypoints[index + 1]
    return None, None


def component_rows(actor):
    rows = []
    try:
        components = actor.get_components_by_class(unreal.ActorComponent)
    except Exception:
        components = []
    for comp in components:
        name = safe_text(comp.get_name())
        cls = safe_text(comp.get_class().get_name())
        if "Peloton" not in name and "Ghost" not in name:
            continue
        mesh_path = None
        mat_paths = []
        try:
            mesh_path = path_of_asset(comp.get_editor_property("static_mesh"))
        except Exception:
            if hasattr(comp, "get_static_mesh"):
                try:
                    mesh_path = path_of_asset(comp.get_static_mesh())
                except Exception:
                    pass
        if not mesh_path:
            for prop_name in ("skeletal_mesh_asset", "skeletal_mesh"):
                try:
                    mesh_path = path_of_asset(comp.get_editor_property(prop_name))
                    if mesh_path:
                        break
                except Exception:
                    pass
        if not mesh_path and hasattr(comp, "get_skeletal_mesh_asset"):
            try:
                mesh_path = path_of_asset(comp.get_skeletal_mesh_asset())
            except Exception:
                pass
        if hasattr(comp, "get_num_materials"):
            try:
                for index in range(int(comp.get_num_materials())):
                    mat_paths.append(path_of_asset(comp.get_material(index)))
            except Exception:
                pass
        visibility = {}
        for method_name in ("is_visible", "is_hidden_in_game"):
            method = getattr(comp, method_name, None)
            if callable(method):
                try:
                    visibility[method_name] = bool(method())
                except Exception:
                    pass
        for prop_name in ("visible", "hidden_in_game"):
            try:
                visibility[prop_name] = bool(comp.get_editor_property(prop_name))
            except Exception:
                pass
        rows.append({"name": name, "class": cls, "mesh": mesh_path, "materials": mat_paths, "visibility": visibility})
    return rows

def actor_visibility(actor):
    state = {}
    for method_name in ("is_hidden", "is_hidden_ed", "is_temporarily_hidden_in_editor"):
        method = getattr(actor, method_name, None)
        if callable(method):
            try:
                state[method_name] = bool(method())
            except Exception:
                pass
    for prop_name in ("hidden", "hidden_in_game"):
        try:
            state[prop_name] = bool(actor.get_editor_property(prop_name))
        except Exception:
            pass
    return state


def actor_is_visible(actor):
    return not any(bool(value) for value in actor_visibility(actor).values() if value is not None)


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(LEVEL_PATH)
    actors = list(actor_subsystem().get_all_level_actors())
    waypoints = load_waypoints(WAYPOINTS_FILE)
    geo = georeference()

    pelotons = []
    peloton_actors = sorted(
        [actor for actor in actors if is_peloton_actor(actor)],
        key=lambda actor: actor_label(actor),
    )
    for actor in peloton_actors:
        label = actor_label(actor)
        segment_start_seq = segment_start_seq_from_peloton_label(label)
        spline = route_spline(actor)
        points = []
        point_count = 0
        if spline:
            try:
                point_count = int(spline.get_number_of_spline_points())
                for index in range(point_count):
                    p = spline.get_location_at_spline_point(index, unreal.SplineCoordinateSpace.WORLD)
                    points.append(p)
            except Exception:
                pass
        spline_is_closed_loop = None
        if spline:
            try:
                spline_is_closed_loop = bool(spline.is_closed_loop())
            except Exception:
                pass
        start_wp, end_wp = find_segment(waypoints, segment_start_seq) if segment_start_seq is not None else (None, None)
        perpendicular_dot_abs = None
        crossing_line_m = None
        route_length_m = None
        route_max_off_axis_m = max_off_axis_m(points)
        if len(points) >= 2:
            crossing_line_m = distance_xy(points[0], points[-1]) / 100.0
            route_length_m = path_length_xy(points) / 100.0
        if start_wp and end_wp and len(points) >= 2:
            along = normalize_xy(llh_to_world(geo, end_wp) - llh_to_world(geo, start_wp))
            crossing = normalize_xy(points[-1] - points[0])
            perpendicular_dot_abs = abs(dot_xy(along, crossing))
        spline_point_llh = [world_to_llh(geo, point) for point in points]
        spline_point_heights_msl = [float(row["height"]) for row in spline_point_llh]

        comps = component_rows(actor)
        rider_skeletal_mesh = get_prop(actor, "RiderSkeletalMesh")
        rider_skeletal_mesh_path = path_of_asset(rider_skeletal_mesh)
        legacy_rider_static_mesh = path_of_asset(get_prop(actor, "RiderStaticMesh"))
        uses_textured_skeletal = bool(
            rider_skeletal_mesh_path and "biker_text_pedal_loop" in rider_skeletal_mesh_path.lower()
        )
        bad_material_hits = [
            {
                "component": row["name"],
                "materials": row["materials"],
            }
            for row in comps
            if "PelotonRider" in row["name"]
            and any(
                token in safe_text(material).lower()
                for material in row["materials"]
                for token in BAD_RIDER_MATERIAL_TOKENS
            )
        ]
        pelotons.append(
            {
                "label": label,
                "segment_start_seq": segment_start_seq,
                "class": actor_class(actor),
                "folder": actor_folder(actor),
                "legacy_rider_static_mesh": legacy_rider_static_mesh,
                "rider_skeletal_mesh": rider_skeletal_mesh_path,
                "uses_textured_skeletal_mesh": uses_textured_skeletal,
                "pedal_morph_target_name": safe_text(get_prop(actor, "PedalMorphTargetName")),
                "pedal_morph_target_present": has_morph_target(rider_skeletal_mesh, get_prop(actor, "PedalMorphTargetName")),
                "animate_pedal_morph": bool(get_prop(actor, "bAnimatePedalMorph")),
                "pedal_cycle_seconds": float(get_prop(actor, "PedalCycleSeconds") or 0.0),
                "rider_material": path_of_asset(get_prop(actor, "RiderMaterial")),
                "rider_count": int(get_prop(actor, "RiderCount") or 0),
                "max_riders_per_row": int(get_prop(actor, "MaxRidersPerRow") or 0),
                "sync_to_target_actor": bool(get_prop(actor, "bSyncToTargetActor")),
                "sync_to_player_camera": bool(get_prop(actor, "bSyncToPlayerCamera")),
                "b_loop": bool(get_prop(actor, "bLoop")),
                "sync_target_actor_label": safe_text(get_prop(actor, "SyncTargetActorLabel")),
                "sync_approach_direction_len_xy": vector_length_xy(get_prop(actor, "SyncApproachDirection")),
                "sync_crossing_distance": float(get_prop(actor, "SyncCrossingDistance") or 0.0),
                "sync_target_speed_cm_s": float(get_prop(actor, "SyncTargetSpeedCmPerSecond") or 0.0),
                "actor_visibility": actor_visibility(actor),
                "spline_point_count": point_count,
                "spline_point_heights_msl": spline_point_heights_msl,
                "spline_is_closed_loop": spline_is_closed_loop,
                "crossing_line_m": crossing_line_m,
                "route_length_m": route_length_m,
                "route_max_off_axis_m": route_max_off_axis_m,
                "perpendicular_dot_abs": perpendicular_dot_abs,
                "forbidden_component_count": len([row for row in comps if "ghost" in row["name"].lower()]),
                "rider_component_count": len([row for row in comps if "PelotonRider" in row["name"]]),
                "bad_rider_material_hits": bad_material_hits,
                "components_sample": comps[:12],
            }
        )

    cow_actors = [actor for actor in actors if is_cow(actor)]
    tower_actors = [actor for actor in actors if is_tower(actor)]
    temp_actors = [actor for actor in actors if is_temp_actor(actor)]
    forbidden_artifacts = [
        row
        for row in (forbidden_artifact_row(actor) for actor in actors)
        if row
    ]
    cow_visible_count = len([actor for actor in cow_actors if actor_is_visible(actor)])
    tower_visible_count = len([actor for actor in tower_actors if actor_is_visible(actor)])
    cow_visibility_ok = (
        cow_visible_count == len(cow_actors)
        if EXPECT_COWS_VISIBLE
        else cow_visible_count == 0
    )
    payload = {
        "ok": True,
        "level": LEVEL_PATH,
        "pelotons": pelotons,
        "loose_biker_count": len([actor for actor in actors if is_loose_biker(actor)]),
        "temp_actor_count": len(temp_actors),
        "temp_actors": [
            {
                "label": actor_label(actor),
                "name": safe_text(actor.get_name()),
                "class": actor_class(actor),
                "folder": actor_folder(actor),
            }
            for actor in temp_actors
        ],
        "forbidden_artifact_count": len(forbidden_artifacts),
        "forbidden_artifacts": forbidden_artifacts,
        "cow_count": len(cow_actors),
        "cow_visible_count": cow_visible_count,
        "tower_count": len(tower_actors),
        "tower_visible_count": tower_visible_count,
        "expect_cows_visible": bool(EXPECT_COWS_VISIBLE),
        "expected_min_peloton_count": MIN_EXPECTED_PELOTON_COUNT,
        "max_riders_per_peloton": MAX_RIDERS_PER_PELOTON,
        "max_riders_per_row": MAX_RIDERS_PER_ROW,
        "expected_peloton_ground_msl": EXPECTED_PELOTON_GROUND_MSL,
        "peloton_ground_tolerance_m": PELOTON_GROUND_TOLERANCE_M,
        "cow_visible_note": "Final all-obstacle capture expects cows visible; set PORCE_PAPER_EXPECT_COWS_VISIBLE=0 for peloton-only captures.",
        "artifact_policy_note": "Prediction/temp geometry is forbidden; persistent DAT_* actors are also forbidden after scene preparation.",
    }
    payload["ok"] = (
        payload["loose_biker_count"] == 0
        and payload["temp_actor_count"] == 0
        and payload["forbidden_artifact_count"] == 0
        and len(pelotons) >= MIN_EXPECTED_PELOTON_COUNT
        and cow_visibility_ok
        and payload["tower_count"] > 0
        and payload["tower_visible_count"] == payload["tower_count"]
        and all(row.get("segment_start_seq") is not None for row in pelotons)
        and all(row.get("uses_textured_skeletal_mesh") for row in pelotons)
        and all(not row.get("legacy_rider_static_mesh") for row in pelotons)
        and all(
            row.get("pedal_morph_target_name") == "key_loop"
            and row.get("pedal_morph_target_present")
            and row.get("animate_pedal_morph")
            and float(row.get("pedal_cycle_seconds") or 0.0) > 0.0
            for row in pelotons
        )
        and all(row.get("rider_material") is None for row in pelotons)
        and all(not row.get("bad_rider_material_hits") for row in pelotons)
        and all(int(row.get("forbidden_component_count", 0)) == 0 for row in pelotons)
        and all(1 <= int(row.get("rider_count") or 0) <= MAX_RIDERS_PER_PELOTON for row in pelotons)
        and all(1 <= int(row.get("max_riders_per_row") or 0) <= MAX_RIDERS_PER_ROW for row in pelotons)
        and all(int(row.get("rider_component_count") or 0) == int(row.get("rider_count") or 0) for row in pelotons)
        and all(bool(row.get("sync_to_target_actor")) for row in pelotons)
        and all(bool(row.get("sync_to_player_camera")) for row in pelotons)
        and all(row.get("sync_target_actor_label") == "BP_AirplaneMarker" for row in pelotons)
        and all(float(row.get("sync_approach_direction_len_xy") or 0.0) > 0.98 for row in pelotons)
        and all(float(row.get("sync_crossing_distance") or 0.0) > 0.0 for row in pelotons)
        and all(float(row.get("sync_target_speed_cm_s") or 0.0) >= 100.0 for row in pelotons)
        and all(not any(row.get("actor_visibility", {}).values()) for row in pelotons)
        and all(int(row.get("spline_point_count") or 0) == 2 for row in pelotons)
        and all(
            all(
                abs(float(height) - EXPECTED_PELOTON_GROUND_MSL) <= PELOTON_GROUND_TOLERANCE_M
                for height in row.get("spline_point_heights_msl", [])
            )
            for row in pelotons
        )
        and all(row.get("spline_is_closed_loop") is False for row in pelotons)
        and all(bool(row.get("b_loop")) for row in pelotons)
        and all((row.get("route_max_off_axis_m") or 0.0) < 0.5 for row in pelotons)
        and all(row.get("perpendicular_dot_abs") is not None and row.get("perpendicular_dot_abs") < 0.02 for row in pelotons)
    )
    report_path = REPO / "pipeline" / "logs" / "paper_peloton_audit_latest.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_json = json.dumps(payload, indent=2, sort_keys=True)
    report_path.write_text(report_json + "\n", encoding="utf-8")
    print(report_json)
    print(f"Paper peloton audit report: {report_path}")
    if not payload["ok"]:
        raise RuntimeError("Paper peloton audit failed")


main()
