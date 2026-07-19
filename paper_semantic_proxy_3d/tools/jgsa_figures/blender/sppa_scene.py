"""Shared Blender scene helpers for the JGSA Grupo A figures.

Imported by the render scripts in this directory (blender -b -P script.py).
Builds primitives from tools/jgsa_figures/assets/blender_assets.json with a
fixed role->color Okabe-Ito palette, soft Eevee lighting and a coherent 3/4
camera.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

TOOLS_DIR = Path(__file__).resolve().parent.parent
ASSETS = TOOLS_DIR / "assets"


def load_assets() -> dict:
    return json.loads((ASSETS / "blender_assets.json").read_text(encoding="utf-8"))


def hex_to_rgba(hexcolor: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    h = hexcolor.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, alpha)


def clean_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            datablocks.remove(block)


def make_material(name: str, hexcolor: str, roughness: float = 0.55,
                  alpha: float = 1.0) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = hex_to_rgba(hexcolor)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = 0.0
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.surface_render_method = "DITHERED"
    return mat


def add_primitive(prim: dict, materials: dict[str, bpy.types.Material]) -> bpy.types.Object:
    kind = prim["type"]
    cx, cy, cz = (float(v) for v in prim["center"])
    sx, sy, sz = (float(v) for v in prim["size"])
    axis = prim.get("axis", "z")
    if kind == "box":
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, cz))
        obj = bpy.context.object
        obj.scale = (sx, sy, sz)
        bevel = obj.modifiers.new("edge_soft", "BEVEL")
        bevel.width = min(0.025, 0.04 * min(sx, sy, sz))
        bevel.segments = 2
    elif kind == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.5, depth=1.0,
                                            location=(cx, cy, cz))
        obj = bpy.context.object
        if axis == "x":
            obj.rotation_euler = (0.0, math.pi / 2, 0.0)
            obj.scale = (sz, sy, sx)
        elif axis == "y":
            obj.rotation_euler = (math.pi / 2, 0.0, 0.0)
            obj.scale = (sx, sz, sy)
        else:
            obj.scale = (sx, sy, sz)
        bevel = obj.modifiers.new("edge_soft", "BEVEL")
        bevel.width = min(0.02, 0.05 * min(sx, sy, sz))
        bevel.segments = 2
        for poly in obj.data.polygons:
            poly.use_smooth = True
    elif kind == "ellipsoid":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.5,
                                             location=(cx, cy, cz))
        obj = bpy.context.object
        obj.scale = (sx, sy, sz)
        for poly in obj.data.polygons:
            poly.use_smooth = True
    else:
        raise ValueError(kind)
    obj.data.materials.append(materials[prim["category"]])
    return obj


def add_actor(actor: list[dict], materials: dict[str, bpy.types.Material]) -> list[bpy.types.Object]:
    return [add_primitive(p, materials) for p in actor]


def add_gt_mesh(obj_path: Path, material: bpy.types.Material) -> bpy.types.Object:
    verts, faces = [], []
    with obj_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("v "):
                _, x, y, z = line.split()
                verts.append((float(x), float(y), float(z)))
            elif line.startswith("f "):
                parts = [int(t.split("/")[0]) for t in line.split()[1:]]
                faces.append(tuple(p - 1 for p in parts))
    mesh = bpy.data.meshes.new("gt_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("gt_mesh", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    # flat shading keeps the 64^3 voxel structure of the GT evaluation grid
    return obj


def scene_bbox(objects: list[bpy.types.Object]) -> tuple[Vector, float]:
    """Center and half-diagonal of the evaluated world bbox of objects."""
    import numpy as np  # bundled with Blender
    mins = np.full(3, np.inf)
    maxs = np.full(3, -np.inf)
    for obj in objects:
        for corner in obj.bound_box:
            w = obj.matrix_world @ Vector(corner)
            mins = np.minimum(mins, np.array(w))
            maxs = np.maximum(maxs, np.array(w))
    center = Vector(((mins + maxs) / 2).tolist())
    radius = float(np.linalg.norm(maxs - mins)) / 2.0
    return center, max(radius, 1e-3)


def add_camera(center: Vector, radius: float, azimuth_deg: float = -58.0,
               elevation_deg: float = 24.0, margin: float = 1.28) -> bpy.types.Object:
    az, el = math.radians(azimuth_deg), math.radians(elevation_deg)
    direction = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
    distance = margin * radius / math.sin(math.radians(39.6) / 2)  # 52 mm lens vertical fov
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 52.0
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = center + direction * distance
    look = center - cam.location
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def add_light(name: str, location: tuple[float, float, float], energy: float,
              size: float) -> bpy.types.Object:
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (math.radians(20), math.radians(15), math.radians(-30))
    return obj


def setup_lighting(center: Vector, radius: float) -> None:
    d = max(4.0 * radius, 8.0)
    key = add_light("key", (center.x + 0.6 * d, center.y - 0.75 * d, center.z + 0.9 * d), 900, 5.0)
    key.rotation_euler = (math.radians(28), math.radians(24), math.radians(35))
    fill = add_light("fill", (center.x - 0.8 * d, center.y - 0.3 * d, center.z + 0.45 * d), 380, 4.0)
    fill.rotation_euler = (math.radians(55), math.radians(-10), math.radians(120))
    rim = add_light("rim", (center.x - 0.25 * d, center.y + 0.85 * d, center.z + 0.8 * d), 650, 3.5)
    rim.rotation_euler = (math.radians(-15), math.radians(140), math.radians(200))


def setup_ground(z: float = 0.0) -> bpy.types.Object:
    bpy.ops.mesh.primitive_plane_add(size=200.0, location=(0.0, 0.0, z - 0.005))
    plane = bpy.context.object
    mat = make_material("ground", "#FFFFFF", roughness=0.96)
    plane.data.materials.append(mat)
    return plane


def setup_render(width: int, height: int) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.image_settings.color_depth = "8"
    world = bpy.data.worlds.new("white_world") if not scene.world else scene.world
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    bg.inputs["Strength"].default_value = 0.4
    # faithful palette reproduction: Standard view transform keeps the
    # Okabe-Ito base colors recognizable (AgX washes them out)
    try:
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "Medium High Contrast"
    except TypeError:
        try:
            scene.view_settings.look = "None"
        except TypeError:
            pass


def render_to(path: Path) -> None:
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print("rendered", path)


def role_materials(assets: dict) -> dict[str, bpy.types.Material]:
    return {cat: make_material(f"role_{i}", color)
            for i, (cat, color) in enumerate(assets["role_categories"].items())}
