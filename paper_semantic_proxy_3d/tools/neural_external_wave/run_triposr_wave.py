"""Wave-local TripoSR warm batch runner (Amendment 05).

Differs from the 2026-07-01 qualitative runner only in robustness and honesty
of measurement: per-case try/except (a crash is reported, not fatal) and no
VRAM cap by default (peak VRAM is measured uncapped on the RTX 5090).
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
    parser = argparse.ArgumentParser(description="Benchmark TripoSR warm, per-case crash tolerant.")
    parser.add_argument("--objects-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo-dir", required=True)
    parser.add_argument("--vram-limit-gb", type=float, default=None)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--pretrained-model-name-or-path", default="stabilityai/TripoSR")
    parser.add_argument("--chunk-size", type=int, default=4096)
    parser.add_argument("--mc-resolution", type=int, default=128)
    parser.add_argument("--model-save-format", choices=["obj", "glb"], default="obj")
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

    from tsr.system import TSR

    objects = read_objects(objects_csv)
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = configure_torch_vram_cap(args.vram_limit_gb)
    device = args.device if torch.cuda.is_available() else "cpu"

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    start = time.perf_counter()
    model = TSR.from_pretrained(
        args.pretrained_model_name_or_path,
        config_name="config.yaml",
        weight_name="model.ckpt",
    )
    model.renderer.set_chunk_size(args.chunk_size)
    model.to(device)
    load_sec = time.perf_counter() - start
    emit(
        "SPPA_BENCH_MODEL",
        {
            "model": "triposr_warm",
            "status": "loaded",
            "load_sec": load_sec,
            "device": device,
            "mc_resolution": args.mc_resolution,
            "chunk_size": args.chunk_size,
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
            with torch.no_grad():
                scene_codes = model([image], device=device)
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            inference_sec = time.perf_counter() - start

            start = time.perf_counter()
            meshes = model.extract_mesh(scene_codes, True, resolution=args.mc_resolution)
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            extract_sec = time.perf_counter() - start

            mesh_path = out / f"{label}.{args.model_save_format}"
            start = time.perf_counter()
            meshes[0].export(mesh_path)
            export_sec = time.perf_counter() - start
            wall_sec = time.perf_counter() - start_wall
            payload = {
                "model": "triposr_warm",
                "label": label,
                "prompt": item["prompt"],
                "status": "ok",
                "inference_sec": inference_sec,
                "extract_sec": extract_sec,
                "export_sec": export_sec,
                "wall_sec": wall_sec,
                "gpu_after": gpu_snapshot(),
                **torch_peak(),
            }
            payload.update(mesh_stats(mesh_path))
        except Exception as exc:  # reported, not fatal (Amendment 05 E5)
            payload = {
                "model": "triposr_warm",
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
