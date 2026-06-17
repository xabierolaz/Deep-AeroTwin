"""Disable PorceTelemetry obstacle-echo spawning in the audit map (editor-side)."""
import json
import unreal

OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\disable_twin_echo.json"
info = {"ok": False, "world": None, "components_disabled": []}
try:
    les = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = les.get_editor_world()
    info["world"] = world.get_name() if world else None

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in actor_subsystem.get_all_level_actors():
        comps = actor.get_components_by_class(unreal.PorceTelemetryComponent) \
            if hasattr(unreal, "PorceTelemetryComponent") else []
        for comp in comps:
            comp.set_editor_property("enabled", False)
            info["components_disabled"].append(f"{actor.get_actor_label()}.{comp.get_name()}")
    if not info["components_disabled"]:
        # fallback: search by class name string
        for actor in actor_subsystem.get_all_level_actors():
            for comp in actor.get_components_by_class(unreal.ActorComponent):
                if "PorceTelemetry" in comp.get_class().get_name():
                    comp.set_editor_property("enabled", False)
                    info["components_disabled"].append(f"{actor.get_actor_label()}.{comp.get_name()}")
    info["ok"] = True
except Exception as exc:  # noqa: BLE001
    info["error"] = str(exc)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(info, fh, indent=2)
print("TWIN_ECHO " + json.dumps(info))
