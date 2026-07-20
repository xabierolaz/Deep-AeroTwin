"""Render one role-colored SPPA proxy (lattice_tower) from the frozen graphs.json.
Run: blender --background --python render_sppa_proxy_fig.py
Output: figures/assets/proxy_lattice_tower.png (640x640, transparent)
"""
import bpy, json, math, os
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
GRAPHS = os.path.join(ROOT, "reproducibility", "sppa_mvfit", "method", "graphs.json")
OUT = os.path.join(ROOT, "figures", "assets", "proxy_lattice_tower.png")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

slots = [s for s in json.load(open(GRAPHS))["graphs"]["lattice_tower"]]
ROLE_COLORS = {
    "primary":   (0.78, 0.20, 0.16),   # spine / load-bearing column
    "secondary": (0.16, 0.45, 0.75),   # legs
    "platform":  (0.95, 0.62, 0.10),   # platforms
}

def mat(rgb):
    m = bpy.data.materials.new("role")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = 0.55
    return m

mats = {k: mat(v) for k, v in ROLE_COLORS.items()}
platform_i = 0
for s in slots:
    cx, cy, cz = s["center"]
    sx, sy, sz = s["size"]
    if s["type"] == "box":
        bpy.ops.mesh.primitive_cube_add(location=(cx, cy, cz))
        o = bpy.context.object
        o.scale = (sx / 2, sy / 2, sz / 2)
    else:  # cylinder
        bpy.ops.mesh.primitive_cylinder_add(radius=sx / 2 if sx == sy else (sx + sy) / 4,
                                            depth=sz, location=(cx, cy, cz))
        o = bpy.context.object
    if not s["secondary"]:
        role = "primary"
    elif s["type"] == "box" and sz < 0.3:
        role = "platform"
    else:
        role = "secondary"
    o.data.materials.append(mats[role])

# floor disc for grounding
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
pl = bpy.context.object
pm = bpy.data.materials.new("floor"); pm.use_nodes = True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.92, 0.92, 0.92, 1)
pl.data.materials.append(pm)

bpy.ops.object.light_add(type="SUN", location=(5, -5, 10))
bpy.context.object.data.energy = 2.2
bpy.context.object.rotation_euler = (math.radians(35), math.radians(15), 0)
world = bpy.data.worlds.new("W"); scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.7

bpy.ops.object.camera_add(location=(6.8, -6.8, 5.4))
cam = bpy.context.object
cam.rotation_euler = (Vector((0, 0, 2.5)) - cam.location).to_track_quat("-Z", "Y").to_euler()
cam.data.angle = math.radians(55)
scene.camera = cam

scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.render.resolution_x = scene.render.resolution_y = 640
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = True
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("PROXY_RENDER_SAVED", OUT)
