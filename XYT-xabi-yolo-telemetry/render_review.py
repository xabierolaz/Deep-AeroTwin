from pathlib import Path
import math

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_visual_review"
NAMES = ["cow", "biker", "tree", "car", "truck", "bush", "tractor"]


def read_mtl(path):
    colors = {}
    current = None
    if not path.exists():
        return colors
    for line in path.read_text(encoding="ascii", errors="ignore").splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "newmtl":
            current = parts[1]
        elif parts[0] == "Kd" and current:
            colors[current] = tuple(
                int(max(0.0, min(1.0, float(v))) * 255) for v in parts[1:4]
            )
    return colors


def read_obj(path):
    vertices = []
    faces = []
    material = "gray"
    for line in path.read_text(encoding="ascii", errors="ignore").splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "v":
            vertices.append(tuple(float(v) for v in parts[1:4]))
        elif parts[0] == "usemtl":
            material = parts[1]
        elif parts[0] == "f":
            faces.append(([int(p.split("/")[0]) - 1 for p in parts[1:]], material))
    return vertices, faces


def shade(color, amount):
    return tuple(int(max(0, min(255, c * amount))) for c in color)


def render(obj_path, size=720):
    colors = read_mtl(obj_path.with_suffix(".mtl"))
    vertices, faces = read_obj(obj_path)
    angle = math.radians(35)
    elevation = math.radians(24)
    ca, sa = math.cos(angle), math.sin(angle)
    ce, se = math.cos(elevation), math.sin(elevation)

    projected = []
    depths = []
    for x, y, z in vertices:
        xr = ca * x - sa * y
        yr = sa * x + ca * y
        y2 = ce * yr - se * z
        z2 = se * yr + ce * z
        projected.append((xr, y2))
        depths.append(z2)

    xs = [p[0] for p in projected]
    ys = [p[1] for p in projected]
    pad = 60
    scale = min(
        (size - 2 * pad) / max(1e-6, max(xs) - min(xs)),
        (size - 2 * pad) / max(1e-6, max(ys) - min(ys)),
    )
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    points = [((x - cx) * scale + size / 2, (y - cy) * scale + size / 2) for x, y in projected]

    image = Image.new("RGB", (size, size), (245, 246, 248))
    draw = ImageDraw.Draw(image)
    ordered = sorted(faces, key=lambda f: sum(depths[i] for i in f[0]) / len(f[0]))
    min_depth, max_depth = min(depths), max(depths)
    for indices, material in ordered:
        poly = [points[i] for i in indices]
        base = colors.get(material, (150, 150, 150))
        avg_depth = sum(depths[i] for i in indices) / len(indices)
        amount = 0.78 + 0.28 * ((avg_depth - min_depth) / max(1e-6, max_depth - min_depth))
        draw.polygon(poly, fill=shade(base, amount), outline=(35, 35, 35))
    draw.text((16, 16), obj_path.stem, fill=(0, 0, 0))
    return image


def main():
    OUT.mkdir(exist_ok=True)
    thumbs = []
    for name in NAMES:
        image = render(ROOT / f"{name}.obj")
        image.save(OUT / f"{name}.png")
        thumbs.append(image.resize((360, 360)))

    sheet = Image.new("RGB", (360 * 4, 360 * 2), (255, 255, 255))
    for index, image in enumerate(thumbs):
        sheet.paste(image, ((index % 4) * 360, (index // 4) * 360))
    sheet.save(OUT / "contact_sheet.png")
    print(OUT / "contact_sheet.png")


if __name__ == "__main__":
    main()
