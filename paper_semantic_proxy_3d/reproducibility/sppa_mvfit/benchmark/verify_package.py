from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = PACKAGE_ROOT.parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from benchmark.run_benchmark import CONDITIONS, METHODS, canonical_json, load_development, sha256_bytes, sha256_file  # noqa: E402
from source.source_generators import voxelize_source  # noqa: E402


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def verify_static_boundary() -> None:
    source_files = list((PACKAGE_ROOT / "source").glob("*.py"))
    method_files = list((PACKAGE_ROOT / "method").glob("*.py"))
    for path in source_files:
        if any(name == "method" or name.startswith("method.") for name in imports(path)):
            fail(f"source imports method: {path}")
    for path in method_files:
        if any(name == "source" or name.startswith("source.") for name in imports(path)):
            fail(f"method imports source: {path}")


def verify_no_machine_paths() -> None:
    backslash = chr(92)
    needles = ("D:" + backslash, "C:" + backslash + "Users" + backslash, "D:/" + "Deep-AeroTwin", "AYTE" + " DOCTOR")
    for path in PACKAGE_ROOT.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix.lower() in {".npy", ".png", ".pdf", ".pyc"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in needles:
            if needle in text:
                fail(f"machine-specific path {needle!r} in {path.relative_to(PACKAGE_ROOT)}")


def verify_no_test_artifacts() -> None:
    forbidden = [PACKAGE_ROOT / "data" / "test", PACKAGE_ROOT / "results" / "test", PACKAGE_ROOT / "test_seed_manifest.json"]
    for path in forbidden:
        if path.exists():
            fail(f"test artifact exists before gate: {path}")


def verify_development() -> None:
    rows, masks = load_development()
    if len(rows) != 144 or masks.shape != (144, len(CONDITIONS), 2, 96, 96):
        fail(f"development dimensions drift: rows={len(rows)} masks={masks.shape}")
    for index, row in enumerate(rows):
        actor_hash = sha256_bytes(canonical_json(row["actor"]).encode("utf-8"))
        if actor_hash != row["actor_sha256"]:
            fail(f"actor hash drift: {row['case_id']}")
        gt = voxelize_source(row["actor"], 64)
        gt_hash = sha256_bytes(np.packbits(gt, bitorder="little").tobytes())
        if gt_hash != row["gt_64_packbits_sha256"]:
            fail(f"GT hash drift: {row['case_id']}")
        for condition_index, condition in enumerate(CONDITIONS):
            mask_hash = sha256_bytes(np.packbits(masks[index, condition_index], bitorder="little").tobytes())
            if mask_hash != row["mask_sha256"][condition]:
                fail(f"mask hash drift: {row['case_id']} {condition}")
    dataset_manifest = json.loads((PACKAGE_ROOT / "data" / "development" / "dataset_manifest.json").read_text(encoding="utf-8"))
    for filename, expected in dataset_manifest["files"].items():
        observed = sha256_file(PACKAGE_ROOT / "data" / "development" / filename)
        if observed != expected:
            fail(f"dataset file hash drift: {filename}")
    raw_path = PACKAGE_ROOT / "results" / "development" / "raw_metrics.csv"
    if raw_path.exists():
        with raw_path.open("r", encoding="utf-8", newline="") as handle:
            raw_rows = list(csv.DictReader(handle))
        expected_rows = 144 * len(CONDITIONS) * len(METHODS)
        if len(raw_rows) != expected_rows:
            fail(f"raw row count {len(raw_rows)} != {expected_rows}")
        if any(row["status"] not in {"pass", "exception"} for row in raw_rows):
            fail("unknown raw status")


def write_integrity_manifest(development: bool) -> Path:
    files: dict[str, str] = {}
    for path in sorted(PACKAGE_ROOT.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.name == "integrity_manifest.json":
            continue
        files[path.relative_to(PACKAGE_ROOT).as_posix()] = sha256_file(path)
    payload = {
        "schema_version": "SPPA-MVFIT-INTEGRITY-1.0",
        "development_verified": bool(development),
        "test_artifacts_present": False,
        "file_count": len(files),
        "files": files,
    }
    output = PACKAGE_ROOT / "integrity_manifest.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    verify_static_boundary()
    verify_no_machine_paths()
    verify_no_test_artifacts()
    if args.development:
        verify_development()
    output = write_integrity_manifest(args.development)
    print(f"PASS: SPPA-MVFit package verified; manifest={output}")


if __name__ == "__main__":
    main()
