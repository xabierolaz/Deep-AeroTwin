"""Run the prespecified 48/64/80-cubed resolution sensitivity check."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from benchmark.test_authorization import require_test_authorization  # noqa: E402
from benchmark.metrics import voxel_iou  # noqa: E402
from method.sppa_mvfit import baseline_occupancy, infer_method, voxelize_actor  # noqa: E402
from source.source_generators import voxelize_source  # noqa: E402

DATA_ROOT = PACKAGE_ROOT / "data" / "test"
RESULTS_ROOT = PACKAGE_ROOT / "results" / "test"


def main() -> int:
    require_test_authorization()
    public = json.loads((DATA_ROOT / "public_cases.json").read_text(encoding="utf-8"))
    masks = np.load(DATA_ROOT / "observation_masks.npy", allow_pickle=False)
    actors = {}
    with (DATA_ROOT / "private_source_actors.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            actors[row["case_id"]] = row["actor"]
    selected = [index for index, case in enumerate(public) if int(case["index"]) < 5]
    methods = ("sppa_mvfit", "generic_mvfit")
    means: dict[str, dict[str, float]] = {method: {} for method in methods}
    for resolution in (48, 64, 80):
        differences = []
        for index in selected:
            case = public[index]
            gt = voxelize_source(actors[case["case_id"]], resolution)
            top, side = masks[index, 0, 0], masks[index, 0, 1]
            predictions = {}
            for method in methods:
                result = infer_method(method, case["family"], top, side)
                predictions[method] = voxelize_actor(result["actor"], resolution)
            differences.append(voxel_iou(gt, predictions["sppa_mvfit"]) - voxel_iou(gt, predictions["generic_mvfit"]))
        means["sppa_mvfit"][str(resolution)] = float(np.mean(differences))
        means["generic_mvfit"][str(resolution)] = 0.0
    change_48 = abs(means["sppa_mvfit"]["48"] - means["sppa_mvfit"]["64"])
    change_80 = abs(means["sppa_mvfit"]["80"] - means["sppa_mvfit"]["64"])
    report = {
        "schema": "sppa-mvfit-resolution-sensitivity-v1",
        "actor_count": len(selected),
        "resolutions": [48, 64, 80],
        "paired_difference_mean_by_resolution": means["sppa_mvfit"],
        "abs_change_48_vs_64": change_48,
        "abs_change_80_vs_64": change_80,
        "threshold": 0.015,
        "pass": max(change_48, change_80) < 0.015,
        "provenance": "synthetic_geometry",
    }
    (RESULTS_ROOT / "resolution_sensitivity.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
