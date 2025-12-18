# Deep-AeroTwin: Autonomous Navigation & Digital Twin Framework

**Version:** 2.3  
**Author:** Xabier Olaz

<div align="center">
  <video width="100%" controls autoplay loop muted>
    <source src="readme_video.mp4" type="video/mp4">
    Your browser does not support the video tag.
  </video>
</div>

## Overview

**Deep-AeroTwin** is a cutting-edge aerospace framework designed to bridge the gap between simulation and reality. It operates on a dual-pipeline architecture designed for two distinct operational modes: **Autonomous Synthetic Simulation** (Current) and **Real-Time Digital Twin Teleoperation** (In Development).

The core philosophy is to leverage **Unreal Engine 5** not just for visualization, but as the primary interface for both autonomous training and human-piloted operations.

---

## System Architecture: The Dual Pipeline

### 1. Pipeline A: Synthetic Autonomy (Implemented v2.3)
Currently active. This mode is a high-fidelity Hardware-In-The-Loop (HITL/SITL) simulation for developing autonomous obstacle avoidance behaviors.
*   **Input:** Synthetic sensor data from Unreal Engine (AirSim/Cesium).
*   **Logic:** The **PORCE System** (Path planning & Obstacle avoidance with Real-time Collision Evasion).
*   **Output:** Autonomous flight commands sent to the ArduPilot SITL controller.

### 2. Pipeline B: Real-Time Digital Twin (In Development)
*Target of the next major release.* 
This mode reverses the data flow to support remote piloting of physical drones.
*   **Input:** Live video stream and telemetry from a physical drone.
*   **Processing:** Real-time Computer Vision detects physical obstacles (towers, buildings, terrain).
*   **Replication:** The system dynamically "spawns" and updates these objects inside the Unreal Engine map in real-time.
*   **Goal:** The pilot flies the physical drone by looking **only** at the pristine, high-fidelity Unreal Engine render, which acts as a noise-free, perfect "Digital Twin" of the chaotic real world.

---

## Current Core Technology: The PORCE System

In the current v2.3 release, the focus is on **PORCE**, the intelligent engine that allows the drone to react autonomously to dynamic obstacles during inspection missions.

### Operational Logic

1.  **Normal Flight:** The drone executes its pre-planned mission (waypoints) at a cruise speed of **8 m/s**.
2.  **Detection Phase (> 45m):** The Vision System (YOLOv5/OpenVINO) identifies obstacles up to 80 meters away from the synthetic feed. It tracks their relative position but does not yet intervene.
3.  **Reaction Phase (<= 45m):** Once an obstacle breaches the `REACTION_DISTANCE` threshold:
    *   The primary mission is paused.
    *   A local occupancy grid (400m x 400m) is generated around the drone.
    *   The detected obstacle is mapped as a "No-Fly Zone" with a safety radius.
4.  **Path Planning (A*):** PORCE calculates an optimal detour path through the grid, ensuring the drone stays at least **12 meters** (`SAFETY_RADIUS`) away from the hazard.
5.  **Evasion Execution:** The drone navigates the new path. To prevent collisions with unseen cables, the system treats towers as "infinite columns" (never attempting to fly *over* them, only *around*).
6.  **Mission Resumption:** Once the obstacle is cleared, the drone seamlessly rejoins its original flight path.

### Safety Mechanisms

*   **Look-Ahead Orientation:** The drone's yaw is locked to its velocity vector, ensuring the camera always faces the direction of travel for continuous obstacle scanning.
*   **Infinite Column Assumption:** Safety logic that forbids flying directly over vertical structures to avoid high-voltage lines.
*   **Emergency Escape:** If the drone initializes inside a danger zone, a specific routine prioritizes exiting the safety radius before navigation resumes.

---

## Configuration & Constants

Key system parameters defined in `pipeline/constants.py`:

| Parameter | Value | Description |
| :--- | :--- | :--- |
| **CRUISE_SPEED** | `8 m/s` | Standard mission velocity. |
| **REACTION_DISTANCE** | `45 m` | Distance at which evasion logic triggers. |
| **SAFETY_RADIUS** | `12 m` | Minimum keep-out distance from any obstacle center. |
| **GRID_RESOLUTION** | `10 m` | Size of each cell in the A* navigation grid. |
| **DETECTION_RANGE** | `80 m` | Maximum reliable range of the computer vision system. |
| **GRID_SIZE** | `400 m` | Size of the local navigation horizon (40x40 grid). |

---

## Installation & Usage

### Prerequisites
*   Windows 10/11
*   Python 3.8+
*   Unreal Engine 5.x
*   ArduPilot SITL

### Setup
1.  Clone the repository:
    ```bash
    git clone https://github.com/xabierolaz/Deep-AeroTwin.git
    cd Deep-AeroTwin
    ```
2.  Install Python dependencies:
    ```bash
    pip install -r pipeline/requirements.txt
    ```

### Running the Simulation
Execute the main launcher to start SITL and the Python pipeline:
```bash
./launch.bat
```
*Ensure Unreal Engine is running with the project loaded before starting the pipeline.*

---

## License
Project under proprietary license. All rights reserved.
