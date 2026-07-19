# SPAR3D Access Note

SPAR3D was selected as a first-wave fast open-source baseline because it reports
sub-second single-image 3D generation and is the point-aware successor in the
same Stability AI family as Stable Fast 3D.

Installation outcome:

- Python 3.10 / PyTorch 2.8 dev / CUDA 12.8: installation completed after
  pinning `flet==0.23.2` to satisfy `transparent-background==1.3.3`.

Benchmark attempt:

```text
D:\Deep-AeroTwin-UE57-Test\third_party\sota_3d_generators\_venvs\spar3d_py310\Scripts\python.exe
tools\sppa_sota_benchmark\run_spar3d_warm_batch.py
--objects-csv experiments\sppa_sota_benchmark\inputs\objects_rgba.csv
--output-dir experiments\sppa_sota_benchmark\outputs\spar3d_rgba_lowvram_6gb
--repo-dir third_party\sota_3d_generators\stable-point-aware-3d
--vram-limit-gb 6
--texture-resolution 1024
--remesh-option none
--low-vram-mode
```

Outcome:

- Model loading failed before inference with Hugging Face `GatedRepoError`.
- The account is not authorized for `stabilityai/stable-point-aware-3d`.

Interpretation:

SPAR3D is unresolved in this pass because model weights were inaccessible. It
should be rerun after access approval before inclusion in numeric tables.
