# External mesh sanity check — SPPA-MVFit

**Label: external sanity check (exploratory, post-hoc).** Not part of the sealed
confirmatory protocol. Nothing here modifies `reproducibility/sppa_mvfit/`
(modules are *imported only*; the sealed scripts were never re-executed) and
nothing here is cited in the paper `.tex` as confirmatory evidence.

## Purpose

Probe whether the frozen SPPA-MVFit method (fit of a family-specific semantic
primitive graph to two silhouette views, top + side) generalizes from the
synthetic benchmark geometry to **real, independently sourced meshes**, using
the sealed inference code exactly as-is.

## Datasets (chosen before any evaluation — see `CLASS_MAPPING.md`)

| Source | Classes used | Why |
|---|---|---|
| **Objaverse v1** (`allenai/objaverse`, Hugging Face, LVIS annotations) | trailer_truck, bus, school_bus, horse, dog, cow, Christmas_tree, water_tower, clock_tower, motorcycle, bicycle | Not gated; per-object GLB meshes; LVIS class labels cover most SPPA families. |
| **ModelNet40** (HF mirror `naderalfares/ModelNet40`, test split, per-file OFF) | car, plant | Not gated; canonical z-up meshes for the two families Objaverse covers poorly. |

ShapeNet mirrors on Hugging Face were inspected and **discarded**: the
candidate repos were either gated or contained point clouds instead of meshes.

Per-file URLs, byte counts and SHA-256 hashes are frozen in
`manifest.json → downloads` (104 entries; 103 prepared, 52 selected).

### Licenses

- ModelNet40: provided for research use (see the Princeton ModelNet page); the
  HF mirror redistributes the same OFF files.
- Objaverse: the dataset is released under ODC-BY; individual objects carry
  their original CC licenses. **Limitation:** per-object licenses of the 92
  Objaverse objects used here were not individually retrieved; only the LVIS
  class label and uid were recorded (uids in `manifest.json`).

## Class → family mapping

Frozen in `CLASS_MAPPING.md` before evaluation:

| SPPA family | External classes | n |
|---|---|---|
| compact_vehicle | ModelNet40 `car` | 10 |
| articulated_vehicle | Objaverse `trailer_truck` (5), `bus` (2), `school_bus` (1) | 8 |
| quadruped | Objaverse `horse` (4), `dog` (3), `cow` (3) | 10 |
| branching_vertical | Objaverse `Christmas_tree` (4), ModelNet40 `plant` (4) | 8 |
| lattice_tower | Objaverse `clock_tower` (3), `water_tower` (5) | 8 |
| rider_cycle | Objaverse `bicycle` (4), `motorcycle` (4) | 8 |
| **Total** | | **52** |

Approximations: `lattice_tower` (clock/water towers are not lattice towers in
the synthetic-generator sense), `rider_cycle` (no rider), `branching_vertical`
(plants/trees). These are the closest public classes available.

## Preprocessing pipeline (scripts in `scripts/`)

1. **Orientation**: ModelNet40 used as-is (native z-up); Objaverse GLB rotated
   +90° about x (glTF y-up → z-up). Yaw chosen by PCA of the horizontal
   footprint (sign ambiguity ±180° unresolved — documented limitation).
2. **Metric scale**: per-class reference axis and target size (e.g. car →
   x = 4.4 m, water tower → z = 5.5 m; full table in `scripts/common.py`).
   Sizes are *declared*, not measured — a limitation.
3. Centered in xy, base at z = 0, inside the sealed world box
   (x ∈ [−4.8, 4.8], y ∈ [−3.2, 3.2], z ∈ [0, 6.4]).
4. **Observed masks**: triangles rasterized at 256², downsampled to 96² with
   the sealed `_downsample_any`, indexed as `top[x, y]`, `side[x, z]` at cell
   centers, exactly as the sealed generator.
5. **GT voxels (convention v3)**: `binary_closing` (1 iteration, 3³
   connectivity-1 structuring element) of the union of
   (a) a fine surface splat (`trimesh.voxelized(0.03)` remapped to the 64³
   benchmark grid) and (b) interior fill by ray parity along +y evaluated at
   the 64³ cell centers. Rationale: parity fill alone leaks through open or
   sub-cell geometry (billboard foliage, bicycle spokes, lattice members) —
   the main methodological finding of this sanity check. Residual bias
   remains for those classes (bicycle GT is extremely sparse, so IoU there is
   structurally low for every method).
6. **QC**: every candidate inspected on `qc/sheet_*.png` montages; cases with
   wrong class, grossly rotated yaw, broken or oversize meshes were rejected
   (reasons frozen per case in `manifest.json`).

## Evaluation

- Sealed API used verbatim: `infer_method` (`sppa_mvfit`, `generic_mvfit`,
  `sppa_text_only`), `baseline_occupancy` (`bbox`, `ellipsoid`, `capsule`,
  `billboard`, `nonsemantic_visual_hull`), `voxelize_actor`,
  `benchmark.metrics.voxel_iou` at 64³.
- Conditions: **clean** (primary, all 8 methods) and **mild_morphology**
  (robustness probe, `sppa_mvfit` + `generic_mvfit` only). The `_morph` /
  `case_seed` operators were re-implemented verbatim from the sealed
  `run_benchmark.py` (that module requires a `.git` checkout at import time and
  cannot be imported directly); morphology seed = `stable_jitter(case_id)`.
- 520 runs total: 52 × 8 clean + 52 × 2 mild, in `results/results.jsonl`.
- Statistics: bootstrap over cases, 10 000 resamples, seed 77157 (same value
  as the sealed protocol).

## Results (clean condition, voxel IoU, mean over cases)

| Method | compact | articulated | quadruped | branching | lattice | rider | **All** |
|---|---|---|---|---|---|---|---|
| **SPPA-MVFit** | **0.632** | **0.633** | **0.423** | **0.215** | **0.157** | **0.361** | **0.413** |
| Generic-MVFit | 0.508 | 0.319 | 0.393 | 0.382 | 0.288 | 0.288 | 0.370 |
| SPPA text-only | 0.449 | 0.188 | 0.242 | 0.058 | 0.101 | 0.172 | 0.213 |
| AABB | 0.577 | 0.593 | 0.386 | 0.244 | 0.368 | 0.259 | 0.411 |
| Ellipsoid | 0.613 | 0.527 | 0.496 | 0.369 | 0.470 | 0.398 | 0.485 |
| Capsule | 0.654 | 0.605 | 0.477 | 0.365 | 0.472 | 0.342 | 0.492 |
| Billboard | 0.164 | 0.070 | 0.256 | 0.111 | 0.077 | 0.333 | 0.172 |
| Visual hull | 0.809 | 0.783 | 0.715 | 0.462 | 0.581 | 0.530 | 0.656 |

Global 95 % bootstrap CIs: SPPA-MVFit 0.413 [0.359, 0.467]; Generic 0.370
[0.335, 0.405]; Visual hull 0.656 [0.606, 0.704].

- **Paired SPPA − Generic: +0.043 [−0.007, +0.094]** (n = 52).
- **Paired SPPA − Visual hull: −0.243 [−0.285, −0.203]** (n = 52).
- Robustness (mild morphology): SPPA 0.380 [0.331, 0.429], Δ = −0.033 vs
  clean; Generic 0.357 [0.324, 0.390], Δ = −0.013.
- Mean inference time: SPPA ≈ 9.8 ms/case, Generic ≈ 11.9 ms/case.

Booktabs version: `external_sanity_table.tex`; full machine-readable summary:
`external_sanity.json`.

### Comparison with the sealed internal test (synthetic geometry)

Internal clean means (240 actors): SPPA 0.557, Generic 0.367, Visual hull
0.522; primary endpoint SPPA − Generic = +0.190 [0.181, 0.199], H1
(superiority margin 0.03) passed internally.

Externally: SPPA drops to 0.413 (−0.144), Generic is unchanged at 0.370
(+0.003), Visual hull rises to 0.656 (+0.134). The paired advantage shrinks to
+0.043 with a CI that includes 0, so **the internal superiority margin does
not replicate on real meshes at n = 52**: SPPA still wins clearly in the two
vehicle families and ties on quadrupeds, but loses to Generic in
branching_vertical (0.215 vs 0.382) and lattice_tower (0.157 vs 0.288) —
families whose real instances are dominated by thin/open geometry that the
semantic template under-covers and the GT voxelization itself struggles with.
Reported as-is; this is information, not a protocol failure.

## Main observed failure modes

1. **Template–instance mismatch in lattice_tower**: Objaverse `water_tower`
   includes horizontal-tank layouts whose side silhouette is a wide lattice
   deck, not a vertical column (see
   `qualitative/lattice_tower-objaverse-water_tower-02.png`, SPPA IoU 0.118).
2. **Thin/open geometry** (tree foliage as billboard cards, bicycle spokes,
   lattice members): ray-parity GT fill leaks, requiring the v3 closing
   convention; residual sparsity still depresses all IoUs in those families.
3. **LVIS mislabels**: `horse-02` is actually a giraffe — kept as an honest
   OOD case and flagged here.
4. **Yaw ambiguity**: several candidates had grossly rotated yaws after PCA
   alignment and were rejected at QC; the ±180° sign ambiguity remains
   unresolved for the kept cases.
5. **Non-semantic upper bound**: the two-view visual hull is very strong on
   real silhouettes (0.656) and beats every fitting method globally, unlike in
   the synthetic benchmark — consistent with real masks being cleaner and more
   informative than the synthetic ones.
6. Download-level failures: one empty GLB (motorcycle-05), one oversize GLB
   (bus-00, > 60 MB); both replaced by backfill candidates.

## Seeds and reproducibility

- Case-selection RNG: seed 20260718. Bootstrap: seed 77157, 10 000 resamples.
- Morphology probe seed: `stable_jitter(case_id)` (SHA-256 of the case id).
- Checkpoint state: `manifest.json` (`steps`, per-case status, download
  hashes).
- Scripts (run order): `download_meshes.py` → `backfill_download.py` →
  `prepare_cases.py` → `probe_orientation.py` → `make_qc_montage.py` →
  `revoxelize_gt.py` → `evaluate.py` → `analyze.py` → `make_qualitative.py`
  (support: `common.py`, `mesh_lib.py`).
- Environment: CPython 3.12 (user install), `PYTHONUTF8=1`; `pip --user`
  additions: `objaverse 0.1.7`, `fast-simplification`, `rtree 1.4.1`.

## Files

| Path | Content |
|---|---|
| `external_sanity.json` | full statistics (means, CIs, paired diffs, robustness, timings) |
| `external_sanity_table.tex` | booktabs table of the clean results |
| `CLASS_MAPPING.md` | pre-registered dataset choice and class mapping |
| `CHANGELOG.md` | deviations from the pre-registration |
| `manifest.json` | checkpoint: downloads (URL/SHA-256), per-case status, steps |
| `results/results.jsonl` | 520 evaluation rows |
| `cases/*.npz` | per-case `top`, `side`, `gt` arrays + metadata + normalized OBJ |
| `qc/sheet_*.png` | QC montages used for selection |
| `qualitative/*.png` | observed masks vs SPPA actor render vs GT projections |
