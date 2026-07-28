from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import statistics
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bench_common import ROOT

CLASS_ALIASES = {
    "bike": "biker",
    "bicycle": "biker",
    "person_on_bike": "biker",
}


@dataclass
class TrackObservation:
    source_path: str
    event_index: int
    ts: float
    iso_utc: str
    track_key: str
    class_name: str
    confidence: float | None
    bbox: dict[str, Any] | None
    world_m: dict[str, Any] | None
    lat: float | None
    lon: float | None
    yaw_deg: float | None
    heading_deg: float | None
    track_age_s: float | None
    track_seen_count: int | None


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


def summarize_us(values_ns: list[int]) -> dict[str, float | int]:
    values_us = [float(v) / 1000.0 for v in values_ns]
    if not values_us:
        return {"n": 0, "min_us": 0.0, "p50_us": 0.0, "p95_us": 0.0, "p99_us": 0.0, "max_us": 0.0}
    return {
        "n": len(values_us),
        "min_us": min(values_us),
        "mean_us": statistics.fmean(values_us),
        "p50_us": pct(values_us, 50),
        "p95_us": pct(values_us, 95),
        "p99_us": pct(values_us, 99),
        "max_us": max(values_us),
    }


def normalize_class(name: str) -> str:
    key = str(name or "unknown").strip().lower()
    return CLASS_ALIASES.get(key, key)


def track_key(row: dict[str, Any]) -> str:
    entity = row.get("entity_id")
    if entity:
        return str(entity)
    source = row.get("source_id")
    if source is not None:
        return f"{row.get('source', 'source')}:{source}"
    return f"brain:{row.get('id', 'unknown')}"


def as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return None
        return result
    except Exception:
        return None


def as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def extract_observations(paths: list[Path]) -> tuple[list[TrackObservation], list[dict[str, Any]]]:
    observations: list[TrackObservation] = []
    source_rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            source_rows.append({"path": str(path), "status": "missing", "events": 0, "observations": 0})
            continue
        events = 0
        obs_before = len(observations)
        truncated = 0
        active_count_sum = 0
        active_count_events = 0
        config: dict[str, Any] = {}
        for event_index, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines()):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            events += 1
            if event.get("kind") == "brain_config":
                config = event
            if event.get("kind") != "obstacle_ingest":
                continue
            if event.get("sample_truncated"):
                truncated += 1
            active_count = as_int(event.get("active_count"))
            if active_count is not None:
                active_count_sum += active_count
                active_count_events += 1
            for row in event.get("sample") or []:
                observations.append(
                    TrackObservation(
                        source_path=str(path),
                        event_index=event_index,
                        ts=float(event.get("ts", 0.0) or 0.0),
                        iso_utc=str(event.get("iso_utc", "")),
                        track_key=track_key(row),
                        class_name=normalize_class(str(row.get("type", "unknown"))),
                        confidence=as_float(row.get("confidence")),
                        bbox=row.get("bbox") if isinstance(row.get("bbox"), dict) else None,
                        world_m=row.get("world_m") if isinstance(row.get("world_m"), dict) else None,
                        lat=as_float(row.get("lat")),
                        lon=as_float(row.get("lon")),
                        yaw_deg=as_float(row.get("yaw_deg")),
                        heading_deg=as_float(row.get("heading_deg")),
                        track_age_s=as_float(row.get("track_age_s")),
                        track_seen_count=as_int(row.get("track_seen_count")),
                    )
                )
        source_rows.append(
            {
                "path": str(path),
                "status": "ok",
                "events": events,
                "observations": len(observations) - obs_before,
                "truncated_obstacle_ingest_events": truncated,
                "active_count_sum": active_count_sum,
                "active_count_events": active_count_events,
                "workflow": config.get("workflow"),
                "control_mode": config.get("control_mode"),
                "porce_enable_evasion": config.get("porce_enable_evasion"),
                "obstacle_token_enabled": config.get("obstacle_token_enabled"),
            }
        )
    observations.sort(key=lambda item: (item.source_path, item.ts, item.event_index, item.track_key))
    return observations, source_rows


def bbox_shape(bbox: dict[str, Any] | None) -> tuple[float | None, float | None]:
    if not bbox:
        return None, None
    width = as_float(bbox.get("w") or bbox.get("width"))
    height = as_float(bbox.get("h") or bbox.get("height"))
    if width is None:
        x1 = as_float(bbox.get("x1") or bbox.get("xmin"))
        x2 = as_float(bbox.get("x2") or bbox.get("xmax"))
        if x1 is not None and x2 is not None:
            width = abs(x2 - x1)
    if height is None:
        y1 = as_float(bbox.get("y1") or bbox.get("ymin"))
        y2 = as_float(bbox.get("y2") or bbox.get("ymax"))
        if y1 is not None and y2 is not None:
            height = abs(y2 - y1)
    return width, height


def shape_changed(prev: TrackObservation, curr: TrackObservation, threshold_ratio: float) -> bool:
    prev_w, prev_h = bbox_shape(prev.bbox)
    curr_w, curr_h = bbox_shape(curr.bbox)
    for a, b in ((prev_w, curr_w), (prev_h, curr_h)):
        if a is None or b is None:
            continue
        denom = max(abs(a), 1e-6)
        if abs(b - a) / denom >= threshold_ratio:
            return True
    return False


def update_proxy_state(state: dict[str, Any], obs: TrackObservation) -> dict[str, Any]:
    pose = state.setdefault("pose", {})
    pose["lat"] = obs.lat
    pose["lon"] = obs.lon
    pose["world_m"] = obs.world_m
    pose["yaw_deg"] = obs.yaw_deg
    pose["heading_deg"] = obs.heading_deg
    state["confidence"] = obs.confidence
    state["last_ts"] = obs.ts
    state["track_seen_count"] = obs.track_seen_count
    state["track_age_s"] = obs.track_age_s
    return state


def analyze_policy(
    observations: list[TrackObservation],
    shape_threshold_ratio: float,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[int]]:
    states: dict[tuple[str, str], dict[str, Any]] = {}
    prev_obs: dict[tuple[str, str], TrackObservation] = {}
    rows: list[dict[str, Any]] = []
    update_times_ns: list[int] = []
    counts = {"create": 0, "pose_update": 0, "shape_param_update": 0, "regenerate_topology": 0}
    reason_counts: dict[str, int] = {}
    conservative_rebuild_count = 0

    for obs in observations:
        key = (obs.source_path, obs.track_key)
        action = "pose_update"
        reason = "pose_or_confidence_update"
        if key not in states:
            states[key] = {"class_name": obs.class_name, "created_ts": obs.ts}
            action = "create"
            reason = "first_observation_for_track"
        else:
            prev = prev_obs[key]
            if obs.class_name != prev.class_name:
                action = "regenerate_topology"
                reason = "class_change"
                states[key]["class_name"] = obs.class_name
            elif shape_changed(prev, obs, shape_threshold_ratio):
                action = "shape_param_update"
                reason = f"bbox_shape_change_ge_{shape_threshold_ratio:.2f}"
                conservative_rebuild_count += 1

        start = time.perf_counter_ns()
        update_proxy_state(states[key], obs)
        elapsed = time.perf_counter_ns() - start
        update_times_ns.append(elapsed)

        counts[action] += 1
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        rows.append(
            {
                "source_path": obs.source_path,
                "event_index": obs.event_index,
                "ts": obs.ts,
                "iso_utc": obs.iso_utc,
                "track_key": obs.track_key,
                "class_name": obs.class_name,
                "action": action,
                "reason": reason,
                "conservative_rebuild_if_non_parametric": action == "shape_param_update",
                "confidence": obs.confidence,
                "track_seen_count": obs.track_seen_count,
                "track_age_s": obs.track_age_s,
                "update_cpu_ns": elapsed,
            }
        )
        prev_obs[key] = obs

    by_source: dict[str, dict[str, Any]] = {}
    for row in rows:
        source = row["source_path"]
        entry = by_source.setdefault(
            source,
            {
                "source_path": source,
                "first_ts": row["ts"],
                "last_ts": row["ts"],
                "observations": 0,
                "tracks": set(),
                "create": 0,
                "pose_update": 0,
                "shape_param_update": 0,
                "regenerate_topology": 0,
                "conservative_rebuild_if_non_parametric": 0,
            },
        )
        entry["first_ts"] = min(entry["first_ts"], row["ts"])
        entry["last_ts"] = max(entry["last_ts"], row["ts"])
        entry["observations"] += 1
        entry["tracks"].add(row["track_key"])
        entry[row["action"]] += 1
        if row["conservative_rebuild_if_non_parametric"]:
            entry["conservative_rebuild_if_non_parametric"] += 1

    source_summaries = []
    for entry in by_source.values():
        duration_s = max(0.0, float(entry["last_ts"]) - float(entry["first_ts"]))
        tracks_n = len(entry["tracks"])
        source_summaries.append(
            {
                "source_path": entry["source_path"],
                "duration_s": duration_s,
                "observations": entry["observations"],
                "tracks": tracks_n,
                "create": entry["create"],
                "pose_update": entry["pose_update"],
                "shape_param_update": entry["shape_param_update"],
                "regenerate_topology": entry["regenerate_topology"],
                "conservative_rebuild_if_non_parametric": entry["conservative_rebuild_if_non_parametric"],
                "topology_regenerations_per_track": entry["regenerate_topology"] / tracks_n if tracks_n else 0.0,
                "topology_regenerations_per_minute": entry["regenerate_topology"] / (duration_s / 60.0) if duration_s > 0 else 0.0,
                "shape_updates_per_track": entry["shape_param_update"] / tracks_n if tracks_n else 0.0,
                "shape_updates_per_minute": entry["shape_param_update"] / (duration_s / 60.0) if duration_s > 0 else 0.0,
            }
        )

    summary = {
        "observations": len(observations),
        "tracks": len({(obs.source_path, obs.track_key) for obs in observations}),
        "actions": counts,
        "reason_counts": reason_counts,
        "conservative_rebuild_if_non_parametric": conservative_rebuild_count,
        "sources": source_summaries,
    }
    return rows, summary, update_times_ns


def benchmark_creation(module, classes: list[str], iterations: int, warmup: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_times: list[int] = []
    for class_name in classes:
        builder_key = normalize_class(class_name)
        builder = module.BUILDERS.get(builder_key)
        if builder is None:
            rows.append({"class_name": class_name, "status": "missing_builder"})
            continue
        for _ in range(warmup):
            mesh = module.Mesh()
            builder(mesh)
        times: list[int] = []
        vertices = 0
        faces = 0
        for _ in range(iterations):
            start = time.perf_counter_ns()
            mesh = module.Mesh()
            builder(mesh)
            elapsed = time.perf_counter_ns() - start
            times.append(elapsed)
            vertices = len(mesh.vertices)
            faces = len(mesh.faces)
        all_times.extend(times)
        summary = summarize_us(times)
        rows.append(
            {
                "class_name": class_name,
                "builder_key": builder_key,
                "status": "ok",
                "vertices": vertices,
                "faces": faces,
                **summary,
            }
        )
    return rows, summarize_us(all_times)


def benchmark_debug_export(module, classes: list[str], iterations: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_times: list[int] = []
    with tempfile.TemporaryDirectory(prefix="sppa_export_") as tmp:
        tmp_path = Path(tmp)
        for class_name in classes:
            builder_key = normalize_class(class_name)
            builder = module.BUILDERS.get(builder_key)
            if builder is None:
                rows.append({"class_name": class_name, "status": "missing_builder"})
                continue
            times: list[int] = []
            for index in range(iterations):
                mesh = module.Mesh()
                builder(mesh)
                obj_path = tmp_path / f"{builder_key}_{index}.obj"
                mtl_path = tmp_path / f"{builder_key}_{index}.mtl"
                start = time.perf_counter_ns()
                module.write_mtl(str(mtl_path))
                module.write_obj(mesh, str(obj_path), mtl_path.name)
                elapsed = time.perf_counter_ns() - start
                times.append(elapsed)
            all_times.extend(times)
            rows.append({"class_name": class_name, "builder_key": builder_key, "status": "ok", **summarize_us(times)})
    return rows, summarize_us(all_times)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    creation = report["creation_cpu_us"]
    update = report["update_policy_cpu_us"]
    policy = report["track_policy"]
    lines = [
        "# SPPA Track Lifecycle Measurement",
        "",
        "This report separates measured CPU costs from policy-derived track events.",
        "It is not an Unreal frame-time benchmark and it is not a native SPPA runtime trace.",
        "",
        "## Cost Summary",
        "",
        "| Metric | n | P50 | P95 | P99 | Max | Unit |",
        "|---|---:|---:|---:|---:|---:|---|",
        f"| In-memory proxy creation | {creation['n']} | {creation['p50_us']:.3f} | {creation['p95_us']:.3f} | {creation['p99_us']:.3f} | {creation['max_us']:.3f} | microseconds/object |",
        f"| Pose/state update decision | {update['n']} | {update['p50_us']:.3f} | {update['p95_us']:.3f} | {update['p99_us']:.3f} | {update['max_us']:.3f} | microseconds/track observation |",
        "",
        "Debug OBJ/MTL export is deliberately reported separately because the intended runtime backend should keep proxies resident rather than exporting files per frame.",
        "",
        "## Regeneration Policy Results",
        "",
        f"- Observations: {policy['observations']}",
        f"- Tracks: {policy['tracks']}",
        f"- Creates: {policy['actions']['create']}",
        f"- Pose/confidence updates: {policy['actions']['pose_update']}",
        f"- Shape/scale parameter updates: {policy['actions']['shape_param_update']}",
        f"- Topology regenerations: {policy['actions']['regenerate_topology']}",
        f"- Conservative full-rebuild upper bound if the proxy were not parametric: {policy['conservative_rebuild_if_non_parametric']}",
        "",
        "| Source | Duration s | Tracks | Observations | Creates | Pose updates | Shape updates | Topology regens | Topology regen/track | Topology regen/min |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for source in policy["sources"]:
        lines.append(
            f"| `{source['source_path']}` | {source['duration_s']:.3f} | {source['tracks']} | "
            f"{source['observations']} | {source['create']} | {source['pose_update']} | "
            f"{source['shape_param_update']} | {source['regenerate_topology']} | "
            f"{source['topology_regenerations_per_track']:.3f} | "
            f"{source['topology_regenerations_per_minute']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Honest Interpretation",
            "",
            "- Creation cost is measured for the current Python procedural template builder, in memory.",
            "- Update cost is measured for policy/state update only; Unreal actor transform and render-thread cost remain pending.",
            "- Regeneration frequency is derived from recorded `obstacle_ingest` track observations using the declared policy: first observation creates; stable observations update; bbox-scale changes are counted as parametric shape updates; class changes are counted as topology regeneration.",
            "- The available logs do not contain native SPPA create/update/regenerate events, so this must be described as policy-implied regeneration, not directly observed runtime regeneration.",
            "- Some source logs report truncated obstacle samples; lifecycle counts are therefore based on recorded samples, while `source_logs.csv` records active-count sums where available.",
            "- If a paper needs a final operational number, the next required artifact is an Unreal trace that logs semantic proxy actor create/update/reconfigure/despawn events with frame timestamps.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure SPPA creation/update costs and policy-derived track regeneration.")
    parser.add_argument(
        "--generator",
        default=str(ROOT / "XYT-xabi-yolo-telemetry" / "xyt_generate_3d.py"),
    )
    parser.add_argument(
        "--events",
        nargs="+",
        default=[
            str(ROOT / "pipeline" / "logs" / "zero_trust" / "20260701_144043" / "real_twin" / "brain" / "events.jsonl"),
            str(ROOT / "pipeline" / "logs" / "zero_trust" / "20260701_144043" / "simulation" / "brain" / "events.jsonl"),
        ],
    )
    parser.add_argument("--out-dir", default=str(ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_lifecycle_measurement" / "20260701_144043"))
    parser.add_argument("--classes", nargs="+", default=["bike", "cow", "tower", "car", "truck", "tractor", "tree"])
    parser.add_argument("--iterations", type=int, default=10000)
    parser.add_argument("--warmup", type=int, default=500)
    parser.add_argument("--export-iterations", type=int, default=100)
    parser.add_argument("--shape-threshold-ratio", type=float, default=0.20)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    module = load_generator(Path(args.generator))
    creation_rows, creation_summary = benchmark_creation(module, args.classes, args.iterations, args.warmup)
    export_rows, export_summary = benchmark_debug_export(module, args.classes, args.export_iterations)
    observations, source_rows = extract_observations([Path(p) for p in args.events])
    lifecycle_rows, policy_summary, update_times = analyze_policy(observations, args.shape_threshold_ratio)
    update_summary = summarize_us(update_times)

    report = {
        "measurement_type": "python_cpu_and_policy_derived_from_logs",
        "generator": str(Path(args.generator)),
        "events": args.events,
        "creation_cpu_us": creation_summary,
        "debug_obj_export_cpu_us": export_summary,
        "update_policy_cpu_us": update_summary,
        "track_policy": policy_summary,
        "source_logs": source_rows,
        "caveats": [
            "Creation cost is Python procedural template construction, not Unreal actor spawn.",
            "Debug OBJ/MTL export is not the intended runtime path and is reported separately.",
            "Update cost is descriptor/pose state update only, not Unreal render-thread frame time.",
            "Regenerations are policy-implied from obstacle_ingest logs; native SPPA runtime events were not present in the source logs.",
        ],
    }

    (out_dir / "sppa_lifecycle_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_csv(out_dir / "creation_cost_by_class.csv", creation_rows)
    write_csv(out_dir / "debug_export_cost_by_class.csv", export_rows)
    write_csv(out_dir / "source_logs.csv", source_rows)
    write_csv(out_dir / "policy_lifecycle_events.csv", lifecycle_rows)
    write_markdown(out_dir / "sppa_lifecycle_report.md", report)
    print(out_dir)


if __name__ == "__main__":
    main()
