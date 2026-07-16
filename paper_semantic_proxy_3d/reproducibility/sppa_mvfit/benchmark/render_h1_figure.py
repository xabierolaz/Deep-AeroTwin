"""Render a compact H1 visual: GT vs Generic-MVFit vs SPPA-MVFit occupancy for three families."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

PACKAGE = Path(__file__).resolve().parents[1]
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

from method.sppa_mvfit import fit_graph, voxelize_actor  # noqa: E402
from source.source_generators import generate_source_actor, render_source_masks, voxelize_source  # noqa: E402

OUT = PACKAGE.parents[1] / "figures" / "sppa_mvfit_h1_occupancy_examples.png"


def surface_boxes(occ: np.ndarray, max_cells: int = 900) -> list[list[list[float]]]:
    coords = np.argwhere(occ)
    if len(coords) == 0:
        return []
    if len(coords) > max_cells:
        step = int(np.ceil(len(coords) / max_cells))
        coords = coords[::step]
    faces: list[list[list[float]]] = []
    for z, y, x in coords:
        x0, y0, z0 = float(x), float(y), float(z)
        x1, y1, z1 = x0 + 1.0, y0 + 1.0, z0 + 1.0
        faces.extend(
            [
                [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0]],
                [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]],
                [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]],
                [[x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]],
                [[x0, y0, z0], [x0, y1, z0], [x0, y1, z1], [x0, y0, z1]],
                [[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]],
            ]
        )
    return faces


def plot_occ(ax, occ: np.ndarray, title: str, color: str) -> None:
    faces = surface_boxes(occ)
    if faces:
        coll = Poly3DCollection(faces, alpha=0.35, facecolor=color, edgecolor="none")
        ax.add_collection3d(coll)
    ax.set_xlim(0, occ.shape[2])
    ax.set_ylim(0, occ.shape[1])
    ax.set_zlim(0, occ.shape[0])
    ax.set_title(title, fontsize=9)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    ax.view_init(elev=18, azim=35)


def main() -> int:
    cases = [
        ("compact_vehicle", "csg_id", 210010),
        ("lattice_tower", "csg_id", 210080),
        ("rider_cycle", "implicit_ood", 210200),
    ]
    fig = plt.figure(figsize=(10.5, 8.2), dpi=160)
    for row, (family, stratum, seed) in enumerate(cases):
        source = generate_source_actor(family, stratum, seed)
        top, side = render_source_masks(source)
        gt = voxelize_source(source, 48)
        generic = voxelize_actor(fit_graph("generic", top, side)["actor"], 48)
        sppa = voxelize_actor(fit_graph(family, top, side)["actor"], 48)
        for col, (occ, title, color) in enumerate(
            [
                (gt, f"{family}\nGT occupancy", "#4C78A8"),
                (generic, "Generic-MVFit", "#F58518"),
                (sppa, "SPPA-MVFit", "#54A24B"),
            ]
        ):
            ax = fig.add_subplot(3, 3, row * 3 + col + 1, projection="3d")
            plot_occ(ax, occ, title if row == 0 else title.split("\n")[-1] if col == 0 and row else title, color)
            if col == 0:
                ax.text2D(-0.08, 0.5, family.replace("_", " "), transform=ax.transAxes, rotation=90, va="center", fontsize=8)
    fig.suptitle("Held-out synthetic occupancy examples (illustrative; not the primary table)", fontsize=11)
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight")
    plt.close(fig)
    print(json.dumps({"figure": str(OUT), "exists": OUT.exists()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
