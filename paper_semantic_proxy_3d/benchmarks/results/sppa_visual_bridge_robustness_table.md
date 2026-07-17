# SPPA Visual Bridge Robustness Battery

This table summarizes the agnostic visual-primitive bridge robustness battery. It supports anti-shortcut and regression claims for the frozen probes and synthetic controls; it does not claim universal real-world primitive correctness or visual image-to-3D SOTA.

- Status: passed
- Failures: none

| Check | Scope | Cases/variants | Metric | Status | Warnings | Limit |
|---|---|---:|---|---|---:|---|
| Cue extraction | real crops | 4 | 4 frozen real probes | passed | 0 | Checks descriptor/export consistency, not primitive correctness. |
| Label invariance | real crops | 4 | geometry hash unchanged | passed | 0 | Guards label/tag shortcuts only. |
| Identity invariance | real crops | 4 | geometry hash unchanged | passed | 0 | Guards case-name hardcoding only. |
| Path invariance | real crops | 4 | geometry hash unchanged | passed | 0 | Guards filename/path shortcuts only. |
| Detector representation | real crops | 12 | mask order/duplicates unchanged | passed | 0 | Guards representation-only side channels. |
| Combined side channels | real crops | 4 | geometry hash unchanged | passed | 0 | Does not prove primitive correctness. |
| Mirror equivariance | real crops | 4 | primary stable, 17 secondary warnings | passed | 17 | Secondary line/weak-pair drift remains recorded. |
| Photometric stability | real crops | 16 | primary stable, 15 secondary warnings | passed | 15 | Deterministic perturbations only, not real illumination coverage. |
| Synthetic controls | synthetic | 5 | all controls passed | passed | 0 | Known geometry controls, not detector quality. |
| Synthetic sweep | synthetic | 72 | acc=1.000, round F1=1.000, line F1=1.000 | passed | 0 | Synthetic primitive behavior only. |
| Synthetic fuzz | synthetic | 240 | 4 seeds, acc=1.000, round/line F1=1.000/1.000 | passed | 0 | Randomized synthetic cues, not real UAV rates. |
