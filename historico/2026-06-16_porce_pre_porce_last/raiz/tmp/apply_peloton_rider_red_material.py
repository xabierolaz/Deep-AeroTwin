import unreal


ASSET_DIR = "/Game/Peloton"
RIDER_MATERIAL_NAME = "M_PelotonRider"
RIDER_MATERIAL_PATH = f"{ASSET_DIR}/{RIDER_MATERIAL_NAME}"
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


def create_or_update_rider_material():
    ensure_directory(ASSET_DIR)
    material = unreal.EditorAssetLibrary.load_asset(RIDER_MATERIAL_PATH)
    if not material:
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        material = asset_tools.create_asset(
            asset_name=RIDER_MATERIAL_NAME,
            package_path=ASSET_DIR,
            asset_class=unreal.Material,
            factory=unreal.MaterialFactoryNew(),
        )
    if not material:
        raise RuntimeError(f"Could not create material: {RIDER_MATERIAL_PATH}")

    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    material.set_editor_property("two_sided", True)
    try:
        material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    except Exception:
        pass

    editing = unreal.MaterialEditingLibrary
    color = editing.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -420, -60)
    color.set_editor_property("parameter_name", "RiderColor")
    color.set_editor_property("default_value", unreal.LinearColor(1.0, 0.0, 0.0, 1.0))
    editing.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    editing.connect_material_property(color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
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


def main():
    rider_material = create_or_update_rider_material()

    blueprint = unreal.EditorAssetLibrary.load_asset(BP_PATH)
    if not blueprint:
        raise RuntimeError(f"Blueprint not found: {BP_PATH}")

    defaults = unreal.get_default_object(generated_class(blueprint))
    set_property(defaults, ["rider_material", "RiderMaterial"], rider_material)
    unreal.EditorAssetLibrary.save_loaded_asset(blueprint)

    unreal.EditorLevelLibrary.load_level(MAP_PATH)
    actor = find_actor()
    if not actor:
        raise RuntimeError(f"Actor not found: {ACTOR_LABEL}")

    set_property(actor, ["rider_material", "RiderMaterial"], rider_material)
    call_rebuild(actor)
    unreal.EditorLevelLibrary.save_current_level()

    rider_components = [
        component
        for component in actor.get_components_by_class(unreal.StaticMeshComponent)
        if component.get_name().startswith("PelotonRiderMesh_")
    ]
    slot_names = []
    if rider_components:
        slot_names = [
            rider_components[0].get_material(index).get_name()
            for index in range(rider_components[0].get_num_materials())
        ]

    print(f"Peloton rider material path={rider_material.get_path_name()}")
    print("Peloton rider material color=red")
    print(f"Peloton rider mesh components={len(rider_components)}")
    print(f"Peloton rider slot materials={slot_names}")


if __name__ == "__main__":
    main()
