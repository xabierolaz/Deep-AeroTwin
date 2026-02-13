#!/usr/bin/env python3
"""
Synthetic dataset generator for YOLO (biker/cow/tower) from local OBJ assets.

Key properties (for drone-like views):
- "Dome" sampling: camera positions are sampled on the *upper* hemisphere only (z > 0).
- Object remains upright; we only vary yaw and lateral offset slightly.
- Heavy domain randomization: backgrounds, noise, blur, JPEG artifacts, cutout occlusions.

Output structure:
  dataset/
    images/{train,val,test}/*.jpg
    labels/{train,val,test}/*.txt   (YOLO bbox format)
"""

from __future__ import annotations

import argparse
import math
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
import pyrender
import trimesh


THIS_DIR = Path(__file__).resolve().parent
ASSETS_DIR = THIS_DIR / "assets_folder"


CLASSES: list[tuple[str, Path]] = [
    ("biker", ASSETS_DIR / "biker.obj"),
    ("cow", ASSETS_DIR / "cow.obj"),
    ("tower", ASSETS_DIR / "tower.obj"),
]


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def _ensure_clean_dirs(out_dir: Path) -> None:
    for split in ("train", "val", "test"):
        for kind in ("images", "labels"):
            p = out_dir / kind / split
            if p.exists():
                shutil.rmtree(p)
            p.mkdir(parents=True, exist_ok=True)


def _uniform_upper_hemisphere_dir(rng: np.random.Generator, min_elev_deg: float) -> np.ndarray:
    # Sample uniformly over the upper hemisphere (z > 0). To avoid degenerate grazing
    # angles, clamp to a minimum elevation above horizon.
    min_elev_deg = float(min_elev_deg)
    min_z = float(math.sin(math.radians(min_elev_deg)))  # z = sin(elevation)
    z = rng.uniform(min_z, 1.0)
    phi = rng.uniform(0.0, 2.0 * math.pi)
    r_xy = math.sqrt(max(0.0, 1.0 - z * z))
    x = r_xy * math.cos(phi)
    y = r_xy * math.sin(phi)
    return np.array([x, y, z], dtype=np.float64)


def _look_at(camera_pos: np.ndarray, target: np.ndarray) -> np.ndarray:
    # Camera forward points from camera to target.
    forward = (target - camera_pos).astype(np.float64)
    forward /= max(1e-9, float(np.linalg.norm(forward)))

    up_world = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    right = np.cross(forward, up_world)
    if float(np.linalg.norm(right)) < 1e-9:
        right = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    right /= max(1e-9, float(np.linalg.norm(right)))
    up = np.cross(right, forward)
    up /= max(1e-9, float(np.linalg.norm(up)))

    pose = np.eye(4, dtype=np.float64)
    # pyrender camera convention: columns are basis vectors.
    pose[:3, 0] = right
    pose[:3, 1] = up
    pose[:3, 2] = -forward
    pose[:3, 3] = camera_pos
    return pose


def _bbox_from_mask(mask: np.ndarray) -> tuple[float, float, float, float] | None:
    # mask: HxW bool
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if (not np.any(rows)) or (not np.any(cols)):
        return None
    ymin, ymax = np.where(rows)[0][[0, -1]]
    xmin, xmax = np.where(cols)[0][[0, -1]]
    w_px = float(xmax - xmin)
    h_px = float(ymax - ymin)
    if w_px <= 1.0 or h_px <= 1.0:
        return None
    h, w = mask.shape[:2]
    cx = float(xmin) + w_px / 2.0
    cy = float(ymin) + h_px / 2.0
    return (cx / float(w), cy / float(h), w_px / float(w), h_px / float(h))


def _rand_color(rng: np.random.Generator, lo: int = 0, hi: int = 255) -> tuple[int, int, int]:
    return tuple(int(x) for x in rng.integers(lo, hi + 1, size=(3,)))


def _background_field(w: int, h: int, rng: np.random.Generator) -> np.ndarray:
    base = np.full((h, w, 3), (rng.integers(70, 140), rng.integers(90, 170), rng.integers(60, 120)), dtype=np.uint8)
    # Grass/dirt patches
    for _ in range(int(rng.integers(30, 90))):
        color = _rand_color(rng, 20, 220)
        center = (int(rng.integers(0, w)), int(rng.integers(0, h)))
        axes = (int(rng.integers(10, 160)), int(rng.integers(10, 160)))
        angle = float(rng.uniform(0, 360))
        cv2.ellipse(base, center, axes, angle, 0, 360, color, -1)
    # Tracks/lines
    for _ in range(int(rng.integers(3, 10))):
        pt1 = (int(rng.integers(-w // 4, w + w // 4)), int(rng.integers(0, h)))
        pt2 = (int(rng.integers(-w // 4, w + w // 4)), int(rng.integers(0, h)))
        cv2.line(base, pt1, pt2, _rand_color(rng, 0, 255), int(rng.integers(1, 4)))
    # Rocks
    for _ in range(int(rng.integers(2, 7))):
        r = int(rng.integers(10, 80))
        center = (int(rng.integers(0, w)), int(rng.integers(0, h)))
        cv2.circle(base, center, r, _rand_color(rng, 30, 220), -1)
    return base


def _background_urban(w: int, h: int, rng: np.random.Generator) -> np.ndarray:
    base = np.full((h, w, 3), _rand_color(rng, 80, 200), dtype=np.uint8)
    # Buildings/blocks
    for _ in range(int(rng.integers(20, 80))):
        x1, y1 = int(rng.integers(0, w)), int(rng.integers(0, h))
        x2, y2 = int(rng.integers(x1, w)), int(rng.integers(y1, h))
        cv2.rectangle(base, (x1, y1), (x2, y2), _rand_color(rng, 0, 255), -1)
    # Edges
    edges = cv2.Canny(base, 50, 150)
    base[edges > 0] = _rand_color(rng, 0, 255)
    return base


def _background_sky_field(w: int, h: int, rng: np.random.Generator) -> np.ndarray:
    # Simple gradient with noisy clouds.
    sky_top = np.array(_rand_color(rng, 160, 255), dtype=np.float32)
    field_bottom = np.array(_rand_color(rng, 0, 160), dtype=np.float32)
    y = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    grad = (1.0 - y) * sky_top + y * field_bottom
    base = np.repeat(grad[:, None, :], w, axis=1).astype(np.uint8)

    clouds = rng.integers(0, 256, size=(h, w), dtype=np.uint8)
    clouds = cv2.GaussianBlur(clouds, (0, 0), sigmaX=float(rng.uniform(5, 25)))
    base = cv2.addWeighted(base, 1.0, cv2.cvtColor(clouds, cv2.COLOR_GRAY2BGR), float(rng.uniform(0.05, 0.25)), 0.0)
    return base


def _background_noise(w: int, h: int, rng: np.random.Generator) -> np.ndarray:
    noise = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
    # Blur noise into texture
    k = int(rng.integers(9, 61))
    if k % 2 == 0:
        k += 1
    noise = cv2.GaussianBlur(noise, (k, k), sigmaX=float(rng.uniform(1.0, 12.0)))
    return noise


def _create_background(w: int, h: int, rng: np.random.Generator) -> np.ndarray:
    mode = rng.choice(["field", "urban", "sky_field", "noise"], p=[0.45, 0.20, 0.20, 0.15])
    if mode == "field":
        bg = _background_field(w, h, rng)
    elif mode == "urban":
        bg = _background_urban(w, h, rng)
    elif mode == "sky_field":
        bg = _background_sky_field(w, h, rng)
    else:
        bg = _background_noise(w, h, rng)

    # Global background noise
    if bool(rng.integers(0, 2)):
        sigma = float(rng.uniform(5.0, 25.0))
        n = rng.normal(0.0, sigma, size=bg.shape).astype(np.float32)
        bg = np.clip(bg.astype(np.float32) + n, 0, 255).astype(np.uint8)
    return bg


def _apply_motion_blur(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    if rng.uniform(0.0, 1.0) > 0.25:
        return img
    k = int(rng.integers(5, 31))
    if k % 2 == 0:
        k += 1
    kernel = np.zeros((k, k), dtype=np.float32)
    # Line kernel at random angle.
    angle = float(rng.uniform(0.0, math.pi))
    x0 = (k - 1) / 2.0
    for i in range(k):
        x = i - x0
        y = math.tan(angle) * x
        j = int(round(y + x0))
        if 0 <= j < k:
            kernel[j, i] = 1.0
    s = float(kernel.sum())
    if s <= 0:
        return img
    kernel /= s
    return cv2.filter2D(img, -1, kernel)


def _apply_color_jitter(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    # Brightness/contrast.
    alpha = float(rng.uniform(0.6, 1.5))  # contrast
    beta = float(rng.uniform(-30, 30))  # brightness
    out = np.clip(img.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)

    # Saturation/hue in HSV.
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.int16)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * float(rng.uniform(0.6, 1.6)), 0, 255)
    hsv[:, :, 0] = (hsv[:, :, 0] + int(rng.integers(-12, 13))) % 180
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def _apply_sensor_noise(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    # Gaussian sensor noise.
    sigma = float(rng.uniform(0.0, 18.0))
    if sigma <= 0.1:
        return img
    n = rng.normal(0.0, sigma, size=img.shape).astype(np.float32)
    return np.clip(img.astype(np.float32) + n, 0, 255).astype(np.uint8)


def _apply_jpeg(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    if rng.uniform(0.0, 1.0) > 0.35:
        return img
    q = int(rng.integers(15, 70))
    ok, enc = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
    if not ok:
        return img
    dec = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    return dec if dec is not None else img


def _apply_cutout(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    if rng.uniform(0.0, 1.0) > 0.35:
        return img
    out = img.copy()
    h, w = out.shape[:2]
    for _ in range(int(rng.integers(1, 6))):
        cw = int(rng.integers(w // 20, w // 4))
        ch = int(rng.integers(h // 20, h // 4))
        x1 = int(rng.integers(0, max(1, w - cw)))
        y1 = int(rng.integers(0, max(1, h - ch)))
        x2 = x1 + cw
        y2 = y1 + ch
        color = _rand_color(rng, 0, 255)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, -1)
    return out


def _apply_blur(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    if rng.uniform(0.0, 1.0) > 0.25:
        return img
    k = int(rng.integers(3, 11))
    if k % 2 == 0:
        k += 1
    return cv2.GaussianBlur(img, (k, k), sigmaX=float(rng.uniform(0.5, 2.2)))


def _augment_bgr(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = img
    out = _apply_color_jitter(out, rng)
    out = _apply_motion_blur(out, rng)
    out = _apply_blur(out, rng)
    out = _apply_sensor_noise(out, rng)
    out = _apply_cutout(out, rng)
    out = _apply_jpeg(out, rng)
    return out


@dataclass(frozen=True)
class GenCfg:
    out_dir: Path
    img_size: int
    num_per_class: int
    seed: int
    min_elev_deg: float
    min_dist: float
    max_dist: float
    split_train: float
    split_val: float
    split_test: float
    min_box_area: float


def _make_scene(mesh: trimesh.Trimesh, img_size: int) -> tuple[pyrender.Scene, pyrender.Node, pyrender.Node, list[pyrender.Node], pyrender.OffscreenRenderer]:
    scene = pyrender.Scene(bg_color=[0, 0, 0, 0], ambient_light=[0.35, 0.35, 0.35])
    mesh_node = scene.add(pyrender.Mesh.from_trimesh(mesh, smooth=False))
    cam = pyrender.PerspectiveCamera(yfov=np.pi / 3.0, aspectRatio=1.0)
    cam_node = scene.add(cam, pose=np.eye(4))
    lights: list[pyrender.Node] = []
    # Two directional lights for stronger variation.
    for _ in range(2):
        light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=3.0)
        lights.append(scene.add(light, pose=np.eye(4)))
    r = pyrender.OffscreenRenderer(img_size, img_size)
    return scene, mesh_node, cam_node, lights, r


def _load_and_normalize_mesh(obj_path: Path) -> trimesh.Trimesh:
    mesh = trimesh.load(str(obj_path), force="mesh")
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))
    if not isinstance(mesh, trimesh.Trimesh):
        raise TypeError(f"unsupported_mesh:{type(mesh)}")

    # Put models upright (legacy assets are often in different coordinate systems).
    rot = trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0])
    mesh.apply_transform(rot)

    mesh.apply_translation(-mesh.centroid)
    scale = 1.0 / float(np.max(mesh.extents))
    mesh.apply_scale(scale)

    # Neutral base color; appearance robustness comes from domain randomization.
    mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, vertex_colors=[110, 110, 110, 255])
    return mesh


def _pick_split(rng: np.random.Generator, cfg: GenCfg) -> str:
    x = float(rng.uniform(0.0, 1.0))
    if x < cfg.split_train:
        return "train"
    if x < cfg.split_train + cfg.split_val:
        return "val"
    return "test"


def _write_label(path: Path, class_id: int, bbox: tuple[float, float, float, float]) -> None:
    path.write_text(f"{class_id} {bbox[0]:.6f} {bbox[1]:.6f} {bbox[2]:.6f} {bbox[3]:.6f}\n", encoding="utf-8")


def _compose(bg_bgr: np.ndarray, fg_rgb: np.ndarray, mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    # Feather alpha to avoid a "paper cutout" look.
    h, w = mask.shape[:2]
    alpha = mask.astype(np.float32)
    alpha = cv2.GaussianBlur(alpha, (0, 0), sigmaX=float(rng.uniform(0.8, 2.0)))
    alpha = np.clip(alpha, 0.0, 1.0)[:, :, None]

    fg_bgr = cv2.cvtColor(fg_rgb, cv2.COLOR_RGB2BGR)
    mask3 = mask[:, :, None]

    # Add object-side appearance randomness (texture + tint) for robustness.
    if rng.uniform(0.0, 1.0) < 0.90:
        tint = rng.uniform(0.6, 1.4, size=(1, 1, 3)).astype(np.float32)
        fg_bgr = np.clip(fg_bgr.astype(np.float32) * tint, 0, 255).astype(np.uint8)
    if rng.uniform(0.0, 1.0) < 0.70:
        tex = _background_noise(w, h, rng)
        a = float(rng.uniform(0.15, 0.55))
        blended = cv2.addWeighted(fg_bgr, 1.0 - a, tex, a, 0.0)
        fg_bgr = np.where(mask3, blended, fg_bgr)

    # Simple shadow: shift mask and darken.
    if rng.uniform(0.0, 1.0) < 0.65:
        dx = int(rng.integers(-20, 21))
        dy = int(rng.integers(5, 35))
        shadow_u8 = (mask.astype(np.uint8) * 255)
        M = np.array([[1.0, 0.0, float(dx)], [0.0, 1.0, float(dy)]], dtype=np.float32)
        shadow = cv2.warpAffine(shadow_u8, M, (w, h), flags=cv2.INTER_NEAREST, borderValue=0).astype(np.float32) / 255.0
        shadow = cv2.GaussianBlur(shadow, (0, 0), sigmaX=float(rng.uniform(2.0, 10.0)))
        shadow = (shadow * float(rng.uniform(0.15, 0.45))).clip(0.0, 1.0)[:, :, None]
        bg_bgr = np.clip(bg_bgr.astype(np.float32) * (1.0 - shadow), 0, 255).astype(np.uint8)

    out = (fg_bgr.astype(np.float32) * alpha + bg_bgr.astype(np.float32) * (1.0 - alpha)).astype(np.uint8)
    return out


def _generate_for_class(cfg: GenCfg, class_name: str, class_id: int, obj_path: Path) -> None:
    if not obj_path.exists():
        raise FileNotFoundError(f"missing_asset:{obj_path}")

    rng = np.random.default_rng(cfg.seed + class_id * 1337)

    mesh = _load_and_normalize_mesh(obj_path)
    scene, mesh_node, cam_node, lights, renderer = _make_scene(mesh, cfg.img_size)

    written = 0
    attempts = 0
    max_attempts = int(cfg.num_per_class * 3)
    while written < cfg.num_per_class and attempts < max_attempts:
        attempts += 1

        split = _pick_split(rng, cfg)

        # Object pose (upright, slight lateral jitter + random yaw).
        yaw = float(rng.uniform(0.0, 2.0 * math.pi))
        jitter_xy = float(rng.uniform(0.0, 0.20))
        jitter_phi = float(rng.uniform(0.0, 2.0 * math.pi))
        tx = jitter_xy * math.cos(jitter_phi)
        ty = jitter_xy * math.sin(jitter_phi)
        mesh_pose = np.eye(4, dtype=np.float64)
        mesh_pose[:3, :3] = trimesh.transformations.rotation_matrix(yaw, [0, 0, 1])[:3, :3]
        mesh_pose[:3, 3] = np.array([tx, ty, 0.0], dtype=np.float64)
        scene.set_pose(mesh_node, pose=mesh_pose)

        # Camera pose (upper hemisphere dome).
        dist = float(rng.uniform(cfg.min_dist, cfg.max_dist))
        d = _uniform_upper_hemisphere_dir(rng, cfg.min_elev_deg)
        cam_pos = d * dist

        target = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        target += np.array([float(rng.uniform(-0.08, 0.08)), float(rng.uniform(-0.08, 0.08)), 0.0], dtype=np.float64)

        cam_pose = _look_at(cam_pos, target)
        scene.set_pose(cam_node, pose=cam_pose)

        # Randomize lighting around camera direction.
        for ln in lights:
            light_pose = cam_pose.copy()
            light_pose[:3, 3] = cam_pos + rng.normal(0.0, 0.15, size=(3,))  # small offset
            scene.set_pose(ln, pose=light_pose)

        # Render and build mask/bbox.
        rgb, depth = renderer.render(scene)
        mask = (depth > 0.0)
        bbox = _bbox_from_mask(mask)
        if bbox is None:
            continue
        box_area = float(bbox[2] * bbox[3])
        if box_area < cfg.min_box_area:
            continue

        bg = _create_background(cfg.img_size, cfg.img_size, rng)
        composed = _compose(bg, rgb, mask, rng)
        composed = _augment_bgr(composed, rng)

        fname = f"{class_name}_{written:06d}.jpg"
        img_path = cfg.out_dir / "images" / split / fname
        lbl_path = cfg.out_dir / "labels" / split / (Path(fname).stem + ".txt")
        cv2.imwrite(str(img_path), composed)
        _write_label(lbl_path, class_id, bbox)

        written += 1
        if written % 250 == 0:
            print(f"[gen] {class_name}: {written}/{cfg.num_per_class} written (attempts={attempts})", flush=True)

    renderer.delete()
    if written < cfg.num_per_class:
        raise RuntimeError(f"insufficient_images:{class_name}:written={written} attempts={attempts} target={cfg.num_per_class}")


def _make_preview_grid(dataset_dir: Path, out_path: Path, n: int = 16) -> None:
    imgs = []
    for p in sorted((dataset_dir / "images" / "train").glob("*.jpg"))[: max(1, n)]:
        img = cv2.imread(str(p))
        if img is None:
            continue
        imgs.append(cv2.resize(img, (256, 256)))
        if len(imgs) >= n:
            break
    if not imgs:
        return
    # 4x4 grid
    while len(imgs) < 16:
        imgs.append(imgs[-1].copy())
    rows = [np.concatenate(imgs[i : i + 4], axis=1) for i in range(0, 16, 4)]
    grid = np.concatenate(rows, axis=0)
    cv2.imwrite(str(out_path), grid)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate synthetic YOLO dataset from 3D OBJ assets (dome sampling).")
    p.add_argument("--out", type=Path, default=(THIS_DIR / "dataset"))
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--num-per-class", type=int, default=2000)
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--min-elev-deg", type=float, default=5.0, help="Min elevation above horizon for dome sampling (upper hemisphere only).")
    p.add_argument("--min-dist", type=float, default=1.2)
    p.add_argument("--max-dist", type=float, default=6.0)
    p.add_argument("--split-train", type=float, default=0.80)
    p.add_argument("--split-val", type=float, default=0.10)
    p.add_argument("--split-test", type=float, default=0.10)
    p.add_argument("--min-box-area", type=float, default=0.004, help="Reject samples with too-small bboxes.")
    p.add_argument("--preview", action="store_true", help="Write preview grid image after generation.")
    return p.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.imgsz < 128:
        raise SystemExit("imgsz_too_small")
    if args.num_per_class < 10:
        raise SystemExit("num_per_class_too_small")
    if args.min_dist <= 0 or args.max_dist <= 0 or args.max_dist <= args.min_dist:
        raise SystemExit("invalid_dist_range")
    if args.min_elev_deg < 0.0 or args.min_elev_deg >= 89.0:
        raise SystemExit("invalid_min_elev_deg")
    split_sum = float(args.split_train + args.split_val + args.split_test)
    if abs(split_sum - 1.0) > 1e-6:
        raise SystemExit(f"invalid_split_sum:{split_sum}")

    cfg = GenCfg(
        out_dir=args.out,
        img_size=int(args.imgsz),
        num_per_class=int(args.num_per_class),
        seed=int(args.seed),
        min_elev_deg=float(args.min_elev_deg),
        min_dist=float(args.min_dist),
        max_dist=float(args.max_dist),
        split_train=float(args.split_train),
        split_val=float(args.split_val),
        split_test=float(args.split_test),
        min_box_area=float(args.min_box_area),
    )

    _seed_everything(cfg.seed)
    print(f"[gen] output={cfg.out_dir} imgsz={cfg.img_size} per_class={cfg.num_per_class} seed={cfg.seed}", flush=True)
    _ensure_clean_dirs(cfg.out_dir)

    for class_id, (class_name, obj_path) in enumerate(CLASSES):
        print(f"[gen] class={class_name} obj={obj_path}", flush=True)
        _generate_for_class(cfg, class_name, class_id, obj_path)

    if bool(args.preview):
        _make_preview_grid(cfg.out_dir, THIS_DIR / "preview_grid.jpg", n=16)
        print(f"[gen] wrote preview: {THIS_DIR / 'preview_grid.jpg'}", flush=True)

    print("[gen] done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
