from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = PACKAGE_ROOT.parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from benchmark.run_benchmark import REPO_ROOT, environment_snapshot, sha256_bytes, sha256_file  # noqa: E402
from benchmark.verify_package import verify_development, verify_no_machine_paths, verify_no_test_artifacts, verify_static_boundary  # noqa: E402


def bundle_hash(items: Iterable[tuple[str, str]]) -> str:
    payload = "\n".join(f"{name}\t{digest}" for name, digest in sorted(items)) + "\n"
    return sha256_bytes(payload.encode("utf-8"))


def git_output(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT)


def main() -> None:
    verify_static_boundary()
    verify_no_machine_paths()
    verify_no_test_artifacts()
    verify_development()

    logical_files: dict[str, Path] = {
        "paper/SPPA_PREREGISTRATION_20260715.md": PAPER_ROOT / "SPPA_PREREGISTRATION_20260715.md",
        "paper/SPPA_PROTOCOL_AMENDMENT_01_20260715.md": PAPER_ROOT / "SPPA_PROTOCOL_AMENDMENT_01_20260715.md",
        "paper/SPPA_PROTOCOL_AMENDMENT_02_20260715.md": PAPER_ROOT / "SPPA_PROTOCOL_AMENDMENT_02_20260715.md",
        "paper/SPPA_PROTOCOL_AMENDMENT_03_20260716.md": PAPER_ROOT / "SPPA_PROTOCOL_AMENDMENT_03_20260716.md",
        "paper/SPPA_CONTRIBUTION_SELECTION_20260715.md": PAPER_ROOT / "SPPA_CONTRIBUTION_SELECTION_20260715.md",
        "paper/SPPA_CLAIM_EVIDENCE_MATRIX_20260715.md": PAPER_ROOT / "SPPA_CLAIM_EVIDENCE_MATRIX_20260715.md",
        "paper/editorial_audits/20260715/ROUND_02.md": PAPER_ROOT / "editorial_audits" / "20260715" / "ROUND_02.md",
        "paper/editorial_audits/20260715/ROUND_03.md": PAPER_ROOT / "editorial_audits" / "20260715" / "ROUND_03.md",
        "paper/editorial_audits/20260715/ROUND_04.md": PAPER_ROOT / "editorial_audits" / "20260715" / "ROUND_04.md",
    }
    for path in PACKAGE_ROOT.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.name in {"pretest_freeze.json", "integrity_manifest.json"}:
            continue
        logical_files[f"package/{path.relative_to(PACKAGE_ROOT).as_posix()}"] = path
    missing = [name for name, path in logical_files.items() if not path.exists()]
    if missing:
        raise SystemExit(f"missing freeze inputs: {missing}")
    hashes = {name: sha256_file(path) for name, path in sorted(logical_files.items())}
    method_items = [(name, digest) for name, digest in hashes.items() if name.startswith("package/method/")]
    source_items = [(name, digest) for name, digest in hashes.items() if name.startswith("package/source/")]
    analysis_items = [
        (name, digest)
        for name, digest in hashes.items()
        if name.startswith("package/benchmark/") or name == "package/protocol_config.json"
    ]
    development_items = [
        (name, digest)
        for name, digest in hashes.items()
        if name.startswith("package/data/development/") or name.startswith("package/results/development/")
    ]
    status = git_output("status", "--porcelain=v1", "-z")
    diff = git_output("diff", "--binary", "--no-ext-diff")
    payload = {
        "schema_version": "SPPA-MVFIT-PRETEST-FREEZE-1.0",
        "created_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "provenance": "synthetic_geometry",
        "test_seed_fetched": False,
        "test_artifacts_present": False,
        "confirmatory_test_executed": False,
        "protocol_gate": "pending_local_triple_role_pass_after_amendment_03",
        "git": {
            "head": git_output("rev-parse", "HEAD").decode("ascii").strip(),
            "branch": git_output("branch", "--show-current").decode("utf-8").strip(),
            "dirty": bool(status),
            "status_porcelain_z_sha256": sha256_bytes(status),
            "tracked_diff_binary_sha256": sha256_bytes(diff),
            "clean_clone_release_ready": False,
            "boundary": "This freeze records the preserved dirty checkout; it is not a clean release commit.",
        },
        "environment": environment_snapshot(),
        "bundle_hashes": {
            "method": bundle_hash(method_items),
            "source": bundle_hash(source_items),
            "analysis": bundle_hash(analysis_items),
            "development_data_and_results": bundle_hash(development_items),
            "all_inputs": bundle_hash(hashes.items()),
        },
        "files": hashes,
    }
    output = PACKAGE_ROOT / "pretest_freeze.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pretest_freeze": str(output), "sha256": sha256_file(output), **payload["bundle_hashes"]}, indent=2))


if __name__ == "__main__":
    main()
