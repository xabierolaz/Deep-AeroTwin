"""Validate synthetic Pipeline B replay payloads against the intended contract.

This script intentionally uses only the Python standard library. It performs a
focused structural validation instead of full JSON-Schema evaluation, so it can
run on the paper machine without adding dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "replay" / "generated" / "pipeline_b_degraded_link_replay.jsonl"
OUT = ROOT / "outputs" / "contract_validation_summary.json"


def has_position(obs: dict) -> bool:
    world = obs.get("world_m")
    if isinstance(world, dict) and world.get("north") is not None and world.get("east") is not None:
        return True
    if obs.get("world_north_m") is not None and obs.get("world_east_m") is not None:
        return True
    if obs.get("lat") is not None and obs.get("lon") is not None:
        return True
    return False


def validate_obstacle(obs: dict, line_no: int, idx: int) -> list[str]:
    errors = []
    for key in ("source", "type", "confidence"):
        if key not in obs:
            errors.append(f"line {line_no} obstacle {idx}: missing {key}")
    if not has_position(obs):
        errors.append(f"line {line_no} obstacle {idx}: missing position")
    confidence = obs.get("confidence")
    if not isinstance(confidence, (int, float)) or not (0 <= float(confidence) <= 1):
        errors.append(f"line {line_no} obstacle {idx}: confidence outside [0,1]")
    if "source_id" not in obs and "id" not in obs:
        errors.append(f"line {line_no} obstacle {idx}: missing source_id/id")
    return errors


def main() -> None:
    if not REPLAY.exists():
        raise SystemExit(f"Replay file missing: {REPLAY}. Run pipeline_b_generate_replay.py first.")

    total_payloads = 0
    total_obstacles = 0
    errors: list[str] = []
    first_nonempty_payload: dict | None = None

    with REPLAY.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            total_payloads += 1
            payload = json.loads(line)
            if "obstacles" not in payload or not isinstance(payload["obstacles"], list):
                errors.append(f"line {line_no}: missing obstacles[]")
                continue
            if "timestamp_s" not in payload:
                errors.append(f"line {line_no}: missing timestamp_s")
            if payload["obstacles"] and first_nonempty_payload is None:
                first_nonempty_payload = payload
            for idx, obs in enumerate(payload["obstacles"]):
                total_obstacles += 1
                errors.extend(validate_obstacle(obs, line_no, idx))

    summary = {
        "status": "pass" if not errors else "fail",
        "scope": "synthetic_software_only_contract_validation",
        "replay": str(REPLAY),
        "total_payloads": total_payloads,
        "total_obstacles": total_obstacles,
        "error_count": len(errors),
        "errors": errors[:50],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    if first_nonempty_payload is not None:
        (ROOT / "outputs" / "sample_post_obstacles_payload.json").write_text(
            json.dumps(first_nonempty_payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
