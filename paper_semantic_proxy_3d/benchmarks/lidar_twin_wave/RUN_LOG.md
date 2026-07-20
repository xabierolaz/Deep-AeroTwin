# E14 — Run log (2026-07-20, kimi-code subagent)

All times UTC+0, single session. Machine: Windows, Git Bash; offline Python
`C:\Users\xabie\AppData\Local\Programs\Python\Python312\python.exe`,
PYTHONUTF8=1.

| # | Step | Result |
|---|------|--------|
| 1 | Read refs: E7 (`e7_common.py`, `run_e7_real_stream.py`), `tower_geometry.json`, E11a PIE scripts, `tools/unreal_mcp_call.py` | OK |
| 2 | `tasklist` — no UnrealEditor running | OK |
| 3 | Froze `E14_PROTOCOL.md` (before any outcome) | OK |
| 4 | Launched editor `UnrealEditor.exe AirTraffic.uproject /Game/Ejea` (PID 55920, mine) | OK |
| 5 | MCP bridge poll (`system_control execute_python` print) | OK |
| 6 | `control_editor play` | PIE up |
| 7 | `execute_python Unreal/Scripts/e14_lidar_scan_pie.py` run 1 | probe ABORT: 0 hits — `HitResult` binding has no `.blocking_hit`; fields reachable via `hit.to_tuple()` (T0=blocking, T4=impact, T9=actor) |
| 8 | Trace probes in PIE | tower `StaticMeshActor_4` hit at z=834.5 cm (top ~20.5 m over anchor); simple collision OK; complex trace returned None → declared simple collision |
| 9 | Fixed unpack, re-armed scan | OK |
| 10 | Capture: 55/55 scans, 317,680 rays, 316,149 hits in 29.3 s; Cesium load 100%; probe actors incl. `t0`, `Google Photorealistic 3D Tiles` | OK → `points.jsonl` |
| 11 | `run_e14_lidar_wave.py` run 1 | SANITY FAIL: gt_voxels=26 — even-odd solid fill wrong for thin-beam lattice (vertical rays parallel to members); ground p10 biased height −2..3 m. No method score used for the fix |
| 12 | Protocol Amendment A1 (surface occupancy + ground p2) documented in `E14_PROTOCOL.md` | OK |
| 13 | Rerun | 11/11 clean detections, 7/11 degraded (4 detection failures, kept as rows) |
| 14 | `make_e14_outputs.py` — table, figure, supplementary 1-voxel-tolerant IoU | OK |
| 15 | Optional fog shot: transient `ExponentialHeightFog` (density 0.15) spawned in PIE world; viewport stayed possessed by the game pawn (unpossess/deferred-spawn unavailable in this Python binding) → kept as illustrative, documented in README | PARTIAL (honest) |
| 16 | `control_editor stop` (PIE), bridge blocked `quit` (security), WM_CLOSE to PID 55920 | Editor closed; `tasklist` clean; no orphans |

## Editor cleanliness

- No UE project code/config touched. Added only
  `Unreal/Scripts/e14_lidar_scan_pie.py`; all outputs under
  `paper_semantic_proxy_3d/benchmarks/lidar_twin_wave/`.
- All spawned actors (fog, none else persisted) were transient to the PIE
  world; PIE stopped before editor close. Level never saved.
- `Unreal/Saved/Screenshots/` transient copies removed; the kept shot lives
  in the benchmark dir.

## Time budget note

Total wall ≈ 25 min within the subagent budget; full 28-pose coverage not
needed (5 poses/tower sufficed; resume path documented in README).
