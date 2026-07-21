# Real flight photos — SPPA vs neural generators (2026-07-21)

Scope: two user-supplied real flight photos (`rea_flight_data/real_photos/tower.png`,
`tractor.png`, 640×480, aerial oblique views). SPPA ran the full detector
pipeline (YOLOE-26s → mask → geo-projection → gate → runtime builder).
Neural baselines received their best input (centered RGB crop of the object,
`experiments/sppa_sota_benchmark/inputs/*_real_flight*_512.png`), on the same
RTX 5090 under the 6 GB torch-allocator stress cap used by the July waves.

**No 3D ground truth exists for these photos, so no voxel IoU is reported;
fidelity is qualitative only.** Measured IoU comparisons live in the sealed
synthetic wave (`benchmarks/results/sppa_neural_flagship_wave.json`).

## Tower (YOLOE `electric pylon` 0.49, 38-pt mask)

| Method | Input | Triangles | Time | Peak VRAM | Qualitative fidelity |
|---|---|---|---|---|---|
| SPPA proxy (runtime builder) | detector mask + tag | 396 | 0.15–0.25 ms compile (9.4 ms median MVFit fit path, sealed) | 0 MB (CPU) | tapered lattice pylon with crossarms, recognizable |
| SPPA, tag-only (archetype priors) | label only | 396 | 0.25 ms | 0 MB (CPU) | same topology, prior dims (6.0 m height) |
| SPPA, bbox+tag (clamped) | detector bbox + tag | 396 | 0.19 ms | 0 MB (CPU) | same topology, 40.5×18.6×28.0 m pre-gate dims |
| TripoSR warm, r128, 6 GB | RGB crop | 26,836 | 0.49 s inference (1.22 s wall) | 1,868 MB | amorphous blob, no tower structure |
| Hunyuan3D-2mini-turbo, 6 GB | RGB crop | — (hard failure) | 1.3–2.5 s to failure | 4,552 MB | `No surface found` at 5 and 20 steps; aerial view out of distribution (control on 2026-07-03 ground-level photo: 592,504 tris, 2.14 s, 4,579 MB — works) |

Gate story: raw mask footprint 39.9×17.5 m → clamped by the vertical-structure
aspect prior to 5.60×5.60×28.00 m.

## Tractor (YOLOE `two-wheeled vehicle` 0.48 — wrong token → conservative `generic_vehicle`)

| Method | Input | Triangles | Time | Peak VRAM | Qualitative fidelity |
|---|---|---|---|---|---|
| SPPA proxy (runtime builder) | detector mask + tag | 576 | 0.19 ms compile | 0 MB (CPU) | green tractor: hood, cab, roof, 4 wheels, recognizable |
| SPPA, tag-only (archetype priors) | label only | 576 | 0.22 ms | 0 MB (CPU) | same topology, prior dims |
| SPPA, bbox+tag (clamped) | detector bbox + tag | 576 | 0.24 ms | 0 MB (CPU) | same topology, 6.7×5.6×2.6 m pre-gate dims |
| TripoSR warm, r128, 6 GB | RGB crop | 39,700 | 0.09 s inference (0.47 s wall) | 1,870 MB | amorphous blob, no tractor structure |
| Hunyuan3D-2mini-turbo, 6 GB | RGB crop | — (hard failure) | ~1.3 s to failure | 4,552 MB | `No surface found` |

Gate story: raw footprint 7.1×6.0 m → fused to 4.75×2.50×2.60 m by the
vehicle aspect prior.

## Input-mode note (imagen+silueta+tag vs tag+silueta)

SPPA ran all three modes per case (tag-only priors, bbox+tag, mask+tag):
identical compile cost and topology — only the metric dims change (priors →
bbox-clamped → mask-fused). The neural generators accept only the image path;
there is no tag/silhouette mode for them (that is the input-modality
mismatch documented in the paper).

## Verdict (bounded)

On these two aerial photos: SPPA is faster (ms CPU vs seconds GPU), two to
three orders of magnitude cheaper in payload (396–576 tris vs 27k–40k for
TripoSR, none for Hunyuan), uses zero VRAM, and is the only one producing a
recognizable object — Hunyuan3D-2mini fails hard on the aerial view and
TripoSR returns amorphous blobs. The neural failure is view-dependent, not
universal (ground-level 2026-07-03 probes work), and no IoU is claimed
without 3D ground truth.
