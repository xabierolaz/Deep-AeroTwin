"""Silhouette consistency of LOD meshes vs high-LOD reference + mask-dim check."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"
OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sppa_silhouette_lod_audit.json"
LABELS = ["biker", "tractor", "tractor_trailer", "tower", "car"]


def load_gen():
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", GEN)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def mesh_silhouettes(mesh, res: int = 96, pad: float = 0.15):
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    if len(verts) == 0:
        z = np.zeros((res, res), dtype=bool)
        return z, z
    mins = verts.min(0)
    maxs = verts.max(0)
    span = np.maximum(maxs - mins, 1e-6)
    mins = mins - pad * span
    maxs = maxs + pad * span
    face_pts = []
    for idxs, _ in mesh.faces:
        pts = verts[[i - 1 for i in idxs]]
        face_pts.append(pts.mean(0))
        face_pts.extend(list(pts))
    fp = np.asarray(face_pts)

    def raster(xy, i0, i1):
        img = np.zeros((res, res), dtype=bool)
        u = (xy[:, i0] - mins[i0]) / (maxs[i0] - mins[i0] + 1e-12)
        w = (xy[:, i1] - mins[i1]) / (maxs[i1] - mins[i1] + 1e-12)
        ui = np.clip((u * (res - 1)).astype(int), 0, res - 1)
        wi = np.clip((w * (res - 1)).astype(int), 0, res - 1)
        img[wi, ui] = True
        return ndimage.binary_dilation(img, iterations=1)

    return raster(fp, 0, 1), raster(fp, 0, 2)


def iou(a, b) -> float:
    inter = np.logical_and(a, b).sum()
    uni = np.logical_or(a, b).sum()
    return float(inter / uni) if uni else 1.0


def build(module, label: str, lod: str):
    mesh = module.Mesh(lod=lod)
    if label in module.PARAMETRIC_BUILDERS:
        module.PARAMETRIC_BUILDERS[label](mesh, module.DEFAULT_ARCHETYPE_DIMS_M.get(label, {"length": 2, "width": 1, "height": 1.5}))
    else:
        builder, _, _ = module.resolve_builder(label)
        builder(mesh)
    return mesh


def main() -> int:
    module = load_gen()
    rows = []
    for label in LABELS:
        high = build(module, label, "high")
        ht, hs = mesh_silhouettes(high)
        for lod in ("balanced", "ultra_light"):
            mesh = build(module, label, lod)
            t, s = mesh_silhouettes(mesh)
            rows.append(
                {
                    "label": label,
                    "lod": lod,
                    "triangles": mesh.triangle_count(),
                    "triangles_high": high.triangle_count(),
                    "top_iou_vs_high": round(iou(t, ht), 4),
                    "side_iou_vs_high": round(iou(s, hs), 4),
                    "mean_iou_vs_high": round(0.5 * (iou(t, ht) + iou(s, hs)), 4),
                }
            )
    # Mask/scale adaptation still active (dims, not mesh density).
    mask = {"polygon": [[10, 40], [90, 40], [90, 55], [10, 55]]}
    scale = {"meters_per_pixel": 0.05, "source": "audit", "confidence": 0.9}
    dim_rows = []
    for label in ("tractor", "biker", "car"):
        mesh = module.Mesh(lod="balanced")
        meta = module.build_label_observed(mesh, label, mask=mask, metric_scale=scale, height_m=2.0)
        dim_rows.append(
            {
                "label": label,
                "metric_dims_source": meta.get("metric_dims_source"),
                "effective_dims_m": meta.get("effective_dims_m"),
                "triangles": mesh.triangle_count(),
            }
        )
    balanced = [r for r in rows if r["lod"] == "balanced"]
    ultra = [r for r in rows if r["lod"] == "ultra_light"]
    payload = {
        "schema": "sppa-silhouette-lod-audit-v1",
        "interpretation": {
            "lod_vs_high_iou": "Self-consistency of proxy silhouette under cheap LOD vs high tessellation; not real-image GT.",
            "mask_dims": "Calibrated mask still drives length/width (silhouette footprint adaptation).",
            "what_improved": "Speed and triangle load; not photoreal image silhouette reconstruction.",
        },
        "rows": rows,
        "mask_dim_adaptation": dim_rows,
        "summary": {
            "mean_iou_balanced_vs_high": round(float(np.mean([r["mean_iou_vs_high"] for r in balanced])), 4),
            "mean_iou_ultra_vs_high": round(float(np.mean([r["mean_iou_vs_high"] for r in ultra])), 4),
            "mean_tris_balanced": round(float(np.mean([r["triangles"] for r in balanced])), 1),
            "mean_tris_high": round(float(np.mean([r["triangles_high"] for r in balanced])), 1),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print("mask_dim_adaptation", dim_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
