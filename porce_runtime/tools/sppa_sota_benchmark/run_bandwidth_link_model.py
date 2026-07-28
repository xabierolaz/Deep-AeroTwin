from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from bench_common import ROOT, rel, write_csv


DEFAULT_ROWS = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "experiments_root"
    / "sppa_descriptor_update"
    / "20260702_observed_material_v04_large"
    / "replay_update_rows.csv"
)
DEFAULT_OUT = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_bandwidth" / "20260703_link_budget_model"


def parse_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def stable_hash(text: str, n: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:n]


def compact_json_bytes(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def modeled_box_json_bytes(row: dict[str, str]) -> int:
    payload = {
        "v": "BOX-JSON-0.1",
        "id": stable_hash(row.get("track_id", "")),
        "f": int(parse_float(row.get("frame_id", "0"))),
        "t": row.get("timestamp", ""),
        "a": row.get("action", ""),
        "c": row.get("label", ""),
        "p": [0.0, 0.0, 0.0],
        "d": [1.0, 1.0, 1.0],
        "yaw": None if row.get("yaw_ambiguous") == "True" else 0.0,
        "flags": {
            "yaw_ambiguous": row.get("yaw_ambiguous") in {"True", "true", "1"},
            "scale_source": row.get("scale_source", ""),
        },
    }
    return compact_json_bytes(payload)


def modeled_box_binary_bytes(row: dict[str, str]) -> int:
    # Aligned binary model: id hash, timestamp, class id, confidence, position,
    # dimensions, yaw, flags, and small message header. It is a favorable lower
    # bound for telemetry boxes, not a measured project protocol.
    return 96 if row.get("action") == "create" else 64


def modeled_mesh_create_bytes(row: dict[str, str]) -> int:
    triangles = max(0, int(parse_float(row.get("triangles", "0"))))
    # Favorable indexed low-poly mesh model: amortized vertices + triangle
    # indices. This is intentionally cheaper than OBJ/JSON mesh transfer.
    return max(256, triangles * 48)


def pctl(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    idx = min(len(xs) - 1, max(0, int(round((len(xs) - 1) * q))))
    return xs[idx]


def summarize_group(rows: list[dict[str, str]], video_mbps: list[float]) -> dict[str, Any]:
    duration_by_source: dict[str, list[datetime]] = defaultdict(list)
    actions: dict[str, int] = defaultdict(int)
    packet_bytes: list[float] = []
    descriptor_bytes: list[float] = []
    sppa_all = 0
    sppa_changed_only = 0
    box_json_all = 0
    box_json_changed_only = 0
    box_binary_all = 0
    box_binary_changed_only = 0
    mesh_create_once = 0
    mesh_transform_updates = 0

    for row in rows:
        action = row.get("action", "")
        changed = action != "no_op"
        actions[action] += 1
        pkt = int(parse_float(row.get("packet_bytes", "0")))
        desc = int(parse_float(row.get("descriptor_bytes", "0")))
        packet_bytes.append(float(pkt))
        descriptor_bytes.append(float(desc))
        sppa_all += pkt
        if changed:
            sppa_changed_only += pkt
        bj = modeled_box_json_bytes(row)
        bb = modeled_box_binary_bytes(row)
        box_json_all += bj
        box_binary_all += bb
        if changed:
            box_json_changed_only += bj
            box_binary_changed_only += bb
        if action in {"create", "regenerate_topology"}:
            mesh_create_once += modeled_mesh_create_bytes(row)
        elif changed:
            mesh_transform_updates += 64
        ts = parse_time(row.get("timestamp", ""))
        if ts is not None:
            duration_by_source[row.get("source_log", "unknown")].append(ts)

    duration_s = 0.0
    for times in duration_by_source.values():
        if len(times) > 1:
            duration_s += max(0.0, (max(times) - min(times)).total_seconds())
    duration_s = duration_s or 0.0

    def rate(total: int | float) -> float:
        return float(total) / duration_s if duration_s > 0 else 0.0

    video_rows = {
        f"video_{str(mbps).replace('.', '_')}_mbps_Bps": (mbps * 1_000_000.0 / 8.0)
        for mbps in video_mbps
    }

    return {
        "rows": len(rows),
        "duration_s": duration_s,
        "source_logs": len(duration_by_source),
        "unique_tracks": len({r.get("track_id", "") for r in rows}),
        "unique_frames": len({(r.get("source_log", ""), r.get("frame_id", "")) for r in rows}),
        "action_counts": dict(sorted(actions.items())),
        "packet_bytes_p50": pctl(packet_bytes, 0.50),
        "packet_bytes_p95": pctl(packet_bytes, 0.95),
        "descriptor_bytes_p50": pctl(descriptor_bytes, 0.50),
        "descriptor_bytes_p95": pctl(descriptor_bytes, 0.95),
        "sppa_all_packets_total_B": sppa_all,
        "sppa_changed_only_total_B": sppa_changed_only,
        "box_json_all_total_B": box_json_all,
        "box_json_changed_only_total_B": box_json_changed_only,
        "box_binary_all_total_B": box_binary_all,
        "box_binary_changed_only_total_B": box_binary_changed_only,
        "mesh_create_plus_transform_total_B": mesh_create_once + mesh_transform_updates,
        "mesh_create_only_total_B": mesh_create_once,
        "sppa_all_packets_Bps": rate(sppa_all),
        "sppa_changed_only_Bps": rate(sppa_changed_only),
        "box_json_all_Bps": rate(box_json_all),
        "box_json_changed_only_Bps": rate(box_json_changed_only),
        "box_binary_all_Bps": rate(box_binary_all),
        "box_binary_changed_only_Bps": rate(box_binary_changed_only),
        "mesh_create_plus_transform_Bps": rate(mesh_create_once + mesh_transform_updates),
        "mesh_create_only_Bps": rate(mesh_create_once),
        "row_rate_per_s": rate(len(rows)),
        **video_rows,
    }


def fmt_bytes_per_s(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.3f} MB/s"
    if value >= 1_000:
        return f"{value / 1_000:.3f} kB/s"
    return f"{value:.1f} B/s"


def write_markdown(path: Path, rows_path: Path, summary: dict[str, Any], table_rows: list[dict[str, Any]]) -> None:
    best = min(table_rows, key=lambda r: float(r["sppa_changed_only_Bps"]))
    lines = [
        "# SPPA Link-Budget Model",
        "",
        "This artifact is a byte-accounting model over the existing SPPA descriptor/update replay.",
        "It is not a measured UAV radio link, not a video encoder benchmark, and not proof of bandwidth advantage.",
        "",
        f"- Source rows: `{rel(rows_path)}`",
        f"- Output summary: `{rel(path.with_suffix('.json'))}`",
        f"- Thresholds evaluated: {', '.join(str(r['shape_threshold']) for r in table_rows)}",
        "",
        "## Interpretation Rules",
        "",
        "- SPPA packet sizes are measured from the existing JSON update-packet artifact.",
        "- Box JSON, box binary, mesh transfer, and video rows are explicit models.",
        "- `SPPA all packets` assumes even no-op packets are emitted; this is an upper-bound policy.",
        "- `SPPA changed only` suppresses no-op packets; this is the more plausible runtime transport policy.",
        "- SPPA descriptors are normally local renderer artifacts if the ground station generates proxies from telemetry; they only become link payload if the architecture transmits descriptors directly.",
        "",
        "## Summary",
        "",
        "| shape threshold | rows | duration s | SPPA all | SPPA changed-only | box JSON all | box binary all | mesh create+xfm |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in table_rows:
        lines.append(
            "| {shape_threshold} | {rows} | {duration_s:.1f} | {sppa_all} | {sppa_changed} | {box_json} | {box_binary} | {mesh} |".format(
                shape_threshold=row["shape_threshold"],
                rows=row["rows"],
                duration_s=float(row["duration_s"]),
                sppa_all=fmt_bytes_per_s(float(row["sppa_all_packets_Bps"])),
                sppa_changed=fmt_bytes_per_s(float(row["sppa_changed_only_Bps"])),
                box_json=fmt_bytes_per_s(float(row["box_json_all_Bps"])),
                box_binary=fmt_bytes_per_s(float(row["box_binary_all_Bps"])),
                mesh=fmt_bytes_per_s(float(row["mesh_create_plus_transform_Bps"])),
            )
        )
    lines.extend(
        [
            "",
            "The lowest changed-only SPPA modeled transport rate in this replay is "
            f"{fmt_bytes_per_s(float(best['sppa_changed_only_Bps']))} at shape threshold {best['shape_threshold']}.",
            "This is still much larger than the favorable binary box model, and much smaller than the modeled compressed-video rates.",
            "Therefore the honest claim is not that SPPA beats all semantic telemetry encodings; rather, SPPA occupies a middle ground between sparse boxes and video/mesh transfer while preserving a part-based actor representation.",
            "",
            "## Video Scenarios",
            "",
            "| video scenario | bytes/s |",
            "|---|---:|",
        ]
    )
    for key, value in summary["video_scenarios_Bps"].items():
        lines.append(f"| {key} | {fmt_bytes_per_s(float(value))} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--video-mbps", type=float, nargs="+", default=[2.0, 5.0, 10.0])
    args = parser.parse_args()

    rows_by_threshold: dict[str, list[dict[str, str]]] = defaultdict(list)
    with args.rows.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rows_by_threshold[row.get("shape_threshold", "unknown")].append(row)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    table_rows: list[dict[str, Any]] = []
    for threshold, rows in sorted(rows_by_threshold.items(), key=lambda kv: float(kv[0]) if kv[0] != "unknown" else 999):
        item = summarize_group(rows, args.video_mbps)
        item["shape_threshold"] = threshold
        table_rows.append(item)

    summary = {
        "artifact": "SPPA-BANDWIDTH-LINK-MODEL-0.1",
        "source_rows": rel(args.rows),
        "output_dir": rel(args.out_dir),
        "video_scenarios_Bps": {
            f"{mbps:g} Mbps compressed video": mbps * 1_000_000.0 / 8.0
            for mbps in args.video_mbps
        },
        "model_limits": [
            "SPPA packet bytes are measured from JSON replay artifacts.",
            "Box, mesh, and video baselines are models, not measured radio-link traffic.",
            "No-op suppression is a transport policy model; the replay also reports an emit-all upper-bound policy.",
            "This does not prove bandwidth advantage for SPPA.",
        ],
        "thresholds": table_rows,
    }
    (args.out_dir / "bandwidth_link_model_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    write_csv(args.out_dir / "bandwidth_link_model_by_threshold.csv", table_rows)
    write_markdown(args.out_dir / "bandwidth_link_model_summary.md", args.rows, summary, table_rows)
    print(json.dumps({"out_dir": rel(args.out_dir), "thresholds": len(table_rows)}, sort_keys=True))


if __name__ == "__main__":
    main()
