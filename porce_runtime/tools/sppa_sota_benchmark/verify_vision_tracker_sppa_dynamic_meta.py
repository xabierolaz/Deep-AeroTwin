#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

os.environ.setdefault("PORCE_MOCK_MAVLINK", "0")

from vision_system import VisionSystem  # noqa: E402


def _det(conf: float, north: float, east: float, yaw_deg: float, source: str) -> dict:
    return {
        "lat": 40.0 + north * 1e-5,
        "lon": -3.0 + east * 1e-5,
        "distance": 20.0,
        "type": "vehicle",
        "confidence": float(conf),
        "source": "vision",
        "bbox": {"x1": 400, "y1": 450, "x2": 600, "y2": 550},
        "cx": 500.0,
        "cy": 500.0,
        "world_m": {"north": float(north), "east": float(east), "up": 1.2},
        "world_north_m": float(north),
        "world_east_m": float(east),
        "world_up_m": 1.2,
        "yaw_deg": float(yaw_deg),
        "heading_deg": float(yaw_deg),
        "sppa_footprint_source": source,
        "sppa_metric_dims_m": {"length": 4.0, "width": 2.0, "height": 1.5},
        "sppa_scale_source": source,
        "sppa_descriptor_id": f"descriptor-{source}",
        "sppa_descriptor_json": (
            '{"descriptor_schema":"SPPA-DESC-0.2","descriptor_id":"descriptor-'
            + source
            + '","parts":[]}'
        ),
    }


def main() -> int:
    out_dir = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_geometric_projection" / "20260703_tracker_dynamic_meta"
    out_dir.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    vision = VisionSystem.__new__(VisionSystem)
    vision._tracks = {}
    vision._next_track_id = 1

    first = _det(0.95, 10.0, 2.0, 45.0, "first_high_conf")
    seen_1 = vision._update_tracks_from_detections([first], 100.0)
    if seen_1 != {1}:
        failures.append(f"unexpected_first_seen:{seen_1}")

    second = _det(0.70, 14.0, 5.0, 91.0, "second_lower_conf")
    seen_2 = vision._update_tracks_from_detections([second], 100.2)
    if seen_2 != {1}:
        failures.append(f"unexpected_second_seen:{seen_2}")

    track = vision._tracks.get(1)
    observed = dict(track.semantic_meta or {}) if track is not None else {}
    if track is None:
        failures.append("track_missing")
    if observed.get("sppa_footprint_source") != "second_lower_conf":
        failures.append(f"dynamic_source_not_refreshed:{observed.get('sppa_footprint_source')}")
    world_m = observed.get("world_m") or {}
    if round(float(world_m.get("north", -999.0)), 3) != 14.0:
        failures.append(f"world_m_north_not_refreshed:{world_m}")
    if round(float(world_m.get("east", -999.0)), 3) != 5.0:
        failures.append(f"world_m_east_not_refreshed:{world_m}")
    if round(float(observed.get("yaw_deg", -999.0)), 3) != 91.0:
        failures.append(f"yaw_not_refreshed:{observed.get('yaw_deg')}")
    if observed.get("sppa_descriptor_id") != "descriptor-second_lower_conf":
        failures.append(f"descriptor_not_refreshed:{observed.get('sppa_descriptor_id')}")

    report = {
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "observed_semantic_meta": observed,
        "claim_boundary": (
            "Tracker-only regression using synthetic detections; it verifies SPPA dynamic metadata refresh "
            "without loading YOLO, camera capture, or network publishing."
        ),
    }
    (out_dir / "vision_tracker_sppa_dynamic_meta_summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "vision_tracker_sppa_dynamic_meta_summary.md").write_text(
        "\n".join(
            [
                "# Vision Tracker SPPA Dynamic Metadata",
                "",
                f"- Status: {report['status']}",
                f"- Failures: {len(failures)}",
                "",
                "Boundary: synthetic tracker-only regression.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
