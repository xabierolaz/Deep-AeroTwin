# Provenance — frames/ (v2 re-render, 2026-07-20)

- `frames/` (84 PNGs) was re-rendered from **towers_realistic_v2.blend** (cable fix on SingleMast.002, PBR ground Ground104/Ground103, galvanized steel, Nishita 20°/215° + sun, AgX Medium High Contrast, −3.3 EV).
- Settings: Cycles GPU (OPTIX), 96 spp, OIDN denoise, bounces 6/2/3/1, 640×640 PNG. Mean 2.0 s/frame, total 168 s (RTX 5090).
- Camera poses: IDENTICAL to v1 — same rig math as `blender_enhance_towers.py` (rings oblique30/oblique45 × 12 az + nadir × 4 at +60 m, FOV 70, radius = max(35, h/(2·tan 21°))). Spot-checked vs `manifest.jsonl`: matches to the centimeter, so the manifest remains valid and was NOT modified (its schema is pose-only, no render provenance).
- Previous v1 frames (old scene, cables not attached at t2, flat ground) preserved intact in `frames_v1_backup/`.
- Render script: `tmp/render_wave_v2.py` (render-only, skips existing PNGs > 15 KB; tower order t2, t0, t1 — resumable).
- `frames_styled/` and `styled_pilot/` belong to the old-scene styling run and were not touched.
