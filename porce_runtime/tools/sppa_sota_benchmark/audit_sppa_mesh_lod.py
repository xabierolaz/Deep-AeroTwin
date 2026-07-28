"""Audit SPPA archetype triangle budgets across mesh LOD levels."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"
OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sppa_mesh_lod_budget.json"
LABELS = ["biker", "tower", "tractor", "tractor_trailer", "car", "cow", "person", "tree"]


def load_gen():
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", GEN)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build(module, label: str, lod: str):
    mesh = module.Mesh(lod=lod)
    if label in module.PARAMETRIC_BUILDERS:
        dims = module.DEFAULT_ARCHETYPE_DIMS_M.get(label, {"length": 2.0, "width": 1.0, "height": 1.5})
        module.PARAMETRIC_BUILDERS[label](mesh, dims)
    else:
        builder, _, _ = module.resolve_builder(label)
        builder(mesh)
    return {
        "label": label,
        "lod": lod,
        "triangles": mesh.triangle_count(),
        "vertices": len(mesh.vertices),
        "parts": len(mesh.parts),
        "part_triangles": sorted(
            (
                {
                    "role": part.get("role"),
                    "primitive": part.get("primitive"),
                    "triangle_budget": part.get("triangle_budget"),
                }
                for part in mesh.parts
            ),
            key=lambda row: -int(row["triangle_budget"] or 0),
        )[:8],
    }


def main() -> int:
    module = load_gen()
    rows = []
    for lod in ("high", "balanced", "ultra_light"):
        for label in LABELS:
            rows.append(build(module, label, lod))
    pivot = {}
    for row in rows:
        pivot.setdefault(row["label"], {})[row["lod"]] = row["triangles"]
    summary = {
        "default_lod": module.SPPA_MESH_LOD,
        "policy": "fidelity-preserving triangle reduction via LOD-aware tessellation",
        "rows": rows,
        "triangle_pivot": pivot,
        "balanced_vs_high": {
            label: {
                "high": vals["high"],
                "balanced": vals["balanced"],
                "ratio": round(vals["balanced"] / vals["high"], 3) if vals["high"] else None,
                "saved": vals["high"] - vals["balanced"],
            }
            for label, vals in pivot.items()
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "balanced_vs_high": summary["balanced_vs_high"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
