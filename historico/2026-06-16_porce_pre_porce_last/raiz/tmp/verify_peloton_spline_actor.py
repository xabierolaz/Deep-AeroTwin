import unreal


MAP_PATH = "/Game/Ejea"
ACTOR_LABEL = "Peloton_Ciclistas_EditableSpline"


def get_property(target, candidates):
    for name in candidates:
        try:
            return target.get_editor_property(name)
        except Exception:
            pass
    return None


def main():
    unreal.EditorLevelLibrary.load_level(MAP_PATH)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors() if actor_subsystem else unreal.EditorLevelLibrary.get_all_level_actors()
    actor = next((candidate for candidate in actors if candidate.get_actor_label() == ACTOR_LABEL), None)
    if not actor:
        raise RuntimeError(f"Actor not found: {ACTOR_LABEL}")

    rider_count = get_property(actor, ["rider_count", "RiderCount"])
    max_row = get_property(actor, ["max_riders_per_row", "MaxRidersPerRow"])
    speed = get_property(actor, ["speed_cm_per_second", "SpeedCmPerSecond"])
    spline = get_property(actor, ["route_spline", "RouteSpline"])
    mesh_instances = get_property(actor, ["rider_mesh_instances", "RiderMeshInstances"])
    rider_mesh = get_property(actor, ["rider_static_mesh", "RiderStaticMesh"])
    rider_render_mode = get_property(actor, ["rider_render_mode", "RiderRenderMode"])
    forward_ghost_distance = get_property(actor, ["forward_ghost_distance", "ForwardGhostDistance"])
    backward_ghost_distance = get_property(actor, ["backward_ghost_distance", "BackwardGhostDistance"])
    ghost_material = get_property(actor, ["ghost_material", "GhostMaterial"])
    rider_material = get_property(actor, ["rider_material", "RiderMaterial"])

    spline_points = spline.get_number_of_spline_points() if spline else 0
    is_closed = spline.is_closed_loop() if spline else False
    instance_count = mesh_instances.get_instance_count() if mesh_instances else 0
    mesh_component_count = len([
        component
        for component in actor.get_components_by_class(unreal.StaticMeshComponent)
        if component.get_name().startswith("PelotonRiderMesh_")
    ])
    forward_ghost_count = len([
        component
        for component in actor.get_components_by_class(unreal.StaticMeshComponent)
        if component.get_name().startswith("PelotonForwardGhost")
    ])
    backward_ghost_count = len([
        component
        for component in actor.get_components_by_class(unreal.StaticMeshComponent)
        if component.get_name().startswith("PelotonBackwardGhost")
    ])
    mesh_name = rider_mesh.get_name() if rider_mesh else "NONE"
    ghost_material_name = ghost_material.get_name() if ghost_material else "NONE"
    rider_material_name = rider_material.get_name() if rider_material else "NONE"

    print(f"Peloton verification actor={actor.get_actor_label()} class={actor.get_class().get_name()}")
    print(f"Peloton verification riders={rider_count} mesh_components={mesh_component_count} instances={instance_count} max_row={max_row}")
    print(f"Peloton verification spline_points={spline_points} closed={is_closed} speed={speed}")
    print(f"Peloton verification mesh={mesh_name} render_mode={rider_render_mode} rider_material={rider_material_name}")
    print(f"Peloton verification ghosts forward={forward_ghost_count} backward={backward_ghost_count} material={ghost_material_name}")
    print(f"Peloton verification ghost_distances forward={forward_ghost_distance} backward={backward_ghost_distance}")

    if rider_count != 18:
        raise RuntimeError(f"Unexpected rider count: {rider_count}")
    if mesh_component_count != 18:
        raise RuntimeError(f"Unexpected rider mesh component count: {mesh_component_count}")
    if instance_count != 0:
        raise RuntimeError(f"Unexpected rider mesh instance count: {instance_count}")
    if spline_points < 4 or not is_closed:
        raise RuntimeError("Spline route is not configured as expected.")
    if mesh_name != "biker_mesh":
        raise RuntimeError(f"Unexpected rider mesh: {mesh_name}")
    if forward_ghost_count <= 0 or backward_ghost_count <= 0:
        raise RuntimeError(f"Unexpected ghost counts: forward={forward_ghost_count}, backward={backward_ghost_count}")
    if ghost_material_name != "M_PelotonGhost":
        raise RuntimeError(f"Unexpected ghost material: {ghost_material_name}")
    if rider_material_name != "M_PelotonRider":
        raise RuntimeError(f"Unexpected rider material: {rider_material_name}")

    rider_component = next((
        component
        for component in actor.get_components_by_class(unreal.StaticMeshComponent)
        if component.get_name().startswith("PelotonRiderMesh_")
    ), None)
    forward_ghost_component = next((
        component
        for component in actor.get_components_by_class(unreal.StaticMeshComponent)
        if component.get_name().startswith("PelotonForwardGhost")
    ), None)
    if not rider_component or not forward_ghost_component:
        raise RuntimeError("Could not resolve representative rider/ghost components.")

    rider_material_names = [rider_component.get_material(index).get_name() for index in range(rider_component.get_num_materials())]
    ghost_material_names = [forward_ghost_component.get_material(index).get_name() for index in range(forward_ghost_component.get_num_materials())]
    print(f"Peloton verification rider_slot_materials={rider_material_names}")
    print(f"Peloton verification ghost_slot_materials={ghost_material_names}")

    if not rider_material_names or not all("M_PelotonRider" in name for name in rider_material_names):
        raise RuntimeError(f"Rider material was not applied to all slots: {rider_material_names}")
    if not ghost_material_names or not all("M_PelotonGhost" in name for name in ghost_material_names):
        raise RuntimeError(f"Ghost dynamic material was not applied to all slots: {ghost_material_names}")

    start_location = forward_ghost_component.get_world_location()
    setter = getattr(actor, "set_preview_distance", None)
    if callable(setter):
        setter(float(editor_preview_distance) + 900.0 if (editor_preview_distance := get_property(actor, ["editor_preview_distance", "EditorPreviewDistance"])) is not None else 900.0)
    else:
        set_property(actor, ["editor_preview_distance", "EditorPreviewDistance"], 900.0)
        rebuild = getattr(actor, "rebuild_peloton", None)
        if callable(rebuild):
            rebuild()
    end_location = forward_ghost_component.get_world_location()
    moved = (
        (start_location.x - end_location.x) ** 2
        + (start_location.y - end_location.y) ** 2
        + (start_location.z - end_location.z) ** 2
    ) ** 0.5
    print(f"Peloton verification ghost_move_delta={moved}")
    if moved <= 1.0:
        raise RuntimeError("Forward ghost did not move when preview distance changed.")


if __name__ == "__main__":
    main()
