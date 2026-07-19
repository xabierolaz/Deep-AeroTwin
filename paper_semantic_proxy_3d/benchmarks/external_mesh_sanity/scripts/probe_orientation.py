# external sanity check (exploratory, post-hoc)
"""Orientation probe: render top/side silhouettes under rotation hypotheses."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import mesh_lib


def panel(ax, mask, title):
    ax.imshow(mask.T, origin="lower", cmap="gray", interpolation="nearest")
    ax.set_title(title, fontsize=8)
    ax.set_xticks([])
    ax.set_yticks([])


def probe(mesh_path: Path, hypotheses: dict[str, np.ndarray], out_png: Path, ref_axis: str, target: float, use_pca: bool = True):
    mesh = mesh_lib.load_mesh(mesh_path)
    n = len(hypotheses)
    fig, axes = plt.subplots(2, n, figsize=(3 * n, 6.4))
    for col, (name, rot) in enumerate(hypotheses.items()):
        m, info = mesh_lib.apply_orientation(mesh, rot, use_pca, None)
        m, sinfo = mesh_lib.normalize_scale_place(m, ref_axis, target)
        top, side = mesh_lib.render_masks(m)
        ext = m.extents
        panel(axes[0, col], top, f"{name}\ntop [x,y] ext={ext.round(2)}")
        panel(axes[1, col], side, f"{name}\nside [x,z] yaw={info['pca_yaw_deg'] and round(info['pca_yaw_deg'],1)}")
    fig.suptitle(mesh_path.name, fontsize=9)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=110)
    plt.close(fig)
    print("wrote", out_png)


def main():
    ident = np.eye(3)
    yup = mesh_lib.rot_about_x(90)  # +Y -> +Z
    zup_from_neg_y = mesh_lib.rot_about_x(-90)  # -Y -> +Z (alternative)
    hyps = {"identity(z-up?)": ident, "y-up->z-up": yup, "neg-y-up->z-up": zup_from_neg_y}
    root = common.OUTPUT_ROOT
    probe(root / "meshes" / "modelnet40" / "car" / "car_0258.off", hyps, root / "qc" / "probe_car.png", "x", 4.4, use_pca=False)
    probe(root / "meshes" / "modelnet40" / "car" / "car_0249.off", hyps, root / "qc" / "probe_car2.png", "x", 4.4, use_pca=False)
    probe(root / "meshes" / "modelnet40" / "plant" / "plant_0306.off", hyps, root / "qc" / "probe_plant.png", "z", 2.2, use_pca=False)
    probe(root / "meshes" / "modelnet40" / "plant" / "plant_0339.off", hyps, root / "qc" / "probe_plant2.png", "z", 2.2, use_pca=False)
    probe(root / "meshes" / "objaverse" / "horse" / "b25366a78f134cc3bab5d990a32bfbc8.glb", hyps, root / "qc" / "probe_horse.png", "x", 2.4, use_pca=True)
    probe(root / "meshes" / "objaverse" / "motorcycle" / "a06ac84d848242c58c3d4517c189f8e3.glb", hyps, root / "qc" / "probe_motorcycle.png", "x", 2.2, use_pca=True)


if __name__ == "__main__":
    main()
