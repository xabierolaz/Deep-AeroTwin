import json
import math
import os
import time
import traceback
from pathlib import Path

import unreal


REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
WAYPOINTS_FILE = REPO / "pipeline" / "ejea_default.waypoints"
OUT_DIR = REPO / "figuras_paper_unreal_generadas" / "unreal_real_flight"
WIDTH = 1280
HEIGHT = 720
FRAME_PREFIX = "real_unreal_camera"
TEMP_CAMERA_LABEL = "DAT_PaperRealFlightCamera"
CAPTURE_SETTLE_PASSES = 6
CAPTURE_SETTLE_SLEEP_S = 0.35
QUIT_AFTER_SCRIPT = os.environ.get("PORCE_UNREAL_QUIT_AFTER_SCRIPT", "0").strip().lower() in ("1", "true", "yes")
TEXTURED_RIDER_SKELETAL_MESH_PATH = (
    "/Game/Peloton/TexturedBiker/biker_text_pedal_loop/SkeletalMeshes/"
    "biker_text_pedal_loop.biker_text_pedal_loop"
)
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


def actor_label(actor):
    try:
        return str(actor.get_actor_label())
    except Exception:
        return str(actor.get_name())


def vec(v):
    return {"x": float(v.x), "y": float(v.y), "z": float(v.z)}


def rot(r):
    return {"pitch": float(r.pitch), "yaw": float(r.yaw), "roll": float(r.roll)}


def get_actor_by_label(label):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in subsystem.get_all_level_actors():
        if actor_label(actor) == label:
            return actor
    return None


def find_peloton():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in subsystem.get_all_level_actors():
        text = " ".join([actor_label(actor), str(actor.get_name()), str(actor.get_class().get_name())]).lower()
        if "peloton" in text:
            return actor
    return None


def configure_cesium_for_capture():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    changed = {}
    for actor in subsystem.get_all_level_actors():
        if actor.get_class().get_name() == "CesiumCameraManager":
            for key, value in {
                "UsePlayerCameras": True,
                "UseEditorCameras": True,
                "UseSceneCapturesInLevel": True,
            }.items():
                try:
                    if actor.get_editor_property(key) != value:
                        actor.modify()
                        actor.set_editor_property(key, value)
                except Exception:
                    pass
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


def hide_irrelevant_scene_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    changed = []
    for actor in subsystem.get_all_level_actors():
        text = " ".join([actor_label(actor), str(actor.get_name()), str(actor.get_class().get_name())]).lower()
        hide = False
        if "tower" in text or "cow" in text or "vaca" in text:
            hide = True
        if "dat_papercapture_" in text:
            hide = True
        if hide:
            try:
                actor.set_is_temporarily_hidden_in_editor(True)
                actor.set_actor_hidden_in_game(True)
                changed.append(actor_label(actor))
            except Exception:
                pass
    return changed


def cleanup_temp_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in list(subsystem.get_all_level_actors()):
        label_text = actor_label(actor)
        name_text = str(actor.get_name())
        if label_text.startswith("DAT_") or name_text.startswith("DAT_") or label_text == TEMP_CAMERA_LABEL:
            try:
                subsystem.destroy_actor(actor)
            except Exception:
                pass


def load_required_rider_mesh():
    mesh = unreal.EditorAssetLibrary.load_asset(TEXTURED_RIDER_SKELETAL_MESH_PATH)
    if not mesh:
        raise RuntimeError("Missing required textured rider skeletal mesh: %s" % TEXTURED_RIDER_SKELETAL_MESH_PATH)
    return mesh


def stage_peloton(actor):
    if not actor:
        return {}
    settings = {
        "RiderCount": 8,
        "MaxRidersPerRow": 3,
        "LongitudinalSpacing": 190.0,
        "LateralSpacing": 105.0,
        "AlternateRowLateralStagger": 35.0,
        "SpeedCmPerSecond": 640.0,
        "EditorPreviewDistance": 1850.0,
        "bAnimateInEditor": False,
        "bAnimateInGame": True,
        "RiderSkeletalMesh": load_required_rider_mesh(),
        "RiderMaterial": None,
        "bAnimatePedalMorph": True,
        "PedalMorphTargetName": "key_loop",
    }
    applied = {}
    for key, value in settings.items():
        try:
            actor.set_editor_property(key, value)
            applied[key] = True
        except Exception:
            applied[key] = False
    try:
        actor.set_preview_distance(settings["EditorPreviewDistance"])
    except Exception:
        pass
    try:
        actor.rebuild_peloton()
    except Exception:
        pass
    return applied


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
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in subsystem.get_all_level_actors():
        if "CesiumGeoreference" in actor_label(actor) or str(actor.get_class().get_name()) == "CesiumGeoreference":
            return actor
    raise RuntimeError("CesiumGeoreference actor not found")


def llh_to_world(geo, lon, lat, height):
    return geo.transform_longitude_latitude_height_position_to_unreal(unreal.Vector(float(lon), float(lat), float(height)))


def world_to_llh(geo, world):
    llh = geo.transform_unreal_position_to_longitude_latitude_height(world)
    return {"lon": float(llh.x), "lat": float(llh.y), "height": float(llh.z)}


def normalize(v):
    size = math.sqrt(float(v.x) ** 2 + float(v.y) ** 2 + float(v.z) ** 2)
    if size <= 1e-6:
        return unreal.Vector(1.0, 0.0, 0.0)
    return unreal.Vector(v.x / size, v.y / size, v.z / size)


def look_at_rotation(camera_location, target_location):
    direction = target_location - camera_location
    yaw = math.degrees(math.atan2(direction.y, direction.x))
    horizontal = math.sqrt(direction.x * direction.x + direction.y * direction.y)
    pitch = math.degrees(math.atan2(direction.z, horizontal))
    return unreal.Rotator(pitch=pitch, yaw=yaw, roll=0.0)


def set_actor_llh(actor, lon, lat, height):
    anchor = actor.get_component_by_class(unreal.CesiumGlobeAnchorComponent)
    if anchor:
        anchor.move_to_longitude_latitude_height(unreal.Vector(float(lon), float(lat), float(height)))
    else:
        actor.set_actor_location(llh_to_world(georeference(), lon, lat, height), False, False)


def configure_capture(world):
    cleanup_temp_actors()
    capture_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SceneCapture2D,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(pitch=0.0, yaw=0.0, roll=0.0),
    )
    capture_actor.set_actor_label(TEMP_CAMERA_LABEL)
    capture = capture_actor.capture_component2d
    if not capture:
        raise RuntimeError("Failed to create SceneCaptureComponent2D")
    render_target = unreal.RenderingLibrary.create_render_target2d(
        world,
        WIDTH,
        HEIGHT,
        unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB,
        unreal.LinearColor(0, 0, 0, 1),
    )
    capture.texture_target = render_target
    capture.fov_angle = 54.0
    capture.capture_every_frame = False
    capture.capture_on_movement = False
    try:
        capture.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
    except Exception:
        pass
    return capture_actor, capture, render_target


def export_frame(world, capture, render_target, name):
    unreal.RenderingLibrary.clear_render_target2d(world, render_target, unreal.LinearColor(0, 0, 0, 1))
    for _ in range(CAPTURE_SETTLE_PASSES):
        capture.capture_scene()
        time.sleep(CAPTURE_SETTLE_SLEEP_S)
    capture.capture_scene()
    unreal.RenderingLibrary.export_render_target(world, render_target, str(OUT_DIR), name)
    raw_path = OUT_DIR / name
    png_path = OUT_DIR / (name + ".png")
    if raw_path.exists() and not png_path.exists():
        raw_path.replace(png_path)
    return str(png_path if png_path.exists() else raw_path)

def maybe_quit_editor():
    if QUIT_AFTER_SCRIPT:
        unreal.SystemLibrary.quit_editor()


def interpolate(a, b, t):
    return {
        "lat": float(a["lat"]) + (float(b["lat"]) - float(a["lat"])) * float(t),
        "lon": float(a["lon"]) + (float(b["lon"]) - float(a["lon"])) * float(t),
        "alt_msl": float(a["alt_msl"]) + (float(b["alt_msl"]) - float(a["alt_msl"])) * float(t),
    }


def nearest_segment_to_peloton(geo, waypoints, peloton_world):
    best = None
    for i in range(len(waypoints) - 1):
        a = llh_to_world(geo, waypoints[i]["lon"], waypoints[i]["lat"], waypoints[i]["alt_msl"])
        b = llh_to_world(geo, waypoints[i + 1]["lon"], waypoints[i + 1]["lat"], waypoints[i + 1]["alt_msl"])
        ab = b - a
        ap = peloton_world - a
        denom = max(1e-6, ab.dot(ab))
        t = max(0.0, min(1.0, ap.dot(ab) / denom))
        closest = a + ab * t
        d = (closest - peloton_world).length()
        if best is None or d < best["distance_cm"]:
            best = {"idx": i, "t": float(t), "distance_cm": float(d), "closest": closest}
    return best


def build_samples(geo, waypoints, peloton):
    origin, extent = peloton.get_actor_bounds(False)
    best = nearest_segment_to_peloton(geo, waypoints, origin)
    idx = int(best["idx"])
    t0 = float(best["t"])
    # Fly through the peloton encounter: pre-trigger, detection, closest pass, recovery.
    ts = [max(0.02, t0 - 0.34), max(0.02, t0 - 0.18), t0, min(0.98, t0 + 0.16), min(0.98, t0 + 0.32)]
    samples = []
    for n, t in enumerate(ts):
        p = interpolate(waypoints[idx], waypoints[idx + 1], t)
        samples.append({"frame": n + 1, "segment_idx": idx, "segment_t": t, **p})
    return samples, best


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cesium_changes = configure_cesium_for_capture()
    hidden = hide_irrelevant_scene_actors()
    world = unreal.EditorLevelLibrary.get_editor_world()
    geo = georeference()
    airplane = get_actor_by_label("BP_AirplaneMarker")
    if not airplane:
        raise RuntimeError("BP_AirplaneMarker not found")
    peloton = find_peloton()
    if not peloton:
        raise RuntimeError("Peloton actor not found")
    peloton_applied = stage_peloton(peloton)
    waypoints = load_waypoints(WAYPOINTS_FILE)
    if len(waypoints) < 2:
        raise RuntimeError("Not enough waypoints loaded")

    peloton_origin, peloton_extent = peloton.get_actor_bounds(False)
    samples, segment = build_samples(geo, waypoints, peloton)
    capture_actor, capture, render_target = configure_capture(world)
    manifest_frames = []

    for sample in samples:
        current = llh_to_world(geo, sample["lon"], sample["lat"], sample["alt_msl"])
        # Camera remains mounted on the UAV, slightly above/behind the aircraft body.
        set_actor_llh(airplane, sample["lon"], sample["lat"], sample["alt_msl"])
        airplane.set_actor_rotation(look_at_rotation(current, peloton_origin), False)

        camera_pos = current + unreal.Vector(0.0, 0.0, 40.0)
        # Aim at the peloton, keeping a downward onboard-camera view.
        camera_target = peloton_origin + unreal.Vector(0.0, 0.0, 120.0)
        capture_actor.set_actor_location(camera_pos, False, False)
        capture_actor.set_actor_rotation(look_at_rotation(camera_pos, camera_target), False)
        capture.fov_angle = 50.0 if sample["frame"] in (2, 3, 4) else 56.0
        name = f"{FRAME_PREFIX}_{sample['frame']:02d}"
        path = export_frame(world, capture, render_target, name)
        manifest_frames.append({
            **sample,
            "path": path,
            "aircraft_world": vec(current),
            "aircraft_llh": {"lon": float(sample["lon"]), "lat": float(sample["lat"]), "height": float(sample["alt_msl"])},
            "camera_world": vec(capture_actor.get_actor_location()),
            "camera_rotation": rot(capture_actor.get_actor_rotation()),
            "target_world": vec(camera_target),
        })

    manifest = {
        "ok": True,
        "source": "Unreal waypoint flight camera, mounted at BP_AirplaneMarker trajectory samples",
        "cesium_profile": CESIUM_PAPER_PROFILE,
        "cesium_changes": cesium_changes,
        "waypoints_file": str(WAYPOINTS_FILE),
        "waypoints_loaded": len(waypoints),
        "peloton": {
            "label": actor_label(peloton),
            "class": str(peloton.get_class().get_name()),
            "bounds_origin": vec(peloton_origin),
            "bounds_extent": vec(peloton_extent),
            "llh": world_to_llh(geo, peloton_origin),
            "applied": peloton_applied,
        },
        "nearest_route_segment": {
            "idx": int(segment["idx"]),
            "t": float(segment["t"]),
            "distance_m": float(segment["distance_cm"]) / 100.0,
        },
        "hidden_for_capture": hidden,
        "frames": manifest_frames,
    }
    (OUT_DIR / "real_flight_capture_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


try:
    main()
except Exception:
    print(json.dumps({"ok": False, "traceback": traceback.format_exc()}, indent=2))
    raise
finally:
    cleanup_temp_actors()
    maybe_quit_editor()
