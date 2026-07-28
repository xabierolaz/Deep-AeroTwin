from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import torch

from bench_common import ROOT, emit, gpu_snapshot, mesh_stats, read_objects, write_csv, torch_peak


MODEL_KEY = "direct3d_s2"


def resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Direct3D-S2 on a benchmark object CSV.")
    parser.add_argument("--objects-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo-dir", default="third_party/sota_3d_generators/Direct3D-S2")
    parser.add_argument("--pretrained-model", default="wushuang98/Direct3D-S2")
    parser.add_argument("--subfolder", default="direct3d-s2-v-1-1")
    parser.add_argument("--sdf-resolution", type=int, default=512)
    parser.add_argument("--remove-interior", action="store_true", default=True)
    parser.add_argument("--remesh", action="store_true")
    args = parser.parse_args()

    objects_csv = resolve(args.objects_csv)
    output_dir = resolve(args.output_dir)
    repo_dir = resolve(args.repo_dir)
    run_dir = output_dir.parent
    sys.path.insert(0, str(repo_dir))

    from direct3d_s2.pipeline import Direct3DS2Pipeline

    objects = read_objects(objects_csv)
    output_dir.mkdir(parents=True, exist_ok=True)
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    start = time.perf_counter()
    pipeline = Direct3DS2Pipeline.from_pretrained(args.pretrained_model, subfolder=args.subfolder)
    pipeline.to("cuda:0" if torch.cuda.is_available() else "cpu")
    load_sec = time.perf_counter() - start
    emit(
        "SPPA_BENCH_MODEL",
        {
            "model": MODEL_KEY,
            "status": "loaded",
            "load_sec": load_sec,
            "device": "cuda:0" if torch.cuda.is_available() else "cpu",
            "sdf_resolution": args.sdf_resolution,
            "subfolder": args.subfolder,
            "gpu_after_load": gpu_snapshot(),
            **torch_peak(),
        },
    )

    rows = []
    for item in objects:
        label = item["label"]
        image_path = resolve(item["image"])
        out = output_dir / MODEL_KEY / label
        out.mkdir(parents=True, exist_ok=True)
        mesh_path = out / f"{label}.obj"
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
        start = time.perf_counter()
        try:
            result = pipeline(
                str(image_path),
                sdf_resolution=args.sdf_resolution,
                remove_interior=args.remove_interior,
                remesh=args.remesh,
            )
            mesh = result["mesh"]
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
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    main()
