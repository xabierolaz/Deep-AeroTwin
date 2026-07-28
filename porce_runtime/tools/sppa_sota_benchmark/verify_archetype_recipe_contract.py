from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def load_generator(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load generator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def part_material_roles(mesh: Any) -> set[str]:
    roles: set[str] = set()
    for part in getattr(mesh, "parts", []):
        for key in ("material_role", "role"):
            value = part.get(key) if isinstance(part, dict) else None
            if value:
                roles.add(str(value))
        meta = part.get("meta") if isinstance(part, dict) else None
        if isinstance(meta, dict):
            value = meta.get("material_role")
            if value:
                roles.add(str(value))
    return roles


def dims_dict(values: list[float]) -> dict[str, float]:
    length, width, height = values
    return {"length": float(length), "width": float(width), "height": float(height)}


def run_label(module: Any, label: str, dims_m: list[float]) -> dict[str, Any]:
    mesh = module.Mesh()
    meta = module.build_label_parametric(mesh, label, dims_dict(dims_m))
    return {
        "label": label,
        "meta": meta,
        "part_count": len(mesh.parts),
        "material_roles": sorted(part_material_roles(mesh)),
        "triangles": module.mesh_triangle_count(mesh),
    }


def expected_status(recipe_id: str, label_kind: str, meta: dict[str, Any]) -> str:
    explicit = meta.get("expected_resolution_status")
    if explicit:
        return str(explicit)
    if recipe_id == "unknown":
        return "fallback_unknown_label"
    if label_kind == "exact":
        return "exact_class"
    return "keyword_archetype"


def verify_recipe(module: Any, recipe: dict[str, Any]) -> dict[str, Any]:
    recipe_id = str(recipe["id"])
    allowed_archetypes = set(recipe.get("runtime_archetypes") or [recipe_id])
    required_roles = set(recipe.get("required_roles") or [])
    dims_m = recipe.get("sample_dims_m") or [1.0, 1.0, 1.0]
    expected_resolution_status = recipe.get("expected_resolution_status")
    rows: list[dict[str, Any]] = []
    failures: list[str] = []

    def check(label: str, label_kind: str) -> None:
        row = run_label(module, label, dims_m)
        meta = row["meta"]
        if expected_resolution_status:
            meta = dict(meta)
            meta["expected_resolution_status"] = expected_resolution_status
        row_failures: list[str] = []
        if meta.get("archetype") not in allowed_archetypes:
            row_failures.append(f"archetype={meta.get('archetype')} allowed={sorted(allowed_archetypes)}")
        expected = expected_status(recipe_id, label_kind, meta)
        if meta.get("resolution_status") != expected:
            row_failures.append(f"resolution_status={meta.get('resolution_status')} expected={expected}")
        roles = set(row["material_roles"])
        if not required_roles.issubset(roles):
            row_failures.append(f"missing_required_roles={sorted(required_roles - roles)}")
        if expected_resolution_status == "open_label_verified_recipe" and meta.get("shape_policy") != "verified_open_label_part_layout_from_metric_dims":
            row_failures.append(f"shape_policy={meta.get('shape_policy')}")
        elif recipe_id != "unknown" and expected_resolution_status != "open_label_verified_recipe" and meta.get("shape_policy") != "semantic_part_layout_from_metric_dims":
            row_failures.append(f"shape_policy={meta.get('shape_policy')}")
        if recipe_id == "unknown" and meta.get("shape_policy") != "fallback_conservative_volume_from_metric_dims":
            row_failures.append(f"unknown_shape_policy={meta.get('shape_policy')}")
        row["label_kind"] = label_kind
        row["status"] = "ok" if not row_failures else "failed"
        row["failures"] = row_failures
        rows.append(row)
        failures.extend(f"{recipe_id}:{label}:{failure}" for failure in row_failures)

    for label in recipe.get("exact_labels") or []:
        check(str(label), "exact")
    for keyword in recipe.get("keyword_labels") or []:
        check(f"field {keyword}", "keyword")

    return {
        "id": recipe_id,
        "allowed_runtime_archetypes": sorted(allowed_archetypes),
        "checked_labels": len(rows),
        "failed": len(failures),
        "rows": rows,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify reviewed SPPA archetype recipes against the runtime resolver/generator.")
    parser.add_argument("--recipes", default=str(ROOT / "tools" / "sppa_sota_benchmark" / "sppa_archetype_recipes_v03.json"))
    parser.add_argument("--generator", default=str(ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"))
    parser.add_argument("--output", default="experiments/sppa_open_label_smoke/latest/archetype_recipe_contract.json")
    args = parser.parse_args()

    recipes_path = Path(args.recipes)
    generator_path = Path(args.generator)
    recipes = json.loads(recipes_path.read_text(encoding="utf-8"))
    module = load_generator(generator_path)

    top_failures: list[str] = []
    if recipes.get("runtime_llm_allowed") is not False:
        top_failures.append("runtime_llm_allowed must be false")
    if recipes.get("ontology_version") != getattr(module, "ONTOLOGY_VERSION", None):
        top_failures.append(f"ontology_version={recipes.get('ontology_version')} generator={getattr(module, 'ONTOLOGY_VERSION', None)}")
    if recipes.get("archetype_version") != getattr(module, "ARCHETYPE_VERSION", None):
        top_failures.append(f"archetype_version={recipes.get('archetype_version')} generator={getattr(module, 'ARCHETYPE_VERSION', None)}")
    if recipes.get("generator_version") != getattr(module, "GENERATOR_VERSION", None):
        top_failures.append(f"generator_version={recipes.get('generator_version')} generator={getattr(module, 'GENERATOR_VERSION', None)}")

    recipe_rows = [verify_recipe(module, recipe) for recipe in recipes.get("archetypes") or []]
    all_failures = list(top_failures)
    for row in recipe_rows:
        all_failures.extend(row["failures"])

    result = {
        "recipes": str(recipes_path),
        "generator": str(generator_path),
        "contract_schema": recipes.get("contract_schema"),
        "runtime_llm_allowed": recipes.get("runtime_llm_allowed"),
        "total_archetypes": len(recipe_rows),
        "total_checked_labels": sum(row["checked_labels"] for row in recipe_rows),
        "failed": len(all_failures),
        "top_level_failures": top_failures,
        "archetypes": recipe_rows,
    }

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(result, indent=2, sort_keys=True))
    if all_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
