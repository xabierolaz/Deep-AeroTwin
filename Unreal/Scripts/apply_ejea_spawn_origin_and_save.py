import json
import traceback
from pathlib import Path

import unreal

LEVEL_PATH = "/Game/Ejea"
REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
WAYPOINTS_FILE = REPO / "pipeline" / "ejea_default.waypoints"
OUT_PATH = REPO / "pipeline" / "logs" / "apply_ejea_spawn_origin_latest.json"
AIRPLANE_LABEL = "BP_AirplaneMarker"


def actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def safe_text(value):
    return "" if value is None else str(value)


def actor_label(actor):
    try:
        return safe_text(actor.get_actor_label())
    except Exception:
        return safe_text(actor.get_name())


def actor_class(actor):
    try:
        return safe_text(actor.get_class().get_name())
    except Exception:
        return ""


def vec(value):
    return {"x": float(value.x), "y": float(value.y), "z": float(value.z)}


def load_home_waypoint():
    for line in WAYPOINTS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("QGC"):
            continue
        parts = line.split()
        if len(parts) >= 11:
            return {
                "seq": int(float(parts[0])),
                "lat": float(parts[8]),
                "lon": float(parts[9]),
                "alt_msl": float(parts[10]),
            }
    raise RuntimeError(f"No waypoint rows found in {WAYPOINTS_FILE}")


def find_actor_by_label(label):
    for actor in actor_subsystem().get_all_level_actors():
        if actor_label(actor) == label:
            return actor
    return None


def find_georeferences():
    rows = []
    for actor in actor_subsystem().get_all_level_actors():
        text = " ".join([actor_label(actor), safe_text(actor.get_name()), actor_class(actor)]).lower()
        if "cesiumgeoreference" in text:
            rows.append(actor)
    return rows


def get_prop(actor, name):
    try:
        value = actor.get_editor_property(name)
        if isinstance(value, float):
            return float(value)
        return value
    except Exception:
        return None


def set_prop(actor, name, value):
    try:
        actor.modify()
    except Exception:
        pass
    actor.set_editor_property(name, value)


def globe_anchor(actor):
    try:
        return actor.get_component_by_class(unreal.CesiumGlobeAnchorComponent)
    except Exception:
        return None


def anchor_llh(actor):
    anchor = globe_anchor(actor)
    if not anchor:
        return None
    try:
        return vec(anchor.get_longitude_latitude_height())
    except Exception:
        return None


def move_anchor(actor, lon, lat, height):
    anchor = globe_anchor(actor)
    if not anchor:
        return False
    try:
        actor.modify()
    except Exception:
        pass
    anchor.move_to_longitude_latitude_height(unreal.Vector(float(lon), float(lat), float(height)))
    return True


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(LEVEL_PATH)
    home = load_home_waypoint()
    georeferences = find_georeferences()
    airplane = find_actor_by_label(AIRPLANE_LABEL)

    rows = []
    for geo in georeferences:
        before = {
            "origin_latitude": get_prop(geo, "origin_latitude"),
            "origin_longitude": get_prop(geo, "origin_longitude"),
            "origin_height": get_prop(geo, "origin_height"),
        }
        set_prop(geo, "origin_latitude", float(home["lat"]))
        set_prop(geo, "origin_longitude", float(home["lon"]))
        set_prop(geo, "origin_height", float(home["alt_msl"]))
        after = {
            "origin_latitude": get_prop(geo, "origin_latitude"),
            "origin_longitude": get_prop(geo, "origin_longitude"),
            "origin_height": get_prop(geo, "origin_height"),
        }
        rows.append({"label": actor_label(geo), "class": actor_class(geo), "before": before, "after": after})

    airplane_row = None
    if airplane:
        before_llh = anchor_llh(airplane)
        moved = move_anchor(airplane, home["lon"], home["lat"], home["alt_msl"])
        airplane_row = {
            "label": actor_label(airplane),
            "class": actor_class(airplane),
            "moved_anchor": bool(moved),
            "before_llh": before_llh,
            "after_llh": anchor_llh(airplane),
            "world_location": vec(airplane.get_actor_location()),
        }

    saved = bool(unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True))
    payload = {
        "ok": bool(georeferences) and airplane_row is not None,
        "level": LEVEL_PATH,
        "home": home,
        "georeferences": rows,
        "airplane": airplane_row,
        "saved_dirty_packages": saved,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["ok"]:
        raise RuntimeError("Failed to apply Ejea spawn origin")


try:
    main()
except Exception:
    payload = {"ok": False, "traceback": traceback.format_exc()}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise
