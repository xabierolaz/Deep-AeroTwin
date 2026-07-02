# Semantic Primitive Proxy Paper

This folder is the standalone SPPA paper. Its contribution is not the UAV
telemetry/VR pipeline itself; the contribution is the semantic-to-3D proxy
layer that converts YOLO/track/telemetry object evidence into lightweight
parametric 3D actors.

Scope:

- Keep SPPA separate from the Pipeline B/VRIH telemetry paper.
- Treat Unreal and YOLO telemetry as shared platform infrastructure.
- Claim only what the SPPA paper measures: local deterministic proxy creation,
  descriptor updates, packaged synthetic rendering cost, and comparison against
  lightweight/open 3D generation baselines where evidence exists.
- Keep live flight, VR user study, and full operational safety claims out of
  this paper unless new evidence is added.

Official files:

- `semantic_proxy_3d_paper.tex`
- `semantic_proxy_3d_references.bib`
- `semantic_proxy_3d_paper.bbl`
- `semantic_proxy_3d_paper.pdf`
- `figures/`

Related evidence lives in:

- `docs/sppa_*.md`
- `experiments/sppa_*`
- `tools/sppa_sota_benchmark/`
- `Unreal/Plugins/PorceTelemetry/`
