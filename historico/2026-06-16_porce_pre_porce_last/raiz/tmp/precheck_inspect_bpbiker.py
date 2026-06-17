"""Dump bp_biker's component meshes/materials; also list ciclista assets."""
import json
import unreal

OUT = r"D:\Deep-AeroTwin-UE57-Test\tmp\bpbiker_info.json"
info = {"ok": False}
try:
    bp = unreal.EditorAssetLibrary.load_blueprint_class("/Game/bp_biker")
    cdo = unreal.get_default_object(bp)
    comps_info = []
    # CDO components may not include SCS components; spawn a temp actor instead.
    world_actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
        bp, unreal.Vector(0, 0, -100000), unreal.Rotator()
    )
    try:
        for comp in world_actor.get_components_by_class(unreal.StaticMeshComponent):
            mesh = comp.get_editor_property("static_mesh")
            mats = []
            for i in range(comp.get_num_materials()):
                m = comp.get_material(i)
                mats.append(m.get_path_name() if m else "None")
            comps_info.append(
                {
                    "component": comp.get_name(),
                    "mesh": mesh.get_path_name() if mesh else "None",
                    "materials": mats,
                    "rel_scale": list(comp.get_editor_property("relative_scale3d").to_tuple()),
                }
            )
        for comp in world_actor.get_components_by_class(unreal.SkeletalMeshComponent):
            mesh = comp.get_editor_property("skeletal_mesh_asset") if hasattr(comp, "skeletal_mesh_asset") else None
            try:
                mesh = comp.get_editor_property("skeletal_mesh_asset")
            except Exception:
                try:
                    mesh = comp.get_editor_property("skeletal_mesh")
                except Exception:
                    mesh = None
            mats = []
            for i in range(comp.get_num_materials()):
                m = comp.get_material(i)
                mats.append(m.get_path_name() if m else "None")
            comps_info.append(
                {
                    "component": comp.get_name() + " (skeletal)",
                    "mesh": mesh.get_path_name() if mesh else "None",
                    "materials": mats,
                }
            )
    finally:
        world_actor.destroy_actor()
    info["bp_biker_components"] = comps_info

    # ciclista assets
    for asset in ["/Game/ciclista", "/Game/ciclista1", "/Game/ciclista2", "/Game/biker_mesh"]:
        try:
            a = unreal.EditorAssetLibrary.load_asset(asset)
            entry = {"class": a.get_class().get_name()}
            if isinstance(a, unreal.StaticMesh):
                entry["materials"] = [
                    (a.get_material(i).get_path_name() if a.get_material(i) else "None")
                    for i in range(a.get_num_sections(0))
                ]
            info[asset] = entry
        except Exception as exc:
            info[asset] = f"error: {exc}"
    info["ok"] = True
except Exception as exc:  # noqa: BLE001
    info["error"] = str(exc)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(info, fh, indent=2)
print("BPBIKER_DONE " + json.dumps(info)[:400])
