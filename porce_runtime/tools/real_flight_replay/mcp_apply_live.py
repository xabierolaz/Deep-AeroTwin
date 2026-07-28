import json

import requests
import unreal

out = {}
try:
    obs = requests.get("http://127.0.0.1:8080/api/ui/data", timeout=5).json().get("obstacles", [])
    out["n_obs"] = len(obs)
    pie = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    for a in unreal.GameplayStatics.get_all_actors_of_class(pie, unreal.Actor):
        try:
            if a.get_actor_label() == "ReplayTwinManager":
                c = a.get_components_by_class(unreal.PorceTelemetryComponent)[0]
                try:
                    out["apply"] = str(c.apply_obstacle_batch_json(json.dumps({"obstacles": obs})))
                except Exception as e2:
                    import traceback
                    out["apply_err"] = traceback.format_exc()
                break
        except Exception:
            pass
except Exception as e:
    import traceback
    out["error"] = traceback.format_exc()
print("JSONOUT:" + json.dumps(out))
