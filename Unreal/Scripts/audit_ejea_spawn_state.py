import json
import math
import traceback
from pathlib import Path

import unreal

LEVEL_PATH = "/Game/Ejea"
REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
WAYPOINTS_FILE = REPO / "pipeline" / "ejea_default.waypoints"
OUT_PATH = REPO / "pipeline" / "logs" / "ejea_spawn_state_latest.json"
MAX_KEY_ACTOR_DISTANCE_M = 250.0


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


def actor_folder(actor):
    try:
        return safe_text(actor.get_folder_path())
    except Exception:
        return ""


def vec(value):
    return {"x": float(value.x), "y": float(value.y), "z": float(value.z)}


def rot(value):
    return {"pitch": float(value.pitch), "yaw": float(value.yaw), "roll": float(value.roll)}


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


def distance_m(a_lat, a_lon, b_lat, b_lon):
    earth = 6371000.0
    d_lat = math.radians(float(b_lat) - float(a_lat))
    d_lon = math.radians(float(b_lon) - float(a_lon))
    lat1 = math.radians(float(a_lat))
    lat2 = math.radians(float(b_lat))
    h = math.sin(d_lat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2.0) ** 2
    return earth * 2.0 * math.atan2(math.sqrt(h), math.sqrt(max(0.0, 1.0 - h)))


def globe_anchor_llh(actor):
    try:
        components = actor.get_components_by_class(unreal.ActorComponent)
    except Exception:
        components = []
    for component in components:
        try:
            if component.get_class().get_name() != "CesiumGlobeAnchorComponent":
                continue
            llh = component.get_longitude_latitude_height()
            return {"lon": float(llh.x), "lat": float(llh.y), "height": float(llh.z)}
        except Exception:
            continue
    return None


def georeference_row(actor, home):
    row = {}
    for prop in ("origin_latitude", "origin_longitude", "origin_height"):
        try:
            row[prop] = float(actor.get_editor_property(prop))
        except Exception:
            row[prop] = None
    lat = row.get("origin_latitude")
    lon = row.get("origin_longitude")
    row["distance_to_ejea_home_m"] = (
        None if lat is None or lon is None else distance_m(home["lat"], home["lon"], lat, lon)
    )
    return row


def interesting_actor(actor):
    text = " ".join([actor_label(actor), safe_text(actor.get_name()), actor_class(actor), actor_folder(actor)]).lower()
    if globe_anchor_llh(actor) is not None:
        return True
    return any(
        token in text
        for token in (
            "airplane",
            "playerstart",
            "player",
            "camera",
            "pawn",
            "drone",
            "cesiumgeoreference",
            "georeference",
            "sunsky",
        )
    )


def actor_row(actor, home):
    llh = globe_anchor_llh(actor)
    row = {
        "label": actor_label(actor),
        "name": safe_text(actor.get_name()),
        "class": actor_class(actor),
        "folder": actor_folder(actor),
        "world_location": vec(actor.get_actor_location()),
        "world_rotation": rot(actor.get_actor_rotation()),
        "globe_anchor_llh": llh,
        "distance_to_ejea_home_m": None,
    }
    if llh is not None:
        row["distance_to_ejea_home_m"] = distance_m(home["lat"], home["lon"], llh["lat"], llh["lon"])
    if "cesiumgeoreference" in row["class"].lower() or "cesiumgeoreference" in row["label"].lower():
        row["georeference"] = georeference_row(actor, home)
    return row


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(LEVEL_PATH)
    home = load_home_waypoint()
    actors = list(actor_subsystem().get_all_level_actors())
    rows = [actor_row(actor, home) for actor in actors if interesting_actor(actor)]
    key_rows = [
        row
        for row in rows
        if row["label"] in ("BP_AirplaneMarker", "PlayerStart")
        or "cesiumgeoreference" in row["class"].lower()
        or "cesiumgeoreference" in row["label"].lower()
    ]
    failures = []
    for row in key_rows:
        dist = row.get("distance_to_ejea_home_m")
        geo_dist = (row.get("georeference") or {}).get("distance_to_ejea_home_m")
        effective_dist = geo_dist if geo_dist is not None else dist
        if effective_dist is not None and float(effective_dist) > MAX_KEY_ACTOR_DISTANCE_M:
            failures.append(
                {
                    "label": row["label"],
                    "class": row["class"],
                    "distance_to_ejea_home_m": float(effective_dist),
                }
            )
    payload = {
        "ok": len(failures) == 0,
        "level": LEVEL_PATH,
        "home": home,
        "max_key_actor_distance_m": MAX_KEY_ACTOR_DISTANCE_M,
        "failures": failures,
        "key_actors": key_rows,
        "actors": rows,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if failures:
        raise RuntimeError("Ejea spawn audit failed")


try:
    main()
except Exception:
    trace_payload = {"ok": False, "traceback": traceback.format_exc()}
    print(json.dumps(trace_payload, indent=2, sort_keys=True))
    raise
