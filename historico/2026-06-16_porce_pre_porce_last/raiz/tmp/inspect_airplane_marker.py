"""Dump BP_AirplaneMarker instance editable properties (bools/floats/strings)."""
import json
import unreal

OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\airplane_marker_props.json"
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = next((a for a in actor_subsystem.get_all_level_actors()
              if a.get_actor_label() == "BP_AirplaneMarker"), None)
info = {"found": actor is not None, "props": {}}
if actor:
    # Enumerate BP-generated class properties via reflection dump
    try:
        export = unreal.SystemLibrary.get_display_name(actor)
        info["display"] = str(export)
    except Exception:
        pass
    cls = actor.get_class()
    info["class_path"] = cls.get_path_name()
    # Try common debug-related property names
    candidates = [
        "ShowDebug", "show_debug", "bShowDebug", "DrawDebug", "draw_debug",
        "ShowLabels", "show_labels", "DebugLabels", "debug_labels",
        "ShowDetections", "show_detections", "DrawDetections", "draw_detections",
        "ShowObstacleLabels", "show_obstacle_labels", "debug", "Debug",
        "bDebug", "verbose", "Verbose", "ShowHud", "show_hud", "DrawHud", "draw_hud",
    ]
    for name in candidates:
        try:
            val = actor.get_editor_property(name)
            info["props"][name] = str(val)
        except Exception:
            pass
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(info, fh, indent=2)
print("AM " + json.dumps(info))
