from __future__ import annotations

import argparse
import time
from contextlib import nullcontext
from pathlib import Path

import torch
from PIL import Image

from bench_common import ROOT, configure_torch_vram_cap, emit, gpu_snapshot, mesh_stats, read_objects, set_pythonpath_for, torch_peak


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Stable Fast 3D with one resident model load.")
    parser.add_argument("--objects-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo-dir", required=True)
    parser.add_argument("--vram-limit-gb", type=float, default=None)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--pretrained-model", default="stabilityai/stable-fast-3d")
    parser.add_argument("--texture-resolution", type=int, default=1024)
    parser.add_argument("--remesh-option", choices=["none", "triangle", "quad"], default="none")
    parser.add_argument("--target-vertex-count", type=int, default=-1)
    args = parser.parse_args()

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

    from sf3d.system import SF3D

    objects = read_objects(objects_csv)
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = configure_torch_vram_cap(args.vram_limit_gb)
    device = args.device if torch.cuda.is_available() else "cpu"

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    start = time.perf_counter()
    model = SF3D.from_pretrained(
        args.pretrained_model,
        config_name="config.yaml",
        weight_name="model.safetensors",
    )
    model.to(device)
    model.eval()
    load_sec = time.perf_counter() - start
    emit(
        "SPPA_BENCH_MODEL",
        {
            "model": "sf3d_warm",
            "status": "loaded",
            "load_sec": load_sec,
            "device": device,
            "texture_resolution": args.texture_resolution,
            "remesh_option": args.remesh_option,
            "target_vertex_count": args.target_vertex_count,
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
        image = Image.open(image_path).convert("RGBA")
        out = output_dir / label
        out.mkdir(parents=True, exist_ok=True)
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
        start_wall = time.perf_counter()
        try:
            with torch.no_grad():
                with (
                    torch.autocast(device_type=device, dtype=torch.bfloat16)
                    if "cuda" in device
                    else nullcontext()
                ):
                    mesh, _ = model.run_image(
                        [image],
                        bake_resolution=args.texture_resolution,
                        remesh=args.remesh_option,
                        vertex_count=args.target_vertex_count,
                    )
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            generation_sec = time.perf_counter() - start_wall
            mesh_path = out / f"{label}.glb"
            start = time.perf_counter()
            mesh.export(mesh_path, include_normals=True)
            export_sec = time.perf_counter() - start
            payload = {
                "model": "sf3d_warm",
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
        except Exception as exc:
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            payload = {
                "model": "sf3d_warm",
                "label": label,
                "prompt": item["prompt"],
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "wall_sec": time.perf_counter() - start_wall,
                "gpu_after": gpu_snapshot(),
                **torch_peak(),
            }
        emit("SPPA_BENCH_OBJECT", payload)


if __name__ == "__main__":
    main()
