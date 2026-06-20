import json
import traceback
from pathlib import Path

import unreal

LEVEL_PATH = "/Game/Ejea"
AIRPLANE_LABEL = "BP_AirplaneMarker"
REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
OUT_PATH = REPO / "pipeline" / "logs" / "paper_runtime_camera_profile_latest.json"

CAMERA_FIELD_OF_VIEW_DEG = 70.0
CAMERA_RELATIVE_LOCATION = unreal.Vector(10.97047829544725, -140.89237708653337, -339.17019578119596)
CAMERA_RELATIVE_PITCH_DEG = -25.0
CAMERA_RELATIVE_YAW_DEG = -90.0
CAMERA_RELATIVE_ROLL_DEG = 0.0


def actor_label(actor):
    try:
        return str(actor.get_actor_label())
    except Exception:
        return str(actor.get_name())


def actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def vec(value):
    return {"x": float(value.x), "y": float(value.y), "z": float(value.z)}


def rot(value):
    return {"pitch": float(value.pitch), "yaw": float(value.yaw), "roll": float(value.roll)}


def get_airplane():
    for actor in actor_subsystem().get_all_level_actors():
        if actor_label(actor) == AIRPLANE_LABEL or str(actor.get_name()).startswith(AIRPLANE_LABEL):
            return actor
    raise RuntimeError(f"{AIRPLANE_LABEL} not found")


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
    airplane = get_airplane()
    camera = airplane.get_component_by_class(unreal.CameraComponent)
    if not camera:
        raise RuntimeError(f"{AIRPLANE_LABEL} has no CameraComponent")
    camera_name = str(camera.get_name())

    try:
        airplane.modify()
        camera.modify()
    except Exception:
        pass

    before = {
        "field_of_view": float(camera.get_editor_property("field_of_view")),
        "relative_location": vec(camera.get_editor_property("relative_location")),
        "relative_rotation": rot(camera.get_editor_property("relative_rotation")),
    }

    camera.set_editor_property("field_of_view", CAMERA_FIELD_OF_VIEW_DEG)
    camera.set_editor_property("relative_location", CAMERA_RELATIVE_LOCATION)
    camera.set_editor_property(
        "relative_rotation",
        unreal.Rotator(
            pitch=CAMERA_RELATIVE_PITCH_DEG,
            yaw=CAMERA_RELATIVE_YAW_DEG,
            roll=CAMERA_RELATIVE_ROLL_DEG,
        ),
    )
    try:
        camera.set_editor_property("b_constrain_aspect_ratio", False)
    except Exception:
        pass

    after = {
        "field_of_view": float(camera.get_editor_property("field_of_view")),
        "relative_location": vec(camera.get_editor_property("relative_location")),
        "relative_rotation": rot(camera.get_editor_property("relative_rotation")),
    }

    dirty_before_save = dirty_package_names()
    saved = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(
        save_map_packages=True,
        save_content_packages=True,
    )
    payload = {
        "ok": True,
        "level": LEVEL_PATH,
        "airplane": actor_label(airplane),
        "camera_component": camera_name,
        "before": before,
        "after": after,
        "dirty_before_save": dirty_before_save,
        "saved": bool(saved),
        "dirty_after_save": dirty_package_names(),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


try:
    main()
except Exception:
    payload = {"ok": False, "traceback": traceback.format_exc()}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    raise
