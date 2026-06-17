#!/usr/bin/env python3
"""
configure_wan_control.py — toma el script OFICIAL de VideoX-Fun
(examples/wan2.2_fun/predict_v2v_control.py) y reescribe SOLO las variables de
configuración a nuestros valores de AeroTwin, escribiendo predict_aerotwin.py.

Así usamos el código real de upstream (no una copia que pueda quedar obsoleta);
solo cambiamos los parámetros. Sin torch: corre en cualquier sitio.

  python neural/configure_wan_control.py \
    --src   VideoX-Fun/examples/wan2.2_fun/predict_v2v_control.py \
    --out   VideoX-Fun/examples/wan2.2_fun/predict_aerotwin.py \
    --model "models/Diffusion_Transformer/Wan2.2-Fun-A14B-Control" \
    --control /mnt/d/Deep-AeroTwin-UE57-Test/neural/ejea_control_canny.mp4 \
    --ref     /mnt/d/Deep-AeroTwin-UE57-Test/tmp/ejea_ref_frame.png \
    --prompt-file /mnt/d/Deep-AeroTwin-UE57-Test/neural/ejea_prompt.txt \
    --size 480 480 --frames 81 --fps 16 --steps 40 --guidance 6.0 \
    --gpu-mode sequential_cpu_offload \
    --save /mnt/d/Deep-AeroTwin-UE57-Test/neural/wan_control_out
"""
import argparse, re, sys

NEG_EN = ("blurry, distorted, deformed, warped geometry, melting structures, "
          "extra objects, hallucinated buildings, text, watermark, low quality, "
          "oversaturated, cartoon, painting, washed out, flicker")


def set_global(text, name, value_literal):
    """Reescribe la 1ª asignación de nivel de módulo `name = ...` (una línea)."""
    pat = re.compile(rf"(?m)^{re.escape(name)}\s*=.*$")
    repl = f"{name} = {value_literal}"
    new, n = pat.subn(repl, text, count=1)
    if n == 0:
        print(f"  [WARN] no encontré la variable '{name}' (¿cambió upstream?)", file=sys.stderr)
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--config-path", default=None,
                    help="ruta del yaml de config dentro del repo (p.ej. config/wan2.1/wan_civitai.yaml para VACE)")
    ap.add_argument("--control", required=True)
    ap.add_argument("--ref", default=None, help="imagen de referencia (color/apariencia; Fun-Control)")
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--size", nargs=2, type=int, default=[480, 480], help="H W")
    ap.add_argument("--frames", type=int, default=81)
    ap.add_argument("--fps", type=int, default=16)
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--guidance", type=float, default=6.0)
    ap.add_argument("--seed", type=int, default=43)
    ap.add_argument("--gpu-mode", default="sequential_cpu_offload")
    ap.add_argument("--save", required=True)
    args = ap.parse_args()

    prompt = open(args.prompt_file, encoding="utf-8").read().strip()
    text = open(args.src, encoding="utf-8").read()

    text = set_global(text, "GPU_memory_mode", repr(args.gpu_mode))
    text = set_global(text, "model_name", repr(args.model))
    if args.config_path:
        text = set_global(text, "config_path", repr(args.config_path))
    text = set_global(text, "control_video", repr(args.control))
    if args.ref:  # Fun-Control usa ref_image; VACE no lo tiene (warn inocuo)
        text = set_global(text, "ref_image", repr(args.ref))
    text = set_global(text, "start_image", "None")
    text = set_global(text, "end_image", "None")
    text = set_global(text, "prompt", repr(prompt))
    text = set_global(text, "negative_prompt", repr(NEG_EN))
    text = set_global(text, "sample_size", repr([args.size[0], args.size[1]]))
    text = set_global(text, "video_length", str(args.frames))
    text = set_global(text, "fps", str(args.fps))
    text = set_global(text, "num_inference_steps", str(args.steps))
    text = set_global(text, "guidance_scale", str(args.guidance))
    text = set_global(text, "seed", str(args.seed))
    text = set_global(text, "save_path", repr(args.save))

    open(args.out, "w", encoding="utf-8").write(text)
    print(f"OK -> {args.out}\n  model={args.model}\n  control={args.control}\n"
          f"  ref={args.ref}\n  size={args.size} frames={args.frames} steps={args.steps} "
          f"gpu_mode={args.gpu_mode}")


if __name__ == "__main__":
    main()
