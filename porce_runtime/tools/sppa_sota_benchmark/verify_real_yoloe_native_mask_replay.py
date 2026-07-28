from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPLAY_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "benchmarks"
    / "results"
    / "real_image_assumed_flight_replay.json"
)
DEFAULT_DETECTOR_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_detection_reference"
    / "20260703_yoloe26s_universal_open_vocab_cpu"
    / "sppa_open_vocab_detector_probe.json"
)
DEFAULT_OUT = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_geometric_projection"
    / "20260704_real_yoloe_native_mask_replay"
    / "real_yoloe_native_mask_replay_verify.json"
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def detector_mask_stats(detector_data: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for image in detector_data.get("images", []):
        detections = image.get("detections") or []
        native = [
            det
            for det in detections
            if isinstance(det.get("mask_polygon_px"), list)
            and len(det.get("mask_polygon_px") or []) >= 3
        ]
        rows.append(
            {
                "image": image.get("image"),
                "detections": len(detections),
                "native_mask_detections": len(native),
                "selected_detector_label": (image.get("selected_tag") or {}).get("detector_label"),
            }
        )
    return {
        "images": len(rows),
        "rows": rows,
        "images_with_native_masks": sum(1 for row in rows if row["native_mask_detections"] > 0),
    }


def verify(replay: dict[str, Any], detector: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    rows = replay.get("rows") or []
    if len(rows) != 4:
        failures.append(f"expected_4_replay_rows_got_{len(rows)}")
    for row in rows:
        case_id = row.get("case_id")
        if not row.get("native_detector_mask_available"):
            failures.append(f"{case_id}:native_detector_mask_missing")
        if int(row.get("native_detector_mask_point_count") or 0) < 3:
            failures.append(f"{case_id}:native_detector_mask_too_few_points")
        if row.get("mask_path_used") != "native_yoloe_detector_mask":
            failures.append(f"{case_id}:mask_path_not_native:{row.get('mask_path_used')}")
        source = str(row.get("sppa_observation_metric_evidence_source") or "")
        if not source.startswith("real_mask_ground_projected"):
            failures.append(f"{case_id}:metric_source_not_real_mask:{source}")
        if not row.get("sppa_descriptor_has_mask_polygon"):
            failures.append(f"{case_id}:descriptor_missing_mask_polygon")
        if row.get("metric_ground_truth") is not False or row.get("telemetry_is_measured") is not False:
            failures.append(f"{case_id}:claim_boundary_flags_not_false")
    det_stats = detector_mask_stats(detector)
    if det_stats["images_with_native_masks"] < 4:
        failures.append(f"detector_native_masks_not_present_for_all_images:{det_stats['images_with_native_masks']}/4")
    return {
        "schema": "SPPA-REAL-YOLOE-NATIVE-MASK-REPLAY-VERIFY-0.1",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "replay_rows": len(rows),
        "replay_passed_count": replay.get("passed_count"),
        "detector_mask_stats": det_stats,
        "case_rows": [
            {
                "case_id": row.get("case_id"),
                "mask_path_used": row.get("mask_path_used"),
                "native_detector_mask_point_count": row.get("native_detector_mask_point_count"),
                "metric_source": row.get("sppa_observation_metric_evidence_source"),
                "descriptor_mask_point_count": row.get("sppa_descriptor_mask_point_count"),
                "metric_dims_m": row.get("sppa_metric_dims_m"),
                "native_mask_quality_score": (row.get("native_detector_mask") or {}).get("quality_score"),
            }
            for row in rows
        ],
        "claim_boundary": (
            "Verifies native YOLOE/Ultralytics mask polygons are consumed by SPPA-OBS and preserved in descriptors. "
            "It does not verify mask correctness against ground-truth segmentation, measured flight telemetry, or 3D reference geometry."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify real YOLOE native mask replay path.")
    parser.add_argument("--replay-json", type=Path, default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--detector-json", type=Path, default=DEFAULT_DETECTOR_JSON)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    replay_json = args.replay_json if args.replay_json.is_absolute() else ROOT / args.replay_json
    detector_json = args.detector_json if args.detector_json.is_absolute() else ROOT / args.detector_json
    out = args.out if args.out.is_absolute() else ROOT / args.out
    report = verify(read_json(replay_json), read_json(detector_json))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md = out.with_suffix(".md")
    lines = [
        "# Real YOLOE Native Mask Replay Verify",
        "",
        f"- Status: `{report['status']}`",
        f"- Replay rows: {report['replay_rows']}",
        f"- Detector images with native masks: {report['detector_mask_stats']['images_with_native_masks']}/4",
        "",
        "| Case | Mask path | Metric source | Native pts | Descriptor pts |",
        "|---|---|---|---:|---:|",
    ]
    for row in report["case_rows"]:
        lines.append(
            f"| `{row['case_id']}` | `{row['mask_path_used']}` | `{row['metric_source']}` | "
            f"{row['native_detector_mask_point_count']} | {row['descriptor_mask_point_count']} |"
        )
    lines += ["", "Boundary: " + report["claim_boundary"], ""]
    if report["failures"]:
        lines += ["## Failures", ""]
        lines += [f"- {failure}" for failure in report["failures"]]
    md.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": report["status"], "failures": report["failures"], "json": str(out)}, indent=2))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
