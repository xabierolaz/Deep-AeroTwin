import json
import traceback
from pathlib import Path

import unreal

LEVEL_PATH = "/Game/Ejea"
AIRPLANE_LABEL = "BP_AirplaneMarker"
REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
OUT_PATH = REPO / "pipeline" / "logs" / "airplane_camera_runtime_state_latest.json"


def actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def safe_text(value):
    try:
        return str(value)
    except Exception:
        return ""


def actor_label(actor):
    try:
        return safe_text(actor.get_actor_label())
    except Exception:
        return safe_text(actor.get_name())


def rot(value):
    return {"pitch": float(value.pitch), "yaw": float(value.yaw), "roll": float(value.roll)}


def vec(value):
    return {"x": float(value.x), "y": float(value.y), "z": float(value.z)}


def get_airplane():
    for actor in actor_subsystem().get_all_level_actors():
        if actor_label(actor) == AIRPLANE_LABEL or safe_text(actor.get_name()).startswith(AIRPLANE_LABEL):
            return actor
    raise RuntimeError(f"{AIRPLANE_LABEL} not found")


def prop(component, names):
    for name in names:
        try:
            return component.get_editor_property(name)
        except Exception:
            continue
    return None


def prop_row(component, names):
    row = {}
    for name in names:
        try:
            value = component.get_editor_property(name)
        except Exception:
            continue
        if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
            row[name] = vec(value)
        elif hasattr(value, "pitch") and hasattr(value, "yaw") and hasattr(value, "roll"):
            row[name] = rot(value)
        else:
            row[name] = safe_text(value)
    return row


def component_row(component):
    row = {
        "name": safe_text(component.get_name()),
        "class": safe_text(component.get_class().get_name()),
    }
    row.update(
        prop_row(
            component,
            [
                "relative_location",
                "relative_rotation",
                "field_of_view",
                "b_constrain_aspect_ratio",
                "b_use_pawn_control_rotation",
                "b_absolute_rotation",
                "b_absolute_location",
                "auto_activate",
                "component_tick",
                "tick_interval",
                "primary_component_tick",
                "poll_rate_hz",
                "PollRateHz",
                "endpoint_url",
                "EndpointUrl",
            ],
        )
    )
    return row


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(LEVEL_PATH)
    airplane = get_airplane()
    components = []
    try:
        raw_components = airplane.get_components_by_class(unreal.ActorComponent)
    except Exception:
        raw_components = []
    for component in raw_components:
        components.append(component_row(component))

    camera = airplane.get_component_by_class(unreal.CameraComponent)
    payload = {
        "ok": True,
        "level": LEVEL_PATH,
        "airplane": {
            "label": actor_label(airplane),
            "name": safe_text(airplane.get_name()),
            "class": safe_text(airplane.get_class().get_name()),
            "location": vec(airplane.get_actor_location()),
            "rotation": rot(airplane.get_actor_rotation()),
        },
        "camera_component": None if camera is None else component_row(camera),
        "components": components,
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
