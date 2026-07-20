# E11a — Capture Log: oblique twin wave (towers)

Date: 2026-07-19 · Operator: kimi-code subagent (E11a) · Level: `/Game/Ejea` (UE 5.7.4)

## TL;DR

- **Geometry dump: COMPLETE and verified.** `gt/tower_geometry.json` + LOD0 OBJ of the
  shared mesh (`gt/tower_mesh.obj`, `gt/tower_mesh_Internal.obj`).
- **Orbit capture: BLOCKED, honestly reported.** The headless `-run=pythonscript`
  commandlet **never ticks the engine**. Cesium 3D Tiles need ticks to stream and
  async static-mesh render-data builds need ticks to finish. Frames can be captured
  mechanically (exact poses, PNG readback works) but the scene content is invalid:
  terrain absent (black), tower mesh not rendered. 3 invalid smoke PNGs are kept in
  `frames_smoke_invalid/` as evidence; `frames/` is empty pending a valid capture.
- **No project code/config was modified.** Only new python scripts under
  `Unreal/Scripts/` and outputs under this directory.

## What was run (chronological)

All editor sessions used the verified pattern (plus `-AllowCommandletRendering`
where noted — required, see "Blocker" below):

```
PORCE_UNREAL_QUIT_AFTER_SCRIPT=1 \
"D:/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" \
"D:/Deep-AeroTwin-UE57-Test/Unreal/AirTraffic.uproject" \
-run=pythonscript "-script=<script>" -unattended -nop4 -nosplash \
-stdout -FullStdOutLogOutput [-AllowCommandletRendering]
```

| # | Script | Result |
|---|--------|--------|
| 1 | `Unreal/Scripts/dump_tower_geometry.py` (run 1) | OK — 11/11 actors, mesh-vertex API absent (log: `logs/dump_geometry_run1.log`) |
| 2 | `dump_tower_geometry.py` run 2 (exporter fallback added) | OK — OBJ written (log: `logs/dump_geometry_run2.log`) |
| 3 | `orbit_capture_towers.py` smoke `--towers t0 --limit 3` (run 1) | FAIL — `export_render_target`: "render target has been released" |
| 4 | smoke run 2 (+root attempt) | FAIL — same (`add_to_root` does not exist in this python build) |
| 5 | `probe_rt_readout_paths.py` (run 1) | FAIL (script error on `add_to_root`), rerun OK: world in commandlet is `/Temp/Untitled_0`, RT readout dead there |
| 6 | smoke run 3 (readback path) | FAIL — `read_render_target` returned 0 samples |
| 7 | smoke run 4 (+`-AllowCommandletRendering`) | MECHANICAL OK, CONTENT INVALID — RHI went from `Null` to `D3D12`; PNGs written but terrain black, tower not rendered |
| 8 | `probe_commandlet_ticks.py` | OK — **proof: nothing ticks** (slate post-tick cb 0 fires in 20 s; mesh `get_lod_count` stays -1) |
| 9 | `probe_commandlet_hooks.py` | OK — enumerated APIs; no tick source; `automation_wait_for_loading` needs latent_info |
| 10 | `probe_commandlet_screenshots.py` | **Editor CRASH** (FunctionalTesting.dll AV) — automation screenshots need a viewport; path dead |

Wall time: ~2–3 min per commandlet session (startup-dominated); ~3.5 min for the
D3D12 smoke (shader recompiles). Editor startup loads `/Game/Ejea` only via
`load_map` (commandlet boots into `/Temp/Untitled_0`).

## Geometry ground truth (done, verified)

`gt/tower_geometry.json` — per actor (t0,t1,t2,t3,t4,t5,t7,t9,t10,tower12,tower13):
world location/rotation (euler+quat), AABB origin/extent, pivot→bounds offset,
globe-anchor LLH (CesiumGeoreference transform), static mesh asset, component
classes, ground line-trace result (traces return `None` in commandlet: no physics
scene — AGL must be derived from anchor heights).

Key facts:
- All 11 towers share `/Game/tower_mesh.tower_mesh`; AABB ≈ 8.2 × 7.4 × **20.71 m** tall.
- Mesh pivot at the base: bounds-origin offset z = +1019.6 cm ≈ half height −16 cm
  (tower slightly embedded in terrain). So look-at target = AABB centre ≡
  anchor + half tower height (as specced).
- Yaw per actor in JSON (−29…−44°).
- `gt/tower_mesh.obj` (12144 v / 4048 f, per-corner duplicates) and
  `gt/tower_mesh_Internal.obj` (1615 v / 4048 f, welded) — **same 1458 unique
  positions**, LOD0, exported via `unreal.StaticMeshExporterOBJ` (AssetExportTask).
  Axis mapping documented in JSON `obj_notes`: OBJ (x,y,z) = Unreal local (x,z,y),
  Y-up, centimetres. Mesh-local footprint 742 × 343 cm, height 2067 cm.
- Raw python mesh APIs (`StaticMesh.get_mesh_description`, `unreal.MeshDescription`)
  are NOT available in this UE 5.7.4 build — exporter path used instead (logged in
  JSON `distinct_mesh_assets[0].extraction.attempts`).

## The blocker (orbit capture)

Two stacked issues, both root-caused to **the pythonscript commandlet does not run
the engine loop**:

1. **NullRHI by default** — without `-AllowCommandletRendering`, `rhiname="Null"`:
   render-target resources are never created (`export_render_target` → "render
   target has been released"; `read_render_target` → 0 samples).
   *Fix found:* add `-AllowCommandletRendering` → `rhiname="D3D12"`, captures
   render and readback works (this flag is a deviation from the verbatim command in
   the task brief; it is still the same headless commandlet pattern, documented here).
2. **No ticking even with rendering** — `capture_scene()` forces an immediate scene
   render (sky + some static meshes visible), but nothing ticks between poses:
   - Cesium 3D Tiles never stream (network responses are dispatched to the game
     thread in `ACesium3DTileset::Tick`) → terrain is absent/black.
   - Async static-mesh render-data builds never complete → `tower_mesh` has
     `get_lod_count = -1` in-session and the towers do not render (the bright blobs
     in the smoke frames are the peloton/cow meshes, which were already built).
   - Slate/FTicker callbacks never fire (probe evidence in `logs/probe_ticks.json`).
   - `take_automation_screenshot_at_camera` **crashes the editor** in this context.

Evidence frames: `frames_smoke_invalid/t0_oblique30_az0*.png` (sky gradient on top,
black terrain, peloton figures; tower absent). Note the in-editor validity check
(pixel std > 5) PASSED these frames (sky variance) — automated non-black checks are
insufficient; a centre-region mean > 0 check is required. Manifest of that smoke:
`frames_smoke_invalid/manifest_smoke_run4.jsonl` (poses themselves verified exact:
35.00 m radius, pitch −30.00° to 2 d.p.).

## How to resume (options — need maintainer decision, all currently blocked by policy)

The orbit script `Unreal/Scripts/orbit_capture_towers.py` is ready and resumable
(`PORCE_ORBIT_TOWERS=t0,t1 PORCE_ORBIT_LIMIT=N` or `--towers/--limit`; existing
PNGs ≥ 15 KB are skipped; manifest.jsonl rewritten deterministically per scope).
But valid content requires an engine that ticks. Options:

- **(a) MRQ commandlet (canonical).** Author a transient LevelSequence +
  MoviePipeline Queue with the exact poses (reuse `build_poses()`), render with
  `-run=MovieRenderPipelineCommandlet -MoviePipelineConfig=<queue>` +
  `-AllowCommandletRendering`, engine warm-up ≥ 64 frames per shot for Cesium
  settle. **Requires permission to save two assets under `Unreal/Content/E11aTmp/`
  (auto-deleted afterwards)** — currently forbidden by the "only scripts + output
  dirs" constraint.
- **(b) `-game` headless run** (ticks natively; script must be ported off editor
  subsystems). Forbidden by the "commandlet only" constraint.
- **(c) Live editor session** driven via MCP bridge (how previous repo captures were
  actually produced — no PPM/PNG from a commandlet exists in the repo). Forbidden
  by the same constraint.

Estimated effort once unblocked: authoring script ~1 h; render of 308 frames
(11 towers × 28 poses; 640×640, FOV 70, oblique 30°/45° at r = max(35, h/(2·tan21°))
= 35 m, nadir at +60 m) ≈ 15–25 min in one session, then
`python Unreal/Scripts/recode_orbit_frames_jpg.py` for JPG q88 + validation.

## Files

- `gt/tower_geometry.json`, `gt/tower_mesh.obj`, `gt/tower_mesh_Internal.obj`
- `Unreal/Scripts/dump_tower_geometry.py`, `orbit_capture_towers.py`,
  `recode_orbit_frames_jpg.py` (offline JPG step, ready)
- Diagnostics: `Unreal/Scripts/probe_rt_readout_paths.py`,
  `probe_commandlet_ticks.py`, `probe_commandlet_hooks.py`,
  `probe_commandlet_screenshots.py`; logs in `logs/`
- `frames_smoke_invalid/` — invalid-content evidence (3 PNGs + smoke manifest)
- `frames/` — empty; waiting for a valid capture route
