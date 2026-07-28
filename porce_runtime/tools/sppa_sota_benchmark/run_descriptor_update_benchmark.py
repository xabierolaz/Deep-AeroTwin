from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bench_common import ROOT, gpu_snapshot, write_csv, write_jsonl

try:
    from measure_sppa_lifecycle import extract_observations
except Exception:
    extract_observations = None


KNOWN_LABELS = ["car", "truck", "tractor", "cow", "tree", "biker"]
OPEN_LABELS = ["delivery van", "antenna mast", "horse animal"]
UNKNOWN_LABELS = ["solar panel", "shipping container", "barrel"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_head() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def require_atomic_output_dir(out_dir: Path, allow_existing: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = [path for path in out_dir.iterdir() if path.name != ".gitkeep"]
    if existing and not allow_existing:
        raise SystemExit(
            f"Output directory is not empty: {out_dir}. "
            "Use a new directory or pass --allow-existing if you intentionally want to overwrite files."
        )


def load_generator(generator_path: Path):
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", generator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {generator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(math.ceil((p / 100.0) * len(ordered))) - 1))
    return float(ordered[idx])


def summarize(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"n": 0, "min": 0.0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    return {
        "n": len(values),
        "min": min(values),
        "mean": statistics.fmean(values),
        "p50": pct(values, 50),
        "p95": pct(values, 95),
        "p99": pct(values, 99),
        "max": max(values),
    }


def rect_mask(bbox: dict[str, float]) -> list[list[float]]:
    x = float(bbox["x"])
    y = float(bbox["y"])
    w = float(bbox["w"])
    h = float(bbox["h"])
    return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]


def synthetic_observations() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for frame in range(10):
        bbox = {"x": 400, "y": 240, "w": 44, "h": 180}
        rows.append(
            {
                "scenario": "static_tower",
                "track_id": "static_tower_01",
                "frame_id": frame,
                "timestamp": f"2026-07-02T12:00:{frame:02d}Z",
                "label": "tower",
                "confidence": 0.91,
                "image_width": 1280,
                "image_height": 720,
                "bbox": bbox,
                "mask": rect_mask(bbox),
                "world_pose": {"x": 20.0, "y": 5.0, "z": 0.0},
                "dims_m": {"length": 0.8, "width": 0.8, "height": 4.5},
            }
        )
    for frame in range(12):
        bbox = {"x": 200 + frame * 8, "y": 280, "w": 110, "h": 55}
        rows.append(
            {
                "scenario": "moving_car",
                "track_id": "moving_car_01",
                "frame_id": frame,
                "timestamp": f"2026-07-02T12:01:{frame:02d}Z",
                "label": "car",
                "confidence": 0.84 - frame * 0.005,
                "image_width": 1280,
                "image_height": 720,
                "bbox": bbox,
                "mask": rect_mask(bbox),
                "world_pose": {"x": frame * 0.65, "y": 3.0, "z": 0.0},
                "dims_m": {"length": 4.3, "width": 1.8, "height": 1.55},
            }
        )
    widths = [140, 146, 153, 164, 175, 188, 205, 222, 238, 255, 270, 286]
    for frame, width in enumerate(widths):
        bbox = {"x": 180, "y": 260, "w": width, "h": 85}
        rows.append(
            {
                "scenario": "truck_scale_change",
                "track_id": "truck_scale_01",
                "frame_id": frame,
                "timestamp": f"2026-07-02T12:02:{frame:02d}Z",
                "label": "truck",
                "confidence": 0.79,
                "image_width": 1280,
                "image_height": 720,
                "bbox": bbox,
                "mask": rect_mask(bbox),
                "world_pose": {"x": 10.0, "y": frame * 0.08, "z": 0.0},
                "dims_m": {"length": 5.0 + frame * 0.18, "width": 2.35, "height": 2.8},
            }
        )
    labels = ["car", "car", "car", "truck", "truck", "truck"]
    for frame, label in enumerate(labels):
        bbox = {"x": 320, "y": 260, "w": 120 + frame * 4, "h": 62}
        rows.append(
            {
                "scenario": "class_change",
                "track_id": "class_change_01",
                "frame_id": frame,
                "timestamp": f"2026-07-02T12:03:{frame:02d}Z",
                "label": label,
                "confidence": 0.82,
                "image_width": 1280,
                "image_height": 720,
                "bbox": bbox,
                "mask": rect_mask(bbox),
                "world_pose": {"x": 4.0 + frame * 0.3, "y": 8.0, "z": 0.0},
                "dims_m": {"length": 4.5 if label == "car" else 6.2, "width": 1.9 if label == "car" else 2.4, "height": 1.7 if label == "car" else 2.8},
            }
        )
    return rows


def build_descriptor_for_observation(
    module,
    obs: dict[str, Any],
    thresholds: dict[str, float],
    prev_world_pose: dict[str, Any] | None = None,
    previous_descriptor_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], float]:
    mesh = module.Mesh()
    create_start = time.perf_counter_ns()
    meta = module.build_label(mesh, obs["label"])
    create_cpu_us = (time.perf_counter_ns() - create_start) / 1000.0
    desc_start = time.perf_counter_ns()
    descriptor = module.build_sppa_descriptor(
        mesh,
        meta,
        obs.get("confidence", 1.0),
        bbox=obs.get("bbox"),
        mask=obs.get("mask"),
        world_pose=obs.get("world_pose"),
        prev_world_pose=prev_world_pose,
        image_width=obs.get("image_width"),
        image_height=obs.get("image_height"),
        dims_m=obs.get("dims_m"),
        yaw_deg=obs.get("yaw_deg"),
        heading_deg=obs.get("heading_deg"),
        track_id=obs.get("track_id"),
        timestamp=obs.get("timestamp"),
        frame_id=obs.get("frame_id"),
        track_age_s=obs.get("track_age_s"),
        track_seen_count=obs.get("track_seen_count"),
        source_log=obs.get("source_log"),
        source_event_index=obs.get("source_event_index"),
        previous_descriptor_id=previous_descriptor_id,
        thresholds=thresholds,
        create_cpu_us=create_cpu_us,
    )
    descriptor_wall_us = (time.perf_counter_ns() - desc_start) / 1000.0
    return descriptor, meta, descriptor_wall_us


def run_smoke(module, out_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    labels = [("known", label) for label in KNOWN_LABELS]
    labels += [("open_keyword", label) for label in OPEN_LABELS]
    labels += [("unknown_fallback", label) for label in UNKNOWN_LABELS]
    rows: list[dict[str, Any]] = []
    descriptors: list[dict[str, Any]] = []
    packets: list[dict[str, Any]] = []
    thresholds = dict(module.DEFAULT_SCHEDULER_THRESHOLDS)
    for kind, label in labels:
        obs = {
            "scenario": "descriptor_smoke",
            "track_id": f"smoke_{kind}_{label.replace(' ', '_')}",
            "frame_id": 0,
            "timestamp": "2026-07-02T12:10:00Z",
            "label": label,
            "confidence": 0.88 if kind != "unknown_fallback" else 0.62,
        }
        descriptor, _, descriptor_wall_us = build_descriptor_for_observation(module, obs, thresholds)
        decision_start = time.perf_counter_ns()
        decision = module.schedule_descriptor_update(None, descriptor, thresholds)
        schedule_us = (time.perf_counter_ns() - decision_start) / 1000.0
        module.apply_schedule_to_descriptor(descriptor, decision)
        packet = module.build_runtime_update_packet(descriptor, decision)
        descriptors.append(descriptor)
        packets.append(packet)
        rows.append(
            {
                "kind": kind,
                "label": label,
                "archetype": descriptor["semantic"]["archetype"],
                "resolution_status": descriptor["semantic"]["resolution_status"],
                "unknown_label": descriptor["semantic"]["unknown_label"],
                "yaw_source": descriptor["pose"]["yaw_source"],
                "yaw_ambiguous": descriptor["pose"]["yaw_ambiguous"],
                "scale_source": descriptor["scale"]["scale_source"],
                "parts": len(descriptor["parts"]),
                "triangles": descriptor["mesh"]["triangles"],
                "descriptor_bytes": descriptor["cost"]["descriptor_bytes"],
                "packet_bytes": packet["packet_bytes"],
                "descriptor_build_us": descriptor_wall_us,
                "schedule_us": schedule_us,
                "action": decision["action"],
            }
        )
    write_csv(out_dir / "descriptor_smoke.csv", rows)
    write_jsonl(out_dir / "descriptor_smoke_samples.jsonl", descriptors)
    write_jsonl(out_dir / "descriptor_smoke_update_packets.jsonl", packets)
    return rows, descriptors


def run_sequence_rows(
    module,
    observations: list[dict[str, Any]],
    thresholds: dict[str, float],
    source_kind: str,
    descriptor_sample_limit: int = 50,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    last_descriptors: dict[str, dict[str, Any]] = {}
    shape_anchor_descriptors: dict[str, dict[str, Any]] = {}
    prev_world: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    packet_samples: list[dict[str, Any]] = []
    sampled_packet_actions: set[tuple[str, float, str]] = set()
    for index, obs in enumerate(observations):
        track_id = str(obs.get("track_id") or "unknown_track")
        previous_descriptor = last_descriptors.get(track_id)
        descriptor, _, descriptor_wall_us = build_descriptor_for_observation(
            module,
            obs,
            thresholds,
            prev_world_pose=prev_world.get(track_id),
            previous_descriptor_id=previous_descriptor.get("descriptor_id") if previous_descriptor else None,
        )
        decision_start = time.perf_counter_ns()
        decision = module.schedule_descriptor_update(shape_anchor_descriptors.get(track_id), descriptor, thresholds)
        schedule_us = (time.perf_counter_ns() - decision_start) / 1000.0
        module.apply_schedule_to_descriptor(descriptor, decision)
        packet_start = time.perf_counter_ns()
        packet = module.build_runtime_update_packet(descriptor, decision)
        packet_build_us = (time.perf_counter_ns() - packet_start) / 1000.0
        effective_create_us = descriptor["cost"]["create_cpu_us"] if decision["action"] in ("create", "regenerate_topology") else 0.0
        create_total_python_us = (
            descriptor["cost"]["create_cpu_us"] + descriptor_wall_us + schedule_us + packet_build_us
            if decision["action"] in ("create", "regenerate_topology")
            else 0.0
        )
        pose_update_no_mesh_us = (
            schedule_us + packet_build_us
            if decision["action"] in ("pose_update", "no_op", "shape_param_update")
            else 0.0
        )
        row = {
            "source_kind": source_kind,
            "shape_threshold": thresholds["shape_ratio"],
            "scenario": obs.get("scenario"),
            "source_log": obs.get("source_log"),
            "source_event_index": obs.get("source_event_index"),
            "track_id": track_id,
            "frame_id": obs.get("frame_id"),
            "timestamp": obs.get("timestamp"),
            "label": obs.get("label"),
            "archetype": descriptor["semantic"]["archetype"],
            "resolution_status": descriptor["semantic"]["resolution_status"],
            "action": decision["action"],
            "reason": decision["reason"],
            "yaw_source": descriptor["pose"]["yaw_source"],
            "yaw_ambiguous": descriptor["pose"]["yaw_ambiguous"],
            "scale_source": descriptor["scale"]["scale_source"],
            "descriptor_build_us": descriptor_wall_us,
            "descriptor_build_with_parts_us": descriptor_wall_us,
            "schedule_us": schedule_us,
            "scheduler_decision_us": schedule_us,
            "update_packet_build_us": packet_build_us,
            "effective_create_us": effective_create_us,
            "create_total_python_us": create_total_python_us,
            "pose_update_no_mesh_us": pose_update_no_mesh_us,
            "descriptor_bytes": descriptor["cost"]["descriptor_bytes"],
            "packet_bytes": packet["packet_bytes"],
            "triangles": descriptor["mesh"]["triangles"],
            "parts": len(descriptor["parts"]),
            "previous_descriptor_id": descriptor["track"].get("previous_descriptor_id"),
        }
        rows.append(row)
        if len(samples) < descriptor_sample_limit:
            samples.append(descriptor)
        packet_key = (source_kind, float(thresholds["shape_ratio"]), decision["action"])
        if len(packet_samples) < descriptor_sample_limit or packet_key not in sampled_packet_actions:
            packet_samples.append(packet)
            sampled_packet_actions.add(packet_key)
        last_descriptors[track_id] = descriptor
        if decision["action"] in ("create", "shape_param_update", "regenerate_topology"):
            shape_anchor_descriptors[track_id] = descriptor
        if obs.get("world_pose"):
            prev_world[track_id] = obs["world_pose"]
    return rows, samples, packet_samples


def observation_from_replay(obs: Any) -> dict[str, Any]:
    return {
        "scenario": "replay_policy_observation",
        "track_id": f"{obs.source_path}:{obs.track_key}",
        "frame_id": obs.event_index,
        "timestamp": obs.iso_utc or str(obs.ts),
        "label": obs.class_name,
        "confidence": obs.confidence if obs.confidence is not None else 1.0,
        "bbox": obs.bbox,
        "world_pose": obs.world_m,
        "yaw_deg": obs.yaw_deg,
        "heading_deg": obs.heading_deg,
        "track_age_s": obs.track_age_s,
        "track_seen_count": obs.track_seen_count,
        "source_log": obs.source_path,
        "source_event_index": obs.event_index,
    }


def source_counts(observations: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for obs in observations:
        source = str(obs.get("source_log") or "synthetic")
        counts[source] = counts.get(source, 0) + 1
    return counts


def stratified_replay_observations(
    observations: list[Any],
    max_total: int | None,
    max_per_log: int | None,
) -> list[dict[str, Any]]:
    groups: dict[str, list[Any]] = {}
    for obs in observations:
        groups.setdefault(str(obs.source_path), []).append(obs)
    for items in groups.values():
        items.sort(key=lambda item: (item.ts, item.event_index, item.track_key))

    if max_per_log is not None and max_per_log > 0:
        selected_raw: list[Any] = []
        for source in sorted(groups):
            selected_raw.extend(groups[source][:max_per_log])
        selected_raw.sort(key=lambda item: (item.source_path, item.ts, item.event_index, item.track_key))
        if max_total is not None and max_total > 0 and len(selected_raw) > max_total:
            selected_raw = round_robin_cap(selected_raw, max_total)
        return [observation_from_replay(obs) for obs in selected_raw]

    selected: list[Any] = []
    indexes = {source: 0 for source in groups}
    sources = sorted(groups)
    while sources and (max_total is None or max_total <= 0 or len(selected) < max_total):
        progressed = False
        for source in list(sources):
            index = indexes[source]
            if index >= len(groups[source]):
                sources.remove(source)
                continue
            selected.append(groups[source][index])
            indexes[source] += 1
            progressed = True
            if max_total is not None and max_total > 0 and len(selected) >= max_total:
                break
        if not progressed:
            break
    selected.sort(key=lambda item: (item.source_path, item.ts, item.event_index, item.track_key))
    return [observation_from_replay(obs) for obs in selected]


def round_robin_cap(observations: list[Any], max_total: int) -> list[Any]:
    groups: dict[str, list[Any]] = {}
    for obs in observations:
        groups.setdefault(str(obs.source_path), []).append(obs)
    indexes = {source: 0 for source in groups}
    sources = sorted(groups)
    selected: list[Any] = []
    while sources and len(selected) < max_total:
        progressed = False
        for source in list(sources):
            index = indexes[source]
            if index >= len(groups[source]):
                sources.remove(source)
                continue
            selected.append(groups[source][index])
            indexes[source] += 1
            progressed = True
            if len(selected) >= max_total:
                break
        if not progressed:
            break
    selected.sort(key=lambda item: (item.source_path, item.ts, item.event_index, item.track_key))
    return selected


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    action_counts: dict[str, int] = {}
    threshold_action_counts: dict[str, dict[str, int]] = {}
    for row in rows:
        action_counts[row["action"]] = action_counts.get(row["action"], 0) + 1
        key = str(row["shape_threshold"])
        bucket = threshold_action_counts.setdefault(key, {})
        bucket[row["action"]] = bucket.get(row["action"], 0) + 1
    return {
        "rows": len(rows),
        "action_counts": action_counts,
        "threshold_action_counts": threshold_action_counts,
        "descriptor_build_us": summarize([float(r["descriptor_build_us"]) for r in rows]),
        "descriptor_build_with_parts_us": summarize([float(r["descriptor_build_with_parts_us"]) for r in rows]),
        "schedule_us": summarize([float(r["schedule_us"]) for r in rows]),
        "scheduler_decision_us": summarize([float(r["scheduler_decision_us"]) for r in rows]),
        "update_packet_build_us": summarize([float(r["update_packet_build_us"]) for r in rows]),
        "effective_create_us": summarize([float(r["effective_create_us"]) for r in rows if float(r["effective_create_us"]) > 0.0]),
        "create_total_python_us": summarize([float(r["create_total_python_us"]) for r in rows if float(r["create_total_python_us"]) > 0.0]),
        "pose_update_no_mesh_us": summarize([float(r["pose_update_no_mesh_us"]) for r in rows if float(r["pose_update_no_mesh_us"]) > 0.0]),
        "descriptor_bytes": summarize([float(r["descriptor_bytes"]) for r in rows]),
        "packet_bytes": summarize([float(r["packet_bytes"]) for r in rows]),
    }


REQUIRED_DESCRIPTOR_PATHS = [
    "descriptor_schema",
    "descriptor_id",
    "generator_version",
    "ontology_version",
    "archetype_version",
    "policy_version",
    "created_utc",
    "input_hash",
    "track.track_id",
    "track.timestamp",
    "track.frame_id",
    "track.previous_descriptor_id",
    "semantic.raw_label",
    "semantic.normalized_label",
    "semantic.class_confidence",
    "semantic.archetype",
    "semantic.resolution_status",
    "semantic.unknown_label",
    "evidence.evidence_sources",
    "evidence.bbox_px",
    "evidence.image_width",
    "evidence.image_height",
    "evidence.image_size_px",
    "evidence.mask_hash",
    "evidence.world_pose",
    "pose.position_world",
    "pose.coordinate_frame",
    "pose.yaw_source",
    "pose.yaw_modulo",
    "pose.yaw_ambiguous",
    "scale.scale_source",
    "scale.scale_uncertainty",
    "uncertainty.confidence",
    "uncertainty.yaw_ambiguous",
    "parts",
    "runtime_policy.cache_key",
    "runtime_policy.action",
    "runtime_policy.action_reason",
    "runtime_policy.thresholds",
    "mesh.triangles",
    "cost.create_cpu_us",
    "cost.descriptor_build_cpu_us",
    "cost.descriptor_bytes",
]

REQUIRED_PACKET_PATHS = [
    "packet_schema",
    "descriptor_schema",
    "descriptor_id",
    "cache_key",
    "action",
    "reason",
    "thresholds",
    "track",
    "semantic.archetype",
    "semantic.resolution_status",
    "semantic.class_confidence",
    "pose.yaw_source",
    "pose.yaw_modulo",
    "pose.yaw_ambiguous",
    "uncertainty.confidence",
    "packet_bytes",
]


def path_exists(payload: dict[str, Any], dotted_path: str) -> bool:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def validate_payloads(kind: str, payloads: list[dict[str, Any]], required_paths: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, payload in enumerate(payloads):
        missing = [path for path in required_paths if not path_exists(payload, path)]
        rows.append(
            {
                "kind": kind,
                "index": index,
                "descriptor_id": payload.get("descriptor_id"),
                "action": payload.get("action") or payload.get("runtime_policy", {}).get("action"),
                "status": "ok" if not missing else "missing_required_fields",
                "missing_count": len(missing),
                "missing_paths": ";".join(missing),
            }
        )
    return rows


def validation_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    failed = sum(1 for row in rows if row["status"] != "ok")
    return {"total": total, "failed": failed, "passed": total - failed}


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# SPPA Evidence-Aware Descriptor and Update Benchmark",
        "",
        "This benchmark measures the Python SPPA-DESC/SPPA-UPD contract and deterministic scheduler.",
        "It is not an Unreal render-thread, VR FPS, or human-subject validation benchmark.",
        "",
        "## Environment",
        "",
        f"- GPU snapshot: `{json.dumps(report['gpu_before'], sort_keys=True)}`",
        f"- Descriptor schema: `{report['descriptor_schema']}`",
        f"- Update packet schema: `{report['update_packet_schema']}`",
        f"- Replay base observations: {report['replay_base_observations']}",
        f"- Replay threshold-expanded rows: {report['replay']['rows']}",
        f"- Shape thresholds: {report['shape_thresholds']}",
        f"- Validation: {report['validation_summary']['passed']} passed, {report['validation_summary']['failed']} failed",
        "",
        "## Smoke Coverage",
        "",
        "| Kind | n | Unknown/fallback |",
        "|---|---:|---:|",
    ]
    for kind, stats in report["smoke_by_kind"].items():
        lines.append(f"| {kind} | {stats['n']} | {stats['unknown']} |")
    lines.extend(
        [
            "",
            "## Synthetic Scheduler Sensitivity",
            "",
            "| Shape threshold | Create | Pose update | Shape update | Topology regenerate | No-op |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for threshold, counts in sorted(report["synthetic"]["threshold_action_counts"].items(), key=lambda item: float(item[0])):
        lines.append(
            f"| {float(threshold):.2f} | {counts.get('create', 0)} | {counts.get('pose_update', 0)} | "
            f"{counts.get('shape_param_update', 0)} | {counts.get('regenerate_topology', 0)} | {counts.get('no_op', 0)} |"
        )
    lines.extend(
        [
            "",
            "## Timing Summary",
            "",
            "| Source | Metric | n | P50 us | P95 us | P99 us | Max us |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for source in ("synthetic", "replay"):
        if source not in report or report[source]["rows"] == 0:
            continue
        for metric in (
            "descriptor_build_with_parts_us",
            "scheduler_decision_us",
            "update_packet_build_us",
            "create_total_python_us",
            "pose_update_no_mesh_us",
            "descriptor_bytes",
            "packet_bytes",
        ):
            stats = report[source][metric]
            unit = "bytes" if metric.endswith("bytes") else "us"
            lines.append(
                f"| {source} | {metric} ({unit}) | {stats['n']} | {stats['p50']:.3f} | "
                f"{stats['p95']:.3f} | {stats['p99']:.3f} | {stats['max']:.3f} |"
            )
    if report.get("replay", {}).get("rows", 0):
        lines.extend(
            [
                "",
                "## Replay Source Distribution",
                "",
                "| Source log | Selected observations |",
                "|---|---:|",
            ]
        )
        for source, count in sorted(report["replay_source_sample_counts"].items()):
            lines.append(f"| `{source}` | {count} |")
        lines.extend(
            [
                "",
                "## Replay Scheduler Counts",
                "",
                "| Shape threshold | Create | Pose update | Shape update | Topology regenerate | No-op |",
                "|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for threshold, counts in sorted(report["replay"]["threshold_action_counts"].items(), key=lambda item: float(item[0])):
            lines.append(
                f"| {float(threshold):.2f} | {counts.get('create', 0)} | {counts.get('pose_update', 0)} | "
                f"{counts.get('shape_param_update', 0)} | {counts.get('regenerate_topology', 0)} | {counts.get('no_op', 0)} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation Boundaries",
            "",
            "- Full descriptor bytes are create/regenerate contract bytes; per-frame updates should use SPPA-UPD packet bytes.",
            "- Metric scale is used only when explicit `dims_m` is supplied; bbox/mask-only rows remain image-space evidence.",
            "- Mask/PCA yaw is axial modulo pi and remains ambiguous unless explicit yaw, heading, or velocity evidence exists.",
            "- Replay rows are policy-derived from available logs, not native Unreal actor instrumentation.",
            "- `descriptor_build_with_parts_us` includes Python mesh/part descriptor assembly per observation; it is not a pure runtime transform update.",
            "- `pose_update_no_mesh_us` includes scheduler decision plus update-packet construction only; Unreal transform and render-thread cost remain unmeasured.",
            "- The next required artifact for operational claims is a native Unreal trace of spawn/reconfigure/transform/despawn plus frame timings.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    run_started_utc = utc_now()
    parser = argparse.ArgumentParser(description="Benchmark SPPA-DESC descriptors and SPPA-UPD scheduler packets.")
    parser.add_argument("--generator", default=str(ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"))
    parser.add_argument("--out-dir", default=str(ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_descriptor_update" / "20260702_descriptor_v04_atomic"))
    parser.add_argument("--allow-existing", action="store_true", help="Allow writing into a non-empty output directory")
    parser.add_argument("--shape-thresholds", nargs="+", type=float, default=[0.05, 0.10, 0.20, 0.30])
    parser.add_argument("--max-replay-observations", type=int, default=0, help="Optional global cap after stratified sampling; 0 means no global cap")
    parser.add_argument("--max-replay-observations-per-log", type=int, default=3000)
    parser.add_argument(
        "--events",
        nargs="+",
        default=[
            str(ROOT / "pipeline" / "logs" / "zero_trust" / "20260701_144043" / "real_twin" / "brain" / "events.jsonl"),
            str(ROOT / "pipeline" / "logs" / "zero_trust" / "20260701_144043" / "simulation" / "brain" / "events.jsonl"),
        ],
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    require_atomic_output_dir(out_dir, args.allow_existing)

    module = load_generator(Path(args.generator))
    gpu_before = gpu_snapshot()
    smoke_rows, smoke_descriptors = run_smoke(module, out_dir)

    synthetic_all: list[dict[str, Any]] = []
    synthetic_samples: list[dict[str, Any]] = []
    synthetic_packet_samples: list[dict[str, Any]] = []
    for threshold in args.shape_thresholds:
        thresholds = dict(module.DEFAULT_SCHEDULER_THRESHOLDS)
        thresholds["shape_ratio"] = threshold
        rows, samples, packets = run_sequence_rows(module, synthetic_observations(), thresholds, "synthetic")
        synthetic_all.extend(rows)
        synthetic_samples.extend(samples[:10])
        synthetic_packet_samples.extend(packets)
    write_csv(out_dir / "synthetic_update_rows.csv", synthetic_all)
    write_jsonl(out_dir / "synthetic_descriptor_samples.jsonl", synthetic_samples[:80])
    write_jsonl(out_dir / "synthetic_update_packet_samples.jsonl", synthetic_packet_samples[:240])

    replay_all: list[dict[str, Any]] = []
    replay_samples: list[dict[str, Any]] = []
    replay_packet_samples: list[dict[str, Any]] = []
    replay_sources: list[dict[str, Any]] = []
    replay_observations: list[dict[str, Any]] = []
    event_paths = [Path(path) for path in args.events]
    existing_events = [path for path in event_paths if path.exists()]
    if extract_observations is not None and existing_events:
        observations, replay_sources = extract_observations(existing_events)
        max_total = args.max_replay_observations if args.max_replay_observations and args.max_replay_observations > 0 else None
        max_per_log = args.max_replay_observations_per_log if args.max_replay_observations_per_log and args.max_replay_observations_per_log > 0 else None
        replay_observations = stratified_replay_observations(observations, max_total, max_per_log)
        for threshold in args.shape_thresholds:
            thresholds = dict(module.DEFAULT_SCHEDULER_THRESHOLDS)
            thresholds["shape_ratio"] = threshold
            rows, samples, packets = run_sequence_rows(module, replay_observations, thresholds, "replay")
            replay_all.extend(rows)
            replay_samples.extend(samples[:10])
            replay_packet_samples.extend(packets)
    write_csv(out_dir / "replay_update_rows.csv", replay_all)
    write_jsonl(out_dir / "replay_descriptor_samples.jsonl", replay_samples[:80])
    write_jsonl(out_dir / "replay_update_packet_samples.jsonl", replay_packet_samples[:240])

    smoke_by_kind: dict[str, dict[str, int]] = {}
    for row in smoke_rows:
        entry = smoke_by_kind.setdefault(row["kind"], {"n": 0, "unknown": 0})
        entry["n"] += 1
        entry["unknown"] += 1 if row["unknown_label"] else 0

    validation_rows: list[dict[str, Any]] = []
    validation_rows.extend(validate_payloads("smoke_descriptor", smoke_descriptors, REQUIRED_DESCRIPTOR_PATHS))
    validation_rows.extend(validate_payloads("synthetic_descriptor", synthetic_samples[:80], REQUIRED_DESCRIPTOR_PATHS))
    validation_rows.extend(validate_payloads("replay_descriptor", replay_samples[:80], REQUIRED_DESCRIPTOR_PATHS))
    validation_rows.extend(validate_payloads("synthetic_packet", synthetic_packet_samples[:240], REQUIRED_PACKET_PATHS))
    validation_rows.extend(validate_payloads("replay_packet", replay_packet_samples[:240], REQUIRED_PACKET_PATHS))
    write_csv(out_dir / "contract_validation.csv", validation_rows)

    report = {
        "descriptor_schema": module.SPPA_DESCRIPTOR_VERSION,
        "update_packet_schema": module.SPPA_UPDATE_PACKET_VERSION,
        "gpu_before": gpu_before,
        "shape_thresholds": args.shape_thresholds,
        "smoke_by_kind": smoke_by_kind,
        "synthetic": summarize_rows(synthetic_all),
        "replay": summarize_rows(replay_all),
        "replay_base_observations": len(replay_observations),
        "replay_source_sample_counts": source_counts(replay_observations),
        "replay_sources": replay_sources,
        "replay_events_found": [str(path) for path in existing_events],
        "validation_summary": validation_summary(validation_rows),
    }
    (out_dir / "descriptor_update_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(out_dir / "descriptor_update_summary.md", report)
    run_manifest = {
        "started_utc": run_started_utc,
        "ended_utc": utc_now(),
        "command": " ".join(sys.argv),
        "cwd": str(Path.cwd()),
        "git_head": git_head(),
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "output_dir": str(out_dir),
        "generator": str(Path(args.generator)),
        "shape_thresholds": args.shape_thresholds,
        "max_replay_observations": args.max_replay_observations,
        "max_replay_observations_per_log": args.max_replay_observations_per_log,
        "events_requested": args.events,
        "events_found": [str(path) for path in existing_events],
        "replay_base_observations": len(replay_observations),
        "replay_source_sample_counts": source_counts(replay_observations),
        "gpu_before": gpu_before,
        "artifacts": sorted({path.name for path in out_dir.iterdir() if path.is_file()} | {"run_manifest.json"}),
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote " + str(out_dir / "descriptor_update_summary.md"))
    print("wrote " + str(out_dir / "descriptor_update_report.json"))
    print("wrote " + str(out_dir / "run_manifest.json"))


if __name__ == "__main__":
    main()
