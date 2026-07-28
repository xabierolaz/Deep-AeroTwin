from __future__ import annotations

import argparse
import os
import runpy
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a Python script after optionally capping PyTorch CUDA allocator memory."
    )
    parser.add_argument("--cwd", required=True, help="Working directory for the target script.")
    parser.add_argument("--script", required=True, help="Target Python script path, relative to --cwd or absolute.")
    parser.add_argument(
        "--vram-limit-gb",
        type=float,
        default=None,
        help="Optional PyTorch CUDA allocator budget in GiB. This is not a physical GPU partition.",
    )
    parser.add_argument("script_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    cwd = Path(args.cwd).resolve()
    script = Path(args.script)
    if not script.is_absolute():
        script = cwd / script

    cap_fraction = None
    try:
        import torch

        if args.vram_limit_gb is not None and torch.cuda.is_available():
            total_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
            cap_fraction = min(max(args.vram_limit_gb / total_gb, 0.0), 1.0)
            torch.cuda.set_per_process_memory_fraction(cap_fraction, 0)
            print(
                "SPPA_BENCH_VRAM_CAP "
                f"limit_gb={args.vram_limit_gb:.3f} "
                f"total_gb={total_gb:.3f} "
                f"fraction={cap_fraction:.6f}",
                flush=True,
            )
    except Exception as exc:  # pragma: no cover - intentionally defensive wrapper
        print(f"SPPA_BENCH_VRAM_CAP_ERROR {type(exc).__name__}: {exc}", flush=True)

    if str(cwd) not in sys.path:
        sys.path.insert(0, str(cwd))
    os.chdir(cwd)

    target_args = args.script_args
    if target_args and target_args[0] == "--":
        target_args = target_args[1:]
    sys.argv = [str(script)] + target_args

    try:
        runpy.run_path(str(script), run_name="__main__")
    finally:
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.synchronize()
                print(
                    "SPPA_BENCH_TORCH_PEAK "
                    f"allocated_mb={torch.cuda.max_memory_allocated() / 1024**2:.2f} "
                    f"reserved_mb={torch.cuda.max_memory_reserved() / 1024**2:.2f}",
                    flush=True,
                )
                if cap_fraction is not None:
                    print(
                        "SPPA_BENCH_TORCH_CAP_FRACTION "
                        f"{torch.cuda.get_per_process_memory_fraction(0):.6f}",
                        flush=True,
                    )
        except Exception as exc:  # pragma: no cover
            print(f"SPPA_BENCH_TORCH_PEAK_ERROR {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
