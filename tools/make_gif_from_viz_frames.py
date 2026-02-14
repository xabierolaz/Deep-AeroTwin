#!/usr/bin/env python3
"""
Build a GIF from the top-down 2D PNG frames produced by `pipeline/viz_recorder.py`.

Default input:
  - <repo>/pipeline/logs/viz_frames/frame_####.png

Example:
  python tools/make_gif_from_viz_frames.py --in-dir pipeline/logs/viz_frames --out pipeline/logs/viz.gif --fps 10 --width 960
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_dir(p: str) -> Path:
    path = Path(p).expanduser()
    if path.is_dir():
        return path
    cand = _repo_root() / p
    if cand.is_dir():
        return cand
    return path


def _resize_to_width(img, width: int):
    if width <= 0:
        return img
    w, h = img.size
    if w == width:
        return img
    new_h = max(1, int(round(h * (float(width) / float(w)))))
    try:
        resample = img.Resampling.LANCZOS  # Pillow>=9
    except Exception:
        resample = getattr(img, "LANCZOS", 1)
    return img.resize((int(width), int(new_h)), resample=resample)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Make a GIF from viz recorder frames.")
    p.add_argument(
        "--in-dir",
        default=str(_repo_root() / "pipeline" / "logs" / "viz_frames"),
        help="Directory containing PNG frames (default: pipeline/logs/viz_frames).",
    )
    p.add_argument(
        "--glob",
        default="frame_*.png",
        help="Glob pattern for frame files (default: frame_*.png).",
    )
    p.add_argument(
        "--out",
        default=str(_repo_root() / "pipeline" / "logs" / "viz.gif"),
        help="Output GIF path (default: pipeline/logs/viz.gif).",
    )
    p.add_argument("--fps", type=float, default=10.0, help="Playback FPS for the GIF (default: 10).")
    p.add_argument("--duration-ms", type=int, default=None, help="Override per-frame duration in ms (overrides --fps).")
    p.add_argument("--every", type=int, default=1, help="Use every Nth frame (default: 1).")
    p.add_argument("--max-frames", type=int, default=0, help="Limit number of frames (0 = no limit).")
    p.add_argument("--width", type=int, default=960, help="Resize frames to this width (0 = keep original).")
    p.add_argument("--optimize", action="store_true", help="Enable GIF optimization (slower, smaller).")
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    try:
        from PIL import Image  # type: ignore
    except Exception as e:
        print(f"[error] Pillow not installed: {e}")
        print("Install it with: pip install Pillow")
        return 2

    in_dir = _resolve_dir(str(args.in_dir))
    if not in_dir.is_dir():
        print(f"[error] input dir not found: {in_dir}")
        return 2

    pattern = str(args.glob)
    frames = sorted(in_dir.glob(pattern))
    if not frames and pattern == "frame_*.png":
        frames = sorted(in_dir.glob("*.png"))
    if not frames:
        print(f"[error] no frames found in {in_dir} (glob={pattern!r})")
        return 2

    every = int(args.every) if int(args.every) > 0 else 1
    frames = frames[::every]
    if int(args.max_frames) > 0:
        frames = frames[: int(args.max_frames)]

    out_path = Path(str(args.out)).expanduser()
    if not out_path.is_absolute():
        out_path = _repo_root() / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.duration_ms is not None:
        duration_ms = int(args.duration_ms)
    else:
        fps = float(args.fps)
        if not (fps > 0.0):
            print("[error] --fps must be > 0")
            return 2
        duration_ms = max(1, int(round(1000.0 / fps)))

    width = int(args.width)

    base = Image.open(frames[0]).convert("RGB")
    base = _resize_to_width(base, width)
    out_frames = []
    for p in frames[1:]:
        im = Image.open(p).convert("RGB")
        im = _resize_to_width(im, width)
        if im.size != base.size:
            # Keep GIF dimensions stable even if a frame differs.
            im = im.resize(base.size)
        out_frames.append(im)

    base.save(
        str(out_path),
        save_all=True,
        append_images=out_frames,
        duration=duration_ms,
        loop=0,
        optimize=bool(args.optimize),
    )

    print(
        f"[ok] wrote {out_path} frames={len(frames)} size={base.size[0]}x{base.size[1]} "
        f"duration_ms={duration_ms} optimize={bool(args.optimize)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

