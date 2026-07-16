#!/usr/bin/env python3
"""Strict local reproduction gate for the SPPA-MVFit paper package."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PAPER_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = PAPER_ROOT / "reproducibility" / "sppa_mvfit"
RESULTS = PACKAGE / "results" / "test"
EXPECTED = {
    "pretest_freeze": "8E2ADBF32F299B24CD2A5AB87C74D142E707696F79D18DF0C3332209C3B46CA3",
    "protocol_pass": "2348946BDDB04B8E5CA7D2C845C5F5C45F1AE06F8907E99218ED5E9A379FA74F",
    "sealed_binary": "F870C57D9CC6FF4868EFB25FD2926FA7D19858EAF8CD0E9781F38990D7D145FD",
    "raw_metrics": "57A82D234F55013D76BEF2E36CF2B3F7C5617DD4FA6EF811C2A8447A04C0AD63",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    blockers: list[str] = []

    paths = {
        "pretest_freeze": PACKAGE / "pretest_freeze.json",
        "protocol_pass": PAPER_ROOT / "editorial_audits" / "20260715" / "PROTOCOL_AUDIT_PASS.json",
        "sealed_binary": RESULTS / "sealed_predictions.bin",
        "raw_metrics": RESULTS / "raw_metrics.csv",
        "confirmatory": RESULTS / "confirmatory_summary.json",
        "h1_tex": PAPER_ROOT / "benchmarks" / "results" / "sppa_mvfit_h1_summary.tex",
        "means_tex": PAPER_ROOT / "benchmarks" / "results" / "sppa_mvfit_method_means.tex",
        "amendment03": PAPER_ROOT / "SPPA_PROTOCOL_AMENDMENT_03_20260716.md",
    }
    for name, path in paths.items():
        if not path.exists():
            blockers.append(f"missing {name}: {path}")

    for key, expected in EXPECTED.items():
        path = paths[key]
        if path.exists():
            digest = sha256_file(path)
            if digest != expected:
                blockers.append(f"hash mismatch {key}: got {digest}, expected {expected}")

    if paths["confirmatory"].exists():
        conf = json.loads(paths["confirmatory"].read_text(encoding="utf-8"))
        if conf.get("provenance") != "synthetic_geometry":
            blockers.append("confirmatory provenance is not synthetic_geometry")
        if not conf.get("h1_pass"):
            blockers.append("H1 did not pass in sealed confirmatory summary")
        if conf.get("primary", {}).get("actor_count") != 240:
            blockers.append("confirmatory actor_count is not 240")

    paper = (PAPER_ROOT / "semantic_proxy_3d_paper.tex").read_text(encoding="utf-8")
    for forbidden in (
        "measured flight ground truth",
        "SOTA ranking of image-to-3D",
        "class-agnostic open-set universal",
        "operator benefit proven",
    ):
        if forbidden.lower() in paper.lower():
            blockers.append(f"forbidden claim string present: {forbidden}")

    # Contract tests when strict and pytest is available.
    if args.strict:
        try:
            test_file = PACKAGE / "tests" / "test_contract.py"
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", str(test_file), "-q"],
                cwd=str(PACKAGE),
                capture_output=True,
                text=True,
                check=False,
                env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": str(PACKAGE)},
            )
            if proc.returncode != 0:
                # Fallback: git repo with junction layout.
                ok = False
                errors = [proc.stdout + proc.stderr]
                for start in (Path.cwd().resolve(), *PAPER_ROOT.resolve().parents):
                    if not (start / ".git").exists():
                        continue
                    rel = "paper_semantic_proxy_3d/reproducibility/sppa_mvfit/tests/test_contract.py"
                    if not (start / rel).exists():
                        continue
                    proc2 = subprocess.run(
                        [sys.executable, "-m", "pytest", rel, "-q"],
                        cwd=str(start),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if proc2.returncode == 0:
                        ok = True
                        break
                    errors.append(proc2.stdout + proc2.stderr)
                if not ok:
                    blockers.append("contract tests failed: " + (errors[-1][:300] if errors else "unknown"))
        except Exception as exc:  # pragma: no cover
            blockers.append(f"contract test execution error: {exc}")

    report = {
        "blockers": blockers,
        "blocker_count": len(blockers),
        "h1_pass": True if not any("H1" in b for b in blockers) else False,
        "strict": bool(args.strict),
    }
    print(json.dumps(report, indent=2))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
