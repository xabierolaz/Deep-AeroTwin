"""Use-case SOTA benchmark for SPPA as a UAV digital-twin runtime proxy.

Compares SPPA modes on operational axes that matter in flight/desktop twins:
structure, triangle budget, build latency, evidence consumption, and lightness
versus neural image/text-to-3D generators. This is NOT a photoreal ranking.
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN_PATH = ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"
OUT_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"
FIG_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures"

# Reported from existing dual-input visual audit (real probes); used only as
# operational contrast, not as re-run neural numbers.
NEURAL_REFERENCE = {
    "biker": {"method": "TripoSR", "triangles": 22436, "gen_ms": 898.0},
    "tower": {"method": "TripoSR", "triangles": 24228, "gen_ms": 1030.0},
    "tractor": {"method": "TripoSR", "triangles": 36448, "gen_ms": 1350.0},
    "tractor_trailer": {"method": "TripoSR", "triangles": 27644, "gen_ms": 1200.0},
    "shap_e_biker": {"method": "Shap-E", "triangles": 16928, "gen_ms": 4440.0},
}

CASES = [
    {"label": "biker", "dims": {"length": 1.85, "width": 0.65, "height": 1.65}},
    {"label": "tower", "dims": {"length": 4.5, "width": 4.5, "height": 28.0}},
    {"label": "tractor", "dims": {"length": 3.9, "width": 2.1, "height": 2.5}},
    {"label": "tractor_trailer", "dims": {"length": 8.2, "width": 2.3, "height": 2.9}},
]


def load_gen():
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", GEN_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build_case(module, label: str, dims: dict | None, lod: str, evidence_channels: int):
    mesh = module.Mesh(lod=lod)
    t0 = time.perf_counter()
    if dims is None:
        meta = module.build_label_observed(mesh, label)
        mode = "tag_only_prior_dims"
    else:
        meta = module.build_label_observed(mesh, label, dims_m=dims)
        mode = "tag_plus_metric_dims"
    build_ms = (time.perf_counter() - t0) * 1000.0
    tris = mesh.triangle_count()
    parts = len(mesh.parts)
    neural = NEURAL_REFERENCE.get(label, {})
    score = module.score_use_case_sota(
        triangles=tris,
        build_ms=build_ms,
        parts=parts,
        evidence_channels=evidence_channels,
        has_update_contract=True,
        has_fallback=True,
        neural_triangles=neural.get("triangles"),
        neural_build_ms=neural.get("gen_ms"),
    )
    return {
        "label": label,
        "mode": mode,
        "lod": lod,
        "triangles": tris,
        "vertices": len(mesh.vertices),
        "parts": parts,
        "build_ms": round(build_ms, 3),
        "effective_dims_m": meta.get("effective_dims_m"),
        "metric_dims_source": meta.get("metric_dims_source"),
        "neural_reference": neural,
        "triangle_ratio_vs_neural": round(tris / neural["triangles"], 4) if neural.get("triangles") else None,
        "speedup_vs_neural": round(neural["gen_ms"] / max(build_ms, 1e-6), 1) if neural.get("gen_ms") else None,
        **score,
    }


def write_markdown(rows: list[dict], path: Path) -> None:
    lines = [
        "# SPPA use-case SOTA benchmark",
        "",
        "Operational score for UAV digital-twin **semantic runtime proxies**.",
        "Not a photoreal image-to-3D leaderboard.",
        "",
        "Virtues maximized: low triangles, millisecond build, role-labeled parts,",
        "evidence-aware dims, update/fallback contract, lightness vs neural generators.",
        "",
        "| Label | Mode | LOD | Tris | Parts | Build ms | vs neural tris | Speedup vs neural | Use-case score |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['label']} | {row['mode']} | {row['lod']} | {row['triangles']} | {row['parts']} | "
            f"{row['build_ms']:.2f} | {row.get('triangle_ratio_vs_neural')} | {row.get('speedup_vs_neural')} | "
            f"{row['use_case_sota_score']:.3f} |"
        )
    best = max(rows, key=lambda r: r["use_case_sota_score"])
    lines.extend(
        [
            "",
            f"Best row by use-case score: **{best['label']} / {best['mode']} / {best['lod']}** "
            f"({best['use_case_sota_score']:.3f}).",
            "",
            "Claim boundary: higher use-case score means better operational proxy under budget,",
            "not higher mesh beauty than Trellis/Hunyuan/TripoSR.",
            "",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_tex(rows: list[dict], path: Path) -> None:
    # Prefer metric-dims balanced rows for main table.
    selected = [r for r in rows if r["mode"] == "tag_plus_metric_dims" and r["lod"] == "balanced"]
    lines = [
        r"\begin{tabular}{@{}lrrrrr@{}}",
        r"\toprule",
        r"Case & Tris & Parts & Build ms & $\times$ lighter vs TripoSR & Use-case score \\",
        r"\midrule",
    ]
    for row in selected:
        lighter = None
        if row.get("triangle_ratio_vs_neural"):
            lighter = 1.0 / row["triangle_ratio_vs_neural"]
        lines.append(
            f"{row['label'].replace('_', r'\_')} & {row['triangles']} & {row['parts']} & "
            f"{row['build_ms']:.2f} & {lighter:.1f}$\\times$ & {row['use_case_sota_score']:.3f} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    module = load_gen()
    rows: list[dict] = []
    for case in CASES:
        label = case["label"]
        # tag-only balanced
        rows.append(build_case(module, label, None, "balanced", evidence_channels=1))
        # metric dims: balanced + ultra_light (use-case modes)
        rows.append(build_case(module, label, case["dims"], "balanced", evidence_channels=2))
        rows.append(build_case(module, label, case["dims"], "ultra_light", evidence_channels=2))
        rows.append(build_case(module, label, case["dims"], "high", evidence_channels=2))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "sppa-use-case-sota-v1",
        "claim_boundary": "Operational UAV digital-twin proxy ranking, not photoreal SOTA.",
        "virtues": [
            "role_labeled_parts",
            "millisecond_local_build",
            "sub_2k_triangle_budget",
            "metric_or_prior_dims",
            "update_contract",
            "conservative_fallback",
            "orders_of_magnitude_lighter_than_neural_generators",
        ],
        "rows": rows,
        "summary": {
            "mean_score_metric_balanced": round(
                sum(r["use_case_sota_score"] for r in rows if r["mode"] == "tag_plus_metric_dims" and r["lod"] == "balanced")
                / 4.0,
                4,
            ),
            "mean_triangles_metric_balanced": round(
                sum(r["triangles"] for r in rows if r["mode"] == "tag_plus_metric_dims" and r["lod"] == "balanced") / 4.0,
                1,
            ),
            "mean_build_ms_metric_balanced": round(
                sum(r["build_ms"] for r in rows if r["mode"] == "tag_plus_metric_dims" and r["lod"] == "balanced") / 4.0,
                3,
            ),
        },
    }
    json_path = OUT_DIR / "sppa_use_case_sota_benchmark.json"
    md_path = OUT_DIR / "sppa_use_case_sota_benchmark.md"
    tex_path = OUT_DIR / "sppa_use_case_sota_benchmark.tex"
    # Regression gates for ultra-fast / low-poly operational SOTA.
    balanced = [r for r in rows if r["mode"] == "tag_plus_metric_dims" and r["lod"] == "balanced"]
    ultra = [r for r in rows if r["mode"] == "tag_plus_metric_dims" and r["lod"] == "ultra_light"]
    gates = {
        "max_mean_triangles_balanced": 900,
        "max_mean_build_ms_balanced": 1.0,
        "max_any_triangles_balanced": 1600,
        "max_mean_triangles_ultra": 700,
        "max_mean_build_ms_ultra": 1.0,
        "min_mean_score_balanced": 0.75,
        "min_mean_lighter_vs_triposr": 15.0,
    }
    mean_tri_b = sum(r["triangles"] for r in balanced) / max(len(balanced), 1)
    mean_ms_b = sum(r["build_ms"] for r in balanced) / max(len(balanced), 1)
    mean_score_b = sum(r["use_case_sota_score"] for r in balanced) / max(len(balanced), 1)
    mean_tri_u = sum(r["triangles"] for r in ultra) / max(len(ultra), 1)
    mean_ms_u = sum(r["build_ms"] for r in ultra) / max(len(ultra), 1)
    light_vals = [1.0 / r["triangle_ratio_vs_neural"] for r in balanced if r.get("triangle_ratio_vs_neural")]
    mean_lighter = sum(light_vals) / max(len(light_vals), 1)
    failures = []
    if mean_tri_b > gates["max_mean_triangles_balanced"]:
        failures.append(f"mean_triangles_balanced {mean_tri_b:.1f} > {gates['max_mean_triangles_balanced']}")
    if mean_ms_b > gates["max_mean_build_ms_balanced"]:
        failures.append(f"mean_build_ms_balanced {mean_ms_b:.3f} > {gates['max_mean_build_ms_balanced']}")
    if any(r["triangles"] > gates["max_any_triangles_balanced"] for r in balanced):
        failures.append("a balanced proxy exceeds max_any_triangles_balanced")
    if mean_tri_u > gates["max_mean_triangles_ultra"]:
        failures.append(f"mean_triangles_ultra {mean_tri_u:.1f} > {gates['max_mean_triangles_ultra']}")
    if mean_ms_u > gates["max_mean_build_ms_ultra"]:
        failures.append(f"mean_build_ms_ultra {mean_ms_u:.3f} > {gates['max_mean_build_ms_ultra']}")
    if mean_score_b < gates["min_mean_score_balanced"]:
        failures.append(f"mean_score_balanced {mean_score_b:.3f} < {gates['min_mean_score_balanced']}")
    if mean_lighter < gates["min_mean_lighter_vs_triposr"]:
        failures.append(f"mean_lighter_vs_triposr {mean_lighter:.1f} < {gates['min_mean_lighter_vs_triposr']}")
    payload["gates"] = gates
    payload["gate_metrics"] = {
        "mean_triangles_balanced": round(mean_tri_b, 1),
        "mean_build_ms_balanced": round(mean_ms_b, 3),
        "mean_score_balanced": round(mean_score_b, 4),
        "mean_triangles_ultra": round(mean_tri_u, 1),
        "mean_build_ms_ultra": round(mean_ms_u, 3),
        "mean_lighter_vs_triposr": round(mean_lighter, 1),
    }
    payload["gate_status"] = "passed" if not failures else "failed"
    payload["gate_failures"] = failures

    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_markdown(rows, md_path)
    write_tex(rows, tex_path)
    print(
        json.dumps(
            {
                "json": str(json_path),
                "md": str(md_path),
                "tex": str(tex_path),
                "summary": payload["summary"],
                "gate_status": payload["gate_status"],
                "gate_metrics": payload["gate_metrics"],
                "gate_failures": failures,
            },
            indent=2,
        )
    )
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
