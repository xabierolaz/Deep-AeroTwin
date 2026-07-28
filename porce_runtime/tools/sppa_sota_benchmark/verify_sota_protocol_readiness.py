#!/usr/bin/env python
"""Verify the honest publication claim posture for SPPA comparisons."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROTOCOL = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "protocols" / "sppa_sota_protocol_v01.json"
DEFAULT_JSON_OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sota_protocol_readiness.json"
DEFAULT_MD_OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sota_protocol_readiness.md"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def as_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def provenance_summary(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "exists": False,
            "items": 0,
            "candidate_real_inputs": 0,
            "candidate_real_bbox_items": 0,
            "candidate_real_mask_items": 0,
            "candidate_real_reference_mesh_items": 0,
            "ground_truth_items": 0,
            "detector_crop_items": 0,
            "mask_items": 0,
            "reference_mesh_items": 0,
            "all_items_are_gt_with_reference": False,
        }
    data = read_json(path)
    items = list(data.get("items", []))
    candidates = list(data.get("candidate_real_inputs", []))
    gt_items = [item for item in items if item.get("is_ground_truth") is True]
    reference_items = [
        item
        for item in items
        if item.get("has_mask") is True or item.get("has_reference_mesh") is True
    ]
    return {
        "exists": True,
        "items": len(items),
        "candidate_real_inputs": len(candidates),
        "candidate_real_bbox_items": sum(1 for item in candidates if item.get("has_bbox") is True),
        "candidate_real_mask_items": sum(1 for item in candidates if item.get("has_mask") is True),
        "candidate_real_reference_mesh_items": sum(1 for item in candidates if item.get("has_reference_mesh") is True),
        "ground_truth_items": len(gt_items),
        "detector_crop_items": sum(1 for item in items if item.get("source_type") == "detector_crop"),
        "mask_items": sum(1 for item in items if item.get("has_mask") is True),
        "reference_mesh_items": sum(1 for item in items if item.get("has_reference_mesh") is True),
        "all_items_are_gt_with_reference": bool(items) and len(gt_items) == len(items) and len(reference_items) == len(items),
    }


def task_fit_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "rows": 0, "methods": []}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return {
        "exists": True,
        "rows": len(rows),
        "methods": [row.get("model_key") or row.get("method") for row in rows],
    }


def input_set_status(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in protocol.get("input_sets", []):
        manifest_path = as_path(item.get("manifest"))
        figure_path = as_path(item.get("paper_figure"))
        summary = provenance_summary(manifest_path)
        rows.append(
            {
                "id": item.get("id"),
                "declared_status": item.get("status"),
                "can_be_sota_input_set": item.get("can_be_sota_input_set") is True,
                "manifest": rel(manifest_path) if manifest_path else None,
                "manifest_exists": bool(manifest_path and manifest_path.exists()),
        "paper_figure": rel(figure_path) if figure_path else None,
        "paper_figure_exists": bool(figure_path and figure_path.exists()),
        "annotation_manifest": item.get("annotation_manifest"),
        "annotation_manifest_exists": bool(as_path(item.get("annotation_manifest")) and as_path(item.get("annotation_manifest")).exists()),
        "minimum_cases": item.get("minimum_cases"),
                "provenance": summary,
                "why_not": item.get("why_not"),
            }
        )
    return rows


def method_status(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for method in protocol.get("method_registry", []):
        local_status = str(method.get("local_status", "unknown"))
        has_successful_local_run = local_status.startswith("run_on_")
        rows.append(
            {
                "id": method.get("id"),
                "role": method.get("role"),
                "required_for_sota_protocol": method.get("required_for_sota_protocol") is True,
                "local_status": local_status,
                "has_successful_local_run": has_successful_local_run,
                "notes": method.get("notes"),
            }
        )
    return rows


def metric_status(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for metric in protocol.get("required_metric_artifacts", []):
        artifact_path = as_path(metric.get("artifact"))
        declared_status = str(metric.get("status", "unknown"))
        rows.append(
            {
                "id": metric.get("id"),
                "declared_status": declared_status,
                "artifact": rel(artifact_path) if artifact_path else None,
                "artifact_exists": bool(artifact_path and artifact_path.exists()),
                "acceptable_metrics": metric.get("acceptable_metrics", []),
            }
        )
    return rows


def build_requirements(
    inputs: list[dict[str, Any]],
    methods: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    task_fit: dict[str, Any],
) -> list[dict[str, str]]:
    requirements: list[dict[str, str]] = []

    def add(key: str, status: str, evidence: str, missing: str) -> None:
        requirements.append({"key": key, "status": status, "evidence": evidence, "missing": missing})

    sota_inputs = [
        row
        for row in inputs
        if row["can_be_sota_input_set"]
        and row["manifest_exists"]
        and row["provenance"]["all_items_are_gt_with_reference"]
        and row["provenance"]["items"] >= int(row.get("minimum_cases") or 0)
    ]
    add(
        "frozen_gt_input_set",
        "complete" if sota_inputs else "missing",
        f"{len(sota_inputs)} input set(s) currently satisfy minimum cases + GT/reference manifest.",
        "Create or import the public/recorded GT manifest with enough cases and per-item masks, footprints, reference meshes, or approved preference tasks.",
    )

    current_proxy = next((row for row in inputs if row["id"] == "current_six_case_proxy_grid"), None)
    current_prov = current_proxy["provenance"] if current_proxy else {}
    add(
        "first_row_ground_truth",
        "complete" if current_prov.get("all_items_are_gt_with_reference") else "missing",
        (
            f"current_grid_items={current_prov.get('items', 0)}, "
            f"gt={current_prov.get('ground_truth_items', 0)}, "
            f"masks={current_prov.get('mask_items', 0)}, "
            f"reference_meshes={current_prov.get('reference_mesh_items', 0)}"
        ),
        "Do not label the first row as GT until every displayed item is annotated/reference evidence.",
    )

    required_methods = [row for row in methods if row["required_for_sota_protocol"]]
    successful_required = [row for row in required_methods if row["has_successful_local_run"]]
    missing_required = [row["id"] for row in required_methods if not row["has_successful_local_run"]]
    add(
        "required_method_outputs",
        "complete" if len(successful_required) == len(required_methods) and required_methods else "partial",
        f"{len(successful_required)}/{len(required_methods)} required methods have successful local runs; missing_or_unusable={missing_required}.",
        "Run the remaining contemporary methods on the same frozen input set or document defensible exclusions.",
    )

    missing_metric_artifacts = [
        row["id"]
        for row in metrics
        if row["id"] != "runtime_cost_metrics" and not row["artifact_exists"]
    ]
    add(
        "quality_metrics",
        "complete" if not missing_metric_artifacts else "missing",
        f"missing_quality_metric_artifacts={missing_metric_artifacts}.",
        "Add reference geometry, image-alignment, and/or human/task-preference metric artifacts before ranking quality.",
    )

    add(
        "runtime_cost_metrics",
        "partial" if task_fit["exists"] and task_fit["rows"] > 0 else "missing",
        f"historical_excluded_task_fit_rows={task_fit['rows']}, methods={task_fit['methods']}.",
        "The historical pass/fail ranking is circular and excluded. Retain raw runtime/cost measurements only as provenance.",
    )

    real_inputs = next(
        (row for row in inputs if row["id"] in {"user_real_input_probes", "user_real_biker_tower_probes"}),
        None,
    )
    real_prov = real_inputs["provenance"] if real_inputs else {}
    add(
        "detector_tag_gt_separation",
        "partial" if real_prov.get("candidate_real_inputs", 0) > 0 else "missing",
        (
            f"candidate_real_inputs={real_prov.get('candidate_real_inputs', 0)}, "
            f"candidate_real_bbox_items={real_prov.get('candidate_real_bbox_items', 0)}, "
            f"real_probe_gt={real_prov.get('ground_truth_items', 0)}, "
            f"detector_crop_items={real_prov.get('detector_crop_items', 0)}."
        ),
        "Promote real probes only after storing detector boxes/masks/confidences separately from reviewed tags and GT references.",
    )

    return requirements


def build_claim_posture(
    *,
    can_claim_image_to_3d_leaderboard: bool,
    can_claim_runtime_task_fit: bool,
    status_counts: dict[str, int],
) -> dict[str, Any]:
    if can_claim_image_to_3d_leaderboard:
        headline = "image_to_3d_sota_leaderboard_ready"
        paper_position = (
            "The evidence is sufficient for a full image-to-3D leaderboard claim, "
            "provided the paper reports the frozen input set, shared metrics, and all method outputs."
        )
    elif can_claim_runtime_task_fit:
        headline = "ambitious_bounded_systems_claim"
        paper_position = (
            "SPPA should be positioned as a UAV/VR semantic-proxy systems method with a defended "
            "runtime task-fit ranking, not as a photorealistic image-to-3D SOTA leaderboard."
        )
    else:
        headline = "protocol_audit_only"
        paper_position = (
            "Current evidence is developmental only. The historical task-fit ranking is circular and excluded; "
            "do not present a comparative claim before the frozen external audit and held-out test."
        )

    return {
        "headline": headline,
        "paper_position": paper_position,
        "supported_now": [
            "Runtime/task-fit comparison for the UAV/VR semantic-proxy contract."
            if can_claim_runtime_task_fit
            else "Protocol audit of missing evidence.",
            "Claim that SPPA converts imperfect detector/tag evidence into lightweight, controllable semantic proxies.",
            "Claim that the current comparative visual grid is qualitative input-alignment evidence, not visual ground truth.",
        ],
        "not_supported_yet": [
            "A full image-to-3D visual SOTA leaderboard claim.",
            "A ground-truth first row in the comparative visual figure.",
            "A quality ranking against contemporary image-to-3D methods without shared GT/reference metrics.",
        ],
        "ambitious_next_claim": (
            "Test the frozen family-conditioned semantic graph against an input-matched, equal-budget generic graph "
            "on held-out synthetic CSG and structurally distinct implicit OOD actors, after a valid external protocol audit."
        ),
        "why_not_full_visual_sota_yet": (
            f"Protocol evidence is incomplete: complete={status_counts.get('complete', 0)}, "
            f"partial={status_counts.get('partial', 0)}, missing={status_counts.get('missing', 0)}."
        ),
    }


def build_report(protocol_path: Path) -> dict[str, Any]:
    protocol = read_json(protocol_path)
    inputs = input_set_status(protocol)
    methods = method_status(protocol)
    metrics = metric_status(protocol)
    task_fit = task_fit_summary(ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sppa_task_fit_ranking.csv")
    requirements = build_requirements(inputs, methods, metrics, task_fit)
    status_counts = {
        status: sum(1 for row in requirements if row["status"] == status)
        for status in ["complete", "partial", "missing"]
    }
    can_claim_image_to_3d_leaderboard = status_counts["partial"] == 0 and status_counts["missing"] == 0
    # The historical six-criterion pass/fail score encoded properties chosen for
    # SPPA itself. Artifact existence is provenance, not permission to rank.
    can_claim_runtime_task_fit = False
    claim_posture = build_claim_posture(
        can_claim_image_to_3d_leaderboard=can_claim_image_to_3d_leaderboard,
        can_claim_runtime_task_fit=can_claim_runtime_task_fit,
        status_counts=status_counts,
    )
    return {
        "protocol": rel(protocol_path),
        "protocol_exists": protocol_path.exists(),
        "schema": protocol.get("schema"),
        "current_decision": protocol.get("current_decision", {}),
        "external_protocol_context": protocol.get("external_protocol_context", []),
        "input_sets": inputs,
        "methods": methods,
        "metrics": metrics,
        "task_fit_runtime_ranking": {
            **task_fit,
            "excluded_from_submission": True,
            "exclusion_reason": "circular criteria encoded the proposed representation's declared properties",
        },
        "requirements": requirements,
        "status_counts": status_counts,
        "claim_posture": claim_posture,
        "can_claim_image_to_3d_sota_leaderboard": can_claim_image_to_3d_leaderboard,
        "can_claim_runtime_task_fit_ranking": can_claim_runtime_task_fit,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# SPPA Comparison Claim Readiness",
        "",
        "Generated by `tools/sppa_sota_benchmark/verify_sota_protocol_readiness.py`.",
        "",
        "## Verdict",
        "",
        f"- Protocol: `{report['protocol']}`",
        f"- Claim posture: `{report['claim_posture']['headline']}`",
        f"- Paper position: {report['claim_posture']['paper_position']}",
        f"- Full visual image-to-3D leaderboard ready: {report['can_claim_image_to_3d_sota_leaderboard']}",
        f"- Runtime semantic-proxy task-fit ranking ready: {report['can_claim_runtime_task_fit_ranking']}",
        f"- Requirement counts: complete={report['status_counts']['complete']}, partial={report['status_counts']['partial']}, missing={report['status_counts']['missing']}",
        f"- Current comparative figure role: {report['current_decision'].get('comparative_figure_role')}",
        "",
        "## Supported Claim",
        "",
        *[f"- {item}" for item in report["claim_posture"]["supported_now"]],
        "",
        "## Not Supported Yet",
        "",
        *[f"- {item}" for item in report["claim_posture"]["not_supported_yet"]],
        "",
        "## Ambitious Next Claim",
        "",
        report["claim_posture"]["ambitious_next_claim"],
        "",
        "## Requirements",
        "",
    ]
    for req in report["requirements"]:
        lines += [
            f"### `{req['key']}`",
            "",
            f"- Status: {req['status']}",
            f"- Evidence: {req['evidence']}",
            f"- Missing: {req['missing']}",
            "",
        ]
    lines += ["## Input Sets", ""]
    for item in report["input_sets"]:
        prov = item["provenance"]
        lines += [
            f"### `{item['id']}`",
            "",
            f"- Declared status: {item['declared_status']}",
            f"- Manifest exists: {item['manifest_exists']} (`{item['manifest']}`)",
            f"- Paper figure exists: {item['paper_figure_exists']} (`{item['paper_figure']}`)",
            f"- Annotation manifest exists: {item['annotation_manifest_exists']} (`{item['annotation_manifest']}`)",
            f"- Items / GT / detector crops: {prov['items']} / {prov['ground_truth_items']} / {prov['detector_crop_items']}",
            f"- Masks / reference meshes / real candidates: {prov['mask_items']} / {prov['reference_mesh_items']} / {prov['candidate_real_inputs']}",
            f"- Candidate real bbox/mask/reference-mesh items: {prov['candidate_real_bbox_items']} / {prov['candidate_real_mask_items']} / {prov['candidate_real_reference_mesh_items']}",
            f"- Can be SOTA input set: {item['can_be_sota_input_set']}",
            f"- Why not: {item['why_not'] or 'n/a'}",
            "",
        ]
    lines += ["## Required Methods", ""]
    for method in report["methods"]:
        if not method["required_for_sota_protocol"]:
            continue
        lines.append(
            f"- `{method['id']}`: {method['local_status']} "
            f"(successful_local_run={method['has_successful_local_run']})"
        )
    lines += ["", "## Metric Artifacts", ""]
    for metric in report["metrics"]:
        lines.append(
            f"- `{metric['id']}`: declared={metric['declared_status']}, "
            f"exists={metric['artifact_exists']}, artifact=`{metric['artifact']}`"
        )
    lines += ["", "## External Context", ""]
    for item in report["external_protocol_context"]:
        lines.append(f"- [{item.get('name')}]({item.get('url')}): {item.get('why_it_matters')}")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when full visual image-to-3D leaderboard evidence is not supported.")
    args = parser.parse_args()

    protocol_path = args.protocol if args.protocol.is_absolute() else ROOT / args.protocol
    report = build_report(protocol_path)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(args.md_out, report)
    print(
        json.dumps(
            {
                "json": str(args.json_out),
                "markdown": str(args.md_out),
                "claim_posture": report["claim_posture"]["headline"],
                "paper_position": report["claim_posture"]["paper_position"],
                "full_visual_image_to_3d_leaderboard_ready": report["can_claim_image_to_3d_sota_leaderboard"],
                "runtime_semantic_proxy_task_fit_ready": report["can_claim_runtime_task_fit_ranking"],
                "status_counts": report["status_counts"],
            },
            indent=2,
        )
    )
    if args.strict and not report["can_claim_image_to_3d_sota_leaderboard"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
