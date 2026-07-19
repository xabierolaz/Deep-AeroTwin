# external sanity check (exploratory, post-hoc)
"""Shared utilities: paths, checkpoint manifest, sealed-package imports."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

OUTPUT_ROOT = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d\benchmarks\external_mesh_sanity")
MESHES_DIR = OUTPUT_ROOT / "meshes"
CASES_DIR = OUTPUT_ROOT / "cases"
QC_DIR = OUTPUT_ROOT / "qc"
RESULTS_DIR = OUTPUT_ROOT / "results"
SCRIPTS_DIR = OUTPUT_ROOT / "scripts"
MANIFEST_PATH = OUTPUT_ROOT / "manifest.json"
LABEL = "external sanity check (exploratory, post-hoc)"

SEALED_PACKAGE = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d\reproducibility\sppa_mvfit")
if str(SEALED_PACKAGE) not in sys.path:
    sys.path.insert(0, str(SEALED_PACKAGE))

# Sealed modules (imported, never executed as scripts, never modified).
from method.sppa_mvfit import GRAPHS, WORLD  # noqa: E402

FAMILIES = [
    "compact_vehicle",
    "articulated_vehicle",
    "quadruped",
    "branching_vertical",
    "lattice_tower",
    "rider_cycle",
]

# case selection plan: family -> list of (source, external_class, n_candidates, n_final)
SELECTION_PLAN = {
    "compact_vehicle": [("modelnet40", "car", 10, 8)],
    "articulated_vehicle": [("objaverse", "trailer_truck", 7, 5), ("objaverse", "bus_(vehicle)", 5, 3)],
    "quadruped": [("objaverse", "horse", 5, 3), ("objaverse", "dog", 5, 3), ("objaverse", "cow", 4, 3)],
    "branching_vertical": [("objaverse", "Christmas_tree", 6, 4), ("modelnet40", "plant", 6, 4)],
    "lattice_tower": [("objaverse", "water_tower", 6, 4), ("objaverse", "clock_tower", 6, 4)],
    "rider_cycle": [("objaverse", "motorcycle", 6, 4), ("objaverse", "bicycle", 6, 4)],
}

# declared metric scale: external_class -> (reference_axis, target_size_m)
SCALE_CRITERIA = {
    "car": ("x", 4.4),
    "trailer_truck": ("x", 8.8),
    "bus_(vehicle)": ("x", 8.8),
    "school_bus": ("x", 8.8),
    "horse": ("x", 2.4),
    "dog": ("x", 1.1),
    "cow": ("x", 2.4),
    "Christmas_tree": ("z", 3.6),
    "plant": ("z", 2.2),
    "water_tower": ("z", 5.5),
    "clock_tower": ("z", 5.8),
    "motorcycle": ("x", 2.2),
    "bicycle": ("x", 1.85),
}

RANDOM_SEED = 20260718


def ensure_dirs() -> None:
    for d in (MESHES_DIR, CASES_DIR, QC_DIR, RESULTS_DIR, SCRIPTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {
        "label": LABEL,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "random_seed": RANDOM_SEED,
        "steps": {},
        "downloads": {},
        "candidates": [],
        "cases": {},
        "evaluations": {},
        "notes": [],
    }


def save_manifest(manifest: dict) -> None:
    tmp = MANIFEST_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, MANIFEST_PATH)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def log_note(manifest: dict, note: str) -> None:
    manifest["notes"].append({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "note": note})
