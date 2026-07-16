"""Read-only check that the release can be reconstructed from Git."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path.cwd().resolve()
while not (REPO_ROOT / ".git").exists() and REPO_ROOT != REPO_ROOT.parent:
    REPO_ROOT = REPO_ROOT.parent

PACKAGE_FILES = [
    "README.md",
    "requirements-lock.txt",
    "protocol_config.json",
    "method/graphs.json",
    "method/sppa_mvfit.py",
    "source/source_generators.py",
    "benchmark/metrics.py",
    "benchmark/run_benchmark.py",
    "benchmark/verify_package.py",
    "benchmark/test_authorization.py",
    "benchmark/check_clean_clone_gate.py",
    "benchmark/export_paper_tables.py",
    "benchmark/analyze_test.py",
    "benchmark/evaluate_test.py",
    "benchmark/run_test_methods.py",
    "benchmark/generate_test_data.py",
    "benchmark/prepare_test_seed_manifest.py",
    "tests/test_contract.py",
    "results/test/confirmatory_summary.json",
    "results/test/raw_metrics.csv",
    "pretest_freeze.json",
    "test_seed_manifest.json",
]
PAPER_FILES = [
    "SPPA_PROTOCOL_AMENDMENT_01_20260715.md",
    "SPPA_PROTOCOL_AMENDMENT_02_20260715.md",
    "SPPA_PROTOCOL_AMENDMENT_03_20260716.md",
    "SPPA_CONTRIBUTION_SELECTION_20260715.md",
    "SPPA_CLAIM_EVIDENCE_MATRIX_20260715.md",
    "SPPA_PREREGISTRATION_20260715.md",
    "SPPA_SUBMISSION_STATUS_20260716.md",
    "RELEASE_MANIFEST.md",
    "semantic_proxy_3d_paper.tex",
    "semantic_proxy_3d_submission_supplement.tex",
    "semantic_proxy_3d_references.bib",
    "tools/reproduce_sppa_mvfit_paper.py",
    "editorial_audits/20260715/PROTOCOL_AUDIT_PASS.json",
    "benchmarks/results/sppa_mvfit_h1_summary.tex",
    "benchmarks/results/sppa_mvfit_method_means.tex",
    "benchmarks/results/sppa_mvfit_secondary_deltas.tex",
]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, encoding="utf-8", errors="replace")


def tracked(logical: str) -> bool:
    return subprocess.run(["git", "ls-files", "--error-unmatch", "--", logical], cwd=REPO_ROOT, capture_output=True, text=True).returncode == 0


def main() -> int:
    missing: list[str] = []
    untracked: list[str] = []
    for relative in PACKAGE_FILES:
        logical = f"paper_semantic_proxy_3d/reproducibility/sppa_mvfit/{relative}"
        if not (PACKAGE_ROOT / relative).exists():
            missing.append(logical)
        elif not tracked(logical):
            untracked.append(logical)
    for relative in PAPER_FILES:
        logical = f"paper_semantic_proxy_3d/{relative}"
        if not (PACKAGE_ROOT / ".." / ".." / relative).resolve().exists():
            missing.append(logical)
        elif not tracked(logical):
            untracked.append(logical)
    status = git(
        "status",
        "--porcelain=v1",
        "--",
        "paper_semantic_proxy_3d/reproducibility/sppa_mvfit",
        *[f"paper_semantic_proxy_3d/{p}" for p in PAPER_FILES],
    )
    # The gate report is rewritten by this script; do not treat it as a dirty source file.
    modified = [
        line
        for line in status.splitlines()
        if line
        and not line.startswith("??")
        and "clean_clone_gate.json" not in line
    ]
    report = {
        "schema": "sppa-clean-clone-gate-v1",
        "required_count": len(PACKAGE_FILES) + len(PAPER_FILES),
        "missing": missing,
        "untracked": untracked,
        "modified": modified,
        "pass": not missing and not untracked and not modified,
        "boundary": "Read-only; no clone, reset, staging, or worktree mutation.",
    }
    output = PACKAGE_ROOT / "clean_clone_gate.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
