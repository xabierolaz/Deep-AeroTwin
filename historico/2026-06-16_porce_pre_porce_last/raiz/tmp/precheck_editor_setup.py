"""In-editor setup for the YOLO pre-check (runs inside Unreal's Python)."""
import json
import unreal

OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\precheck_editor_setup.json"
ACTOR_LABEL = "Peloton_Ciclistas_EditableSpline"

info = {"ok": False}
try:
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors()
    actor = next((a for a in actors if a.get_actor_label() == ACTOR_LABEL), None)
    if actor is None:
        raise RuntimeError("peloton actor not found")

    loc = actor.get_actor_location()
    info["peloton_location"] = {"x": loc.x, "y": loc.y, "z": loc.z}
    info["class"] = actor.get_class().get_name()

    def get_prop(target, names):
        for name in names:
            try:
                return target.get_editor_property(name)
            except Exception:
                pass
        return None

    info["rider_count"] = get_prop(actor, ["rider_count", "RiderCount"])
    info["speed_cm_s"] = get_prop(actor, ["speed_cm_per_second", "SpeedCmPerSecond"])
    info["start_distance"] = get_prop(actor, ["start_distance", "StartDistance"])

    # Disable ghost visualization for evidence capture (audit risk #2).
    ghosts_changed = []
    for prop in ["show_forward_leader_ghosts", "bShowForwardLeaderGhosts",
                 "show_backward_leader_ghosts", "bShowBackwardLeaderGhosts",
                 "show_ghosts", "bShowGhosts"]:
        try:
            actor.set_editor_property(prop, False)
            ghosts_changed.append(prop)
        except Exception:
            pass
    info["ghost_props_disabled"] = ghosts_changed

    # Hide any ghost mesh components outright.
    hidden = 0
    for comp in actor.get_components_by_class(unreal.StaticMeshComponent):
        name = comp.get_name()
        if "Ghost" in name:
            comp.set_visibility(False, True)
            comp.set_hidden_in_game(True)
            hidden += 1
    info["ghost_components_hidden"] = hidden

    # Spline first point world position (to know where riders pass).
    spline = get_prop(actor, ["route_spline", "RouteSpline"])
    if spline:
        pts = []
        n = spline.get_number_of_spline_points()
        for i in range(min(n, 12)):
            p = spline.get_location_at_spline_point(i, unreal.SplineCoordinateSpace.WORLD)
            pts.append({"x": p.x, "y": p.y, "z": p.z})
        info["spline_points_world"] = pts
        info["spline_length"] = spline.get_spline_length()

    # PIE settings: new window at 640x640.
    try:
        play_settings = unreal.LevelEditorPlaySettings.get_default_object()
    except Exception:
        play_settings = unreal.get_default_object(unreal.LevelEditorPlaySettings)
    changed = {}
    try:
        play_settings.set_editor_property("new_window_width", 640)
        play_settings.set_editor_property("new_window_height", 640)
        changed["new_window_size"] = "640x640"
    except Exception as exc:
        changed["new_window_size_error"] = str(exc)
    try:
        play_settings.set_editor_property(
            "last_executed_play_mode_type", unreal.PlayModeType.PLAY_IN_EDITOR_FLOATING
        )
        changed["mode"] = "PLAY_IN_EDITOR_FLOATING"
    except Exception as exc:
        changed["mode_error"] = str(exc)
    info["pie_settings"] = changed

    info["ok"] = True
except Exception as exc:  # noqa: BLE001
    info["error"] = str(exc)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(info, fh, indent=2)
print("PRECHECK_SETUP_DONE " + json.dumps(info)[:500])
