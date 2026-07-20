# E11 "Oblique Twin Wave" — Analysis Protocol (FROZEN before any outcome)

Status: **frozen** on 2026-07-20, before running detection, fitting, or scoring.
Label: *exploratory post-hoc analysis (not confirmatory)*.

E11 measures **reconstruction fidelity across view angles**: 308 captured twin
frames (640×640, FOV 70°) of 11 real lattice towers of the Ejea map, arranged
in three view rings per tower — `oblique30` (12 azimuths, elevation 30°,
slant radius 35 m), `oblique45` (12 azimuths, elevation 45°, slant 35 m) and
`nadir` (4 azimuths, +60 m above the pivot) — 28 poses × 11 towers.

## 1. Scope declarations (frozen)

- **Positions are LOCKED to ground truth.** The evaluation window origin is
  the tower's exact simulator pivot (globe anchor), z=0 at pivot height.
  No position is ever estimated from the observation; localization is out of
  scope (it is the subject of another paper). **No localization metric is
  computed or claimed.** An assertion in the code checks the window center
  offset from the GT pivot is exactly zero.
- **Hybrid evidence**: simulated imagery (UE 5.7 digital twin) + a real
  trained detector (YOLO) + exact simulator GT. Declared as such; not claimed
  as field evidence.
- Detector errors are kept as the **natural condition**: every detection at
  conf ≥ 0.10 is evaluated, with the family token taken from the detector
  label (`biker→rider_cycle`, `cow→quadruped`, `tower→lattice_tower`, the
  fixed a-priori E7 mapping). Wrong tokens are flagged (`token_correct`)
  and counted, never cleaned.

## 2. Inputs (all verified on disk before freezing)

- Frames + manifest: `frames/*.png` (308), `manifest.jsonl` (per frame:
  frame_id, tower_id, ring, azimuth, camera LLH + world loc/rot
  euler+quaternion, look_at, agl_m, fov).
- Exact GT: `gt/tower_geometry.json` (11 towers: world loc/quat, bounds,
  globe-anchor LLH) and the welded real mesh `gt/tower_mesh_Internal.obj`
  (1615 v / 4048 f; OBJ (x,y,z) = Unreal local (x,z,y), centimeters, +Y up —
  per `obj_notes`).
- Detector: `yolo/weights/yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt`
  (classes biker/cow/tower), conf = 0.10, imgsz = 640 (identical to E7).
- Sealed fitter (read-only import): `reproducibility/sppa_mvfit/method/sppa_mvfit.py`.
- E7 machinery (read-only import, unmodified): `benchmarks/real_stream_wave/e7_common.py`,
  `benchmarks/real_stream_wave/run_e7_real_stream.py`.

## 3. Observation model (identical construction to E7, view geometry from manifest)

Per detection, ONE observation, identical input for every method:

- **View geometry**: the manifest camera euler is converted to the pipeline's
  NED telemetry convention as
  `yaw_ned = (unreal_yaw + 90) mod 360`, `pitch_ned = unreal_pitch`,
  `roll_ned = −unreal_roll` (roll is 0.0 in every captured frame), with camera
  mount angles 0/0/0, VFOV 70°, `alt_agl = manifest.agl_m`,
  `max_range_m = 80`, `clamp_to_max_range = false` (E7 camera constants).
  *Verified before freezing*: with this mapping, `GeoProjector.pixel_to_ray_ned`
  reproduces the exact manifest-quaternion forward ray to < 1e-3 deg on a
  sampled subset of frames, and the look-at target projects to the image
  center to < 0.01 px.
- **Oriented ground footprint**: `GeoProjector.bbox_to_ground_footprint_m` on
  the raw detector bbox (8 perimeter points → ground plane → PCA oriented
  rect: center, length, width, axial orientation). Gates identical to E7:
  length, width ≥ 0.05 m.
- **Monocular height**: line-by-line port of the pipeline estimator
  (`e7_common.estimate_height_m`): ray through bbox top-center aligned in
  least squares to the vertical line over the projected bbox bottom-center
  base point; `height = AGL − ray_down·t`; gate `height ≥ 0.10 m`.
- Observations that fail any gate are excluded and counted
  (`observation_failed`); no case rows are written for them. This is the
  expected failure mode at exact nadir (vertical rays carry no height
  signal) and is reported honestly if it occurs.

## 4. Fit at the LOCKED position

- Per-case metric window: E7 `case_window(fp_len, fp_wid, height, family)`
  (x = footprint major axis, z up from local ground), **centered on the
  locked GT pivot** — the observation contributes *shape only* (footprint
  length/width/orientation, height); its center is asserted to be the GT
  pivot. If the GT mesh window-frame AABB would stick out of the window
  (possible for wrong family tokens with small nominal sizes), the window is
  enlarged symmetrically to contain it plus one cell; the enlargement is
  identical for every method of the case (equal conditions preserved).
- Observation masks: E7 `rasterize_masks` (top = footprint rect, side =
  height profile, 96×96, `OBS_RES`).
- Methods (E7 `run_method` verbatim, same per-case window and masks):
  - `sppa_mvfit`: sealed frozen coordinate descent (31 candidates, 5
    parameters, frozen BOUNDS) in operational **top-only + height-anchor**
    mode (x/y fitted on the footprint mask; z-scale anchored to the
    monocular height within frozen bounds), family token from the detector.
  - `generic_mvfit`: same fitter, generic graph.
  - `obb`: oriented box (footprint length × width × height).
  - `aabb`: NE-axis-aligned box of the footprint points × height.
  - `visual_hull`: sealed `baseline_occupancy("nonsemantic_visual_hull")`.
  - `capsule`: sealed `baseline_occupancy("capsule")`.
- In-memory monkeypatch style identical to E7 (`mv.WORLD`, `mv.GRAPHS`
  per-case metric copies); nothing under `reproducibility/` is written.

## 5. Exact-GT voxelization

- Welded OBJ → meters, Unreal-local frame → rotate by the tower's exact
  world quaternion → local NE frame relative to the pivot
  (East = +ux, North = −uy, Up = +uz; mapping verified from tower-pair
  baselines and camera rays) → per-case window frame (rotation by the
  footprint bearing around z).
- Solid voxelization at the E7 eval grid (64³) in the per-case window:
  conservative surface marking (per-triangle candidate cells from the
  triangle AABB; plane–box overlap test; closest-point-on-triangle within
  the cell half-diagonal) followed by `scipy.ndimage.binary_fill_holes`
  (enclosed-interior fill; the tower is an open lattice, so this is the
  declared "enclosed-solid" convention, standard for voxel-IoU benchmarks).
- Sanity (reported): GT voxel occupancy is non-trivial for every case;
  surface vs filled voxel-count statistics are logged.

## 6. Metrics

(a) **Per-detection 3D voxel IoU** vs exact GT, per case × method:
    `|occ ∩ gt| / |occ ∪ gt|` on the 64³ grid in the per-case window.
(b) **Cross-view consistency** per tower:
    - Canonical per-tower window: bearing 0 (x = North, y = East, z up from
      the pivot), extents from `case_window` with the GT AABB dims and the
      `lattice_tower` family (fixed per tower, declared, identical for all
      views and methods of that tower).
    - Each fitted proxy is re-expressed in the canonical frame: actor
      methods (sppa, generic, obb, aabb) exactly, by evaluating the sealed
      `_primitive_occupancy` on grid points rotated into the case frame;
      voxel methods (visual_hull, capsule) by nearest-neighbor resampling of
      the case occupancy into the canonical frame (declared approximation,
      affects only consistency, not metric (a)).
    - One proxy per frame: the highest-confidence tower-token detection.
      Consistency is computed on tower-token detections only (wrong tokens
      are analyzed separately under (d)).
    - Pairwise IoU between proxies fitted from different views: all pairs
      within `oblique30`, all pairs within `oblique45`, and nadir-vs-oblique
      pairs (both oblique rings pooled); reported per tower and pooled.
    - Fitted-parameter spread: per-tower std of `exp(theta[0..2])` (metric
      scales) and of `theta[3..4]` across views.
    - **Consensus proxy** per tower: elementwise median theta across the
      tower's views → actor → voxel IoU vs GT in the canonical window
      (reported per tower and pooled).
(c) **Breakdowns** of (a) by ring and by tower.
(d) **Wrong tokens**: count, rate per ring, and their (a)-scores, flagged.

## 7. Statistics

- Paired bootstrap 95% CIs, 10 000 resamples, **seed 20260720**
  (`numpy.random.default_rng(20260720)`), resampling cases within each ring
  jointly across methods (paired design: all methods share the same cases).
- Reported: per ring × method mean and median 3D IoU with bootstrap CI of
  the mean; paired differences SPPA − baseline with CI; consistency means
  with CI over towers/pairs as applicable.

## 8. Outputs (all new files under `benchmarks/oblique_twin_wave/`)

- `detections.jsonl` — one row per detection (frame_id, det_index, class,
  confidence, bbox).
- `results.jsonl` — one row per case × method (resumable: existing case_ids
  are skipped on rerun), including theta, voxel IoU, token flag, latency.
- `e11_analysis.json` — full aggregate (per-ring, per-tower, consistency,
  spread, consensus, wrong-token arm, sanity stats).
- `e11_main_table.tex` — booktabs table: per ring × method mean/median 3D
  IoU [95% CI], plus the cross-view consistency row (SPPA vs best baseline).
- `fig_e11_oblique.png` — panels: (a) two sample frames with detections
  marked; (b) 3D IoU by ring, SPPA vs baselines; (c) cross-view consistency
  per tower; (d) an oblique frame with the fitted SPPA proxy reprojection.
- `README.md` — how to reproduce/resume.

## 9. Sanity checks (asserted in code)

1. Every detection joins to exactly one manifest frame and its tower.
2. GT voxel occupancy non-trivial in every case window.
3. Locked-position invariant: window center offset from the GT pivot == 0;
   no code path estimates position (no `match_gt`, no footprint-center
   placement).
4. Fit budget drift check inherited from the sealed fitter (31 candidates).
