import json
import os
from pathlib import Path

import unreal

REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
SOURCE = REPO / "Unreal" / "SourceAssets" / "Peloton" / "biker_text_pedal_loop.glb"
DEST = "/Game/Peloton/TexturedBiker"
OUT = REPO / "pipeline" / "logs" / "import_textured_biker_morph_latest.json"


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


def call_first(asset, names):
    for name in names:
        method = getattr(asset, name, None)
        if callable(method):
            try:
                return method()
            except Exception:
                pass
    return None


def summarize_asset(asset):
    row = {
        "path": object_path(asset),
        "class": class_name(asset),
    }
    morphs = call_first(
        asset,
        (
            "get_all_morph_target_names",
            "get_morph_target_names",
        ),
    )
    if morphs is not None:
        row["morph_targets"] = [safe_text(item) for item in morphs]
    if hasattr(asset, "get_num_lods"):
        try:
            row["lod_count"] = int(asset.get_num_lods())
        except Exception:
            pass
    if hasattr(asset, "get_materials"):
        try:
            row["material_count"] = len(asset.get_materials())
        except Exception:
            pass
    return row


def main():
    if not SOURCE.exists():
        raise RuntimeError(f"Missing source GLB: {SOURCE}")

    unreal.EditorAssetLibrary.make_directory(DEST)

    existing_paths = [
        path
        for path in unreal.EditorAssetLibrary.list_assets(DEST, recursive=True, include_folder=False)
        if path
    ]
    force_reimport = os.environ.get("PORCE_FORCE_REIMPORT_TEXTURED_BIKER", "0").strip().lower() in ("1", "true", "yes")
    imported_paths = []
    if force_reimport or not existing_paths:
        task = unreal.AssetImportTask()
        task.filename = str(SOURCE)
        task.destination_path = DEST
        task.automated = True
        task.replace_existing = True
        task.replace_existing_settings = True
        task.save = True

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        imported_paths = [safe_text(path) for path in getattr(task, "imported_object_paths", [])]

    folder_assets = [
        path
        for path in unreal.EditorAssetLibrary.list_assets(DEST, recursive=True, include_folder=False)
        if path
    ]
    assets = []
    for path in sorted(set(imported_paths + folder_assets)):
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if asset:
            assets.append(summarize_asset(asset))

    payload = {
        "ok": bool(assets),
        "source": str(SOURCE),
        "destination": DEST,
        "skipped_existing_import": bool(existing_paths and not force_reimport),
        "imported_object_paths": imported_paths,
        "assets": assets,
        "has_skeletal_mesh": any(row.get("class") == "SkeletalMesh" for row in assets),
        "has_morph_target_key_loop": any(
            "key_loop" in [name.lower() for name in row.get("morph_targets", [])]
            for row in assets
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["ok"]:
        raise RuntimeError("Textured biker import produced no assets")


main()
