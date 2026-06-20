import json
import math
import os
import time
import traceback
from pathlib import Path

import unreal


OUT_DIR = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent / "figuras_paper_unreal_generadas"
CAPTURE_DIR = OUT_DIR / "unreal_scene_captures"
WIDTH = 1920
HEIGHT = 1080
CAPTURE_SETTLE_PASSES = 6
CAPTURE_SETTLE_SLEEP_S = 0.35
CESIUM_PAPER_PROFILE = {
    "MaximumScreenSpaceError": 8.0,
    "PreloadAncestors": True,
    "PreloadSiblings": True,
    "ForbidHoles": True,
    "MaximumSimultaneousTileLoads": 96,
    "MaximumCachedBytes": 8 * 1024 * 1024 * 1024,
    "LoadingDescendantLimit": 0,
    "EnableFrustumCulling": False,
    "EnableFogCulling": False,
    "EnforceCulledScreenSpaceError": True,
    "CulledScreenSpaceError": 16.0,
    "EnableOcclusionCulling": False,
    "DelayRefinementForOcclusion": False,
    "UseLodTransitions": False,
    "LodTransitionLength": 1.0,
    "SuspendUpdate": False,
    "UpdateInEditor": True,
    "UnloadEditorTilesInPlayMode": False,
}


TEMP_PREFIX = "DAT_PaperCapture_"
QUIT_AFTER_SCRIPT = os.environ.get("PORCE_UNREAL_QUIT_AFTER_SCRIPT", "0").strip().lower() in ("1", "true", "yes")
TEXTURED_RIDER_SKELETAL_MESH_PATH = (
    "/Game/Peloton/TexturedBiker/biker_text_pedal_loop/SkeletalMeshes/"
    "biker_text_pedal_loop.biker_text_pedal_loop"
)


def label(actor):
    try:
        return str(actor.get_actor_label())
    except Exception:
        return str(actor.get_name())


def vec(v):
    return {"x": float(v.x), "y": float(v.y), "z": float(v.z)}


def find_actor(containing):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    needle = containing.lower()
    for actor in subsystem.get_all_level_actors():
        haystack = " ".join([label(actor), str(actor.get_name()), str(actor.get_class().get_name())]).lower()
        if needle in haystack:
            return actor
    return None


def find_peloton_actor():
    return find_actor("peloton")


def load_required_rider_mesh():
    mesh = unreal.EditorAssetLibrary.load_asset(TEXTURED_RIDER_SKELETAL_MESH_PATH)
    if not mesh:
        raise RuntimeError("Missing required textured rider skeletal mesh: %s" % TEXTURED_RIDER_SKELETAL_MESH_PATH)
    return mesh


def configure_cesium_for_capture():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    changed = {}
    for actor in subsystem.get_all_level_actors():
        if actor.get_class().get_name() == "CesiumCameraManager":
            for key, value in {
                "UsePlayerCameras": True,
                "UseEditorCameras": True,
                "UseSceneCapturesInLevel": True,
            }.items():
                try:
                    if actor.get_editor_property(key) != value:
                        actor.modify()
                        actor.set_editor_property(key, value)
                except Exception:
                    pass
        if actor.get_class().get_name() != "Cesium3DTileset":
            continue
        actor_changes = {}
        for key, value in CESIUM_PAPER_PROFILE.items():
            try:
                previous = actor.get_editor_property(key)
                if previous != value:
                    actor.modify()
                    actor.set_editor_property(key, value)
                    actor_changes[key] = {"from": previous, "to": value}
            except Exception:
                pass
        try:
            actor.refresh_tileset()
        except Exception:
            pass
        changed[label(actor)] = actor_changes
    return changed


def hide_irrelevant_for_peloton():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    changed = []
    for actor in subsystem.get_all_level_actors():
        text = " ".join([label(actor), str(actor.get_name()), str(actor.get_class().get_name())]).lower()
        visible = True
        if "tower" in text or "cow" in text or "vaca" in text:
            visible = False
        if "cesiumcredits" in text or "credits" in text:
            visible = False
        try:
            actor.set_actor_hidden_in_game(not visible)
            actor.set_is_temporarily_hidden_in_editor(not visible)
            changed.append({"actor": label(actor), "visible": visible})
        except Exception:
            pass
    return changed


def stage_peloton(actor):
    settings = {
        "RiderCount": 8,
        "MaxRidersPerRow": 3,
        "LongitudinalSpacing": 190.0,
        "LateralSpacing": 105.0,
        "AlternateRowLateralStagger": 35.0,
        "SpeedCmPerSecond": 640.0,
        "EditorPreviewDistance": 1850.0,
        "bAnimateInEditor": False,
        "bAnimateInGame": True,
        "RiderSkeletalMesh": load_required_rider_mesh(),
        "RiderMaterial": None,
        "bAnimatePedalMorph": True,
        "PedalMorphTargetName": "key_loop",
    }
    applied = {}
    for key, value in settings.items():
        try:
            actor.set_editor_property(key, value)
            applied[key] = True
        except Exception:
            applied[key] = False
    try:
        actor.set_preview_distance(settings["EditorPreviewDistance"])
    except Exception:
        pass
    try:
        actor.rebuild_peloton()
    except Exception:
        pass
    return applied


def cleanup_temp():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in list(subsystem.get_all_level_actors()):
        actor_label = label(actor)
        actor_name = str(actor.get_name())
        if (
            actor_label.startswith("DAT_")
            or actor_name.startswith("DAT_")
            or actor_label.startswith(TEMP_PREFIX)
            or actor_name.startswith(TEMP_PREFIX)
        ):
            try:
                subsystem.destroy_actor(actor)
            except Exception:
                pass


def spawn_box_marker(name, location, scale, color=(0.05, 0.85, 0.20)):
    mesh = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/Cube.Cube")
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.StaticMeshActor, location)
    actor.set_actor_label(TEMP_PREFIX + name)
    comp = actor.get_component_by_class(unreal.StaticMeshComponent)
    if comp:
        comp.set_static_mesh(mesh)
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        comp.set_editor_property("cast_shadow", False)
        comp.set_world_scale3d(unreal.Vector(scale[0], scale[1], scale[2]))
        mat = make_material(TEMP_PREFIX + "Mat_" + name, color, opacity=0.65)
        if mat:
            comp.set_material(0, mat)
    return actor


def make_material(name, color, opacity=1.0):
    # Reuse a transient editor material if one already exists during this run.
    package_path = "/Game/Generated/PaperCaptures/" + name
    if unreal.EditorAssetLibrary.does_asset_exist(package_path):
        existing = unreal.EditorAssetLibrary.load_asset(package_path)
        if existing:
            return existing
    try:
        unreal.EditorAssetLibrary.make_directory("/Game/Generated/PaperCaptures")
        factory = unreal.MaterialFactoryNew()
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, "/Game/Generated/PaperCaptures", unreal.Material, factory)
        mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT if opacity < 1.0 else unreal.BlendMode.BLEND_OPAQUE)
        mat.set_editor_property("two_sided", True)
        red = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, -80)
        red.set_editor_property("r", color[0])
        green = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, 40)
        green.set_editor_property("r", color[1])
        blue = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, 160)
        blue.set_editor_property("r", color[2])
        alpha = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, 280)
        alpha.set_editor_property("r", opacity)
        vec_expr = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionMakeMaterialAttributes, 120, 0)
        unreal.MaterialEditingLibrary.connect_material_property(red, "", unreal.MaterialProperty.MP_BASE_COLOR)
        unreal.MaterialEditingLibrary.connect_material_property(alpha, "", unreal.MaterialProperty.MP_OPACITY)
        unreal.MaterialEditingLibrary.recompile_material(mat)
        return mat
    except Exception:
        return None


def spawn_text(name, text, location, rotation, size=85, color=unreal.Color(40, 255, 90, 255)):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.TextRenderActor, location, rotation)
    actor.set_actor_label(TEMP_PREFIX + name)
    comp = actor.get_component_by_class(unreal.TextRenderComponent)
    if comp:
        comp.set_text(text)
        comp.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
        comp.set_vertical_alignment(unreal.VerticalTextAligment.EVRTA_TEXT_CENTER)
        comp.set_world_size(size)
        comp.set_text_render_color(color)
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    return actor


def get_actor_bounds(actor):
    origin, extent = actor.get_actor_bounds(False)
    return origin, extent


def look_at_rotation(camera_location, target_location):
    direction = target_location - camera_location
    yaw = math.degrees(math.atan2(direction.y, direction.x))
    horizontal = math.sqrt(direction.x * direction.x + direction.y * direction.y)
    pitch = math.degrees(math.atan2(direction.z, horizontal))
    return unreal.Rotator(pitch=pitch, yaw=yaw, roll=0.0)


def capture_scene(name, location, target, fov=42.0, post_label=None):
    world = unreal.EditorLevelLibrary.get_editor_world()
    rotation = look_at_rotation(location, target)
    capture = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, location, rotation)
    capture.set_actor_label(TEMP_PREFIX + name + "_Camera")
    component = capture.capture_component2d
    render_target = unreal.RenderingLibrary.create_render_target2d(world, WIDTH, HEIGHT)
    try:
        render_target.set_editor_property("render_target_format", unreal.TextureRenderTargetFormat.RTF_RGBA8)
    except Exception:
        pass
    component.texture_target = render_target
    component.fov_angle = fov
    component.capture_every_frame = False
    component.capture_on_movement = False
    try:
        component.primitive_render_mode = unreal.SceneCapturePrimitiveRenderMode.PRIM_RENDER_SCENE_PRIMITIVES
    except Exception:
        pass
    try:
        component.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
    except Exception:
        pass
    unreal.RenderingLibrary.clear_render_target2d(world, render_target, unreal.LinearColor(0, 0, 0, 1))
    for _ in range(CAPTURE_SETTLE_PASSES):
        component.capture_scene()
        time.sleep(CAPTURE_SETTLE_SLEEP_S)
    component.capture_scene()
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    unreal.RenderingLibrary.export_render_target(world, render_target, str(CAPTURE_DIR), name)
    raw_path = CAPTURE_DIR / name
    output = CAPTURE_DIR / (name + ".png")
    if raw_path.exists() and not output.exists():
        raw_path.replace(output)
    return {
        "name": name,
        "path": str(output),
        "camera_location": vec(location),
        "target": vec(target),
        "rotation": {"pitch": float(rotation.pitch), "yaw": float(rotation.yaw), "roll": float(rotation.roll)},
        "fov": fov,
        "label": post_label,
    }

def maybe_quit_editor():
    if QUIT_AFTER_SCRIPT:
        unreal.SystemLibrary.quit_editor()


def spawn_yolo_markers(peloton):
    origin, extent = get_actor_bounds(peloton)
    # Tall, thin in-scene YOLO-style boxes around the peloton body and travel direction.
    z = origin.z + max(120.0, extent.z * 0.45)
    markers = []
    markers.append(spawn_box_marker("YOLO_BikerBBox_Main", unreal.Vector(origin.x, origin.y, z), (0.12, max(0.35, extent.y / 50.0), max(0.35, extent.z / 52.0)), (0.05, 0.95, 0.18)))
    markers.append(spawn_box_marker("YOLO_PelotonBBox_Wide", unreal.Vector(origin.x + extent.x * 0.18, origin.y, z + 25), (max(0.35, extent.x / 48.0), 0.12, max(0.30, extent.z / 60.0)), (0.05, 0.95, 0.18)))
    markers.append(spawn_box_marker("YOLO_TrackVector", unreal.Vector(origin.x + extent.x * 0.70, origin.y + extent.y * 0.50, z + 20), (1.6, 0.08, 0.08), (0.95, 0.72, 0.10)))
    text_rot = unreal.Rotator(pitch=0.0, yaw=0.0, roll=0.0)
    markers.append(spawn_text("YOLO_Label_Main", "YOLO biker 0.91", unreal.Vector(origin.x - extent.x * 0.34, origin.y - extent.y * 0.58, z + extent.z * 0.38), text_rot, 92))
    markers.append(spawn_text("YOLO_Label_Track", "track id: peloton", unreal.Vector(origin.x + extent.x * 0.35, origin.y + extent.y * 0.72, z + extent.z * 0.22), text_rot, 74, unreal.Color(245, 196, 55, 255)))
    return [label(item) for item in markers if item]


def main():
    cleanup_temp()
    cesium_changes = configure_cesium_for_capture()
    hidden = hide_irrelevant_for_peloton()
    peloton = find_peloton_actor()
    if not peloton:
        raise RuntimeError("No peloton actor found")
    applied = stage_peloton(peloton)
    origin, extent = get_actor_bounds(peloton)
    center = origin

    # Aerial/oblique view: visibly inside Unreal terrain with current riders only.
    peloton_camera = unreal.Vector(center.x - max(900.0, extent.x * 2.0), center.y - max(900.0, extent.y * 1.8), center.z + 900.0)
    peloton_target = unreal.Vector(center.x, center.y, center.z + 80.0)
    peloton_capture = capture_scene("paper_unreal_peloton_scene", peloton_camera, peloton_target, fov=38.0, post_label="Peloton rendered in Unreal")

    marker_names = spawn_yolo_markers(peloton)
    # UAV/front-camera view: the detection overlay is geometry in the Unreal scene.
    yolo_camera = unreal.Vector(center.x - max(1400.0, extent.x * 2.8), center.y + max(1200.0, extent.y * 2.2), center.z + 520.0)
    yolo_target = unreal.Vector(center.x + extent.x * 0.10, center.y, center.z + 130.0)
    yolo_capture = capture_scene("paper_unreal_yolo_detection_scene", yolo_camera, yolo_target, fov=34.0, post_label="YOLO markers rendered as Unreal scene geometry")

    print(json.dumps(
        {
            "ok": True,
            "peloton": {
                "label": label(peloton),
                "class": str(peloton.get_class().get_name()),
                "bounds_origin": vec(origin),
                "bounds_extent": vec(extent),
                "applied": applied,
            },
            "hidden_actor_changes": hidden[:20],
            "cesium_profile": CESIUM_PAPER_PROFILE,
            "cesium_changes": cesium_changes,
            "markers": marker_names,
            "captures": [peloton_capture, yolo_capture],
        },
        indent=2,
    ))


try:
    main()
except Exception:
    print(json.dumps({"ok": False, "traceback": traceback.format_exc()}, indent=2))
    raise
finally:
    cleanup_temp()
    maybe_quit_editor()
