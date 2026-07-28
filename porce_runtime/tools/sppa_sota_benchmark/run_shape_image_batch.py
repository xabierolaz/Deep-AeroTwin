from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import torch

from bench_common import ROOT, configure_torch_vram_cap, emit, gpu_snapshot, mesh_stats, read_objects, set_pythonpath_for, torch_peak


def create_pan_cameras(size: int, device: torch.device):
    from shap_e.models.nn.camera import DifferentiableCameraBatch, DifferentiableProjectiveCamera

    origins = []
    xs = []
    ys = []
    zs = []
    for theta in np.linspace(0, 2 * np.pi, num=20):
        z = np.array([np.sin(theta), np.cos(theta), -0.5])
        z /= np.sqrt(np.sum(z**2))
        origin = -z * 4
        x = np.array([np.cos(theta), -np.sin(theta), 0.0])
        y = np.cross(z, x)
        origins.append(origin)
        xs.append(x)
        ys.append(y)
        zs.append(z)
    return DifferentiableCameraBatch(
        shape=(1, len(xs)),
        flat_camera=DifferentiableProjectiveCamera(
            origin=torch.from_numpy(np.stack(origins, axis=0)).float().to(device),
            x=torch.from_numpy(np.stack(xs, axis=0)).float().to(device),
            y=torch.from_numpy(np.stack(ys, axis=0)).float().to(device),
            z=torch.from_numpy(np.stack(zs, axis=0)).float().to(device),
            width=size,
            height=size,
            x_fov=0.7,
            y_fov=0.7,
        ),
    )


@torch.no_grad()
def decode_latent_mesh(transmitter, latent: torch.Tensor):
    from shap_e.models.transmitter.base import Transmitter
    from shap_e.util.collections import AttrDict

    bottleneck = transmitter.encoder if isinstance(transmitter, Transmitter) else transmitter
    decoded = transmitter.renderer.render_views(
        AttrDict(cameras=create_pan_cameras(2, latent.device)),
        params=bottleneck.bottleneck_to_params(latent[None]),
        options=AttrDict(rendering_mode="stf", render_with_direction=False),
    )
    return decoded.raw_meshes[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Shap-E image-to-3D with one resident model load.")
    parser.add_argument("--objects-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--vram-limit-gb", type=float, default=None)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--guidance-scale", type=float, default=3.0)
    parser.add_argument("--karras-steps", type=int, default=64)
    parser.add_argument("--sigma-min", type=float, default=1e-3)
    parser.add_argument("--sigma-max", type=float, default=160.0)
    parser.add_argument("--s-churn", type=float, default=0.0)
    parser.add_argument("--use-fp16", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    objects_csv = Path(args.objects_csv)
    if not objects_csv.is_absolute():
        objects_csv = ROOT / objects_csv
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    from shap_e.diffusion.gaussian_diffusion import diffusion_from_config
    from shap_e.diffusion.sample import sample_latents
    from shap_e.models.download import load_config, load_model

    def load_image(image_path: str):
        from PIL import Image

        img = Image.open(image_path)
        img.load()
        return img

    objects = read_objects(objects_csv)
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = configure_torch_vram_cap(args.vram_limit_gb)
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    start = time.perf_counter()
    transmitter = load_model("transmitter", device=device)
    model = load_model("image300M", device=device)
    diffusion = diffusion_from_config(load_config("diffusion"))
    load_sec = time.perf_counter() - start
    emit(
        "SPPA_BENCH_MODEL",
        {
            "model": f"shap_e_image_k{args.karras_steps}",
            "status": "loaded",
            "load_sec": load_sec,
            "device": str(device),
            "input_mode": "image",
            "image_model": "image300M",
            "batch_size": args.batch_size,
            "guidance_scale": args.guidance_scale,
            "karras_steps": args.karras_steps,
            "use_fp16": args.use_fp16,
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
            image = load_image(str(image_path))
            start = time.perf_counter()
            latents = sample_latents(
                batch_size=args.batch_size,
                model=model,
                diffusion=diffusion,
                guidance_scale=args.guidance_scale,
                model_kwargs={"images": [image] * args.batch_size},
                progress=False,
                clip_denoised=True,
                use_fp16=args.use_fp16,
                use_karras=True,
                karras_steps=args.karras_steps,
                sigma_min=args.sigma_min,
                sigma_max=args.sigma_max,
                s_churn=args.s_churn,
            )
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            sample_sec = time.perf_counter() - start

            start = time.perf_counter()
            mesh = decode_latent_mesh(transmitter, latents[0]).tri_mesh()
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            decode_sec = time.perf_counter() - start

            mesh_path = out / f"{label}.obj"
            start = time.perf_counter()
            with mesh_path.open("w", encoding="utf-8") as f:
                mesh.write_obj(f)
            export_sec = time.perf_counter() - start
            payload = {
                "model": f"shap_e_image_k{args.karras_steps}",
                "label": label,
                "prompt": item.get("prompt") or label,
                "status": "ok",
                "input_mode": "image",
                "sample_sec": sample_sec,
                "decode_sec": decode_sec,
                "export_sec": export_sec,
                "wall_sec": time.perf_counter() - start_wall,
                "gpu_after": gpu_snapshot(),
                **torch_peak(),
            }
            payload.update(mesh_stats(mesh_path))
        except Exception as exc:
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            payload = {
                "model": f"shap_e_image_k{args.karras_steps}",
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
