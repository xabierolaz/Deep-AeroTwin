from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


MODEL_INFO: dict[str, dict[str, Any]] = {
    "sppa": {
        "display": "SPPA",
        "input": "normalized tag / gated observation",
        "deterministic_contract": True,
        "track_updateable_actor": True,
        "uses_gpu_inference": False,
        "notes": "Runtime semantic proxy with deterministic descriptor and observation gating.",
    },
    "triposr_warm": {
        "display": "TripoSR warm",
        "input": "clean RGBA proxy crop",
        "deterministic_contract": False,
        "track_updateable_actor": False,
        "uses_gpu_inference": True,
        "notes": "Fast image-conditioned mesh generator.",
    },
    "hunyuan3d_2mini_turbo_shape": {
        "display": "Hunyuan3D-2mini Turbo",
        "input": "clean RGBA proxy crop",
        "deterministic_contract": False,
        "track_updateable_actor": False,
        "uses_gpu_inference": True,
        "notes": "High-density image-conditioned mesh generator.",
    },
    "shap_e_text_k16": {
        "display": "Shap-E text K=16",
        "input": "prompt/tag",
        "deterministic_contract": False,
        "track_updateable_actor": False,
        "uses_gpu_inference": True,
        "notes": "Legacy text-conditioned mesh generator in speed-oriented settings.",
    },
    "point_e_text_sdf32": {
        "display": "Point-E text + SDF32",
        "input": "prompt/tag",
        "deterministic_contract": False,
        "track_updateable_actor": False,
        "uses_gpu_inference": True,
        "notes": "Legacy point-cloud generator with SDF mesh conversion.",
    },
}


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def as_float(row: dict[str, str], key: str) -> float:
    value = row.get(key) or "0"
    return float(value)


def summarize_model(model: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    wall = [as_float(row, "wall_sec") for row in rows]
    triangles = [int(as_float(row, "triangles")) for row in rows]
    reserved = [as_float(row, "torch_peak_reserved_mb") for row in rows]
    info = MODEL_INFO.get(model, {})
    median_wall_s = statistics.median(wall)
    max_triangles = max(triangles)
    max_reserved_mb = max(reserved)

    latency_pass = median_wall_s <= 1.0 / 30.0
    geometry_pass = max_triangles <= 5_000
    vram_pass = max_reserved_mb <= 1_024.0
    no_gpu_pass = not bool(info.get("uses_gpu_inference", True))
    contract_pass = bool(info.get("deterministic_contract", False))
    actor_pass = bool(info.get("track_updateable_actor", False))
    score = sum([latency_pass, geometry_pass, vram_pass, no_gpu_pass, contract_pass, actor_pass])

    return {
        "method": info.get("display", model),
        "model_key": model,
        "input": info.get("input", "unknown"),
        "n": len(rows),
        "median_wall_s": median_wall_s,
        "min_wall_s": min(wall),
        "max_wall_s": max(wall),
        "median_triangles": int(statistics.median(triangles)),
        "min_triangles": min(triangles),
        "max_triangles": max_triangles,
        "max_reserved_mb": max_reserved_mb,
        "latency_30hz_pass": latency_pass,
        "triangle_budget_pass": geometry_pass,
        "vram_1gb_pass": vram_pass,
        "no_gpu_inference_pass": no_gpu_pass,
        "deterministic_contract_pass": contract_pass,
        "track_updateable_actor_pass": actor_pass,
        "task_fit_score_0_6": score,
        "notes": info.get("notes", ""),
    }


def collect(run_dirs: list[Path]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for run_dir in run_dirs:
        for row in read_rows(run_dir / "objects.csv"):
            if row.get("status") != "ok":
                continue
            model = row.get("model", "")
            if model not in MODEL_INFO:
                continue
            grouped.setdefault(model, []).append(row)
    rows = [summarize_model(model, model_rows) for model, model_rows in grouped.items()]
    return sorted(rows, key=lambda row: (-row["task_fit_score_0_6"], row["median_wall_s"], row["method"]))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def yn(value: bool) -> str:
    return "Y" if value else "N"


def tex_escape(text: str) -> str:
    return (
        text.replace("\\", "\\textbackslash{}")
        .replace("&", "\\&")
        .replace("%", "\\%")
        .replace("_", "\\_")
        .replace("#", "\\#")
    )


def write_tex(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    criteria = [
        ("lat.", "latency_30hz_pass"),
        ("tris", "triangle_budget_pass"),
        ("mem", "vram_1gb_pass"),
        ("GPU", "no_gpu_inference_pass"),
        ("contract", "deterministic_contract_pass"),
        ("update", "track_updateable_actor_pass"),
    ]
    lines = [
        "% Auto-generated by tools/sppa_sota_benchmark/make_sppa_task_fit_ranking.py",
        "\\begin{table}[h]",
        "\\centering",
        "\\scriptsize",
        "\\setlength{\\tabcolsep}{4pt}",
        "\\renewcommand{\\arraystretch}{1.08}",
        "\\caption{SPPA runtime task-fit ranking derived from the local July 2026 generator stress runs. This ranking is for the UAV/VR semantic-proxy contract, not for image-to-3D visual SOTA. The six score criteria are: median generation below 33 ms, maximum mesh below 5k triangles, maximum torch reserved memory below 1 GB, no GPU inference, deterministic descriptor contract, and track-updateable actor semantics.}",
        "\\label{tab:sppa-task-fit-ranking}",
        "\\begin{tabularx}{\\linewidth}{@{}L{0.24\\linewidth}L{0.18\\linewidth}r r r r Y@{}}",
        "\\toprule",
        "Method & Input & Score & Wall & Max tris & VRAM & Failed criteria \\\\",
        "\\midrule",
    ]
    for row in rows:
        failed = [label for label, key in criteria if not row[key]]
        lines.append(
            " & ".join(
                [
                    tex_escape(row["method"]),
                    tex_escape(row["input"]),
                    f"{row['task_fit_score_0_6']}/6",
                    f"{row['median_wall_s']:.4f}s",
                    f"{row['max_triangles']:,}",
                    f"{row['max_reserved_mb']:.0f}MB",
                    tex_escape(", ".join(failed) if failed else "-"),
                ]
            )
            + " \\\\"
        )
    lines += [
        "\\bottomrule",
        "\\end{tabularx}",
        "\\end{table}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_md(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# SPPA Runtime Task-Fit Ranking",
        "",
        "This is a local systems ranking for the SPPA UAV/VR runtime contract. It is not an image-to-3D SOTA ranking.",
        "",
        "Pass criteria:",
        "",
        "- latency: median wall time <= 33 ms;",
        "- triangles: maximum mesh size <= 5,000 triangles;",
        "- memory: maximum torch reserved memory <= 1 GB;",
        "- no GPU: no runtime neural GPU inference;",
        "- contract: deterministic SPPA descriptor/update contract;",
        "- update: track-updateable actor semantics.",
        "",
        "| Rank | Method | Score | Input | Median wall | Max tris | Max VRAM | Notes |",
        "|---:|---|---:|---|---:|---:|---:|---|",
    ]
    for rank, row in enumerate(rows, start=1):
        lines.append(
            f"| {rank} | {row['method']} | {row['task_fit_score_0_6']}/6 | {row['input']} | "
            f"{row['median_wall_s']:.4f}s | {row['max_triangles']} | {row['max_reserved_mb']:.0f}MB | {row['notes']} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SPPA runtime task-fit ranking from local generator stress runs.")
    parser.add_argument(
        "--run-dir",
        action="append",
        type=Path,
        required=True,
        help="Run directory containing objects.csv. Pass multiple times.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "ranking" / "20260703_task_fit",
    )
    parser.add_argument(
        "--paper-results-dir",
        type=Path,
        default=ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results",
    )
    args = parser.parse_args()

    rows = collect([path if path.is_absolute() else ROOT / path for path in args.run_dir])
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    paper_results_dir = args.paper_results_dir if args.paper_results_dir.is_absolute() else ROOT / args.paper_results_dir

    write_csv(out_dir / "sppa_task_fit_ranking.csv", rows)
    write_tex(out_dir / "sppa_task_fit_ranking.tex", rows)
    write_md(out_dir / "sppa_task_fit_ranking.md", rows)
    (out_dir / "sppa_task_fit_ranking.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")

    write_csv(paper_results_dir / "sppa_task_fit_ranking.csv", rows)
    write_tex(paper_results_dir / "sppa_task_fit_ranking.tex", rows)
    write_md(paper_results_dir / "sppa_task_fit_ranking.md", rows)
    print(out_dir / "sppa_task_fit_ranking.csv")
    print(paper_results_dir / "sppa_task_fit_ranking.tex")


if __name__ == "__main__":
    main()
