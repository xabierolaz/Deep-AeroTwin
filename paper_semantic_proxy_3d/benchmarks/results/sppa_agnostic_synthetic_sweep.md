# SPPA Agnostic Synthetic Sweep

Deterministic synthetic sweep for agnostic image-space primitive cues. The fitter receives pixels, bbox, and unlabeled masks only. The sweep measures synthetic primitive behavior, not real detector quality.

- Status: pass
- Cases: 72
- Passes: 72
- Failures: 0
- Primary-scope accuracy: 1.0000
- Strong round-pair precision/recall/F1: 1.0000 / 1.0000 / 1.0000
- Line-structure precision/recall/F1: 1.0000 / 1.0000 / 1.0000
- Figure: `D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d\figures\sppa_agnostic_synthetic_sweep_examples.png`

| Family | Cases | Passes | Failures |
|---|---:|---:|---:|
| blank_negative | 12 | 12 | 0 |
| elongated_round_pair | 12 | 12 | 0 |
| line_structure | 12 | 12 | 0 |
| round_pair | 12 | 12 | 0 |
| single_circle_negative | 12 | 12 | 0 |
| texture_negative | 12 | 12 | 0 |

## Boundary

This sweep evaluates geometry-cue behavior on deterministic synthetic images. It is stronger than hand-picked examples, but it is not a real detector benchmark and does not prove real-world universal part recovery.
