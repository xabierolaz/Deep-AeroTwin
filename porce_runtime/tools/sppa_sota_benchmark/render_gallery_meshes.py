# -*- coding: utf-8 -*-
"""Gallery software renderer: consistent-camera PNG renders for every
(case, method) mesh of the 20260722 generator gallery.

Painter's algorithm (no GL), trimesh for OBJ/GLB/PLY loading, vertex colors
when present, Lambert shading otherwise. White background, isotropic fit,
fixed view (azimuth 35 deg, elevation 25 deg) identical for all methods.

Run with the triposr venv python (has trimesh + PIL + numpy).
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw

ROOT = Path(r"D:\Deep-AeroTwin-UE57-Test")
RUN = ROOT / "experiments/sppa_sota_benchmark/runs/20260722_generator_gallery"
SIZE = 512
MARGIN = 0.06  # fraction of canvas
AZIMUTH_DEG = 35.0
ELEVATION_DEG = 25.0
LIGHT_DIR = np.array([0.4, 0.8, 0.45], dtype=np.float64)
LIGHT_DIR /= np.linalg.norm(LIGHT_DIR)

CASES = ["tower", "tractor", "biker", "cow", "car", "tractor_trailer"]
METHODS = {
    "triposr_warm_r128_6gb": ["obj"],
    "shap_e_image_k64_6gb": ["obj"],
    "point_e_image_sdf32_6gb": ["ply"],
    "hunyuan3d_2mini_turbo_rgba_6gb": ["glb"],
}


def load_mesh(path: Path):
    loaded = trimesh.load(path, force="scene", process=False)
    geoms = list(getattr(loaded, "geometry", {}).values())
    if not geoms and hasattr(loaded, "vertices"):
        geoms = [loaded]
    if not geoms:
        raise RuntimeError(f"no geometry in {path}")
    verts_list, faces_list, colors_list = [], [], []
    offset = 0
    for g in geoms:
        v = np.asarray(g.vertices, dtype=np.float64)
        f = np.asarray(g.faces, dtype=np.int64)
        # per-face color from visuals, fallback None
        fc = None
        try:
            vis = g.visual
            if hasattr(vis, "vertex_colors") and len(vis.vertex_colors) == len(v):
                vc = np.asarray(vis.vertex_colors, dtype=np.float64)[:, :3]
                fc = vc[f].mean(axis=1)
            elif hasattr(vis, "face_colors") and len(vis.face_colors) == len(f):
                fc = np.asarray(vis.face_colors, dtype=np.float64)[:, :3]
        except Exception:
            fc = None
        verts_list.append(v)
        faces_list.append(f + offset)
        if fc is not None:
            colors_list.append(fc)
        offset += len(v)
    verts = np.vstack(verts_list)
    faces = np.vstack(faces_list)
    face_colors = None
    if colors_list and len(colors_list) == len(verts_list):
        face_colors = np.vstack(colors_list)
        if face_colors.max() <= 1.0:
            face_colors = face_colors * 255.0
    return verts, faces, face_colors


def rotation_matrix() -> np.ndarray:
    az = math.radians(AZIMUTH_DEG)
    el = math.radians(ELEVATION_DEG)
    rz = np.array(
        [
            [math.cos(az), -math.sin(az), 0.0],
            [math.sin(az), math.cos(az), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    rx = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, math.cos(el), -math.sin(el)],
            [0.0, math.sin(el), math.cos(el)],
        ]
    )
    # view: rotate about Z (azimuth) then tilt about X (elevation); camera looks down -Z
    return rx @ rz


def render(verts: np.ndarray, faces: np.ndarray, face_colors) -> Image.Image:
    # normalize: center, isotropic scale to unit extent
    center = (verts.max(axis=0) + verts.min(axis=0)) / 2.0
    verts = verts - center
    scale = np.abs(verts).max()
    if scale <= 0:
        raise RuntimeError("degenerate mesh extent")
    verts = verts / scale

    verts = verts @ rotation_matrix().T
    tri = verts[faces]  # [F,3,3]
    depth = tri[:, :, 2].mean(axis=1)
    order = np.argsort(depth)  # far first -> near last

    # screen projection (orthographic): x right, y up -> image y down
    half = SIZE * (0.5 - MARGIN)
    sx = tri[:, :, 0] * half + SIZE / 2.0
    sy = -tri[:, :, 1] * half + SIZE / 2.0

    # face normals for lambert
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    nlen = np.linalg.norm(n, axis=1)
    nlen[nlen == 0] = 1.0
    n = n / nlen[:, None]
    # light in view space
    lv = rotation_matrix() @ LIGHT_DIR
    lambert = np.abs(n @ lv)
    shade = 0.35 + 0.65 * lambert

    if face_colors is not None:
        base = face_colors.astype(np.float64)
    else:
        base = np.full((len(faces), 3), 175.0)
    colors = np.clip(base * shade[:, None] * (0.75 if face_colors is not None else 1.0), 0, 255)
    if face_colors is not None:
        # mild ambient lift so vertex-colored meshes don't go too dark
        colors = np.clip(base * (0.55 + 0.45 * lambert[:, None]), 0, 255)

    img = Image.new("RGB", (SIZE, SIZE), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    for fi in order:
        poly = [(float(sx[fi, k]), float(sy[fi, k])) for k in range(3)]
        c = colors[fi]
        draw.polygon(poly, fill=(int(c[0]), int(c[1]), int(c[2])))
    return img


def main() -> None:
    rows = []
    for method, exts in METHODS.items():
        for case in CASES:
            case_dir = RUN / "outputs" / method / case
            mesh_path = None
            for ext in exts:
                cand = case_dir / f"{case}.{ext}"
                if cand.exists():
                    mesh_path = cand
                    break
            row = {"method": method, "case": case}
            if mesh_path is None:
                row.update({"status": "no_mesh", "render_path": None})
                rows.append(row)
                print(f"SKIP {method}/{case}: no mesh", flush=True)
                continue
            start = time.perf_counter()
            try:
                verts, faces, face_colors = load_mesh(mesh_path)
                img = render(verts, faces, face_colors)
                render_path = case_dir / f"{case}_render.png"
                img.save(render_path)
                row.update(
                    {
                        "status": "ok",
                        "render_path": str(render_path.relative_to(ROOT)).replace("\\", "/"),
                        "render_sec": time.perf_counter() - start,
                        "faces": int(len(faces)),
                        "colored": bool(face_colors is not None),
                    }
                )
                print(f"OK   {method}/{case}: {len(faces)} faces", flush=True)
            except Exception as exc:
                row.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
                print(f"ERR  {method}/{case}: {exc}", flush=True)
            rows.append(row)
    out = RUN / "renders_index.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    sys.exit(main())
