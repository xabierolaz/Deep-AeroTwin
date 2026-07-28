#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_GLOB = "frame_*.png"
DEFAULT_OUT_NAME = "viz.gif"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_in_dir() -> Path:
    return _repo_root() / "pipeline" / "logs" / "viz_frames"


def _default_out_path() -> Path:
    return _repo_root() / "pipeline" / "logs" / DEFAULT_OUT_NAME


def _default_latest_run_file() -> Path:
    return _repo_root() / "pipeline" / "logs" / "zero_trust" / "LATEST_RUN.txt"


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str).expanduser()
    if path.exists():
        return path
    candidate = _repo_root() / path
    return candidate


def _latest_run_dir(path_str: str) -> Optional[Path]:
    latest_file = _resolve_path(path_str)
    if not latest_file.is_file():
        return None
    try:
        raw = latest_file.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    if not raw:
        return None
    run_dir = _resolve_path(raw)
    if run_dir.is_dir():
        return run_dir
    return None


def _parse_run_stamp_seconds(run_dir: Path) -> Optional[float]:
    match = re.search(r"(\d{8}_\d{6})", run_dir.name)
    if not match:
        return None
    try:
        stamp_dt = datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
    except Exception:
        return None
    return float(stamp_dt.timestamp())


def _run_time_window_seconds(run_dir: Path, margin_s: float) -> tuple[float, float]:
    start_s = _parse_run_stamp_seconds(run_dir)
    if start_s is None:
        start_s = float(run_dir.stat().st_mtime)

    end_s = start_s
    try:
        for file_path in run_dir.rglob("*"):
            if file_path.is_file():
                end_s = max(end_s, float(file_path.stat().st_mtime))
    except Exception:
        pass

    margin = max(0.0, float(margin_s))
    return start_s - margin, end_s + margin


def _filter_frames_by_time_window(frame_paths: list[Path], start_s: float, end_s: float) -> list[Path]:
    selected = []
    for frame_path in frame_paths:
        try:
            ts = float(frame_path.stat().st_mtime)
        except Exception:
            continue
        if start_s <= ts <= end_s:
            selected.append(frame_path)
    return selected


def _infer_fps_from_mtime(frame_paths: list[Path], fallback_fps: float = 10.0) -> float:
    if len(frame_paths) < 2:
        return float(fallback_fps)
    times = []
    for path in frame_paths:
        try:
            times.append(float(path.stat().st_mtime))
        except Exception:
            continue
    if len(times) < 2:
        return float(fallback_fps)
    deltas = []
    for i in range(1, len(times)):
        dt = times[i] - times[i - 1]
        if dt > 0.0:
            deltas.append(dt)
    if not deltas:
        return float(fallback_fps)
    median_dt = float(statistics.median(deltas))
    if median_dt <= 0.0:
        return float(fallback_fps)
    fps = 1.0 / median_dt
    return max(1.0, min(60.0, fps))


def _resize(image, width: int):
    if width <= 0:
        return image
    src_w, src_h = image.size
    if src_w == width:
        return image
    dst_h = max(1, int(round(src_h * (float(width) / float(src_w)))))
    try:
        resample = image.Resampling.LANCZOS
    except Exception:
        resample = getattr(image, "LANCZOS", 1)
    return image.resize((int(width), int(dst_h)), resample=resample)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GIF from viz recorder PNG frames (manual, not in runtime flow).")
    parser.add_argument(
        "--latest-run",
        action="store_true",
        help="Use latest zero-trust run window from LATEST_RUN.txt and keep only matching viz frames.",
    )
    parser.add_argument(
        "--latest-run-file",
        default=str(_default_latest_run_file()),
        help="Path to LATEST_RUN.txt (used with --latest-run).",
    )
    parser.add_argument(
        "--run-dir",
        default="",
        help="Optional run directory override (used with --latest-run).",
    )
    parser.add_argument(
        "--run-margin-s",
        type=float,
        default=2.0,
        help="Time margin in seconds around run window when matching viz frames.",
    )
    parser.add_argument(
        "--in-dir",
        default=str(_default_in_dir()),
        help="Input directory with PNG frames.",
    )
    parser.add_argument(
        "--glob",
        default=DEFAULT_GLOB,
        help="Glob pattern for frames.",
    )
    parser.add_argument(
        "--out",
        default=str(_default_out_path()),
        help="Output GIF path.",
    )
    parser.add_argument("--fps", type=float, default=0.0, help="GIF playback FPS (0 = auto from frame mtimes).")
    parser.add_argument("--every", type=int, default=1, help="Use every Nth frame.")
    parser.add_argument("--max-frames", type=int, default=0, help="Limit number of frames (0 = all).")
    parser.add_argument("--width", type=int, default=960, help="Resize frames to width (0 = no resize).")
    parser.add_argument("--optimize", action="store_true", help="Enable GIF optimization.")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:
        print(f"[ERROR] Pillow no disponible: {exc}")
        print("Instala: pip install Pillow")
        return 2

    input_dir = _resolve_path(str(args.in_dir))
    if not input_dir.is_dir():
        print(f"[ERROR] Input dir no existe: {input_dir}")
        return 2

    run_dir = None
    run_window = None
    if bool(args.latest_run):
        if str(args.run_dir).strip():
            run_dir = _resolve_path(str(args.run_dir).strip())
            if not run_dir.is_dir():
                print(f"[ERROR] --run-dir no existe: {run_dir}")
                return 2
        else:
            run_dir = _latest_run_dir(str(args.latest_run_file))
            if run_dir is None:
                print(f"[ERROR] No se pudo resolver latest run desde: {args.latest_run_file}")
                return 2
        run_window = _run_time_window_seconds(run_dir, float(args.run_margin_s))
        print(f"[INFO] latest-run={run_dir}")

    frame_paths = sorted(input_dir.glob(str(args.glob)))
    if not frame_paths and str(args.glob) == DEFAULT_GLOB:
        frame_paths = sorted(input_dir.glob("*.png"))
    if not frame_paths:
        print(f"[ERROR] No hay frames en {input_dir}")
        return 2

    if run_window is not None:
        start_s, end_s = run_window
        selected = _filter_frames_by_time_window(frame_paths, start_s, end_s)
        if not selected:
            print(
                f"[ERROR] No hay frames que caigan en la ventana del run "
                f"({datetime.fromtimestamp(start_s)} .. {datetime.fromtimestamp(end_s)})."
            )
            return 2
        frame_paths = selected

    every = max(1, int(args.every))
    frame_paths = frame_paths[::every]
    if int(args.max_frames) > 0:
        frame_paths = frame_paths[: int(args.max_frames)]
    if not frame_paths:
        print("[ERROR] Seleccion de frames vacia tras filtros.")
        return 2

    fps = float(args.fps)
    if fps <= 0.0:
        fps = _infer_fps_from_mtime(frame_paths, fallback_fps=10.0)
    duration_ms = max(1, int(round(1000.0 / fps)))

    output_path = Path(str(args.out)).expanduser()
    if not output_path.is_absolute():
        output_path = _repo_root() / output_path
    if run_dir is not None and str(args.out) == str(_default_out_path()):
        output_path = run_dir / DEFAULT_OUT_NAME
    output_path.parent.mkdir(parents=True, exist_ok=True)

    base = Image.open(frame_paths[0]).convert("RGB")
    base = _resize(base, int(args.width))
    append = []
    for frame_path in frame_paths[1:]:
        frame = Image.open(frame_path).convert("RGB")
        frame = _resize(frame, int(args.width))
        if frame.size != base.size:
            frame = frame.resize(base.size)
        append.append(frame)

    base.save(
        str(output_path),
        save_all=True,
        append_images=append,
        duration=duration_ms,
        loop=0,
        optimize=bool(args.optimize),
    )

    print(
        f"[OK] GIF generado: {output_path} | frames={len(frame_paths)} | "
        f"size={base.size[0]}x{base.size[1]} | fps={fps:g}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
