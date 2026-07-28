#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

from geo_projector import GeoProjector  # noqa: E402
from sppa_observation import build_sppa_observation_contract, descriptor_kwargs_from_observation  # noqa: E402
from sppa_runtime_descriptor import build_sppa_descriptor_payload  # noqa: E402
from sppa_silhouette import build_image_silhouette_proxy  # noqa: E402


DEFAULT_DETECTOR_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_detection_reference"
    / "20260703_yoloe26s_universal_open_vocab_cpu"
    / "sppa_open_vocab_detector_probe.json"
)
DEFAULT_ANNOTATIONS_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_detection_reference"
    / "20260703_real_input_annotations"
    / "real_input_2d_annotations.json"
)
DEFAULT_OUT_DIR = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_geometric_projection"
    / "20260703_real_image_assumed_flight_replay"
)


ASSUMED_FLIGHT_BY_LABEL = {
    "biker": {"alt_agl_m": 14.0, "drone_yaw_deg": 35.0},
    "tower": {"alt_agl_m": 45.0, "drone_yaw_deg": 12.0},
    "tractor": {"alt_agl_m": 35.0, "drone_yaw_deg": 68.0},
    "tractor_trailer": {"alt_agl_m": 40.0, "drone_yaw_deg": 72.0},
}
DECLARED_HEIGHT_PRIOR_BY_LABEL = {
    "biker": 1.85,
    "tower": 28.0,
    "tractor": 2.6,
    "tractor_trailer": 3.4,
}
COMMON_CAMERA = {
    "drone_pitch_deg": 0.0,
    "drone_roll_deg": 0.0,
    "camera_vfov_deg": 70.0,
    "mount_roll_deg": 0.0,
    "mount_pitch_deg": -90.0,
    "mount_yaw_deg": 0.0,
    "max_range_m": 250.0,
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path | str | None) -> str | None:
    if path is None:
        return None
    p = Path(path)
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def as_bbox(det: dict[str, Any]) -> list[float] | None:
    raw = det.get("xyxy") or det.get("bbox") or det.get("bbox_xyxy")
    if not isinstance(raw, list | tuple) or len(raw) != 4:
        return None
    vals = [float(v) for v in raw]
    if not all(math.isfinite(v) for v in vals):
        return None
    x1, y1, x2, y2 = vals
    if x2 <= x1 or y2 <= y1:
        return None
    return vals


def union_bbox(boxes: list[list[float]]) -> list[float] | None:
    if not boxes:
        return None
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


def select_detector_bbox(image_row: dict[str, Any]) -> tuple[list[float] | None, list[dict[str, Any]], str]:
    selected = image_row.get("selected_tag") or {}
    detector_label = str(selected.get("detector_label") or "").strip().lower()
    detections = list(image_row.get("detections") or [])
    if not detector_label or not detections:
        return None, [], "missing_detector_selection"

    if "+" in detector_label:
        component_labels = [part.strip() for part in detector_label.split("+") if part.strip()]
        used: list[dict[str, Any]] = []
        boxes: list[list[float]] = []
        for component in component_labels:
            candidates = [
                det
                for det in detections
                if str(det.get("class_name", "")).strip().lower() == component
            ]
            candidates.sort(key=lambda det: float(det.get("confidence", 0.0)), reverse=True)
            if not candidates:
                continue
            bbox = as_bbox(candidates[0])
            if bbox is not None:
                used.append(candidates[0])
                boxes.append(bbox)
        return union_bbox(boxes), used, "detector_composite_union"

    candidates = [
        det
        for det in detections
        if str(det.get("class_name", "")).strip().lower() == detector_label
    ]
    candidates.sort(key=lambda det: float(det.get("confidence", 0.0)), reverse=True)
    if candidates:
        bbox = as_bbox(candidates[0])
        if bbox is not None:
            return bbox, [candidates[0]], "detector_single_box"

    detections.sort(key=lambda det: float(det.get("confidence", 0.0)), reverse=True)
    bbox = as_bbox(detections[0]) if detections else None
    return bbox, detections[:1], "detector_top_box_fallback"

def selected_mask_area_px(used_detections: list[dict[str, Any]]) -> float | None:
    values: list[float] = []
    for det in used_detections:
        try:
            value = float(det.get("mask_area_px"))
        except Exception:
            continue
        if math.isfinite(value) and value > 0:
            values.append(value)
    return sum(values) if values else None

def convex_hull(points: list[list[float]]) -> list[list[float]]:
    unique = sorted({(round(float(x), 6), round(float(y), 6)) for x, y in points})
    if len(unique) <= 1:
        return [[x, y] for x, y in unique]

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return [[x, y] for x, y in lower[:-1] + upper[:-1]]

def limit_polygon_points(points: list[list[float]], max_points: int = 64) -> list[list[float]]:
    if len(points) <= max_points:
        return points
    step = max(1, int(math.ceil(len(points) / float(max_points))))
    return points[::step]

def native_detector_mask_from_detections(
    used_detections: list[dict[str, Any]],
    *,
    confidence: float,
) -> dict[str, Any] | None:
    polygons: list[list[list[float]]] = []
    areas: list[float] = []
    for det in used_detections:
        polygon = det.get("mask_polygon_px")
        if isinstance(polygon, list) and len(polygon) >= 3:
            clean: list[list[float]] = []
            for point in polygon:
                try:
                    x, y = point[:2]
                except Exception:
                    continue
                clean.append([float(x), float(y)])
            if len(clean) >= 3:
                polygons.append(clean)
        try:
            area = float(det.get("mask_polygon_area_px2") or det.get("mask_area_px") or 0.0)
        except Exception:
            area = 0.0
        if math.isfinite(area) and area > 0.0:
            areas.append(area)
    if not polygons:
        return None
    if len(polygons) == 1:
        polygon = limit_polygon_points(polygons[0])
        method = "ultralytics_result_masks_xy_single_contour"
    else:
        polygon = limit_polygon_points(convex_hull([point for poly in polygons for point in poly]))
        method = "ultralytics_result_masks_xy_composite_convex_hull"
    if len(polygon) < 3:
        return None
    return {
        "source": "real_detector_mask_yoloe_native_polygon_not_ground_truth",
        "method": method,
        "status": "native_detector_mask_available",
        "quality_score": max(0.0, min(1.0, float(confidence))),
        "area_px2": sum(areas) if areas else None,
        "polygon": polygon,
        "component_count": len(polygons),
        "claim_boundary": (
            "Native YOLOE/Ultralytics mask polygon from real image inference. "
            "It is detector evidence, not ground-truth segmentation."
        ),
    }


def metric_projection(
    bbox: list[float],
    image_size: dict[str, Any],
    flight: dict[str, float],
    declared_height_prior_m: float | None,
) -> tuple[dict[str, Any] | None, dict[str, float] | None, dict[str, float] | None]:
    width = int(image_size["width"])
    height = int(image_size["height"])
    x1, y1, x2, y2 = bbox
    bbox_payload = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
    params = {
        "image_height": height,
        "image_width": width,
        "drone_yaw_deg": flight["drone_yaw_deg"],
        "drone_pitch_deg": flight["drone_pitch_deg"],
        "drone_roll_deg": flight["drone_roll_deg"],
        "alt_agl_m": flight["alt_agl_m"],
        "camera_vfov_deg": flight["camera_vfov_deg"],
        "mount_roll_deg": flight["mount_roll_deg"],
        "mount_pitch_deg": flight["mount_pitch_deg"],
        "mount_yaw_deg": flight["mount_yaw_deg"],
        "max_range_m": flight["max_range_m"],
    }
    footprint = GeoProjector.bbox_to_ground_footprint_m(bbox_payload, **params)
    bottom_center = GeoProjector.pixel_to_ground_offset_m(
        (y1 + y2) / 2.0,
        (x1 + x2) / 2.0,
        **params,
    )
    world_m = None
    if bottom_center is not None:
        world_m = {
            "north": float(bottom_center["north_m"]),
            "east": float(bottom_center["east_m"]),
            "up": 0.0,
        }
    dims = None
    if footprint is not None:
        dims = {
            "length": float(footprint["length_m"]),
            "width": float(footprint["width_m"]),
        }
        if declared_height_prior_m is not None:
            dims["height"] = float(declared_height_prior_m)
    return footprint, world_m, dims


def build_rows(detector_data: dict[str, Any], annotations: dict[str, Any]) -> list[dict[str, Any]]:
    annotations_by_image = {
        str(item.get("image")): item
        for item in annotations.get("items", [])
        if item.get("image")
    }
    rows: list[dict[str, Any]] = []
    for image_row in detector_data.get("images", []):
        image_path = str(image_row.get("image") or "")
        ann = annotations_by_image.get(image_path)
        if ann is None:
            continue
        label = str(ann.get("label") or "unknown")
        flight = dict(COMMON_CAMERA)
        flight.update(ASSUMED_FLIGHT_BY_LABEL.get(label, {"alt_agl_m": 30.0, "drone_yaw_deg": 0.0}))
        flight["telemetry_source"] = "declared_assumed_replay_not_measured"
        flight["telemetry_is_measured"] = False
        declared_height_prior_m = DECLARED_HEIGHT_PRIOR_BY_LABEL.get(label)

        bbox, used_detections, bbox_source = select_detector_bbox(image_row)
        selected = image_row.get("selected_tag") or {}
        detector_runtime_label = str(selected.get("runtime_archetype_id") or selected.get("sppa_tag") or "").strip()
        reviewed_semantic_tag = str(ann.get("reviewed_semantic_tag") or "").strip()
        runtime_label = reviewed_semantic_tag or detector_runtime_label or label
        semantic_text_source = (
            "reviewed_semantic_tag_plus_detector_evidence"
            if reviewed_semantic_tag
            else "detector_normalizer_tag"
        )
        confidence = float(selected.get("confidence") or 0.0)
        failures: list[str] = []
        footprint = None
        world_m = None
        dims = None
        descriptor_payload: dict[str, Any] = {}
        observation: dict[str, Any] | None = None
        bbox_only_observation: dict[str, Any] | None = None
        silhouette: dict[str, Any] | None = None
        native_mask: dict[str, Any] | None = None
        descriptor_mask_meta: dict[str, Any] | None = None
        if bbox is None:
            failures.append("no_detector_bbox_available")
        else:
            expected_mask_area = selected_mask_area_px(used_detections)
            native_mask = native_detector_mask_from_detections(used_detections, confidence=confidence)
            image_file = Path(image_path)
            if not image_file.is_absolute():
                image_file = ROOT / image_file
            silhouette = build_image_silhouette_proxy(
                image_path=image_file,
                bbox={"x1": bbox[0], "y1": bbox[1], "x2": bbox[2], "y2": bbox[3]},
                expected_mask_area_px=expected_mask_area,
                label=runtime_label,
            )
            mask_for_observation = native_mask or (silhouette if silhouette.get("status") == "ok" else None)
            observation_source = (
                "real_image_detector_native_yoloe_mask_declared_assumed_flight_replay"
                if native_mask
                else "real_image_detector_bbox_plus_declared_silhouette_proxy_assumed_flight_replay"
            )
            bbox_only_observation = build_sppa_observation_contract(
                label=runtime_label,
                confidence=confidence,
                bbox={"x1": bbox[0], "y1": bbox[1], "x2": bbox[2], "y2": bbox[3]},
                image_width=int(ann["image_size"]["width"]),
                image_height=int(ann["image_size"]["height"]),
                flight=flight,
                height_prior_m=declared_height_prior_m,
                height_source="declared_family_replay_prior_not_measured",
                track_id=f"{label}:bbox_only",
                frame_id=0,
                timestamp="2026-07-03T00:00:00Z",
                telemetry_measured=False,
                metric_ground_truth=False,
                source="real_image_detector_bbox_only_declared_assumed_flight_replay",
            )
            observation = build_sppa_observation_contract(
                label=runtime_label,
                confidence=confidence,
                bbox={"x1": bbox[0], "y1": bbox[1], "x2": bbox[2], "y2": bbox[3]},
                mask=mask_for_observation,
                image_width=int(ann["image_size"]["width"]),
                image_height=int(ann["image_size"]["height"]),
                flight=flight,
                height_prior_m=declared_height_prior_m,
                height_source="declared_family_replay_prior_not_measured",
                track_id=label,
                frame_id=0,
                timestamp="2026-07-03T00:00:00Z",
                telemetry_measured=False,
                metric_ground_truth=False,
                source=observation_source,
            )
            obs_metric = observation.get("metric") or {}
            footprint = obs_metric.get("footprint_m")
            world_m = obs_metric.get("world_m")
            dims = obs_metric.get("metric_dims_m")
            if footprint is None:
                failures.append("metric_footprint_projection_failed")
            if world_m is None:
                failures.append("world_position_projection_failed")
            descriptor_payload = build_sppa_descriptor_payload(
                label=runtime_label,
                confidence=confidence,
                max_descriptor_bytes=30000,
                **descriptor_kwargs_from_observation(observation),
            )
            descriptor_json = descriptor_payload.get("sppa_descriptor_json")
            descriptor_mask_meta = None
            if descriptor_json:
                try:
                    descriptor_mask_meta = (
                        (json.loads(descriptor_json).get("evidence") or {}).get("mask_ref_or_polygon")
                    )
                except Exception:
                    descriptor_mask_meta = None

        rows.append(
            {
                "case_id": label,
                "image": image_path,
                "image_is_real": True,
                "image_source": "real_user_supplied_image",
                "detector_is_real": True,
                "detector_source": detector_data.get("profile_id"),
                "detector_model": detector_data.get("model"),
                "detector_label": selected.get("detector_label"),
                "detector_confidence": confidence,
                "bbox_xyxy": bbox,
                "bbox_source": bbox_source,
                "used_detections": used_detections,
                "detector_mask_area_px": selected_mask_area_px(used_detections),
                "native_detector_mask": native_mask,
                "native_detector_mask_available": native_mask is not None,
                "native_detector_mask_point_count": 0 if native_mask is None else len(native_mask.get("polygon") or []),
                "silhouette_proxy": silhouette,
                "mask_path_used": (
                    "native_yoloe_detector_mask"
                    if native_mask
                    else ("image_derived_silhouette_proxy" if silhouette and silhouette.get("status") == "ok" else "bbox_only")
                ),
                "reviewed_semantic_tag": reviewed_semantic_tag,
                "sppa_tag": selected.get("sppa_tag"),
                "detector_runtime_archetype_id": detector_runtime_label,
                "runtime_archetype_id": runtime_label,
                "semantic_text_source": semantic_text_source,
                "normalization_rule": selected.get("sppa_match"),
                "claim_status": selected.get("claim_status"),
                "conservative": selected.get("conservative"),
                "flight_replay": flight,
                "declared_height_prior_m": declared_height_prior_m,
                "height_prior_source": "declared_family_replay_prior_not_measured",
                "metric_ground_truth": False,
                "telemetry_is_measured": False,
                "telemetry_source": "declared_assumed_replay_not_measured",
                "publication_label": "real image + real YOLOE detector evidence + declared assumed-flight telemetry replay",
                "world_m": world_m,
                "sppa_footprint_m": footprint,
                "bbox_only_footprint_m": None
                if bbox_only_observation is None
                else (bbox_only_observation.get("metric") or {}).get("footprint_m"),
                "bbox_only_metric_dims_m": None
                if bbox_only_observation is None
                else (bbox_only_observation.get("metric") or {}).get("metric_dims_m"),
                "sppa_metric_dims_m": descriptor_payload.get("sppa_metric_dims_m") or dims,
                "yaw_deg": footprint.get("orientation_deg_axial") if footprint else None,
                "yaw_ambiguous": footprint.get("yaw_ambiguous") if footprint else None,
                "sppa_descriptor_id": descriptor_payload.get("sppa_descriptor_id"),
                "sppa_observation_id": descriptor_payload.get("sppa_observation_id"),
                "sppa_observation_status": None if observation is None else observation.get("status"),
                "sppa_observation_metric_evidence_source": None
                if observation is None
                else (observation.get("metric") or {}).get("metric_evidence_source"),
                "sppa_scale_source": descriptor_payload.get("sppa_scale_source"),
                "sppa_shape_policy": descriptor_payload.get("sppa_shape_policy"),
                "sppa_uncertainty": descriptor_payload.get("sppa_uncertainty"),
                "sppa_descriptor_has_mask_polygon": bool(descriptor_mask_meta),
                "sppa_descriptor_mask_hash": None if not descriptor_mask_meta else descriptor_mask_meta.get("hash"),
                "sppa_descriptor_mask_point_count": 0 if not descriptor_mask_meta else descriptor_mask_meta.get("point_count"),
                "sppa_descriptor_error": descriptor_payload.get("sppa_descriptor_error"),
                "status": "passed" if not failures else "failed",
                "failures": failures,
                "claim_boundary": (
                    "The image and YOLOE detector evidence are real local inputs. The flight pose, AGL, "
                    "and camera geometry are declared replay parameters, not measured flight telemetry; "
                    "therefore metric position/scale are scenario-relative and not ground truth."
                ),
            }
        )
    return rows


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Real-Image Assumed-Flight SPPA Replay",
        "",
        "This artifact upgrades the paper evidence without mislabeling telemetry.",
        "",
        "## Claim Boundary",
        "",
        report["claim_boundary"],
        "",
        "## Summary",
        "",
        f"- Cases: {report['case_count']}",
        f"- Passed: {report['passed_count']}",
        f"- Failed: {report['failed_count']}",
        "- Images are real: yes",
        "- Detector evidence is real YOLOE inference: yes",
        "- Flight telemetry is measured: no",
        "- Height priors are measured: no",
        "- Metric output is scenario-relative: yes",
        "",
        "## Cases",
        "",
        "| Case | Detector label | SPPA tag | Evidence source | Silhouette q | Dims m | World m | Status |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["rows"]:
        dims = row.get("sppa_metric_dims_m") or {}
        world = row.get("world_m") or {}
        dims_txt = (
            f"L={float(dims.get('length', 0.0)):.2f}, "
            f"W={float(dims.get('width', 0.0)):.2f}, "
            f"H={float(dims.get('height', 0.0)):.2f}"
        ) if dims else "-"
        world_txt = (
            f"N={float(world.get('north', 0.0)):.2f}, "
            f"E={float(world.get('east', 0.0)):.2f}"
        ) if world else "-"
        silhouette = row.get("silhouette_proxy") or {}
        q = silhouette.get("quality_score")
        q_txt = "-" if q is None else f"{float(q):.3f}"
        lines.append(
            "| "
            f"`{row['case_id']}` | `{row.get('detector_label')}` | `{row.get('sppa_tag')}` | "
            f"`{row.get('sppa_observation_metric_evidence_source')}` | {q_txt} | "
            f"{dims_txt} | {world_txt} | `{row['status']}` |"
        )
    lines += [
        "",
        "## Paper Wording",
        "",
        (
            "We evaluate SPPA on real user-supplied UAV-style images using YOLOE detector evidence. "
            "For the metric-proxy path, we run a declared assumed-flight telemetry replay: camera pose, "
            "AGL, mount geometry, and family height priors are scenario parameters rather than measured flight logs. "
            "The silhouette column is an image-derived proxy inside the detector/reviewed bbox, not a ground-truth mask. "
            "This evaluates the SPPA projection and proxy-construction pipeline while keeping measured-flight claims separate."
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detector-json", type=Path, default=DEFAULT_DETECTOR_JSON)
    parser.add_argument("--annotations-json", type=Path, default=DEFAULT_ANNOTATIONS_JSON)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    detector_json = args.detector_json if args.detector_json.is_absolute() else ROOT / args.detector_json
    annotations_json = args.annotations_json if args.annotations_json.is_absolute() else ROOT / args.annotations_json
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    detector_data = read_json(detector_json)
    annotations = read_json(annotations_json)
    rows = build_rows(detector_data, annotations)
    report = {
        "schema": "SPPA-REAL-IMAGE-ASSUMED-FLIGHT-REPLAY-0.1",
        "created_utc": "2026-07-03T00:00:00Z",
        "detector_json": rel(detector_json),
        "annotations_json": rel(annotations_json),
        "case_count": len(rows),
        "passed_count": sum(1 for row in rows if row["status"] == "passed"),
        "failed_count": sum(1 for row in rows if row["status"] != "passed"),
        "image_is_real": True,
        "detector_is_real": True,
        "telemetry_is_measured": False,
        "metric_ground_truth": False,
        "claim_posture": "real_image_detector_evidence_with_declared_assumed_flight_replay",
        "claim_boundary": (
            "Real user images and real YOLOE detector outputs are used. Flight pose, AGL, and camera "
            "mount geometry plus family height priors are declared replay assumptions, not measured telemetry. "
            "Metric SPPA pose/scale is therefore scenario-relative and must not be described as real measured flight localization."
        ),
        "rows": rows,
    }
    json_path = out_dir / "real_image_assumed_flight_replay.json"
    md_path = out_dir / "real_image_assumed_flight_replay.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_path, report)
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(md_path),
                "case_count": report["case_count"],
                "passed_count": report["passed_count"],
                "failed_count": report["failed_count"],
                "claim_posture": report["claim_posture"],
            },
            indent=2,
        )
    )
    return 1 if report["failed_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
