# E14 — LiDAR Twin Wave (simulated-LiDAR degraded-sensing demonstration)

Exploratory post-hoc experiment for the SPPA-MVFit paper. **SIMULATED
LiDAR-class returns** (line raycasts inside Unreal Engine 5.7 PIE on the
Ejea twin) — NOT hardware. **No camera anywhere** in the perception path.
**Positions locked to GT**; reconstruction-only scope. Protocol frozen before
any outcome in `E14_PROTOCOL.md` (incl. documented Amendment A1).

## Question

When the camera is useless (night / fog / smoke), can a LiDAR-class sensor
still feed the SAME reconstruction contract — oriented ground footprint +
height anchor -> sealed SPPA-MVFit production mode — and produce a faithful
proxy of the 11 Ejea transmission towers?

## Sensor model (declared, simulated)

- Origins: 5 poses/tower from `oblique_twin_wave/manifest.jsonl` (oblique30°
  ring az {0,90,180,270} + nadir at +60 m), 55 scans.
- Ray fan per scan: azimuth linspace(±60°, 361) x elevation
  linspace(±25°, 16) about the aim direction (5776 rays), UE
  `LineTraceSingle` (visibility channel, simple collision), first blocking
  hit = return, UE cap 500 m. 317,680 rays fired; 316,149 raw hits.
- Raw hits are exact; degradation is applied offline with frozen seeds so
  both arms are exactly paired:
  - `clean`: dropout 5%, range noise sigma=2 cm, max range 150 m.
  - `degraded` ("heavy fog"): dropout 50%, angular downsample x4 az / x2 el
    (728 rays/scan), noise sigma=5 cm, max range 100 m.

## Detection (GT-free)

Merged per tower in the actor frame: vertical-structure clustering (1 m XY
cells with z-range >= 5 m, 8-connected, largest component), ground = p2 of
cluster z (Amendment A1), height = max z - ground, footprint = PCA min-max
rect on the lowest 25% points. Only length/width/yaw/height reach the
fitter; the window is locked to the GT anchor.

## Reconstruction and scoring

Sealed fitter read-only (`reproducibility/sppa_mvfit/method/sppa_mvfit.py`,
per-case `mv.WORLD`/`mv.GRAPHS` in memory, E7 top-only production mode,
31 candidates, frozen bounds) + E7 baselines (generic, OBB, AABB, visual
hull, capsule). GT = welded tower LOD0 OBJ voxelized as surface occupancy
at 64³ in the per-case E7 window (Amendment A1: the lattice is a thin-beam
structure; even-odd solid fill is not applicable). Primary metric: 3D voxel
IoU; bootstrap 95% CIs (10k, seed 77157).

## Honest notes (read before citing)

- **Voxel-exact 3D IoU is ~0.08 for EVERY method.** The tower is mostly
  air: GT occupancy is ~1,100 of 262,144 voxels, so even the OBB's
  structural ceiling is |GT|/|OBB| ~= 0.08. The metric at 64³ is dominated
  by sub-voxel member placement; two different lattice realisations almost
  never coincide voxel-exactly. SPPA-MVFit does NOT beat the baselines on
  this truth (clean: SPPA 0.081 [0.076-0.086], generic 0.084, capsule 0.083).
- What the camera-less path DOES recover reliably: footprint 7.9 x 4.0 m vs
  GT 7.42 x 3.43 m (all 11 towers), yaw within ~6°, height within ~5%
  (median), footprint-IoU ~0.43. With 1-voxel tolerance (post-hoc
  supplementary, labeled in `e14_analysis.json`): SPPA 0.168, capsule 0.190.
- SPPA is the most *economical* proxy: ~2.8k occupied voxels vs OBB's 14.3k
  at comparable IoU (voxel precision 10.5% vs 6.7%) — i.e., SPPA's mass
  lands on structure, the box's mass is mostly air. That is the honest
  version of the advantage here.
- **Graceful degradation is measured, not assumed:** at 50% dropout + 4x2
  angular downsample, 4/11 towers are LOST to detection failure (the real
  cost); survivors are pairwise comparable to clean (paired deltas in
  `e14_analysis.json`; degraded-arm means suffer survivor bias — use the
  paired table).
- UE simple-collision hulls stand in for laser returns; beam divergence,
  multi-return, reflectivity and motion distortion are not modelled.

## Files

- `E14_PROTOCOL.md` — frozen protocol + Amendment A1.
- `points.jsonl` — 55 rows (one per scan): raw exact returns, resumable key
  `frame_id`.
- `results.jsonl` — one row per (tower, arm, method); resumable.
- `e14_analysis.json` — per arm x method IoU/precision/recall + CIs, paired
  deltas, supplementary 1-voxel-tolerant IoU.
- `e14_table.tex` — booktabs table (clean vs degraded x method).
- `fig_e14_lidar.png` — (a) returns on tower t3, (b) footprint+proxy vs GT
  top silhouette, (c) IoU bars by arm.
- `fig_e14_fog_pie.png` — illustrative PIE viewport. A transient
  ExponentialHeightFog actor (density 0.15) was spawned in the PIE world,
  but the game mode re-possesses its pawn every frame, so the viewport
  could not be detached to the tower pose; the shot shows the standard PIE
  flight view. Illustrative only; no metric depends on it.
- `e14_detect_dump.json` — per tower/arm cluster points + observation
  (used by the figure).
- `capture_status_e14.json` — UE-side capture status (55/55, probe actors).
- `RUN_LOG.md` — chronological run log.
- `run_e14_lidar_wave.py`, `make_e14_outputs.py` — offline pipeline
  (degradation, detection, fitting, scoring, outputs).
- `Unreal/Scripts/e14_lidar_scan_pie.py` — in-PIE capture (tick-driven,
  resumable).

## Reproduce / resume

1. Editor + PIE: launch `UnrealEditor.exe Unreal/AirTraffic.uproject
   /Game/Ejea`, `control_editor play` via `tools/unreal_mcp_call.py`, then
   `system_control execute_python` with
   `Unreal/Scripts/e14_lidar_scan_pie.py` (skips existing `frame_id`s;
   Cesium gate: load_progress >= 99).
2. Offline:
   `python run_e14_lidar_wave.py` then `python make_e14_outputs.py`
   (both resumable/idempotent; delete `results.jsonl` to refit).
3. Full 28-pose coverage: extend `POSE_SUBSET` in the capture script and
   rerun (points.jsonl is append-only).
