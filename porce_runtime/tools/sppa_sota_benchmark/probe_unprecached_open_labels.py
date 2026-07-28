from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_open_label_probe" / "20260704_unprecache_probe" / "open_label_unprecache_inputs.csv"
DEFAULT_OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_open_label_probe" / "20260704_unprecache_probe" / "probe_outputs"
DEFAULT_GENERATOR = ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"


def load_generator(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_normalizer() -> Any:
    spec = importlib.util.spec_from_file_location("sppa_semantic_normalizer", ROOT / "pipeline" / "sppa_semantic_normalizer.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load pipeline/sppa_semantic_normalizer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


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


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_dims(module: Any, value: str | None) -> dict[str, float] | None:
    if not value:
        return None
    if hasattr(module, "parse_dims_cli"):
        return module.parse_dims_cli(value)
    if hasattr(module, "parse_dims_arg"):
        return module.parse_dims_arg(value)
    parts = [float(part.strip()) for part in value.split(",")]
    return {"length": parts[0], "width": parts[1], "height": parts[2]}


def material_roles(mesh: Any) -> list[str]:
    roles = []
    for part in getattr(mesh, "parts", []):
        role = str(part.get("role") or part.get("material_role") or "")
        if role and role not in roles:
            roles.append(role)
    return roles


def run_one(
    module: Any,
    *,
    mode: str,
    raw_label: str,
    generator_label: str,
    row: dict[str, str],
    out_root: Path,
    normalizer_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    safe_label = module.safe_name(raw_label) if hasattr(module, "safe_name") else raw_label.replace(" ", "_")
    label_dir = out_root / mode / "outputs" / "sppa" / safe_label
    label_dir.mkdir(parents=True, exist_ok=True)
    mesh = module.Mesh()
    dims = parse_dims(module, row.get("dims_m"))
    start = time.perf_counter()
    meta = module.build_label_observed(mesh, generator_label, dims_m=dims)
    build_ms = (time.perf_counter() - start) * 1000.0

    obj_path = label_dir / f"{safe_label}.obj"
    mtl_path = label_dir / f"{safe_label}.mtl"
    descriptor_path = label_dir / f"{safe_label}.descriptor.json"
    manifest_path = label_dir / f"{safe_label}.materials.json"
    module.write_mtl(str(mtl_path))
    module.write_obj(mesh, str(obj_path), mtl_path.name)
    material_manifest = module.write_material_manifest(
        str(manifest_path),
        mesh,
        meta,
        safe_float(row.get("confidence"), 1.0),
    )
    descriptor = module.write_sppa_descriptor(
        str(descriptor_path),
        mesh,
        meta,
        safe_float(row.get("confidence"), 1.0),
        dims_m=meta.get("effective_dims_m") or dims,
        track_id=f"{mode}:{safe_label}",
    )

    fallback = str(meta.get("resolution_status") or "").startswith("fallback")
    part_count = len(getattr(mesh, "parts", []))
    triangles = module.mesh_triangle_count(mesh) if hasattr(module, "mesh_triangle_count") else sum(
        int(part.get("triangle_budget") or 0) for part in getattr(mesh, "parts", [])
    )
    return {
        "mode": mode,
        "raw_label": raw_label,
        "generator_label": generator_label,
        "normalizer_sppa_tag": (normalizer_payload or {}).get("sppa_tag"),
        "normalizer_runtime_label": (normalizer_payload or {}).get("runtime_label"),
        "normalizer_rule": (normalizer_payload or {}).get("normalization_rule"),
        "normalizer_claim_status": (normalizer_payload or {}).get("claim_status"),
        "normalizer_conservative": (normalizer_payload or {}).get("conservative"),
        "generator_archetype": meta.get("archetype"),
        "resolution_status": meta.get("resolution_status"),
        "shape_policy": meta.get("shape_policy"),
        "metric_dims_source": meta.get("metric_dims_source"),
        "open_label_recipe_id": (meta.get("open_label_verification") or {}).get("recipe_id"),
        "open_label_verifier_accepted": (meta.get("open_label_verification") or {}).get("accepted"),
        "open_label_verifier_failures": ";".join((meta.get("open_label_verification") or {}).get("failures", [])),
        "fallback": fallback,
        "part_count": part_count,
        "triangles": triangles,
        "vertices": len(getattr(mesh, "vertices", [])),
        "faces": len(getattr(mesh, "faces", [])),
        "roles": ";".join(material_roles(mesh)),
        "fallback_material_count": sum(
            1 for item in material_manifest.get("materials", []) if item.get("evidence_source") == "fallback_unknown"
        ),
        "descriptor_bytes": descriptor.get("cost", {}).get("descriptor_bytes"),
        "build_ms": round(build_ms, 4),
        "obj_path": rel(obj_path),
        "descriptor_path": rel(descriptor_path),
    }


def build_markdown(path: Path, report: dict[str, Any]) -> None:
    rows = report["rows"]
    lines = [
        "# Uncached Open-Label SPPA Probe",
        "",
        "This is an exploratory test harness for conservative SPPA intake plus verifier-gated open-label proxy recipes.",
        "",
        "## Verdict",
        "",
        f"- Input labels: {report['input_count']}",
        f"- Raw mode fallback count: {report['raw_fallback_count']} / {report['input_count']}",
        f"- Normalized mode fallback count: {report['normalized_fallback_count']} / {report['input_count']}",
        f"- Raw keyword/family count: {report['raw_family_count']} / {report['input_count']}",
        f"- Normalized family count: {report['normalized_family_count']} / {report['input_count']}",
        f"- Raw verified open-label recipes: {report['raw_open_label_verified_count']} / {report['input_count']}",
        f"- Normalized verified open-label recipes: {report['normalized_open_label_verified_count']} / {report['input_count']}",
        f"- Critical mismatch count: {report['critical_mismatch_count']}",
        "",
        "## Comparison",
        "",
        "| Raw label | Raw result | Normalized input | Normalized result | Comment |",
        "|---|---|---|---|---|",
    ]
    by_label: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_label.setdefault(row["raw_label"], {})[row["mode"]] = row
    for label, pair in by_label.items():
        raw = pair.get("raw", {})
        norm = pair.get("normalized", {})
        comment = "same"
        if raw.get("fallback") and not norm.get("fallback"):
            comment = "normalizer improves coverage"
        elif not raw.get("fallback") and norm.get("fallback"):
            comment = "normalizer downgrades to fallback"
        elif raw.get("generator_archetype") != norm.get("generator_archetype"):
            comment = "archetype changes"
        lines.append(
            f"| `{label}` | `{raw.get('generator_archetype')}`/{raw.get('resolution_status')} | "
            f"`{norm.get('generator_label')}` via `{norm.get('normalizer_rule')}` | "
            f"`{norm.get('generator_archetype')}`/{norm.get('resolution_status')} | {comment} |"
        )
    lines += [
        "",
        "## Claim Boundary",
        "",
        "The current system is open-label intake with conservative fallback plus verifier-gated proxy recipes for a limited set of useful open labels.",
        "It is not arbitrary image-to-3D reconstruction and it does not claim object-specific detail beyond the accepted semantic part recipe.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe current SPPA behavior on non-precached/open labels.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--generator", type=Path, default=DEFAULT_GENERATOR)
    args = parser.parse_args()

    input_path = args.input if args.input.is_absolute() else ROOT / args.input
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    generator_path = args.generator if args.generator.is_absolute() else ROOT / args.generator
    module = load_generator(generator_path)
    normalizer = load_normalizer()
    source_rows = read_csv(input_path)

    rows: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    for row in source_rows:
        raw_label = row["label"]
        confidence = safe_float(row.get("confidence"), 1.0)
        normalized = normalizer.normalize_runtime_detection({"class_name": raw_label, "confidence": confidence})
        mapping_rows.append({"raw_label": raw_label, **normalized})
        rows.append(
            run_one(
                module,
                mode="raw",
                raw_label=raw_label,
                generator_label=raw_label,
                row=row,
                out_root=out_dir,
                normalizer_payload=None,
            )
        )
        rows.append(
            run_one(
                module,
                mode="normalized",
                raw_label=raw_label,
                generator_label=str(normalized.get("runtime_label") or "unknown"),
                row=row,
                out_root=out_dir,
                normalizer_payload=normalized,
            )
        )

    raw_rows = [row for row in rows if row["mode"] == "raw"]
    norm_rows = [row for row in rows if row["mode"] == "normalized"]
    critical_mismatches = [
        row
        for row in norm_rows
        if row["normalizer_runtime_label"]
        and row["generator_archetype"] != row["normalizer_runtime_label"]
        and row["normalizer_runtime_label"] != "vegetation"
    ]
    report = {
        "schema": "SPPA-UNPRECACHED-OPEN-LABEL-PROBE-0.1",
        "input_csv": rel(input_path),
        "generator": rel(generator_path),
        "input_count": len(source_rows),
        "raw_fallback_count": sum(1 for row in raw_rows if row["fallback"]),
        "normalized_fallback_count": sum(1 for row in norm_rows if row["fallback"]),
        "raw_family_count": sum(1 for row in raw_rows if not row["fallback"]),
        "normalized_family_count": sum(1 for row in norm_rows if not row["fallback"]),
        "raw_open_label_verified_count": sum(1 for row in raw_rows if row["resolution_status"] == "open_label_verified_recipe"),
        "normalized_open_label_verified_count": sum(1 for row in norm_rows if row["resolution_status"] == "open_label_verified_recipe"),
        "critical_mismatch_count": len(critical_mismatches),
        "critical_mismatches": critical_mismatches,
        "mapping_rows": mapping_rows,
        "rows": rows,
        "claim_boundary": "Conservative SPPA intake plus verifier-gated open-label proxy recipes; not arbitrary object-specific reconstruction.",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "unprecached_open_label_probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_csv(out_dir / "unprecached_open_label_probe.csv", rows)
    write_csv(out_dir / "normalizer_mapping.csv", mapping_rows)
    build_markdown(out_dir / "unprecached_open_label_probe.md", report)
    print(json.dumps({k: report[k] for k in ("input_count", "raw_fallback_count", "normalized_fallback_count", "raw_open_label_verified_count", "normalized_open_label_verified_count", "critical_mismatch_count")}, indent=2))


if __name__ == "__main__":
    main()
