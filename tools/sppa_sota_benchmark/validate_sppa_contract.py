from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def path_exists(payload: dict[str, Any], dotted_path: str) -> bool:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def validate(payload: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    missing = [key for key in schema.get("required", []) if key not in payload]
    missing.extend(path for path in schema.get("x-requiredPaths", []) if not path_exists(payload, path))
    const_errors = []
    for key, spec in schema.get("properties", {}).items():
        if isinstance(spec, dict) and "const" in spec and payload.get(key) != spec["const"]:
            const_errors.append(f"{key}!={spec['const']}")
    return missing + const_errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate SPPA descriptor/update JSONL samples against required contract fields.")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--jsonl", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    payloads = load_jsonl(Path(args.jsonl))
    rows = []
    failed = 0
    for index, payload in enumerate(payloads):
        errors = validate(payload, schema)
        failed += 1 if errors else 0
        rows.append(
            {
                "index": index,
                "id": payload.get("descriptor_id"),
                "status": "ok" if not errors else "failed",
                "error_count": len(errors),
                "errors": errors,
            }
        )

    result = {"jsonl": args.jsonl, "schema": args.schema, "total": len(payloads), "failed": failed, "rows": rows}
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
