import unreal


ASSET_DIR = "/Game/Peloton"
ASSET_NAME = "BP_PelotonSpline"
MAP_PATH = "/Game/Ejea"
ACTOR_LABEL = "Peloton_Ciclistas_EditableSpline"


def ensure_directory(path: str) -> None:
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)


def create_or_load_blueprint():
    asset_path = f"{ASSET_DIR}/{ASSET_NAME}"
    existing = unreal.EditorAssetLibrary.load_asset(asset_path)
    if existing:
        return existing

    parent_class = unreal.load_class(None, "/Script/AirTraffic.PelotonSplineActor")
    if not parent_class:
        parent_class = unreal.PelotonSplineActor

    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent_class)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    return asset_tools.create_asset(
        asset_name=ASSET_NAME,
        package_path=ASSET_DIR,
        asset_class=unreal.Blueprint,
        factory=factory,
    )


def get_generated_class(blueprint):
    generated_class_getter = getattr(blueprint, "generated_class", None)
    generated_class = generated_class_getter() if callable(generated_class_getter) else None
    if not generated_class:
        try:
            generated_class = blueprint.get_editor_property("generated_class")
        except Exception:
            generated_class = None
    if not generated_class:
        compile_blueprint(blueprint)
        generated_class_getter = getattr(blueprint, "generated_class", None)
        generated_class = generated_class_getter() if callable(generated_class_getter) else None
    if not generated_class:
        unreal.EditorAssetLibrary.save_loaded_asset(blueprint)
        generated_class = unreal.load_class(None, f"{ASSET_DIR}/{ASSET_NAME}.{ASSET_NAME}_C")
    return generated_class


def compile_blueprint(blueprint) -> bool:
    for utility_name in ["KismetEditorUtilities", "BlueprintEditorLibrary"]:
        utility = getattr(unreal, utility_name, None)
        compile_method = getattr(utility, "compile_blueprint", None) if utility else None
        if callable(compile_method):
            compile_method(blueprint)
            return True
    return False


def set_property(target, candidates, value) -> bool:
    if isinstance(candidates, str):
        candidates = [candidates]

    last_error = None
    for name in candidates:
        try:
            target.set_editor_property(name, value)
            return True
        except Exception as exc:
            last_error = exc

    unreal.log_warning(f"Could not set {candidates[0]} on {target}: {last_error}")
    return False


def get_property(target, candidates):
    if isinstance(candidates, str):
        candidates = [candidates]

    for name in candidates:
        try:
            return target.get_editor_property(name)
        except Exception:
            pass
    return None


def call_method(target, candidates):
    for name in candidates:
        method = getattr(target, name, None)
        if callable(method):
            method()
            return True
    return False


def configure_blueprint(blueprint):
    generated_class = get_generated_class(blueprint)
    if not generated_class:
        raise RuntimeError("Could not resolve generated class for BP_PelotonSpline.")

    defaults = unreal.get_default_object(generated_class)
    rider_mesh = unreal.EditorAssetLibrary.load_asset("/Game/biker_mesh")
    if rider_mesh:
        set_property(defaults, ["rider_static_mesh", "RiderStaticMesh"], rider_mesh)

    rider_class = unreal.load_class(None, "/Game/bp_biker.bp_biker_C")
    if rider_class:
        set_property(defaults, ["rider_class", "RiderClass"], rider_class)

    set_property(defaults, ["rider_count", "RiderCount"], 18)
    set_property(defaults, ["max_riders_per_row", "MaxRidersPerRow"], 5)
    set_property(defaults, ["longitudinal_spacing", "LongitudinalSpacing"], 220.0)
    set_property(defaults, ["lateral_spacing", "LateralSpacing"], 95.0)
    set_property(defaults, ["alternate_row_lateral_stagger", "AlternateRowLateralStagger"], 35.0)
    set_property(defaults, ["speed_cm_per_second", "SpeedCmPerSecond"], 850.0)
    set_property(defaults, ["loop", "b_loop", "bLoop"], True)
    set_property(defaults, ["animate_in_game", "b_animate_in_game", "bAnimateInGame"], True)
    set_property(defaults, ["animate_in_editor", "b_animate_in_editor", "bAnimateInEditor"], False)
    set_property(defaults, ["rider_yaw_offset", "RiderYawOffset"], 0.0)

    compile_blueprint(blueprint)
    unreal.EditorAssetLibrary.save_loaded_asset(blueprint)


def find_existing_actor():
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors() if actor_subsystem else unreal.EditorLevelLibrary.get_all_level_actors()
    for actor in actors:
        if actor.get_actor_label() == ACTOR_LABEL:
            return actor
    return None


def spawn_actor_from_class(actor_class, location, rotation):
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if actor_subsystem:
        return actor_subsystem.spawn_actor_from_class(actor_class, location, rotation)
    return unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, location, rotation)


def configure_actor(actor):
    actor.set_actor_label(ACTOR_LABEL)
    actor.set_actor_location(unreal.Vector(0.0, 0.0, 120.0), False, False)
    actor.set_actor_rotation(unreal.Rotator(0.0, 0.0, 0.0), False)
    rider_mesh = unreal.EditorAssetLibrary.load_asset("/Game/biker_mesh")
    if rider_mesh:
        set_property(actor, ["rider_static_mesh", "RiderStaticMesh"], rider_mesh)
    set_property(actor, ["rider_count", "RiderCount"], 18)
    set_property(actor, ["max_riders_per_row", "MaxRidersPerRow"], 5)
    set_property(actor, ["speed_cm_per_second", "SpeedCmPerSecond"], 850.0)
    set_property(actor, ["loop", "b_loop", "bLoop"], True)
    set_property(actor, ["animate_in_game", "b_animate_in_game", "bAnimateInGame"], True)
    set_property(actor, ["animate_in_editor", "b_animate_in_editor", "bAnimateInEditor"], False)

    spline = get_property(actor, ["route_spline", "RouteSpline"])
    if spline:
        spline.clear_spline_points(False)
        route_points = [
            unreal.Vector(-1400.0, -550.0, 0.0),
            unreal.Vector(-350.0, 900.0, 0.0),
            unreal.Vector(1200.0, 650.0, 0.0),
            unreal.Vector(1550.0, -600.0, 0.0),
            unreal.Vector(150.0, -1050.0, 0.0),
        ]
        for point in route_points:
            spline.add_spline_point(point, unreal.SplineCoordinateSpace.LOCAL, False)
        spline.set_closed_loop(True, False)
        spline.update_spline()

    call_method(actor, ["rebuild_peloton", "RebuildPeloton"])


def main():
    ensure_directory(ASSET_DIR)
    blueprint = create_or_load_blueprint()
    if not blueprint:
        raise RuntimeError("Could not create BP_PelotonSpline.")
    configure_blueprint(blueprint)

    unreal.EditorLevelLibrary.load_level(MAP_PATH)
    bp_class = unreal.load_class(None, f"{ASSET_DIR}/{ASSET_NAME}.{ASSET_NAME}_C")
    if not bp_class:
        raise RuntimeError("Could not load generated BP_PelotonSpline class.")

    actor = find_existing_actor()
    if not actor:
        actor = spawn_actor_from_class(
            bp_class,
            unreal.Vector(0.0, 0.0, 120.0),
            unreal.Rotator(0.0, 0.0, 0.0),
        )
    configure_actor(actor)

    unreal.EditorLevelLibrary.save_current_level()
    unreal.EditorAssetLibrary.save_directory(ASSET_DIR, only_if_is_dirty=False, recursive=True)
    print(f"Peloton blueprint ready: {ASSET_DIR}/{ASSET_NAME}")
    print(f"Peloton actor placed: {ACTOR_LABEL} in {MAP_PATH}")


if __name__ == "__main__":
    main()
