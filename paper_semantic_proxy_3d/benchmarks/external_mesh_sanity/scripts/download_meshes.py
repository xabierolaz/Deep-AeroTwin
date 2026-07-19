# external sanity check (exploratory, post-hoc)
"""Download candidate meshes (ModelNet40 via HF per-file; Objaverse v1 LVIS via HF).

Checkpoint-safe: skips downloads already recorded in manifest with matching sha256.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common


def stable_jitter(text: str) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)

HF_MN40 = "https://huggingface.co/datasets/naderalfares/ModelNet40"
HF_OBJAVERSE = "https://huggingface.co/datasets/allenai/objaverse"
TIMEOUT = 120


def http_get(url: str, dest: Path, max_bytes: int = 200_000_000) -> tuple[int, str]:
    """Stream download with size guard. Returns (nbytes, sha256)."""
    import hashlib

    digest = hashlib.sha256()
    with requests.get(url, stream=True, timeout=TIMEOUT) as r:
        r.raise_for_status()
        total = 0
        with dest.open("wb") as fh:
            for chunk in r.iter_content(1 << 20):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    fh.close()
                    dest.unlink(missing_ok=True)
                    raise RuntimeError(f"oversized download aborted: {url}")
                digest.update(chunk)
                fh.write(chunk)
    return total, digest.hexdigest().upper()


def modelnet40_listing(class_name: str) -> list[str]:
    url = f"https://huggingface.co/api/datasets/naderalfares/ModelNet40/tree/main/ModelNet40/{class_name}/test"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return [item["path"] for item in r.json() if item["path"].endswith(".off")]


def objaverse_object_paths(cache: Path) -> dict[str, str]:
    """uid -> repo path (e.g. glbs/000-000/<uid>.glb). Cached locally."""
    out = cache / "object-paths.json"
    if not out.exists():
        gz = cache / "object-paths.json.gz"
        # reuse objaverse-package cache if present
        pkg_cache = Path.home() / ".objaverse" / "hf-objaverse-v1" / "object-paths.json.gz"
        if pkg_cache.exists():
            gz.write_bytes(pkg_cache.read_bytes())
        else:
            url = f"{HF_OBJAVERSE}/resolve/main/object-paths.json.gz"
            print("downloading object-paths.json.gz ...")
            nbytes, sha = http_get(url, gz)
            print(f"  {nbytes/1e6:.1f} MB sha256={sha[:16]}...")
        with gzip.open(gz, "rt", encoding="utf-8") as fh:
            json.dump(json.load(fh), out.open("w", encoding="utf-8"))
    return json.loads(out.read_text(encoding="utf-8"))


def objaverse_lvis(cache: Path) -> dict[str, list[str]]:
    out = cache / "lvis.json"
    if not out.exists():
        gz = cache / "lvis-annotations.json.gz"
        pkg_cache = Path.home() / ".objaverse" / "hf-objaverse-v1" / "lvis-annotations.json.gz"
        if pkg_cache.exists():
            gz.write_bytes(pkg_cache.read_bytes())
        else:
            url = f"{HF_OBJAVERSE}/resolve/main/lvis-annotations.json.gz"
            print("downloading lvis-annotations.json.gz ...")
            nbytes, sha = http_get(url, gz)
            print(f"  {nbytes/1e6:.1f} MB sha256={sha[:16]}...")
        with gzip.open(gz, "rt", encoding="utf-8") as fh:
            json.dump(json.load(fh), out.open("w", encoding="utf-8"))
    return json.loads(out.read_text(encoding="utf-8"))


def main() -> int:
    common.ensure_dirs()
    manifest = common.load_manifest()
    rng = random.Random(common.RANDOM_SEED)
    cache = common.OUTPUT_ROOT / "cache"
    cache.mkdir(exist_ok=True)

    # ---------- build candidate list ----------
    candidates: list[dict] = []
    seen = {c["case_id"] for c in manifest.get("candidates", [])}
    for family, entries in common.SELECTION_PLAN.items():
        for source, ext_class, n_cand, n_final in entries:
            for idx in range(n_cand):
                case_id = f"ext-{family}-{source}-{ext_class.replace('_(vehicle)', '').replace('_(', '-').replace(')', '')}-{idx:02d}"
                if case_id in seen:
                    continue
                candidates.append(
                    {
                        "case_id": case_id,
                        "family": family,
                        "source": source,
                        "external_class": ext_class,
                        "candidate_index": idx,
                        "n_final_target": n_final,
                        "status": "pending_download",
                    }
                )
    manifest["candidates"].extend(candidates)
    common.save_manifest(manifest)
    print(f"total candidates registered: {len(manifest['candidates'])}")

    # ---------- ModelNet40 downloads ----------
    mn40_needed = sorted({(c["external_class"]) for c in manifest["candidates"] if c["source"] == "modelnet40"})
    listings: dict[str, list[str]] = {}
    for cls in mn40_needed:
        listings[cls] = modelnet40_listing(cls)
        print(f"ModelNet40 {cls}: {len(listings[cls])} test meshes listed")

    for cand in manifest["candidates"]:
        if cand["source"] != "modelnet40" or cand["status"] != "pending_download":
            continue
        cls = cand["external_class"]
        pool = listings[cls]
        # deterministic per-candidate pick without replacement per class
        used = {d.get("repo_path") for d in manifest["downloads"].values() if d.get("class") == cls and d.get("source") == "modelnet40"}
        choice = None
        local_rng = random.Random(common.RANDOM_SEED + stable_jitter(cand["case_id"]) % 100000)
        order = pool[:]
        local_rng.shuffle(order)
        for p in order:
            if p not in used:
                choice = p
                break
        if choice is None:
            cand["status"] = "rejected"
            cand["reject_reason"] = "no unused modelnet40 mesh left"
            continue
        dest = common.MESHES_DIR / "modelnet40" / cls / Path(choice).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = f"{HF_MN40}/resolve/main/{choice}"
        key = cand["case_id"]
        if key in manifest["downloads"] and dest.exists():
            cand["status"] = "downloaded"
            cand["mesh_relpath"] = str(dest.relative_to(common.OUTPUT_ROOT))
            continue
        try:
            nbytes, sha = http_get(url, dest)
        except Exception as exc:  # noqa: BLE001
            cand["status"] = "download_failed"
            cand["reject_reason"] = str(exc)[:200]
            print(f"  FAILED {cand['case_id']}: {exc}")
            continue
        manifest["downloads"][key] = {
            "url": url,
            "repo_path": choice,
            "mesh_relpath": str(dest.relative_to(common.OUTPUT_ROOT)),
            "bytes": nbytes,
            "sha256": sha,
            "source": "modelnet40",
            "class": cls,
        }
        cand["status"] = "downloaded"
        cand["mesh_relpath"] = str(dest.relative_to(common.OUTPUT_ROOT))
        print(f"  {cand['case_id']} <- {choice} ({nbytes/1e6:.2f} MB)")
        common.save_manifest(manifest)  # checkpoint after each file

    # ---------- Objaverse downloads ----------
    object_paths = objaverse_object_paths(cache)
    lvis = objaverse_lvis(cache)
    for cand in manifest["candidates"]:
        if cand["source"] != "objaverse" or cand["status"] != "pending_download":
            continue
        cls = cand["external_class"]
        pool = lvis.get(cls, [])
        used = {d.get("uid") for d in manifest["downloads"].values() if d.get("class") == cls}
        local_rng = random.Random(common.RANDOM_SEED + stable_jitter(cand["case_id"]) % 100000)
        order = pool[:]
        local_rng.shuffle(order)
        uid = next((u for u in order if u not in used and u in object_paths), None)
        if uid is None:
            cand["status"] = "rejected"
            cand["reject_reason"] = f"no unused objaverse uid for {cls}"
            continue
        repo_path = object_paths[uid]
        url = f"{HF_OBJAVERSE}/resolve/main/{repo_path}"
        dest = common.MESHES_DIR / "objaverse" / cls.replace("_(vehicle)", "") / f"{uid}.glb"
        dest.parent.mkdir(parents=True, exist_ok=True)
        key = cand["case_id"]
        try:
            nbytes, sha = http_get(url, dest, max_bytes=60_000_000)
        except Exception as exc:  # noqa: BLE001
            cand["status"] = "download_failed"
            cand["reject_reason"] = str(exc)[:200]
            print(f"  FAILED {cand['case_id']}: {exc}")
            common.save_manifest(manifest)
            continue
        manifest["downloads"][key] = {
            "url": url,
            "mesh_relpath": str(dest.relative_to(common.OUTPUT_ROOT)),
            "bytes": nbytes,
            "sha256": sha,
            "source": "objaverse",
            "class": cls,
            "uid": uid,
        }
        cand["status"] = "downloaded"
        cand["mesh_relpath"] = str(dest.relative_to(common.OUTPUT_ROOT))
        cand["uid"] = uid
        print(f"  {cand['case_id']} <- uid {uid} ({nbytes/1e6:.2f} MB)")
        common.save_manifest(manifest)

    manifest["steps"]["download"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    common.log_note(manifest, "download pass finished")
    common.save_manifest(manifest)
    n_ok = sum(1 for c in manifest["candidates"] if c["status"] == "downloaded")
    print(f"downloaded candidates: {n_ok}/{len(manifest['candidates'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
