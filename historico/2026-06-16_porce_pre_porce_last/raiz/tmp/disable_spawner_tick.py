"""Disable the spawner BP actor tick in the audit map (kills VaRest debug labels)."""
import json
import unreal

OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\disable_spawner_tick.json"
info = {"ok": False, "world": None, "actors": []}
try:
    les = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = les.get_editor_world()
    info["world"] = world.get_name() if world else None
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in actor_subsystem.get_all_level_actors():
        label = actor.get_actor_label().lower()
        if "spawner" in label:
            actor.set_actor_tick_enabled(False)
            try:
                actor.set_editor_property("start_with_tick_enabled", False)
            except Exception:
                pass
            # also components' auto-activate ticks
            for comp in actor.get_components_by_class(unreal.ActorComponent):
                try:
                    comp.set_component_tick_enabled(False)
                except Exception:
                    pass
            info["actors"].append(actor.get_actor_label())
    info["ok"] = True
except Exception as exc:  # noqa: BLE001
    info["error"] = str(exc)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(info, fh, indent=2)
print("SPAWNER_TICK " + json.dumps(info))
