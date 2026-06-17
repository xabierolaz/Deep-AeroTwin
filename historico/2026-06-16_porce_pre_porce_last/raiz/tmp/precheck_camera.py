"""Position editor viewport camera at drone-like vantages of the peloton."""
import json
import math
import unreal

OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\precheck_camera.json"
ACTOR_LABEL = "Peloton_Ciclistas_EditableSpline"

info = {"ok": False}
try:
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors()
    actor = next((a for a in actors if a.get_actor_label() == ACTOR_LABEL), None)
    if actor is None:
        raise RuntimeError("peloton actor not found")

    comps = [
        c for c in actor.get_components_by_class(unreal.StaticMeshComponent)
        if c.get_name().startswith("PelotonRiderMesh_")
    ]
    if not comps:
        raise RuntimeError("no rider mesh components")
    positions = [c.get_world_location() for c in comps]
    cx = sum(p.x for p in positions) / len(positions)
    cy = sum(p.y for p in positions) / len(positions)
    cz = sum(p.z for p in positions) / len(positions)
    info["rider_count"] = len(comps)
    info["centroid"] = {"x": cx, "y": cy, "z": cz}

    # Vantage list: (horizontal dist m, height m, azimuth deg)
    vantages = []
    for dist_m, alt_m, az in [(30, 18, 40), (50, 23, 40), (80, 23, 110)]:
        d = dist_m * 100.0
        h = alt_m * 100.0
        rad = math.radians(az)
        cam_x = cx + d * math.cos(rad)
        cam_y = cy + d * math.sin(rad)
        cam_z = cz + h
        dx, dy, dz = cx - cam_x, cy - cam_y, cz - cam_z
        yaw = math.degrees(math.atan2(dy, dx))
        pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
        vantages.append(
            {
                "dist_m": dist_m,
                "alt_m": alt_m,
                "az": az,
                "loc": {"x": cam_x, "y": cam_y, "z": cam_z},
                "rot": {"pitch": pitch, "yaw": yaw, "roll": 0.0},
            }
        )
    info["vantages"] = vantages

    # Set viewport to the first vantage now; realtime on.
    les = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    v0 = vantages[0]
    les.set_level_viewport_camera_info(
        unreal.Vector(v0["loc"]["x"], v0["loc"]["y"], v0["loc"]["z"]),
        unreal.Rotator(roll=0.0, pitch=v0["rot"]["pitch"], yaw=v0["rot"]["yaw"]),
    )
    info["ok"] = True
except Exception as exc:  # noqa: BLE001
    info["error"] = str(exc)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(info, fh, indent=2)
print("CAMERA_DONE " + json.dumps(info)[:300])
