# SPPA contribution selection record

Decision date: 2026-07-15

## Selected contribution

**Generic multiview primitive fitting (`SPPA-MVFit`).** The available checkout
contains a shared semantic primitive generator, agnostic image-space probes,
synthetic controls, and enough local CPU/GPU compute to build an independently
generated synthetic 3D benchmark. A bounded optimizer can therefore be
implemented and evaluated against explicit 3D ground truth without inventing
flight telemetry or human observations.

The contribution is ambitious only within a narrow contract: semantic family,
calibrated top/side masks, and lightweight primitive output. It is not universal
image-to-3D reconstruction.

## Rejected alternatives

### Representation-selection policy

Rejected as the central contribution. The repository has cost measurements but
does not have independently validated downstream utility weights, operator
preferences, or risk functions. A policy optimized against hand-chosen weights
would reproduce the circularity of the removed 6/6 task-fit ranking.

### Public semantic-telemetry-to-actor benchmark

Rejected as the central contribution for this submission. A release-ready local
benchmark can be produced, but it cannot honestly be called public until its
data, licenses, immutable archive/DOI, and clean-clone reproduction are hosted
outside this workstation. The four real images also lack metric 3D ground truth
and cannot support that benchmark.

## Evidence that must decide the paper

The preregistered H1 result, not visual attractiveness, determines whether the
new contribution survives. A failed H1 remains reportable and triggers claim
narrowing. The existing agnostic 72-case sweep and 240-case fuzz are engineering
regressions only because their synthetic patterns and expected cues were built
around the same heuristic; their 100% results are not reused as the primary
endpoint.

## Target implication

Advanced Engineering Informatics remains conditional. It is plausible only if
the final work demonstrates a general engineering knowledge-representation
mechanism and scalable measured behavior. If the evidence remains entirely
synthetic and spatial/visual, Journal of Geovisualization and Spatial Analysis
is the more defensible provisional target. The final choice requires a fresh
scope, policy, quartile, and agreement check after the evidence freeze.

