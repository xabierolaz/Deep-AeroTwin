import json
import math
from pathlib import Path

import unreal


LEVEL_PATH = "/Game/Ejea"
REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
WAYPOINTS_FILE = REPO / "pipeline" / "ejea_default.waypoints"
OUT = REPO / "pipeline" / "logs" / "cesium_ejea_route_precache_latest.json"

SAMPLES_PER_SEGMENT = 3
CAMERA_VIEWPORT_SIZE = unreal.Vector2D(960.0, 960.0)
CAMERA_FOV_DEG = 82.0
CAMERA_PITCH_DEG = -58.0
CAMERA_ALT_MSL = 523.0


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


def actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def set_prop(obj, name, value):
    last_error = None
    candidates = (name, name[0].lower() + name[1:])
    snake = []
    for char in name:
        if char.isupper() and snake:
            snake.append("_")
        snake.append(char.lower())
    candidates = candidates + ("".join(snake),)
    for candidate in candidates:
        try:
            obj.set_editor_property(candidate, value)
            return candidate
        except Exception as exc:
            last_error = exc
    raise RuntimeError("Could not set %s on %s: %s" % (name, obj, last_error))


def get_prop(obj, name):
    candidates = (name, name[0].lower() + name[1:])
    snake = []
    for char in name:
        if char.isupper() and snake:
            snake.append("_")
        snake.append(char.lower())
    candidates = candidates + ("".join(snake),)
    for candidate in candidates:
        try:
            value = obj.get_editor_property(candidate)
            if hasattr(value, "value"):
                value = value.value
            return value
        except Exception:
            pass
    return None


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
        lat = float(parts[8])
        lon = float(parts[9])
        if abs(lat) < 0.0001 or abs(lon) < 0.0001:
            continue
        points.append(
            {
                "seq": int(float(parts[0])),
                "cmd": cmd,
                "lat": lat,
                "lon": lon,
                "alt_msl": float(parts[10]),
            }
        )
    return points


def georeference():
    for actor in actor_subsystem().get_all_level_actors():
        text = " ".join([actor_label(actor), actor_class(actor)]).lower()
        if "cesiumgeoreference" in text:
            return actor
    raise RuntimeError("CesiumGeoreference actor not found")


def llh_to_world(geo, lon, lat, height):
    return geo.transform_longitude_latitude_height_position_to_unreal(
        unreal.Vector(float(lon), float(lat), float(height))
    )


def find_or_create_camera_manager():
    for actor in actor_subsystem().get_all_level_actors():
        if actor_class(actor) == "CesiumCameraManager":
            return actor, False
    manager_class = getattr(unreal, "CesiumCameraManager", None)
    if manager_class is None:
        raise RuntimeError("CesiumCameraManager class is not available")
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        manager_class,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
    )
    try:
        actor.set_actor_label("CesiumCameraManager_RoutePrecache")
    except Exception:
        pass
    return actor, True


def yaw_from_world_delta(delta):
    return math.degrees(math.atan2(float(delta.y), float(delta.x)))


def build_camera(location, yaw):
    camera = unreal.CesiumCamera()
    set_prop(camera, "ViewportSize", CAMERA_VIEWPORT_SIZE)
    set_prop(camera, "Location", location)
    set_prop(camera, "Rotation", unreal.Rotator(pitch=CAMERA_PITCH_DEG, yaw=yaw, roll=0.0))
    set_prop(camera, "FieldOfViewDegrees", CAMERA_FOV_DEG)
    set_prop(camera, "OverrideAspectRatio", 1.0)
    return camera


def build_route_cameras(geo, waypoints):
    cameras = []
    samples = []
    last_yaw = 0.0
    for index in range(len(waypoints) - 1):
        start = waypoints[index]
        end = waypoints[index + 1]
        if abs(float(start["lat"]) - float(end["lat"])) < 1e-9 and abs(float(start["lon"]) - float(end["lon"])) < 1e-9:
            continue
        start_world = llh_to_world(geo, start["lon"], start["lat"], CAMERA_ALT_MSL)
        end_world = llh_to_world(geo, end["lon"], end["lat"], CAMERA_ALT_MSL)
        yaw = yaw_from_world_delta(end_world - start_world)
        last_yaw = yaw
        for step in range(SAMPLES_PER_SEGMENT):
            t = float(step) / float(SAMPLES_PER_SEGMENT)
            lat = float(start["lat"]) + (float(end["lat"]) - float(start["lat"])) * t
            lon = float(start["lon"]) + (float(end["lon"]) - float(start["lon"])) * t
            location = llh_to_world(geo, lon, lat, CAMERA_ALT_MSL)
            cameras.append(build_camera(location, yaw))
            samples.append(
                {
                    "segment_start_seq": int(start["seq"]),
                    "t": t,
                    "lat": lat,
                    "lon": lon,
                    "alt_msl": CAMERA_ALT_MSL,
                    "yaw": yaw,
                }
            )
    if waypoints:
        last = waypoints[-1]
        last_world = llh_to_world(geo, last["lon"], last["lat"], CAMERA_ALT_MSL)
        yaw = last_yaw
        cameras.append(build_camera(last_world, yaw))
        samples.append(
            {
                "segment_start_seq": int(last["seq"]),
                "t": 1.0,
                "lat": float(last["lat"]),
                "lon": float(last["lon"]),
                "alt_msl": CAMERA_ALT_MSL,
                "yaw": yaw,
            }
        )
    return cameras, samples


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
    geo = georeference()
    waypoints = load_waypoints(WAYPOINTS_FILE)
    if len(waypoints) < 2:
        raise RuntimeError("Not enough waypoints loaded from %s" % WAYPOINTS_FILE)
    manager, created = find_or_create_camera_manager()
    manager.modify()
    set_prop(manager, "UsePlayerCameras", True)
    set_prop(manager, "UseEditorCameras", True)
    set_prop(manager, "UseSceneCapturesInLevel", True)
    cameras, samples = build_route_cameras(geo, waypoints)
    used_property = set_prop(manager, "AdditionalCameras", cameras)

    dirty_before_save = dirty_package_names()
    saved = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(
        save_map_packages=True,
        save_content_packages=True,
    )
    payload = {
        "ok": True,
        "level": LEVEL_PATH,
        "camera_manager": actor_label(manager),
        "created_camera_manager": created,
        "additional_cameras_property": used_property,
        "additional_cameras": len(cameras),
        "samples_per_segment": SAMPLES_PER_SEGMENT,
        "camera_fov_deg": CAMERA_FOV_DEG,
        "camera_pitch_deg": CAMERA_PITCH_DEG,
        "camera_alt_msl": CAMERA_ALT_MSL,
        "route_samples": samples,
        "dirty_before_save": dirty_before_save,
        "saved": bool(saved),
        "dirty_after_save": dirty_package_names(),
        "note": "Additional Cesium cameras are virtual tile-selection cameras; they do not render into the paper capture.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True)
    OUT.write_text(text + "\n", encoding="utf-8")
    print(text)


main()
