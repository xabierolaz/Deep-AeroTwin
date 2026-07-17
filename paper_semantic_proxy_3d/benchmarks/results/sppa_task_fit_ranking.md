# SPPA Runtime Task-Fit Ranking

This is a local systems ranking for the SPPA UAV/VR runtime contract. It is not an image-to-3D SOTA ranking.

Pass criteria:

- latency: median wall time <= 33 ms;
- triangles: maximum mesh size <= 5,000 triangles;
- memory: maximum torch reserved memory <= 1 GB;
- no GPU: no runtime neural GPU inference;
- contract: deterministic SPPA descriptor/update contract;
- update: track-updateable actor semantics.

| Rank | Method | Score | Input | Median wall | Max tris | Max VRAM | Notes |
|---:|---|---:|---|---:|---:|---:|---|
| 1 | SPPA | 6/6 | normalized tag / gated observation | 0.0031s | 1904 | 0MB | Runtime semantic proxy with deterministic descriptor and observation gating. |
| 2 | TripoSR warm | 0/6 | clean RGBA proxy crop | 0.4604s | 31012 | 2028MB | Fast image-conditioned mesh generator. |
| 3 | Hunyuan3D-2mini Turbo | 0/6 | clean RGBA proxy crop | 1.5042s | 1698032 | 6092MB | High-density image-conditioned mesh generator. |
| 4 | Shap-E text K=16 | 0/6 | prompt/tag | 2.0080s | 131668 | 6120MB | Legacy text-conditioned mesh generator in speed-oriented settings. |
| 5 | Point-E text + SDF32 | 0/6 | prompt/tag | 6.4266s | 5454 | 3644MB | Legacy point-cloud generator with SDF mesh conversion. |
