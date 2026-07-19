"""Export assets for the JGSA Blender figures (Grupo A).

Reads the sealed SPPA-MVFIT package read-only and writes, under
tools/jgsa_figures/assets/:
  - blender_assets.json  : primitive lists (type/center/size/axis + slot role)
                           for the 6 default family graphs, the truck fitting
                           sequence (theta_init / theta_fit) and the fitted
                           quadruped; plus case metadata (IoU, theta values).
  - gt_truck.obj         : GT mesh of the truck case (64^3 voxel grid ->
                           marching cubes via trimesh, world coordinates).
  - gt_quadruped.obj     : GT mesh of the quadruped case (same pipeline).
  - masks_truck.png      : observed top | side masks of the truck case (clean).

Cases (chosen from sealed raw_metrics.csv, clean condition, sppa_mvfit):
  truck     = test-csg_id-articulated_vehicle-013 (best csg_id articulated, IoU 0.5707)
  quadruped = test-csg_id-quadruped-018          (IoU 0.8218, E6 csg_id stratum)

Roles per slot follow benchmarks/mvfit_reviewer_experiments/e6_role_aware/
ROLE_MAPPING_FROZEN.md (frozen before role-aware computation).

Run with the system Python (numpy/scipy/trimesh/skimage):
  "C:\\Users\\xabie\\AppData\\Local\\Programs\\Python\\Python312\\python.exe" export_blender_assets.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True  # keep the sealed package untouched

REPO = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d")
SEAL = REPO / "reproducibility" / "sppa_mvfit"
ASSETS = REPO / "tools" / "jgsa_figures" / "assets"
sys.path.insert(0, str(SEAL))

from method import sppa_mvfit as mv  # noqa: E402  (sealed module, read-only import)

TRUCK = "test-csg_id-articulated_vehicle-013"
QUAD = "test-csg_id-quadruped-018"

FAMILIES = (
    "compact_vehicle",
    "articulated_vehicle",
    "quadruped",
    "branching_vertical",
    "lattice_tower",
    "rider_cycle",
)

# slot roles per family, from ROLE_MAPPING_FROZEN.md (E6, frozen)
SLOT_ROLES = {
    "compact_vehicle": ["body", "cabin", "wheel", "wheel", "wheel", "wheel", "bumper", "bumper"],
    "articulated_vehicle": ["tractor", "cabin", "trailer", "hitch", "wheel", "wheel", "wheel", "wheel"],
    "quadruped": ["body", "head", "leg", "leg", "leg", "leg", "neck", "tail"],
    "branching_vertical": ["trunk", "crown", "crown", "crown", "crown", "branch", "branch", "branch"],
    "lattice_tower": ["core", "leg", "leg", "leg", "leg", "platform", "platform", "platform"],
    "rider_cycle": ["wheel", "wheel", "frame", "frame", "frame", "torso", "head", "fork"],
}

# role -> category (fixed palette, Okabe-Ito)
ROLE_CATEGORY = {
    "body": "primary structure", "tractor": "primary structure", "trunk": "primary structure",
    "core": "primary structure", "torso": "primary structure",
    "cabin": "cabin / head", "head": "cabin / head",
    "wheel": "wheels / legs", "leg": "wheels / legs",
    "trailer": "cargo / crown", "crown": "cargo / crown",
    "bumper": "appendages", "hitch": "appendages", "neck": "appendages",
    "tail": "appendages", "fork": "appendages", "branch": "appendages",
    "frame": "frame / platforms", "platform": "frame / platforms",
}
CATEGORY_COLORS = {  # Okabe-Ito
    "primary structure": "#0072B2",
    "cabin / head": "#E69F00",
    "wheels / legs": "#009E73",
    "cargo / crown": "#56B4E9",
    "appendages": "#D55E00",
    "frame / platforms": "#CC79A7",
}

WORLD = {a: tuple(float(v) for v in mv.WORLD[a]) for a in ("x", "y", "z")}
RES = 64


def load_private_actors() -> dict[str, dict]:
    actors = {}
    with (SEAL / "data" / "test" / "private_source_actors.jsonl").open("r", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            actors[row["case_id"]] = row["actor"]
    return actors


def gt_actor_components(actor: dict) -> list[dict]:
    """Adapt private GT components (kind -> type) to the method actor schema."""
    comps = []
    for i, c in enumerate(actor["components"]):
        comps.append({
            "slot_index": i,
            "type": c["kind"],
            "axis": c.get("axis", "z"),
            "secondary": False,
            "center": [float(v) for v in c["center"]],
            "size": [float(v) for v in c["size"]],
        })
    return comps


def voxel_to_world_mesh(occ: np.ndarray):
    """64^3 boolean grid -> marching-cubes mesh in world coordinates (trimesh)."""
    import trimesh
    from trimesh.voxel import encoding as venc

    steps = tuple((WORLD[a][1] - WORLD[a][0]) / RES for a in ("x", "y", "z"))
    lows = tuple(WORLD[a][0] for a in ("x", "y", "z"))
    transform = np.eye(4)
    transform[0, 0], transform[1, 1], transform[2, 2] = steps
    transform[0, 3], transform[1, 3], transform[2, 3] = (
        lows[0] + 0.5 * steps[0], lows[1] + 0.5 * steps[1], lows[2] + 0.5 * steps[2])
    grid = trimesh.voxel.VoxelGrid(venc.DenseEncoding(occ), transform=transform)
    mesh = grid.marching_cubes
    # Some trimesh versions return marching-cubes vertices in grid-index
    # coordinates, ignoring the VoxelGrid transform. Detect that case
    # (vertices outside the world bounds) and apply the transform manually.
    world_hi = max(WORLD[a][1] for a in ("x", "y", "z"))
    if float(mesh.vertices.max()) > world_hi + 1.0:
        mesh.apply_transform(transform)
    return mesh


def write_obj(mesh, path: Path) -> None:
    """Minimal OBJ writer (v/f), coordinates exactly as in mesh.vertices."""
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# GT mesh from sealed 64^3 voxel grid (marching cubes, trimesh)\n")
        for v in mesh.vertices:
            fh.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for f in mesh.faces:
            fh.write(f"f {f[0] + 1} {f[1] + 1} {f[2] + 1}\n")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    actors = load_private_actors()

    cases = json.loads((SEAL / "data" / "test" / "public_cases.json").read_text(encoding="utf-8"))
    case_index = {c["case_id"]: c["index"] for c in cases}
    masks = np.load(SEAL / "data" / "test" / "observation_masks.npy")

    # sealed thetas (sppa_mvfit, clean)
    thetas = {}
    with (SEAL / "results" / "test" / "sealed_method_outputs.jsonl").open("r", encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            if d["case_id"] in (TRUCK, QUAD) and d["condition"] == "clean" \
                    and d["metadata"].get("method") == "sppa_mvfit":
                thetas[d["case_id"]] = [float(v) for v in d["metadata"]["theta"]]
    assert set(thetas) == {TRUCK, QUAD}, thetas.keys()

    # sealed per-case voxel IoU for annotation
    ious = {}
    with (SEAL / "results" / "test" / "raw_metrics.csv").open("r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["case_id"] in (TRUCK, QUAD) and row["condition"] == "clean" \
                    and row["method"] == "sppa_mvfit":
                ious[row["case_id"]] = float(row["voxel_iou"])

    def with_roles(family: str, actor: list[dict]) -> list[dict]:
        out = []
        for prim in actor:
            role = SLOT_ROLES[family][prim["slot_index"]]
            cat = ROLE_CATEGORY[role]
            out.append({**prim, "role": role, "category": cat,
                        "color": CATEGORY_COLORS[cat]})
        return out

    payload: dict = {
        "world": WORLD,
        "families": {},
        "role_categories": CATEGORY_COLORS,
        "cases": {},
    }

    # 1) six default family graphs (theta = default)
    theta0 = mv.default_theta()
    for fam in FAMILIES:
        actor = mv.build_actor(fam, theta0)
        payload["families"][fam] = with_roles(fam, actor)

    # 2) truck fitting sequence
    ci = case_index[TRUCK]
    top, side = masks[ci, 0, 0], masks[ci, 0, 1]
    theta_init, empty = mv.initialize_theta("articulated_vehicle", top, side)
    assert not empty
    truck_fit_actor = mv.build_actor("articulated_vehicle", np.asarray(thetas[TRUCK]))
    truck_init_actor = mv.build_actor("articulated_vehicle", theta_init)

    # sanity: voxel IoU of sealed-theta actor vs sealed metric
    pred = mv.voxelize_actor(truck_fit_actor, RES)
    gt_occ = mv.voxelize_actor(gt_actor_components(actors[TRUCK]), RES)
    iou = float(np.count_nonzero(pred & gt_occ) / np.count_nonzero(pred | gt_occ))
    print(f"truck recompute IoU {iou:.6f} vs sealed {ious[TRUCK]:.6f}")
    assert abs(iou - ious[TRUCK]) < 1e-9

    gt_truck_mesh = voxel_to_world_mesh(gt_occ)
    write_obj(gt_truck_mesh, ASSETS / "gt_truck.obj")

    # mask panel image (top | side), object = black on white; +y/+z up
    from PIL import Image
    top_img = np.where(top.T[::-1, :], 0, 255).astype(np.uint8)
    side_img = np.where(side.T[::-1, :], 0, 255).astype(np.uint8)
    panel = np.concatenate([top_img, np.full((96, 8), 255, np.uint8), side_img], axis=1)
    Image.fromarray(panel, mode="L").save(ASSETS / "masks_truck.png")

    payload["cases"][TRUCK] = {
        "family": "articulated_vehicle",
        "theta_init": [float(v) for v in theta_init],
        "theta_fit": thetas[TRUCK],
        "voxel_iou": ious[TRUCK],
        "actor_init": with_roles("articulated_vehicle", truck_init_actor),
        "actor_fit": with_roles("articulated_vehicle", truck_fit_actor),
        "gt_obj": "gt_truck.obj",
        "masks_png": "masks_truck.png",
    }

    # 3) quadruped fitted actor + GT mesh
    ci_q = case_index[QUAD]
    quad_fit_actor = mv.build_actor("quadruped", np.asarray(thetas[QUAD]))
    gt_quad_occ = mv.voxelize_actor(gt_actor_components(actors[QUAD]), RES)
    pred_q = mv.voxelize_actor(quad_fit_actor, RES)
    iou_q = float(np.count_nonzero(pred_q & gt_quad_occ) / np.count_nonzero(pred_q | gt_quad_occ))
    print(f"quadruped recompute IoU {iou_q:.6f} vs sealed {ious[QUAD]:.6f}")
    assert abs(iou_q - ious[QUAD]) < 1e-9
    gt_quad_mesh = voxel_to_world_mesh(gt_quad_occ)
    write_obj(gt_quad_mesh, ASSETS / "gt_quadruped.obj")
    payload["cases"][QUAD] = {
        "family": "quadruped",
        "theta_fit": thetas[QUAD],
        "voxel_iou": ious[QUAD],
        "actor_fit": with_roles("quadruped", quad_fit_actor),
        "gt_obj": "gt_quadruped.obj",
    }

    (ASSETS / "blender_assets.json").write_text(
        json.dumps(payload, indent=1), encoding="utf-8")
    print("assets written to", ASSETS)


if __name__ == "__main__":
    main()
