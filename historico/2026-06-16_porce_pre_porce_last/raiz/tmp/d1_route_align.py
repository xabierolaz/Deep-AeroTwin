"""Compare mission waypoints (lat/lon) with peloton spline in UE world coords."""
import json
import unreal

OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\d1_route_align.json"
WPT = r"D:\Deep-AeroTwin-UE57-Test\pipeline\ejea_default.waypoints"
ACTOR_LABEL = "Peloton_Ciclistas_EditableSpline"

info = {"ok": False}
try:
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors()
    georef = next((a for a in actors if "CesiumGeoreference" in a.get_class().get_name()), None)
    peloton = next((a for a in actors if a.get_actor_label() == ACTOR_LABEL), None)
    if georef is None or peloton is None:
        raise RuntimeError(f"georef={georef} peloton={peloton}")

    wps = []
    for line in open(WPT, encoding="utf-8"):
        if line.startswith("QGC") or not line.strip():
            continue
        p = line.split()
        if len(p) >= 11:
            wps.append({"seq": int(p[0]), "lat": float(p[8]), "lon": float(p[9]), "alt": float(p[10])})

    # locate transform function
    fn_names = [
        "transform_longitude_latitude_height_position_to_unreal",
        "transform_longitude_latitude_height_to_unreal",
    ]
    fn = None
    for name in fn_names:
        if hasattr(georef, name):
            fn = getattr(georef, name)
            info["transform_fn"] = name
            break
    if fn is None:
        info["georef_methods"] = [m for m in dir(georef) if "transform" in m.lower()]
        raise RuntimeError("no transform fn found")

    wp_ue = []
    for wp in wps:
        v = fn(unreal.Vector(wp["lon"], wp["lat"], 360.0))  # ~ground height guess (m)
        wp_ue.append({"seq": wp["seq"], "x": v.x, "y": v.y, "z": v.z, "lat": wp["lat"], "lon": wp["lon"]})
    info["waypoints_ue"] = wp_ue

    spline = peloton.get_editor_property("route_spline")
    pts = []
    for i in range(spline.get_number_of_spline_points()):
        p = spline.get_location_at_spline_point(i, unreal.SplineCoordinateSpace.WORLD)
        pts.append({"x": p.x, "y": p.y, "z": p.z})
    info["spline_points"] = pts

    # min distance from spline centroid to each waypoint (2D)
    import math
    cx = sum(p["x"] for p in pts) / len(pts)
    cy = sum(p["y"] for p in pts) / len(pts)
    dists = [
        {"seq": w["seq"], "dist_m": round(math.hypot(w["x"] - cx, w["y"] - cy) / 100.0, 1)}
        for w in wp_ue
    ]
    info["spline_centroid_to_wp_m"] = dists
    info["ok"] = True
except Exception as exc:  # noqa: BLE001
    info["error"] = str(exc)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(info, fh, indent=2)
print("ALIGN " + json.dumps(info)[:600])
