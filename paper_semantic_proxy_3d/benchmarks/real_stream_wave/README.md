# E7 — Real Stream Wave (exploratory post-hoc, NOT sealed)

**Status:** exploratory post-hoc analysis. It is *not* part of the sealed,
preregistered benchmark suite and must be cited as exploratory. Nothing outside
`benchmarks/real_stream_wave/` is written by these scripts.

**Motivation.** Reviewer weakness #1: every sealed endpoint of SPPA-MVFit is
synthetic/internal. E7 evaluates the **sealed fitter** on a **real recorded UAV
vision stream** with the **real detector**, under equal conditions for every
method, with no cherry-picking: every accepted detection in the stream becomes
a case.

## Data sources (all read-only)

| Asset | Path |
|---|---|
| Stream events | `D:\Deep-AeroTwin-UE57-Test\pipeline\logs\zero_trust\20260620_084932\vision\events.jsonl` (4184 lines; 2788 `vision_frame` events) |
| Frames | `...\vision\frames\` (1394 JPG 640×640, even frames) |
| Geo projection | `D:\Deep-AeroTwin-UE57-Test\pipeline\geo_projector.py` (pinhole + mavlink attitude, VFOV 70°, mount pitch −25°, max range 80 m — values verified against `porce_defaults.env` and the `vision_config` event) |
| Exact static GT | `D:\Deep-AeroTwin-UE57-Test\pipeline\logs\ejea_spawn_state_latest.json` (Cesium globe anchors) |
| Sealed fitter | `reproducibility/sppa_mvfit/method/sppa_mvfit.py` (reused read-only; graphs/WORLD patched **in memory only**, same monkeypatch style as E1–E6) |

Flight: digital-twin sortie over Ejea (Navarra), 2026-06-20 06:49 UTC,
takeoff at the Cesium origin, low cruise (**AGL 10–23 m**; no frame exceeds
23 m AGL), 944 frames with detections after telemetry lock.

## Design (equal conditions, auditable)

1. **One observation per accepted detection**, identical for all methods:
   - *Oriented ground footprint*: `GeoProjector.bbox_to_ground_footprint_m`
     on the raw detector bbox (8 perimeter points → ground plane via pinhole +
     mavlink attitude + AGL; PCA oriented rect: centre, length, width, yaw).
   - *Height estimate*: line-by-line port of the pipeline's own monocular
     estimator (`vision_system._estimate_height_m_from_bbox`): ray through the
     bbox top-centre aligned in least squares to the vertical line over the
     projected bottom-centre base point.
   - *Family token* from the **real detector label**: `biker→rider_cycle`,
     `cow→quadruped`, `tower→lattice_tower`. Detector errors are **not
     cleaned**; they are reported as a natural condition (token arm below).
2. **Case gates** (declared, from the pipeline's own operational rules):
   telemetry locked (lat/lon ≠ 0), AGL ≥ 10 m (the pipeline's publish gate),
   observation construction succeeds. Exclusions: 271 below-AGL detections,
   32 observation failures, 0 telemetry-unlocked, 0 unmapped classes.
   → **1902 cases** (308 tower, 848 cow, 746 biker detections).
3. **Methods on the same observation**: SPPA-MVFit (operational top-only mode:
   x/y fitted on the footprint mask, z-scale anchored to the monocular height
   estimate within the frozen bounds), Generic-MVFit (same fitter, generic
   graph), OBB, AABB, visual hull, capsule. Both MVFits use the **frozen
   coordinate descent: 31 candidates, 5 parameters, frozen BOUNDS**, identical
   budget. Occupancy for metrics is voxelized at 64³ in a per-case metric
   window centred on the footprint (window sized from the observation with
   headroom for the frozen scale bounds; identical for all methods).
4. **Metric scaling of the frozen graphs** (declared a priori, not fitted to
   any GT): per-family nominal height maps the scale-normalized graphs to
   metres — lattice tower 25 m, quadruped 1.5 m, rider cycle 1.8 m. Reachable
   real sizes = nominal × [0.55, 1.80] (frozen bounds).
5. **GT association**: exact simulator anchors (11 towers + 1 cow found in the
   spawn state — see deviations). Nearest anchor within a declared
   class-specific radius: tower 40 m, cow 10 m (radii declared; t0↔cow anchors
   are ~34 m apart so no cross-matches are possible).
6. **Metrics**: (a) 3D centroid error of the fitted proxy vs the GT anchor
   (vertical reference: anchor height + nominal family height/2);
   (b) footprint IoU in plan vs a **declared** GT base (tower 5×5 m, cow
   2.2×0.9 m, oriented by the anchor's world yaw — base dimensions are not in
   any log; declared, not measured); (c) 2D reprojection IoU: occupied voxel
   centres reprojected through the **real** camera model and compared with the
   real detector bbox (splat → 5×5 closing → fill holes, identical for all);
   (d) latency per case.

## Deviations from the original tasking (found during auditing)

1. **11 tower anchors, not 14.** The spawn state contains t0–t5, t7, t9, t10,
   tower12, tower13 (+ cow + markers A/B). t6, t8, t11 have no anchor in the
   file. The peloton audit log mentions `tower_count: 42`/`cow_count: 8`, but
   that is a different scene census; the designated GT source is the spawn
   state, so GT = 11 towers + 1 cow.
2. **The cow is never detected at its anchor.** 0/571 cow detections have the
   cow anchor reprojected inside the bbox (sanity check). The actor is
   *animated* (`cowanimateduntitled`) and may have wandered. Consequently the
   cow class has **no valid 3D GT**: all 114 GT-matched cow detections are
   matched to *tower* anchors (wrong token). 3D-GT metrics exist only for
   towers (79 token-correct matches).
3. **Peloton audit log contains no positions** (route metadata only: 18 loops
   of 96 m). No per-frame or audit-time biker GT is recoverable → bikers are
   evaluated with the 2D reprojection metric only, as tasked.
4. **No segmentation weights.** `yolo/weights/` contains only the detection
   model (`yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt`); no
   `yoloe*seg*.pt` exists. Declared fallback: the detector bbox is the mask
   for the 2D reprojection IoU.
5. **Detector errors are real and kept**: 138/217 GT-matched cases carry a
   wrong family token (114 cow→tower, 24 biker→tower). These pollute nothing —
   they are reported as the token arm.

## Results (n = 1902 cases; loc./footprint on the 217 GT-matched)

| Method | Loc. err. 3D med [P25,P75] (m) | Footprint IoU | 2D reproj. IoU med [P25,P75] | Latency (ms) |
|---|---|---|---|---|
| SPPA-MVFit | 32.76 [27.86, 37.39] | 0.000 | 0.298 [0.218, 0.392] | 11.82 |
| Generic-MVFit | 32.75 [27.67, 37.29] | 0.000 | 0.423 [0.394, 0.448] | 13.44 |
| OBB | 32.71 [27.73, 37.16] | 0.000 | 0.446 [0.398, 0.492] | 0.22 |
| AABB | 32.66 [27.73, 36.44] | 0.000 | 0.330 [0.299, 0.357] | 0.25 |
| Visual hull | 32.71 [27.73, 37.16] | 0.000 | 0.446 [0.398, 0.493] | 0.50 |
| Capsule | 32.71 [27.73, 37.16] | 0.000 | 0.445 [0.422, 0.466] | 1.31 |

Token arm (SPPA-MVFit, 138 wrong-token matched cases): 2D reproj. IoU with the
**real (wrong) token 0.381** [0.303, 0.410]; **correct-token refit 0.025**
[0.023, 0.034].

Per-class 2D reproj. IoU medians (SPPA / Generic / OBB / AABB / hull /
capsule): tower 0.142/0.295/0.422/0.164/0.423/0.453;
cow 0.398/0.429/0.450/0.341/0.450/0.449;
biker 0.252/0.428/0.453/0.329/0.453/0.438.

## Key findings (reported as-is, no favourable selection)

1. **Localization is observation-bound.** Fitted-centroid 3D error ≈
   footprint-centre→anchor distance for every method (fig. panel d, y=x).
   Median ≈ 33 m because the flat-ground monocular projection compresses
   ranges: the drone cruises at 10–23 m AGL while the tower line sits ~12 m
   *below* the local ground plane under the drone (terrain relief), so
   distances are compressed by the ratio AGL/height-above-target-base
   (e.g. f478: true t0 base at 91 m → projected at 25–49 m). This is the real
   operational condition of the pipeline, not a fitter defect, and it hits all
   methods identically.
2. **Footprint IoU is degenerate (median 0 everywhere).** With ≈33 m
   observation bias and a 5×5 m declared GT base, overlap is almost always
   empty. Kept in the table for honesty; informative only at observation error
   ≪ base size.
3. **SPPA-MVFit does NOT win the 2D reprojection IoU on this stream.**
   Box-shaped proxies (OBB/hull/capsule ≈ 0.45) fit the bbox evidence best —
   the metric rewards filling the rectangle. The articulated family graphs
   (thin tower column, quadruped legs) plus the frozen bounds' minimum size
   (tower z-scale ≥ 0.55 × 25 m = 13.75 m vs a ≈5 m monocular height estimate)
   reproject to shapes that overlap the bbox less (SPPA 0.298, Generic 0.423).
   The family prior costs image-IoU under noisy monocular evidence — the
   mirror image of the sealed benchmark, where the same prior wins on true-3D
   shape IoU (unavailable for real data).
4. **Wrong family tokens measurably break 3D-2D consistency.** Refitting the
   138 wrong-token cases with the correct family collapses reprojection IoU
   (0.381 → 0.025): the correct prior (e.g. a ≥13.75 m tower) cannot explain
   the small 2D evidence that made the detector fire "cow". The token carries
   real geometric weight.
5. **Geometry validated end-to-end.** Reprojecting the exact anchors through
   the benchmark camera model places the tower base inside the detector bbox
   for the close range (e.g. t0 sequence f478+: 22–26 px ≈ 4–5 m at 91 m); over
   all tower detections 29.6 % inside, median offset 107 px (dominated by
   far/multi-tower ambiguities and bbox-centre vs anchor-base offset).
6. **Latency**: MVFit ≈ 12–14 ms/case (real-time capable at the stream's
   2–15 fps) vs 0.2–1.3 ms for primitive baselines.

## Limitations

- Exploratory post-hoc; not preregistered, not sealed.
- Low-altitude stream (AGL 10–23 m, near the 10 m publish gate): the
  terrain-relief bias above is specific to this sortie's geometry.
- bbox-as-mask for the 2D metric (no segmentation weights exist; declared).
- Declared GT base dimensions and per-family nominal heights (not measured).
- GT association radii declared (40/10 m); matched subset = 217/1902 cases.
- Bikers: 2D metric only (no GT recoverable; peloton splines move, audit log
  stores no positions).

## Audit trail

- First run (2026-07-18) contained a window double-scaling defect:
  `case_window` read graph extents from the already monkeypatched
  `mv.GRAPHS`, re-applying the metric scale (windows up to ±46 m × 260 m),
  which starved the 64³ evaluation grid (SPPA tower reproj ≈ 0.006, correct-
  token refit arm ≡ 0). Fixed in `e7_common.graph_extent_units` (now always
  reads the pristine `ORIG_GRAPHS`) and the full suite was rerun; all numbers
  above are post-fix. `debug_refit_arm.py` reproduces the defect/fix.
- `sanity_geometry.py` — anchor↔bbox reprojection validation.
- `debug_one_case.py` / `debug_frame_478.png` — single-case geometry dump and
  overlay.

## Reproduce

```bash
cd "D:\AYTE DOCTOR\SPPA_semantic_proxy_3d\benchmarks\real_stream_wave"
python run_e7_real_stream.py    # cases -> fits -> results.jsonl + e7_summary.json (~4 min)
python analyze_e7.py            # -> e7_analysis.json + real_stream_table.tex
python make_fig_e7.py           # -> fig_real_stream.png (300 dpi, Okabe-Ito)
python sanity_geometry.py       # optional geometry validation
```

Python 3.12 (`C:\Users\xabie\AppData\Local\Programs\Python\Python312\python.exe`,
`PYTHONUTF8=1`); numpy/scipy/matplotlib/Pillow. Sealed package imported
read-only from `reproducibility/sppa_mvfit`; pipeline modules imported
read-only from `D:\Deep-AeroTwin-UE57-Test\pipeline`.

## Files

- `results.jsonl` — 11 550 rows (1902 cases × 6 methods + 138 correct-token
  refits), one row per case × method.
- `e7_summary.json` — machine summary of the run.
- `e7_analysis.json` — aggregated numbers used in the table/figure/report.
- `real_stream_table.tex` — booktabs tabulars (main + token arm), e3 pattern.
- `fig_real_stream.png` — 4-panel figure (frame, plan view, evidence fit,
  observation-bound localization).
- `e7_common.py`, `run_e7_real_stream.py`, `analyze_e7.py`, `make_fig_e7.py`,
  `sanity_geometry.py`, `debug_one_case.py`, `debug_refit_arm.py`,
  `debug_frame_478.png`.
