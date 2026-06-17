"""Tune the peloton in Ejea_AuditD1: realistic speed, more riders."""
import json
import unreal

OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\scene_tune_peloton.json"
ACTOR_LABEL = "Peloton_Ciclistas_EditableSpline"
info = {"ok": False}
try:
    les = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = les.get_editor_world()
    info["world"] = world.get_name() if world else None
    if info["world"] != "Ejea_AuditD1":
        raise RuntimeError(f"wrong world loaded: {info['world']}")

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = next(
        (a for a in actor_subsystem.get_all_level_actors() if a.get_actor_label() == ACTOR_LABEL),
        None,
    )
    if actor is None:
        raise RuntimeError("peloton not found")

    # 650 cm/s = 23.4 km/h: realistic riding pace; keeps the group near the
    # corridor crossing for much longer than the previous 73 km/h.
    actor.set_editor_property("speed_cm_per_second", 650.0)
    actor.set_editor_property("rider_count", 16)
    try:
        actor.set_editor_property("start_distance", 0.0)
    except Exception:
        pass
    info["speed"] = float(actor.get_editor_property("speed_cm_per_second"))
    info["riders"] = int(actor.get_editor_property("rider_count"))
    info["render_mode"] = str(actor.get_editor_property("rider_render_mode"))
    info["rider_class"] = str(actor.get_editor_property("rider_class"))
    child = actor.get_components_by_class(unreal.ChildActorComponent)
    info["child_actors"] = len(child)
    info["ok"] = True
except Exception as exc:  # noqa: BLE001
    info["error"] = str(exc)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(info, fh, indent=2)
print("SCENE_TUNE " + json.dumps(info))
