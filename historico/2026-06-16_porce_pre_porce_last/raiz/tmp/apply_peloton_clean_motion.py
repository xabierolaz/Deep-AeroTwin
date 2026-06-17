import unreal


BP_PATH = "/Game/Peloton/BP_PelotonSpline"
MAP_PATH = "/Game/Ejea"
ACTOR_LABEL = "Peloton_Ciclistas_EditableSpline"


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


def clean_motion_enum_value():
    enum_class = getattr(unreal, "PelotonRiderRenderMode", None)
    if not enum_class:
        raise RuntimeError("PelotonRiderRenderMode enum is not available.")

    for candidate in ["STATIC_MESH_COMPONENTS", "StaticMeshComponents"]:
        value = getattr(enum_class, candidate, None)
        if value is not None:
            return value

    raise RuntimeError(f"Could not resolve clean motion enum value. Available: {dir(enum_class)}")


def call_rebuild(actor):
    for name in ["rebuild_peloton", "RebuildPeloton"]:
        method = getattr(actor, name, None)
        if callable(method):
            method()
            return
    raise RuntimeError("Could not call RebuildPeloton on actor.")


def generated_class(blueprint):
    getter = getattr(blueprint, "generated_class", None)
    if callable(getter):
        return getter()
    return unreal.load_class(None, f"{BP_PATH}.BP_PelotonSpline_C")


def find_actor():
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors() if actor_subsystem else unreal.EditorLevelLibrary.get_all_level_actors()
    return next((actor for actor in actors if actor.get_actor_label() == ACTOR_LABEL), None)


def main():
    clean_motion = clean_motion_enum_value()

    blueprint = unreal.EditorAssetLibrary.load_asset(BP_PATH)
    if not blueprint:
        raise RuntimeError(f"Blueprint not found: {BP_PATH}")

    bp_class = generated_class(blueprint)
    defaults = unreal.get_default_object(bp_class)
    if not set_property(defaults, ["rider_render_mode", "RiderRenderMode"], clean_motion):
        raise RuntimeError("Could not set RiderRenderMode on blueprint defaults.")
    unreal.EditorAssetLibrary.save_loaded_asset(blueprint)

    unreal.EditorLevelLibrary.load_level(MAP_PATH)
    actor = find_actor()
    if not actor:
        raise RuntimeError(f"Actor not found: {ACTOR_LABEL}")

    if not set_property(actor, ["rider_render_mode", "RiderRenderMode"], clean_motion):
        raise RuntimeError("Could not set RiderRenderMode on map actor.")
    call_rebuild(actor)
    unreal.EditorLevelLibrary.save_current_level()

    mode = get_property(actor, ["rider_render_mode", "RiderRenderMode"])
    mesh_components = [
        component
        for component in actor.get_components_by_class(unreal.StaticMeshComponent)
        if component.get_name().startswith("PelotonRiderMesh_")
    ]
    mesh_instances = get_property(actor, ["rider_mesh_instances", "RiderMeshInstances"])
    instance_count = mesh_instances.get_instance_count() if mesh_instances else 0

    print(f"Peloton clean motion mode applied: {mode}")
    print(f"Peloton clean motion mesh components: {len(mesh_components)}")
    print(f"Peloton clean motion instanced mesh count: {instance_count}")


if __name__ == "__main__":
    main()
