from __future__ import annotations

import argparse
import os
import sys
import time
from contextlib import nullcontext
from pathlib import Path

import torch
from huggingface_hub import snapshot_download

from bench_common import (
    ROOT,
    configure_torch_vram_cap,
    emit,
    gpu_snapshot,
    mesh_stats,
    read_objects,
    write_csv,
    torch_peak,
)


MODEL_KEY = "triposg_or_tripo_p1"


def resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TripoSG on a benchmark object CSV.")
    parser.add_argument("--objects-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo-dir", default="third_party/sota_3d_generators/TripoSG")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dtype", choices=["float16", "bfloat16", "float32"], default="float16")
    parser.add_argument("--num-inference-steps", type=int, default=20)
    parser.add_argument("--guidance-scale", type=float, default=7.0)
    parser.add_argument("--faces", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--vram-limit-gb", type=float, default=None)
    args = parser.parse_args()

    objects_csv = resolve(args.objects_csv)
    output_dir = resolve(args.output_dir)
    repo_dir = resolve(args.repo_dir)
    run_dir = output_dir.parent
    model_dir = repo_dir / "pretrained_weights" / "TripoSG"
    rmbg_dir = repo_dir / "pretrained_weights" / "RMBG-1.4"

    sys.path.insert(0, str(repo_dir))
    sys.path.insert(0, str(repo_dir / "scripts"))
    old_cwd = Path.cwd()
    os.chdir(repo_dir)
    try:
        from inference_triposg import BriaRMBG, TripoSGPipeline, run_triposg
    finally:
        os.chdir(old_cwd)

    objects = read_objects(objects_csv)
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = configure_torch_vram_cap(args.vram_limit_gb)
    device = args.device if torch.cuda.is_available() else "cpu"
    dtype = {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }[args.dtype]
    if device == "cpu":
        dtype = torch.float32

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    load_start = time.perf_counter()
    snapshot_download(repo_id="VAST-AI/TripoSG", local_dir=model_dir)
    snapshot_download(repo_id="briaai/RMBG-1.4", local_dir=rmbg_dir)
    rmbg_net = BriaRMBG.from_pretrained(str(rmbg_dir)).to(device)
    rmbg_net.eval()
    pipe = TripoSGPipeline.from_pretrained(str(model_dir)).to(device, dtype)
    load_sec = time.perf_counter() - load_start
    emit(
        "SPPA_BENCH_MODEL",
        {
            "model": MODEL_KEY,
            "status": "loaded",
            "load_sec": load_sec,
            "device": device,
            "dtype": args.dtype,
            "num_inference_steps": args.num_inference_steps,
            "guidance_scale": args.guidance_scale,
            "faces": args.faces,
            "gpu_after_load": gpu_snapshot(),
            **cap,
            **torch_peak(),
        },
    )

    rows = []
    for item in objects:
        label = item["label"]
        image_path = resolve(item["image"])
        out = output_dir / MODEL_KEY / label
        out.mkdir(parents=True, exist_ok=True)
        mesh_path = out / f"{label}.glb"
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
        start = time.perf_counter()
        try:
            with torch.no_grad():
                with (
                    torch.autocast(device_type=device, dtype=dtype)
                    if "cuda" in device and dtype in {torch.float16, torch.bfloat16}
                    else nullcontext()
                ):
                    mesh = run_triposg(
                        pipe,
                        str(image_path),
                        rmbg_net,
                        seed=args.seed,
                        num_inference_steps=args.num_inference_steps,
                        guidance_scale=args.guidance_scale,
                        faces=args.faces,
                    )
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            generation_sec = time.perf_counter() - start
            export_start = time.perf_counter()
            mesh.export(mesh_path)
            export_sec = time.perf_counter() - export_start
            row = {
                "model": MODEL_KEY,
                "label": label,
                "prompt": item.get("prompt", ""),
                "status": "ok",
                "generation_sec": generation_sec,
                "export_sec": export_sec,
                "wall_sec": generation_sec + export_sec,
                "gpu_after": gpu_snapshot(),
                **torch_peak(),
            }
            row.update(mesh_stats(mesh_path))
        except Exception as exc:
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            row = {
                "model": MODEL_KEY,
                "label": label,
                "prompt": item.get("prompt", ""),
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "wall_sec": time.perf_counter() - start,
                "gpu_after": gpu_snapshot(),
                **torch_peak(),
            }
        rows.append(row)
        emit("SPPA_BENCH_OBJECT", row)

    write_csv(run_dir / "objects.csv", rows)


if __name__ == "__main__":
    main()
