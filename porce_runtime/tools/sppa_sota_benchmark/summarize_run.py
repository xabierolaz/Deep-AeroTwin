from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path


def f(row: dict[str, str], key: str) -> float:
    value = row.get(key) or "0"
    return float(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize one SPPA SOTA benchmark run.")
    parser.add_argument("run_dir")
    args = parser.parse_args()
    rows = list(csv.DictReader((Path(args.run_dir) / "objects.csv").open("r", encoding="utf-8")))
    print("model,n,median_wall_s,min_wall_s,max_wall_s,median_triangles,min_triangles,max_triangles,median_reserved_mb,max_reserved_mb")
    for model in sorted({row["model"] for row in rows}):
        subset = [row for row in rows if row["model"] == model]
        wall = [f(row, "wall_sec") for row in subset]
        triangles = [int(f(row, "triangles")) for row in subset]
        reserved = [f(row, "torch_peak_reserved_mb") for row in subset]
        print(
            ",".join(
                [
                    model,
                    str(len(subset)),
                    f"{statistics.median(wall):.4f}",
                    f"{min(wall):.4f}",
                    f"{max(wall):.4f}",
                    str(int(statistics.median(triangles))),
                    str(min(triangles)),
                    str(max(triangles)),
                    f"{statistics.median(reserved):.1f}",
                    f"{max(reserved):.1f}",
                ]
            )
        )


if __name__ == "__main__":
    main()
