"""D1 prep: ghosts off on peloton, PIE new-window 640x640."""
import json
import unreal

OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\d1_editor_prep.json"
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

    ghost_flags = []
    for prop in ["show_forward_leader_ghosts", "show_backward_leader_ghosts",
                 "bShowForwardLeaderGhosts", "bShowBackwardLeaderGhosts",
                 "ForwardGhostCount", "forward_ghost_count_setting"]:
        try:
            actor.set_editor_property(prop, False)
            ghost_flags.append(prop)
        except Exception:
            pass
    info["ghost_flags_set"] = ghost_flags

    hidden = 0
    for comp in actor.get_components_by_class(unreal.StaticMeshComponent):
        if "Ghost" in comp.get_name():
            comp.set_visibility(False, True)
            comp.set_hidden_in_game(True)
            hidden += 1
    info["ghost_components_hidden"] = hidden

    ghost_child = 0
    for comp in actor.get_components_by_class(unreal.ChildActorComponent):
        if "Ghost" in comp.get_name():
            comp.set_visibility(False, True)
            comp.set_hidden_in_game(True)
            ghost_child += 1
    info["ghost_childactors_hidden"] = ghost_child

    # PIE settings via CDO with exact UPROPERTY names
    cls = unreal.load_class(None, "/Script/UnrealEd.LevelEditorPlaySettings")
    cdo = unreal.get_default_object(cls)
    pie = {}
    for name, value in [("NewWindowWidth", 640), ("NewWindowHeight", 640)]:
        try:
            cdo.set_editor_property(name, value)
            pie[name] = "ok"
        except Exception as exc:
            pie[name] = str(exc)[:120]
    try:
        cdo.set_editor_property("LastExecutedPlayModeType", unreal.PlayModeType.PLAY_IN_EDITOR_FLOATING)
        pie["LastExecutedPlayModeType"] = "ok"
    except Exception as exc:
        pie["LastExecutedPlayModeType"] = str(exc)[:120]
    info["pie"] = pie
    info["ok"] = True
except Exception as exc:  # noqa: BLE001
    info["error"] = str(exc)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(info, fh, indent=2)
print("D1PREP " + json.dumps(info))
