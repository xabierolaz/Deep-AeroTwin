"""Switch peloton to ChildActorBlueprint mode with the ciclista Blueprint."""
import json
import unreal

OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\precheck_childactor.json"
ACTOR_LABEL = "Peloton_Ciclistas_EditableSpline"

info = {"ok": False}
try:
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = next(
        (a for a in actor_subsystem.get_all_level_actors() if a.get_actor_label() == ACTOR_LABEL),
        None,
    )
    if actor is None:
        raise RuntimeError("peloton actor not found")

    ciclista = unreal.EditorAssetLibrary.load_blueprint_class("/Game/ciclista")
    if ciclista is None:
        raise RuntimeError("ciclista class not loaded")

    actor.set_editor_property("rider_class", ciclista)
    actor.set_editor_property(
        "rider_render_mode", unreal.PelotonRiderRenderMode.CHILD_ACTOR_BLUEPRINT
    )
    info["render_mode"] = str(actor.get_editor_property("rider_render_mode"))
    info["rider_class"] = str(actor.get_editor_property("rider_class"))

    # Force reconstruction
    try:
        actor.rerun_construction_scripts()
        info["reconstructed"] = True
    except Exception as exc:
        info["reconstructed"] = f"error: {exc}"

    # count child actor components after switch
    child_comps = actor.get_components_by_class(unreal.ChildActorComponent)
    info["child_actor_components"] = len(child_comps)
    sm_comps = [
        c for c in actor.get_components_by_class(unreal.StaticMeshComponent)
        if c.get_name().startswith("PelotonRiderMesh_")
    ]
    info["static_rider_components"] = len(sm_comps)
    info["ok"] = True
except Exception as exc:  # noqa: BLE001
    info["error"] = str(exc)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(info, fh, indent=2)
print("CHILDACTOR_DONE " + json.dumps(info))
