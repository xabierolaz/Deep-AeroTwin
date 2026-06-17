import unreal


ASSET_DIR = "/Game/Peloton"
RIDER_MATERIAL_NAME = "M_PelotonRider"
RIDER_MATERIAL_PATH = f"{ASSET_DIR}/{RIDER_MATERIAL_NAME}"
GHOST_MATERIAL_NAME = "M_PelotonGhost"
GHOST_MATERIAL_PATH = f"{ASSET_DIR}/{GHOST_MATERIAL_NAME}"
BP_PATH = "/Game/Peloton/BP_PelotonSpline"
MAP_PATH = "/Game/Ejea"
ACTOR_LABEL = "Peloton_Ciclistas_EditableSpline"


def ensure_directory(path):
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)


def set_property(target, candidates, value):
    for name in candidates:
        try:
            target.set_editor_property(name, value)
            return True
        except Exception:
            pass
    return False


def get_property(target, candidates):
    for name in candidates:
        try:
            return target.get_editor_property(name)
        except Exception:
            pass
    return None


def create_material(asset_name, asset_path):
    ensure_directory(ASSET_DIR)
    material = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not material:
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        material = asset_tools.create_asset(
            asset_name=asset_name,
            package_path=ASSET_DIR,
            asset_class=unreal.Material,
            factory=unreal.MaterialFactoryNew(),
        )
    if not material:
        raise RuntimeError(f"Could not create material: {asset_path}")
    return material


def reset_material(material):
    return unreal.MaterialEditingLibrary


def set_unlit(material):
    material.set_editor_property("two_sided", True)
    try:
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    except Exception:
        pass


def create_or_update_rider_material():
    material = create_material(RIDER_MATERIAL_NAME, RIDER_MATERIAL_PATH)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    set_unlit(material)

    editing = reset_material(material)
    color = editing.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -420, -60)
    color.set_editor_property("parameter_name", "RiderColor")
    color.set_editor_property("default_value", unreal.LinearColor(1.0, 0.0, 0.0, 1.0))

    editing.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    editing.connect_material_property(color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    editing.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def create_or_update_ghost_material():
    material = create_material(GHOST_MATERIAL_NAME, GHOST_MATERIAL_PATH)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    set_unlit(material)

    editing = reset_material(material)
    color = editing.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -420, -80)
    color.set_editor_property("parameter_name", "GhostColor")
    color.set_editor_property("default_value", unreal.LinearColor(1.0, 0.0, 0.0, 1.0))

    opacity = editing.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -420, 120)
    opacity.set_editor_property("parameter_name", "GhostOpacity")
    opacity.set_editor_property("default_value", 0.35)

    editing.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    editing.connect_material_property(color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    editing.connect_material_property(opacity, "", unreal.MaterialProperty.MP_OPACITY)
    editing.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def generated_class(blueprint):
    getter = getattr(blueprint, "generated_class", None)
    if callable(getter):
        generated = getter()
        if generated:
            return generated
    return unreal.load_class(None, f"{BP_PATH}.BP_PelotonSpline_C")


def find_actor():
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors() if actor_subsystem else unreal.EditorLevelLibrary.get_all_level_actors()
    return next((actor for actor in actors if actor.get_actor_label() == ACTOR_LABEL), None)


def call_rebuild(actor):
    for name in ["rebuild_peloton", "RebuildPeloton"]:
        method = getattr(actor, name, None)
        if callable(method):
            method()
            return
    raise RuntimeError("Could not call RebuildPeloton.")


def configure(target, rider_material, ghost_material, reset_defaults):
    set_property(target, ["rider_material", "RiderMaterial"], rider_material)
    set_property(target, ["ghost_material", "GhostMaterial"], ghost_material)
    set_property(target, ["riders_cast_shadows", "b_riders_cast_shadows", "bRidersCastShadows"], False)
    set_property(target, ["show_forward_leader_ghosts", "b_show_forward_leader_ghosts", "bShowForwardLeaderGhosts"], True)
    set_property(target, ["show_backward_last_ghosts", "b_show_backward_last_ghosts", "bShowBackwardLastGhosts"], True)
    if reset_defaults:
        set_property(target, ["forward_ghost_distance", "ForwardGhostDistance"], 1800.0)
        set_property(target, ["backward_ghost_distance", "BackwardGhostDistance"], 1800.0)
        set_property(target, ["forward_ghost_start_offset", "ForwardGhostStartOffset"], 250.0)
        set_property(target, ["backward_ghost_start_offset", "BackwardGhostStartOffset"], 250.0)
        set_property(target, ["ghost_spacing", "GhostSpacing"], 300.0)
        set_property(target, ["max_ghosts_per_side", "MaxGhostsPerSide"], 8)
        set_property(target, ["ghost_max_opacity", "GhostMaxOpacity"], 0.38)
        set_property(target, ["ghost_min_opacity", "GhostMinOpacity"], 0.1)
        set_property(target, ["use_ghost_heatmap", "b_use_ghost_heatmap", "bUseGhostHeatmap"], True)
        set_property(target, ["ghost_hot_color", "GhostHotColor"], unreal.LinearColor(1.0, 0.0, 0.0, 1.0))
        set_property(target, ["ghost_mid_color", "GhostMidColor"], unreal.LinearColor(0.0, 1.0, 0.08, 1.0))
        set_property(target, ["ghost_cold_color", "GhostColdColor"], unreal.LinearColor(0.0, 0.08, 1.0, 1.0))
    set_property(target, ["forward_ghost_color", "ForwardGhostColor"], unreal.LinearColor(1.0, 0.0, 0.0, 1.0))
    set_property(target, ["backward_ghost_color", "BackwardGhostColor"], unreal.LinearColor(0.0, 0.32, 1.0, 1.0))


def count_prefixed_static_mesh_components(actor, prefix):
    return len([
        component
        for component in actor.get_components_by_class(unreal.StaticMeshComponent)
        if component.get_name().startswith(prefix)
    ])


def main():
    rider_material = create_or_update_rider_material()
    ghost_material = create_or_update_ghost_material()

    blueprint = unreal.EditorAssetLibrary.load_asset(BP_PATH)
    if not blueprint:
        raise RuntimeError(f"Blueprint not found: {BP_PATH}")
    defaults = unreal.get_default_object(generated_class(blueprint))
    configure(defaults, rider_material, ghost_material, reset_defaults=True)
    unreal.EditorAssetLibrary.save_loaded_asset(blueprint)

    unreal.EditorLevelLibrary.load_level(MAP_PATH)
    actor = find_actor()
    if not actor:
        raise RuntimeError(f"Actor not found: {ACTOR_LABEL}")
    configure(actor, rider_material, ghost_material, reset_defaults=False)
    call_rebuild(actor)
    unreal.EditorLevelLibrary.save_current_level()

    forward_count = count_prefixed_static_mesh_components(actor, "PelotonForwardGhost")
    backward_count = count_prefixed_static_mesh_components(actor, "PelotonBackwardGhost")
    print(f"Peloton rider material: {rider_material.get_path_name()}")
    print(f"Peloton leader/last ghosts material: {ghost_material.get_path_name()}")
    print(f"Peloton leader/last ghosts forward_count={forward_count} backward_count={backward_count}")
    print(f"Peloton leader/last ghosts forward_distance={get_property(actor, ['forward_ghost_distance', 'ForwardGhostDistance'])}")
    print(f"Peloton leader/last ghosts backward_distance={get_property(actor, ['backward_ghost_distance', 'BackwardGhostDistance'])}")


if __name__ == "__main__":
    main()
