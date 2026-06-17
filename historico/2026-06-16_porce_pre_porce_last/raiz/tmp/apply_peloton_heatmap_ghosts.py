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


def configure(target):
    set_property(target, ["use_ghost_heatmap", "b_use_ghost_heatmap", "bUseGhostHeatmap"], True)
    set_property(target, ["ghost_hot_color", "GhostHotColor"], unreal.LinearColor(1.0, 0.0, 0.0, 1.0))
    set_property(target, ["ghost_mid_color", "GhostMidColor"], unreal.LinearColor(0.0, 1.0, 0.08, 1.0))
    set_property(target, ["ghost_cold_color", "GhostColdColor"], unreal.LinearColor(0.0, 0.08, 1.0, 1.0))
    set_property(target, ["ghost_min_opacity", "GhostMinOpacity"], 0.1)
    set_property(target, ["max_ghosts_per_side", "MaxGhostsPerSide"], 8)
    set_property(target, ["riders_cast_shadows", "b_riders_cast_shadows", "bRidersCastShadows"], False)


def count_prefixed_static_mesh_components(actor, prefix):
    return len([
        component
        for component in actor.get_components_by_class(unreal.StaticMeshComponent)
        if component.get_name().startswith(prefix)
    ])


def main():
    blueprint = unreal.EditorAssetLibrary.load_asset(BP_PATH)
    if not blueprint:
        raise RuntimeError(f"Blueprint not found: {BP_PATH}")

    defaults = unreal.get_default_object(generated_class(blueprint))
    configure(defaults)
    unreal.EditorAssetLibrary.save_loaded_asset(blueprint)

    unreal.EditorLevelLibrary.load_level(MAP_PATH)
    actor = find_actor()
    if not actor:
        raise RuntimeError(f"Actor not found: {ACTOR_LABEL}")

    configure(actor)
    call_rebuild(actor)
    unreal.EditorLevelLibrary.save_current_level()

    forward_count = count_prefixed_static_mesh_components(actor, "PelotonForwardGhost")
    backward_count = count_prefixed_static_mesh_components(actor, "PelotonBackwardGhost")
    print(f"Peloton heatmap ghosts enabled={get_property(actor, ['use_ghost_heatmap', 'b_use_ghost_heatmap', 'bUseGhostHeatmap'])}")
    print(f"Peloton heatmap colors hot={get_property(actor, ['ghost_hot_color', 'GhostHotColor'])}")
    print(f"Peloton heatmap colors mid={get_property(actor, ['ghost_mid_color', 'GhostMidColor'])}")
    print(f"Peloton heatmap colors cold={get_property(actor, ['ghost_cold_color', 'GhostColdColor'])}")
    print(f"Peloton heatmap min opacity={get_property(actor, ['ghost_min_opacity', 'GhostMinOpacity'])}")
    print(f"Peloton heatmap ghost counts forward={forward_count} backward={backward_count}")
    print(f"Peloton max ghosts per side={get_property(actor, ['max_ghosts_per_side', 'MaxGhostsPerSide'])}")


if __name__ == "__main__":
    main()
