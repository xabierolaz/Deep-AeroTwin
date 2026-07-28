from __future__ import annotations

import argparse
import time
from pathlib import Path

import torch
from PIL import Image

from bench_common import ROOT, configure_torch_vram_cap, emit, gpu_snapshot, read_objects, rel, torch_peak


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Point-E image-to-3D with one resident model load.")
    parser.add_argument("--objects-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--vram-limit-gb", type=float, default=None)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--base-name", default="base40M")
    parser.add_argument("--base-points", type=int, default=1024)
    parser.add_argument("--total-points", type=int, default=4096)
    parser.add_argument("--guidance-scale", type=float, default=3.0)
    parser.add_argument("--mesh", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--sdf-grid-size", type=int, default=32)
    parser.add_argument("--sdf-batch-size", type=int, default=4096)
    args = parser.parse_args()

    objects_csv = Path(args.objects_csv)
    if not objects_csv.is_absolute():
        objects_csv = ROOT / objects_csv
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    from point_e.diffusion.configs import DIFFUSION_CONFIGS, diffusion_from_config
    from point_e.diffusion.sampler import PointCloudSampler
    from point_e.models.configs import MODEL_CONFIGS, model_from_config
    from point_e.models.download import load_checkpoint
    from point_e.util.pc_to_mesh import marching_cubes_mesh

    objects = read_objects(objects_csv)
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = configure_torch_vram_cap(args.vram_limit_gb)
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    start = time.perf_counter()
    base_model = model_from_config(MODEL_CONFIGS[args.base_name], device)
    base_model.load_state_dict(load_checkpoint(args.base_name, device))
    base_model.eval()
    upsampler_model = model_from_config(MODEL_CONFIGS["upsample"], device)
    upsampler_model.load_state_dict(load_checkpoint("upsample", device))
    upsampler_model.eval()
    base_diffusion = diffusion_from_config(DIFFUSION_CONFIGS[args.base_name])
    upsampler_diffusion = diffusion_from_config(DIFFUSION_CONFIGS["upsample"])

    sdf_model = None
    if args.mesh:
        sdf_model = model_from_config(MODEL_CONFIGS["sdf"], device)
        sdf_model.load_state_dict(load_checkpoint("sdf", device))
        sdf_model.eval()

    sampler = PointCloudSampler(
        device=device,
        models=[base_model, upsampler_model],
        diffusions=[base_diffusion, upsampler_diffusion],
        num_points=[args.base_points, args.total_points - args.base_points],
        aux_channels=["R", "G", "B"],
        guidance_scale=[args.guidance_scale, args.guidance_scale],
    )
    load_sec = time.perf_counter() - start
    emit(
        "SPPA_BENCH_MODEL",
        {
            "model": "point_e_image_sdf32" if args.mesh else "point_e_image_pointcloud",
            "status": "loaded",
            "load_sec": load_sec,
            "device": str(device),
            "input_mode": "image",
            "base_name": args.base_name,
            "base_points": args.base_points,
            "total_points": args.total_points,
            "mesh_enabled": args.mesh,
            "sdf_grid_size": args.sdf_grid_size if args.mesh else None,
            "sdf_batch_size": args.sdf_batch_size if args.mesh else None,
            "guidance_scale": args.guidance_scale,
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
            samples = None
            with torch.inference_mode():
                for x in sampler.sample_batch_progressive(
                    batch_size=1,
                    model_kwargs={"images": [image]},
                ):
                    samples = x
            if samples is None:
                raise RuntimeError("Point-E sampler returned no samples")
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            pointcloud_sec = time.perf_counter() - start

            pointcloud = sampler.output_to_point_clouds(samples)[0]
            pc_ply_path = out / f"{label}_points.ply"
            start = time.perf_counter()
            with pc_ply_path.open("wb") as f:
                pointcloud.write_ply(f)
            point_export_sec = time.perf_counter() - start

            payload = {
                "model": "point_e_image_sdf32" if args.mesh else "point_e_image_pointcloud",
                "label": label,
                "prompt": item.get("prompt") or label,
                "status": "ok",
                "input_mode": "image",
                "pointcloud_sec": pointcloud_sec,
                "point_export_sec": point_export_sec,
                "point_count": int(len(pointcloud.coords)),
                "pointcloud_ply_path": rel(pc_ply_path),
                "gpu_after": gpu_snapshot(),
            }

            mesh_sec = 0.0
            mesh_export_sec = 0.0
            if args.mesh:
                if sdf_model is None:
                    raise RuntimeError("mesh requested but SDF model is not loaded")
                start = time.perf_counter()
                mesh = marching_cubes_mesh(
                    pc=pointcloud,
                    model=sdf_model,
                    batch_size=args.sdf_batch_size,
                    grid_size=args.sdf_grid_size,
                    progress=False,
                )
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
                mesh_sec = time.perf_counter() - start
                mesh_path = out / f"{label}.ply"
                start = time.perf_counter()
                with mesh_path.open("wb") as f:
                    mesh.write_ply(f)
                mesh_export_sec = time.perf_counter() - start
                payload.update(
                    {
                        "mesh_sec": mesh_sec,
                        "mesh_export_sec": mesh_export_sec,
                        "mesh_path": rel(mesh_path),
                        "mesh_bytes": mesh_path.stat().st_size,
                        "vertices": int(len(mesh.verts)),
                        "faces": int(len(mesh.faces)),
                        "triangles": int(len(mesh.faces)),
                    }
                )
            else:
                payload.update(
                    {
                        "mesh_sec": 0.0,
                        "mesh_export_sec": 0.0,
                        "mesh_path": "",
                        "mesh_bytes": 0,
                        "vertices": int(len(pointcloud.coords)),
                        "faces": 0,
                        "triangles": 0,
                    }
                )
            payload.update(
                {
                    "wall_sec": time.perf_counter() - start_wall,
                    **torch_peak(),
                }
            )
        except Exception as exc:
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            payload = {
                "model": "point_e_image_sdf32" if args.mesh else "point_e_image_pointcloud",
                "label": label,
                "prompt": item.get("prompt") or label,
                "status": "error",
                "input_mode": "image",
                "error": f"{type(exc).__name__}: {exc}",
                "wall_sec": time.perf_counter() - start_wall,
                "gpu_after": gpu_snapshot(),
                **torch_peak(),
            }
        emit("SPPA_BENCH_OBJECT", payload)


if __name__ == "__main__":
    main()
