"""Release private GT only after sealed method outputs are complete."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from benchmark.metrics import evaluate_geometry  # noqa: E402
from benchmark.test_authorization import AUDIT_PATH, require_test_authorization  # noqa: E402
from method.sppa_mvfit import WORLD  # noqa: E402
from source.source_generators import voxelize_source  # noqa: E402

DATA_ROOT = PACKAGE_ROOT / "data" / "test"
RESULTS_ROOT = PACKAGE_ROOT / "results" / "test"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    auth = require_test_authorization()
    sealed_path = RESULTS_ROOT / "sealed_output_manifest.json"
    binary_path = RESULTS_ROOT / "sealed_predictions.bin"
    records_path = RESULTS_ROOT / "sealed_method_outputs.jsonl"
    if not sealed_path.exists() or not binary_path.exists() or not records_path.exists():
        raise RuntimeError("sealed method outputs are missing; private GT remains locked")
    sealed = json.loads(sealed_path.read_text(encoding="utf-8"))
    if not sealed.get("sealed_before_private_gt_evaluation"):
        raise RuntimeError("method output manifest does not prove pre-GT sealing")
    if sealed.get("binary_sha256") != sha256_file(binary_path) or sealed.get("records_sha256") != sha256_file(records_path):
        raise RuntimeError("sealed method outputs changed after sealing")
    actors: dict[str, dict] = {}
    with (DATA_ROOT / "private_source_actors.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            actors[row["case_id"]] = row["actor"]
    diagonal = float(np.linalg.norm([WORLD["x"][1] - WORLD["x"][0], WORLD["y"][1] - WORLD["y"][0], WORLD["z"][1] - WORLD["z"][0]]))
    gt_cache: dict[str, np.ndarray] = {}
    rows: list[dict] = []
    with binary_path.open("rb") as binary, records_path.open("r", encoding="utf-8") as records:
        for line in records:
            record = json.loads(line)
            case_id = record["case_id"]
            if case_id not in gt_cache:
                gt_cache[case_id] = voxelize_source(actors[case_id], 64)
            binary.seek(int(record["offset"]))
            packed = binary.read(int(record["length"]))
            pred = np.unpackbits(np.frombuffer(packed, dtype=np.uint8), bitorder="little")[: 64 ** 3].reshape((64, 64, 64)).astype(bool)
            metrics = evaluate_geometry(gt_cache[case_id], pred, True, diagonal)
            rows.append({
                "case_id": case_id,
                "family": record["family"],
                "stratum": record["stratum"],
                "condition": record["condition"],
                "method": record["method"],
                "status": "pass",
                "inference_ms": record["inference_ms"],
                **metrics,
                **{key: record["metadata"].get(key, "") for key in ("evaluations", "objective", "primitive_count", "triangle_equiv", "descriptor_bytes")},
            })
    output = RESULTS_ROOT / "raw_metrics.csv"
    fieldnames = list(rows[0].keys())
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "schema": "sppa-mvfit-test-metrics-v1",
        "provenance": "synthetic_geometry",
        "split": "held_out_confirmatory",
        "record_count": len(rows),
        "sealed_output_manifest_sha256": sha256_file(sealed_path),
        "external_protocol_pass_sha256": sha256_file(AUDIT_PATH),
        "pretest_freeze_sha256": sha256_file(PACKAGE_ROOT / "pretest_freeze.json"),
        "raw_metrics_sha256": sha256_file(output),
    }
    (RESULTS_ROOT / "evaluation_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
