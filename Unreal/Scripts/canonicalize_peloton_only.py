import json
import math
import os
import traceback
from pathlib import Path

import unreal

LEVEL_PATH = "/Game/Ejea"
PELOTON_BP_PATH = "/Game/Peloton/BP_PelotonSpline"
TEXTURED_RIDER_SKELETAL_MESH_PATH = (
    "/Game/Peloton/TexturedBiker/biker_text_pedal_loop/SkeletalMeshes/"
    "biker_text_pedal_loop.biker_text_pedal_loop"
)
PELOTON_MATERIAL_DIR = "/Game/Peloton/Materials"
PAPER_CONTEXT_MATERIAL_SPECS = [
    ("M_PaperContextGroundSage", (0.16, 0.22, 0.13), 0.92, 0.02),
    ("M_PaperContextRoadAsphalt", (0.075, 0.078, 0.075), 0.88, 0.02),
    ("M_PaperContextRouteCyan", (0.0, 0.32, 0.54), 0.64, 0.04),
    ("M_PaperContextSkySoft", (0.36, 0.52, 0.72), 0.84, 0.02),
]
REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
WAYPOINTS_FILE = REPO / "pipeline" / "ejea_default.waypoints"
MISSION_NOMINAL_GROUND_SPEED_MPS = max(0.1, float(os.environ.get("PORCE_PAPER_DRONE_GROUND_SPEED_MPS", "7.0")))
MISSION_TAKEOFF_DELAY_S = max(0.0, float(os.environ.get("PORCE_PAPER_TAKEOFF_DELAY_S", "25.0")))

BASE_PELOTON_SETTINGS = {
    "RiderCount": 8,
    "MaxRidersPerRow": 3,
    "LongitudinalSpacing": 190.0,
    "LateralSpacing": 105.0,
    "AlternateRowLateralStagger": 35.0,
    "RiderZOffset": 0.0,
    "SpeedCmPerSecond": 640.0,
    "StartDistance": 0.0,
    "EditorPreviewDistance": 0.0,
    "bLoop": True,
    "bAnimateInGame": True,
    "bAnimateInEditor": False,
    "bFaceAlongSpline": True,
    "RiderYawOffset": 0.0,
    "bRidersCastShadows": False,
    "bAnimatePedalMorph": True,
    "PedalMorphTargetName": "key_loop",
    "PedalCycleSeconds": 0.55,
    "PedalMorphMin": 0.0,
    "PedalMorphMax": 1.0,
    "PedalPhaseOffsetPerRider": 0.137,
}

PELOTON_SEGMENT_START_SEQS = tuple(range(1, 10))
PELOTON_CROSSING_T_VALUES = (0.30, 0.70)
PELOTON_CROSSING_HALF_WIDTH_M = 48.0
PELOTON_GROUND_HEIGHT_MSL = float(os.environ.get("PORCE_PAPER_PELOTON_GROUND_MSL", "500.0"))
PELOTON_GROUND_CLEARANCE_CM = 8.0
PELOTON_GROUND_CLEARANCE_M = PELOTON_GROUND_CLEARANCE_CM / 100.0
PELOTON_GROUND_HEIGHT_SOURCE = (
    "Mission/Cesium runtime baseline from ejea_default.waypoints: home/land terrain "
    "altitude is 500 m MSL and runtime detections report ground objects at about 500-502 m MSL."
)
PELOTON_GROUND_ELEVATION_MSL_BY_SEQ = {seq: PELOTON_GROUND_HEIGHT_MSL for seq in range(0, 12)}


def build_peloton_route_specs():
    specs = []
    for segment_start_seq in PELOTON_SEGMENT_START_SEQS:
        for crossing_index, t in enumerate(PELOTON_CROSSING_T_VALUES, start=1):
            direction = 1.0
            rider_count = 6 + 2 * ((segment_start_seq + crossing_index) % 2)
            speed_cm_s = 560.0 + float((segment_start_seq * 37 + crossing_index * 29) % 120)
            specs.append(
                {
                    "label": "Peloton_Route_WP%02d_T%02d_Cross" % (
                        segment_start_seq,
                        int(round(t * 100.0)),
                    ),
                    "segment_start_seq": segment_start_seq,
                    "t": t,
                    "direction": direction,
                    "rider_count": rider_count,
                    "max_riders_per_row": 3,
                    "speed_cm_s": speed_cm_s,
                    "crossing_half_width_m": PELOTON_CROSSING_HALF_WIDTH_M,
                }
            )
    return specs


PELOTON_ROUTE_SPECS = build_peloton_route_specs()

LEGACY_CYCLIST_TOKENS = (
    "ciclista",
    "ciclista1",
    "ciclista2",
    "bp_biker",
)


def actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def safe_text(value):
    if value is None:
        return ""
    return str(value)


def actor_label(actor):
    try:
        return safe_text(actor.get_actor_label())
    except Exception:
        return safe_text(actor.get_name())


def actor_folder(actor):
    try:
        return safe_text(actor.get_folder_path())
    except Exception:
        return ""


def actor_class(actor):
    try:
        return safe_text(actor.get_class().get_name())
    except Exception:
        return ""


def actor_text(actor):
    return " ".join(
        [
            actor_label(actor),
            safe_text(actor.get_name()),
            actor_class(actor),
            actor_folder(actor),
        ]
    ).lower()


def is_peloton_actor(actor):
    return "peloton" in actor_text(actor)


def component_static_mesh_path(component):
    mesh = None
    try:
        mesh = component.get_editor_property("static_mesh")
    except Exception:
        pass
    if mesh is None:
        try:
            mesh = component.get_static_mesh()
        except Exception:
            pass
    if mesh is None:
        return ""
    try:
        return safe_text(mesh.get_path_name())
    except Exception:
        return safe_text(mesh)


def actor_uses_loose_biker_mesh(actor):
    try:
        components = actor.get_components_by_class(unreal.StaticMeshComponent)
    except Exception:
        return False
    for component in components:
        mesh_path = component_static_mesh_path(component).lower()
        if "/game/biker_mesh" in mesh_path:
            return True
    return False


def is_loose_cyclist_actor(actor):
    if is_peloton_actor(actor):
        return False

    text = actor_text(actor)
    folder = actor_folder(actor).strip("/\\").lower()
    if folder == "bikers":
        return True
    if any(token in text for token in LEGACY_CYCLIST_TOKENS):
        return True
    if "biker" in text and "biker_mesh" not in text:
        return True
    return actor_uses_loose_biker_mesh(actor)


def actor_row(actor):
    return {
        "label": actor_label(actor),
        "name": safe_text(actor.get_name()),
        "class": actor_class(actor),
        "folder": actor_folder(actor),
    }


def vec(value):
    return {"x": float(value.x), "y": float(value.y), "z": float(value.z)}


def load_asset(path):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset:
        return asset
    return unreal.load_object(None, path)

def create_color_material(name, color, roughness=0.65, specular=0.08):
    package_path = PELOTON_MATERIAL_DIR + "/" + name
    if unreal.EditorAssetLibrary.does_asset_exist(package_path):
        existing = unreal.EditorAssetLibrary.load_asset(package_path)
        if existing:
            return existing

    unreal.EditorAssetLibrary.make_directory(PELOTON_MATERIAL_DIR)
    factory = unreal.MaterialFactoryNew()
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name,
        PELOTON_MATERIAL_DIR,
        unreal.Material,
        factory,
    )
    if not material:
        return None

    material.set_editor_property("two_sided", True)
    base = unreal.MaterialEditingLibrary.create_material_expression(
        material,
        unreal.MaterialExpressionConstant3Vector,
        -400,
        -80,
    )
    base.set_editor_property("constant", unreal.LinearColor(color[0], color[1], color[2], 1.0))
    unreal.MaterialEditingLibrary.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)

    rough = unreal.MaterialEditingLibrary.create_material_expression(
        material,
        unreal.MaterialExpressionConstant,
        -400,
        80,
    )
    rough.set_editor_property("r", float(roughness))
    unreal.MaterialEditingLibrary.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)

    spec = unreal.MaterialEditingLibrary.create_material_expression(
        material,
        unreal.MaterialExpressionConstant,
        -400,
        210,
    )
    spec.set_editor_property("r", float(specular))
    unreal.MaterialEditingLibrary.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR)

    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material

def ensure_paper_context_materials():
    materials = []
    for name, color, roughness, specular in PAPER_CONTEXT_MATERIAL_SPECS:
        material = create_color_material(name, color, roughness, specular)
        if material:
            materials.append(material)
    return materials


def load_peloton_class():
    load_blueprint_class = getattr(unreal.EditorAssetLibrary, "load_blueprint_class", None)
    if callable(load_blueprint_class):
        peloton_class = load_blueprint_class(PELOTON_BP_PATH)
        if peloton_class:
            return peloton_class
    return unreal.load_object(None, PELOTON_BP_PATH + "." + PELOTON_BP_PATH.rsplit("/", 1)[-1] + "_C")


def set_property(actor, key, value):
    try:
        actor.set_editor_property(key, value)
        return True
    except Exception:
        return False


def destroy_legacy_prediction_components(actor):
    removed = []
    try:
        components = actor.get_components_by_class(unreal.ActorComponent)
    except Exception:
        return removed
    for component in components:
        name = safe_text(component.get_name())
        if "ghost" not in name.lower():
            continue
        try:
            component.destroy_component()
            removed.append(name)
        except Exception:
            pass
    return removed


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
        lat = float(parts[8])
        lon = float(parts[9])
        alt = float(parts[10])
        if abs(lat) < 0.0001 or abs(lon) < 0.0001:
            continue
        if cmd not in (16, 21, 22):
            continue
        points.append({"seq": int(float(parts[0])), "cmd": cmd, "lat": lat, "lon": lon, "alt_msl": alt})
    return points


def georeference():
    for actor in actor_subsystem().get_all_level_actors():
        if "CesiumGeoreference" in actor_label(actor) or actor_class(actor) == "CesiumGeoreference":
            return actor
    raise RuntimeError("CesiumGeoreference actor not found")


def llh_to_world(geo, lon, lat, height):
    return geo.transform_longitude_latitude_height_position_to_unreal(
        unreal.Vector(float(lon), float(lat), float(height))
    )


def world_to_llh(geo, world):
    llh = geo.transform_unreal_position_to_longitude_latitude_height(world)
    return {"lon": float(llh.x), "lat": float(llh.y), "height": float(llh.z)}


def interpolate_waypoint(a, b, t, height_override=None):
    height = float(a["alt_msl"]) + (float(b["alt_msl"]) - float(a["alt_msl"])) * float(t)
    if height_override is not None:
        height = float(height_override)
    return {
        "lat": float(a["lat"]) + (float(b["lat"]) - float(a["lat"])) * float(t),
        "lon": float(a["lon"]) + (float(b["lon"]) - float(a["lon"])) * float(t),
        "height": height,
    }


def terrain_height_msl_for_segment(a, b, t):
    a_height = PELOTON_GROUND_ELEVATION_MSL_BY_SEQ.get(int(a["seq"]), PELOTON_GROUND_HEIGHT_MSL)
    b_height = PELOTON_GROUND_ELEVATION_MSL_BY_SEQ.get(int(b["seq"]), a_height)
    return float(a_height) + (float(b_height) - float(a_height)) * float(t) + PELOTON_GROUND_CLEARANCE_M


def normalize_xy(value):
    size = math.sqrt(float(value.x) * float(value.x) + float(value.y) * float(value.y))
    if size <= 1e-6:
        return unreal.Vector(1.0, 0.0, 0.0)
    return unreal.Vector(float(value.x) / size, float(value.y) / size, 0.0)


def distance(a, b):
    delta = b - a
    return math.sqrt(float(delta.x) ** 2 + float(delta.y) ** 2 + float(delta.z) ** 2)


def editor_world():
    subsystem_class = getattr(unreal, "UnrealEditorSubsystem", None)
    if subsystem_class:
        try:
            subsystem = unreal.get_editor_subsystem(subsystem_class)
            if subsystem:
                world = subsystem.get_editor_world()
                if world:
                    return world
        except Exception:
            pass
    return unreal.EditorLevelLibrary.get_editor_world()


def hit_result_location(hit_result):
    for prop_name in ("impact_point", "location"):
        try:
            value = hit_result.get_editor_property(prop_name)
            if value is not None:
                return value
        except Exception:
            pass
    for attr_name in ("impact_point", "location"):
        try:
            value = getattr(hit_result, attr_name)
            if value is not None:
                return value
        except Exception:
            pass
    return None


def trace_ground_at_world_xy(point, ignore_actors=None):
    world = editor_world()
    if world is None:
        return None

    trace_type = getattr(unreal.TraceTypeQuery, "TRACE_TYPE_QUERY1", None)
    draw_debug = getattr(unreal.DrawDebugTrace, "NONE", None)
    if trace_type is None or draw_debug is None:
        return None

    start = unreal.Vector(float(point.x), float(point.y), float(point.z) + 50000.0)
    end = unreal.Vector(float(point.x), float(point.y), float(point.z) - 100000.0)
    try:
        result = unreal.SystemLibrary.line_trace_single(
            world,
            start,
            end,
            trace_type,
            True,
            ignore_actors or [],
            draw_debug,
            True,
            unreal.LinearColor(1.0, 0.0, 0.0, 1.0),
            unreal.LinearColor(0.0, 1.0, 0.0, 1.0),
            0.0,
        )
    except Exception:
        return None

    if not result:
        return None
    try:
        hit, hit_result = result
    except Exception:
        return None
    if not hit:
        return None
    hit_location = hit_result_location(hit_result)
    if hit_location is None:
        return None
    return unreal.Vector(float(point.x), float(point.y), float(hit_location.z) + PELOTON_GROUND_CLEARANCE_CM)


def path_length(points):
    if len(points) < 2:
        return 0.0
    total = 0.0
    for index in range(len(points) - 1):
        total += distance(points[index], points[index + 1])
    return total


def mission_distance_to_crossing(geo, waypoints, segment_index, center_llh):
    total = 0.0
    for index in range(segment_index):
        a = waypoints[index]
        b = waypoints[index + 1]
        aw = llh_to_world(geo, a["lon"], a["lat"], a["alt_msl"])
        bw = llh_to_world(geo, b["lon"], b["lat"], b["alt_msl"])
        total += distance(aw, bw) / 100.0

    start = waypoints[segment_index]
    start_w = llh_to_world(geo, start["lon"], start["lat"], start["alt_msl"])
    center_w = llh_to_world(geo, center_llh["lon"], center_llh["lat"], center_llh["height"])
    total += distance(start_w, center_w) / 100.0
    return total


def normalize_distance(distance_cm, length_cm):
    if length_cm <= 1e-6:
        return max(0.0, float(distance_cm))
    wrapped = math.fmod(float(distance_cm), float(length_cm))
    if wrapped < 0.0:
        wrapped += float(length_cm)
    return wrapped


def find_segment_by_start_seq(waypoints, seq):
    for index in range(len(waypoints) - 1):
        if int(waypoints[index]["seq"]) == int(seq):
            return index, waypoints[index], waypoints[index + 1]
    raise RuntimeError("Waypoint segment starting at seq %s not found" % seq)


def build_crossing_route(geo, waypoints, spec, ignore_actors=None):
    index, start_wp, end_wp = find_segment_by_start_seq(waypoints, spec["segment_start_seq"])
    height = terrain_height_msl_for_segment(start_wp, end_wp, spec["t"])
    center_llh = interpolate_waypoint(start_wp, end_wp, spec["t"], height_override=height)
    mission_center_llh = interpolate_waypoint(start_wp, end_wp, spec["t"], height_override=None)
    center = llh_to_world(geo, center_llh["lon"], center_llh["lat"], center_llh["height"])
    start_world = llh_to_world(geo, start_wp["lon"], start_wp["lat"], height)
    end_world = llh_to_world(geo, end_wp["lon"], end_wp["lat"], height)

    along = normalize_xy(end_world - start_world)
    side_sign = 1.0 if float(spec.get("direction", 1.0)) >= 0.0 else -1.0
    right = unreal.Vector(-along.y * side_sign, along.x * side_sign, 0.0)

    half = float(spec["crossing_half_width_m"]) * 100.0

    raw_points = [
        center - right * half,
        center + right * half,
    ]
    points = []
    ground_samples = []
    for point in raw_points:
        ground_point = trace_ground_at_world_xy(point, ignore_actors=ignore_actors)
        if ground_point is None:
            points.append(point)
            ground_samples.append(
                {
                    "hit": False,
                    "source": "dem_fallback",
                    "world": vec(point),
                    "llh": world_to_llh(geo, point),
                }
            )
            continue
        points.append(ground_point)
        ground_samples.append(
            {
                "hit": True,
                "source": "line_trace",
                "world": vec(ground_point),
                "llh": world_to_llh(geo, ground_point),
            }
        )
    center = (points[0] + points[1]) * 0.5
    center_llh = world_to_llh(geo, center)
    distance_to_crossing = half
    route_length_cm = path_length(points)
    mission_distance_m = mission_distance_to_crossing(geo, waypoints, index, mission_center_llh)
    drone_eta_s = MISSION_TAKEOFF_DELAY_S + mission_distance_m / MISSION_NOMINAL_GROUND_SPEED_MPS
    peloton_speed_cm_s = float(spec["speed_cm_s"])
    runtime_start_distance_cm = normalize_distance(
        distance_to_crossing - peloton_speed_cm_s * drone_eta_s,
        route_length_cm,
    )
    return {
        "segment_index": index,
        "segment_start_seq": int(start_wp["seq"]),
        "segment_end_seq": int(end_wp["seq"]),
        "center_llh": center_llh,
        "mission_center_llh": mission_center_llh,
        "center_world": center,
        "points": points,
        "ground_samples": ground_samples,
        "distance_to_crossing_cm": distance_to_crossing,
        "route_length_cm": route_length_cm,
        "mission_distance_to_crossing_m": mission_distance_m,
        "drone_eta_s": drone_eta_s,
        "runtime_start_distance_cm": runtime_start_distance_cm,
        "approach_direction": along,
    }


def route_spline(actor):
    try:
        spline = actor.get_editor_property("RouteSpline")
        if spline:
            return spline
    except Exception:
        pass
    return actor.get_component_by_class(unreal.SplineComponent)


def set_spline_route(actor, points):
    spline = route_spline(actor)
    if not spline:
        raise RuntimeError("Peloton actor %s has no RouteSpline" % actor_label(actor))
    try:
        spline.modify()
    except Exception:
        pass
    spline.clear_spline_points(False)
    for point in points:
        spline.add_spline_point(point, unreal.SplineCoordinateSpace.WORLD, False)
    spline.set_closed_loop(False)
    spline.update_spline()
    return len(points)


def configure_peloton(actor, spec, route):
    try:
        actor.modify()
    except Exception:
        pass

    applied = {}
    removed_legacy_components = destroy_legacy_prediction_components(actor)
    if removed_legacy_components:
        applied["RemovedLegacyPredictionComponents"] = removed_legacy_components
    textured_rider_mesh = load_asset(TEXTURED_RIDER_SKELETAL_MESH_PATH)
    if not textured_rider_mesh:
        raise RuntimeError("Missing required textured rider skeletal mesh: %s" % TEXTURED_RIDER_SKELETAL_MESH_PATH)
    applied["RiderSkeletalMesh"] = set_property(actor, "RiderSkeletalMesh", textured_rider_mesh)
    applied["RiderMaterial"] = set_property(actor, "RiderMaterial", None)

    settings = dict(BASE_PELOTON_SETTINGS)
    settings.update(
        {
            "RiderCount": int(spec["rider_count"]),
            "MaxRidersPerRow": int(spec["max_riders_per_row"]),
            "SpeedCmPerSecond": float(spec["speed_cm_s"]),
            "StartDistance": float(route["runtime_start_distance_cm"]),
            "EditorPreviewDistance": float(route["distance_to_crossing_cm"]),
            "bSyncToTargetActor": True,
            "bSyncToPlayerCamera": True,
            "SyncTargetActorLabel": "BP_AirplaneMarker",
            "SyncApproachDirection": unreal.Vector(float(route["approach_direction"].x), float(route["approach_direction"].y), 0.0),
            "SyncTargetSpeedCmPerSecond": float(MISSION_NOMINAL_GROUND_SPEED_MPS) * 100.0,
            "SyncCrossingDistance": float(route["distance_to_crossing_cm"]),
            "SyncPhaseOffset": 520.0,
        }
    )

    for key, value in settings.items():
        applied[key] = set_property(actor, key, value)

    try:
        actor.set_folder_path("Peloton")
    except Exception:
        pass
    try:
        actor.set_actor_tick_enabled(True)
    except Exception:
        pass
    try:
        actor.set_preview_distance(settings["EditorPreviewDistance"])
    except Exception:
        pass
    try:
        actor.rebuild_peloton()
    except Exception:
        pass
    return applied


def set_peloton_label(actor, label):
    try:
        actor.set_actor_label(label)
    except Exception:
        pass


def find_pelotons():
    return [actor for actor in actor_subsystem().get_all_level_actors() if is_peloton_actor(actor)]


def spawn_peloton(label):
    peloton_class = load_peloton_class()
    if not peloton_class:
        raise RuntimeError("Could not load peloton blueprint class: %s" % PELOTON_BP_PATH)
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        peloton_class,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
    )
    actor.set_actor_label(label)
    return actor


def ensure_scripted_pelotons():
    desired_labels = [spec["label"] for spec in PELOTON_ROUTE_SPECS]
    existing = find_pelotons()
    by_label = {actor_label(actor): actor for actor in existing}
    reusable = [actor for actor in existing if actor_label(actor) not in desired_labels]
    result = {}

    for label in desired_labels:
        actor = by_label.get(label)
        if actor is None and reusable:
            actor = reusable.pop(0)
            set_peloton_label(actor, label)
        if actor is None:
            actor = spawn_peloton(label)
        result[label] = actor

    destroyed_extra = []
    for actor in reusable:
        row = actor_row(actor)
        try:
            actor_subsystem().destroy_actor(actor)
            row["destroyed"] = True
        except Exception as exc:
            row["destroyed"] = False
            row["error"] = str(exc)
        destroyed_extra.append(row)
    return result, destroyed_extra


def destroy_loose_cyclists():
    subsystem = actor_subsystem()
    destroyed = []
    for actor in list(subsystem.get_all_level_actors()):
        if not is_loose_cyclist_actor(actor):
            continue
        row = actor_row(actor)
        try:
            subsystem.destroy_actor(actor)
            row["destroyed"] = True
        except Exception as exc:
            row["destroyed"] = False
            row["error"] = str(exc)
        destroyed.append(row)
    return destroyed


def dirty_package_names():
    dirty = []
    for fn_name in ("get_dirty_content_packages", "get_dirty_map_packages"):
        fn = getattr(unreal.EditorLoadingAndSavingUtils, fn_name, None)
        if not fn:
            continue
        for package in fn():
            try:
                dirty.append(str(package.get_name()))
            except Exception:
                dirty.append(str(package))
    return sorted(set(dirty))


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(LEVEL_PATH)
    context_materials = ensure_paper_context_materials()
    destroyed_loose = destroy_loose_cyclists()
    geo = georeference()
    waypoints = load_waypoints(WAYPOINTS_FILE)
    if len(waypoints) < 2:
        raise RuntimeError("Not enough waypoints loaded from %s" % WAYPOINTS_FILE)

    pelotons_by_label, destroyed_extra = ensure_scripted_pelotons()
    configured = []
    for spec in PELOTON_ROUTE_SPECS:
        peloton = pelotons_by_label[spec["label"]]
        route = build_crossing_route(geo, waypoints, spec, ignore_actors=list(pelotons_by_label.values()))
        point_count = set_spline_route(peloton, route["points"])
        configured.append(
            {
                "actor": actor_row(peloton),
                "route": {
                    "segment_start_seq": route["segment_start_seq"],
                    "segment_end_seq": route["segment_end_seq"],
                    "center_llh": route["center_llh"],
                    "mission_center_llh": route["mission_center_llh"],
                    "center_world": vec(route["center_world"]),
                    "point_count": point_count,
                    "distance_to_crossing_m": float(route["distance_to_crossing_cm"]) / 100.0,
                    "runtime_start_distance_m": float(route["runtime_start_distance_cm"]) / 100.0,
                    "route_length_m": float(route["route_length_cm"]) / 100.0,
                    "mission_distance_to_crossing_m": float(route["mission_distance_to_crossing_m"]),
                    "drone_eta_s": float(route["drone_eta_s"]),
                    "approach_direction": vec(route["approach_direction"]),
                    "spline_points_world": [vec(point) for point in route["points"]],
                    "ground_samples": route["ground_samples"],
                },
                "applied": configure_peloton(peloton, spec, route),
            }
        )

    remaining_loose = [
        actor_row(actor)
        for actor in actor_subsystem().get_all_level_actors()
        if is_loose_cyclist_actor(actor)
    ]
    actual_labels = sorted(actor_label(actor) for actor in find_pelotons())
    desired_labels = sorted(spec["label"] for spec in PELOTON_ROUTE_SPECS)
    missing_labels = [label for label in desired_labels if label not in actual_labels]

    dirty_before_save = dirty_package_names()
    saved = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(
        save_map_packages=True,
        save_content_packages=True,
    )
    dirty_after_save = dirty_package_names()

    payload = {
        "ok": len(remaining_loose) == 0 and len(missing_labels) == 0,
        "level": LEVEL_PATH,
        "waypoints_file": str(WAYPOINTS_FILE),
        "waypoints_loaded": len(waypoints),
        "sync": {
            "nominal_drone_ground_speed_mps": float(MISSION_NOMINAL_GROUND_SPEED_MPS),
            "takeoff_delay_s": float(MISSION_TAKEOFF_DELAY_S),
        },
        "terrain": {
            "height_source": PELOTON_GROUND_HEIGHT_SOURCE,
            "ground_clearance_m": float(PELOTON_GROUND_CLEARANCE_M),
            "waypoint_elevation_msl": dict(PELOTON_GROUND_ELEVATION_MSL_BY_SEQ),
        },
        "destroyed_loose_cyclist_actors": destroyed_loose,
        "destroyed_extra_peloton_actors": destroyed_extra,
        "pelotons": configured,
        "actual_peloton_labels": actual_labels,
        "missing_peloton_labels": missing_labels,
        "remaining_loose_cyclist_actors": remaining_loose,
        "paper_context_materials": [safe_text(material.get_path_name()) for material in context_materials],
        "dirty_before_save": dirty_before_save,
        "saved": bool(saved),
        "dirty_after_save": dirty_after_save,
    }
    report_path = REPO / "pipeline" / "logs" / "canonicalize_peloton_only_latest.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_json = json.dumps(payload, indent=2, sort_keys=True)
    report_path.write_text(report_json + "\n", encoding="utf-8")
    print(report_json)
    print("Canonical peloton report: %s" % report_path)
    if remaining_loose:
        raise RuntimeError("Loose cyclist actors remain after canonicalization")
    if missing_labels:
        raise RuntimeError("Missing scripted peloton labels: %s" % ", ".join(missing_labels))


try:
    main()
except Exception:
    print(json.dumps({"ok": False, "traceback": traceback.format_exc()}, indent=2))
    raise
