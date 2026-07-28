from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
LOG_ROOT = REPO / "pipeline" / "logs" / "zero_trust"


def latest_run() -> Path:
    pointer = LOG_ROOT / "LATEST_RUN.txt"
    text = pointer.read_text(encoding="utf-8", errors="replace").strip()
    path = Path(text)
    return path if path.is_absolute() else LOG_ROOT / path


def iter_events(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def bbox_area(det: dict[str, Any]) -> float:
    box = det.get("bbox")
    try:
        if isinstance(box, dict):
            return max(0.0, float(box["x2"]) - float(box["x1"])) * max(0.0, float(box["y2"]) - float(box["y1"]))
        if isinstance(box, list) and len(box) >= 4:
            return max(0.0, float(box[2]) - float(box[0])) * max(0.0, float(box[3]) - float(box[1]))
    except Exception:
        return 0.0
    return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize a zero_trust vision run.")
    parser.add_argument("run", nargs="?", type=Path, help="Run directory. Defaults to LATEST_RUN.txt.")
    parser.add_argument("--tail", type=int, default=12)
    args = parser.parse_args()

    run = (args.run or latest_run()).resolve()
    events_path = run / "vision" / "events.jsonl"
    kind_counts: Counter[str] = Counter()
    detection_counts: Counter[str] = Counter()
    outgoing_counts: Counter[str] = Counter()
    best_by_type: dict[str, dict[str, Any]] = {}
    biker_tail: list[dict[str, Any]] = []
    lines = 0

    for event in iter_events(events_path):
        lines += 1
        kind = str(event.get("kind") or "")
        kind_counts[kind] += 1
        frame = event.get("frame")
        for det in event.get("detections") or []:
            if not isinstance(det, dict):
                continue
            typ = str(det.get("type") or "unknown")
            detection_counts[typ] += 1
            item = {
                "frame": frame,
                "type": typ,
                "confidence": det.get("confidence"),
                "bbox": det.get("bbox"),
                "area": bbox_area(det),
                "distance": det.get("distance"),
            }
            current = best_by_type.get(typ)
            if current is None or float(item["area"] or 0.0) > float(current.get("area") or 0.0):
                best_by_type[typ] = item
            if typ == "biker":
                biker_tail.append(item)
                if len(biker_tail) > args.tail:
                    biker_tail = biker_tail[-args.tail:]
        outgoing = event.get("outgoing") or []
        if isinstance(outgoing, list):
            for det in outgoing:
                if isinstance(det, dict):
                    outgoing_counts[str(det.get("type") or "unknown")] += 1

    payload = {
        "run": str(run),
        "events_path": str(events_path),
        "events_exists": events_path.exists(),
        "lines": lines,
        "kind_counts": dict(kind_counts),
        "detection_counts": dict(detection_counts),
        "outgoing_counts": dict(outgoing_counts),
        "best_by_type": best_by_type,
        "biker_tail": biker_tail,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
