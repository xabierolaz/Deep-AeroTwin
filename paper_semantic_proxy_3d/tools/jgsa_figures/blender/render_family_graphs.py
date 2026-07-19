"""Render the six SPPA family graphs (default theta), colored by slot role.

One PNG per family -> tools/jgsa_figures/assets/render_fam_<family>.png
Composited into figures/fig_family_graphs_blender.png by compose_family_graphs.py.

Run: "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" -b -P render_family_graphs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sppa_scene as S  # noqa: E402

FAMILIES = (
    "compact_vehicle",
    "articulated_vehicle",
    "quadruped",
    "branching_vertical",
    "lattice_tower",
    "rider_cycle",
)


def main() -> None:
    assets = S.load_assets()
    for family in FAMILIES:
        S.clean_scene()
        materials = S.role_materials(assets)
        objects = S.add_actor(assets["families"][family], materials)
        S.setup_ground(z=0.0)
        center, radius = S.scene_bbox(objects)
        S.add_camera(center, radius, azimuth_deg=-58.0, elevation_deg=24.0, margin=1.30)
        S.setup_lighting(center, radius)
        S.setup_render(1200, 900)
        S.render_to(S.ASSETS / f"render_fam_{family}.png")


if __name__ == "__main__":
    main()
