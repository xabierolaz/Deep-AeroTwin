from __future__ import annotations

import csv
import json
import os
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def read_objects(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def emit(event: str, payload: dict[str, Any]) -> None:
    print(f"{event} {json.dumps(payload, sort_keys=True)}", flush=True)


def gpu_snapshot() -> dict[str, Any]:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
        name, driver, total, used, util = [part.strip() for part in out.split(",")[:5]]
        return {
            "name": name,
            "driver": driver,
            "memory_total_mb": int(total),
            "memory_used_mb": int(used),
            "utilization_gpu_pct": int(util),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def torch_peak() -> dict[str, float]:
    try:
        import torch

        if not torch.cuda.is_available():
            return {}
        torch.cuda.synchronize()
        return {
            "torch_peak_allocated_mb": torch.cuda.max_memory_allocated() / 1024**2,
            "torch_peak_reserved_mb": torch.cuda.max_memory_reserved() / 1024**2,
        }
    except Exception:
        return {}


def obj_stats(path: Path) -> dict[str, Any]:
    vertices = 0
    faces = 0
    triangles = 0
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("v "):
                vertices += 1
            elif line.startswith("f "):
                faces += 1
                n = len(line.split()) - 1
                triangles += max(0, n - 2)
    return {
        "mesh_path": rel(path),
        "mesh_bytes": path.stat().st_size,
        "vertices": vertices,
        "faces": faces,
        "triangles": triangles,
    }


def mesh_stats(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".obj":
        return obj_stats(path)
    try:
        import trimesh

        loaded = trimesh.load(path, force="scene")
        geometries = list(getattr(loaded, "geometry", {}).values())
        if not geometries and hasattr(loaded, "vertices"):
            geometries = [loaded]
        vertices = sum(len(getattr(g, "vertices", [])) for g in geometries)
        faces = sum(len(getattr(g, "faces", [])) for g in geometries)
        return {
            "mesh_path": rel(path),
            "mesh_bytes": path.stat().st_size,
            "vertices": int(vertices),
            "faces": int(faces),
            "triangles": int(faces),
        }
    except Exception as exc:
        return {
            "mesh_path": rel(path),
            "mesh_bytes": path.stat().st_size if path.exists() else 0,
            "mesh_stats_error": f"{type(exc).__name__}: {exc}",
        }


def ensure_clean_child_dir(base: Path, child: str) -> Path:
    out = base / child
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def configure_torch_vram_cap(limit_gb: float | None) -> dict[str, Any]:
    if limit_gb is None:
        return {"vram_limit_gb": None}
    try:
        import torch

        if not torch.cuda.is_available():
            return {"vram_limit_gb": limit_gb, "vram_cap_error": "cuda unavailable"}
        total_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        fraction = min(max(limit_gb / total_gb, 0.0), 1.0)
        torch.cuda.set_per_process_memory_fraction(fraction, 0)
        return {
            "vram_limit_gb": limit_gb,
            "gpu_total_gb": total_gb,
            "torch_vram_fraction": fraction,
        }
    except Exception as exc:
        return {"vram_limit_gb": limit_gb, "vram_cap_error": f"{type(exc).__name__}: {exc}"}


def set_pythonpath_for(path: Path) -> None:
    import sys

    resolved = str(path.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    os.chdir(path)
