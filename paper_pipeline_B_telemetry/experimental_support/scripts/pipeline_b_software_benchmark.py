"""Run software-only Pipeline B benchmark over deterministic replay data."""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "replay" / "generated" / "pipeline_b_degraded_link_replay.jsonl"
TRUTH = ROOT / "replay" / "generated" / "pipeline_b_replay_ground_truth.csv"
CONFIG = ROOT / "configs" / "network_profiles.json"
OUT = ROOT / "outputs"


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    xs = sorted(float(v) for v in values)
    if len(xs) == 1:
        return xs[0]
    rank = (len(xs) - 1) * pct / 100.0
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (rank - lo)


def load_replay() -> list[dict]:
    if not REPLAY.exists():
        raise SystemExit(f"Replay file missing: {REPLAY}. Run pipeline_b_generate_replay.py first.")
    payloads = []
    with REPLAY.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                payloads.append(json.loads(line))
    return payloads


def load_truth() -> list[dict]:
    if not TRUTH.exists():
        raise SystemExit(f"Truth file missing: {TRUTH}. Run pipeline_b_generate_replay.py first.")
    with TRUTH.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def compact_size(payload: dict) -> int:
    return len(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def bandwidth_summary(payloads: list[dict]) -> dict:
    if not payloads:
        return {}
    duration_s = max(float(p["timestamp_s"]) for p in payloads) - min(float(p["timestamp_s"]) for p in payloads)
    duration_s = max(duration_s, 1e-9)
    sizes = [compact_size(p) for p in payloads]
    total_bytes = sum(sizes)
    bins: dict[int, int] = defaultdict(int)
    for payload, size in zip(payloads, sizes):
        bins[int(math.floor(float(payload["timestamp_s"])))] += int(size)
    bps_bins = [8.0 * b for b in bins.values()]
    baseline_bps = {
        "h264_low_fpv_2mbps": 2_000_000,
        "h265_low_fpv_1_2mbps": 1_200_000,
        "webrtc_fpv_4mbps": 4_000_000,
    }
    mean_bps = 8.0 * total_bytes / duration_s
    return {
        "scope": "synthetic_software_only",
        "payload_count": len(payloads),
        "duration_s": duration_s,
        "total_bytes": total_bytes,
        "mean_payload_bytes": statistics.mean(sizes),
        "p95_payload_bytes": percentile([float(s) for s in sizes], 95),
        "packet_rate_hz": len(payloads) / duration_s,
        "mean_bps": mean_bps,
        "p95_one_second_bps": percentile(bps_bins, 95),
        "baseline_bps": baseline_bps,
        "reduction_vs_baseline": {
            name: (1.0 - mean_bps / float(bps)) for name, bps in baseline_bps.items()
        },
    }


def truth_index(rows: list[dict]) -> dict[float, dict[str, dict]]:
    idx: dict[float, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        t = round(float(row["timestamp_s"]), 3)
        idx[t][row["truth_id"]] = row
    return idx


def in_outage(t: float, windows: list[dict]) -> bool:
    return any(float(w["start_s"]) <= t < float(w["end_s"]) for w in windows)


def simulate_profile(payloads: list[dict], truth_rows: list[dict], profile: dict, config: dict) -> tuple[dict, list[float]]:
    rng = random.Random(1009 + sum(ord(c) for c in profile["name"]))
    stale_threshold_s = float(config["stale_threshold_s"])
    remove_threshold_s = float(config["remove_threshold_s"])
    latency_model = config["latency_model_ms"]
    truth = truth_index(truth_rows)
    display_last_seen: dict[str, float] = {}
    display_source_ids: dict[str, int] = {}
    id_switches = 0
    delivered_packets = 0
    dropped_packets = 0
    false_fresh_count = 0
    stale_count = 0
    removed_count = 0
    active_truth_count = 0
    visible_truth_count = 0
    observed_truth_count = 0
    fragmentation_events: dict[str, int] = defaultdict(int)
    was_fragmented: dict[str, bool] = defaultdict(bool)
    latencies_ms: list[float] = []

    for payload in payloads:
        t = float(payload["timestamp_s"])
        outage = in_outage(t, profile.get("outage_windows_s", []))
        lost = outage or (rng.random() < float(profile["loss_probability"]))
        if lost:
            dropped_packets += 1
        else:
            delivered_packets += 1
            network_delay = float(profile["fixed_delay_ms"]) + rng.uniform(0.0, float(profile["jitter_ms"]))
            d2b = max(0.0, rng.gauss(float(latency_model["detector_to_brain_mean"]), float(latency_model["detector_to_brain_jitter"])))
            brain = max(0.0, rng.gauss(float(latency_model["brain_processing_mean"]), float(latency_model["brain_processing_jitter"])))
            poll = rng.uniform(0.0, float(latency_model["unreal_poll_interval"]))
            actor = max(0.0, rng.gauss(float(latency_model["unreal_actor_update_mean"]), float(latency_model["unreal_actor_update_jitter"])))
            hmd = max(0.0, rng.gauss(float(latency_model["hmd_refresh_mean"]), float(latency_model["hmd_refresh_jitter"])))
            latencies_ms.append(network_delay + d2b + brain + poll + actor + hmd)
            for obs in payload["obstacles"]:
                truth_id = str(obs.get("truth_id") or obs.get("entity_id") or obs.get("source_id"))
                source_id = int(obs.get("source_id", obs.get("id", -1)))
                if truth_id in display_source_ids and display_source_ids[truth_id] != source_id:
                    id_switches += 1
                display_source_ids[truth_id] = source_id
                display_last_seen[truth_id] = t

        current_truth = truth.get(round(t, 3), {})
        observed_now = {str(o.get("truth_id")) for o in payload["obstacles"]} if not lost else set()
        for truth_id, row in current_truth.items():
            active = int(row["active"]) == 1
            visible = int(row["visible_to_detector"]) == 1
            if active:
                active_truth_count += 1
            if visible:
                visible_truth_count += 1
            if truth_id in observed_now:
                observed_truth_count += 1
            last_seen = display_last_seen.get(truth_id)
            if active and last_seen is not None:
                age = t - last_seen
                if visible is False and age <= stale_threshold_s:
                    false_fresh_count += 1
                if age > stale_threshold_s and age <= remove_threshold_s:
                    stale_count += 1
                if age > remove_threshold_s:
                    removed_count += 1
                    if not was_fragmented[truth_id]:
                        fragmentation_events[truth_id] += 1
                        was_fragmented[truth_id] = True
                else:
                    was_fragmented[truth_id] = False

    total_packets = delivered_packets + dropped_packets
    summary = {
        "profile": profile["name"],
        "scope": "synthetic_software_only",
        "packets_total": total_packets,
        "packets_delivered": delivered_packets,
        "packets_dropped": dropped_packets,
        "drop_rate": dropped_packets / total_packets if total_packets else 0.0,
        "visible_entity_recall": observed_truth_count / visible_truth_count if visible_truth_count else 0.0,
        "false_freshness_rate": false_fresh_count / active_truth_count if active_truth_count else 0.0,
        "stale_state_rate": stale_count / active_truth_count if active_truth_count else 0.0,
        "removed_state_rate": removed_count / active_truth_count if active_truth_count else 0.0,
        "id_switches": id_switches,
        "track_fragmentation_events": sum(fragmentation_events.values()),
    }
    return summary, latencies_ms


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    payloads = load_replay()
    truth_rows = load_truth()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)

    bw = bandwidth_summary(payloads)
    profile_rows: list[dict] = []
    latency_rows: list[dict] = []
    all_latencies: dict[str, list[float]] = {}
    for profile in config["profiles"]:
        row, latencies = simulate_profile(payloads, truth_rows, profile, config)
        profile_rows.append(row)
        all_latencies[profile["name"]] = latencies
        latency_rows.append(
            {
                "profile": profile["name"],
                "scope": "synthetic_software_only",
                "samples": len(latencies),
                "mean_ms": statistics.mean(latencies) if latencies else 0.0,
                "p50_ms": percentile(latencies, 50),
                "p95_ms": percentile(latencies, 95),
                "p99_ms": percentile(latencies, 99),
            }
        )

    tracking_rows = [
        {
            "profile": row["profile"],
            "scope": row["scope"],
            "id_switches": row["id_switches"],
            "track_fragmentation_events": row["track_fragmentation_events"],
            "false_freshness_rate": row["false_freshness_rate"],
            "stale_state_rate": row["stale_state_rate"],
            "removed_state_rate": row["removed_state_rate"],
        }
        for row in profile_rows
    ]

    write_csv(OUT / "bandwidth_summary.csv", [bw])
    write_csv(OUT / "network_degradation_summary.csv", profile_rows)
    write_csv(OUT / "latency_budget_summary.csv", latency_rows)
    write_csv(OUT / "tracking_summary.csv", tracking_rows)

    summary = {
        "status": "software_only_synthetic_results_not_physical_validation",
        "replay": str(REPLAY),
        "truth": str(TRUTH),
        "bandwidth": bw,
        "network_degradation": profile_rows,
        "latency_budget": latency_rows,
        "tracking": tracking_rows,
    }
    (OUT / "pipeline_b_software_only_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )

    lines = [
        "# Pipeline B software-only synthetic benchmark summary",
        "",
        "**Status:** synthetic/software-only. These values do not replace flight, HMD, geospatial, or human-operator validation.",
        "",
        "## Bandwidth",
        "",
        f"- Payloads: {bw['payload_count']}",
        f"- Duration: {bw['duration_s']:.2f} s",
        f"- Mean semantic telemetry: {bw['mean_bps'] / 1000.0:.2f} kbps",
        f"- P95 one-second semantic telemetry: {bw['p95_one_second_bps'] / 1000.0:.2f} kbps",
        f"- Mean payload size: {bw['mean_payload_bytes']:.1f} bytes",
        "",
        "## Network degradation",
        "",
        "| Profile | Drop rate | Visible recall | False freshness | Stale rate | Fragmentation | ID switches |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in profile_rows:
        lines.append(
            f"| {row['profile']} | {row['drop_rate']:.3f} | {row['visible_entity_recall']:.3f} | "
            f"{row['false_freshness_rate']:.3f} | {row['stale_state_rate']:.3f} | "
            f"{row['track_fragmentation_events']} | {row['id_switches']} |"
        )
    lines.extend(
        [
            "",
            "## Latency budget",
            "",
            "| Profile | Samples | Mean ms | P95 ms | P99 ms |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in latency_rows:
        lines.append(
            f"| {row['profile']} | {row['samples']} | {row['mean_ms']:.1f} | {row['p95_ms']:.1f} | {row['p99_ms']:.1f} |"
        )
    lines.extend(
        [
            "",
            "## Manuscript use",
            "",
            "Use these files to replace `TBD-BW`, `TBD-LOSS`, `TBD-TRACK`, and software-only parts of `TBD-LAT` only if the paper explicitly labels them as synthetic/software-only. Do not present them as hardware or operator evidence.",
        ]
    )
    (OUT / "pipeline_b_software_only_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT / "pipeline_b_software_only_summary.md")


if __name__ == "__main__":
    main()
