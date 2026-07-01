# Pipeline B Telemetry / VRIH - Canonical Tracker

This is the only Markdown file maintained inside this paper folder. The manuscript source is `pipeline_b_concept.tex`; do not duplicate the full article text here. This file is the tracker for journal fit, A2/baremo logic, submission package, and next actions.

## Canonical Files

| File | Role |
|---|---|
| `pipeline_b_concept.tex` | Controlled manuscript draft. Edit this for paper content. |
| `pipeline_b_concept.pdf` | Compiled VRIH-format PDF output. Regenerate after LaTeX edits. |
| `VRIH2025.cls` | Official VRIH LaTeX class copied from the 2025 template package. |
| `vrih_highlights.txt` | VRIH-style highlights draft. |
| `figures/pipeline_b_architecture.png` | Current architecture figure used in the manuscript. |
| `generate_pipeline_b_architecture.py` | Reproducible figure generator. |
| `vrih_template/` | Downloaded official Word and LaTeX templates from the journal guide. |
| `pipeline_b_article_draft_backup.tex` | Backup of the previous generic `article` draft before VRIH conversion. |

## Journal Target: Virtual Reality & Intelligent Hardware

Journal URL: https://www.keaipublishing.com/en/journals/virtual-reality-and-intelligent-hardware/

Editorial status:

- Preliminary details were sent to VRIH.
- On 2026-07-01 at 10:44, Ms. Zhengfang Wu replied that the academic editor completed the initial assessment and encouraged full submission through Editorial Manager.
- This is a positive scope signal, not acceptance and not peer review. The full submission will still undergo comprehensive academic-editor assessment.
- Evidence file: `vrih_scope_encouragement_2026-07-01.txt`.

Why it fits:

- The paper is now framed as a VR digital-twin operator display, not as a pure UAV telemetry paper.
- VRIH scope includes VR/AR/MR, AI for VR/AR/MR, computer vision, sensing, visualization, teleoperation, scene management, tracking, and software architectures.
- The strongest fit is the HMD/VR pilot-facing task: dynamic UAV scene reconstruction for operator situational awareness under degraded video, narrow FOV, or BVLOS-like supervision.

Submission constraints currently known from the VRIH guide for authors:

| Requirement | Current handling |
|---|---|
| Research paper must be grounded in experiments and results. | The draft now contains an explicit evaluation protocol; results remain TBD. |
| Rapid communications are limited to 4 pages. | Not suitable; target full research paper. |
| Abstract should not exceed 250 words. | Current abstract is below 250 words. |
| Keywords: 1 to 7. | Current paper has 7 keywords. |
| Highlights are supported/expected as a separate item. | Drafted in `vrih_highlights.txt`. |
| Editable manuscript source required. | Current source is LaTeX and now uses the VRIH template class. |

Current format status:

- `pipeline_b_concept.tex` now uses the official `VRIH2025` LaTeX class.
- Compile with `xelatex`, not `pdflatex`, because the VRIH class loads `fontspec`.
- Current VRIH-format PDF length: 12 pages.
- The guide does not state a maximum length for full research papers. The only explicit page cap found is rapid communications: maximum 4 pages, which is not suitable for this work.

## A2 / Ayudante Doctor Baremo

Local baremo source:

`D:\AYTE DOCTOR\Convocatoria_Xabier_Olaz\00_BAREMO_CONVOCATORIA\BAREMO_DEFINITIVO_CONTRASTADO_A2.md`

Operational conclusion:

- The UPNA A2 rule gives the strong points to JCR-indexed journals: Q1 up to 3, Q2 up to 2, Q3 up to 1.
- VRIH is strategically attractive only if we can document the JCR status and quartile for the relevant year.
- The VRIH editorial email states a newly released 2025 Impact Factor of 6.1, and previous editorial material mentions high CiteScore and Scopus Q1 categories. These are useful quality indicators, but the local baremo says JCR quartile is the safe evidence for Q1/Q2/Q3 points.
- Before counting points, save the official JCR/Clarivate sheet for VRIH, including year, category, Journal Impact Factor, and quartile.

Practical planning value:

| Scenario | Baremo planning value |
|---|---|
| VRIH documented as JCR Q1 in the relevant year | Strong target, up to 3 points before author/contribution weighting. |
| VRIH documented as JCR Q2 | Still strong, up to 2 points. |
| VRIH has Impact Factor but no usable JCR quartile evidence | Do not plan as Q1/Q2; treat cautiously until verified. |
| Only Scopus/CiteScore/SJR evidence available | Useful as support, but not enough for the safest A2 estimate. |

## Current Manuscript Framing

Current title:

**A Virtual-Reality Digital Twin Operator Display for Dynamic UAV Scene Reconstruction from In-Flight Detections**

Core claim:

An implemented human-in-the-loop VR operator display reconstructs a dynamic UAV scene from in-flight object detections by converting them into georeferenced semantic telemetry and rendering persistent actors inside an Unreal/Cesium digital twin.

Claims deliberately avoided:

- No claim that the system replaces video.
- No claim that it is a primary piloting interface.
- No claim that it guarantees safe human piloting.
- No claim that semantic telemetry alone is sufficient for detect-and-avoid or BVLOS compliance.

## What Can Be Completed Now

Important: these items are preparatory evidence. They reduce risk and make the experiment reproducible, but they are not enough by themselves for a VRIH research paper if the manuscript claims an HMD/VR operator display.

| Work package | Output |
|---|---|
| VRIH-focused rewrite | Done in `pipeline_b_concept.tex`: title, abstract, motivation, contribution, conclusion. |
| Runtime contract documentation | Done in draft: `POST /api/obstacles`, `GET /api/ui/data`, entity lifecycle. |
| Evidence map | Done in draft: claim-to-evidence table. |
| Software-only bandwidth benchmark | Still to run: semantic message sizes, mean bitrate, p95 bitrate, packet rate. |
| Partial latency benchmark | Still to instrument: detector/sender to Brain to Unreal actor update. |
| Packet loss/jitter robustness | Still to implement with replay or impairment layer. |
| Synthetic tracking benchmark | Still to run with controlled trajectories and stale/despawn policies. |
| VRIH highlights | Drafted in `vrih_highlights.txt`. |

## Hardware-Dependent Work

| Evidence | Hardware needed |
|---|---|
| VR demonstration screenshots/video | HMD plus running Unreal VR configuration. |
| End-to-end source-to-HMD latency | HMD, instrumented detection source or real UAV, timestamp/capture method. |
| Geospatial error | Calibrated camera, UAV pose/GNSS, surveyed or RTK ground truth objects. |
| Human operator utility | HMD, participants/pilots, task protocol, baselines, questionnaires. |
| Low-visibility claims | Sensor-specific night/fog/glare/smoke or equivalent controlled trials. |

## VRIH Preliminary Email Draft

Subject:

Preliminary details for VRIH scope assessment - VR digital twin operator display for UAV operation

Dear Ms. Zhengfang Wu,

Thank you for your kind reply. As requested, please find below the preliminary details of the manuscript we are preparing. We would be grateful if the academic editor could assess whether this topic fits the scope of *Virtual Reality & Intelligent Hardware* before we proceed with the full submission.

**Proposed title**

A Virtual-Reality Digital Twin Operator Display for Dynamic UAV Scene Reconstruction from In-Flight Detections

**Proposed authorship**

Xabier Olaz; Daniel Alaez; Iker Goñi; Jesús Villadangos

**Abstract**

Remote UAV operation requires the pilot to maintain spatial awareness of the aircraft, terrain, obstacles, and mission-relevant objects under conditions where direct visual contact or continuous high-quality video may be unavailable. Conventional video-only or map-based interfaces can become limiting when communication bandwidth is constrained, when the camera field of view is narrow, or when the operation is performed beyond visual line of sight. This manuscript presents an implemented virtual-reality digital twin operator display in which a UAV pilot wearing a head-mounted display can inspect a dynamically reconstructed 3D representation of the operational scene.

The system converts in-flight object detections into georeferenced semantic telemetry and uses these data to spawn, update, and remove dynamic entities inside an immersive Unreal Engine and Cesium-based environment. By complementing video and map views with a persistent synthetic scene, the display preserves spatial context around the UAV and the surrounding environment rather than forcing the pilot to interpret all operational cues through a single camera perspective. The approach is intended as an auxiliary situational-awareness layer for tasks in which spatial interpretation is critical, such as obstacle monitoring, target localization, infrastructure inspection, and degraded-link supervision.

The contribution is a human-in-the-loop operator-display architecture that connects UAV perception, geospatial semantic telemetry, runtime scene management, and immersive VR visualization. The manuscript will describe the implemented perception-to-visualization pipeline, the runtime data contract between airborne or ground-side perception services and the VR environment, and the evaluation protocol for communication load, source-to-VR-headset latency, geospatial consistency, dynamic object persistence, and operator utility.

**Keywords**

Virtual reality; UAV; digital twin; scene reconstruction; semantic telemetry; teleoperation; situational awareness

Best regards,

Jesús Villadangos
Xabier Olaz

## Immediate Next Actions

1. Compile the rewritten LaTeX and fix errors.
2. Replace `TBD-BW` with a software-only bandwidth benchmark from replayed or synthetic detections.
3. Instrument Brain and Unreal timestamps for partial latency.
4. Capture HMD screenshots/video when the VR setup is available.
5. Retrieve and archive the VRIH JCR/Clarivate evidence before relying on Q1/Q2 A2 points.
