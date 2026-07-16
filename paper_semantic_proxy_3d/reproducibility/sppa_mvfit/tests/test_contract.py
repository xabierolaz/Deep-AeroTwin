from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from benchmark.run_benchmark import CONDITIONS, development_cases, make_conditions  # noqa: E402
from method.sppa_mvfit import GRAPHS, build_actor, default_theta, fit_graph, infer_method, render_actor_masks  # noqa: E402
from source.source_generators import FAMILIES, generate_source_actor, render_source_masks, voxelize_source  # noqa: E402


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def test_all_graphs_have_exactly_eight_slots() -> None:
    assert set(GRAPHS) == set(FAMILIES) | {"generic"}
    assert all(len(slots) == 8 for slots in GRAPHS.values())


def test_text_only_calls_shared_builder_without_hidden_actor() -> None:
    for family in FAMILIES:
        expected = build_actor(family, default_theta())
        observed = infer_method("sppa_text_only", family, np.zeros((96, 96), bool), np.zeros((96, 96), bool))["actor"]
        assert canonical_hash(expected) == canonical_hash(observed)


def test_fitter_budget_and_determinism() -> None:
    actor = build_actor("compact_vehicle", default_theta())
    top, side = render_actor_masks(actor, 96)
    first = fit_graph("compact_vehicle", top, side)
    second = fit_graph("compact_vehicle", top, side)
    assert first["evaluations"] == 31
    assert first["theta"] == second["theta"]
    assert first["objective"] == second["objective"]
    assert canonical_hash(first["actor"]) == canonical_hash(second["actor"])


def test_source_generator_is_deterministic_and_separate() -> None:
    first = generate_source_actor("quadruped", "csg_id", 110048)
    second = generate_source_actor("quadruped", "csg_id", 110048)
    assert canonical_hash(first) == canonical_hash(second)
    assert np.array_equal(voxelize_source(first), voxelize_source(second))
    top_a, side_a = render_source_masks(first)
    top_b, side_b = render_source_masks(second)
    assert np.array_equal(top_a, top_b)
    assert np.array_equal(side_a, side_b)


def test_conditions_are_deterministic_and_complete() -> None:
    actor = generate_source_actor("compact_vehicle", "csg_id", 110000)
    top, side = render_source_masks(actor)
    first = make_conditions(top, side, 110000)
    second = make_conditions(top, side, 110000)
    assert first.shape == (len(CONDITIONS), 2, 96, 96)
    assert np.array_equal(first, second)
    assert np.array_equal(first[0, 0], top)
    assert np.array_equal(first[0, 1], side)


def test_development_split_is_balanced_and_does_not_use_test() -> None:
    cases = development_cases()
    assert len(cases) == 144
    assert min(case["seed"] for case in cases) == 110000
    assert max(case["seed"] for case in cases) == 110143
    assert {case["stratum"] for case in cases} == {"csg_id"}
    for family in FAMILIES:
        assert sum(case["family"] == family for case in cases) == 24


def test_no_cross_import_between_source_and_method() -> None:
    source_text = (PACKAGE_ROOT / "source" / "source_generators.py").read_text(encoding="utf-8")
    method_text = (PACKAGE_ROOT / "method" / "sppa_mvfit.py").read_text(encoding="utf-8")
    assert "from method" not in source_text
    assert "import method" not in source_text
    assert "from source" not in method_text
    assert "import source" not in method_text

