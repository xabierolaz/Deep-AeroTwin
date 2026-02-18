# PORCE Zero-Trust Design Audit

Date: 2026-02-18
Scope: `pipeline/vision_system.py`, `pipeline/flight_controller.py`, `pipeline/porce_manager.py`, runtime logs in `pipeline/logs/zero_trust/*`

## 1) Observed design problems

1. Reactive-only obstacle model in Brain
- Current behavior: `flight_controller.py` replaces `state['obstacles']` on every POST and uses global freshness (`OBSTACLE_EXPIRY_S`).
- Risk: if camera stops seeing a fixed obstacle for a short period, planner can treat the world as clear.

2. No static-vs-dynamic obstacle policy
- Current behavior: tower, cow, biker share the same lifecycle semantics.
- Risk: fixed objects should persist longer and move less; dynamic objects should decay faster.

3. Replan churn while evasion is active
- Current behavior: replan can replace an existing evasion path after `EVASION_REPLAN_MIN_INTERVAL_S`.
- Risk: route never stabilizes, path gets overwritten, low `evasion_completed`.

4. Planner fails at short range and system keeps advancing mission
- Current behavior: when A* fails (`route_failed`), system continues navigation to mission WP.
- Risk: exactly in high-risk near-obstacle situations, behavior is unsafe.

5. Planner uses obstacle cloud without selection
- Current behavior: A* receives full obstacle list from vision output.
- Risk: noisy/far detections can reduce planner feasibility in local grid.

6. Trigger distance does not encode planner feasibility boundary
- Current behavior: decision trigger uses only `REACTION_DISTANCE_M`.
- Risk: if nearest obstacle is already in low-feasibility zone, trigger is too late for robust bypass.

## 2) External audit evidence (last run)

- `evasion_route_generated=130`, `evasion_route_failed=118`, `evasion_completed=5`.
- Most route failures occur at short nearest distance.
- Replanning happened mostly while evasion was already active.
- Large fraction of `decision_snapshot` in GUIDED had stale global-age semantics despite non-empty obstacle state.

## 3) Solution architecture

1. Add Brain world-model obstacle memory
- Keep obstacle tracks in Brain (`obstacle_tracks`) with per-track `last_seen_ts`.
- Associate incoming detections by class + geo distance.
- Build active obstacle list from track TTL policy, not from single global timestamp.

2. Split static and dynamic policies
- Static classes (default: `tower`) get long TTL and conservative smoothing.
- Dynamic classes (`biker`, `cow`, others) get short TTL and faster updates.

3. Disable replan churn by default
- Do not replan while `evasion_path` is active unless explicitly enabled.
- Optional guarded replan only under tighter distance gate.

4. Add failsafe hold on close-range route failure
- If A* fails and nearest obstacle is very close, hold position for a short time window instead of advancing mission WP.

5. Filter obstacles before planner
- Use nearest/local obstacle subset for A* (`max distance`, `max count`).
- Keep mission logic aware of full state, but planning local and robust.

## 4) Config knobs to implement

- `PORCE_OBS_STATIC_CLASS_NAMES=tower`
- `PORCE_OBS_TRACK_TTL_STATIC_S=180.0`
- `PORCE_OBS_TRACK_TTL_DYNAMIC_S=4.0`
- `PORCE_OBS_TRACK_ASSOC_STATIC_M=20.0`
- `PORCE_OBS_TRACK_ASSOC_DYNAMIC_M=12.0`
- `PORCE_OBS_TRACK_MAX=256`
- `PORCE_EVASION_ALLOW_REPLAN_WHEN_ACTIVE=0`
- `PORCE_EVASION_ACTIVE_REPLAN_DISTANCE_M=12.0`
- `PORCE_EVASION_PLANNER_OBS_MAX_DISTANCE_M=55.0`
- `PORCE_EVASION_PLANNER_OBS_MAX_COUNT=20`
- `PORCE_EVASION_FAILSAFE_MIN_DIST_M=22.0`
- `PORCE_EVASION_FAILSAFE_HOLD_S=2.5`
- `PORCE_EVASION_FAILSAFE_ESCALATE_ENABLE=1`
- `PORCE_EVASION_FAILSAFE_ESCALATE_FAILS=3`
- `PORCE_EVASION_FAILSAFE_ESCALATE_WINDOW_S=12.0`
- `PORCE_EVASION_FAILSAFE_ESCALATE_COOLDOWN_S=20.0`
- `PORCE_EVASION_FAILSAFE_ESCALATE_ACTION=RTL`
- `PORCE_VISION_TRACK_MATCH_MAX_PX=80`
- `PORCE_VISION_TRACK_MATCH_MAX_DIST_M=18`
- `PORCE_VISION_TRACK_MAX_ACTIVE=256`

## 5) Acceptance checks after implementation

1. `route_failed` drops sharply at medium range.
2. `evasion_completed` increases and route churn drops.
3. `decision_reason=obstacles_stale_or_empty` in GUIDED decreases when static tower exits camera FOV briefly.
4. In close-range A* fail cases, logs show failsafe hold event instead of direct mission advance.

## 6) Additional scripts/parameters that affect robustness (beyond PORCE)

1. `pipeline/vision_system.py`
- Capture geometry mismatch (`PORCE_CAPTURE_EXPECT_WIDTH/HEIGHT` vs real captured size) degrades projection quality.
- Detection/post gates (`PORCE_VISION_DET_CONF`, `PORCE_VISION_PUBLISH_CONF`, `PORCE_VISION_MIN_SEEN_TO_PUBLISH*`) directly shape recall vs false positives.
- Header/footer ignores (`PORCE_VISION_IGNORE_TOP_*`, `PORCE_VISION_IGNORE_BOTTOM_*`) can silently suppress detections if oversized.

2. `pipeline/geo_projector.py`
- Pixel->ground intersection is strict; many rejects come from no ground intersection or geometry inconsistency.
- `max_range_m` clamp (fed by `PORCE_*_DETECTION_RANGE_M`) limits far detections and can hide distant objects if too low.

3. `pipeline/constants.py` + `pipeline/porce_defaults.env` + `launch.bat`
- Runtime behavior is mostly env-driven; wrong env overrides can invalidate tuning even if code is correct.
- Launcher auto-sets tokens and audit root; a stale/custom shell session can still override values unexpectedly.

4. `pipeline/porce_manager.py`
- Grid resolution (`PORCE_GRID_CELL_SIZE_M`), inflation (`PORCE_SAFETY_DISTANCE_M`), and radius/iterations define planner feasibility limits.

## 7) Implementation status

Implemented in code:
- Brain obstacle world-model with static/dynamic TTL + association.
- Anti-churn replan policy (replan while evading disabled by default).
- Local planner obstacle subset filtering.
- Close-range route-failure failsafe hold.
- Failsafe escalation after repeated close-range route failures (configurable action: `RTL`/`LAND`/`HOLD`).
- Adaptive reaction trigger based on current speed (configurable min/base/max envelope).
- Vision tracking IDs stabilized via detection-to-track association (class + pixel + distance gates).
- New env knobs in `constants.py` and `porce_defaults.env`.

## 8) Runtime zero-trust validation command

Use:
- `tools\validate_latest_run.bat`
- or `python tools\validate_zero_trust_run.py --run-dir <run_dir>`

What it validates:
- Mission altitude profile vs plan (`takeoff`, `cruise`, `landing`) from `brain/trajectory.csv`.
- Waypoint reach and waypoint altitude consistency.
- Mission progression (`max_wp_idx` reached end-of-plan).
- Vision capture resolution consistency from `vision/events.jsonl`.
- Camera env profile (`VFOV`, camera pitch, expected capture size) when available in `PORCE_ENV.txt`.

Output:
- Console PASS/FAIL summary.
- JSON report written to `<run_dir>\ZERO_TRUST_FLIGHT_REPORT.json`.
