from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from bench_common import ROOT, emit, write_csv
from run_sppa_unified_real_inputs import (
    annotation_index,
    bbox_dict,
    detector_refined_semantic_label_for,
    image_cues_index,
    image_size,
    load_generator,
    observation_decision,
    observed_color_for,
    read_json,
    semantic_label_for,
    visual_metric_yaw_consistency_for,
    visual_part_evidence_for,
    world_pose,
)


DEFAULT_REPLAY_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "benchmarks"
    / "results"
    / "real_image_assumed_flight_replay.json"
)
DEFAULT_ANNOTATIONS_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_detection_reference"
    / "20260703_real_input_annotations"
    / "real_input_2d_annotations.json"
)
DEFAULT_IMAGE_CUES_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "benchmarks"
    / "results"
    / "sppa_agnostic_image_space_parts_probe.json"
)
DEFAULT_OUT_DIR = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_sota_benchmark"
    / "runs"
    / "20260705_sppa_input_mode_comparison"
)
DEFAULT_RESULTS_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"

MODE_ORDER = ("tag_only", "detector_metric", "detector_metric_visual")
MODE_LABELS = {
    "tag_only": "text/tag only",
    "detector_metric": "YOLOE + metric",
    "detector_metric_visual": "YOLOE + metric + visual",
}
MODE_CONTRACTS = {
    "tag_only": "Reviewed text tag only; no image, bbox, mask, metric replay, or visual cues.",
    "detector_metric": "Real YOLOE detector text plus declared metric replay/observation fusion; no visual part cues.",
    "detector_metric_visual": "Real YOLOE detector text plus declared metric replay, agnostic image-space primitive cues, and conservative observed material color.",
}


def csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_descriptor(row: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(row.get("descriptor_path") or ""))
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def dim_tuple(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        return (
            round(float(value.get("length")), 4),
            round(float(value.get("width")), 4),
            round(float(value.get("height")), 4),
        )
    except (TypeError, ValueError):
        return None


def dim_text(value: Any) -> str:
    dims = dim_tuple(value)
    if dims is None:
        return "n/a"
    return f"{dims[0]:.2f}x{dims[1]:.2f}x{dims[2]:.2f}"


def latex_escape(value: Any) -> str:
    text = str(value if value is not None else "")
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def latex_short_case(value: Any) -> str:
    return {"tractor_trailer": "tractor+trailer"}.get(str(value), str(value))


def latex_short_mode(value: Any) -> str:
    return {
        "tag_only": "text",
        "detector_metric": "det+metric",
        "detector_metric_visual": "det+metric+visual",
    }.get(str(value), str(value))


def latex_short_semantic(value: Any) -> str:
    return {
        "vertical_structure": "vertical",
        "farm_vehicle": "farm",
        "tractor_trailer": "tractor+trailer",
        "articulated_vehicle": "articulated",
    }.get(str(value), str(value))


def latex_short_dims(value: Any) -> str:
    dims = dim_tuple(value)
    if dims is None:
        return "-"
    return f"{dims[0]:.2f}/{dims[1]:.2f}/{dims[2]:.2f}"


def compact_source(source: Any) -> str:
    text = str(source or "")
    return {
        "semantic_prior_dims": "prior",
        "constraint_fused_vehicle_observation": "vehicle-fused",
        "constraint_fused_vertical_height": "height-fused",
        "accepted_vehicle_observation": "vehicle-accepted",
        "metric_dims_input": "metric-input",
    }.get(text, text.replace("_", "-") or "n/a")


def generate_mode(
    *,
    module: Any,
    unified_module: Any,
    row: dict[str, Any],
    ann: dict[str, Any] | None,
    image_cues: dict[str, dict[str, Any]],
    mode: str,
    out_root: Path,
) -> dict[str, Any]:
    case_label = str(row.get("case_id") or "unknown")
    width, height = image_size(ann)
    uncertainty = row.get("sppa_uncertainty") if isinstance(row.get("sppa_uncertainty"), dict) else None
    detector_refined: dict[str, Any] | None = None
    observation_fusion: dict[str, Any] | None = None
    dims = None
    bbox = None
    mask = None
    world = None
    yaw_deg = None
    visual_part_evidence = None
    visual_metric_yaw_consistency = None
    observed_color = None

    if mode == "tag_only":
        semantic_label, semantic_source = semantic_label_for(row, ann)
        confidence = 1.0
        prompt = f"{semantic_label} semantic tag only"
        semantic_text_source = semantic_source
        metric_dims_source_override = None
    else:
        semantic_label, semantic_source, detector_refined = detector_refined_semantic_label_for(row)
        confidence = float(row.get("detector_confidence") or 0.0)
        decision = observation_decision(module, row, semantic_label)
        use_observation = bool(decision.get("applied"))
        dims = decision.get("dims_m") if use_observation and isinstance(decision.get("dims_m"), dict) else None
        observation_fusion = decision if use_observation else None
        bbox = bbox_dict(row.get("bbox_xyxy")) if use_observation else None
        world = world_pose(row) if use_observation else None
        apply_image_geometry = use_observation and bool(decision.get("image_geometry_reliable"))
        mask = row.get("native_detector_mask") if apply_image_geometry else None
        yaw_deg = row.get("yaw_deg") if apply_image_geometry else None
        metric_dims_source_override = str(decision.get("source") or "") if use_observation else None
        prompt = f"{semantic_label} from YOLOE detector text plus declared metric observation"
        semantic_text_source = f"{semantic_source}+declared_metric_observation" if use_observation else semantic_source
        if mode == "detector_metric_visual":
            visual_part_evidence = visual_part_evidence_for(case_label, image_cues)
            visual_metric_yaw_consistency = visual_metric_yaw_consistency_for(row, ann, visual_part_evidence)
            observed_color = observed_color_for(row, ann, semantic_label) if use_observation else None
            prompt = f"{prompt} plus agnostic image-space primitive cues"
            semantic_text_source = f"{semantic_text_source}+agnostic_visual_cues+observed_color"
        if uncertainty is not None and use_observation:
            uncertainty = dict(uncertainty)
            uncertainty["observation_fusion"] = {
                key: value
                for key, value in decision.items()
                if key
                in {
                    "version",
                    "source",
                    "policy",
                    "quality",
                    "shape_low_confidence",
                    "raw_aspect",
                    "target_aspect_range",
                    "fusion_weight",
                    "fusion_reasons",
                    "image_geometry_reliable",
                }
            }

    payload = unified_module.emit_mesh(
        module=module,
        model_name=mode,
        case_label=case_label,
        semantic_label=semantic_label,
        semantic_text_source=semantic_text_source,
        prompt=prompt,
        out_root=out_root,
        confidence=confidence,
        dims_m=dims,
        bbox=bbox,
        mask=mask,
        world=world,
        yaw_deg=yaw_deg,
        image_width=width,
        image_height=height,
        observation_uncertainty=uncertainty,
        metric_dims_source_override=metric_dims_source_override,
        observation_fusion=observation_fusion,
        visual_part_evidence=visual_part_evidence,
        visual_metric_yaw_consistency=visual_metric_yaw_consistency,
        observed_color=observed_color,
    )
    descriptor = read_descriptor(payload)
    payload["mode_label"] = MODE_LABELS[mode]
    payload["mode_contract"] = MODE_CONTRACTS[mode]
    payload["mode_order"] = MODE_ORDER.index(mode)
    payload["detector_label"] = row.get("detector_label")
    payload["detector_confidence"] = row.get("detector_confidence")
    payload["observation_applied"] = bool(observation_fusion)
    payload["observation_gate"] = str((observation_fusion or {}).get("gate") or "none")
    payload["fused_metric_dims_m"] = dims
    payload["effective_dims_text"] = dim_text(payload.get("effective_dims_m"))
    payload["metric_dims_source_compact"] = compact_source(payload.get("metric_dims_source"))
    payload["visual_input_available"] = visual_part_evidence is not None
    payload["visual_metric_yaw_input_available"] = visual_metric_yaw_consistency is not None
    payload["topology_hash"] = descriptor.get("topology_hash")
    payload["descriptor_id"] = descriptor.get("descriptor_id")
    payload["runtime_llm_used"] = descriptor.get("resolver", {}).get("runtime_llm_used")
    payload["resolver_source"] = descriptor.get("resolver", {}).get("resolver_source")
    if detector_refined is not None:
        payload["detector_refined_sppa_tag"] = detector_refined.get("sppa_tag")
        payload["detector_refined_runtime_archetype"] = detector_refined.get("runtime_archetype_id")
        payload["detector_refined_rule"] = detector_refined.get("normalization_rule")
        payload["detector_refinement_applied"] = (detector_refined.get("observation_refinement") or {}).get("applied")
    return payload


def annotate_deltas(rows: list[dict[str, Any]]) -> None:
    by_case: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_case.setdefault(str(row.get("label")), {})[str(row.get("model"))] = row
    for case_rows in by_case.values():
        tag = case_rows.get("tag_only", {})
        metric = case_rows.get("detector_metric", {})
        tag_dims = dim_tuple(tag.get("effective_dims_m"))
        metric_dims = dim_tuple(metric.get("effective_dims_m"))
        tag_hash = tag.get("topology_hash")
        metric_hash = metric.get("topology_hash")
        for row in case_rows.values():
            dims = dim_tuple(row.get("effective_dims_m"))
            topology = row.get("topology_hash")
            row["dims_changed_vs_tag_only"] = dims != tag_dims
            row["topology_changed_vs_tag_only"] = bool(topology and tag_hash and topology != tag_hash)
            row["geometry_changed_vs_tag_only"] = row["dims_changed_vs_tag_only"] or row["topology_changed_vs_tag_only"]
            row["dims_changed_vs_detector_metric"] = dims != metric_dims
            row["topology_changed_vs_detector_metric"] = bool(topology and metric_hash and topology != metric_hash)
            row["geometry_changed_vs_detector_metric"] = (
                row["dims_changed_vs_detector_metric"] or row["topology_changed_vs_detector_metric"]
            )


def build_report(rows: list[dict[str, Any]], out_json: Path, out_md: Path, out_tex: Path) -> None:
    annotate_deltas(rows)
    summary = {
        "schema": "SPPA-INPUT-MODE-COMPARISON-0.1",
        "claim_boundary": (
            "This compares the same deterministic SPPA generator under three input contracts. "
            "Text-only uses a reviewed tag and no image. Detector modes use real YOLOE text plus declared "
            "metric replay; the visual mode adds agnostic image-space cues. It is not 3D ground truth, "
            "not measured flight localization, and not a visual SOTA leaderboard."
        ),
        "case_count": len({row.get("label") for row in rows}),
        "mode_count": len(MODE_ORDER),
        "row_count": len(rows),
        "visual_rows": sum(1 for row in rows if row.get("model") == "detector_metric_visual"),
        "visual_rows_with_evidence_applied": sum(
            1
            for row in rows
            if row.get("model") == "detector_metric_visual" and row.get("visual_part_evidence_applied")
        ),
        "visual_rows_with_shape_conditioning": sum(
            1
            for row in rows
            if row.get("model") == "detector_metric_visual" and row.get("visual_shape_conditioning_applied")
        ),
        "visual_rows_with_geometry_delta_vs_metric": sum(
            1
            for row in rows
            if row.get("model") == "detector_metric_visual" and row.get("geometry_changed_vs_detector_metric")
        ),
        "detector_metric_rows_with_geometry_delta_vs_text": sum(
            1
            for row in rows
            if row.get("model") == "detector_metric" and row.get("geometry_changed_vs_tag_only")
        ),
        "max_wall_ms": round(max(float(row.get("wall_sec") or 0.0) for row in rows) * 1000.0, 3) if rows else 0.0,
        "max_triangles": max(int(row.get("triangles") or 0) for row in rows) if rows else 0,
        "max_descriptor_bytes": max(int(row.get("descriptor_bytes") or 0) for row in rows) if rows else 0,
        "rows": rows,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    md_lines = [
        "# SPPA Input Mode Comparison",
        "",
        summary["claim_boundary"],
        "",
        f"- Cases: {summary['case_count']}",
        f"- Visual rows with applied visual evidence: {summary['visual_rows_with_evidence_applied']}/{summary['visual_rows']}",
        f"- Visual rows with shape conditioning: {summary['visual_rows_with_shape_conditioning']}/{summary['visual_rows']}",
        f"- Visual rows with geometry delta vs detector+metric: {summary['visual_rows_with_geometry_delta_vs_metric']}/{summary['visual_rows']}",
        f"- Detector+metric rows with geometry delta vs text-only: {summary['detector_metric_rows_with_geometry_delta_vs_text']}/{summary['case_count']}",
        f"- Max wall time: {summary['max_wall_ms']:.3f} ms",
        f"- Max triangles: {summary['max_triangles']}",
        f"- Max descriptor bytes: {summary['max_descriptor_bytes']}",
        "",
        "| Case | Mode | Semantic label | Scale source | Dims m | Visual shape | Geom delta vs text | Geom delta vs metric | Tris | Wall ms |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(rows, key=lambda item: (str(item.get("label")), int(item.get("mode_order", 0)))):
        md_lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("label")),
                    str(row.get("mode_label")),
                    str(row.get("semantic_label")),
                    str(row.get("metric_dims_source_compact")),
                    str(row.get("effective_dims_text")),
                    str(bool(row.get("visual_shape_conditioning_applied"))),
                    str(bool(row.get("geometry_changed_vs_tag_only"))),
                    str(bool(row.get("geometry_changed_vs_detector_metric"))),
                    str(row.get("triangles")),
                    f"{float(row.get('wall_sec') or 0.0) * 1000.0:.3f}",
                ]
            )
            + " |"
        )
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    tex_lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\tiny",
        r"\setlength{\tabcolsep}{2pt}",
        r"\renewcommand{\arraystretch}{1.06}",
        r"\caption{SPPA input-mode comparison. All rows call the same deterministic generator. Text-only uses no image; detector rows use real YOLOE text with declared metric replay; the visual row adds agnostic image-space primitive cues that may condition existing roles.}",
        r"\label{tab:sppa-input-mode-comparison}",
        r"\begin{tabular}{@{}llllrcr@{}}",
        r"\toprule",
        r"Case & Mode & Semantic & Dims L/W/H (m) & Visual tris & $\Delta$ vs metric & Tris \\",
        r"\midrule",
    ]
    for row in sorted(rows, key=lambda item: (str(item.get("label")), int(item.get("mode_order", 0)))):
        added_visual = row.get("visual_shape_conditioning_added_triangles") if row.get("visual_shape_conditioning_applied") else "-"
        delta_metric = "yes" if row.get("geometry_changed_vs_detector_metric") else "no"
        tex_lines.append(
            " & ".join(
                [
                    latex_escape(latex_short_case(row.get("label"))),
                    latex_escape(latex_short_mode(row.get("model"))),
                    latex_escape(latex_short_semantic(row.get("semantic_label"))),
                    latex_escape(latex_short_dims(row.get("effective_dims_m"))),
                    latex_escape(added_visual),
                    latex_escape(delta_metric),
                    latex_escape(row.get("triangles")),
                ]
            )
            + r" \\"
        )
    tex_lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ]
    )
    out_tex.write_text("\n".join(tex_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare SPPA text-only, detector-metric, and detector-metric-visual input modes.")
    parser.add_argument("--replay-json", type=Path, default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--annotations-json", type=Path, default=DEFAULT_ANNOTATIONS_JSON)
    parser.add_argument("--image-cues-json", type=Path, default=DEFAULT_IMAGE_CUES_JSON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument(
        "--generator",
        type=Path,
        default=ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py",
    )
    args = parser.parse_args()

    replay_json = args.replay_json if args.replay_json.is_absolute() else ROOT / args.replay_json
    annotations_json = args.annotations_json if args.annotations_json.is_absolute() else ROOT / args.annotations_json
    image_cues_json = args.image_cues_json if args.image_cues_json.is_absolute() else ROOT / args.image_cues_json
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    results_dir = args.results_dir if args.results_dir.is_absolute() else ROOT / args.results_dir
    generator = args.generator if args.generator.is_absolute() else ROOT / args.generator
    output_dir.mkdir(parents=True, exist_ok=True)

    # Importing the unified module directly keeps this comparison on the same mesh emission path.
    import run_sppa_unified_real_inputs as unified_module

    module = load_generator(generator)
    replay = read_json(replay_json)
    annotations = annotation_index(annotations_json)
    image_cues = image_cues_index(image_cues_json)
    rows: list[dict[str, Any]] = []
    emit("SPPA_INPUT_MODE_RUN", {"modes": list(MODE_ORDER), "output_dir": str(output_dir)})
    for row in replay.get("rows", []):
        case_label = str(row.get("case_id") or "unknown")
        ann = annotations.get(case_label)
        for mode in MODE_ORDER:
            payload = generate_mode(
                module=module,
                unified_module=unified_module,
                row=row,
                ann=ann,
                image_cues=image_cues,
                mode=mode,
                out_root=output_dir,
            )
            rows.append(payload)
            emit("SPPA_INPUT_MODE_OBJECT", payload)

    annotate_deltas(rows)
    write_csv(output_dir / "objects.csv", rows)
    (output_dir / "SPPA_INPUT_MODE_README.md").write_text(
        "# SPPA Input Mode Comparison\n\n"
        "This run generates the same four real-image stress cases under three input contracts: "
        "reviewed text/tag only, YOLOE detector text plus declared metric observation, and "
        "YOLOE detector text plus declared metric observation plus agnostic visual primitive cues.\n",
        encoding="utf-8",
    )
    build_report(
        rows,
        results_dir / "sppa_input_mode_comparison.json",
        results_dir / "sppa_input_mode_comparison.md",
        results_dir / "sppa_input_mode_comparison.tex",
    )


if __name__ == "__main__":
    main()
