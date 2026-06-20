import json
from pathlib import Path

import unreal

REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
ROOT = "/Game/Peloton/TexturedBiker"
OUT = REPO / "pipeline" / "logs" / "audit_textured_biker_morph_asset_latest.json"


def safe_text(value):
    return "" if value is None else str(value)


def object_path(asset):
    try:
        return safe_text(asset.get_path_name())
    except Exception:
        return safe_text(asset)


def class_name(asset):
    try:
        return safe_text(asset.get_class().get_name())
    except Exception:
        return type(asset).__name__


def get_morph_target_names(asset):
    for method_name in ("get_all_morph_target_names", "get_morph_target_names"):
        method = getattr(asset, method_name, None)
        if callable(method):
            try:
                return [safe_text(name) for name in method()]
            except Exception:
                pass
    names = []
    try:
        morph_targets = asset.get_editor_property("morph_targets")
        for morph_target in morph_targets:
            try:
                names.append(safe_text(morph_target.get_name()))
            except Exception:
                names.append(safe_text(morph_target))
    except Exception:
        pass
    return names


def summarize(asset):
    row = {"path": object_path(asset), "class": class_name(asset)}
    if row["class"] == "SkeletalMesh":
        row["morph_targets"] = get_morph_target_names(asset)
        try:
            row["materials"] = [object_path(mat.material_interface) for mat in asset.get_editor_property("materials")]
        except Exception:
            pass
        for prop_name in ("extended_bounds", "imported_bounds", "bounds"):
            try:
                bounds = asset.get_editor_property(prop_name)
                row[prop_name] = {
                    "origin": {
                        "x": float(bounds.origin.x),
                        "y": float(bounds.origin.y),
                        "z": float(bounds.origin.z),
                    },
                    "box_extent": {
                        "x": float(bounds.box_extent.x),
                        "y": float(bounds.box_extent.y),
                        "z": float(bounds.box_extent.z),
                    },
                    "sphere_radius": float(bounds.sphere_radius),
                }
            except Exception:
                pass
        get_bounds = getattr(asset, "get_bounds", None)
        if callable(get_bounds):
            try:
                bounds = get_bounds()
                row["get_bounds"] = {
                    "origin": {
                        "x": float(bounds.origin.x),
                        "y": float(bounds.origin.y),
                        "z": float(bounds.origin.z),
                    },
                    "box_extent": {
                        "x": float(bounds.box_extent.x),
                        "y": float(bounds.box_extent.y),
                        "z": float(bounds.box_extent.z),
                    },
                    "sphere_radius": float(bounds.sphere_radius),
                }
            except Exception:
                pass
    if row["class"] == "AnimSequence":
        try:
            row["sequence_length"] = float(asset.get_editor_property("sequence_length"))
        except Exception:
            pass
        try:
            row["number_of_sampled_keys"] = int(asset.get_editor_property("number_of_sampled_keys"))
        except Exception:
            pass
    return row


def main():
    paths = unreal.EditorAssetLibrary.list_assets(ROOT, recursive=True, include_folder=False)
    assets = []
    for path in sorted(paths):
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if asset:
            assets.append(summarize(asset))
    payload = {
        "ok": bool(assets),
        "root": ROOT,
        "assets": assets,
        "skeletal_mesh_paths": [row["path"] for row in assets if row["class"] == "SkeletalMesh"],
        "anim_sequence_paths": [row["path"] for row in assets if row["class"] == "AnimSequence"],
        "has_key_loop": any("key_loop" in [name.lower() for name in row.get("morph_targets", [])] for row in assets),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    report = json.dumps(payload, indent=2, sort_keys=True)
    OUT.write_text(report + "\n", encoding="utf-8")
    print(report)
    if not payload["ok"]:
        raise RuntimeError("No textured biker assets found")


main()
