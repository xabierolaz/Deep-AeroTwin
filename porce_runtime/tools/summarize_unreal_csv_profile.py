import argparse
import csv
import json
import math
import statistics
from pathlib import Path


SELECTED_COLUMNS = [
    "FrameTime",
    "GameThreadTime",
    "RenderThreadTime",
    "RenderThreadTime_CriticalPath",
    "RHIThreadTime",
    "GPUTime",
    "RHI/DrawCalls",
    "RHI/PrimitivesDrawn",
    "GPUSceneInstanceCount",
    "GPUMem/LocalUsedMB",
    "GPUMem/LocalBudgetMB",
    "NumInstanceTransformUpdates",
    "Ticks/PorceSppaPackagedBenchmarkRunner",
    "Exclusive/RenderThread/AddPrimitiveSceneInfos",
    "Exclusive/RenderThread/RemovePrimitiveSceneInfos",
    "Exclusive/RenderThread/UpdatePrimitiveInstances",
    "Exclusive/RenderThread/UpdatePrimitiveTransform",
    "Exclusive/RenderThread/UpdateGPUScene",
]


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def stats(values):
    clean = [value for value in values if math.isfinite(value)]
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


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def find_profile_csvs(root):
    candidates = sorted(root.rglob("Saved/Profiling/CSV/*.csv"))
    if candidates:
        return candidates
    return sorted(root.rglob("Profile*.csv"))


def summarize_csv(path):
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    header = reader.fieldnames or []
    present = [column for column in SELECTED_COLUMNS if column in header]
    metric_stats = {}
    for column in present:
        metric_stats[column] = stats([to_float(row.get(column)) for row in rows])

    event_rows = [row.get("EVENTS", "") for row in rows if row.get("EVENTS", "")]
    event_prefixes = {}
    for event in event_rows:
        prefix = event[:160]
        event_prefixes[prefix] = event_prefixes.get(prefix, 0) + 1

    return {
        "file": str(path),
        "bytes": path.stat().st_size,
        "rows": len(rows),
        "columns": len(header),
        "selected_columns_present": present,
        "selected_columns_missing": [column for column in SELECTED_COLUMNS if column not in header],
        "event_rows": len(event_rows),
        "event_prefix_counts": event_prefixes,
        "metrics": metric_stats,
    }


def write_csv(rows, out_path):
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["file", "metric", "n", "p50", "p95", "p99", "max", "mean"])
        for profile in rows:
            for metric, metric_stats in profile["metrics"].items():
                writer.writerow(
                    [
                        profile["file"],
                        metric,
                        metric_stats.get("n", 0),
                        metric_stats.get("p50"),
                        metric_stats.get("p95"),
                        metric_stats.get("p99"),
                        metric_stats.get("max"),
                        metric_stats.get("mean"),
                    ]
                )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()

    run_dir = args.run_dir
    profiles = find_profile_csvs(run_dir)
    summaries = [summarize_csv(path) for path in profiles if path.stat().st_size > 0]
    output = {
        "claim_scope": (
            "Unreal CSV profiler summary. These counters are global to the profiled packaged process "
            "and are not phase/backend-aligned unless separate CSV events or timestamps are added."
        ),
        "run_dir": str(run_dir),
        "profile_files_found": [str(path) for path in profiles],
        "nonempty_profile_files": len(summaries),
        "profiles": summaries,
    }

    json_path = run_dir / "unreal_csv_profile_summary.json"
    csv_path = run_dir / "unreal_csv_profile_summary.csv"
    json_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    write_csv(summaries, csv_path)
    print(f"[unreal_csv_profile] profiles={len(summaries)} json={json_path} csv={csv_path}")


if __name__ == "__main__":
    main()
