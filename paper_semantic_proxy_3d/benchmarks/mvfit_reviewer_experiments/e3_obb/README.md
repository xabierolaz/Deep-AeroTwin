# E3 — Oriented bounding box (OBB) baseline

**Label:** exploratory post-hoc analysis (not confirmatory).

## Question

The sealed primitive baselines include an axis-aligned box (AABB, 0.248) but
no rotation-aware box. Does an oriented bounding box close part of the gap to
SPPA-MVFit (0.557)?

## Construction (fixed before measurement)

1. Top mask → largest connected component (same `ndimage.label` scheme as the
   sealed method) → occupied pixel centers in world (x, y) meters.
2. `cv2.minAreaRect` on those points; box axes taken from `cv2.boxPoints` edge
   vectors (no angle-convention assumptions). Axis-aligned fallback when the
   component has < 3 pixels.
3. **Gap-midpoint refinement** per axis: the boundary lies between the extreme
   occupied center projection and the nearest unoccupied center projection
   (candidates restricted to the slab of the opposite axis, otherwise corner
   regions falsely constrain the face); midpoint = minimax estimator. This
   removes a measured ~0.03 m center bias of raw `minAreaRect` on quantized
   masks (worth ~0.05 IoU).
4. z from the side-mask largest component z-range → right prism.
5. Analytic voxelization on the sealed 64³ grid/world box.

Self-check (aborts on failure): a synthetic box with known yaw = 33° is
voxelized, projected, and reconstructed by this same code; reconstruction 3D
IoU = **0.948 ≥ 0.90** — the estimator recovers center/yaw/extents correctly;
the residual is irreducible 64³ boundary quantization.

## Protocol

n = 240 actors, clean condition, voxel IoU at 64³ vs source GT. Comparators
are read from the sealed `results/test/raw_metrics.csv` (NOT recomputed):
AABB 0.248, visual hull 0.522, SPPA-MVFit 0.557. Bootstrap: stratified
paired, cells (family, stratum), 10 000 resamples, seed 77157.

## Headline numbers (pooled voxel IoU, n = 240)

| Method | Mean IoU | Δ vs OBB | CI95 |
|---|---|---|---|
| Axis-aligned box (sealed) | 0.248 | −0.004 | [−0.005, −0.003] |
| **OBB (this work)** | **0.252** | — | — |
| Visual hull (sealed) | 0.522 | +0.270 | [+0.264, +0.275] |
| SPPA-MVFit (sealed) | 0.557 | +0.306 | [+0.297, +0.314] |

Per stratum — csg_id: OBB 0.224 / AABB 0.221 / hull 0.489 / SPPA 0.551;
implicit_ood: OBB 0.279 / AABB 0.275 / hull 0.554 / SPPA 0.564.
Median inference 0.43 ms/case (p95 0.62 ms).

## Interpretation

OBB beats AABB by only +0.004 IoU (CI [0.003, 0.005], p < 1e-4) and remains
0.27 below the visual hull. The benchmark source generators produce
axis-aligned actors, so orientation degrees of freedom buy almost nothing:
SPPA-MVFit's margin cannot be attributed to handling rotated boxes, and a
stronger geometric box prior is not a competitive alternative. This directly
bounds the "just fit a better box" reviewer concern.

## Files

- `run_e3_obb.py` — runner incl. self-check (exactly reproducible).
- `obb_baseline.json` — full numeric payload.
- `obb_baseline_table.tex` — booktabs comparison table.

## Seeds / determinism

Fully deterministic (no RNG in construction); bootstrap seed 77157.
