"""Step 1 (Amendment 05 E3): deterministic 60-case subset manifest.

Selection rule: inside each (family, stratum) cell of the sealed held-out test,
sort case_id lexicographically and take the first 5. 6 families x 2 strata x 5
= 60 cases. Records the public-input hashes from the sealed dataset manifest.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wave_common import (
    DATA_TEST,
    RESULTS_TEST,
    SUBSET_PER_CELL,
    WAVE_ROOT,
    load_json,
    sha256_file,
    write_json,
)


def main() -> int:
    public = load_json(DATA_TEST / "public_cases.json")
    dataset_manifest = load_json(DATA_TEST / "dataset_manifest.json")

    cells: dict[tuple[str, str], list[dict]] = {}
    for case in public:
        cells.setdefault((case["family"], case["stratum"]), []).append(case)

    selected: list[dict] = []
    for (family, stratum), cases in sorted(cells.items()):
        ordered = sorted(cases, key=lambda c: c["case_id"])
        if len(ordered) < SUBSET_PER_CELL:
            raise RuntimeError(f"cell {family}/{stratum} has only {len(ordered)} cases")
        for case in ordered[:SUBSET_PER_CELL]:
            selected.append(
                {
                    "case_id": case["case_id"],
                    "family": family,
                    "stratum": stratum,
                    "index": case["index"],
                }
            )

    if len(selected) != 60:
        raise RuntimeError(f"expected 60 selected cases, got {len(selected)}")

    manifest = {
        "schema": "sppa-neural-external-wave-subset-v1",
        "amendment": "SPPA_PROTOCOL_AMENDMENT_05_20260717.md (E3)",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "selection_rule": "first 5 case_id (lexicographic order) per family-by-stratum cell",
        "families": sorted({c["family"] for c in selected}),
        "strata": sorted({c["stratum"] for c in selected}),
        "case_count": len(selected),
        "cases": selected,
        "source_hashes": {
            "dataset_manifest_sha256": sha256_file(DATA_TEST / "dataset_manifest.json"),
            "public_cases_json_sha256": dataset_manifest.get("public_cases.json_sha256"),
            "observation_masks_npy_sha256": dataset_manifest.get("observation_masks.npy_sha256"),
            "private_source_actors_jsonl_sha256": dataset_manifest.get("private_source_actors.jsonl_sha256"),
            "raw_metrics_csv_sha256_readonly": sha256_file(RESULTS_TEST / "raw_metrics.csv"),
        },
    }
    out = WAVE_ROOT / "subset_manifest.json"
    write_json(out, manifest)
    print(f"wrote {out}")
    print(f"cases: {len(selected)}")
    for case in selected[:6]:
        print(" ", case["case_id"], case["family"], case["stratum"], case["index"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
