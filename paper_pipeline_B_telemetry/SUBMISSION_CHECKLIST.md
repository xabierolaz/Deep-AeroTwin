# VRIH Submission Checklist — Pipeline B (semantic telemetry)

Target journal: *Virtual Reality & Intelligent Hardware* (VRIH), via Editorial Manager.
Editorial contact: scope encouragement received from Zhengfang Wu, 2026-07-01
(`vrih_scope_encouragement_2026-07-01.txt`). APC: 1200 USD.

## Manuscript package

| Item | File | Status |
|---|---|---|
| Manuscript (PDF) | `pipeline_b_concept.pdf` (27 pp) | ✅ compiled clean, 0 undefined refs |
| Source (LaTeX) | `pipeline_b_concept.tex` + `VRIH2025.cls` | ✅ |
| Abstract | in tex, 239 words (limit 250) | ✅ |
| Keywords | 7 | ✅ |
| Highlights | `vrih_highlights.txt` (5 bullets, ≤85 chars) | ✅ updated with real results |
| CRediT statement | in tex | ✅ roles to be confirmed by all authors |
| Declaration of Competing Interest | in tex | ✅ |
| Declaration of Generative AI | in tex (language editing + code assistance) | ✅ |
| Acknowledgements | Institute of Smart Cities, UPNA | ✅ no specific funding declared |

## Figures (submit as separate files, cited in text)

| # | File | Content |
|---|---|---|
| 1 | `figures/pipeline_b_architecture.png` | Architecture (also .pdf/.svg vector versions available) |
| 2 | `figures/fig_detection_grid.png` | Detector output on 4 real recorded frames |
| 3 | `figures/fig_bandwidth.png` | Semantic telemetry vs H.264/H.265 bitrates |
| 4 | `figures/fig_latency_hist.png` | Detection→Brain latency histogram (n=649) |
| 5 | `figures/fig_trajectory_check.png` | Twin vs ArduPilot reference trajectory (0.24 m max) |
| 6 | `figures/fig_real_vs_map.png` | Real frame + published positions vs PNOA GT (4.3 m P3) |

Regenerators: `make_paper_figures.py` (5, 6), `make_extra_figures.py` (2, 3, 4),
`generate_pipeline_b_architecture.py` (1).

## Supplementary material

- Video: `rea_flight_data/video_final.mp4` — 16.0 MB (limit 150 MB), the edited
  real-flight segment used in the replay (not the raw RR recording).
- Graphical abstract (optional, ≥531×1328 px): not prepared — decide if wanted.

## Declared scope (do not overstate)

- Evidence tier: replay of a recorded real flight over a localhost simulated link,
  desktop twin display. No HMD, no field radio, no human-subject results.
- HMD/VR capture, HITL with live pilot, degraded-RF field campaign, and operator
  study (RQ4) are declared future work.
- One flight, one scenario, one object class — stated in Limitations.

## Before pressing submit

- [ ] All authors confirm CRediT roles (proposal: Xabier — Conceptualization,
  Software, Writing–original draft; Daniel and Iker — Software, Validation,
  Data curation; Villadangos — Supervision, Writing–review, Project administration).
- [ ] Upload the 6 figure files individually in Editorial Manager.
- [ ] Attach `video_final.mp4` as supplementary video.
- [ ] Paste `vrih_highlights.txt` into the highlights field.
- [ ] Reference the 2026-07-01 scope encouragement in the cover letter.
