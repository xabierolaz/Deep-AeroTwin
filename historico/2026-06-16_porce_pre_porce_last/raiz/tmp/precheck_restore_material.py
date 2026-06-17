"""Restore default biker_mesh materials on peloton riders (drop red override)."""
import json
import unreal

OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\precheck_restore_material.json"
ACTOR_LABEL = "Peloton_Ciclistas_EditableSpline"

info = {"ok": False, "components": 0, "slots": 0}
try:
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = next(
        (a for a in actor_subsystem.get_all_level_actors() if a.get_actor_label() == ACTOR_LABEL),
        None,
    )
    if actor is None:
        raise RuntimeError("peloton actor not found")

    try:
        actor.set_editor_property("rider_material", None)
        info["rider_material_cleared"] = True
    except Exception as exc:
        info["rider_material_cleared"] = f"error: {exc}"

    for comp in actor.get_components_by_class(unreal.StaticMeshComponent):
        if not comp.get_name().startswith("PelotonRiderMesh_"):
            continue
        mesh = comp.get_editor_property("static_mesh")
        if mesh is None:
            continue
        info["components"] += 1
        for i in range(comp.get_num_materials()):
            default_mat = mesh.get_material(i)
            comp.set_material(i, default_mat)
            info["slots"] += 1

    # also report default material names
    if info["components"]:
        names = []
        comp = next(
            c for c in actor.get_components_by_class(unreal.StaticMeshComponent)
            if c.get_name().startswith("PelotonRiderMesh_")
        )
        for i in range(comp.get_num_materials()):
            m = comp.get_material(i)
            names.append(m.get_name() if m else "None")
        info["material_names"] = names
    info["ok"] = True
except Exception as exc:  # noqa: BLE001
    info["error"] = str(exc)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(info, fh, indent=2)
print("RESTORE_DONE " + json.dumps(info))
