#!/usr/bin/env python3
"""
extract_depth.py — genera un vídeo de control DEPTH desde el clip, con
Depth-Anything-V2 (vía transformers, sin clonar repo). GPU.

El depth respeta la geometría 3D real (mucho mejor que canny para aéreo):
VACE-Fun/Control acepta depth como control_video.

  python neural/extract_depth.py --video tmp/ejea_clip_input.mp4 \
      --out neural/ejea_control_depth.mp4 --model depth-anything/Depth-Anything-V2-Small-hf
"""
import argparse, sys
import numpy as np
import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="depth-anything/Depth-Anything-V2-Small-hf")
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args()

    import torch
    from transformers import pipeline as hf_pipeline
    from PIL import Image
    dev = 0 if torch.cuda.is_available() else -1
    pipe = hf_pipeline("depth-estimation", model=args.model,
                       device=dev, torch_dtype=torch.float32)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        sys.exit(f"no pude abrir {args.video}")
    w = int(cap.get(3)); h = int(cap.get(4)); fps = cap.get(5) or 16.0
    n = int(cap.get(7))
    if args.max_frames:
        n = min(n, args.max_frames)
    vw = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    c = 0
    for _ in range(n):
        ok, f = cap.read()
        if not ok:
            break
        rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
        out = pipe(Image.fromarray(rgb))
        d = np.array(out["depth"], dtype=np.float32)
        d = (d - d.min()) / (d.max() - d.min() + 1e-6)  # 0..1, cerca=claro
        g = (d * 255).astype(np.uint8)
        if g.shape[:2] != (h, w):
            g = cv2.resize(g, (w, h))
        vw.write(cv2.cvtColor(g, cv2.COLOR_GRAY2BGR))
        c += 1
        if c % 25 == 0:
            print(f"[depth] {c}/{n}", flush=True)
    cap.release(); vw.release()
    print(f"OK {c} frames -> {args.out}")


if __name__ == "__main__":
    main()
