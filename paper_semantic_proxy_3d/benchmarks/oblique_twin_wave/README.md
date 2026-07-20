# E11 "Oblique Twin Wave" — reconstruction fidelity across view angles

Exploratory post-hoc analysis (**not confirmatory**) for the SPPA-MVFit paper.
308 twin frames (640×640, FOV 70°) of 11 real lattice towers of the Ejea map,
three view rings per tower: `oblique30` (12 az), `oblique45` (12 az), `nadir`
(4 az, +60 m). **Positions are LOCKED to ground truth** — only reconstruction
fidelity is evaluated; no localization metrics are computed or claimed.
Evidence is **hybrid**: simulated imagery + real YOLO detector + exact
simulator GT (declared).

Read first: `PROTOCOL_E11.md` (frozen 2026-07-20, before any outcome).

## Pipeline (3 steps)

```bash
PY=/c/Users/xabie/AppData/Local/Programs/Python/Python312/python.exe
PYTHONUTF8=1 $PY run_e11_detect.py      # YOLO (conf 0.10, imgsz 640) -> detections.jsonl
PYTHONUTF8=1 $PY run_e11_analysis.py    # observations -> fits -> results.jsonl  (RESUMABLE)
PYTHONUTF8=1 $PY run_e11_aggregate.py   # -> e11_analysis.json, e11_main_table.tex, fig_e11_oblique.png
```

- `run_e11_analysis.py` is resumable: case_ids already present in
  `results.jsonl` are skipped on rerun (safe under a time budget; delete
  `results.jsonl` to force a full refit).
- Read-only imports: sealed fitter
  `reproducibility/sppa_mvfit/method/sppa_mvfit.py` (via the E7 modules) and
  `benchmarks/real_stream_wave/{e7_common,run_e7_real_stream}.py`. Nothing
  under `reproducibility/` is written; `mv.WORLD`/`mv.GRAPHS` are patched in
  memory only, E7 style.

## Files

- `detections.jsonl` — 673 raw detections (frame_id, class, conf, bbox).
- `results.jsonl` — 2106 rows = 351 fitted cases × 6 methods (per-row theta /
  box params, 3D voxel IoU vs exact GT, token flag, GT voxel counts, latency).
- `e11_analysis.json` — full aggregate: detection census, per-ring and
  per-tower stats (paired bootstrap 95% CI, 10k, seed 20260720), correct-token
  subset, cross-view consistency (per tower + pooled), parameter spread,
  consensus proxy, wrong-token arm, GT voxelization sanity.
- `e11_main_table.tex` — booktabs main table.
- `fig_e11_oblique.png` — (a) sample detections, (b) 3D IoU by ring,
  (c) cross-view consistency per tower, (d) SPPA proxy reprojection.

## Sanity invariants (asserted)

1. Every detection joins to exactly one manifest frame/tower
   (`frame_not_in_manifest = 0`).
2. GT voxel occupancy non-trivial in every case window (assert per case;
   mean ≈ 3.2k solid voxels at 64³).
3. Locked positions: window centered on the GT pivot (asserted symmetric);
   no code path estimates position (`match_gt` is never imported/called).
