"""Render the fitting-sequence panels for the truck case
(test-csg_id-articulated_vehicle-013):
  fit_init.png : family actor at the mask-driven initial theta
  fit_fit.png  : actor at the sealed fitted theta
  fit_gt.png   : GT mesh (64^3 voxel -> marching cubes, trimesh)

Same camera (from the GT bbox) for the three panels.
Composited into figures/fig_fitting_sequence_blender.png by
compose_fitting_sequence.py (which adds the observed-masks panel).

Run: "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" -b -P render_fitting_sequence.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sppa_scene as S  # noqa: E402

CASE = "test-csg_id-articulated_vehicle-013"
GRAY = "#B9BEC4"


def main() -> None:
    assets = S.load_assets()
    case = assets["cases"][CASE]

    # --- determine a shared camera from the GT bbox ---
    S.clean_scene()
    gt_mat = S.make_material("gt_gray", GRAY, roughness=0.85)
    gt = S.add_gt_mesh(S.ASSETS / case["gt_obj"], gt_mat)
    center, radius = S.scene_bbox([gt])
    cam_pos_params = dict(azimuth_deg=-58.0, elevation_deg=22.0, margin=1.24)

    # --- panel: GT mesh ---
    S.setup_ground(z=0.0)
    S.add_camera(center, radius, **cam_pos_params)
    S.setup_lighting(center, radius)
    S.setup_render(1200, 900)
    S.render_to(S.ASSETS / "render_fit_gt.png")

    # --- panels: initial and fitted actors (role colors) ---
    for tag, key in (("init", "actor_init"), ("fit", "actor_fit")):
        S.clean_scene()
        materials = S.role_materials(assets)
        S.add_actor(case[key], materials)
        S.setup_ground(z=0.0)
        S.add_camera(center, radius, **cam_pos_params)
        S.setup_lighting(center, radius)
        S.setup_render(1200, 900)
        S.render_to(S.ASSETS / f"render_fit_{tag}.png")


if __name__ == "__main__":
    main()
