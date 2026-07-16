"""Derive the held-out case seeds from a supplied NIST Beacon pulse.

The command is deliberately unusable until the external protocol-pass record
exists and binds the exact pre-test freeze. It never downloads a pulse itself;
the raw pulse JSON must be supplied and is copied into the resulting manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from benchmark.test_authorization import AUDIT_PATH, FREEZE_PATH, PACKAGE_ROOT, sha256_file

FAMILIES = ("compact_vehicle", "articulated_vehicle", "quadruped", "branching_vertical", "lattice_tower", "rider_cycle")
STRATA = ("csg_id", "implicit_ood")


def ordered_case_ids() -> list[str]:
    return [
        f"test-{stratum}-{family}-{index:03d}"
        for stratum in STRATA
        for family in FAMILIES
        for index in range(20)
    ]


def pulse_output(payload: dict) -> str:
    for key_path in (("pulse", "outputValue"), ("pulse", "output_value"), ("outputValue",), ("output_value",)):
        current = payload
        for key in key_path:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            if isinstance(current, str) and current:
                return current
    raise ValueError("raw NIST JSON has no pulse.outputValue/outputValue string")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pulse-json", type=Path, required=True)
    args = parser.parse_args()
    if not AUDIT_PATH.exists() or not FREEZE_PATH.exists():
        raise SystemExit("REFUSED: external protocol PASS and pre-test freeze are required before seed derivation")
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if audit.get("verdict") != "PASS":
        raise SystemExit("REFUSED: protocol audit is not PASS")
    pulse = json.loads(args.pulse_json.read_text(encoding="utf-8"))
    output_value = pulse_output(pulse)
    case_ids = ordered_case_ids()
    case_seeds = [
        int.from_bytes(hashlib.sha256(output_value.encode("utf-8") + b"SPPA-MVFIT-20260715" + str(index).encode("ascii")).digest()[:8], "big")
        for index in range(len(case_ids))
    ]
    manifest = {
        "schema": "sppa-mvfit-test-seed-v1",
        "source": "NIST Randomness Beacon pulse supplied after external protocol PASS",
        "raw_pulse": pulse,
        "raw_pulse_sha256": hashlib.sha256(args.pulse_json.read_bytes()).hexdigest().upper(),
        "method": "uint64(SHA256(UTF8(outputValue) || UTF8(SPPA-MVFIT-20260715) || UTF8(decimal_index))[0:8])",
        "case_ids": case_ids,
        "case_seeds": case_seeds,
        "external_protocol_pass_sha256": sha256_file(AUDIT_PATH),
        "pretest_freeze_sha256": sha256_file(FREEZE_PATH),
    }
    output = PACKAGE_ROOT / "test_seed_manifest.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "case_count": len(case_ids), "raw_pulse_sha256": manifest["raw_pulse_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
