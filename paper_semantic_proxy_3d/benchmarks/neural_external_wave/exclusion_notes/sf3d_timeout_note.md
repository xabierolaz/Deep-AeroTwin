# Stable Fast 3D Timeout Note

Stable Fast 3D was selected as a first-wave fast open-source baseline because it
reports sub-second single-image mesh reconstruction and targets the same
image-to-3D operating point as TripoSR.

Installation outcome:

- Python 3.12 / PyTorch 2.10 / CUDA 12.9: install failed while compiling
  `gpytoolbox` and `texture_baker`.
- Python 3.10 / PyTorch 2.8 dev / CUDA 12.8: install completed successfully.

Benchmark attempt:

```text
D:\Deep-AeroTwin-UE57-Test\third_party\sota_3d_generators\_venvs\sf3d_py310\Scripts\python.exe
tools\sppa_sota_benchmark\run_sf3d_warm_batch.py
--objects-csv experiments\sppa_sota_benchmark\inputs\objects_rgba.csv
--output-dir experiments\sppa_sota_benchmark\outputs\sf3d_rgba_6gb
--repo-dir third_party\sota_3d_generators\stable-fast-3d
--vram-limit-gb 6
--texture-resolution 1024
--remesh-option none
--target-vertex-count -1
```

Outcome:

- The process emitted no `SPPA_BENCH_MODEL` event before the 20 minute timeout.
- Manual process termination was not performed, per the "do not kill processes"
  instruction.
- `processes_before.txt` in this run records the still-live SF3D benchmark PIDs
  observed before the formal SPPA/TripoSR/Hunyuan run.

Interpretation:

SF3D is unresolved in this pass, not a measured failure of output quality. It
must be rerun in a clean process state before inclusion in numeric tables.
