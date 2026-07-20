# E14 — Simulated-LiDAR degraded-sensing protocol (FROZEN before any outcome)

Experiment: **E14 LiDAR Twin Wave** — exploratory post-hoc analysis (NOT confirmatory).
Date frozen: 2026-07-20. Author: kimi-code subagent.

Narrative under test: when the camera is useless (night / fog / smoke), a
LiDAR-class sensor still yields detections, and the SAME reconstruction
contract (oriented ground footprint + height anchor -> sealed SPPA-MVFit
production mode, locked 31-candidate budget) must produce a faithful proxy.

## Declarations (binding)

- **SIMULATED LiDAR-class returns.** Points are line-raycast hits inside
  Unreal Engine 5.7 PIE on the Ejea twin. This is NOT hardware LiDAR data and
  no hardware truth is claimed.
- **No camera anywhere in the perception path.** RGB is never rendered, read,
  or used. (One optional viewport screenshot is illustrative only and is not
  an input to any metric.)
- **Positions locked to GT.** The reconstruction window is centered on the
  exact GT tower anchor (from `oblique_twin_wave/gt/tower_geometry.json`).
  Detection provides SHAPE only (footprint dimensions + yaw, height). This
  mirrors the operational assumption of a localized detection (GNSS-locked);
  the experiment tests the reconstruction contract, not localization.
- **Reconstruction-only scope.** No detection benchmark, no tracking.
- The sealed fitter
  (`paper_semantic_proxy_3d/reproducibility/sppa_mvfit/method/sppa_mvfit.py`)
  is imported READ-ONLY; per-case `mv.WORLD` / `mv.GRAPHS` are monkeypatched
  in memory only, exactly as in E7 (`real_stream_wave`). Nothing under
  `reproducibility/` is modified. No UE project code/config is modified; only
  new scripts under `Unreal/Scripts/` and outputs here.
- If results are poor, they are reported as-is.

## Cases

- 11 towers: t0,t1,t2,t3,t4,t5,t7,t9,t10,tower12,tower13 (GT anchors from
  `oblique_twin_wave/gt/tower_geometry.json`; welded LOD0 mesh
  `gt/tower_mesh_Internal.obj`, 1615 v / 4048 f, Y-up OBJ, cm, pivot at base).
- Family token: `lattice_tower` for every tower, **declared a priori** (the
  scene objects are transmission lattice towers; no detector supplies the
  token — same declared-mapping role as E7's CLASS_TO_FAMILY).
- Sensor origins per tower (frozen subset of the 28 manifest poses in
  `oblique_twin_wave/manifest.jsonl`): ring `oblique30` azimuths
  {0, 90, 180, 270} deg + `nadir` az000 → **5 scans/tower, 55 scans total**.
- Arms: `clean` and `degraded` (heavy-fog honesty arm). Both arms are derived
  offline from the SAME raw returns (deterministic, frozen seeds) so the arm
  comparison is exactly paired.

## Sensor model (SIMULATED, frozen)

In-PIE per scan (origin = manifest `camera_world`, aim = manifest
`look_at_target_world` = tower AABB centre):

- Ray fan: local spherical grid centred on the aim direction.
  Azimuth offsets: linspace(-60 deg, +60 deg, 361) (0.333 deg step).
  Elevation offsets: linspace(-25 deg, +25 deg, 16) (3.333 deg step).
  → 5776 rays/scan, 317,680 rays total.
- `UKismetSystemLibrary::LineTraceSingle` (visibility channel, complex
  collision OFF unless the smoke probe shows the tower mesh needs it),
  UE trace length 500 m. First blocking hit = the return (LiDAR-like).
- Raw record per return: world hit xyz (cm), travel distance (cm), hit actor
  name. Misses recorded as counts only.

Offline degradation (declared here, applied in post with frozen seeds — this
keeps the two arms exactly paired and the whole experiment byte-reproducible
without re-running UE):

- `clean` arm: per-return dropout p=0.05; range noise sigma=2 cm along the
  ray; max range 150 m; seed 14001.
- `degraded` arm: per-return dropout p=0.50; angular downsample x4 in azimuth
  (every 4th column) and x2 in elevation (every 2nd layer) -> 728 rays/scan;
  range noise sigma=5 cm; max range 100 m; seed 14002.

## Detection model (GT-free, frozen)

Per tower and arm, all returns of its 5 scans are merged in the ACTOR-LOCAL
frame (full actor quaternion inverse; z up, metres, pivot at base):

1. Vertical-structure clustering: rasterize XY at 1 m cells; a cell is a
   STRUCTURE cell if its point z-range >= 5 m; 8-connected components; the
   component with the most points = tower cluster. Tower points = every
   return falling in those cells.
2. Ground z = 10th percentile of tower-point z. Height h = max z - ground z.
3. Footprint: PCA on XY of tower points with z <= ground + 0.25*h.
   centre = mean XY; axes = PCA eigenvectors; length/width = min-max extent
   along the axes (clamped >= 0.3 m); yaw = major-axis angle in the actor
   frame.
4. Observation object = the E7 footprint dict (centre NE, length_m, width_m,
   orientation_deg_axial, 4 corner points) + height_m, re-expressed in the
   per-case window frame. Position is then LOCKED to GT (see below): only
   length/width/yaw/height survive into the observation.

## Reconstruction (E7 machinery, read-only import)

- Window: `run_e7_real_stream.case_window(fp_len, fp_wid, h, 'lattice_tower')`,
  centred on the GT-locked position = actor-local mesh-centre XY
  (anchor + `pivot_to_bounds_origin_offset.xy`), z0 = anchor base z (pivot).
  Window x-axis = actor-local x. (Position lock = the declared GT input.)
- Observation masks: E7 `rasterize_masks` (top = observed footprint rect at
  the observed yaw about the window centre; side = height profile).
- Methods (identical input, E7 set): `sppa_mvfit`, `generic_mvfit`, `obb`,
  `aabb`, `visual_hull`, `capsule`. SPPA/generic run the sealed coordinate
  descent via E7 `fit_top_only` (31 candidates, 5 parameters, frozen BOUNDS;
  z-scale anchored to the LiDAR height estimate — the production top-only
  mode). `mv.GRAPHS` scaled per family via E7 `scaled_graphs_for_family`
  (nominal 25 m lattice tower; in-memory only).

## Scoring (frozen)

- GT occupancy: `tower_mesh_Internal.obj` transformed to actor-local metres
  (OBJ (x,y,z) = Unreal local (x,z,y), cm->m) and voxelized solid at 64^3 in
  the SAME per-case window via +z ray casting (even-odd fill, vectorized
  Moeller-Trumbore, chunked). Computed once per tower (window dims depend on
  the observed footprint, so once per tower x arm).
- Primary metric: **3D voxel IoU** method-occupancy vs GT occupancy, 64^3,
  per (tower, arm, method).
- Secondary: top-down footprint IoU (proxy z-projection vs GT z-projection).
- Stats per arm x method over the 11 towers: mean, median, bootstrap 95% CI
  of the mean (10,000 resamples, seed 77157, matching the sealed PROTOCOL
  bootstrap constants).

## Resumability

`results.jsonl` rows are keyed by (tower_id, arm, method); the runner skips
existing keys. `points.jsonl` rows are keyed by (tower_id, frame_id); the UE
capture skips existing frame_ids. A rerun with the full 28 poses/tower only
requires changing POSE_SUBSET and resuming.

## Optional illustrative evidence

One PIE viewport screenshot with exponential height fog spawned as a
TRANSIENT actor (destroyed afterwards / vanishes with PIE). Illustrative
only; if it costs >15 min it is skipped — metrics matter, not beauty.

## Amendment A1 (2026-07-20, before any method-level outcome was known)

Frozen-plan corrections found by sanity diagnostics on the FIRST run (only
GT voxel counts and detection stats had been inspected; no method score was
used to choose these changes):

1. **GT voxelization model.** The frozen even-odd solid fill is the wrong
   model for this mesh: the tower is a THIN-BEAM LATTICE (mostly-air
   structure, not a watertight solid), and a vertical ray runs parallel to
   most members, so column casting undersamples catastrophically (26 filled
   voxels out of 64^3). Amended: GT occupancy = **surface-intersection
   occupancy** — a voxel is occupied iff the mesh surface passes through it,
   implemented by barycentric sampling of every triangle at <= 0.4 x the
   finest window pitch and marking the containing voxels. This matches how
   the fitter's own lattice graph voxelizes (union of thin solid boxes) and
   is the honest "material present" truth for a lattice.
2. **Detection ground percentile.** ground_z = p10 of cluster z
   systematically overestimates the base (~2-3 m) because lattice returns are
   near-uniformly distributed along the height, biasing every height
   estimate low. Amended: ground_z = **2nd percentile** of tower-point z
   (robust to the declared 2-5 cm range noise).

## Known limitations (declared a priori)

- Raycast returns are geometrically exact (before the declared offline
  noise); real LiDAR has beam divergence, multi-return, material-dependent
  reflectivity and motion distortion — none modelled.
- Terrain comes from Cesium tiles; tile collision must be streamed in (PIE
  settle + load_progress gate). Missed terrain only costs background points.
- Oblique scans see one-sided surfaces; the footprint PCA is fed by the
  merged 4-azimuth + nadir shell, which is why the pose subset spans 4
  azimuths.
