"""Wave-local TripoSG warm batch runner (Amendment 05, E12 flagship extension).

Reference operating point of the local TripoSG 1.5B rectified-flow model
(pretrained_weights/TripoSG, scripts/inference_triposg.py): fp16,
num_inference_steps=50, guidance_scale=7.0, fixed generator seed.

PARITY DECISION (documented in the E12 manifest): the triposr and hunyuan
wave runners feed the input PNG as-is (RGB / RGBA, no background removal;
the hy3dgen shape pipeline has no internal rembg either). The TripoSG
pipeline itself accepts any PIL image, so this runner also feeds the PNG
as-is (convert("RGB"), no RMBG-1.4, no bbox crop/pad). TripoSG's official
inference script would additionally run BriaRMBG + foreground crop + 10%
pad + white background; that difference is documented, not hidden.

Per-case try/except: a crash is reported, not fatal. No VRAM cap by default
(peak VRAM measured uncapped on the RTX 5090).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "supporting_artifacts" / "tools" / "sppa_sota_benchmark"))

from bench_common import ROOT, configure_torch_vram_cap, emit, gpu_snapshot, mesh_stats, read_objects, set_pythonpath_for, torch_peak  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark TripoSG warm, per-case crash tolerant.")
    parser.add_argument("--objects-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo-dir", required=True)
    parser.add_argument("--weights-dir", default=None, help="default: <repo-dir>/pretrained_weights/TripoSG")
    parser.add_argument("--vram-limit-gb", type=float, default=None)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--num-inference-steps", type=int, default=50)
    parser.add_argument("--guidance-scale", type=float, default=7.0)
    parser.add_argument("--seed", type=int, default=12345)
    args = parser.parse_args()

    import numpy as np
    import torch
    import trimesh
    from PIL import Image

    objects_csv = Path(args.objects_csv)
    if not objects_csv.is_absolute():
        objects_csv = ROOT / objects_csv
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    repo_dir = Path(args.repo_dir)
    if not repo_dir.is_absolute():
        repo_dir = ROOT / repo_dir
    weights_dir = Path(args.weights_dir) if args.weights_dir else repo_dir / "pretrained_weights" / "TripoSG"
    set_pythonpath_for(repo_dir)

    from triposg.pipelines.pipeline_triposg import TripoSGPipeline

    objects = read_objects(objects_csv)
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = configure_torch_vram_cap(args.vram_limit_gb)
    device = args.device if torch.cuda.is_available() else "cpu"

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    start = time.perf_counter()
    pipe = TripoSGPipeline.from_pretrained(str(weights_dir)).to(device, torch.float16)
    load_sec = time.perf_counter() - start
    emit(
        "SPPA_BENCH_MODEL",
        {
            "model": "triposg",
            "status": "loaded",
            "load_sec": load_sec,
            "device": device,
            "weights_dir": str(weights_dir),
            "dtype": "float16",
            "num_inference_steps": args.num_inference_steps,
            "guidance_scale": args.guidance_scale,
            "seed": args.seed,
            "preprocess": "as-is RGB PIL (no RMBG-1.4, no bbox crop; parity with triposr/hunyuan wave runners)",
            "gpu_after_load": gpu_snapshot(),
            **cap,
            **torch_peak(),
        },
    )

    for item in objects:
        label = item["label"]
        image_path = Path(item["image"])
        if not image_path.is_absolute():
            image_path = ROOT / image_path
        out = output_dir / label
        out.mkdir(parents=True, exist_ok=True)
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
        start_wall = time.perf_counter()
        try:
            image = Image.open(image_path).convert("RGB")
            start = time.perf_counter()
            generator = torch.Generator(device=device).manual_seed(args.seed)
            outputs = pipe(
                image=image,
                generator=generator,
                num_inference_steps=args.num_inference_steps,
                guidance_scale=args.guidance_scale,
            ).samples[0]
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            generation_sec = time.perf_counter() - start

            mesh = trimesh.Trimesh(outputs[0].astype(np.float32), np.ascontiguousarray(outputs[1]))
            mesh_path = out / f"{label}.glb"
            start = time.perf_counter()
            mesh.export(mesh_path)
            export_sec = time.perf_counter() - start
            wall_sec = time.perf_counter() - start_wall
            payload = {
                "model": "triposg",
                "label": label,
                "prompt": item["prompt"],
                "status": "ok",
                "generation_sec": generation_sec,
                "export_sec": export_sec,
                "wall_sec": wall_sec,
                "gpu_after": gpu_snapshot(),
                **torch_peak(),
            }
            payload.update(mesh_stats(mesh_path))
        except Exception as exc:  # reported, not fatal (Amendment 05 E5)
            payload = {
                "model": "triposg",
                "label": label,
                "prompt": item["prompt"],
                "status": "error",
                "error": f"{type(exc).__name__}: {str(exc)[:400]}",
                "wall_sec": time.perf_counter() - start_wall,
                **torch_peak(),
            }
        emit("SPPA_BENCH_OBJECT", payload)


if __name__ == "__main__":
    main()
