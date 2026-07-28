from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from bench_common import ROOT, gpu_snapshot, write_csv, write_jsonl


PY312 = Path(r"C:\Users\xabie\AppData\Local\Programs\Python\Python312\python.exe")
TRIPOSR_PY = ROOT.parent / "papers" / "semantic_proxy_3d" / "generators" / "sota_3d_generators" / "_venvs" / "triposr" / "Scripts" / "python.exe"
OPENAI_TEXT3D_PY = ROOT.parent / "papers" / "semantic_proxy_3d" / "generators" / "sota_3d_generators" / "_venvs" / "openai_text3d" / "Scripts" / "python.exe"


def process_snapshot() -> str:
    cmd = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -eq 'python.exe' -or $_.Name -like 'UnrealEditor*' } | "
        "Select-Object ProcessId,Name,CommandLine | Format-List",
    ]
    try:
        return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT, timeout=10)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def nvidia_process_snapshot() -> str:
    cmd = [
        "nvidia-smi",
        "--query-compute-apps=pid,process_name,used_memory",
        "--format=csv,noheader,nounits",
    ]
    try:
        return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT, timeout=10)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def parse_events(stdout: str, command_name: str) -> list[dict]:
    rows: list[dict] = []
    for line in stdout.splitlines():
        if not line.startswith("SPPA_BENCH_"):
            continue
        try:
            event, payload = line.split(" ", 1)
            row = json.loads(payload)
            row["event"] = event
            row["command_name"] = command_name
            rows.append(row)
        except Exception as exc:
            rows.append(
                {
                    "event": "SPPA_BENCH_PARSE_ERROR",
                    "command_name": command_name,
                    "raw_line": line,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return rows


def run_command(run_dir: Path, name: str, cmd: list[str], timeout: int) -> list[dict]:
    start = time.perf_counter()
    before = gpu_snapshot()
    try:
        completed = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        status = "ok" if returncode == 0 else "error"
        error = ""
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        status = "timeout"
        error = f"TimeoutExpired: {timeout}s"
    wall = time.perf_counter() - start
    after = gpu_snapshot()

    (run_dir / f"{name}.stdout.log").write_text(stdout, encoding="utf-8", errors="ignore")
    (run_dir / f"{name}.stderr.log").write_text(stderr, encoding="utf-8", errors="ignore")
    events = parse_events(stdout, name)
    events.append(
        {
            "event": "SPPA_BENCH_COMMAND",
            "command_name": name,
            "status": status,
            "returncode": returncode,
            "wall_sec": wall,
            "error": error,
            "gpu_before": before,
            "gpu_after": after,
            "command": " ".join(cmd),
        }
    )
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reproducible SPPA vs fast 3D generator benchmark subset.")
    parser.add_argument("--run-id", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    parser.add_argument("--models", default="sppa,triposr,hunyuan,pointe_text,shape_text")
    parser.add_argument("--vram-limit-gb", type=float, default=6.0)
    parser.add_argument("--objects-csv", default="experiments/sppa_sota_benchmark/inputs/objects.csv")
    parser.add_argument("--objects-rgba-csv", default="experiments/sppa_sota_benchmark/inputs/objects_rgba.csv")
    args = parser.parse_args()

    run_dir = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "gpu_before.json").write_text(json.dumps(gpu_snapshot(), indent=2), encoding="utf-8")
    (run_dir / "processes_before.txt").write_text(process_snapshot(), encoding="utf-8", errors="ignore")
    (run_dir / "nvidia_processes_before.txt").write_text(nvidia_process_snapshot(), encoding="utf-8", errors="ignore")

    commands: dict[str, tuple[list[str], int]] = {
        "sppa": (
            [
                str(PY312),
                "tools/sppa_sota_benchmark/run_sppa_batch.py",
                "--objects-csv",
                args.objects_csv,
                "--output-dir",
                f"experiments/sppa_sota_benchmark/runs/{args.run_id}/outputs/sppa",
            ],
            120,
        ),
        "triposr": (
            [
                str(TRIPOSR_PY),
                "tools/sppa_sota_benchmark/run_triposr_warm_batch.py",
                "--objects-csv",
                args.objects_rgba_csv,
                "--output-dir",
                f"experiments/sppa_sota_benchmark/runs/{args.run_id}/outputs/triposr_warm_r128_6gb",
                "--repo-dir",
                "third_party/sota_3d_generators/TripoSR",
                "--vram-limit-gb",
                str(args.vram_limit_gb),
                "--mc-resolution",
                "128",
                "--chunk-size",
                "4096",
                "--model-save-format",
                "obj",
            ],
            900,
        ),
        "hunyuan": (
            [
                str(PY312),
                "tools/sppa_sota_benchmark/run_hunyuan_shape_batch.py",
                "--objects-csv",
                args.objects_rgba_csv,
                "--output-dir",
                f"experiments/sppa_sota_benchmark/runs/{args.run_id}/outputs/hunyuan3d_2mini_turbo_rgba_6gb",
                "--repo-dir",
                "third_party/sota_3d_generators/Hunyuan3D-2",
                "--vram-limit-gb",
                str(args.vram_limit_gb),
                "--model-path",
                "tencent/Hunyuan3D-2mini",
                "--subfolder",
                "hunyuan3d-dit-v2-mini-turbo",
                "--num-inference-steps",
                "5",
                "--octree-resolution",
                "380",
                "--num-chunks",
                "20000",
                "--enable-flashvdm",
            ],
            900,
        ),
        "pointe_text": (
            [
                str(OPENAI_TEXT3D_PY),
                "tools/sppa_sota_benchmark/run_pointe_text_batch.py",
                "--objects-csv",
                args.objects_csv,
                "--output-dir",
                f"experiments/sppa_sota_benchmark/runs/{args.run_id}/outputs/point_e_text_sdf32_4096_6gb",
                "--vram-limit-gb",
                str(args.vram_limit_gb),
                "--base-points",
                "1024",
                "--total-points",
                "4096",
                "--sdf-grid-size",
                "32",
                "--sdf-batch-size",
                "4096",
            ],
            900,
        ),
        "shape_text": (
            [
                str(OPENAI_TEXT3D_PY),
                "tools/sppa_sota_benchmark/run_shape_text_batch.py",
                "--objects-csv",
                args.objects_csv,
                "--output-dir",
                f"experiments/sppa_sota_benchmark/runs/{args.run_id}/outputs/shap_e_text_k16_6gb",
                "--vram-limit-gb",
                str(args.vram_limit_gb),
                "--batch-size",
                "1",
                "--karras-steps",
                "16",
            ],
            900,
        ),
    }

    selected = [name.strip() for name in args.models.split(",") if name.strip()]
    rows: list[dict] = []
    for name in selected:
        if name not in commands:
            rows.append({"event": "SPPA_BENCH_COMMAND", "command_name": name, "status": "unknown_model"})
            continue
        cmd, timeout = commands[name]
        rows.extend(run_command(run_dir, name, cmd, timeout))

    (run_dir / "gpu_after.json").write_text(json.dumps(gpu_snapshot(), indent=2), encoding="utf-8")
    (run_dir / "processes_after.txt").write_text(process_snapshot(), encoding="utf-8", errors="ignore")
    (run_dir / "nvidia_processes_after.txt").write_text(nvidia_process_snapshot(), encoding="utf-8", errors="ignore")
    write_jsonl(run_dir / "events.jsonl", rows)
    object_rows = [row for row in rows if row.get("event") == "SPPA_BENCH_OBJECT"]
    write_csv(run_dir / "objects.csv", object_rows)
    write_csv(run_dir / "commands.csv", [row for row in rows if row.get("event") == "SPPA_BENCH_COMMAND"])
    print(run_dir)
    if any(row.get("status") in {"error", "timeout"} for row in rows):
        sys.exit(1)


if __name__ == "__main__":
    main()
