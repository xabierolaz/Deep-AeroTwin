"""Hard gates for the held-out test release."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = PACKAGE_ROOT.parents[1]
AUDIT_PATH = PAPER_ROOT / "editorial_audits" / "20260715" / "PROTOCOL_AUDIT_PASS.json"
FREEZE_PATH = PACKAGE_ROOT / "pretest_freeze.json"
SEED_PATH = PACKAGE_ROOT / "test_seed_manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require_test_authorization() -> dict[str, Any]:
    failures: list[str] = []
    if not AUDIT_PATH.exists():
        failures.append(f"missing external protocol-pass record: {AUDIT_PATH}")
    if not FREEZE_PATH.exists():
        failures.append(f"missing pre-test freeze: {FREEZE_PATH}")
    if not SEED_PATH.exists():
        failures.append(f"missing post-audit test-seed manifest: {SEED_PATH}")
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8")) if AUDIT_PATH.exists() else {}
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8")) if FREEZE_PATH.exists() else {}
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8")) if SEED_PATH.exists() else {}
    if audit.get("verdict") != "PASS":
        failures.append("external protocol-pass verdict is not PASS")
    roles = set(audit.get("reviewer_roles", []))
    required_roles = {"methodology_statistics", "clean_clone_reproducibility", "target_journal_editor"}
    if not required_roles.issubset(roles):
        failures.append(f"external protocol pass lacks required roles: {sorted(required_roles - roles)}")
    freeze_hash = sha256_file(FREEZE_PATH) if FREEZE_PATH.exists() else ""
    if audit.get("reviewed_pretest_freeze_sha256") != freeze_hash:
        failures.append("protocol pass does not identify this exact pre-test freeze")
    audit_hash = sha256_file(AUDIT_PATH) if AUDIT_PATH.exists() else ""
    if seed.get("external_protocol_pass_sha256") != audit_hash:
        failures.append("seed manifest is not bound to the external protocol-pass record")
    if seed.get("pretest_freeze_sha256") != freeze_hash:
        failures.append("seed manifest is not bound to this exact pre-test freeze")
    if not isinstance(seed.get("case_seeds"), list) or len(seed.get("case_seeds", [])) != 240:
        failures.append("seed manifest must contain exactly 240 ordered case seeds")
    if failures:
        raise RuntimeError("HELD-OUT TEST LOCKED: " + " | ".join(failures))
    return {"audit": audit, "freeze": freeze, "seed": seed}
