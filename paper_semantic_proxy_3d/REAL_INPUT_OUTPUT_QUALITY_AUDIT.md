# Real-Input Output Quality Audit

Generated during the SPPA submission audit on 2026-07-03.

## Scope

This is a qualitative failure audit for the four real-input probes:

- biker;
- tower;
- tractor;
- tractor_trailer.

It is not a SOTA metric table. It records visible failure modes that must become measurable before any quality ranking is claimed.

## Current Observations

| Case | Detector input | SPPA | TripoSR | Hunyuan3D-2mini |
|---|---|---|---|---|
| biker | No valid biker/bicycle target hit; COCO labels person only | Keeps reviewed `biker` tag but is template-like | Organic blob, not a readable bicycle/rider | Flat/plate-like mesh |
| tower | No valid tower target hit | Keeps reviewed `tower` tag but simplified | Terrain-like blob, not tower structure | Flat/plate-like mesh |
| tractor | No valid tractor target hit; COCO low-conf `train` false positives in ROI | Keeps tractor archetype, readable as tractor | Organic mound, not tractor structure | Tall transparent/plate-like block, badly oriented |
| tractor_trailer | No valid tractor/trailer target hit; COCO false positives such as toothbrush/bed | Keeps tractor archetype but loses trailer because input tag is only `tractor` | Mushroom/blob-like geometry, not tractor+trailer | Tall transparent/plate-like block, badly oriented |

## Consequence For Ranking

A real SOTA ranking cannot use the current visual grid as the metric surface. The figure is useful because it reveals failures, but the ranking needs explicit criteria:

- detector target hit or documented detector failure;
- class/readability score;
- part-presence score, for example wheels, tower mast, trailer tank;
- orientation/scale sanity;
- mesh artifact penalty for plate-like, blob-like, or transparent output;
- runtime and memory reported separately from quality.

## Immediate Policy

Keep SPPA in the paper as a semantic-runtime proxy baseline.

Keep TripoSR and Hunyuan3D outputs as stress-test evidence, not as final SOTA rows, until the input crops and quality metrics are fixed.

For tractor_trailer, do not claim SPPA handles the trailer from the current input; the reviewed semantic tag is only `tractor`, so the missing trailer is an input-contract limitation, not a mesh-renderer bug.
