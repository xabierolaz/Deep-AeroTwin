# Deep-AeroTwin (PORCE)

<div align="center">
  <img src="readme_gif.gif" width="100%" alt="Deep-AeroTwin Demo">
</div>

This repo contains a **Windows + WSL2** setup for running an ArduPilot Copter mission in **SITL**, ingesting obstacles over **HTTP**, and (optionally) running **YOLO** vision to feed the planner (**PORCE**).

## Source Of Truth (Zero-Trust)

Everything stated here is derived from the code in this repo and/or from runs that were executed locally.

* **Pipeline A E2E runner:** `pipeline/e2e_flight_matrix.py`
* **Brain (Flask + MAVLink + PORCE):** `pipeline/flight_controller.py`
* **PORCE planner (A*):** `pipeline/porce_manager.py`
* **SITL launcher (WSL):** `pipeline/run_sitl.sh`
* **Vision (MSS + YOLO -> `/api/obstacles`):** `pipeline/vision_system.py`

## Current Status (Verified)

**Pipeline A (SIMULATION) is operational and validated end-to-end.**

Verified on **2026-02-13** (Windows + WSL2):
* `porce_off_no_detections`: PASS
* `porce_on_no_detections`: PASS
* `porce_off_with_detections`: PASS (token enabled; `inject_posts_unauthorized=0`)
* `porce_on_with_detections`: PASS (token enabled; `inject_posts_unauthorized=0`; `saw_evasion=true`)

## Pipelines

### Pipeline A (SIMULATION)

* Starts **ArduPilot Copter SITL** in WSL (`pipeline/run_sitl.sh`).
* Starts the **Brain** on Windows (`pipeline/flight_controller.py`) and connects MAVLink to `tcp:127.0.0.1:5760`.
* Optional: starts **Vision** (`pipeline/vision_system.py`) which uses **MSS screen capture** + YOLO and POSTs obstacles to the Brain.
* Optional: starts **Viz recorder** (`pipeline/viz_recorder.py`) which polls `/api/ui/data` and writes PNG frames under `pipeline/logs/viz_frames/`.

Launchers:
* `launch_pipeline_A.bat` (recommended)
* E2E harness: `pipeline/e2e_flight_matrix.py` (recommended for CI-like validation)

### Pipeline B (REAL_TWIN) (Not Validated / Experimental)

The repo includes `launch_pipeline_B.bat` and the Brain exposes `/api/unreal/sync`, but **Pipeline B is not yet “real drone + real video”**:
* The Brain MAVLink connection is still hard-coded to `tcp:127.0.0.1:5760` (`pipeline/flight_controller.py`).
* Vision currently uses **MSS screen capture** (no RTSP/VideoCapture integration yet) (`pipeline/vision_system.py`).

Treat Pipeline B as a placeholder until those pieces are made configurable and validated.

## Quick Start (Pipeline A)

1. Install Python deps:
   ```bash
   pip install -r pipeline/requirements.txt
   ```
2. Ensure WSL has an ArduCopter SITL binary:
   * Preferred: initialize/build the `ardupilot` submodule.
   * Fallback supported by code: a WSL home clone at `$HOME/ardupilot/build/sitl/bin/arducopter`.
   * Override supported by code: set `ARDUPILOT_SITL_BIN=/path/to/arducopter` (WSL env).
3. Run one E2E scenario:
   ```powershell
   python pipeline\e2e_flight_matrix.py --scenario porce_off_no_detections --scenario-timeout 420 --arm-timeout 240 --takeoff-timeout 180
   ```

## Pipeline A E2E Matrix

| Scenario | PORCE_ENABLE_EVASION | Obstacle injection | Expected `saw_evasion` |
| :--- | :---: | :---: | :---: |
| `porce_off_no_detections` | 0 | no | false |
| `porce_on_no_detections` | 1 | no | false |
| `porce_off_with_detections` | 0 | yes | false |
| `porce_on_with_detections` | 1 | yes | true |

Logs per run:
* `pipeline/logs/e2e/<scenario>_<timestamp>/brain.log`
* `pipeline/logs/e2e/<scenario>_<timestamp>/sitl.log`

## Obstacle Ingestion Token (Zero-Trust)

If `PORCE_OBSTACLE_TOKEN` is set, the Brain requires all `POST /api/obstacles` to include:
* Header: `X-PORCE-Token: <PORCE_OBSTACLE_TOKEN>`

When the token is enabled, the E2E harness asserts `inject_posts_unauthorized=0`.

## Vision Model (YOLO)

* Default weights (committed): `pipeline/weights/yolo_3d_dome_v1_best.pt`
* Override: set `PORCE_YOLO_MODEL` to a different `.pt` path.
* Classes in the committed model: `biker`, `cow`, `tower`.

Vision posts obstacles as:
* `type`, `confidence`, `source`, `bbox` + `lat/lon/distance` (see `pipeline/vision_system.py`).

## Synthetic Training (OBJ -> Dome Dataset -> YOLO)

Assets:
* `3d_to_dataset_xabi/assets/biker.obj`
* `3d_to_dataset_xabi/assets/cow.obj`
* `3d_to_dataset_xabi/assets/tower.obj`

Generate + train:
```powershell
cd 3d_to_dataset_xabi
python generate_dataset.py --num-per-class 2000 --imgsz 640 --preview
python train_yolo.py --epochs 50 --imgsz 640 --batch 32 --device 0 --name yolo_3d_dome_v1
```

Notes:
* `3d_to_dataset_xabi/dataset/` and `3d_to_dataset_xabi/runs/` are **not committed** (ignored by git).
* The generator samples camera viewpoints from the **upper hemisphere** (“dome”, drone-like: always above the object) and applies heavy domain randomization.

## Repo Layout

* `pipeline/`: runtime (Brain, Vision, E2E runner, launch helpers).
* `pipeline/weights/`: committed final YOLO weight used by Vision by default.
* `3d_to_dataset_xabi/`: synthetic dataset generation + training scripts.
* `tools/`: small developer utilities (e.g. `tools/inspect_model.py`, `tools/check_status.py`).
* `Unreal/`: Unreal project sources (generated binaries/cache are ignored).

## Known Gaps / TODO (Code-Based)

* Make MAVLink connection configurable for a real drone (Brain currently hardcodes SITL TCP).
* Implement/validate video ingestion for REAL_TWIN (Vision currently uses MSS capture).
* Add a true Vision-in-the-loop E2E scenario (current E2E uses an HTTP injector, not YOLO).

## License
Proprietary. All rights reserved.
