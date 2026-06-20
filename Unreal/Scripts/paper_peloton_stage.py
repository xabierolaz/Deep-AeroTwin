import json

import unreal

TEXTURED_RIDER_SKELETAL_MESH_PATH = (
    "/Game/Peloton/TexturedBiker/biker_text_pedal_loop/SkeletalMeshes/"
    "biker_text_pedal_loop.biker_text_pedal_loop"
)


def actor_label(actor):
    try:
        return str(actor.get_actor_label())
    except Exception:
        return str(actor.get_name())


def find_peloton_actor():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in subsystem.get_all_level_actors():
        text = " ".join(
            [
                actor_label(actor),
                str(actor.get_name()),
                str(actor.get_class().get_name()),
            ]
        ).lower()
        if "peloton" in text:
            return actor
    return None


def get_vec(vec):
    return {"x": float(vec.x), "y": float(vec.y), "z": float(vec.z)}


def set_prop(actor, name, value):
    try:
        actor.set_editor_property(name, value)
        return True
    except Exception:
        return False


def load_required_rider_mesh():
    mesh = unreal.EditorAssetLibrary.load_asset(TEXTURED_RIDER_SKELETAL_MESH_PATH)
    if not mesh:
        raise RuntimeError("Missing required textured rider skeletal mesh: %s" % TEXTURED_RIDER_SKELETAL_MESH_PATH)
    return mesh


def apply_stage(actor):
    # Editorial staging for screenshots: readable as a peloton without overloading
    # YOLO/control with many near-identical riders.
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
    applied = {key: set_prop(actor, key, value) for key, value in settings.items()}
    try:
        actor.set_preview_distance(settings["EditorPreviewDistance"])
    except Exception:
        pass
    try:
        actor.rebuild_peloton()
    except Exception:
        pass
    return applied


def summarize(actor, applied):
    origin, extent = actor.get_actor_bounds(False)
    components = actor.get_components_by_class(unreal.ActorComponent)
    component_rows = []
    for comp in components:
        try:
            component_rows.append(
                {
                    "name": str(comp.get_name()),
                    "class": str(comp.get_class().get_name()),
                }
            )
        except Exception:
            pass
    return {
        "label": actor_label(actor),
        "name": str(actor.get_name()),
        "class": str(actor.get_class().get_name()),
        "location": get_vec(actor.get_actor_location()),
        "bounds_origin": get_vec(origin),
        "bounds_extent": get_vec(extent),
        "applied": applied,
        "component_count": len(component_rows),
        "components": component_rows[:40],
    }


peloton = find_peloton_actor()
if not peloton:
    print(json.dumps({"ok": False, "error": "No peloton actor found"}, indent=2))
else:
    print(json.dumps({"ok": True, "peloton": summarize(peloton, apply_stage(peloton))}, indent=2))
