#!/usr/bin/env python3
"""
live_server.py — servidor de restyle en vivo con StreamDiffusionV2 (WSL/GPU).

Mantiene el modelo CALIENTE en un único proceso y expone un endpoint HTTP que
recibe un frame JPEG + noise_scale y devuelve el frame restyled JPEG. El cliente
(live_viewer.py, en Windows) captura la ventana de Unreal y mueve un slider de
noise_scale; aquí ese valor se aplica EN VIVO mutando session.init_noise_scale
entre chunks (es el término dominante, peso 0.9, en compute_noise_scale_and_step).

Arranque (en WSL, dentro de ~/sdv2_venv, desde el repo):
  cd /mnt/d/Deep-AeroTwin-UE57-Test/neural/StreamDiffusionV2
  source ~/sdv2_venv/bin/activate
  pip install fastapi uvicorn   # si no están
  python /mnt/d/Deep-AeroTwin-UE57-Test/neural/live_server.py \
      --config_path configs/wan_causal_dmd_v2v.yaml \
      --checkpoint_folder ckpts/wan_causal_dmd_v2v \
      --prompt_file /mnt/d/Deep-AeroTwin-UE57-Test/neural/ejea_prompt.txt \
      --height 480 --width 480 --step 2 --noise_scale 0.8 \
      --host 0.0.0.0 --port 9500

WSL2 reenvía localhost↔Windows, así el cliente en Windows llega a 127.0.0.1:9500.

=== ESTADO: NO PROBADO EN GPU desde este sandbox (sin torch/CUDA aquí). ===
Construido contra la API real de streamv2v.inference (start_stream_session /
run_stream_batch / compute_noise_scale_and_step) y el contrato de tensores de
demo/util.py (RGB, /127.5-1, (1,3,N,H,W) bfloat16). Puntos a vigilar en el 1er run:
  - chunk_size = 4 * num_frame_per_block (=4 con el yaml actual); first batch = 5.
  - Mutar init_noise_scale a mitad de stream: estable esperado, pero verifícalo
    visualmente (cambios bruscos del slider pueden tardar 1-2 chunks en notarse).
  - cv2 lee JPEG en BGR -> aquí se convierte a RGB antes de normalizar.
"""
import argparse, io, sys, os, threading, time
from types import SimpleNamespace

import numpy as np
import cv2

REPO = os.path.dirname(os.path.abspath(__file__))  # .../neural
SDV2 = os.path.join(REPO, "StreamDiffusionV2")
for p in (SDV2, os.path.join(SDV2, "streamv2v")):
    if p not in sys.path:
        sys.path.insert(0, p)

import torch
from streamv2v.inference import SingleGPUInferencePipeline
from streamv2v.inference_common import merge_cli_config


class LiveEngine:
    def __init__(self, args):
        torch.set_grad_enabled(False)
        if torch.cuda.is_available():
            gid = 0 if args.gpu_id is None else args.gpu_id
            torch.cuda.set_device(gid)
            self.device = torch.device(f"cuda:{gid}")
        else:
            self.device = torch.device("cpu")
            print("[live_server] WARNING: CUDA no disponible, irá lentísimo")

        # args namespace que merge_cli_config espera (mismos campos que el CLI)
        cli = SimpleNamespace(
            config_path=args.config_path, checkpoint_folder=args.checkpoint_folder,
            output_folder=".", prompt_file_path=args.prompt_file, video_path=None,
            noise_scale=args.noise_scale, height=args.height, width=args.width,
            fps=args.fps, step=args.step, seed=args.seed, gpu_id=args.gpu_id,
            model_type="T2V-1.3B", num_frames=81, fixed_noise_scale=False, t2v=False,
            target_fps=None, profile=False, use_taehv=args.use_taehv,
            use_tensorrt=args.use_tensorrt, fast=False,
        )
        self.config = merge_cli_config(args.config_path, cli)
        self.pm = SingleGPUInferencePipeline(self.config, self.device)
        self.pm.load_model(args.checkpoint_folder)

        self.H, self.W = args.height, args.width
        self.base_chunk = 4
        self.chunk_size = self.base_chunk * int(self.config.num_frame_per_block)
        self.first_batch = 1 + self.chunk_size

        self.prompt = open(args.prompt_file).read().strip()
        self.noise_scale = float(args.noise_scale)
        self.session = None
        self.buf = []  # list of normalized RGB frames (H,W,3) float
        self.lock = threading.Lock()
        print(f"[live_server] listo. chunk_size={self.chunk_size} "
              f"first_batch={self.first_batch} res={self.W}x{self.H}")

    def _norm(self, bgr):
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (self.W, self.H))
        return rgb.astype(np.float32) / 127.5 - 1.0  # [-1,1]

    def _to_tensor(self, frames):
        arr = np.stack(frames, axis=0)                  # (N,H,W,3)
        t = torch.from_numpy(arr).unsqueeze(0)          # (1,N,H,W,3)
        t = t.permute(0, 4, 1, 2, 3).to(dtype=torch.bfloat16, device=self.device)
        return t                                        # (1,3,N,H,W)

    def _out_jpeg(self, video_np):
        # video_np: (N,H,W,3) en [0,1] RGB -> último frame -> JPEG BGR
        last = np.clip(video_np[-1] * 255.0, 0, 255).astype(np.uint8)
        bgr = cv2.cvtColor(last, cv2.COLOR_RGB2BGR)
        ok, enc = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return enc.tobytes() if ok else None

    def set_params(self, noise_scale=None, prompt=None, restart=False):
        with self.lock:
            if noise_scale is not None:
                self.noise_scale = float(noise_scale)
            if prompt:
                if prompt != self.prompt:
                    self.prompt = prompt
                    restart = True
            if restart:
                self.session = None
                self.buf = []

    def push(self, jpeg_bytes):
        """Add a frame; return restyled JPEG when a chunk completes, else None."""
        bgr = cv2.imdecode(np.frombuffer(jpeg_bytes, np.uint8), cv2.IMREAD_COLOR)
        if bgr is None:
            return None
        with self.lock:
            self.buf.append(self._norm(bgr))
            if self.session is None:
                if len(self.buf) < self.first_batch:
                    return None
                frames = self.buf[:self.first_batch]
                self.buf = self.buf[self.first_batch:]
                imgs = self._to_tensor(frames)
                self.session, init_video = self.pm.start_stream_session(
                    prompt=self.prompt, images=imgs, noise_scale=self.noise_scale)
                return self._out_jpeg(init_video)
            else:
                if len(self.buf) < self.chunk_size:
                    return None
                frames = self.buf[:self.chunk_size]
                self.buf = self.buf[self.chunk_size:]
                imgs = self._to_tensor(frames)
                # >>> SLIDER EN VIVO: init_noise_scale domina el ruido del chunk <<<
                self.session.init_noise_scale = self.noise_scale
                self.session.noise_scale = self.noise_scale
                outs = self.pm.run_stream_batch(self.session, imgs)
                # run_stream_batch devuelve lista de arrays (cada uno (N,H,W,3))
                last = outs[-1]
                return self._out_jpeg(last)


def build_app(engine: "LiveEngine"):
    from fastapi import FastAPI, Request, Response
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"ok": True, "noise_scale": engine.noise_scale,
                "chunk_size": engine.chunk_size, "buffered": len(engine.buf),
                "session": engine.session is not None}

    @app.post("/params")
    async def params(request: Request):
        d = await request.json()
        engine.set_params(noise_scale=d.get("noise_scale"),
                          prompt=d.get("prompt"), restart=bool(d.get("restart")))
        return {"ok": True, "noise_scale": engine.noise_scale}

    @app.post("/infer")
    async def infer(request: Request):
        ns = request.query_params.get("noise_scale")
        if ns is not None:
            engine.set_params(noise_scale=float(ns))
        body = await request.body()
        out = engine.push(body)
        if out is None:
            return Response(status_code=204)  # need more frames
        return Response(content=out, media_type="image/jpeg")

    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config_path", default="configs/wan_causal_dmd_v2v.yaml")
    ap.add_argument("--checkpoint_folder", default="ckpts/wan_causal_dmd_v2v")
    ap.add_argument("--prompt_file", required=True)
    ap.add_argument("--noise_scale", type=float, default=0.8)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--width", type=int, default=480)
    ap.add_argument("--fps", type=int, default=16)
    ap.add_argument("--step", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--gpu_id", type=int, default=0)
    ap.add_argument("--use_taehv", action="store_true")
    ap.add_argument("--use_tensorrt", action="store_true")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9500)
    args = ap.parse_args()

    import uvicorn
    engine = LiveEngine(args)
    uvicorn.run(build_app(engine), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
