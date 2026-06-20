from __future__ import annotations

import argparse
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
LOG_ROOT = REPO / "pipeline" / "logs" / "zero_trust"


def latest_run() -> Path:
    text = (LOG_ROOT / "LATEST_RUN.txt").read_text(encoding="utf-8", errors="replace").strip()
    path = Path(text)
    return path if path.is_absolute() else LOG_ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description="Print one vision_frame event from a run.")
    parser.add_argument("frame", type=int)
    parser.add_argument("--run", type=Path, default=None)
    args = parser.parse_args()
    run = (args.run or latest_run()).resolve()
    events = run / "vision" / "events.jsonl"
    for line in events.open("r", encoding="utf-8", errors="replace"):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("kind") == "vision_frame" and int(event.get("frame") or -1) == args.frame:
            print(json.dumps(event, indent=2, sort_keys=True))
            return 0
    print(json.dumps({"run": str(run), "frame": args.frame, "found": False}, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
