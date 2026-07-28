from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from bench_common import ROOT, read_objects, write_csv


RUN_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260705_sppa_input_mode_comparison"
OBJECTS_CSV = RUN_DIR / "objects.csv"
RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"
FIGURES_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures"

BUDGETS = {
    "wall_ms": 10.0,
    "triangles": 2500,
    "descriptor_bytes": 32768,
}

MODE_ORDER = {
    "tag_only": 0,
    "detector_metric": 1,
    "detector_metric_visual": 2,
}

MODE_SHORT = {
    "tag_only": "text",
    "detector_metric": "det+metric",
    "detector_metric_visual": "det+metric+visual",
}

CLAIM_BOUNDARY = (
    "Evidence-channel coverage measures which SPPA inputs were actually consumed "
    "under each contract. It is not a 3D quality score, not a human-preference "
    "score, and not a visual image-to-3D SOTA ranking."
)


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y"}


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def yes(value: bool) -> str:
    return "yes" if value else "-"


def evidence_flags(row: dict[str, Any]) -> dict[str, Any]:
    semantic = (
        row.get("status") == "ok"
        and bool(row.get("semantic_label"))
        and not as_bool(row.get("runtime_llm_used"))
    )
    metric = (
        as_bool(row.get("observation_applied"))
        and str(row.get("descriptor_scale_source") or row.get("metric_dims_source") or "")
        not in {"", "semantic_prior_dims"}
    )
    visual = (
        as_bool(row.get("visual_part_evidence_applied"))
        and as_bool(row.get("visual_shape_conditioning_applied"))
        and as_int(row.get("visual_shape_conditioning_added_triangles")) > 0
    )
    yaw = (
        as_bool(row.get("visual_metric_yaw_consistency_applied"))
        and str(row.get("visual_metric_yaw_agreement") or "") in {"aligned", "weakly_aligned"}
    )
    material = as_bool(row.get("observed_color_applied"))
    wall_ms = as_float(row.get("wall_sec")) * 1000.0
    triangles = as_int(row.get("triangles"))
    descriptor_bytes = as_int(row.get("descriptor_bytes"))
    budget = (
        wall_ms <= BUDGETS["wall_ms"]
        and triangles <= BUDGETS["triangles"]
        and descriptor_bytes <= BUDGETS["descriptor_bytes"]
    )
    channels = {
        "semantic": semantic,
        "metric": metric,
        "visual": visual,
        "yaw": yaw,
        "material": material,
    }
    return {
        **channels,
        "active_evidence_channels": sum(1 for value in channels.values() if value),
        "budget_pass": budget,
        "wall_ms": round(wall_ms, 3),
        "triangles": triangles,
        "descriptor_bytes": descriptor_bytes,
    }


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in read_objects(OBJECTS_CSV):
        flags = evidence_flags(row)
        rows.append(
            {
                "case": row["label"],
                "mode": row["model"],
                "mode_short": MODE_SHORT.get(row["model"], row["model"]),
                "mode_order": MODE_ORDER.get(row["model"], 99),
                "semantic": row.get("semantic_label", ""),
                "semantic_channel": flags["semantic"],
                "metric_channel": flags["metric"],
                "visual_channel": flags["visual"],
                "yaw_channel": flags["yaw"],
                "material_channel": flags["material"],
                "active_evidence_channels": flags["active_evidence_channels"],
                "budget_pass": flags["budget_pass"],
                "wall_ms": flags["wall_ms"],
                "triangles": flags["triangles"],
                "descriptor_bytes": flags["descriptor_bytes"],
                "visual_added_triangles": as_int(row.get("visual_shape_conditioning_added_triangles")),
                "yaw_agreement": row.get("visual_metric_yaw_agreement") or "",
                "observed_color_confidence": row.get("observed_color_confidence") or "",
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )
    rows.sort(key=lambda item: (item["case"], item["mode_order"]))
    return rows


def write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    payload = {
        "schema": "SPPA-EVIDENCE-CHANNEL-COVERAGE-0.1",
        "run_dir": str(RUN_DIR),
        "claim_boundary": CLAIM_BOUNDARY,
        "budgets": BUDGETS,
        "rows": rows,
        "summary": summarize(rows),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_mode: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_mode.setdefault(row["mode"], []).append(row)
    return {
        mode: {
            "rows": len(items),
            "mean_active_evidence_channels": round(
                sum(int(item["active_evidence_channels"]) for item in items) / max(1, len(items)), 3
            ),
            "budget_pass_rows": sum(1 for item in items if item["budget_pass"]),
            "visual_channel_rows": sum(1 for item in items if item["visual_channel"]),
            "yaw_channel_rows": sum(1 for item in items if item["yaw_channel"]),
            "material_channel_rows": sum(1 for item in items if item["material_channel"]),
        }
        for mode, items in sorted(by_mode.items(), key=lambda pair: MODE_ORDER.get(pair[0], 99))
    }


def write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# SPPA Evidence-Channel Coverage",
        "",
        CLAIM_BOUNDARY,
        "",
        "| Case | Mode | Semantic | Metric | Visual | Yaw | Material | Channels | Budget | Wall time (ms) | Tris | Descriptor B |",
        "|---|---|---|---|---|---|---|---:|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {case} | {mode_short} | {semantic_channel} | {metric_channel} | {visual_channel} | "
            "{yaw_channel} | {material_channel} | {active_evidence_channels} | {budget_pass} | "
            "{wall_ms:.3f} | {triangles} | {descriptor_bytes} |".format(
                **{
                    **row,
                    "semantic_channel": yes(bool(row["semantic_channel"])),
                    "metric_channel": yes(bool(row["metric_channel"])),
                    "visual_channel": yes(bool(row["visual_channel"])),
                    "yaw_channel": yes(bool(row["yaw_channel"])),
                    "material_channel": yes(bool(row["material_channel"])),
                    "budget_pass": "pass" if row["budget_pass"] else "fail",
                }
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def tex_bool(value: bool) -> str:
    return "yes" if value else "--"


def escape_tex(value: Any) -> str:
    text = str(value)
    return text.replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("&", r"\&")


def write_tex(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\renewcommand{\arraystretch}{1.05}",
        r"\caption{SPPA evidence-channel coverage for the real input-mode ablation. The count reports which bounded evidence channels are consumed by the same SPPA generator; it is not a 3D quality score or visual SOTA ranking. Wall time is reported in milliseconds.}",
        r"\label{tab:sppa-evidence-channel-coverage}",
        r"\begin{tabular}{@{}lllcccccclrr@{}}",
        r"\toprule",
        r"Case & Mode & Semantic & Sem. & Metric & Visual & Yaw & Mat. & Ch. & Budget & Wall (ms) & Tris \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            "{case} & {mode} & {semantic} & {sem} & {metric} & {visual} & {yaw} & {mat} & {channels} & {budget} & {wall:.1f} & {tris} \\\\".format(
                case=escape_tex(row["case"]),
                mode=escape_tex(row["mode_short"]),
                semantic=escape_tex(row["semantic"]),
                sem=tex_bool(bool(row["semantic_channel"])),
                metric=tex_bool(bool(row["metric_channel"])),
                visual=tex_bool(bool(row["visual_channel"])),
                yaw=tex_bool(bool(row["yaw_channel"])),
                mat=tex_bool(bool(row["material_channel"])),
                channels=row["active_evidence_channels"],
                budget="pass" if row["budget_pass"] else "fail",
                wall=float(row["wall_ms"]),
                tris=row["triangles"],
            )
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_plot(path: Path, rows: list[dict[str, Any]]) -> None:
    cases = []
    for row in rows:
        if row["case"] not in cases:
            cases.append(row["case"])
    modes = ["tag_only", "detector_metric", "detector_metric_visual"]
    colors = {
        "tag_only": "#8b8f98",
        "detector_metric": "#4778b3",
        "detector_metric_visual": "#2f9e6e",
    }
    fig, ax = plt.subplots(figsize=(10.5, 4.6), dpi=160)
    width = 0.24
    x_positions = list(range(len(cases)))
    by_key = {(row["case"], row["mode"]): row for row in rows}
    for idx, mode in enumerate(modes):
        xs = [x + (idx - 1) * width for x in x_positions]
        values = [by_key[(case, mode)]["active_evidence_channels"] for case in cases]
        ax.bar(xs, values, width=width, label=MODE_SHORT[mode], color=colors[mode])
        for x, value in zip(xs, values):
            ax.text(x, value + 0.05, str(value), ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x_positions)
    ax.set_xticklabels([case.replace("_", "+") for case in cases], fontsize=9)
    ax.set_ylabel("active bounded evidence channels")
    ax.set_ylim(0, 5.6)
    ax.set_yticks([0, 1, 2, 3, 4, 5])
    ax.grid(axis="y", color="#dddddd", linewidth=0.7)
    ax.legend(loc="upper left", ncol=3, frameon=False)
    ax.set_title("SPPA evidence-channel coverage, not 3D quality")
    fig.text(
        0.01,
        0.01,
        "Channels: semantic normalizer, metric replay, visual role cues, yaw gate, observed material. "
        "All shown rows pass the lightweight runtime budget.",
        fontsize=8,
        color="#444444",
    )
    fig.tight_layout(rect=(0.0, 0.06, 1.0, 1.0))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def main() -> None:
    rows = build_rows()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(RESULTS_DIR / "sppa_evidence_channel_coverage.csv", rows)
    write_json(RESULTS_DIR / "sppa_evidence_channel_coverage.json", rows)
    write_markdown(RESULTS_DIR / "sppa_evidence_channel_coverage.md", rows)
    write_tex(RESULTS_DIR / "sppa_evidence_channel_coverage.tex", rows)
    write_plot(FIGURES_DIR / "sppa_evidence_channel_coverage.png", rows)
    print(json.dumps({"rows": len(rows), "summary": summarize(rows)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
