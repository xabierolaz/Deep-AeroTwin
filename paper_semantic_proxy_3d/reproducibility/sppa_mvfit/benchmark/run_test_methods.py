"""Run frozen methods on public held-out masks without opening private GT."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from benchmark.test_authorization import AUDIT_PATH, require_test_authorization, sha256_file  # noqa: E402
from method.sppa_mvfit import baseline_occupancy, complexity_metadata, infer_method, voxelize_actor  # noqa: E402

DATA_ROOT = PACKAGE_ROOT / "data" / "test"
RESULTS_ROOT = PACKAGE_ROOT / "results" / "test"
METHODS = ("sppa_mvfit", "generic_mvfit", "sppa_text_only", "bbox", "ellipsoid", "capsule", "billboard", "nonsemantic_visual_hull")
CONDITIONS = ("clean", "mild_morphology", "moderate_morphology", "partial_occlusion", "mask_corruption")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    auth = require_test_authorization()
    manifest = json.loads((DATA_ROOT / "dataset_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("provenance") != "synthetic_geometry":
        raise RuntimeError("test dataset provenance is not synthetic_geometry")
    public = json.loads((DATA_ROOT / "public_cases.json").read_text(encoding="utf-8"))
    masks = np.load(DATA_ROOT / "observation_masks.npy", allow_pickle=False)
    if len(public) != 240 or masks.shape != (240, 5, 2, 96, 96):
        raise RuntimeError("unexpected public test input shape")
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    binary_path = RESULTS_ROOT / "sealed_predictions.bin"
    records_path = RESULTS_ROOT / "sealed_method_outputs.jsonl"
    offset = 0
    with binary_path.open("wb") as binary, records_path.open("w", encoding="utf-8") as records:
        for case_index, case in enumerate(public):
            for condition_index, condition in enumerate(CONDITIONS):
                top_mask = masks[case_index, condition_index, 0]
                side_mask = masks[case_index, condition_index, 1]
                for method in METHODS:
                    start = time.perf_counter()
                    if method in {"sppa_mvfit", "generic_mvfit", "sppa_text_only"}:
                        result = infer_method(method, case["family"], top_mask, side_mask)
                        occupancy = voxelize_actor(result["actor"], 64)
                        metadata = {**result, **complexity_metadata(method, result["actor"])}
                        metadata.pop("actor", None)
                    else:
                        occupancy, metadata = baseline_occupancy(method, top_mask, side_mask, 64)
                        metadata.update(complexity_metadata(method, metadata.get("actor"), occupancy))
                        metadata.pop("actor", None)
                    elapsed_ms = (time.perf_counter() - start) * 1000.0
                    packed = np.packbits(occupancy.reshape(-1), bitorder="little").tobytes()
                    binary.write(packed)
                    row = {
                        "case_index": case_index,
                        "case_id": case["case_id"],
                        "family": case["family"],
                        "stratum": case["stratum"],
                        "condition": condition,
                        "method": method,
                        "offset": offset,
                        "length": len(packed),
                        "inference_ms": elapsed_ms,
                        "metadata": metadata,
                    }
                    records.write(json.dumps(row, sort_keys=True) + "\n")
                    offset += len(packed)
        binary.flush()
    sealed = {
        "schema": "sppa-mvfit-sealed-method-outputs-v1",
        "sealed_before_private_gt_evaluation": True,
        "record_count": 240 * 5 * len(METHODS),
        "binary_sha256": sha256_file(binary_path),
        "records_sha256": sha256_file(records_path),
        "pretest_freeze_sha256": sha256_file(PACKAGE_ROOT / "pretest_freeze.json"),
        "external_protocol_pass_sha256": sha256_file(AUDIT_PATH),
        "authorization_reviewer_roles": auth["audit"].get("reviewer_roles", []),
    }
    (RESULTS_ROOT / "sealed_output_manifest.json").write_text(json.dumps(sealed, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(sealed, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
