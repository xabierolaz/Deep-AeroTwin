# SPPA fast 3D generator shortlist, July 2026

Purpose: identify local/open candidates that can realistically challenge SPPA
under a portable UAV/digital-twin constraint. The target class is not "best
visual quality"; it is fast generation, preferably within roughly 3 seconds on
consumer or portable GPU hardware.

## Downloaded for first benchmark wave

Repositories were cloned under:

`third_party/sota_3d_generators/`

This folder is git-ignored because model checkpoints and nested repositories can
be large.

| Candidate | Input | Output | Why included | Main caveat |
|---|---|---|---|---|
| Point-E | Text prompt | Point cloud, optional SDF mesh | Direct text/tag baseline; useful when the only input is a YOLO-style label. | Point cloud alone is not an Unreal mesh; SDF meshing adds time and quality is intentionally low. |
| Shap-E | Text prompt or image | Implicit function / mesh export | Direct text/tag baseline that can run in seconds with low-step sampling. | Fast settings can fragment geometry and produce high triangle counts; not a telemetry-aware runtime representation. |
| TripoSR | Single image | Mesh/OBJ, vertex color or baked texture | Canonical fast open baseline; reports under 0.5 s on A100, MIT license, about 6 GB VRAM for a single image in README. | Requires a usable image crop; older visual quality than newer methods. |
| Stable Fast 3D | Single image | GLB mesh, UV texture/material parameters | TripoSR successor optimized for usable mesh and game-style assets; README reports about 6 GB VRAM. | Image-only; license/access must be checked before publication artifacts. |
| SPAR3D | Single image | GLB mesh with point-cloud-conditioned backside completion | Fast successor to SF3D; paper/model card report under 1 s / 0.7 s and better hidden-side completion. | Default VRAM is heavier; README says 10.5 GB default or roughly 7 GB low-VRAM, slower. |
| Hunyuan3D-2 / 2mini-Turbo | Image, plus local API text route | Shape mesh, optional texture pipeline | Strong fast image-to-3D challenger with mini/turbo shape models and 6 GB shape-generation VRAM in README. | Inspected text route is text-to-image-to-3D, so it must be reported separately from direct tag-to-mesh baselines. Texture path is not portable enough for the SPPA claim. |

## Not first-wave candidates

| Candidate | Reason |
|---|---|
| TRELLIS / TRELLIS.2 | High-quality but too heavy for the portable constraint: official requirements are 16-24 GB+ VRAM and Linux-focused setups. Not a fair first-wave sub-3-second laptop baseline. |
| SAM 3D Objects / Fast-SAM3D | Very relevant to real images, but official setup asks for 32 GB VRAM and Fast-SAM3D still reports object times far above the 3-second target. |
| InstantMesh / OpenLRM / LGM | Useful literature baselines, but reported runtimes are commonly 5-10 seconds or more, outside the first-wave target. |
| DiffSplat | Fast text/image-to-3D Gaussian splats in 1-2 s and MIT licensed, but output is 3DGS rather than a mesh actor. Keep as a reserve if the benchmark includes non-mesh 3D representations. |

## Benchmark policy

SPPA should not be compared only on clean object crops. The benchmark must split
the evidence conditions:

1. No usable image: class label, bounding box, track, footprint/scale estimate.
2. Poor UAV crop: small, blurred, occluded, compressed, top-down or oblique.
3. Clean crop: centered, high-resolution, object-dominant image.
4. Dense scene: many simultaneous detections.

Expected honest outcome:

- Neural generators should win on visual fidelity when a clean crop exists.
- Text-to-3D generators are the fair baseline when only a YOLO tag is available,
  but they still create a fresh asset rather than a persistent track proxy.
- SPPA only wins if it shows lower bounded cost, explicit metric scale/yaw,
  stable per-frame updates, uncertainty/fallback behavior, and better behavior
  when the image evidence is weak or absent.

## Sources checked

- TripoSR: https://github.com/VAST-AI-Research/TripoSR
- Point-E: https://github.com/openai/point-e
- Shap-E: https://github.com/openai/shap-e
- Stable Fast 3D: https://github.com/Stability-AI/stable-fast-3d
- SPAR3D: https://github.com/Stability-AI/stable-point-aware-3d
- Hunyuan3D-2: https://github.com/Tencent-Hunyuan/Hunyuan3D-2
- DiffSplat reserve: https://github.com/chenguolin/DiffSplat
- TRELLIS heavy exclusion: https://github.com/microsoft/TRELLIS and https://github.com/microsoft/TRELLIS.2
- SAM 3D heavy exclusion: https://github.com/facebookresearch/sam-3d-objects
