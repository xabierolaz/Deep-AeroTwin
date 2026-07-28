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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dims_dict(values: list[float] | tuple[float, ...] | None) -> dict[str, float]:
    values = list(values or [1.0, 1.0, 1.0])
    if len(values) != 3:
        raise ValueError(f"sample_dims_m must contain 3 values, got {values!r}")
    length, width, height = values
    return {"length": float(length), "width": float(width), "height": float(height)}


def known_material_roles(module: Any) -> set[str]:
    roles: set[str] = set(getattr(module, "OBSERVED_COLOR_TARGET_ROLES", set()))
    for meta in getattr(module, "MATERIAL_METADATA", {}).values():
        if isinstance(meta, dict) and meta.get("material_role"):
            roles.add(str(meta["material_role"]))
    return roles


def runtime_compile(module: Any, label: str, dims_m: list[float]) -> dict[str, Any]:
    mesh = module.Mesh()
    meta = module.build_label_parametric(mesh, label, dims_dict(dims_m))
    roles = sorted(
        {
            str(part.get("material_role") or part.get("role"))
            for part in getattr(mesh, "parts", [])
            if part.get("material_role") or part.get("role")
        }
    )
    return {
        "meta": meta,
        "part_count": len(mesh.parts),
        "material_roles": roles,
        "triangles": module.mesh_triangle_count(mesh),
    }


def fallback_status(status: str) -> bool:
    return str(status or "").startswith("fallback")


def review_candidate(
    module: Any,
    policy: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []

    allowed_sources = set(policy.get("allowed_authoring_sources") or [])
    allowed_primitives = set(policy.get("allowed_primitives") or [])
    limits = policy.get("hard_limits") or {}
    material_roles = known_material_roles(module)

    candidate_id = str(candidate.get("id") or "")
    source = str(candidate.get("authoring_source") or "")
    label = str(candidate.get("input_label") or "")
    proposed_archetype = str(candidate.get("proposed_archetype") or "")
    sample_dims = candidate.get("sample_dims_m") or [1.0, 1.0, 1.0]
    part_recipe = candidate.get("part_recipe") or []
    required_roles = set(str(v) for v in candidate.get("required_material_roles") or [])

    if not candidate_id:
        blockers.append("missing_candidate_id")
    if source not in allowed_sources:
        blockers.append(f"authoring_source_not_allowed:{source}")
    if candidate.get("runtime_llm_requested") is True:
        blockers.append("runtime_llm_requested")
    if not label.strip():
        blockers.append("missing_input_label")
    if not proposed_archetype:
        blockers.append("missing_proposed_archetype")
    if len(part_recipe) > int(limits.get("max_parts", 999999)):
        blockers.append(f"too_many_parts:{len(part_recipe)}")
    if len(required_roles) < int(limits.get("min_required_material_roles", 0)):
        blockers.append("missing_required_material_roles")

    candidate_primitives: list[str] = []
    candidate_material_roles: list[str] = []
    for index, part in enumerate(part_recipe):
        primitive = str(part.get("primitive") or "")
        material_role = str(part.get("material_role") or "")
        candidate_primitives.append(primitive)
        candidate_material_roles.append(material_role)
        if primitive not in allowed_primitives:
            blockers.append(f"part_{index}_primitive_not_allowed:{primitive}")
        if material_role not in material_roles:
            blockers.append(f"part_{index}_material_role_not_known:{material_role}")

    missing_candidate_roles = sorted(required_roles - set(candidate_material_roles))
    if missing_candidate_roles:
        blockers.append(f"candidate_missing_required_roles:{missing_candidate_roles}")

    try:
        compiled = runtime_compile(module, label, sample_dims)
    except Exception as exc:  # noqa: BLE001 - audit tool should report exact failure
        compiled = {
            "meta": {},
            "part_count": 0,
            "material_roles": [],
            "triangles": 0,
            "compile_error": str(exc),
        }
        blockers.append(f"runtime_compile_error:{exc}")

    meta = compiled.get("meta") or {}
    runtime_archetype = str(meta.get("archetype") or "unknown")
    resolution_status = str(meta.get("resolution_status") or "")
    expected_archetype = candidate.get("expected_runtime_archetype")
    if expected_archetype is not None and runtime_archetype != str(expected_archetype):
        blockers.append(f"runtime_archetype={runtime_archetype},expected={expected_archetype}")

    if fallback_status(resolution_status):
        if proposed_archetype != "unknown":
            blockers.append(f"resolver_forces_fallback:{resolution_status}")
    elif proposed_archetype != runtime_archetype:
        blockers.append(f"proposed_archetype={proposed_archetype},runtime={runtime_archetype}")

    runtime_roles = set(compiled.get("material_roles") or [])
    missing_runtime_roles = sorted(required_roles - runtime_roles)
    if missing_runtime_roles and not fallback_status(resolution_status):
        blockers.append(f"runtime_missing_required_roles:{missing_runtime_roles}")
    elif missing_runtime_roles:
        warnings.append(f"fallback_runtime_missing_candidate_roles:{missing_runtime_roles}")

    max_triangles = int(limits.get("max_triangles", 999999999))
    triangles = int(compiled.get("triangles") or 0)
    if triangles > max_triangles:
        blockers.append(f"triangle_budget_exceeded:{triangles}>{max_triangles}")

    if blockers:
        decision = "rejected"
    elif fallback_status(resolution_status) or proposed_archetype == "unknown":
        decision = "fallback_only"
    else:
        decision = "accepted"

    expected_decision = candidate.get("expected_decision")
    expectation_ok = expected_decision is None or decision == str(expected_decision)

    return {
        "id": candidate_id,
        "input_label": label,
        "authoring_source": source,
        "proposed_archetype": proposed_archetype,
        "runtime_archetype": runtime_archetype,
        "resolution_status": resolution_status,
        "decision": decision,
        "expected_decision": expected_decision,
        "expectation_ok": expectation_ok,
        "blockers": blockers,
        "warnings": warnings,
        "candidate_primitives": sorted(set(candidate_primitives)),
        "candidate_material_roles": sorted(set(candidate_material_roles)),
        "runtime_part_count": compiled.get("part_count"),
        "runtime_material_roles": compiled.get("material_roles"),
        "runtime_triangles": triangles,
        "shape_policy": meta.get("shape_policy"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit offline SPPA recipe candidates before they can become runtime cache entries."
    )
    parser.add_argument(
        "--policy",
        default=str(ROOT / "tools" / "sppa_sota_benchmark" / "sppa_offline_recipe_review_policy_v01.json"),
    )
    parser.add_argument(
        "--candidates",
        default=str(ROOT / "tools" / "sppa_sota_benchmark" / "sppa_offline_recipe_candidates_v01.json"),
    )
    parser.add_argument(
        "--generator",
        default=str(ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"),
    )
    parser.add_argument(
        "--output",
        default="experiments/sppa_open_label_smoke/latest/offline_recipe_review_gate.json",
    )
    args = parser.parse_args()

    policy_path = Path(args.policy)
    candidates_path = Path(args.candidates)
    generator_path = Path(args.generator)
    policy = read_json(policy_path)
    candidates = read_json(candidates_path)
    module = load_generator(generator_path)

    top_failures: list[str] = []
    if policy.get("runtime_llm_allowed") is not False:
        top_failures.append("policy_runtime_llm_allowed_must_be_false")
    if candidates.get("runtime_llm_allowed") is not False:
        top_failures.append("candidates_runtime_llm_allowed_must_be_false")
    if candidates.get("review_policy_id") != policy.get("review_policy_id"):
        top_failures.append(
            f"review_policy_id_mismatch:{candidates.get('review_policy_id')}!={policy.get('review_policy_id')}"
        )

    rows = [review_candidate(module, policy, candidate) for candidate in candidates.get("candidates") or []]
    expectation_failures = [
        f"{row['id']}:{row['decision']}!=expected:{row['expected_decision']}"
        for row in rows
        if not row["expectation_ok"]
    ]
    accepted_with_blockers = [
        f"{row['id']}:{row['blockers']}"
        for row in rows
        if row["decision"] in {"accepted", "fallback_only"} and row["blockers"]
    ]
    failures = top_failures + expectation_failures + accepted_with_blockers

    summary = {
        "policy": str(policy_path),
        "candidates": str(candidates_path),
        "generator": str(generator_path),
        "review_policy_id": policy.get("review_policy_id"),
        "runtime_llm_allowed": False,
        "total_candidates": len(rows),
        "accepted": sum(1 for row in rows if row["decision"] == "accepted"),
        "fallback_only": sum(1 for row in rows if row["decision"] == "fallback_only"),
        "rejected": sum(1 for row in rows if row["decision"] == "rejected"),
        "failed": len(failures),
        "failures": failures,
        "rows": rows,
    }

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
