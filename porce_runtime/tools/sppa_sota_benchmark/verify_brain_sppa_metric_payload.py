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
os.environ.setdefault("PORCE_OBSTACLE_TOKEN_REQUIRED", "0")

import flight_controller as brain  # noqa: E402


def main() -> int:
    out_dir = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_geometric_projection" / "20260703_metric_payload_bridge"
    out_dir.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    payload = {
        "obstacles": [
            {
                "id": 9001,
                "source_id": 9001,
                "source": "vision",
                "type": "vehicle",
                "lat": 40.00001,
                "lon": -3.00002,
                "distance": 12.5,
                "confidence": 0.82,
                "bbox": {"x1": 400, "y1": 450, "x2": 600, "y2": 550},
                "world_m": {"north": 12.0, "east": -3.0, "up": 1.4},
                "yaw_deg": 91.0,
                "sppa_metric_dims_m": {"length": 4.0, "width": 2.0, "height": 1.6},
                "sppa_footprint_source": "bbox_ground_projected_quad",
                "sppa_descriptor_id": "sppa-test-descriptor",
                "sppa_descriptor_json": "{\"descriptor_schema\":\"SPPA-DESC-0.2\",\"descriptor_id\":\"sppa-test-descriptor\",\"parts\":[]}",
            }
        ]
    }

    with brain.app.test_client() as client:
        post = client.post("/api/obstacles", json=payload)
        if post.status_code != 200:
            failures.append(f"post_status:{post.status_code}")
        ui = client.get("/api/ui/data")
        if ui.status_code != 200:
            failures.append(f"ui_status:{ui.status_code}")
            data = {}
        else:
            data = ui.get_json() or {}

    obstacles = data.get("obstacles") or []
    if not obstacles:
        failures.append("no_obstacles_returned")
        observed = {}
    else:
        observed = obstacles[0]

    world_m = observed.get("world_m") or {}
    if round(float(world_m.get("north", 999.0)), 3) != 12.0:
        failures.append(f"world_m_north_not_preserved:{world_m}")
    if round(float(world_m.get("east", 999.0)), 3) != -3.0:
        failures.append(f"world_m_east_not_preserved:{world_m}")
    if round(float(world_m.get("up", 999.0)), 3) != 1.4:
        failures.append(f"world_m_up_not_preserved:{world_m}")
    if round(float(observed.get("yaw_deg", -1.0)), 3) != 91.0:
        failures.append(f"yaw_deg_not_preserved:{observed.get('yaw_deg')}")
    if observed.get("sppa_descriptor_json") != payload["obstacles"][0]["sppa_descriptor_json"]:
        failures.append("sppa_descriptor_json_not_preserved")
    dims = observed.get("sppa_metric_dims_m") or {}
    if round(float(dims.get("length", -1.0)), 3) != 4.0:
        failures.append(f"sppa_metric_dims_not_preserved:{dims}")

    report = {
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "observed_obstacle": observed,
        "claim_boundary": "Flask test-client metadata preservation only; does not start live MAVLink, network polling, or Unreal.",
    }
    (out_dir / "brain_sppa_metric_payload_summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "brain_sppa_metric_payload_summary.md").write_text(
        "\n".join(
            [
                "# Brain SPPA Metric Payload Bridge",
                "",
                f"- Status: {report['status']}",
                f"- Failures: {len(failures)}",
                "",
                "Boundary: Flask test-client metadata preservation only.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
