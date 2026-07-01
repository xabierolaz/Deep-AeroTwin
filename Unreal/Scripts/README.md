# Unreal script inventory

Canonical paper setup is launched from `LANZAR_TODO_PAPER.bat`.

Production commandlet path:

- `apply_ejea_spawn_origin_and_save.py`
- `apply_cesium_paper_streaming_profile.py`
- `configure_cesium_ejea_route_precache.py`
- `canonicalize_peloton_only.py`
- `apply_paper_all_obstacles_profile_and_save.py`
- `apply_paper_runtime_camera_profile.py`
- `audit_paper_peloton_state.py`

Asset maintenance:

- `import_textured_biker_morph.py`
- `audit_textured_biker_morph_asset.py`

Manual/diagnostic tools:

- `apply_runtime_paper_quality_cvars.py`
- `audit_ejea_spawn_state.py`
- `paper_scenario_visibility.py`
- `verify_sppa_backend.py`

SPPA backend reflection smoke:

- `powershell -NoProfile -ExecutionPolicy Bypass -File tools\verify_sppa_backend.ps1`

Figure-2 capture experiments, not part of the automatic launcher:

- `paper_peloton_stage.py`
- `paper_unreal_capture_crossing_precheck.py`
- `paper_unreal_capture_peloton_yolo.py`
- `paper_unreal_real_flight_capture.py`

Retired scripts removed from this folder:

- `apply_paper_moving_peloton_profile_and_save.py`
- `cleanup_dat_temp_actors.py`
- `remove_legacy_spawner_and_obstacle_blueprints.py`
