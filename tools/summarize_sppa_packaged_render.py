import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[int(pos)]
    frac = pos - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


def stats(values):
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not clean:
        return {"n": 0}
    return {
        "n": len(clean),
        "mean": statistics.fmean(clean),
        "p50": percentile(clean, 0.50),
        "p95": percentile(clean, 0.95),
        "p99": percentile(clean, 0.99),
        "max": max(clean),
        "min": min(clean),
    }


def read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def to_int(row, key):
    try:
        return int(float(row.get(key, "0") or 0))
    except ValueError:
        return 0


def to_float(row, key):
    try:
        return float(row.get(key, "nan"))
    except ValueError:
        return float("nan")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: summarize_sppa_packaged_render.py OUT_DIR")
    out_dir = Path(sys.argv[1])
    frame_path = out_dir / "packaged_frame_stats.csv"
    action_path = out_dir / "packaged_action_rows.csv"
    manifest_path = out_dir / "run_manifest.json"
    if not frame_path.exists():
        raise SystemExit(f"missing {frame_path}")
    if not action_path.exists():
        raise SystemExit(f"missing {action_path}")

    frames = read_csv(frame_path)
    actions = read_csv(action_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    frame_groups = defaultdict(list)
    for row in frames:
        if row.get("sample_type") != "measure":
            continue
        key = (row.get("backend", ""), to_int(row, "count"), to_int(row, "repetition"), row.get("phase", ""))
        frame_groups[key].append(row)

    summary_by_rep = []
    for (backend, count, repetition, phase), rows in sorted(frame_groups.items()):
        frame_ms = [to_float(row, "delta_ms") for row in rows]
        fps = [to_float(row, "fps") for row in rows]
        actors = [to_int(row, "managed_actors") for row in rows]
        components = [to_int(row, "static_mesh_components") for row in rows]
        triangles = [to_int(row, "estimated_triangles") for row in rows]
        draws = [to_int(row, "estimated_draw_calls") for row in rows]
        summary_by_rep.append(
            {
                "backend": backend,
                "count": count,
                "repetition": repetition,
                "phase": phase,
                "frame_ms": stats(frame_ms),
                "fps": stats(fps),
                "hitch_frames_gt_33ms": sum(1 for value in frame_ms if value > 33.333),
                "hitch_frames_gt_50ms": sum(1 for value in frame_ms if value > 50.0),
                "managed_actors_p50": percentile(actors, 0.50),
                "static_mesh_components_p50": percentile(components, 0.50),
                "estimated_triangles_p50": percentile(triangles, 0.50),
                "estimated_draw_calls_p50": percentile(draws, 0.50),
            }
        )

    frame_groups_agg = defaultdict(list)
    for row in frames:
        if row.get("sample_type") != "measure":
            continue
        key = (row.get("backend", ""), to_int(row, "count"), row.get("phase", ""))
        frame_groups_agg[key].append(row)

    summary = []
    for (backend, count, phase), rows in sorted(frame_groups_agg.items()):
        frame_ms = [to_float(row, "delta_ms") for row in rows]
        fps = [to_float(row, "fps") for row in rows]
        actors = [to_int(row, "managed_actors") for row in rows]
        components = [to_int(row, "static_mesh_components") for row in rows]
        triangles = [to_int(row, "estimated_triangles") for row in rows]
        draws = [to_int(row, "estimated_draw_calls") for row in rows]
        summary.append(
            {
                "backend": backend,
                "count": count,
                "phase": phase,
                "frame_ms": stats(frame_ms),
                "fps": stats(fps),
                "hitch_frames_gt_33ms": sum(1 for value in frame_ms if value > 33.333),
                "hitch_frames_gt_50ms": sum(1 for value in frame_ms if value > 50.0),
                "managed_actors_p50": percentile(actors, 0.50),
                "static_mesh_components_p50": percentile(components, 0.50),
                "estimated_triangles_p50": percentile(triangles, 0.50),
                "estimated_draw_calls_p50": percentile(draws, 0.50),
            }
        )

    action_groups = defaultdict(list)
    for row in actions:
        key = (row.get("backend", ""), to_int(row, "count"), row.get("action", ""))
        action_groups[key].append(row)

    action_summary = []
    for (backend, count, action), rows in sorted(action_groups.items()):
        elapsed = [to_float(row, "elapsed_ms") for row in rows]
        components = [to_int(row, "static_mesh_components") for row in rows]
        action_summary.append(
            {
                "backend": backend,
                "count": count,
                "action": action,
                "elapsed_ms": stats(elapsed),
                "ok_rows": sum(1 for row in rows if row.get("ok") == "1"),
                "rows": len(rows),
                "static_mesh_components_p50": percentile(components, 0.50),
            }
        )

    max_density = {}
    for backend in sorted({row["backend"] for row in summary}):
        max_density[backend] = {}
        for phase in sorted({row["phase"] for row in summary if row["backend"] == backend}):
            rows = [row for row in summary if row["backend"] == backend and row["phase"] == phase]
            ok_30 = [row["count"] for row in rows if row["frame_ms"].get("p95", float("inf")) <= 33.333]
            ok_60 = [row["count"] for row in rows if row["frame_ms"].get("p95", float("inf")) <= 16.667]
            max_density[backend][phase] = {
                "max_count_at_30fps_p95": max(ok_30) if ok_30 else None,
                "max_count_at_60fps_p95": max(ok_60) if ok_60 else None,
            }

    output = {
        "claim_scope": "Packaged executable internal obstacle replay with rendered frames. This summary uses Tick delta frame time and estimated triangles/draw calls from static mesh components; it is not an HTTP/network replay unless stated by the manifest.",
        "manifest": manifest,
        "frame_summary": summary,
        "frame_summary_by_repetition": summary_by_rep,
        "action_summary": action_summary,
        "max_density": max_density,
    }

    (out_dir / "packaged_render_summary.json").write_text(json.dumps(output, indent=2), encoding="utf-8")

    with (out_dir / "packaged_frame_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "backend",
            "count",
            "phase",
            "n",
            "frame_p50_ms",
            "frame_p95_ms",
            "frame_p99_ms",
            "fps_p50",
            "hitch_gt_33ms",
            "hitch_gt_50ms",
            "actors_p50",
            "components_p50",
            "triangles_p50",
            "estimated_draw_calls_p50",
        ])
        for row in summary:
            writer.writerow([
                row["backend"],
                row["count"],
                row["phase"],
                row["frame_ms"].get("n", 0),
                row["frame_ms"].get("p50"),
                row["frame_ms"].get("p95"),
                row["frame_ms"].get("p99"),
                row["fps"].get("p50"),
                row["hitch_frames_gt_33ms"],
                row["hitch_frames_gt_50ms"],
                row["managed_actors_p50"],
                row["static_mesh_components_p50"],
                row["estimated_triangles_p50"],
                row["estimated_draw_calls_p50"],
            ])

    print(f"[sppa_packaged_render] Summary written: {out_dir / 'packaged_render_summary.json'}")


if __name__ == "__main__":
    main()
