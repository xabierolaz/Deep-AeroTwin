import unreal


MAP_PATH = "/Game/SPPABenchmark"


def main():
    level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level_editor is None:
        raise RuntimeError("LevelEditorSubsystem is not available.")

    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PATH):
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
    else:
        level_editor.new_level(MAP_PATH)

    # Keep the benchmark map deliberately empty. The packaged benchmark runner
    # creates its own camera, light, telemetry component, and synthetic payload.
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if isinstance(actor, unreal.WorldSettings):
            continue
        unreal.EditorLevelLibrary.destroy_actor(actor)

    if not unreal.EditorAssetLibrary.save_asset(MAP_PATH, only_if_is_dirty=False):
        raise RuntimeError(f"Could not save {MAP_PATH}.")

    unreal.log(f"Saved {MAP_PATH} for SPPA packaged render benchmarks.")


if __name__ == "__main__":
    main()
