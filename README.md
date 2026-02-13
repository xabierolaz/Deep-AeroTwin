# Deep-AeroTwin: Autonomous Navigation & Digital Twin Framework

**Version:** 3.0 (Blackwell Ready)  
**Date:** January 2026  
**Core:** PORCE System (Path planning & Obstacle avoidance with Real-time Collision Evasion)

<div align="center">
  <img src="readme_gif.gif" width="100%" alt="Deep-AeroTwin Demo">
</div>

## 1. Overview

**Deep-AeroTwin** is a high-performance aerospace framework designed to bridge the gap between simulation and reality using NVIDIA RTX 50-series hardware. It operates on a **Dual-Pipeline Architecture**, allowing a single codebase to serve two distinct operational goals:

1.  **Pipeline A (Simulation):** Autonomous HITL flight in Unreal Engine 5.6.
2.  **Pipeline B (Digital Twin):** Real-time replication of a physical drone's environment for remote teleoperation.

---

## 2. Quick Start (Dual Launchers)

The project now includes dedicated launchers for each mode. **Do not run `launch.bat` directly** unless you know what you are doing.

### Pipeline A: Autonomous Simulation
*   **Goal:** Test AI evasion logic against synthetic obstacles.
*   **Launcher:** `launch_pipeline_A.bat`
*   **Components:** SITL (WSL) + Unreal Vision (Screen Capture) + Brain + Recorder.
*   **Behavior:** Drone flies autonomously. Detects obstacles via MSS Screen Capture. Avoids them using A*.

### Pipeline B: Digital Twin (Real World)
*   **Goal:** Replicate real-world hazards in Unreal for a human pilot.
*   **Launcher:** `launch_pipeline_B.bat`
*   **Components:** Brain (Real Drone Mode) + Vision (Real Video Feed) + Recorder. **NO SITL**.
*   **Behavior:** 
    1.  Vision System detects real obstacles (Cows, Bikers) from video.
    2.  Brain exposes object data via API (`/api/unreal/sync`).
    3.  Unreal Engine (VaRest) polls API and spawns virtual obstacles in real-time.

---

## 3. The PORCE System (Intelligence Core)

The **PORCE** (Path planning & Obstacle avoidance) engine manages the drone's safety. It is mode-aware and adjusts its physics based on the active pipeline.

| Parameter | Pipeline A (Sim) | Pipeline B (Real) | Description |
| :--- | :--- | :--- | :--- |
| **Cruise Speed** | 8.0 m/s | 5.0 m/s | Slower in reality for safety. |
| **Detection Range** | 80 m | 150 m | Max reliable vision range. |
| **Reaction Distance** | 45 m | 60 m | Distance to trigger evasion. |
| **Safety Radius** | 12 m | 12 m | Hard keep-out zone. |

### Safety Mechanisms
*   **Look-Ahead Orientation:** The drone's yaw is locked to its velocity vector, ensuring the camera always faces the direction of travel for continuous obstacle scanning.
*   **Infinite Column Assumption:** Safety logic that forbids flying directly over vertical structures (towers) to avoid high-voltage lines. The system only plans detours *around* obstacles.
*   **Emergency Escape:** If the drone initializes inside a danger zone, a specific routine prioritizes exiting the safety radius before navigation resumes.

---

## 4. Vision Engine & Synthetic Data (RTX 5090)

The project leverages **YOLOv11 Nano** optimized for NVIDIA Blackwell architecture (CUDA 12.8).

### Synthetic Training Workflow (`3d_to_dataset_xabi/`)
We generate our own datasets to detect specific hazards not found in COCO (like Electric Towers).
1.  **Assets:** 3D Models (`.obj`) of Bikers, Cows, and Towers.
2.  **Generation:** `generate_dataset.py` uses **PyRender** to create thousands of 640x640 labeled images with:
    *   **Upper-hemisphere ("dome") camera sampling** (drone-like views; always from above).
    *   Heavy domain randomization: backgrounds, noise, blur, JPEG artifacts, occlusions, lighting variation.
3.  **Training:** `train_yolo.py` fine-tunes YOLOv11n on this custom dataset.

**Current Model Status:**
*   **Classes:** `biker`, `cow`, `tower`
*   **Weights (committed):** `pipeline/weights/yolo_3d_dome_v1_best.pt`
*   **Training outputs:** `3d_to_dataset_xabi/runs/.../weights/best.pt` (ignored by git)

**Repro (generate + train):**
```powershell
cd D:\Deep-AeroTwin-upstream\3d_to_dataset_xabi
python generate_dataset.py --num-per-class 2000 --imgsz 640 --preview
python train_yolo.py --epochs 50 --imgsz 640 --batch 32 --device 0 --name yolo_3d_dome_v1
```

**Latest metrics (synthetic test split, 2026-02-13):**
* mAP50: ~0.992
* mAP50-95: ~0.922

**RTX 5090 timings (measured, 2026-02-13):**
* Dataset generation (6000 images @ 640): ~6.5 min
* Training (YOLO11n, 50 epochs, batch 32, imgsz 640): ~46.6 min
* Test eval (589 images): ~3 sec (after cache)

---

## 5. Technical Architecture (Microservices)

The system is composed of independent Python processes communicating via HTTP/TCP:

*   **Brain (`flight_controller.py`):** Flask Server (Port 8080). Central hub. Manages state and MAVLink.
*   **Eyes (`vision_system.py`):** YOLO Inference Engine. Captures MSS (Sim) or Video (Real). Sends POST to Brain.
*   **Recorder (`viz_recorder.py`):** Generates high-res mission logs and PNG frames.
*   **Unreal Bridge:** 
    *   **Sim:** Visual feedback only.
    *   **Twin:** Polls `http://localhost:8080/api/unreal/sync` to spawn objects.

### Network Ports
*   **8080:** Brain API (HTTP)
*   **9090:** Master Log Server (TCP)
*   **5760:** SITL Connection (TCP)

---

## 6. Installation

### Requirements
*   Windows 10/11 (with WSL2 enabled)
*   **GPU:** NVIDIA RTX 30/40/50 Series (CUDA 11.8+)
*   **Python:** 3.12+
*   **Unreal Engine:** 5.6

### Setup
1.  Clone repo.
2.  Install dependencies:
    ```bash
    pip install -r pipeline/requirements.txt
    ```
3.  **For Pipeline A:** Ensure ArduPilot SITL is installed in WSL.
4.  **For Pipeline B:** Configure Unreal Engine "VaRest" plugin to point to localhost:8080.

### Running
Double-click `launch_pipeline_A.bat` to fly.

---

## 7. Pipeline A E2E (Flight Matrix)

For reproducible validation of **Pipeline A** (SITL in WSL + Brain on Windows), use:

```powershell
cd D:\Deep-AeroTwin-upstream
python pipeline\e2e_flight_matrix.py --scenario porce_off_no_detections --scenario-timeout 420 --arm-timeout 240 --takeoff-timeout 180
```

### Scenarios

| Scenario | PORCE_ENABLE_EVASION | Obstacle injection | Expected `saw_evasion` |
| :--- | :---: | :---: | :---: |
| `porce_off_no_detections` | 0 | no | false |
| `porce_on_no_detections` | 1 | no | false |
| `porce_off_with_detections` | 0 | yes | false |
| `porce_on_with_detections` | 1 | yes | true |

### Obstacle Ingestion Token (Zero-Trust)

If `PORCE_OBSTACLE_TOKEN` is set, the Brain requires every `POST /api/obstacles` to include:
- Header: `X-PORCE-Token: <PORCE_OBSTACLE_TOKEN>`

The E2E runner asserts `inject_posts_unauthorized=0` when the token is enabled.

### Logs

Each run writes logs under:
- `pipeline/logs/e2e/<scenario>_<timestamp>/brain.log`
- `pipeline/logs/e2e/<scenario>_<timestamp>/sitl.log`

### Current E2E Status

Verified on **2026-02-13** (Pipeline A):
- `porce_off_no_detections`: PASS
- `porce_on_no_detections`: PASS
- `porce_off_with_detections`: PASS (`PORCE_OBSTACLE_TOKEN` enabled; `inject_posts_unauthorized=0`)
- `porce_on_with_detections`: PASS (`PORCE_OBSTACLE_TOKEN` enabled; `inject_posts_unauthorized=0`; `saw_evasion=true`)

---

## License
Proprietary. All rights reserved.
