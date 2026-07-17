# SPPA Agnostic Synthetic Fuzz

Reproducible multi-seed synthetic fuzz for agnostic image-space primitive cues. The fitter receives pixels, bbox, and unlabeled masks only. This tests randomized synthetic primitive behavior, not real detector quality.

- Status: pass
- Seeds: 20260705, 20260706, 20260707, 20260708
- Cases: 240
- Passes: 240
- Failures: 0
- Primary-scope accuracy: 1.0000
- Strong round-pair precision/recall/F1: 1.0000 / 1.0000 / 1.0000
- Line-structure precision/recall/F1: 1.0000 / 1.0000 / 1.0000
- Figure: `D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d\figures\sppa_agnostic_synthetic_fuzz_examples.png`

| Family | Cases | Passes | Failures |
|---|---:|---:|---:|
| blank_negative | 40 | 40 | 0 |
| elongated_round_pair | 40 | 40 | 0 |
| line_structure | 40 | 40 | 0 |
| round_pair | 40 | 40 | 0 |
| single_circle_negative | 40 | 40 | 0 |
| texture_negative | 40 | 40 | 0 |

| Seed | Cases | Passes | Failures |
|---|---:|---:|---:|
| 20260705 | 60 | 60 | 0 |
| 20260706 | 60 | 60 | 0 |
| 20260707 | 60 | 60 | 0 |
| 20260708 | 60 | 60 | 0 |

## Boundary

This is a reproducible randomized synthetic fuzz test over generic primitive cues. It is intentionally stronger than a hand-picked visual audit, but it remains synthetic and does not prove real UAV detector performance or universal 3D reconstruction.
