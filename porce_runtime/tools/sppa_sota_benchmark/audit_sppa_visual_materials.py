#!/usr/bin/env python
"""Audit SPPA visual-grid renders and material manifests used in the paper."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260704_real_all_sppa_unified"
DEFAULT_JSON_OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sppa_visual_material_audit.json"
DEFAULT_MD_OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sppa_visual_material_audit.md"
EXPECTED_LABELS = ["biker", "tower", "tractor", "tractor_trailer"]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def image_ink_stats(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "width": 0,
            "height": 0,
            "ink_pixels": 0,
            "ink_ratio": 0.0,
            "nonwhite_bbox": None,
        }
    image = Image.open(path).convert("RGBA")
    pixels = image.load()
    min_x, min_y = image.width, image.height
    max_x, max_y = -1, -1
    ink = 0
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if a > 20 and (abs(r - 255) > 12 or abs(g - 255) > 12 or abs(b - 255) > 12):
                ink += 1
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    bbox = None if ink == 0 else [min_x, min_y, max_x + 1, max_y + 1]
    return {
        "exists": True,
        "width": image.width,
        "height": image.height,
        "ink_pixels": ink,
        "ink_ratio": round(ink / float(image.width * image.height), 6),
        "nonwhite_bbox": bbox,
    }


def obj_material_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    names: set[str] = set()
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("usemtl "):
                names.add(line.split(maxsplit=1)[1])
    return names


def audit_label(run_dir: Path, label: str) -> dict[str, Any]:
    output_dir = run_dir / "outputs" / "sppa" / label
    view_dir = run_dir / "views" / "models" / "sppa" / label
    obj_path = output_dir / f"{label}.obj"
    mtl_path = output_dir / f"{label}.mtl"
    manifest_path = output_dir / f"{label}.materials.json"
    iso_path = view_dir / "iso.png"
    manifest = load_json(manifest_path)
    materials = list(manifest.get("materials", []))
    manifest_names = {str(item.get("name")) for item in materials if item.get("name")}
    obj_names = obj_material_names(obj_path)
    missing_manifest_names = sorted(obj_names - manifest_names)
    fallback_materials = [
        item.get("name")
        for item in materials
        if item.get("evidence_source") == "fallback_unknown"
        or str(item.get("uncertainty_visual_style", "")).startswith("desaturated")
    ]
    non_opaque_materials = [
        item.get("name")
        for item in materials
        if float(item.get("alpha", 1.0) or 1.0) < 0.95
    ]
    image_stats = image_ink_stats(iso_path)
    checks = {
        "obj_exists": obj_path.exists(),
        "mtl_exists": mtl_path.exists(),
        "manifest_exists": manifest_path.exists(),
        "iso_exists": iso_path.exists(),
        "iso_has_content": image_stats["ink_ratio"] >= 0.015,
        "manifest_has_materials": len(materials) > 0,
        "obj_materials_covered_by_manifest": not missing_manifest_names,
        "no_unknown_fallback_materials": not fallback_materials,
        "no_unexpected_transparency": not non_opaque_materials,
        "procedural_role_policy_declared": manifest.get("material_policy") in {
            "evidence_calibrated_procedural_roles",
            "role_priors_with_optional_observed_color",
        },
    }
    return {
        "label": label,
        "paths": {
            "obj": rel(obj_path),
            "mtl": rel(mtl_path),
            "manifest": rel(manifest_path),
            "iso": rel(iso_path),
        },
        "image": image_stats,
        "material_policy": manifest.get("material_policy"),
        "descriptor_schema": manifest.get("descriptor_schema"),
        "material_count": len(materials),
        "obj_material_count": len(obj_names),
        "fallback_materials": fallback_materials,
        "non_opaque_materials": non_opaque_materials,
        "missing_manifest_materials": missing_manifest_names,
        "checks": checks,
        "status": "pass" if all(checks.values()) else "fail",
    }


def build_report(run_dir: Path) -> dict[str, Any]:
    labels = [label for label in EXPECTED_LABELS]
    rows = [audit_label(run_dir, label) for label in labels]
    failures: list[str] = []
    for row in rows:
        for key, ok in row["checks"].items():
            if not ok:
                failures.append(f"{row['label']}:{key}")
    render_script = ROOT / "tools" / "sppa_sota_benchmark" / "render_mesh_views.py"
    render_text = render_script.read_text(encoding="utf-8", errors="ignore") if render_script.exists() else ""
    render_contract = {
        "render_script": rel(render_script),
        "uses_maintain_order": "maintain_order=True" in render_text,
        "uses_depth_sort": "np.argsort(depth)[::-1]" in render_text,
        "uses_material_manifest": "material_manifest_metadata" in render_text,
        "uses_face_material_colors": "face_material_colors" in render_text,
        "uses_configurable_edge_alpha": "--edge-alpha" in render_text,
    }
    return {
        "run_dir": rel(run_dir),
        "labels": labels,
        "rows": rows,
        "render_contract": render_contract,
        "failures": failures,
        "pass": not failures and all(render_contract.values()),
        "claim_boundary": "SPPA materials are procedural semantic-role priors or explicit fallbacks. They are not photorealistic textures and should not be claimed as observed surface reconstruction unless explicit sensor/operator color evidence is supplied.",
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# SPPA Visual Material Audit",
        "",
        "Generated by `tools/sppa_sota_benchmark/audit_sppa_visual_materials.py`.",
        "",
        "## Verdict",
        "",
        f"- Run directory: `{report['run_dir']}`",
        f"- Pass: {report['pass']}",
        f"- Failures: {', '.join(report['failures']) if report['failures'] else 'none'}",
        f"- Claim boundary: {report['claim_boundary']}",
        "",
        "## Renderer Contract",
        "",
    ]
    for key, value in report["render_contract"].items():
        lines.append(f"- `{key}`: {value}")
    lines += ["", "## Label Checks", ""]
    for row in report["rows"]:
        lines += [
            f"### `{row['label']}`",
            "",
            f"- Status: {row['status']}",
            f"- ISO: `{row['paths']['iso']}`",
            f"- Material manifest: `{row['paths']['manifest']}`",
            f"- Material policy: {row['material_policy']}",
            f"- Material count / OBJ material count: {row['material_count']} / {row['obj_material_count']}",
            f"- Fallback materials: {row['fallback_materials'] or 'none'}",
            f"- Non-opaque materials: {row['non_opaque_materials'] or 'none'}",
            f"- Missing manifest materials: {row['missing_manifest_materials'] or 'none'}",
            f"- ISO ink ratio: {row['image']['ink_ratio']}",
            "",
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when the audit fails.")
    args = parser.parse_args()

    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    report = build_report(run_dir)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(args.md_out, report)
    print(
        json.dumps(
            {
                "json": str(args.json_out),
                "markdown": str(args.md_out),
                "pass": report["pass"],
                "failures": report["failures"],
            },
            indent=2,
        )
    )
    if args.strict and not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
