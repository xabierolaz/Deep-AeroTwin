from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.collections import PolyCollection
from PIL import Image, ImageDraw, ImageFont

from bench_common import ROOT, read_objects, write_csv

VIEW_SPECS = {
    "front": ((0, 2), 1, np.array([0.0, -1.0, 0.0])),
    "side": ((1, 2), 0, np.array([-1.0, 0.0, 0.0])),
    "top": ((0, 1), 2, np.array([0.0, 0.0, 1.0])),
}


def load_as_mesh(path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(path, force="scene", process=False)
    if isinstance(loaded, trimesh.Scene):
        mesh = loaded.to_geometry() if hasattr(loaded, "to_geometry") else loaded.dump(concatenate=True)
    elif isinstance(loaded, trimesh.Trimesh):
        mesh = loaded
    else:
        raise TypeError(f"Unsupported mesh type: {type(loaded).__name__}")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.vertices) == 0 or len(mesh.faces) == 0:
        raise ValueError("empty mesh")
    mesh = mesh.copy()
    mesh.remove_unreferenced_vertices()
    return mesh




def read_obj_material_colors(path: Path) -> tuple[dict[str, np.ndarray], list[str]]:
    material_colors: dict[str, np.ndarray] = {}
    face_materials: list[str] = []
    current_material = ""
    mtl_path = None
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("mtllib "):
                    candidate = line.split(maxsplit=1)[1].strip()
                    mtl_path = path.parent / candidate
                elif line.startswith("usemtl "):
                    current_material = line.split(maxsplit=1)[1].strip()
                elif line.startswith("f "):
                    vertex_count = max(0, len(line.split()) - 1)
                    triangle_count = max(1, vertex_count - 2)
                    face_materials.extend([current_material] * triangle_count)
    except OSError:
        return material_colors, face_materials

    if mtl_path is not None and mtl_path.exists():
        current = ""
        with mtl_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("newmtl "):
                    current = line.split(maxsplit=1)[1].strip()
                elif current and line.startswith("Kd "):
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            material_colors[current] = np.array([float(parts[1]), float(parts[2]), float(parts[3])])
                        except ValueError:
                            pass
    return material_colors, face_materials


def material_manifest_metadata(path: Path) -> dict[str, dict]:
    manifest_path = path.with_suffix(".materials.json")
    if not manifest_path.exists():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(item.get("name", "")): item for item in data.get("materials", []) if item.get("name")}


def apply_manifest_style(color: np.ndarray, metadata: dict | None) -> np.ndarray:
    if not metadata:
        return color
    style = str(metadata.get("uncertainty_visual_style", "none"))
    evidence = str(metadata.get("evidence_source", ""))
    adjusted = np.array(metadata.get("rgb", color), dtype=np.float64)
    if style in {"low_confidence_desaturation", "desaturated_unknown"} or evidence == "fallback_unknown":
        gray = float(adjusted.mean())
        adjusted = 0.35 * adjusted + 0.65 * gray
    if style == "warning_marker":
        adjusted = np.array([1.0, 0.64, 0.05], dtype=np.float64)
    return np.clip(adjusted, 0.0, 1.0)


def face_colors_from_materials(path: Path, face_count: int) -> np.ndarray | None:
    if path.suffix.lower() != ".obj":
        return None
    material_colors, face_materials = read_obj_material_colors(path)
    manifest_metadata = material_manifest_metadata(path)
    if not material_colors and not manifest_metadata:
        return None
    if not face_materials:
        return None
    colors = []
    fallback = np.array([0.27, 0.42, 0.58])
    for material in face_materials[:face_count]:
        base = material_colors.get(material, fallback)
        colors.append(apply_manifest_style(base, manifest_metadata.get(material)))
    if len(colors) < face_count:
        colors.extend([fallback] * (face_count - len(colors)))
    return np.asarray(colors, dtype=np.float64)


def normalize_vertices(vertices: np.ndarray) -> np.ndarray:
    vertices = np.asarray(vertices, dtype=np.float64)
    center = (vertices.min(axis=0) + vertices.max(axis=0)) / 2.0
    vertices = vertices - center
    extents = vertices.max(axis=0) - vertices.min(axis=0)
    scale = float(extents.max())
    if scale <= 0:
        return vertices
    return vertices / scale


def iso_vertices(vertices: np.ndarray) -> np.ndarray:
    yaw = np.deg2rad(-35.0)
    pitch = np.deg2rad(25.0)
    rz = np.array(
        [
            [np.cos(yaw), -np.sin(yaw), 0.0],
            [np.sin(yaw), np.cos(yaw), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    rx = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, np.cos(pitch), -np.sin(pitch)],
            [0.0, np.sin(pitch), np.cos(pitch)],
        ]
    )
    return vertices @ rz.T @ rx.T


def selected_faces(mesh: trimesh.Trimesh, max_faces: int) -> np.ndarray:
    faces = np.asarray(mesh.faces)
    if len(faces) <= max_faces:
        return faces
    step = int(np.ceil(len(faces) / max_faces))
    return faces[::step]


def render_projection(
    mesh: trimesh.Trimesh,
    out_path: Path,
    view_name: str,
    max_faces: int,
    image_size: int,
    source_path: Path | None = None,
) -> tuple[int, int]:
    faces = selected_faces(mesh, max_faces=max_faces)
    vertices = normalize_vertices(mesh.vertices)
    normals = np.asarray(mesh.face_normals)
    material_colors = face_colors_from_materials(source_path, len(mesh.faces)) if source_path is not None else None
    if len(faces) != len(mesh.faces):
        face_indices = np.arange(len(mesh.faces))[:: int(np.ceil(len(mesh.faces) / max_faces))]
        normals = normals[face_indices]
        if material_colors is not None:
            material_colors = material_colors[face_indices]

    if view_name == "iso":
        projected_vertices = iso_vertices(vertices)
        axes = (0, 2)
        depth_axis = 1
        view_direction = np.array([0.35, -0.75, 0.55])
    else:
        axes, depth_axis, view_direction = VIEW_SPECS[view_name]
        projected_vertices = vertices

    polygons = projected_vertices[faces][:, :, list(axes)]
    depth = projected_vertices[faces][:, :, depth_axis].mean(axis=1)
    order = np.argsort(depth)
    polygons = polygons[order]
    normals = normals[order]
    if material_colors is not None:
        material_colors = material_colors[order]

    view_direction = view_direction / np.linalg.norm(view_direction)
    shade = 0.42 + 0.58 * np.clip(np.abs(normals @ view_direction), 0.0, 1.0)
    base = material_colors if material_colors is not None else np.array([0.27, 0.42, 0.58])[None, :]
    colors = np.clip(base * shade[:, None], 0.0, 1.0)

    fig = plt.figure(figsize=(image_size / 100, image_size / 100), dpi=100)
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
    collection = PolyCollection(polygons, facecolors=colors, edgecolors="none", linewidths=0)
    ax.add_collection(collection)
    ax.set_aspect("equal")
    ax.set_xlim(-0.6, 0.6)
    ax.set_ylim(-0.6, 0.6)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)
    return len(mesh.faces), len(faces)


def mesh_records(run_dir: Path) -> list[dict]:
    records: list[dict] = []
    for outputs_name in ("outputs", "outputs_scale"):
        outputs = run_dir / outputs_name
        if not outputs.exists():
            continue
        for path in sorted(outputs.rglob("*")):
            if path.suffix.lower() not in {".obj", ".glb", ".ply"}:
                continue
            if path.name.endswith("_points.ply"):
                continue
            label = path.parent.name
            model = path.parent.parent.name
            records.append({"model": model, "label": label, "path": path})
    return records


def open_input_images(objects_csv: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for item in read_objects(objects_csv):
        image = item.get("image_rgba") or item.get("image") or item.get("image_rgb")
        if not image:
            continue
        path = Path(image)
        if not path.is_absolute():
            path = ROOT / path
        result[item["label"]] = path
    return result


def tile_with_label(image_path: Path, label: str, size: int) -> Image.Image:
    image = Image.open(image_path).convert("RGBA")
    canvas = Image.new("RGBA", (size, size + 26), "white")
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas.alpha_composite(image, ((size - image.width) // 2, (size - image.height) // 2))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    draw.text((8, size + 6), label[:42], fill=(20, 20, 20), font=font)
    return canvas.convert("RGB")


def text_tile(label: str, size: int) -> Image.Image:
    canvas = Image.new("RGB", (size, size + 26), "white")
    draw = ImageDraw.Draw(canvas)
    try:
        title_font = ImageFont.truetype("arial.ttf", 22)
        small_font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        title_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    draw.text((12, size // 2 - 18), label[:48], fill=(20, 20, 20), font=title_font)
    draw.text((8, size + 6), "model", fill=(20, 20, 20), font=small_font)
    return canvas


def build_contact_sheets(view_dir: Path, input_images: dict[str, Path], image_size: int) -> None:
    rows_by_label: dict[str, list[tuple[str, list[Path]]]] = {}
    for model_dir in sorted((view_dir / "models").glob("*")):
        for label_dir in sorted(model_dir.glob("*")):
            label = label_dir.name
            paths = [label_dir / f"{view}.png" for view in ["front", "side", "top", "iso"]]
            if all(path.exists() for path in paths):
                rows_by_label.setdefault(label, []).append((model_dir.name, paths))

    sheets_dir = view_dir / "contact_sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)
    header = ["input", "front", "side", "top", "iso"]
    for label, rows in sorted(rows_by_label.items()):
        tiles: list[list[Image.Image]] = []
        if label in input_images:
            blank = Image.new("RGB", (image_size, image_size + 26), "white")
            input_tile = tile_with_label(input_images[label], f"input: {label}", image_size)
            tiles.append([input_tile, *[blank.copy() for _ in range(4)]])
        for model, paths in rows:
            row = [text_tile(model, image_size)]
            row.extend(tile_with_label(path, view, image_size) for path, view in zip(paths, header[1:]))
            tiles.append(row)
        width = image_size * 5
        height = (image_size + 26) * len(tiles)
        sheet = Image.new("RGB", (width, height), "white")
        for y, row in enumerate(tiles):
            for x, tile in enumerate(row):
                sheet.paste(tile, (x * image_size, y * (image_size + 26)))
        sheet.save(sheets_dir / f"{label}_views.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render orthographic mesh views for benchmark inspection.")
    parser.add_argument("--run-dir", default="experiments/sppa_sota_benchmark/runs/20260701_195624")
    parser.add_argument("--objects-csv", default="experiments/sppa_sota_benchmark/inputs/objects_rgba.csv")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--max-faces", type=int, default=80000)
    parser.add_argument("--image-size", type=int, default=512)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    objects_csv = Path(args.objects_csv)
    if not objects_csv.is_absolute():
        objects_csv = ROOT / objects_csv
    output_dir = Path(args.output_dir) if args.output_dir else run_dir / "views"
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    rows: list[dict] = []
    for record in mesh_records(run_dir):
        mesh_path = record["path"]
        model = record["model"]
        label = record["label"]
        row = {"model": model, "label": label, "mesh_path": str(mesh_path), "status": "ok"}
        try:
            mesh = load_as_mesh(mesh_path)
            for view in ["front", "side", "top", "iso"]:
                out = output_dir / "models" / model / label / f"{view}.png"
                total_faces, rendered_faces = render_projection(mesh, out, view, args.max_faces, args.image_size, source_path=mesh_path)
                row[f"{view}_png"] = str(out)
                row["faces_total"] = total_faces
                row["faces_rendered"] = rendered_faces
        except Exception as exc:
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)

    write_csv(output_dir / "rendered_views.csv", rows)
    build_contact_sheets(output_dir, open_input_images(objects_csv), args.image_size)
    print(output_dir)


if __name__ == "__main__":
    main()
