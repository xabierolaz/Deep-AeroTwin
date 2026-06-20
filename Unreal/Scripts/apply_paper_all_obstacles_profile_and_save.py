import json
from pathlib import Path

import unreal

LEVEL_PATH = "/Game/Ejea"
REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
PROFILE_SCRIPT = REPO / "Unreal" / "Scripts" / "paper_scenario_visibility.py"
OUT = REPO / "pipeline" / "logs" / "paper_all_obstacles_profile_latest.json"
GENERATED_CAPTURE_PATH = "/Game/Generated/PaperCaptures"


def dirty_package_names():
    dirty = []
    for fn_name in ("get_dirty_content_packages", "get_dirty_map_packages"):
        fn = getattr(unreal.EditorLoadingAndSavingUtils, fn_name, None)
        if not fn:
            continue
        for package in fn():
            try:
                dirty.append(str(package.get_name()))
            except Exception:
                dirty.append(str(package))
    return sorted(set(dirty))


def editor_world():
    subsystem_class = getattr(unreal, "UnrealEditorSubsystem", None)
    if subsystem_class:
        try:
            subsystem = unreal.get_editor_subsystem(subsystem_class)
            if subsystem:
                world = subsystem.get_editor_world()
                if world:
                    return world
        except Exception:
            pass
    return unreal.EditorLevelLibrary.get_editor_world()

def actor_label(actor):
    try:
        return str(actor.get_actor_label())
    except Exception:
        return str(actor.get_name())

def is_temp_dat_name(value):
    return str(value).startswith("DAT_")

def cleanup_temp_capture_artifacts():
    destroyed_actors = []
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in list(subsystem.get_all_level_actors()):
        label = actor_label(actor)
        name = str(actor.get_name())
        if is_temp_dat_name(label) or is_temp_dat_name(name):
            destroyed_actors.append({"label": label, "name": name, "class": actor.get_class().get_name()})
            try:
                subsystem.destroy_actor(actor)
            except Exception:
                pass

    deleted_assets = []
    if unreal.EditorAssetLibrary.does_directory_exist(GENERATED_CAPTURE_PATH):
        for asset_path in unreal.EditorAssetLibrary.list_assets(GENERATED_CAPTURE_PATH, recursive=True, include_folder=False):
            asset_name = str(asset_path).rsplit("/", 1)[-1].split(".", 1)[0]
            if is_temp_dat_name(asset_name) and unreal.EditorAssetLibrary.delete_asset(asset_path):
                deleted_assets.append(asset_path)

        remaining = unreal.EditorAssetLibrary.list_assets(GENERATED_CAPTURE_PATH, recursive=True, include_folder=False)
        if not remaining:
            try:
                unreal.EditorAssetLibrary.delete_directory(GENERATED_CAPTURE_PATH)
            except Exception:
                pass

    return {"destroyed_actors": destroyed_actors, "deleted_assets": deleted_assets}


def disable_world_bounds_checks():
    world = editor_world()
    if not world:
        return {"changed": False, "reason": "editor_world_not_found"}
    settings = world.get_world_settings()
    if not settings:
        return {"changed": False, "reason": "world_settings_not_found"}

    tried = []
    for prop_name in ("enable_world_bounds_checks", "b_enable_world_bounds_checks", "bEnableWorldBoundsChecks"):
        try:
            current = bool(settings.get_editor_property(prop_name))
            if current:
                settings.modify()
                settings.set_editor_property(prop_name, False)
            return {"changed": current, "property": prop_name}
        except Exception as exc:
            tried.append({"property": prop_name, "error": str(exc)})
    return {"changed": False, "reason": "property_not_found", "tried": tried}


def set_paper_obstacle_mobility():
    movable = getattr(unreal.ComponentMobility, "MOVABLE", None)
    if movable is None:
        return {"changed": 0, "reason": "movable_enum_not_found"}

    target_meshes = {
        "/Game/tower_mesh.tower_mesh",
        "/Game/cow_mesh.cow_mesh",
    }
    marker_labels = {"A", "B"}
    changed = []
    inspected = 0
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if not actor:
            continue
        try:
            label = str(actor.get_actor_label())
        except Exception:
            label = str(actor.get_name())

        static_mesh_components = actor.get_components_by_class(unreal.StaticMeshComponent)
        mesh_paths = set()
        for component in static_mesh_components:
            try:
                mesh = component.get_editor_property("static_mesh")
                if mesh:
                    mesh_paths.add(str(mesh.get_path_name()))
            except Exception:
                pass

        if not (mesh_paths & target_meshes or label in marker_labels):
            continue

        actor_changed = False
        scene_components = actor.get_components_by_class(unreal.SceneComponent)
        for component in scene_components:
            if not component:
                continue
            try:
                if component.get_editor_property("mobility") != movable:
                    actor.modify()
                    component.modify()
                    component.set_editor_property("mobility", movable)
                    actor_changed = True
            except Exception:
                pass
        inspected += 1
        if actor_changed:
            changed.append(label)

    return {"inspected": inspected, "changed": len(changed), "changed_labels": sorted(changed)}


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(LEVEL_PATH)
    namespace = {"__file__": str(PROFILE_SCRIPT)}
    exec(PROFILE_SCRIPT.read_text(encoding="utf-8"), namespace)
    result = namespace["apply_profile"](
        "paper_all_obstacles",
        dry_run=False,
        include_details=False,
        include_actors=False,
    )
    result["world_bounds_checks"] = disable_world_bounds_checks()
    result["paper_obstacle_mobility"] = set_paper_obstacle_mobility()
    result["temp_capture_cleanup"] = cleanup_temp_capture_artifacts()
    before_save = dirty_package_names()
    saved = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(
        save_map_packages=True,
        save_content_packages=True,
    )
    result["dirty_before_save"] = before_save
    result["saved"] = bool(saved)
    result["dirty_after_save"] = dirty_package_names()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


main()
