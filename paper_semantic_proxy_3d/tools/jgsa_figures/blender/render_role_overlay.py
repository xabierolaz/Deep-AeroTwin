"""Render the role-colored fitted quadruped (test-csg_id-quadruped-018) with
its GT mesh as a semi-transparent gray overlay -> render_role_overlay.png

Composited into figures/fig_role_colored_blender.png by compose_role_colored.py
(left panel; right panel is the E6 role-IoU bar chart).

Run: "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" -b -P render_role_overlay.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sppa_scene as S  # noqa: E402

CASE = "test-csg_id-quadruped-018"


def main() -> None:
    assets = S.load_assets()
    case = assets["cases"][CASE]

    S.clean_scene()
    materials = S.role_materials(assets)
    objects = S.add_actor(case["actor_fit"], materials)
    gt_mat = S.make_material("gt_ghost", "#9AA0A6", roughness=0.9, alpha=0.38)
    gt = S.add_gt_mesh(S.ASSETS / case["gt_obj"], gt_mat)
    S.setup_ground(z=0.0)
    center, radius = S.scene_bbox(objects + [gt])
    S.add_camera(center, radius, azimuth_deg=-58.0, elevation_deg=22.0, margin=1.26)
    S.setup_lighting(center, radius)
    S.setup_render(1400, 950)
    S.render_to(S.ASSETS / "render_role_overlay.png")


if __name__ == "__main__":
    main()
