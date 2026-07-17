"""Wave-local Hunyuan3D-2mini-turbo warm batch runner (Amendment 05).

Same configuration as the 2026-07-01 qualitative run (5 steps, octree 380,
20k chunks, flashvdm, fixed generator seed 12345) with per-case try/except
and uncapped VRAM measurement by default.
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


def first_mesh(result):
    mesh = result[0]
    if isinstance(mesh, list):
        return mesh[0]
    return mesh


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Hunyuan3D shape generation warm, per-case crash tolerant.")
    parser.add_argument("--objects-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo-dir", required=True)
    parser.add_argument("--vram-limit-gb", type=float, default=None)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--model-path", default="tencent/Hunyuan3D-2mini")
    parser.add_argument("--subfolder", default="hunyuan3d-dit-v2-mini-turbo")
    parser.add_argument("--use-safetensors", action="store_true")
    parser.add_argument("--enable-flashvdm", action="store_true")
    parser.add_argument("--num-inference-steps", type=int, default=5)
    parser.add_argument("--octree-resolution", type=int, default=380)
    parser.add_argument("--num-chunks", type=int, default=20000)
    parser.add_argument("--guidance-scale", type=float, default=5.0)
    args = parser.parse_args()

    import torch
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
    set_pythonpath_for(repo_dir)

    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

    objects = read_objects(objects_csv)
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = configure_torch_vram_cap(args.vram_limit_gb)
    device = args.device if torch.cuda.is_available() else "cpu"

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    start = time.perf_counter()
    pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        args.model_path,
        subfolder=args.subfolder,
        use_safetensors=args.use_safetensors,
        device=device,
    )
    load_sec = time.perf_counter() - start

    flashvdm_status = "not_requested"
    if args.enable_flashvdm:
        try:
            pipeline.enable_flashvdm(topk_mode="merge")
            flashvdm_status = "enabled"
        except Exception as exc:
            flashvdm_status = f"failed:{type(exc).__name__}:{str(exc)[:180]}"

    emit(
        "SPPA_BENCH_MODEL",
        {
            "model": "hunyuan3d_2mini_turbo_shape",
            "status": "loaded",
            "load_sec": load_sec,
            "device": device,
            "model_path": args.model_path,
            "subfolder": args.subfolder,
            "use_safetensors": args.use_safetensors,
            "flashvdm": flashvdm_status,
            "num_inference_steps": args.num_inference_steps,
            "octree_resolution": args.octree_resolution,
            "num_chunks": args.num_chunks,
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
            image = Image.open(image_path).convert("RGBA")
            with torch.inference_mode():
                result = pipeline(
                    image=image,
                    num_inference_steps=args.num_inference_steps,
                    octree_resolution=args.octree_resolution,
                    num_chunks=args.num_chunks,
                    guidance_scale=args.guidance_scale,
                    generator=torch.manual_seed(12345),
                    output_type="trimesh",
                    enable_pbar=False,
                )
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            generation_sec = time.perf_counter() - start_wall
            mesh = first_mesh(result)
            if mesh is None:
                raise RuntimeError("pipeline returned no mesh")
            mesh_path = out / f"{label}.glb"
            start = time.perf_counter()
            mesh.export(mesh_path)
            export_sec = time.perf_counter() - start
            payload = {
                "model": "hunyuan3d_2mini_turbo_shape",
                "label": label,
                "prompt": item["prompt"],
                "status": "ok",
                "generation_sec": generation_sec,
                "export_sec": export_sec,
                "wall_sec": generation_sec + export_sec,
                "gpu_after": gpu_snapshot(),
                **torch_peak(),
            }
            payload.update(mesh_stats(mesh_path))
        except Exception as exc:  # reported, not fatal (Amendment 05 E5)
            payload = {
                "model": "hunyuan3d_2mini_turbo_shape",
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
