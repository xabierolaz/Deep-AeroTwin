import argparse
import math
import os
import re


MATERIALS = {
    "brown": (0.45, 0.25, 0.10),
    "dark_brown": (0.20, 0.10, 0.04),
    "cream": (0.85, 0.75, 0.55),
    "black": (0.02, 0.02, 0.02),
    "white": (0.92, 0.92, 0.86),
    "green": (0.10, 0.55, 0.16),
    "dark_green": (0.03, 0.35, 0.09),
    "red": (0.70, 0.05, 0.04),
    "blue": (0.05, 0.18, 0.75),
    "gray": (0.45, 0.45, 0.45),
    "metal": (0.62, 0.62, 0.60),
    "glass": (0.35, 0.70, 0.95),
    "yellow": (0.95, 0.72, 0.06),
}


class Mesh:
    def __init__(self):
        self.vertices = []
        self.faces = []

    def add_vertex(self, x, y, z):
        self.vertices.append((x, y, z))
        return len(self.vertices)

    def add_face(self, indices, material):
        self.faces.append((indices, material))

    def box(self, center, size, material):
        cx, cy, cz = center
        sx, sy, sz = (v / 2 for v in size)
        corners = [
            (cx - sx, cy - sy, cz - sz), (cx + sx, cy - sy, cz - sz),
            (cx + sx, cy + sy, cz - sz), (cx - sx, cy + sy, cz - sz),
            (cx - sx, cy - sy, cz + sz), (cx + sx, cy - sy, cz + sz),
            (cx + sx, cy + sy, cz + sz), (cx - sx, cy + sy, cz + sz),
        ]
        ids = [self.add_vertex(*p) for p in corners]
        for face in [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
                     (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]:
            self.add_face([ids[i] for i in face], material)

    def sphere(self, center, scale, material, rings=6, segments=10):
        cx, cy, cz = center
        sx, sy, sz = scale
        grid = []
        for r in range(rings + 1):
            phi = math.pi * r / rings
            row = []
            for s in range(segments):
                theta = 2 * math.pi * s / segments
                x = cx + sx * math.sin(phi) * math.cos(theta)
                y = cy + sy * math.sin(phi) * math.sin(theta)
                z = cz + sz * math.cos(phi)
                row.append(self.add_vertex(x, y, z))
            grid.append(row)
        for r in range(rings):
            for s in range(segments):
                a = grid[r][s]
                b = grid[r][(s + 1) % segments]
                c = grid[r + 1][(s + 1) % segments]
                d = grid[r + 1][s]
                self.add_face([a, b, c, d], material)

    def cylinder(self, center, radius, depth, material, axis="z", segments=10):
        cx, cy, cz = center
        half = depth / 2
        a_ring, b_ring = [], []
        for s in range(segments):
            theta = 2 * math.pi * s / segments
            u = radius * math.cos(theta)
            v = radius * math.sin(theta)
            if axis == "x":
                a = (cx - half, cy + u, cz + v)
                b = (cx + half, cy + u, cz + v)
            elif axis == "y":
                a = (cx + u, cy - half, cz + v)
                b = (cx + u, cy + half, cz + v)
            else:
                a = (cx + u, cy + v, cz - half)
                b = (cx + u, cy + v, cz + half)
            a_ring.append(self.add_vertex(*a))
            b_ring.append(self.add_vertex(*b))
        for s in range(segments):
            self.add_face(
                [a_ring[s], a_ring[(s + 1) % segments],
                 b_ring[(s + 1) % segments], b_ring[s]],
                material,
            )
        self.add_face(list(reversed(a_ring)), material)
        self.add_face(b_ring, material)

    def cone(self, center, radius, depth, material, axis="z", segments=10):
        cx, cy, cz = center
        half = depth / 2
        base = []
        for s in range(segments):
            theta = 2 * math.pi * s / segments
            u = radius * math.cos(theta)
            v = radius * math.sin(theta)
            if axis == "x":
                p = (cx - half, cy + u, cz + v)
                tip = (cx + half, cy, cz)
            elif axis == "y":
                p = (cx + u, cy - half, cz + v)
                tip = (cx, cy + half, cz)
            else:
                p = (cx + u, cy + v, cz - half)
                tip = (cx, cy, cz + half)
            base.append(self.add_vertex(*p))
        tip_id = self.add_vertex(*tip)
        self.add_face(list(reversed(base)), material)
        for s in range(segments):
            self.add_face([base[s], base[(s + 1) % segments], tip_id], material)

    def torus(self, center, major, minor, material, axis="x", major_steps=14, minor_steps=6):
        cx, cy, cz = center
        grid = []
        for i in range(major_steps):
            theta = 2 * math.pi * i / major_steps
            row = []
            for j in range(minor_steps):
                phi = 2 * math.pi * j / minor_steps
                r = major + minor * math.cos(phi)
                if axis == "x":
                    x = cx + minor * math.sin(phi)
                    y = cy + r * math.cos(theta)
                    z = cz + r * math.sin(theta)
                else:
                    x = cx + r * math.cos(theta)
                    y = cy + minor * math.sin(phi)
                    z = cz + r * math.sin(theta)
                row.append(self.add_vertex(x, y, z))
            grid.append(row)
        for i in range(major_steps):
            for j in range(minor_steps):
                self.add_face([
                    grid[i][j],
                    grid[(i + 1) % major_steps][j],
                    grid[(i + 1) % major_steps][(j + 1) % minor_steps],
                    grid[i][(j + 1) % minor_steps],
                ], material)


def cow(mesh):
    mesh.sphere((0, 0, 1.3), (1.35, 0.55, 0.55), "white")
    mesh.sphere((-0.35, -0.15, 1.45), (0.35, 0.18, 0.18), "black")
    mesh.sphere((0.45, 0.18, 1.2), (0.32, 0.16, 0.16), "black")
    mesh.sphere((-0.75, 0.18, 1.55), (0.28, 0.14, 0.16), "black")
    mesh.sphere((0.15, -0.32, 1.42), (0.30, 0.12, 0.18), "black")
    mesh.sphere((1.55, 0, 1.35), (0.45, 0.35, 0.32), "white")
    mesh.sphere((1.95, 0, 1.25), (0.25, 0.25, 0.18), "cream")
    for y in (-0.36, 0.36):
        mesh.cone((1.45, y, 1.75), 0.08, 0.35, "cream", axis="y")
    for x in (-0.75, 0.75):
        for y in (-0.34, 0.34):
            mesh.cylinder((x, y, 0.65), 0.10, 1.05, "dark_brown", axis="z")
    mesh.cylinder((-1.45, 0, 1.25), 0.035, 0.8, "dark_brown", axis="x")


def tree(mesh):
    mesh.cylinder((0, 0, 0.75), 0.20, 1.5, "brown", segments=12)
    mesh.sphere((0, 0, 2.05), (0.85, 0.75, 0.65), "dark_green", rings=6, segments=12)
    mesh.sphere((-0.42, 0.10, 2.32), (0.52, 0.45, 0.42), "green", rings=5, segments=10)
    mesh.sphere((0.42, -0.10, 2.30), (0.52, 0.45, 0.42), "green", rings=5, segments=10)
    mesh.sphere((0, 0, 2.72), (0.48, 0.42, 0.40), "dark_green", rings=5, segments=10)

def bush(mesh):
    mesh.sphere((0, 0, 0.65), (0.85, 0.65, 0.45), 'dark_green', rings=5, segments=10)
    mesh.sphere((-0.55, 0.05, 0.72), (0.55, 0.45, 0.38), 'green', rings=5, segments=10)
    mesh.sphere((0.55, -0.05, 0.72), (0.55, 0.45, 0.38), 'green', rings=5, segments=10)
    mesh.sphere((0.0, 0.28, 0.92), (0.55, 0.42, 0.36), 'dark_green', rings=5, segments=10)
    mesh.cylinder((0, 0, 0.25), 0.12, 0.5, 'brown', segments=8)


def car(mesh):
    mesh.box((0, 0, 0.75), (2.4, 1.05, 0.55), "red")
    mesh.box((-0.25, 0, 1.18), (1.1, 0.85, 0.48), "red")
    mesh.box((-0.25, -0.43, 1.22), (0.78, 0.04, 0.25), "glass")
    mesh.box((-0.25, 0.43, 1.22), (0.78, 0.04, 0.25), "glass")
    for x in (-0.75, 0.75):
        for y in (-0.58, 0.58):
            mesh.torus((x, y, 0.45), 0.24, 0.07, "black", axis="y")
            mesh.cylinder((x, y, 0.45), 0.13, 0.08, "metal", axis="y")


def truck(mesh):
    mesh.box((-0.55, 0, 0.95), (2.5, 1.1, 0.9), "gray")
    mesh.box((1.15, 0, 0.85), (1.0, 1.05, 0.75), "blue")
    mesh.box((1.33, -0.53, 1.1), (0.42, 0.04, 0.28), "glass")
    for x in (-1.35, -0.35, 0.85, 1.45):
        for y in (-0.62, 0.62):
            mesh.torus((x, y, 0.42), 0.24, 0.07, "black", axis="y")
            mesh.cylinder((x, y, 0.42), 0.13, 0.08, "metal", axis="y")


def tractor(mesh):
    mesh.box((-0.15, 0, 0.85), (1.45, 1.0, 0.65), 'green')
    mesh.box((0.85, 0, 1.18), (0.72, 0.85, 0.8), 'green')
    mesh.box((0.92, -0.43, 1.28), (0.42, 0.04, 0.32), 'glass')
    mesh.box((0.92, 0.43, 1.28), (0.42, 0.04, 0.32), 'glass')
    mesh.box((-1.05, 0, 1.05), (0.65, 0.75, 0.45), 'yellow')
    for y in (-0.58, 0.58):
        mesh.torus((-0.75, y, 0.58), 0.40, 0.10, 'black', axis='y', major_steps=16, minor_steps=6)
        mesh.cylinder((-0.75, y, 0.58), 0.18, 0.10, 'yellow', axis='y')
        mesh.torus((0.85, y, 0.48), 0.28, 0.08, 'black', axis='y', major_steps=14, minor_steps=6)
        mesh.cylinder((0.85, y, 0.48), 0.12, 0.08, 'yellow', axis='y')
    mesh.cylinder((-0.2, 0, 1.45), 0.07, 0.75, 'black', axis='z')


def biker(mesh):
    for x in (-0.85, 0.85):
        mesh.torus((x, 0, 0.55), 0.38, 0.045, "black", axis="y")
        mesh.cylinder((x, 0, 0.55), 0.08, 0.08, "metal", axis="y")
    mesh.cylinder((0, 0, 0.78), 0.035, 1.25, "yellow", axis="x")
    mesh.cylinder((-0.45, 0, 0.95), 0.035, 0.95, "yellow", axis="x")
    mesh.cylinder((0.45, 0, 0.95), 0.035, 0.95, "yellow", axis="x")
    mesh.cylinder((0.0, 0, 1.0), 0.04, 0.75, "metal", axis="z")
    mesh.sphere((0.0, 0, 1.65), (0.28, 0.20, 0.45), "blue")
    mesh.sphere((0.12, 0, 2.12), (0.18, 0.18, 0.18), "cream")
    mesh.cylinder((-0.18, 0, 1.28), 0.045, 0.82, "cream", axis="z")
    mesh.cylinder((0.35, 0, 1.25), 0.045, 0.82, "cream", axis="z")
    mesh.cylinder((0.35, 0, 1.72), 0.04, 0.72, "cream", axis="x")


BUILDERS = {
    "cow": cow,
    "vaca": cow,
    "biker": biker,
    "cyclist": biker,
    "ciclista": biker,
    "tree": tree,
    "arbol": tree,
    "bush": bush,
    "arbusto": bush,
    "car": car,
    "coche": car,
    "truck": truck,
    "camion": truck,
    "tractor": tractor,
}


def safe_name(text):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", text.strip()).strip("_") or "model"


def write_obj(mesh, obj_path, mtl_name):
    with open(obj_path, "w", encoding="ascii") as f:
        f.write(f"mtllib {mtl_name}\n")
        f.write("o XYT_generated\n")
        for v in mesh.vertices:
            f.write(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}\n")
        current = None
        for indices, material in mesh.faces:
            if material != current:
                current = material
                f.write(f"usemtl {material}\n")
            f.write("f " + " ".join(str(i) for i in indices) + "\n")


def write_mtl(mtl_path):
    with open(mtl_path, "w", encoding="ascii") as f:
        for name, rgb in MATERIALS.items():
            f.write(f"newmtl {name}\n")
            f.write(f"Kd {rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f}\n")
            f.write("Ka 0.050 0.050 0.050\n")
            f.write("Ks 0.120 0.120 0.120\n\n")


def main():
    parser = argparse.ArgumentParser(description="XYT instant primitive 3D generator")
    parser.add_argument("word", help="cow, biker, tree, car, truck")
    parser.add_argument("--out-dir", default=".")
    args = parser.parse_args()

    key = args.word.strip().lower()
    builder = BUILDERS.get(key)
    if builder is None:
        known = ", ".join(sorted(set(BUILDERS)))
        raise SystemExit(f"Palabra no soportada: {args.word}. Usa: {known}")

    os.makedirs(args.out_dir, exist_ok=True)
    name = safe_name(args.word)
    obj_path = os.path.join(args.out_dir, f"{name}.obj")
    mtl_path = os.path.join(args.out_dir, f"{name}.mtl")

    mesh = Mesh()
    builder(mesh)
    write_mtl(mtl_path)
    write_obj(mesh, obj_path, os.path.basename(mtl_path))
    print(f"Generado: {obj_path}")
    print(f"Materiales: {mtl_path}")


if __name__ == "__main__":
    main()
