"""Generate the sealed held-out source and public observations after authorization."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from benchmark.run_benchmark import make_conditions  # noqa: E402
from benchmark.test_authorization import require_test_authorization  # noqa: E402
from source.source_generators import FAMILIES, generate_source_actor, render_source_masks, validate_actor_inside_world  # noqa: E402

DATA_ROOT = PACKAGE_ROOT / "data" / "test"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    auth = require_test_authorization()
    seed_manifest = auth["seed"]
    expected_ids = [
        f"test-{stratum}-{family}-{index:03d}"
        for stratum in ("csg_id", "implicit_ood")
        for family in FAMILIES
        for index in range(20)
    ]
    if seed_manifest.get("case_ids") != expected_ids:
        raise RuntimeError("seed manifest case ordering does not match the frozen 12-stratum design")
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    public_rows: list[dict] = []
    private_path = DATA_ROOT / "private_source_actors.jsonl"
    masks = np.zeros((240, 5, 2, 96, 96), dtype=bool)
    with private_path.open("w", encoding="utf-8") as private:
        for case_index, case_id in enumerate(expected_ids):
            _, stratum, family, index_text = case_id.split("-")
            seed = int(seed_manifest["case_seeds"][case_index])
            actor = generate_source_actor(family, stratum, seed)
            if not validate_actor_inside_world(actor):
                raise RuntimeError(f"source actor outside world: {case_id}")
            clean_top, clean_side = render_source_masks(actor)
            masks[case_index] = make_conditions(clean_top, clean_side, seed)
            public_rows.append({"case_id": case_id, "family": family, "stratum": stratum, "index": int(index_text)})
            private.write(json.dumps({"case_id": case_id, "seed": seed, "actor": actor}, sort_keys=True) + "\n")
    public_path = DATA_ROOT / "public_cases.json"
    public_path.write_text(json.dumps(public_rows, indent=2) + "\n", encoding="utf-8")
    mask_path = DATA_ROOT / "observation_masks.npy"
    np.save(mask_path, masks, allow_pickle=False)
    manifest = {
        "schema": "sppa-mvfit-test-dataset-v1",
        "provenance": "synthetic_geometry",
        "public_inputs": ["public_cases.json", "observation_masks.npy"],
        "private_inputs": ["private_source_actors.jsonl"],
        "case_count": 240,
        "conditions": ["clean", "mild_morphology", "moderate_morphology", "partial_occlusion", "mask_corruption"],
        "source_strata": ["csg_id", "implicit_ood"],
        "seed_manifest_sha256": sha256_file(PACKAGE_ROOT / "test_seed_manifest.json"),
    }
    for name in ("public_cases.json", "observation_masks.npy", "private_source_actors.jsonl"):
        manifest[f"{name}_sha256"] = sha256_file(DATA_ROOT / name)
    (DATA_ROOT / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
