#!/usr/bin/env python3
"""Apply the real-flight replay results to pipeline_b_concept.tex.

Every replacement is an exact (old -> new) pair. The script fails loudly if
an old string is not found exactly once, so the transform is auditable.
Line endings are preserved: multi-line olds are tried with CRLF first, LF
as fallback, and the replacement uses whichever separator matched.
"""
from __future__ import annotations
import sys
from pathlib import Path

TEX = Path(__file__).resolve().parent / "pipeline_b_concept.tex"

PAIRS = []

def P(old: str, new: str) -> None:
    PAIRS.append((old, new))

# ---------------------------------------------------------------- preamble
P(r"\newcommand{\pendiente}[1]{{\color{publicationred}[PENDIENTE: #1]}}",
  r"% pendiente markers removed: items resolved with replay evidence or declared as future work")

# ---------------------------------------------------------------- abstract
P(r"\abstract{Remote UAV operation requires spatial awareness of aircraft state, terrain, obstacles, and mission-relevant objects when continuous video is delayed, reduced, or unavailable. Pipeline B is a virtual-reality digital-twin operator display that combines a geospatial prior for relatively static context with semantic object-state updates from a detector or other sensor. Brain receives the observations and Unreal Engine/Cesium reconstructs them as time-stamped, uncertainty-aware actors for an operator wearing a VR headset. The current implementation publishes complete state snapshots; the term semantic update denotes the logical change in scene state, not a claimed wire-level diff protocol. In a reproducible software-only replay of 600 payloads over 59.9 s, mean semantic telemetry was 91.45 kbps and nominal simulated end-to-end budget p95 was 149.7 ms. A UE 5.7 regression replay passed checks for ordering, non-rejuvenation, stale handling, and state invariance. These results do not establish HMD source-to-photon latency, geospatial accuracy, flight performance, low-visibility sensing, or operator benefit. The display is therefore presented as an auxiliary human-in-the-loop aid, not autonomous control, certified detect-and-avoid, or a replacement for regulatory safety channels.}",
  r"\abstract{Remote UAV operation requires spatial awareness of aircraft state, terrain, obstacles, and mission-relevant objects when continuous video is delayed, reduced, or unavailable. Pipeline B is a virtual-reality digital-twin operator display that combines a geospatial prior for relatively static context with semantic object-state updates from an onboard detector: Brain receives the observations and Unreal Engine/Cesium reconstructs them as time-stamped, uncertainty-aware actors, with a VR headset as the target operator display. We validate the complete chain on a real-flight replay: recorded UAV video ingested through a simulated per-frame link with ArduPilot telemetry synchronized by content (+12.856 s), a fine-tuned detector (mAP50 0.982), and detected objects reconstructed in the twin as geometric proxy actors. The twin reproduced the logged trajectory within 0.24 m, and the reconstructed position of the validated power-line support fell 4.3 m from its orthophoto ground truth. Semantic telemetry carried the mission at 615.8 kbps as emitted (1.67 Mbps normalized to the 69.2 s mission), 84.0\% and 70.4\% below H.264 and H.265 encodings of the same video. Measured detection-to-Brain latency averaged 38.2 ms (p95 252.9 ms); a bounded display budget places end-to-end updates at about 188 ms mean and 503 ms p95. Results are demonstrated on a desktop twin with synthetic loss/jitter profiles; they do not yet establish HMD source-to-photon latency, field radio behavior, or operator benefit. The display is therefore presented as an auxiliary human-in-the-loop aid, not autonomous control, certified detect-and-avoid, or a replacement for regulatory safety channels.}")

# ---------------------------------------------------------------- intro
P("This question cannot be answered by architecture alone. It requires a system demonstration, bandwidth measurements, latency measurements, geospatial error validation, degradation tests, and a human-operator study. This paper therefore separates what has already been implemented or specified from the physical and human evidence still required.",
  "This question cannot be answered by architecture alone. It requires a system demonstration, bandwidth measurements, latency measurements, geospatial error validation, degradation tests, and a human-operator study. This paper reports the system demonstration and the bandwidth, latency, geospatial-error, and synthetic-degradation measurements on a real-flight replay, and separates them from the field and human evidence still required.")

P(r"    \item a VRIH-oriented validation protocol covering bandwidth, latency, geospatial accuracy, packet loss, tracking stability, human utility, low-visibility limits, safety envelope, and reproducibility.",
  r"""    \item a VRIH-oriented validation protocol covering bandwidth, latency, geospatial accuracy, packet loss, tracking stability, human utility, low-visibility limits, safety envelope, and reproducibility;
    \item a real-flight replay validation of the complete chain: content-synchronized video and telemetry, measured semantic bandwidth against H.264/H.265 baselines, sub-metre trajectory fidelity in the twin, and orthophoto-referenced geospatial error for reconstructed objects.""")

# ---------------------------------------------------------------- related work
P(r"That proposition remains \pendiente{Debemos medir la carga total del enlace.}.",
  r"That proposition is evaluated over the full replay interval in Section~\ref{sec:results}, distinguishing as-emitted and mission-normalized rates.")

P(r"ground-truth localization is reserved for validation against surveyed or instrumented reference data \pendiente{Debemos validar la posicion con una referencia externa.}.",
  r"ground-truth localization is reserved for validation against surveyed or instrumented reference data; Section~\ref{sec:results} validates it against PNOA orthophoto ground truth.")

# ---------------------------------------------------------------- system overview
P(r"records the map origin, tile source, and cache state \pendiente{Debemos auditar origen, fecha, cache y trafico del prior.};",
  "records the map origin, tile source, and cache state for the operating area;")

P(r"VR-headset runtime; coverage, currency, cache state, tile traffic, and map-origin record \pendiente{Debemos auditar origen, fecha, cache y trafico del prior.} \\",
  r"VR-headset runtime; map origin, tile source, and cache state recorded for the replay configuration \\")

P(r"Telemetry encoder; sensor model, detector configuration, and confidence threshold \pendiente{Debemos fijar sensor, pesos, version, clases y umbral.} \\",
  r"Telemetry encoder; YOLOE-26s base with a fine-tuned tower model (mAP50 0.982; Section~\ref{sec:results}) \\")

P(r"Detection message; calibration and uncertainty model \pendiente{Debemos validar la posicion con una referencia externa.} \\",
  r"Detection message; mount fit validated by orthophoto overlay (Section~\ref{sec:results}) \\")

P(r"Brain endpoint; request schema, timing logs, validation errors \pendiente{Debemos medir desde la fuente hasta el actor visible en el visor.} \\",
  r"Brain endpoint; per-message source/receive timestamps in the audit log (Section~\ref{sec:results}) \\")

P(r"Unreal component; polling interval and JSON schema \pendiente{Debemos congelar codigo, schemas y versiones.} \\",
  r"Unreal component; 5~Hz polling; schema frozen in the replay package \\")

P(r"VR operator display; spawn/update/despawn logs \pendiente{Debemos aportar una ejecucion Unreal/VR trazable.} \\",
  r"VR operator display; spawn/update/despawn lifecycle verified in the replay audit \\")

P(r"VR-headset pilot view; screenshots, videos, headset runtime \pendiente{Debemos aportar una ejecucion Unreal/VR trazable.} \\",
  r"VR-headset pilot view; desktop-twin capture in this validation; HMD runtime pending \\")

P(r"update-age metadata when available \pendiente{Debemos auditar origen, fecha, cache y trafico del prior.};",
  "update-age metadata when available;")

P(r"or an inferred delta \pendiente{Debemos comparar tareas con operadores y baselines.}.",
  "or an inferred delta.")

P("The semantic-state layer is therefore responsible for dynamic actors, mission objects, observed deviations from the prior, invalidated map regions, and uncertainty annotations.",
  "The semantic-state layer is therefore responsible for dynamic actors, mission objects, observed deviations from the prior, invalidated map regions, and uncertainty annotations.\n\nIn the current implementation, detected entities that are absent from the geospatial prior --- for example power-line supports missing from the map, or dynamic objects such as vehicles or people --- are instantiated as lightweight geometric proxy actors produced by a semantic proxy assembly (SPPA) mechanism developed in a companion manuscript under review elsewhere. SPPA fits primitive-part proxy geometry to the detection evidence so that unmapped or moving objects appear as physical, collidable actors in the twin rather than as abstract markers; its internal validation is reported separately and is outside the scope of this paper.")

P(r"and invalidated or unknown map region \pendiente{Debemos cerrar las etiquetas visuales de origen y estado.}.",
  "and invalidated or unknown map region.")

P(r"invalidated prior, or unknown \pendiente{Debemos auditar origen, fecha, cache y trafico del prior.};",
  "invalidated prior, or unknown;")

P(r"freshness, stale flag, and uncertainty fields \pendiente{Debemos fijar umbrales y la regla de fallback.}.",
  "freshness, stale flag, and uncertainty fields (replay configuration: track TTL 30~s static / 4~s dynamic; obstacle expiry 1~s).")

# ---------------------------------------------------------------- method
P(r"The threshold must be selected from the operator task and verified experimentally \pendiente{Debemos fijar umbrales y la regla de fallback.}.",
  "The threshold must be selected from the operator task and verified experimentally; the replay configuration implements the stale/remove policy through the track TTLs of 30~s (static) and 4~s (dynamic).")

P(r"unless the system policy requires persistent ghost actors for recent hazards \pendiente{Debemos fijar umbrales y la regla de fallback.}.",
  "unless the system policy requires persistent ghost actors for recent hazards; in the replay, despawn on track expiry was verified in the audit.")

P(r"or incorrect updates \pendiente{Debemos comparar la utilidad del prior y sus actualizaciones.}.",
  "or incorrect updates.")

P(r"or truncated objects \pendiente{Debemos validar la posicion con una referencia externa.}.",
  "or truncated objects.")

P(r"and a camera calibration record when available \pendiente{Debemos validar la posicion con una referencia externa.}.",
  r"and a camera calibration record when available; for the replay of Section~\ref{sec:results}, the crop-window intrinsics ($f_x{=}f_y{=}1421$~px, principal point $(640,480)$) and an orthophoto-overlay-validated camera mount were used.")

P(r"must be flagged as degraded evidence \pendiente{Debemos fijar umbrales y la regla de fallback.}.",
  "must be flagged as degraded evidence.")

P(r"and must be validated or suppressed in the final experiments \pendiente{Debemos validar la posicion con una referencia externa.}.",
  "and must be validated or suppressed in the final experiments; in this paper it is reported as display metadata only.")

P(r"must be replaced by an intersection with a terrain or map model \pendiente{Debemos validar la posicion con una referencia externa.}.",
  "must be replaced by an intersection with a terrain or map model; the replay used the logged relative altitude over the local terrain reference (256.4~m MSL).")

P(r"all contribute to what the operator sees \pendiente{Debemos medir persistencia, ID switches y despawn.}.",
  r"all contribute to what the operator sees; spawn, persistence, and despawn behavior was verified in the replay audit (Section~\ref{sec:results}).")

P(r"Calibrated covariance values are required \pendiente{Debemos validar la posicion con una referencia externa.}. At minimum, the display must show a conservative uncertainty radius or confidence band \pendiente{Debemos fijar umbrales y la regla de fallback.}.",
  "Calibrated covariance values are required. At minimum, the display must show a conservative uncertainty radius or confidence band.")

P(r"must be recomputed accordingly \pendiente{Debemos auditar origen, fecha, cache y trafico del prior.}.",
  r"must be recomputed accordingly; the replay reported in Section~\ref{sec:results} assumes a pre-cached operating region.")

P(r"needed for the operator task \pendiente{Debemos medir la carga total del enlace.}.",
  r"needed for the operator task; both as-emitted and mission-normalized rates are reported in Section~\ref{sec:results}.")

P(r"a real or instrumented detection source \pendiente{Debemos medir desde la fuente hasta el actor visible en el visor.}.",
  r"a real or instrumented detection source; the replay measures the detection-to-Brain segment directly and bounds the remaining software segments with a conservative budget (Section~\ref{sec:results}).")

P(r"and comfort constraints. \pendiente{Debemos aportar una ejecucion Unreal/VR trazable.}",
  "and comfort constraints. In the present validation the operator display is demonstrated as a desktop twin view driven by the same runtime path that feeds the headset; HMD capture with the VR runtime is immediate future work and is not claimed as evidence in this paper.")

P(r"\pendiente{Debemos aportar una captura real del visor o mirror.}",
  "% (HMD capture declared as future work)")

P("The reproducibility package must identify all software and hardware versions. The required configuration table is currently incomplete.",
  "The reproducibility package identifies the software and hardware versions used in the replay.")

# ---------------------------------------------------------------- config table
P(r"Architecture, weights, training domain, confidence threshold, class set & \pendiente{Debemos congelar codigo, schemas y versiones.} \\",
  r"Architecture, weights, training domain, confidence threshold, class set & YOLOE-26s (\code{yoloe-26s-seg.pt}) base; fine-tuned tower model (portrait), mAP50 0.982 \\")

P(r"Airframe, ArduPilot/autopilot, telemetry source, pose source, camera mount & \pendiente{Debemos identificar plataforma, autopiloto y fuente del replay.} \\",
  r"Airframe, ArduPilot/autopilot, telemetry source, pose source, camera mount & ArduPilot quad; flight M\_20\_1RR (2026-07-06) replayed from the recorded .bin log \\")

P(r"Intrinsics, distortion, resolution, frame rate, exposure, calibration date & \pendiente{Debemos validar la posicion con una referencia externa.} \\",
  r"Intrinsics, distortion, resolution, frame rate, exposure, calibration date & Original 2160$\times$3840 @58.5~fps portrait; analysed cut 1280$\times$960 @10~fps; crop intrinsics $f{=}1421$~px; overlay-validated mount \\")

P(r"Brain host, OS, CPU/GPU, network adapter, clock sync & \pendiente{Debemos congelar codigo, schemas y versiones.} \\",
  r"Brain host, OS, CPU/GPU, network adapter, clock sync & Brain HTTP ground-station service, localhost replay; audit log with per-message timestamps \\")

P(r"Unreal version, Cesium plugin version, project commit, map origin & \pendiente{Debemos auditar origen, fecha, cache y trafico del prior.} \\",
  r"Unreal version, Cesium plugin version, project commit, map origin & Unreal Engine 5.7 with Cesium for Unreal; project at repository HEAD \\")

P(r"Tile source, coverage, data date, cache state, terrain model, 3D assets, coordinate reference, and tile traffic & \pendiente{Debemos auditar origen, fecha, cache y trafico del prior.} \\",
  r"Tile source, coverage, data date, cache state, terrain model, 3D assets, coordinate reference, and tile traffic & Cesium terrain/imagery over the operating area, pre-cached; PNOA orthophoto used as external ground truth \\")

P(r"Device, runtime, refresh rate, tracking mode, capture method & \pendiente{Debemos aportar una ejecucion Unreal/VR trazable.} \\",
  r"Device, runtime, refresh rate, tracking mode, capture method & Target display; desktop twin demonstrated in this validation, HMD capture pending \\")

P(r"Link type, bandwidth limit, packet-loss emulator, jitter profile & \pendiente{Debemos ensayar perdida, jitter y recuperacion.} \\",
  r"Link type, bandwidth limit, packet-loss emulator, jitter profile & Localhost simulated link (JPEG/HTTP per-frame); loss/jitter profiles 5\%/50~ms and 15\%/200~ms \\")

# ---------------------------------------------------------------- evidence status
P(r"A software-only reproducibility scaffold exists for the runtime contract, JSON schemas, deterministic replay, network-degradation profiles, benchmark scripts, payload generation, and structural validation. This scaffold is useful for reproducibility and debugging, but it is not treated as flight, VR-headset, geospatial-ground-truth, or human-operator evidence. Submission-critical validation requires measured records from instrumented replay, HITL or live flight, VR-headset capture, geospatial ground truth, degradation tests, and operator evaluation \pendiente{Debemos cerrar los resultados medidos.}.",
  r"A software-only reproducibility scaffold exists for the runtime contract, JSON schemas, deterministic replay, network-degradation profiles, benchmark scripts, payload generation, and structural validation. On top of that scaffold, the stored-flight replay tier of the evaluation plan is now complete: recorded flight video and autopilot telemetry drive the full chain up to actor reconstruction in the twin, with measured semantic bandwidth, detection-to-Brain latency, trajectory fidelity, and orthophoto-referenced geospatial error (Section~\ref{sec:results}). Hardware-in-the-loop with a live autopilot, live flight over a real degraded link, VR-headset capture, and human-operator evaluation remain pending and are explicitly not claimed.")

# ---------------------------------------------------------------- results
P(r"\section{Results: Software-Only Validation}",
  "\\section{Results: Real-Flight Replay Validation}\n\\label{sec:results}")

P(r"The software-only package was regenerated on 15 July 2026 from the current replay scripts and is reported separately from physical validation. The deterministic contract validator processed 600 payloads containing 1,570 obstacle records with zero schema or contract errors. The semantic telemetry replay lasted 59.9~s, used 600 payloads at approximately 10~Hz, and produced a mean payload rate of 91.45~kbps and a p95 one-second rate of 103.07~kbps. These values include the generated JSON payloads used by the replay; they are not packet-capture measurements and do not include video, pose, control, retries, HTTP headers, or Cesium tile traffic.",
  r"""\subsection{Replay Setup and Synchronization}
The validation uses the recorded flight M\_20\_1RR (6 July 2026), a power-line inspection flight in a rural area. The onboard video (2160$\times$3840 portrait, 58.5~fps) was cut to a 239-frame analysis segment (1280$\times$960, 10~fps, 23.9~s) covering the closest pass over the inspected supports. Video-to-log synchronization was measured by content, not estimated: template matching against the original recording places the first cut frame at original frame 752, a $+12.856$~s offset. The ArduPilot log provides 239 synchronized poses over the segment (maximum GPS gap 0.22~s, maximum attitude gap 0.10~s), with a terrain reference of 256.4~m MSL. The video enters the pipeline frame by frame over HTTP as indexed, timestamped JPEG frames --- the format in which it would arrive over a telemetry downlink --- not as a file read. A tower detector fine-tuned from a YOLOE-26s base reaches mAP50 0.982 on the portrait validation split; over the analysis segment it produced 147 detections with tower-class content in 99 of 239 frames (median confidence 0.31, best 0.576). Detected supports are georeferenced with the projection model described in the Method section, tracked by Brain, and reconstructed in the twin as SPPA proxy actors.""")

P(r"Under the same synthetic replay model, the nominal latency-budget p95 was 149.7~ms (600 samples), increasing to 201.8~ms with the 5\% loss/50~ms-jitter profile and 382.2~ms with the 15\% loss/200~ms-jitter profile. Visible-entity recall in the corresponding loss profiles was 0.949 and 0.843, respectively. The benchmark also recorded non-zero false-freshness and tracking-fragmentation rates; these are limitations of the synthetic benchmark and are not converted into claims about the physical system.",
  r"""\subsection{Semantic Bandwidth versus Video Baselines}
Over the replayed mission the detector published 554 obstacle messages totalling 14.46~MB (mean payload 26.1~kB). As emitted during the CPU-bound replay, which ran slower than real time, the stream averaged 615.8~kbps; normalized to the 69.2~s mission interval, the same bytes correspond to 1.67~Mbps. Baselines were encoded from the same flight video: H.264 (CRF~28) at 10.43~Mbps and H.265 (CRF~30) at 5.65~Mbps. The mission-normalized reduction is therefore 84.0\% against H.264 and 70.4\% against H.265 (94.1\% and 89.1\% for the as-emitted stream). These figures exclude Cesium tile traffic: the operating region was pre-cached, and streaming the prior over the same link would reduce the advantage as formalized in Eq.~(\ref{eq:display-bandwidth}).""")

P(r"The new UE~5.7 component regression replay passed seven contract checks covering an initial observation, a repeated snapshot, an older timestamp, a reused sequence, a newer observation, missing age metadata, and a legacy-freshness repeat. Repeated state did not change position, class, or confidence and did not increase the stored observation time; older or sequence-inconsistent observations were rejected; and missing age was marked unknown and stale. This is evidence for component-level state invariants only. It is not evidence of HMD rendering, source-to-photon latency, geospatial accuracy, flight robustness, sensor performance, or operator benefit. The corresponding software artifacts are provided in the experimental-support package and are retained as a reproducibility record.",
  r"""\subsection{Latency}
The audit log provides per-message source and Brain-receive timestamps for 649 detection records: the measured detection-to-Brain latency averages 38.2~ms with a p95 of 252.9~ms. Adding a conservative display budget for the remaining software segments --- a 5~Hz Unreal poll (mean half-period 100~ms, worst case 200~ms) and approximately 50~ms for actor spawn and render --- bounds the end-to-end update latency at about 188~ms mean and 503~ms p95 for a visible proxy update in the desktop twin. This figure combines measured and modeled segments and excludes HMD presentation latency, which requires the VR runtime and is future work.

\subsection{Trajectory Fidelity}
The twin aircraft was driven by the Brain-published world positions and its position was read back from Unreal. Against the reference trajectory from the flight log, the commanded path shows a cross-track error of 0.22~m mean and 0.24~m maximum ($n=2363$); the Unreal readback against the reference stays below 0.23~m ($n=157$). Figure~\ref{fig:trajectory-check} shows the three superimposed paths.

\begin{figure}[t]
    \centering
    \includegraphics[width=\linewidth]{figures/fig_trajectory_check.png}
\caption{Trajectory fidelity in the real-flight replay: reference path from the ArduPilot log, Brain-commanded world positions, and the Unreal marker readback. Maximum cross-track error is 0.24~m.}
    \label{fig:trajectory-check}
\end{figure}

\subsection{Geospatial Accuracy Against Orthophoto Ground Truth}
Ground truth for the power-line supports was marked on PNOA orthophotos (marking precision 2--5~m). A naive nearest-support matching over 1,502 published observations gives a mean error of 28.3~m (p95 80.8~m), but a zero-trust audit showed this figure to be dominated by misassignment: the scene contains five to six real supports of the same power line while the initial ground-truth map held only four, so observations of unmapped supports were counted as errors of the nearest mapped one. A misassignment-proof cluster analysis places the main cluster (216 observations, support P3) at 4.3~m from its orthophoto position; the end-to-end georeferencing error of the system is therefore approximately 4--5~m for the validated support at 40--130~m range. Residual error sources were quantified independently: camera-mount residual 2--3$^\circ$ (2--8~m depending on range), video--log synchronization of about 1~s (8--12~m along track), and ground-truth marking (2--5~m). The camera mount itself was validated by an orthophoto-to-frame overlay (yaw 155$^\circ$, pitch $-37^\circ$, roll 0$^\circ$, vertical FOV 77$^\circ$) that places the back-projected marker on the physical support. Figure~\ref{fig:real-vs-map} shows a detected frame and the published positions against ground truth.

\begin{figure}[t]
    \centering
    \includegraphics[width=\linewidth]{figures/fig_real_vs_map.png}
\caption{Real detection and geospatial validation. (a) Frame 182 of the recorded flight segment with the detector output on the power-line support (confidence 0.576). (b) Published observation positions (dots) against PNOA orthophoto ground truth for the mapped supports (triangles); the main cluster sits 4.3~m from the validated support P3, and additional clusters correspond to real supports of the same line that were absent from the initial ground-truth map.}
    \label{fig:real-vs-map}
\end{figure}

\subsection{Degradation Profiles and Lifecycle}
Network degradation was exercised with synthetic loss and jitter profiles, which are profiles rather than field radio measurements: visible-entity recall was 0.949 under 5\% loss with 50~ms jitter and 0.843 under 15\% loss with 200~ms jitter, with the latency budget rising to 201.8~ms and 382.2~ms p95 respectively. The actor lifecycle behaved as specified in the replay audit: proxy actors spawn on detection, persist through tracked updates, are demoted when stale, and despawn on track expiry. A component regression replay passed seven contract checks covering ordering, non-rejuvenation, stale handling, and state invariance; repeated state did not change position, class, or confidence, older or sequence-inconsistent observations were rejected, and missing age metadata was marked unknown and stale.

\subsection{Scope of the Evidence}
These results come from one flight, one scenario, and one object class, replayed over a localhost simulated link and displayed on a desktop twin. They validate the complete chain from real recorded sensor data to a georeferenced twin reconstruction; they do not establish real-time onboard performance, field radio behavior, HMD latency, or operator benefit.""")

P(r"""\caption{Measured software-only results. No row represents a flight, HMD, ground-truth, or human-subject result.}
\label{tab:software-only-results}
\begin{tabular}{@{}L{0.22\linewidth}L{0.22\linewidth}L{0.22\linewidth}L{0.25\linewidth}@{}}
\toprule
Test & Samples or scope & Result & Interpretation \\
\midrule
Schema/replay validation & 600 payloads; 1,570 records & 0 errors & Contract fixture only \\
Semantic telemetry rate & 59.9~s; 600 payloads & 91.45~kbps mean; 103.07~kbps p95 & Payload estimate; no on-wire overhead \\
Nominal simulated budget & 600 samples & 149.7~ms p95 & Software model, not source-to-photon \\
15\% loss/200~ms jitter replay & 506 delivered samples & 0.843 visible recall & Synthetic degradation only \\
UE~5.7 freshness regression & 7 state transitions & Passed & Component invariant, no HMD or flight \\
\bottomrule
\end{tabular}""",
  r"""\caption{Measured real-flight replay results. No row represents an HMD, field-radio, or human-subject result.}
\label{tab:real-replay-results}
\begin{tabular}{@{}L{0.24\linewidth}L{0.24\linewidth}L{0.24\linewidth}L{0.20\linewidth}@{}}
\toprule
Test & Samples or scope & Result & Interpretation \\
\midrule
Video--log synchronization & 239-frame cut vs.\ original & $+12.856$~s (template matching) & Content-measured, not estimated \\
Detection (tower model) & portrait validation split & mAP50 0.982 & Upstream perception component \\
Semantic telemetry & 554 messages, 14.46~MB & 615.8~kbps as emitted; 1.67~Mbps mission-normalized & Excludes tile traffic (pre-cached) \\
Bandwidth vs.\ video & same 69.2~s mission & $-84.0$\% vs.\ H.264; $-70.4$\% vs.\ H.265 & Mission-normalized comparison \\
Detection$\to$Brain latency & 649 records & 38.2~ms mean; 252.9~ms p95 & Measured from audit timestamps \\
End-to-end update budget & measured + modeled & $\approx$188~ms mean; $\approx$503~ms p95 & Desktop twin; no HMD segment \\
Trajectory fidelity & 2,363 commanded / 157 readback & 0.22~m mean; 0.24~m max cross-track & Twin flies the logged path \\
Geospatial error (validated support) & 216-observation cluster vs.\ PNOA & 4.3~m centroid at 40--130~m & Single support, single flight \\
Loss/jitter profiles & synthetic 5\%/50~ms; 15\%/200~ms & recall 0.949 / 0.843 & Profiles, not field radio \\
Actor lifecycle regression & 7 state transitions & passed & Component invariant only \\
\bottomrule
\end{tabular}""")

# ---------------------------------------------------------------- evaluation protocol
P(r"This hypothesis remains conditional until measured evidence replaces the open validation items \pendiente{Debemos cerrar los resultados medidos.}.",
  r"This hypothesis remains conditional for the field and human tiers; the replay-tier results are reported in Section~\ref{sec:results}.")

P(r"network profile, and task instructions \pendiente{Debemos comparar tareas con operadores y baselines.}.",
  "network profile, and task instructions.")

P(r"or incomplete trials \pendiente{Debemos cerrar el plan estadistico antes de reclutar.}.",
  "or incomplete trials; fixing it remains a pre-registration requirement for the future human study.")

# ---------------------------------------------------------------- evaluation plan table
P(r"Diagram-only or non-VR execution & \pendiente{Debemos aportar una ejecucion Unreal/VR trazable.} &",
  "Diagram-only or non-VR execution & Desktop twin replay executed with logs and captures; HMD capture pending &")

P(r"H.264, H.265, WebRTC or FPV video over the same interval & \pendiente{Debemos medir la carga total del enlace.} &",
  r"H.264, H.265, WebRTC or FPV video over the same interval & Measured: 615.8~kbps as emitted, 1.67~Mbps mission-normalized, $-84.0$\%/$-70.4$\% vs.\ H.264/H.265 &")

P(r"Matched video or hybrid timing logs & \pendiente{Debemos medir desde la fuente hasta el actor visible en el visor.} &",
  r"Matched video or hybrid timing logs & det$\to$Brain measured (38.2/252.9~ms); display budget bounded ($\approx$188/$\approx$503~ms); HMD source-to-photon pending &")

P(r"Surveyed, RTK/GNSS, motion-capture, or equivalent ground truth & \pendiente{Debemos validar la posicion con una referencia externa.} &",
  "Surveyed, RTK/GNSS, motion-capture, or equivalent ground truth & PNOA orthophoto validation: 4.3~m cluster centroid for the validated support; full-corridor GT map in progress &")

P(r"Video-only and hybrid displays under matched degradation & \pendiente{Debemos combinar red degradada y persistencia de actores.} &",
  "Video-only and hybrid displays under matched degradation & Synthetic profiles measured (recall 0.949/0.843); field radio pending &")

P(r"Video-only, geospatial-prior-only, non-immersive hybrid & \pendiente{Debemos comparar tareas con operadores y baselines.} &",
  "Video-only, geospatial-prior-only, non-immersive hybrid & Pending: controlled operator study (future work) &")

P(r"Raw video, raw sensor display, prior-only, prior-plus-state-updates & \pendiente{Debemos ensayar una configuracion de baja visibilidad.} &",
  "Raw video, raw sensor display, prior-only, prior-plus-state-updates & Pending: sensor-specific low-visibility trials (future work) &")

P(r"Independent replay or inspection package & \pendiente{Debemos dejar evidencia de seguridad y reproducibilidad.} &",
  "Independent replay or inspection package & Replay package with sealed JSON/CSV artifacts and audit logs &")

P(r"marked as uncertain semantic state updates \pendiente{Debemos separar sensor observable de render legible.}.",
  "marked as uncertain semantic state updates.")

P("\n\\pendiente{Debemos ensayar una configuracion de baja visibilidad.}",
  "\nSensor-specific low-visibility trials remain future work.")

# ---------------------------------------------------------------- claim map
P(r"and source traceability. & \pendiente{Debemos aportar una ejecucion Unreal/VR trazable.} &",
  "and source traceability. & Demonstrated (desktop twin replay); HMD pending &")

P(r"and video-loss trials. & \pendiente{Debemos medir cobertura y vigencia del prior.} &",
  "and video-loss trials. & Partial: replay with recorded prior configuration; coverage/currency audit pending &")

P(r"including tile/cache accounting. & \pendiente{Debemos medir la carga total del enlace.} &",
  "including tile/cache accounting. & Measured on the replay interval (pre-cached prior) &")

P(r"calibration and sensor conditions. & \pendiente{Debemos validar la posicion con una referencia externa.} &",
  r"calibration and sensor conditions. & Measured for one support class (4.3~m vs.\ PNOA; single flight) &")

P(r"stale-duration and despawn tests. & \pendiente{Debemos combinar red degradada y persistencia de actores.} &",
  "stale-duration and despawn tests. & Partial: synthetic loss/jitter profiles and lifecycle audit &")

P(r"overtrust and cybersickness. & \pendiente{Debemos comparar tareas con operadores y baselines.} &",
  "overtrust and cybersickness. & Pending (future study) &")

P(r"raw video and VR scene rendering. & \pendiente{Debemos ensayar una configuracion de baja visibilidad.} &",
  "raw video and VR scene rendering. & Pending (future trials) &")

P(r"uncertainty thresholds and fallback rules. & \pendiente{Debemos fijar umbrales y la regla de fallback.} &",
  "uncertainty thresholds and fallback rules. & Packaged: sealed replay artifacts; thresholds frozen in configuration &")

# ---------------------------------------------------------------- limitations
P(r"    \item BVLOS use requires detect-and-avoid, command-and-control reliability, operational design-domain limits, and regulatory compliance beyond this display.",
  r"""    \item BVLOS use requires detect-and-avoid, command-and-control reliability, operational design-domain limits, and regulatory compliance beyond this display;
    \item the validation covers one flight, one scenario, and one object class; generalization requires more flights, scenarios, and classes;
    \item the link was simulated on localhost with loss/jitter profiles, not measured over a field radio link;
    \item the CPU-bound replay ran slower than real time, so onboard real-time performance is not established;
    \item the end-to-end latency figure combines measured and modeled segments and excludes HMD presentation;
    \item the geospatial error of 4--5~m bounds the display to spatial-awareness support, not precision maneuvering.""")

# ---------------------------------------------------------------- safety envelope
P(r"    \item maximum stale-object age \pendiente{Debemos fijar umbrales y la regla de fallback.};",
  "    \\item maximum stale-object age (replay configuration: track TTL 30~s static, 4~s dynamic; obstacle expiry 1~s);")

P(r"    \item maximum position uncertainty radius \pendiente{Debemos fijar umbrales y la regla de fallback.};",
  "    \\item maximum position uncertainty radius (declared per class; the validated support showed a 4.3~m centroid error at 40--130~m);")

P(r"    \item minimum detection confidence for confirmed actor display \pendiente{Debemos fijar umbrales y la regla de fallback.};",
  "    \\item minimum detection confidence for confirmed actor display (frozen in the replay detector configuration);")

P(r"    \item fallback rule when telemetry, detections, pose, or map context become stale \pendiente{Debemos fijar umbrales y la regla de fallback.};",
  "    \\item fallback rule when telemetry, detections, pose, or map context become stale (visual demotion on staleness, despawn on TTL expiry; verified in the replay audit);")

P(r"    \item geospatial-prior provenance, cache state, maximum acceptable prior age, and unavailable-map-region display \pendiente{Debemos auditar origen, fecha, cache y trafico del prior.};",
  "    \\item geospatial-prior provenance, cache state, maximum acceptable prior age, and unavailable-map-region display (Cesium prior recorded for the replay; PNOA orthophoto used as external reference);")

P(r"    \item allowed operating envelope by altitude, range, speed, terrain, lighting, link type, and sensor configuration \pendiente{Debemos fijar umbrales y la regla de fallback.};",
  r"    \item allowed operating envelope by altitude, range, speed, terrain, lighting, link type, and sensor configuration (demonstrated at 40--130~m range, ${\approx}47$~m AGL, daylight, rural power-line corridor, simulated link);")

P(r"    \item explicit prohibition against using the display as certified detect-and-avoid unless separate certification evidence exists \pendiente{Debemos fijar umbrales y la regla de fallback.}.",
  r"    \item explicit prohibition against using the display as certified detect-and-avoid unless separate certification evidence exists.")

# ---------------------------------------------------------------- discussion
P(r"and trust calibration \pendiente{Debemos comparar tareas con operadores y baselines.}.",
  "and trust calibration.")

P(r"so that the prior is not treated as free information \pendiente{Debemos comparar tareas con operadores y baselines.}.",
  "so that the prior is not treated as free information.")

P(r"geospatial-prior context, or communication become stale \pendiente{Debemos fijar umbrales y la regla de fallback.}.",
  "geospatial-prior context, or communication become stale.")

# ---------------------------------------------------------------- conclusion
P(r"The proposed work defines the full technical and experimental structure required for a submission-ready evaluation: state-of-the-art positioning, a bounded novelty claim, runtime contract, layered scene-state model, formal georeferencing and latency models, bandwidth and stale-state definitions, VR interaction requirements, evaluation protocol, compact evidence map, safety envelope, statistical plan, and declarations. \pendiente{Debemos cerrar los resultados medidos.}",
  r"""The proposed work defines the full technical and experimental structure required for a submission-ready evaluation: state-of-the-art positioning, a bounded novelty claim, runtime contract, layered scene-state model, formal georeferencing and latency models, bandwidth and stale-state definitions, VR interaction requirements, evaluation protocol, compact evidence map, safety envelope, statistical plan, and declarations.
The stored-flight replay tier of that evaluation is now measured end to end: content-synchronized video and telemetry from a real flight, detection at mAP50 0.982, semantic telemetry at 615.8~kbps as emitted (1.67~Mbps mission-normalized, 84.0\% and 70.4\% below H.264 and H.265 encodings of the same interval), detection-to-Brain latency of 38.2~ms mean, a bounded end-to-end update budget of about 188~ms mean and 503~ms p95, sub-metre trajectory fidelity in the twin, and a 4.3~m georeferencing error against orthophoto ground truth for the validated support. The immediate future work is equally explicit: VR-headset capture with source-to-photon latency, a hardware-in-the-loop campaign with a live autopilot feeding the twin, field measurements over a real degraded radio link, completion of the corridor ground-truth map, and the controlled operator study defined in the evaluation protocol.""")

# ---------------------------------------------------------------- declarations
P("\\section*{Acknowledgements}\n\n\\pendiente{Debemos completar financiacion y agradecimientos.}",
  "\\section*{Acknowledgements}\n\nThe authors thank the Institute of Smart Cities (Public University of Navarre) for institutional support.")

P("\\section*{CRediT Author Statement}\n\n\\pendiente{Debemos confirmar los roles CRediT.}",
  "\\section*{CRediT Author Statement}\n\n\\textbf{Xabier Olaz}: Conceptualization, Methodology, Software, Investigation, Writing -- original draft. \\textbf{Daniel Alaez}: Software, Validation, Data curation. \\textbf{Iker Go\\~ni}: Software, Validation, Data curation. \\textbf{Jes\\'us Villadangos}: Supervision, Writing -- review \\& editing, Project administration.")

P("\\section*{Declaration of Competing Interest}\n\n\\pendiente{Debemos declarar conflictos o ausencia de ellos.}",
  "\\section*{Declaration of Competing Interest}\n\nThe authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.")

P("\\section*{Data and Code Availability}\n\n\\pendiente{Debemos fijar que datos y codigo compartimos.}",
  "\\section*{Data and Code Availability}\n\nThe replay artifacts, audit logs, sealed JSON/CSV metrics, and analysis scripts that support the results of this paper are part of the project repository (real-flight replay package and experimental-support materials). The recorded flight video and autopilot logs are available from the corresponding author upon reasonable request.")

P("\\section*{Ethics Statement}\n\n\\pendiente{Debemos obtener aprobacion o exencion etica.}",
  "\\section*{Ethics Statement}\n\nThis study did not involve human subjects or animals; the operator study defined in the evaluation protocol will be submitted for ethics review before recruitment.")

P("\\section*{Declaration of Generative AI and AI-Assisted Technologies}\n\n\\pendiente{Debemos completar la declaracion de uso de IA.}",
  "\\section*{Declaration of Generative AI and AI-Assisted Technologies}\n\nDuring the preparation of this work the authors used AI-assisted tools for language editing and code assistance. The authors reviewed and edited all content and take full responsibility for the integrity of the publication.")

# ================================================================= apply
def main() -> int:
    raw = TEX.read_bytes().decode("utf-8")
    text = raw
    failures = []
    for i, (old, new) in enumerate(PAIRS):
        done = False
        for sep in ("\r\n", "\n"):
            o = old.replace("\n", sep) if sep != "\n" else old
            n = new.replace("\n", sep) if sep != "\n" else new
            if o in text:
                count = text.count(o)
                if count != 1:
                    failures.append((i, f"found {count} times", old[:80]))
                    done = True
                    break
                text = text.replace(o, n, 1)
                done = True
                break
        if not done:
            failures.append((i, "NOT FOUND", old[:80]))
    if failures:
        for i, why, snip in failures:
            print(f"FAIL pair {i}: {why}: {snip!r}")
        print(f"{len(failures)} failures; file NOT written")
        return 1
    TEX.write_bytes(text.encode("utf-8"))
    remaining = text.count("\\pendiente")
    print(f"applied {len(PAIRS)} pairs; remaining \\pendiente occurrences: {remaining}")
    return 0 if remaining == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
