import json
import math
import os
import time
import traceback
from pathlib import Path

import unreal

REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
OUT_DIR = REPO / "figuras_paper_unreal_generadas" / "yolo_crossing_precheck" / "raw"
WIDTH = 1280
HEIGHT = 720
LEVEL_PATH = "/Game/Ejea"
WAYPOINTS_FILE = REPO / "pipeline" / "ejea_default.waypoints"
CAPTURE_SETTLE_PASSES = 10
CAPTURE_SETTLE_SLEEP_S = 0.45
TEMP_PREFIX = "DAT_CrossingPrecheck_"
QUIT_AFTER_SCRIPT = os.environ.get("PORCE_UNREAL_QUIT_AFTER_SCRIPT", "0").strip().lower() in ("1", "true", "yes")
SURFACE_MATERIAL_PATH = "/Game/Peloton/Materials/M_PaperContextGroundSage"
ROAD_MATERIAL_PATH = "/Game/Peloton/Materials/M_PaperContextRoadAsphalt"
CESIUM_PAPER_PROFILE = {
    "MaximumScreenSpaceError": 8.0,
    "PreloadAncestors": True,
    "PreloadSiblings": True,
    "ForbidHoles": True,
    "MaximumSimultaneousTileLoads": 96,
    "MaximumCachedBytes": 8 * 1024 * 1024 * 1024,
    "LoadingDescendantLimit": 0,
    "EnableFrustumCulling": False,
    "EnableFogCulling": False,
    "EnforceCulledScreenSpaceError": True,
    "CulledScreenSpaceError": 16.0,
    "EnableOcclusionCulling": False,
    "DelayRefinementForOcclusion": False,
    "UseLodTransitions": False,
    "LodTransitionLength": 1.0,
    "SuspendUpdate": False,
    "UpdateInEditor": True,
    "UnloadEditorTilesInPlayMode": False,
}
ROUTES = [
    {"label": "Peloton_Route_WP01_T70_Cross", "segment_start_seq": 1, "t": 0.70, "height": 500.0},
    {"label": "Peloton_Route_WP03_T30_Cross", "segment_start_seq": 3, "t": 0.30, "height": 500.0},
    {"label": "Peloton_Route_WP06_T70_Cross", "segment_start_seq": 6, "t": 0.70, "height": 500.0},
    {"label": "Peloton_Route_WP08_T30_Cross", "segment_start_seq": 8, "t": 0.30, "height": 500.0},
]
SAMPLE_OFFSETS_M = (-70.0, -45.0, -24.0, 0.0, 24.0, 45.0, 70.0)


def actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def actor_label(actor):
    try:
        return str(actor.get_actor_label())
    except Exception:
        return str(actor.get_name())


def actor_text(actor):
    try:
        folder = str(actor.get_folder_path())
    except Exception:
        folder = ""
    return " ".join([actor_label(actor), str(actor.get_name()), str(actor.get_class().get_name()), folder]).lower()


def vec(value):
    return {"x": float(value.x), "y": float(value.y), "z": float(value.z)}


def georeference():
    for actor in actor_subsystem().get_all_level_actors():
        if "CesiumGeoreference" in actor_label(actor) or str(actor.get_class().get_name()) == "CesiumGeoreference":
            return actor
    raise RuntimeError("CesiumGeoreference actor not found")


def llh_to_world(geo, lon, lat, height):
    return geo.transform_longitude_latitude_height_position_to_unreal(
        unreal.Vector(float(lon), float(lat), float(height))
    )


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


def find_segment_by_start_seq(waypoints, seq):
    for index in range(len(waypoints) - 1):
        if int(waypoints[index]["seq"]) == int(seq):
            return waypoints[index], waypoints[index + 1]
    raise RuntimeError("Waypoint segment starting at seq %s not found" % seq)


def interpolate(a, b, t, height):
    return {
        "lat": float(a["lat"]) + (float(b["lat"]) - float(a["lat"])) * float(t),
        "lon": float(a["lon"]) + (float(b["lon"]) - float(a["lon"])) * float(t),
        "height": float(height),
    }


def normalize_xy(value):
    size = math.sqrt(float(value.x) * float(value.x) + float(value.y) * float(value.y))
    if size <= 1e-6:
        return unreal.Vector(1.0, 0.0, 0.0)
    return unreal.Vector(float(value.x) / size, float(value.y) / size, 0.0)


def yaw_from_direction(direction):
    return math.degrees(math.atan2(float(direction.y), float(direction.x)))


def look_at_rotation(camera_location, target_location):
    direction = target_location - camera_location
    yaw = math.degrees(math.atan2(direction.y, direction.x))
    horizontal = math.sqrt(direction.x * direction.x + direction.y * direction.y)
    pitch = math.degrees(math.atan2(direction.z, horizontal))
    return unreal.Rotator(pitch=pitch, yaw=yaw, roll=0.0)


def cleanup_temp_actors():
    for actor in list(actor_subsystem().get_all_level_actors()):
        label = actor_label(actor)
        name = str(actor.get_name())
        if label.startswith(TEMP_PREFIX) or name.startswith(TEMP_PREFIX):
            try:
                actor_subsystem().destroy_actor(actor)
            except Exception:
                pass


def configure_cesium_for_capture():
    changed = {}
    for actor in actor_subsystem().get_all_level_actors():
        if actor.get_class().get_name() == "CesiumCameraManager":
            manager_changes = {}
            for key, value in {
                "UsePlayerCameras": True,
                "UseEditorCameras": True,
                "UseSceneCapturesInLevel": True,
            }.items():
                try:
                    previous = actor.get_editor_property(key)
                    if previous != value:
                        actor.modify()
                        actor.set_editor_property(key, value)
                        manager_changes[key] = {"from": previous, "to": value}
                except Exception:
                    pass
            changed[actor_label(actor)] = manager_changes
            continue
        if actor.get_class().get_name() != "Cesium3DTileset":
            continue
        actor_changes = {}
        for key, value in CESIUM_PAPER_PROFILE.items():
            try:
                previous = actor.get_editor_property(key)
                if previous != value:
                    actor.modify()
                    actor.set_editor_property(key, value)
                    actor_changes[key] = {"from": previous, "to": value}
            except Exception:
                pass
        try:
            actor.refresh_tileset()
        except Exception:
            pass
        changed[actor_label(actor)] = actor_changes
    return changed


def hide_non_peloton_obstacles():
    hidden = []
    for actor in actor_subsystem().get_all_level_actors():
        text = actor_text(actor)
        hide = "cow" in text or "vaca" in text or "tower" in text or "bp_biker" in text or "ciclista" in text
        if not hide:
            continue
        try:
            actor.set_is_temporarily_hidden_in_editor(True)
            actor.set_actor_hidden_in_game(True)
            hidden.append(actor_label(actor))
        except Exception:
            pass
    return hidden


def spawn_box_helper(name, location, yaw_degrees, scale, material_path):
    mesh = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    material = unreal.EditorAssetLibrary.load_asset(material_path)
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.StaticMeshActor,
        location,
        unreal.Rotator(0.0, float(yaw_degrees), 0.0),
    )
    actor.set_actor_label(TEMP_PREFIX + name)
    actor.set_actor_scale3d(unreal.Vector(float(scale[0]), float(scale[1]), float(scale[2])))
    comp = actor.get_component_by_class(unreal.StaticMeshComponent)
    if comp:
        comp.set_static_mesh(mesh)
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        comp.set_editor_property("cast_shadow", False)
        comp.set_editor_property("receives_decals", False)
        if material:
            comp.set_material(0, material)
    return actor


def spawn_crossing_context(route_label, ground, along):
    right = unreal.Vector(-float(along.y), float(along.x), 0.0)
    road_yaw = yaw_from_direction(right)
    safe_label = route_label.replace("Peloton_Route_", "").replace("_Cross", "")
    surface_center = ground + unreal.Vector(0.0, 0.0, -6.0)
    road_center = ground + unreal.Vector(0.0, 0.0, -2.0)
    surface = spawn_box_helper(
        "Surface_" + safe_label,
        surface_center,
        road_yaw,
        (320.0, 240.0, 0.025),
        SURFACE_MATERIAL_PATH,
    )
    road = spawn_box_helper(
        "Road_" + safe_label,
        road_center,
        road_yaw,
        (190.0, 10.0, 0.035),
        ROAD_MATERIAL_PATH,
    )
    return [actor_label(actor) for actor in (surface, road) if actor]

def apply_capture_cvars(world):
    for command in (
        "r.DefaultFeature.AutoExposure 0",
        "r.EyeAdaptationQuality 0",
        "r.Tonemapper.Sharpen 0.4",
    ):
        try:
            unreal.SystemLibrary.execute_console_command(world, command)
        except Exception:
            pass

def configure_capture_postprocess(capture):
    try:
        capture.set_editor_property("post_process_blend_weight", 1.0)
    except Exception:
        pass
    try:
        settings = capture.get_editor_property("post_process_settings")
    except Exception:
        return

    enum_type = getattr(unreal, "AutoExposureMethod", None)
    if enum_type is not None and hasattr(enum_type, "AEM_MANUAL"):
        try:
            settings.set_editor_property("auto_exposure_method", enum_type.AEM_MANUAL)
        except Exception:
            pass

    for key, value in (
        ("auto_exposure_bias", 0.0),
        ("auto_exposure_min_brightness", 1.0),
        ("auto_exposure_max_brightness", 1.0),
        ("auto_exposure_low_percent", 80.0),
        ("auto_exposure_high_percent", 95.0),
        ("film_slope", 0.82),
        ("film_toe", 0.35),
        ("film_shoulder", 0.20),
    ):
        try:
            settings.set_editor_property(key, value)
        except Exception:
            pass

    try:
        capture.set_editor_property("post_process_settings", settings)
    except Exception:
        pass


def find_actor_by_label(label):
    for actor in actor_subsystem().get_all_level_actors():
        if actor_label(actor) == label:
            return actor
    return None


def configure_capture(world):
    capture_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SceneCapture2D,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
    )
    capture_actor.set_actor_label(TEMP_PREFIX + "Camera")
    capture = capture_actor.capture_component2d
    render_target = unreal.RenderingLibrary.create_render_target2d(world, WIDTH, HEIGHT)
    try:
        render_target.set_editor_property("render_target_format", unreal.TextureRenderTargetFormat.RTF_RGBA8)
    except Exception:
        pass
    try:
        render_target.add_to_root()
    except Exception:
        pass
    capture.texture_target = render_target
    capture.fov_angle = 50.0
    capture.capture_every_frame = False
    capture.capture_on_movement = False
    configure_capture_postprocess(capture)
    try:
        capture.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
    except Exception:
        pass
    return capture_actor, capture, render_target


def clamp_u8(value):
    try:
        return max(0, min(255, int(value)))
    except Exception:
        return 0


def write_render_target_ppm(world, render_target, path):
    samples = unreal.RenderingLibrary.read_render_target(world, render_target, True)
    if not samples:
        raise RuntimeError("read_render_target returned no samples for %s" % path)
    expected = int(WIDTH) * int(HEIGHT)
    if len(samples) != expected:
        raise RuntimeError("read_render_target returned %d samples, expected %d" % (len(samples), expected))

    payload = bytearray(expected * 3)
    out_index = 0
    for sample in samples:
        payload[out_index] = clamp_u8(sample.r)
        payload[out_index + 1] = clamp_u8(sample.g)
        payload[out_index + 2] = clamp_u8(sample.b)
        out_index += 3

    with path.open("wb") as handle:
        handle.write(("P6\n%d %d\n255\n" % (WIDTH, HEIGHT)).encode("ascii"))
        handle.write(payload)


def export_frame(world, capture, render_target, name):
    unreal.RenderingLibrary.clear_render_target2d(world, render_target, unreal.LinearColor(0, 0, 0, 1))
    for _ in range(CAPTURE_SETTLE_PASSES):
        capture.capture_scene()
        time.sleep(CAPTURE_SETTLE_SLEEP_S)
    capture.capture_scene()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = name if name.lower().endswith(".ppm") else name + ".ppm"
    path = OUT_DIR / filename
    write_render_target_ppm(world, render_target, path)
    return str(path)

def maybe_quit_editor():
    if QUIT_AFTER_SCRIPT:
        unreal.SystemLibrary.quit_editor()


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(LEVEL_PATH)
    cleanup_temp_actors()
    cesium_changes = configure_cesium_for_capture()
    hidden = hide_non_peloton_obstacles()
    world = unreal.EditorLevelLibrary.get_editor_world()
    apply_capture_cvars(world)
    geo = georeference()
    waypoints = load_waypoints(WAYPOINTS_FILE)
    capture_actor, capture, render_target = configure_capture(world)
    frames = []
    context_actors = []

    for route in ROUTES:
        peloton = find_actor_by_label(route["label"])
        if not peloton:
            raise RuntimeError("Missing peloton actor %s" % route["label"])
        start_wp, end_wp = find_segment_by_start_seq(waypoints, route["segment_start_seq"])
        center_llh = interpolate(start_wp, end_wp, route["t"], route["height"])
        ground = llh_to_world(geo, center_llh["lon"], center_llh["lat"], center_llh["height"])
        high = llh_to_world(geo, center_llh["lon"], center_llh["lat"], 523.0)
        start_ground = llh_to_world(geo, start_wp["lon"], start_wp["lat"], route["height"])
        end_ground = llh_to_world(geo, end_wp["lon"], end_wp["lat"], route["height"])
        along = normalize_xy(end_ground - start_ground)
        altitude_delta = high - ground
        target = ground + unreal.Vector(0.0, 0.0, 150.0)
        context_actors.extend(spawn_crossing_context(route["label"], ground, along))

        try:
            peloton.set_preview_distance(float(peloton.get_editor_property("EditorPreviewDistance")))
            peloton.rebuild_peloton()
        except Exception:
            pass

        for sample_index, offset_m in enumerate(SAMPLE_OFFSETS_M):
            camera = ground + along * (float(offset_m) * 100.0) + altitude_delta
            camera += unreal.Vector(0.0, 0.0, 80.0)
            capture_actor.set_actor_location(camera, False, False)
            capture_actor.set_actor_rotation(look_at_rotation(camera, target), False)
            capture.fov_angle = 48.0 if abs(float(offset_m)) <= 25.0 else 54.0
            name = "%s_%02d_offset_%+04dm" % (route["label"], sample_index, int(round(offset_m)))
            path = export_frame(world, capture, render_target, name)
            frames.append(
                {
                    "route": route["label"],
                    "offset_m": float(offset_m),
                    "path": path,
                    "camera_world": vec(camera),
                    "target_world": vec(target),
                    "center_llh": center_llh,
                }
            )

    cleanup_temp_actors()
    manifest = {
        "ok": True,
        "level": LEVEL_PATH,
        "waypoints_file": str(WAYPOINTS_FILE),
        "out_dir": str(OUT_DIR),
        "cesium_profile": CESIUM_PAPER_PROFILE,
        "cesium_changes": cesium_changes,
        "hidden_for_capture": hidden,
        "context_actors": context_actors,
        "frames": frames,
    }
    OUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    (OUT_DIR.parent / "capture_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


try:
    main()
except Exception:
    print(json.dumps({"ok": False, "traceback": traceback.format_exc()}, indent=2))
    raise
finally:
    cleanup_temp_actors()
    maybe_quit_editor()
