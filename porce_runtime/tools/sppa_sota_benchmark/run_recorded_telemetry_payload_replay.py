from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bench_common import ROOT, write_csv, write_jsonl
from measure_sppa_lifecycle import TrackObservation, extract_observations


DEFAULT_EVENTS = [
    ROOT / "pipeline" / "logs" / "zero_trust" / "20260701_144043" / "real_twin" / "brain" / "events.jsonl",
    ROOT / "pipeline" / "logs" / "zero_trust" / "20260701_144043" / "simulation" / "brain" / "events.jsonl",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_head() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def git_dirty() -> bool | None:
    try:
        return bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip())
    except Exception:
        return None


def load_generator(generator_path: Path):
    spec = importlib.util.spec_from_file_location("xyt_generate_3d", generator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load generator: {generator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def payload_bytes(payload: Any) -> int:
    return len(stable_json(payload).encode("utf-8"))


def stable_hash(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(math.ceil((p / 100.0) * len(ordered))) - 1))
    return float(ordered[idx])


def summary(values: list[float]) -> dict[str, float | int]:
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


def safe_entity_id(obs: TrackObservation) -> str:
    source = stable_hash(obs.source_path, 10)
    raw = str(obs.track_key or "track")
    safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in raw)[:80]
    return f"rec_{source}_{safe}"


def normalize_world_m(world_m: dict[str, Any] | None) -> dict[str, float] | None:
    if not isinstance(world_m, dict):
        return None
    if {"north", "east", "up"}.issubset(world_m):
        return {
            "north": float(world_m.get("north") or 0.0),
            "east": float(world_m.get("east") or 0.0),
            "up": float(world_m.get("up") or 0.0),
        }
    if {"x", "y", "z"}.issubset(world_m):
        return {
            "x": float(world_m.get("x") or 0.0),
            "y": float(world_m.get("y") or 0.0),
            "z": float(world_m.get("z") or 0.0),
        }
    return None


def descriptor_world_pose(world_m: dict[str, Any] | None) -> dict[str, float | str] | None:
    if not isinstance(world_m, dict):
        return None
    if {"north", "east", "up"}.issubset(world_m):
        return {
            "x": float(world_m.get("east") or 0.0),
            "y": float(world_m.get("north") or 0.0),
            "z": float(world_m.get("up") or 0.0),
            "coordinate_frame": "local_world_m",
        }
    if {"x", "y", "z"}.issubset(world_m):
        return {
            "x": float(world_m.get("x") or 0.0),
            "y": float(world_m.get("y") or 0.0),
            "z": float(world_m.get("z") or 0.0),
            "coordinate_frame": str(world_m.get("coordinate_frame") or world_m.get("frame") or "local_world_m"),
        }
    return None


def common_obstacle(obs: TrackObservation) -> dict[str, Any]:
    label = obs.class_name or "unknown"
    obstacle: dict[str, Any] = {
        "entity_id": safe_entity_id(obs),
        "object_type": label,
        "type": label,
        "confidence": 1.0 if obs.confidence is None else float(obs.confidence),
        "source_log": obs.source_path,
        "source_event_index": int(obs.event_index),
        "track_key": str(obs.track_key),
        "track_age_s": obs.track_age_s,
        "track_seen_count": obs.track_seen_count,
        "timestamp": obs.iso_utc or str(obs.ts),
    }
    world_m = normalize_world_m(obs.world_m)
    if world_m is not None:
        obstacle["world_m"] = world_m
    if obs.lat is not None and obs.lon is not None:
        obstacle["lat"] = float(obs.lat)
        obstacle["lon"] = float(obs.lon)
    if obs.yaw_deg is not None:
        obstacle["yaw_deg"] = float(obs.yaw_deg)
    if obs.heading_deg is not None:
        obstacle["heading_deg"] = float(obs.heading_deg)
    if obs.bbox is not None:
        obstacle["bbox"] = obs.bbox
    return obstacle


def build_descriptor(module, obs: TrackObservation, prev_descriptor: dict[str, Any] | None, prev_world_pose: dict[str, Any] | None, thresholds: dict[str, float]) -> tuple[dict[str, Any], float]:
    mesh = module.Mesh()
    create_start = time.perf_counter_ns()
    meta = module.build_label_observed(
        mesh,
        obs.class_name or "unknown",
        bbox=obs.bbox,
    )
    create_us = (time.perf_counter_ns() - create_start) / 1000.0
    world_pose = descriptor_world_pose(obs.world_m)
    desc_start = time.perf_counter_ns()
    descriptor = module.build_sppa_descriptor(
        mesh,
        meta,
        1.0 if obs.confidence is None else float(obs.confidence),
        bbox=obs.bbox,
        world_pose=world_pose,
        prev_world_pose=prev_world_pose,
        yaw_deg=obs.yaw_deg,
        heading_deg=obs.heading_deg,
        track_id=safe_entity_id(obs),
        timestamp=obs.iso_utc or str(obs.ts),
        frame_id=obs.event_index,
        track_age_s=obs.track_age_s,
        track_seen_count=obs.track_seen_count,
        source_log=obs.source_path,
        source_event_index=obs.event_index,
        previous_descriptor_id=prev_descriptor.get("descriptor_id") if prev_descriptor else None,
        thresholds=thresholds,
        create_cpu_us=create_us,
    )
    descriptor_us = (time.perf_counter_ns() - desc_start) / 1000.0
    return descriptor, descriptor_us


def make_payloads_for_events(module, observations: list[TrackObservation], thresholds: dict[str, float]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, int], list[TrackObservation]] = defaultdict(list)
    for obs in observations:
        grouped[(obs.source_path, obs.event_index)].append(obs)

    last_descriptor: dict[str, dict[str, Any]] = {}
    shape_anchor: dict[str, dict[str, Any]] = {}
    prev_world: dict[str, dict[str, Any]] = {}
    event_rows: list[dict[str, Any]] = []
    observation_rows: list[dict[str, Any]] = []
    common_payloads: list[dict[str, Any]] = []
    sppa_all_payloads: list[dict[str, Any]] = []
    sppa_changed_payloads: list[dict[str, Any]] = []

    for (source_path, event_index) in sorted(grouped, key=lambda key: (key[0], key[1])):
        event_observations = sorted(grouped[(source_path, event_index)], key=lambda item: (item.ts, str(item.track_key)))
        common_obstacles: list[dict[str, Any]] = []
        sppa_all_obstacles: list[dict[str, Any]] = []
        sppa_changed_obstacles: list[dict[str, Any]] = []
        actions: dict[str, int] = {}
        event_descriptor_us: list[float] = []
        event_schedule_us: list[float] = []
        event_packet_us: list[float] = []

        for obs in event_observations:
            entity_id = safe_entity_id(obs)
            common = common_obstacle(obs)
            common_obstacles.append(common)

            descriptor, descriptor_us = build_descriptor(module, obs, last_descriptor.get(entity_id), prev_world.get(entity_id), thresholds)
            schedule_start = time.perf_counter_ns()
            decision = module.schedule_descriptor_update(shape_anchor.get(entity_id), descriptor, thresholds)
            schedule_us = (time.perf_counter_ns() - schedule_start) / 1000.0
            module.apply_schedule_to_descriptor(descriptor, decision)
            packet_start = time.perf_counter_ns()
            packet = module.build_runtime_update_packet(descriptor, decision)
            packet_us = (time.perf_counter_ns() - packet_start) / 1000.0

            action = str(decision["action"])
            actions[action] = actions.get(action, 0) + 1
            event_descriptor_us.append(descriptor_us)
            event_schedule_us.append(schedule_us)
            event_packet_us.append(packet_us)

            sppa_obstacle = dict(common)
            if action in ("create", "regenerate_topology"):
                sppa_obstacle["sppa_descriptor"] = descriptor
            else:
                sppa_obstacle["sppa_update_packet"] = packet
            sppa_all_obstacles.append(sppa_obstacle)
            if action != "no_op":
                sppa_changed_obstacles.append(sppa_obstacle)

            common_bytes = payload_bytes({"obstacles": [common]})
            sppa_bytes = payload_bytes({"obstacles": [sppa_obstacle]})
            observation_rows.append(
                {
                    "source_log": source_path,
                    "event_index": event_index,
                    "timestamp": obs.iso_utc or str(obs.ts),
                    "entity_id": entity_id,
                    "track_key": obs.track_key,
                    "label": obs.class_name,
                    "confidence": obs.confidence,
                    "action": action,
                    "reason": decision["reason"],
                    "archetype": descriptor.get("semantic", {}).get("archetype"),
                    "resolution_status": descriptor.get("semantic", {}).get("resolution_status"),
                    "scale_source": descriptor.get("scale", {}).get("scale_source"),
                    "yaw_source": descriptor.get("pose", {}).get("yaw_source"),
                    "yaw_ambiguous": descriptor.get("pose", {}).get("yaw_ambiguous"),
                    "parts": len(descriptor.get("parts") or []),
                    "triangles": descriptor.get("mesh", {}).get("triangles"),
                    "descriptor_build_us": descriptor_us,
                    "schedule_us": schedule_us,
                    "update_packet_build_us": packet_us,
                    "common_obstacle_payload_bytes": common_bytes,
                    "sppa_obstacle_payload_bytes": sppa_bytes,
                    "descriptor_bytes": descriptor.get("cost", {}).get("descriptor_bytes"),
                    "packet_bytes": packet.get("packet_bytes"),
                }
            )

            last_descriptor[entity_id] = descriptor
            if action in ("create", "shape_param_update", "regenerate_topology"):
                shape_anchor[entity_id] = descriptor
            world_pose = descriptor_world_pose(obs.world_m)
            if world_pose:
                prev_world[entity_id] = world_pose

        common_payload = {"source_log": source_path, "event_index": event_index, "obstacles": common_obstacles}
        sppa_all_payload = {"source_log": source_path, "event_index": event_index, "obstacles": sppa_all_obstacles}
        sppa_changed_payload = {"source_log": source_path, "event_index": event_index, "obstacles": sppa_changed_obstacles}
        common_payloads.append(common_payload)
        sppa_all_payloads.append(sppa_all_payload)
        if sppa_changed_obstacles:
            sppa_changed_payloads.append(sppa_changed_payload)

        event_rows.append(
            {
                "source_log": source_path,
                "event_index": event_index,
                "observations": len(event_observations),
                "changed_observations": len(sppa_changed_obstacles),
                "actions_json": json.dumps(actions, sort_keys=True, separators=(",", ":")),
                "common_payload_bytes": payload_bytes({"obstacles": common_obstacles}),
                "sppa_all_payload_bytes": payload_bytes({"obstacles": sppa_all_obstacles}),
                "sppa_changed_payload_bytes": payload_bytes({"obstacles": sppa_changed_obstacles}) if sppa_changed_obstacles else 0,
                "descriptor_build_us_mean": statistics.fmean(event_descriptor_us) if event_descriptor_us else 0.0,
                "schedule_us_mean": statistics.fmean(event_schedule_us) if event_schedule_us else 0.0,
                "packet_build_us_mean": statistics.fmean(event_packet_us) if event_packet_us else 0.0,
            }
        )

    return event_rows, observation_rows, common_payloads, sppa_all_payloads, sppa_changed_payloads


def source_summary(observations: list[TrackObservation], source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_source: dict[str, dict[str, Any]] = {}
    for obs in observations:
        entry = by_source.setdefault(obs.source_path, {"source_log": obs.source_path, "observations": 0, "events": set(), "tracks": set(), "labels": set()})
        entry["observations"] += 1
        entry["events"].add(obs.event_index)
        entry["tracks"].add(obs.track_key)
        entry["labels"].add(obs.class_name)
    result = []
    source_meta = {row.get("path"): row for row in source_rows}
    for source, entry in sorted(by_source.items()):
        meta = source_meta.get(source, {})
        result.append(
            {
                "source_log": source,
                "status": meta.get("status", "ok"),
                "events_in_file": meta.get("events"),
                "obstacle_ingest_observations": entry["observations"],
                "payload_events": len(entry["events"]),
                "tracks": len(entry["tracks"]),
                "labels": ",".join(sorted(str(label) for label in entry["labels"])),
                "truncated_obstacle_ingest_events": meta.get("truncated_obstacle_ingest_events"),
                "active_count_sum": meta.get("active_count_sum"),
                "active_count_events": meta.get("active_count_events"),
            }
        )
    return result


def action_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        action = str(row["action"])
        counts[action] = counts.get(action, 0) + 1
    return counts


def write_summary_md(path: Path, report: dict[str, Any]) -> None:
    rows = report["observation_summary"]
    bytes_report = report["payload_bytes"]
    lines = [
        "# SPPA Recorded Semantic Telemetry Payload Replay",
        "",
        "This artifact converts recorded `obstacle_ingest` samples into the shared `/api/ui/data` `obstacles[]` payload used by the Unreal asset and SPPA backends.",
        "It is an adapter/contract replay, not a live flight, network, packaged Unreal, render-thread, GPU, VR, or operator study.",
        "",
        "## Scope",
        "",
        "- The common payload contains `entity_id`, class/type, confidence, pose/world fields, and source metadata.",
        "- The asset backend can consume the common payload without SPPA fields.",
        "- The SPPA backend receives the same common fields plus either `sppa_descriptor` for create/regenerate events or `sppa_update_packet` for update events.",
        "- A changed-only stream suppresses no-op SPPA packets to model a more realistic transport policy.",
        "",
        "## Input Sources",
        "",
        "| Source log | Events | Observations | Tracks | Labels |",
        "|---|---:|---:|---:|---|",
    ]
    for source in report["source_summary"]:
        lines.append(
            f"| `{source['source_log']}` | {source['payload_events']} | {source['obstacle_ingest_observations']} | "
            f"{source['tracks']} | `{source['labels']}` |"
        )
    lines.extend(
        [
            "",
            "## Scheduler Actions",
            "",
            "| Action | Observations |",
            "|---|---:|",
        ]
    )
    for action, count in sorted(report["action_counts"].items()):
        lines.append(f"| `{action}` | {count} |")
    lines.extend(
        [
            "",
            "## Payload Byte Accounting",
            "",
            "| Stream | Events | Total bytes | P50 bytes/event | P95 bytes/event |",
            "|---|---:|---:|---:|---:|",
            f"| common asset-compatible payload | {bytes_report['common']['events']} | {bytes_report['common']['total_bytes']} | {bytes_report['common']['bytes_per_event']['p50']:.1f} | {bytes_report['common']['bytes_per_event']['p95']:.1f} |",
            f"| SPPA emit-all payload | {bytes_report['sppa_all']['events']} | {bytes_report['sppa_all']['total_bytes']} | {bytes_report['sppa_all']['bytes_per_event']['p50']:.1f} | {bytes_report['sppa_all']['bytes_per_event']['p95']:.1f} |",
            f"| SPPA changed-only payload | {bytes_report['sppa_changed_only']['events']} | {bytes_report['sppa_changed_only']['total_bytes']} | {bytes_report['sppa_changed_only']['bytes_per_event']['p50']:.1f} | {bytes_report['sppa_changed_only']['bytes_per_event']['p95']:.1f} |",
            "",
            "## Local Adapter Timings",
            "",
            "| Metric | n | P50 us | P95 us | P99 us |",
            "|---|---:|---:|---:|---:|",
            f"| descriptor build | {rows['descriptor_build_us']['n']} | {rows['descriptor_build_us']['p50']:.3f} | {rows['descriptor_build_us']['p95']:.3f} | {rows['descriptor_build_us']['p99']:.3f} |",
            f"| scheduler decision | {rows['schedule_us']['n']} | {rows['schedule_us']['p50']:.3f} | {rows['schedule_us']['p95']:.3f} | {rows['schedule_us']['p99']:.3f} |",
            f"| update packet build | {rows['update_packet_build_us']['n']} | {rows['update_packet_build_us']['p50']:.3f} | {rows['update_packet_build_us']['p95']:.3f} | {rows['update_packet_build_us']['p99']:.3f} |",
            "",
            "## Boundaries",
            "",
            "- The source logs contain sampled obstacle rows; some source events may be truncated and the artifact does not reconstruct unrecorded detections.",
            "- No real detector accuracy, mask quality, georeferencing accuracy, network jitter, Unreal frame time, or VR headset behavior is measured here.",
            "- This artifact supports a narrower claim: recorded semantic obstacle samples can be transformed into the same payload contract used by both spawn backends, with SPPA data attached as an optional extension.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def summarize_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    bytes_per_event = [payload_bytes({"obstacles": payload.get("obstacles", [])}) for payload in payloads]
    return {
        "events": len(payloads),
        "total_bytes": int(sum(bytes_per_event)),
        "bytes_per_event": summary([float(value) for value in bytes_per_event]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert recorded obstacle_ingest logs into shared asset/SPPA obstacles[] payloads.")
    parser.add_argument("--generator", default=str(ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"))
    parser.add_argument("--out-dir", default=str(ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_recorded_payload_replay" / "20260703_recorded_obstacle_ingest"))
    parser.add_argument("--events", nargs="+", default=[str(path) for path in DEFAULT_EVENTS])
    parser.add_argument("--shape-threshold", type=float, default=0.20)
    parser.add_argument("--allow-existing", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    if not args.allow_existing and any(out_dir.iterdir()):
        raise SystemExit(f"Output directory is not empty: {out_dir}. Use --allow-existing to overwrite files.")

    module = load_generator(Path(args.generator))
    thresholds = dict(module.DEFAULT_SCHEDULER_THRESHOLDS)
    thresholds["shape_ratio"] = float(args.shape_threshold)
    event_paths = [Path(path) for path in args.events]
    observations, source_rows = extract_observations(event_paths)
    event_rows, observation_rows, common_payloads, sppa_all_payloads, sppa_changed_payloads = make_payloads_for_events(module, observations, thresholds)

    write_csv(out_dir / "recorded_payload_event_rows.csv", event_rows)
    write_csv(out_dir / "recorded_payload_observation_rows.csv", observation_rows)
    write_jsonl(out_dir / "payload_common_asset_compatible.jsonl", common_payloads)
    write_jsonl(out_dir / "payload_sppa_emit_all.jsonl", sppa_all_payloads)
    write_jsonl(out_dir / "payload_sppa_changed_only.jsonl", sppa_changed_payloads)

    report = {
        "artifact": "sppa_recorded_semantic_telemetry_payload_replay",
        "started_utc": utc_now(),
        "generator": str(Path(args.generator)),
        "events_requested": [str(path) for path in event_paths],
        "events_found": [str(path) for path in event_paths if path.exists()],
        "shape_threshold": args.shape_threshold,
        "source_summary": source_summary(observations, source_rows),
        "observations": len(observations),
        "payload_events": len(event_rows),
        "tracks": len({(obs.source_path, obs.track_key) for obs in observations}),
        "action_counts": action_counts(observation_rows),
        "observation_summary": {
            "descriptor_build_us": summary([float(row["descriptor_build_us"]) for row in observation_rows]),
            "schedule_us": summary([float(row["schedule_us"]) for row in observation_rows]),
            "update_packet_build_us": summary([float(row["update_packet_build_us"]) for row in observation_rows]),
            "common_obstacle_payload_bytes": summary([float(row["common_obstacle_payload_bytes"]) for row in observation_rows]),
            "sppa_obstacle_payload_bytes": summary([float(row["sppa_obstacle_payload_bytes"]) for row in observation_rows]),
        },
        "payload_bytes": {
            "common": summarize_payloads(common_payloads),
            "sppa_all": summarize_payloads(sppa_all_payloads),
            "sppa_changed_only": summarize_payloads(sppa_changed_payloads),
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "git_head": git_head(),
            "git_dirty": git_dirty(),
        },
        "boundaries": [
            "Recorded obstacle_ingest samples only; source logs may be truncated.",
            "Adapter/contract replay only; not live network, packaged Unreal, render-thread, GPU, VR, or operator evidence.",
            "SPPA fields are optional extensions on the same common obstacle payload consumed by the asset backend.",
        ],
    }
    (out_dir / "recorded_payload_replay_summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_summary_md(out_dir / "recorded_payload_replay_summary.md", report)
    (out_dir / "run_manifest.json").write_text(json.dumps({**report, "ended_utc": utc_now()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "observations": len(observations), "payload_events": len(event_rows)}, sort_keys=True))


if __name__ == "__main__":
    main()
