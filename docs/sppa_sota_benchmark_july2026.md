# SPPA Fast 3D Generator Stress Test, July 2026

This note records the first reproducible stress test of the current SPPA
primitive template prototype against fast open-source text-to-3D and
image-to-3D generators.
The purpose is not to claim visual superiority. The purpose is to test whether
neural generators are a practical substitute for telemetry-driven, low-polygon
runtime proxies inside a UAV/Unreal digital twin.

## Hardware Budget Rationale

The workstation used for this run has an NVIDIA GeForce RTX 5090 desktop GPU
with 32 GB VRAM. That is not the deployment target. NVIDIA's 2026 RTX 50-series
laptop table lists standard memory configurations of 24 GB, 16 GB, 12 GB, and
8 GB GDDR7 across the 5090/5080/5070 Ti/5070/5060/5050 laptop family. Epic's
UE5 recommended hardware page lists 8 GB or more graphics RAM for Unreal Engine.
Steam's May 2026 Hardware Survey reports VRAM shares of 8 GB: 25.89%, 12 GB:
12.77%, 16 GB: 24.05%, 24 GB: 5.22%, and 32 GB: 1.20%.

Therefore, a 6 GB PyTorch generation budget is a defensible portable-flight
stress profile: it leaves room for Unreal, the OS/display stack, video, telemetry
tools, and thermal/power headroom on a 16 GB high-end laptop GPU, while still
being feasible on 12 GB/24 GB configurations. This is not a physical GPU
partition. It is implemented with `torch.cuda.set_per_process_memory_fraction`,
which caps PyTorch's CUDA caching allocator to a fraction of visible device
memory.

Sources:

- NVIDIA RTX 50-series laptop memory configurations: https://www.nvidia.com/en-us/geforce/laptops/50-series/
- Epic UE5 hardware recommendations: https://dev.epicgames.com/documentation/unreal-engine/hardware-and-software-specifications-for-unreal-engine
- Steam Hardware Survey, May 2026: https://store.steampowered.com/hwsurvey/Steam-Hardware-Software-Survey-Welcome-to-Steam
- PyTorch CUDA memory fraction docs: https://docs.pytorch.org/docs/stable/generated/torch.cuda.memory.set_per_process_memory_fraction.html

## Run

Formal image/proxy run directory:

`experiments/sppa_sota_benchmark/runs/20260701_195624`

Formal text/tag run directory:

`experiments/sppa_sota_benchmark/runs/20260701_text3d_prompt_baselines`

Common object set:

- `cow`
- `biker`
- `tree`
- `car`
- `truck`
- `tractor`

Inputs:

- SPPA receives the semantic class label.
- Point-E and Shap-E receive the same text prompt/tag field.
- TripoSR and Hunyuan3D receive the RGBA proxy image derived from the same class
  set.
- RGB and RGBA inputs are stored in `experiments/sppa_sota_benchmark/inputs`.

Co-resident processes were not killed. The run directory records
`processes_before.txt`, `nvidia_processes_before.txt`, `processes_after.txt`,
and `nvidia_processes_after.txt`.

## Results

| Method | Input | Median wall time | Range | Median triangles | Range | Peak reserved VRAM |
|---|---|---:|---:|---:|---:|---:|
| SPPA current template | class label | 0.0016 s | 0.0013-0.0038 s | 930 | 488-1,668 | 0 MB |
| Shap-E text, k=16 | text prompt/tag | 2.0080 s | 1.3034-2.3294 s | 70,104 | 17,884-131,668 | 6,120 MB |
| Point-E text + SDF32 | text prompt/tag | 6.4266 s | 6.3121-6.9235 s | 2,807 | 1,026-5,454 | 3,644 MB |
| TripoSR warm, r128 | RGBA proxy image | 0.4604 s | 0.3720-1.3492 s | 21,126 | 19,284-31,012 | 2,028 MB |
| Hunyuan3D-2mini Turbo | RGBA proxy image | 1.5042 s | 1.1873-2.0183 s | 823,392 | 332,020-1,698,032 | 6,092 MB max |

Important caveats:

- TripoSR used a local PyMCubes CPU fallback because `torchmcubes` failed to
  compile on Windows with Python 3.12, PyTorch 2.10, CUDA 12.9, and MSVC. This
  makes TripoSR integration less clean in the current stack and may affect
  extraction timing.
- Point-E used the `base40M-textvec` text model, 4,096 generated points, and
  SDF meshing at grid size 32. The measured time includes point-cloud generation
  plus SDF mesh conversion, because Unreal needs a mesh-like artifact rather
  than only a point cloud.
- Shap-E used `text300M`, batch size 1, fp16, and `karras_steps=16`. This is a
  speed-oriented setting rather than the official notebook's higher-step
  example, so the visual quality should be treated as a fast baseline, not as
  Shap-E's best possible quality.
- Hunyuan3D's local API advertises text input, but the inspected code path first
  runs text-to-image and then shape generation. That route should be reported
  separately as text-to-image-to-3D if benchmarked; it is not a direct tag-only
  text-to-mesh baseline in this pass.
- TripoSR was run at marching-cubes resolution 128 to keep the portable
  real-time profile. Its default 256 setting should be benchmarked separately
  for visual quality.
- Hunyuan3D-2mini Turbo used 5 inference steps, `octree_resolution=380`,
  `num_chunks=20000`, and FlashVDM enabled.
- The inputs are synthetic/proxy images, not degraded real UAV crops. Real UAV
  imagery, motion blur, partial occlusion, compression, and top-down ambiguity
  remain pending.
- SF3D compiled successfully only under Python 3.10/Torch 2.8 CUDA 12.8. Its
  warm benchmark did not emit a model-load event within 20 minutes and was
  treated as timed out for this pass. No manual process kill was performed.
- SPAR3D installed under Python 3.10/Torch 2.8 CUDA 12.8 after pinning
  `flet==0.23.2`, but model loading failed with Hugging Face `GatedRepoError`
  because the account is not authorized for `stabilityai/stable-point-aware-3d`.

## View Artifacts

The runs now include orthographic inspection views for each generated mesh:

`experiments/sppa_sota_benchmark/runs/20260701_195624/views`

`experiments/sppa_sota_benchmark/runs/20260701_text3d_prompt_baselines/views`

For each successful model/object pair, the renderer exports `front`, `side`,
`top`, and `iso` PNGs plus one contact sheet per object in
`views/contact_sheets`. These views are for qualitative inspection only. They do
not alter or simplify the generated mesh files. For very dense meshes, the view
renderer samples at most 80,000 faces for display speed and records both the
true face count and the rendered face count in `views/rendered_views.csv`.

This matters for the paper because UAV relevance is not only "how detailed is
the asset?" but also "does the object preserve a useful footprint, frontal/lateral
extent, and top-down occupancy when viewed from changing flight angles?"

## Temporal Update Policy

SPPA should not be framed as regenerating complete geometry at every video
frame. The deployable policy is track-persistent:

- Create or instantiate one proxy when a stable detection track appears.
- Update pose, scale, velocity, and uncertainty every telemetry/detection tick.
- Regenerate or swap geometry only when class, archetype, dimensions, or
  confidence state crosses a meaningful threshold.
- For static objects, most frames should be transform updates, not geometry
  generation.
- For moving but rigid objects, geometry can remain resident while pose and
  yaw are updated.
- For articulated or shape-changing objects, SPPA needs either parametric parts
  or an explicit `shape_update` event; this is pending validation.

This is a key distinction from image-to-3D generators. As the UAV viewpoint
changes, a neural generator would need either new crops and repeated generation
or a separate tracking/fusion system. SPPA instead treats changing viewpoint as
a camera/pose problem once the semantic proxy is instantiated.

## Interpretation

The result does not show that SPPA is a better 3D generator. It shows that SPPA
occupies a different operating point:

- It can create class-readable obstacle proxies in milliseconds without GPU
  inference.
- It produces bounded, low-polygon meshes suitable for instancing or primitive
  descriptors.
- It does not solve visual fidelity, texture realism, or arbitrary object
  reconstruction.
- Neural generators are already fast enough to be relevant. Shap-E, under a
  speed-oriented 16-step setting, generated text-conditioned meshes in about two
  seconds, but with much heavier and sometimes fragmented geometry. Point-E was
  lighter geometrically but slower than Shap-E after SDF meshing.
- The fair question is not "text-to-3D or image-to-3D versus SPPA" in the
  abstract. It is whether a flight system should regenerate an asset from a tag
  or crop, or instantiate a persistent semantic proxy and update pose/scale/
  uncertainty from the track.

The strongest honest paper claim is therefore:

> For telemetry-driven UAV digital twins, SPPA is not a replacement for
> image-to-3D asset generation; it is a constrained runtime representation for
> cases where the system needs cheap, predictable, class-conditioned obstacle
> volumes under limited VR/Unreal GPU budget.
