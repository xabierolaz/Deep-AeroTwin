#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

from geo_projector import GeoProjector  # noqa: E402
from sppa_runtime_descriptor import build_sppa_descriptor_payload  # noqa: E402


def axial_error_deg(a: float, b: float) -> float:
    delta = abs((float(a) - float(b)) % 180.0)
    return min(delta, 180.0 - delta)


def assert_close(name: str, value: float, expected: float, tol: float, failures: list[str]) -> None:
    if not math.isfinite(float(value)) or abs(float(value) - float(expected)) > float(tol):
        failures.append(f"{name}: got {value:.6f}, expected {expected:.6f} +/- {tol:.6f}")


def main() -> int:
    out_dir = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_geometric_projection" / "20260703_metric_footprint_bridge"
    out_dir.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    camera = {
        "image_height": 1000,
        "image_width": 1000,
        "drone_yaw_deg": 0.0,
        "drone_pitch_deg": 0.0,
        "drone_roll_deg": 0.0,
        "alt_agl_m": 10.0,
        "camera_vfov_deg": 90.0,
        "mount_roll_deg": 0.0,
        "mount_pitch_deg": -90.0,
        "mount_yaw_deg": 0.0,
        "max_range_m": 100.0,
    }
    bbox = {"x1": 400, "y1": 450, "x2": 600, "y2": 550}

    projected_center = GeoProjector.pixel_to_gps(
        500,
        500,
        drone_lat=40.0,
        drone_lon=-3.0,
        clamp_to_max_range=False,
        max_range_margin_m=0.0,
        **camera,
    )
    if projected_center is None:
        failures.append("center pixel did not intersect ground")
    else:
        assert_close("center_distance_m", projected_center[2], 0.0, 1e-5, failures)

    footprint = GeoProjector.bbox_to_ground_footprint_m(bbox, **camera)
    if footprint is None:
        failures.append("bbox footprint projection returned None")
    else:
        assert_close("footprint_length_m", footprint["length_m"], 4.0, 0.05, failures)
        assert_close("footprint_width_m", footprint["width_m"], 2.0, 0.05, failures)
        if axial_error_deg(float(footprint["orientation_deg_axial"]), 90.0) > 0.05:
            failures.append(
                f"footprint_yaw_deg: got {footprint['orientation_deg_axial']:.6f}, expected axial 90 deg"
            )

    descriptor_payload = {}
    descriptor = None
    if footprint is not None:
        descriptor_payload = build_sppa_descriptor_payload(
            label="vehicle",
            confidence=0.84,
            bbox=bbox,
            image_width=1000,
            image_height=1000,
            world_m={"north": 0.0, "east": 0.0, "up": 1.4},
            metric_dims_m={"length": footprint["length_m"], "width": footprint["width_m"]},
            metric_dims_source=footprint["source"],
            footprint_m=footprint,
            yaw_deg=footprint["orientation_deg_axial"],
            track_id="synthetic_metric_vehicle_01",
            frame_id=7,
            timestamp="2026-07-03T12:00:00.000Z",
            max_descriptor_bytes=100000,
        )
        text = descriptor_payload.get("sppa_descriptor_json")
        if not text:
            failures.append(f"descriptor_json_missing:{descriptor_payload.get('sppa_descriptor_error')}")
        else:
            descriptor = json.loads(text)
            resolver = descriptor.get("resolver", {})
            if resolver.get("runtime_llm_used") is not False:
                failures.append("descriptor resolver did not mark runtime_llm_used=false")
            parts = descriptor.get("parts") or []
            if len(parts) < 4:
                failures.append(f"descriptor parts too small: {len(parts)}")
            dims = descriptor.get("scale", {}).get("effective_dims_m") or {}
            assert_close("descriptor_length_m", float(dims.get("length", -1.0)), 4.0, 0.05, failures)
            assert_close("descriptor_width_m", float(dims.get("width", -1.0)), 2.0, 0.05, failures)
            if float(dims.get("height", 0.0) or 0.0) <= 0.15:
                failures.append("descriptor height was not filled from reviewed archetype prior")
            if descriptor.get("scale", {}).get("metric_dims_source") != "bbox_ground_projected_quad":
                failures.append("descriptor metric_dims_source did not preserve projection source")

    report = {
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "camera": camera,
        "bbox": bbox,
        "projected_center": projected_center,
        "footprint": footprint,
        "descriptor_payload_keys": sorted(descriptor_payload.keys()),
        "descriptor_id": None if descriptor is None else descriptor.get("descriptor_id"),
        "descriptor_effective_dims_m": None if descriptor is None else descriptor.get("scale", {}).get("effective_dims_m"),
        "claim_boundary": (
            "Synthetic nadir-camera regression only. It verifies projection math and SPPA descriptor "
            "plumbing, not real YOLOE mask quality, terrain accuracy, or live-flight calibration."
        ),
    }
    (out_dir / "metric_projection_bridge_summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# SPPA UAV Metric Projection Bridge",
        "",
        f"- Status: {report['status']}",
        f"- Footprint length/width: {None if footprint is None else (footprint['length_m'], footprint['width_m'])}",
        f"- Descriptor id: {report['descriptor_id']}",
        f"- Effective dims: {report['descriptor_effective_dims_m']}",
        "",
        "Boundary: synthetic nadir-camera regression only; not real-flight validation.",
    ]
    if failures:
        lines.extend(["", "## Failures", *[f"- {item}" for item in failures]])
    (out_dir / "metric_projection_bridge_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
