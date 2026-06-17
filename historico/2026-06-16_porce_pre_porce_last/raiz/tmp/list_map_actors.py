"""List all actors and their non-trivial components in the audit map."""
import json
import unreal

OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\map_actors.json"
res = []
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for a in actor_subsystem.get_all_level_actors():
    cls = a.get_class().get_name()
    comps = [c.get_class().get_name() for c in a.get_components_by_class(unreal.ActorComponent)]
    interesting = [c for c in comps if not c.startswith(("StaticMeshComponent", "SceneComponent", "BillboardComponent"))]
    res.append({"label": a.get_actor_label(), "class": cls, "tick": a.get_editor_property("primary_actor_tick").get_editor_property("start_with_tick_enabled") if hasattr(a, "primary_actor_tick") else None, "comps": interesting[:8]})
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(res, fh, indent=1)
print(f"ACTORS {len(res)}")
