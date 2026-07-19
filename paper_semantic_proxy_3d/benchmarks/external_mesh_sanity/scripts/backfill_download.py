# external sanity check (exploratory, post-hoc)
"""Backfill: download extra candidates for classes that lost too many in QC."""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from download_meshes import HF_MN40, HF_OBJAVERSE, http_get, objaverse_lvis, objaverse_object_paths, stable_jitter

BACKFILL = {
    # family: [(source, class, n_extra)]
    "articulated_vehicle": [("objaverse", "trailer_truck", 6), ("objaverse", "bus_(vehicle)", 4), ("objaverse", "school_bus", 3)],
    "branching_vertical": [("objaverse", "Christmas_tree", 6)],
    "lattice_tower": [("objaverse", "water_tower", 5), ("objaverse", "clock_tower", 5)],
    "rider_cycle": [("objaverse", "motorcycle", 4)],
}


def main() -> int:
    manifest = common.load_manifest()
    cache = common.OUTPUT_ROOT / "cache"
    object_paths = objaverse_object_paths(cache)
    lvis = objaverse_lvis(cache)
    existing_idx: dict[tuple[str, str], int] = {}
    for cand in manifest["candidates"]:
        key = (cand["family"], cand["external_class"])
        existing_idx[key] = max(existing_idx.get(key, -1), cand["candidate_index"])
    used_uids = {d.get("uid") for d in manifest["downloads"].values()}
    n_new = 0
    for family, entries in BACKFILL.items():
        for source, cls, n_extra in entries:
            pool = [u for u in lvis.get(cls, []) if u not in used_uids and u in object_paths]
            rng = random.Random(common.RANDOM_SEED + stable_jitter(f"backfill-{family}-{cls}") % 100000)
            rng.shuffle(pool)
            start = existing_idx.get((family, cls), -1) + 1
            got = 0
            for uid in pool:
                if got >= n_extra:
                    break
                idx = start + got
                cls_slug = cls.replace("_(vehicle)", "").replace("_(", "-").replace(")", "")
                case_id = f"ext-{family}-{source}-{cls_slug}-{idx:02d}"
                repo_path = object_paths[uid]
                url = f"{HF_OBJAVERSE}/resolve/main/{repo_path}"
                dest = common.MESHES_DIR / "objaverse" / cls_slug / f"{uid}.glb"
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    nbytes, sha = http_get(url, dest, max_bytes=60_000_000)
                except Exception as exc:  # noqa: BLE001
                    print(f"  FAILED {case_id}: {str(exc)[:120]}")
                    continue
                manifest["downloads"][case_id] = {
                    "url": url,
                    "mesh_relpath": str(dest.relative_to(common.OUTPUT_ROOT)),
                    "bytes": nbytes,
                    "sha256": sha,
                    "source": "objaverse",
                    "class": cls,
                    "uid": uid,
                }
                manifest["candidates"].append(
                    {
                        "case_id": case_id,
                        "family": family,
                        "source": source,
                        "external_class": cls,
                        "candidate_index": idx,
                        "n_final_target": None,
                        "status": "downloaded",
                        "mesh_relpath": str(dest.relative_to(common.OUTPUT_ROOT)),
                        "uid": uid,
                        "backfill": True,
                    }
                )
                used_uids.add(uid)
                got += 1
                n_new += 1
                print(f"  {case_id} <- uid {uid} ({nbytes/1e6:.2f} MB)")
                common.save_manifest(manifest)
    common.log_note(manifest, f"backfill downloaded {n_new} extra candidates after QC losses")
    common.save_manifest(manifest)
    print(f"backfill added {n_new} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
