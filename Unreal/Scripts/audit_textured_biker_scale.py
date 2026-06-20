import json
from pathlib import Path

import unreal


LEVEL_PATH = "/Game/Ejea"
MESH_PATH = (
    "/Game/Peloton/TexturedBiker/biker_text_pedal_loop/SkeletalMeshes/"
    "biker_text_pedal_loop.biker_text_pedal_loop"
)
REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
OUT = REPO / "pipeline" / "logs" / "textured_biker_scale_audit_latest.json"


def safe_text(value):
    return "" if value is None else str(value)


def vec(value):
    return {"x": float(value.x), "y": float(value.y), "z": float(value.z)}


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


def path_of_asset(asset):
    if asset is None:
        return None
    try:
        return safe_text(asset.get_path_name())
    except Exception:
        return safe_text(asset)


def box_sphere_bounds(value):
    if value is None:
        return None
    payload = {}
    for name in ("origin", "box_extent", "sphere_radius"):
        try:
            raw = getattr(value, name)
            payload[name] = vec(raw) if hasattr(raw, "x") else float(raw)
        except Exception:
            pass
    return payload or safe_text(value)


def call_bounds(obj):
    rows = {}
    for method_name in ("get_bounds", "get_imported_bounds", "get_bounds_extension"):
        method = getattr(obj, method_name, None)
        if not callable(method):
            continue
        try:
            rows[method_name] = box_sphere_bounds(method())
        except Exception as exc:
            rows[method_name] = {"error": safe_text(exc)}
    for prop_name in ("bounds", "imported_bounds", "positive_bounds_extension", "negative_bounds_extension"):
        try:
            rows[prop_name] = box_sphere_bounds(obj.get_editor_property(prop_name))
        except Exception:
            pass
    return rows


def component_bounds(component):
    payload = {
        "name": safe_text(component.get_name()),
        "class": safe_text(component.get_class().get_name()),
        "world_scale": None,
        "relative_scale": None,
        "mesh": None,
        "bounds": call_bounds(component),
    }
    for method_name, key in (
        ("get_component_scale", "world_scale"),
        ("get_relative_scale3d", "relative_scale"),
    ):
        method = getattr(component, method_name, None)
        if callable(method):
            try:
                payload[key] = vec(method())
            except Exception:
                pass
    for prop_name in ("skeletal_mesh_asset", "skeletal_mesh"):
        try:
            asset = component.get_editor_property(prop_name)
            if asset:
                payload["mesh"] = path_of_asset(asset)
                break
        except Exception:
            pass
    return payload


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(LEVEL_PATH)
    mesh = unreal.EditorAssetLibrary.load_asset(MESH_PATH) or unreal.load_object(None, MESH_PATH)
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    peloton_rows = []
    for actor in actors:
        text = " ".join([actor_label(actor), safe_text(actor.get_name()), actor_class(actor), actor_folder(actor)]).lower()
        if "peloton" not in text:
            continue
        try:
            origin, extent = actor.get_actor_bounds(False)
            actor_bounds = {"origin": vec(origin), "extent": vec(extent)}
        except Exception as exc:
            actor_bounds = {"error": safe_text(exc)}
        comps = []
        try:
            components = actor.get_components_by_class(unreal.SkeletalMeshComponent)
        except Exception:
            components = []
        for comp in components[:10]:
            comps.append(component_bounds(comp))
        peloton_rows.append(
            {
                "label": actor_label(actor),
                "class": actor_class(actor),
                "folder": actor_folder(actor),
                "actor_bounds": actor_bounds,
                "skeletal_component_count": len(components),
                "component_sample": comps[:3],
            }
        )

    payload = {
        "mesh_path": MESH_PATH,
        "mesh_loaded": bool(mesh),
        "mesh_bounds": call_bounds(mesh) if mesh else None,
        "peloton_count": len(peloton_rows),
        "pelotons": peloton_rows[:18],
        "notes": "Unreal units are centimeters; a human+bike should have extents on the order of tens to low hundreds of cm.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True)
    OUT.write_text(text + "\n", encoding="utf-8")
    print(text)


main()
