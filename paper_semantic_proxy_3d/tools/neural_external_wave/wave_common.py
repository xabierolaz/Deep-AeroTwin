"""Shared constants and helpers for the SPPA external neural wave (Amendment 05).

This wave is a SECONDARY descriptive analysis registered in
SPPA_PROTOCOL_AMENDMENT_05_20260717.md. It never touches sealed artifacts:
sealed_predictions.bin, sealed_method_outputs.jsonl, raw_metrics.csv,
confirmatory_summary.json, integrity_manifest.json are read-only here
(raw_metrics.csv is only READ to extract the existing SPPA-MVFit clean rows).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

PAPER_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PAPER_ROOT / "reproducibility" / "sppa_mvfit"
WAVE_ROOT = PAPER_ROOT / "benchmarks" / "neural_external_wave"
RESULTS_ROOT = PAPER_ROOT / "benchmarks" / "results"
TOOLS_BENCH = PAPER_ROOT / "supporting_artifacts" / "tools" / "sppa_sota_benchmark"
REPO_ROOT = PAPER_ROOT.parent  # D:\\Deep-AeroTwin-UE57-Test
TRIPOSR_REPO = REPO_ROOT / "third_party" / "sota_3d_generators" / "TripoSR"
HUNYUAN_REPO = REPO_ROOT / "third_party" / "sota_3d_generators" / "Hunyuan3D-2"
TRIPOSR_VENV_PYTHON = REPO_ROOT / "third_party" / "sota_3d_generators" / "_venvs" / "triposr" / "Scripts" / "python.exe"

DATA_TEST = PACKAGE_ROOT / "data" / "test"
RESULTS_TEST = PACKAGE_ROOT / "results" / "test"

WORLD = {"x": (-4.8, 4.8), "y": (-3.2, 3.2), "z": (0.0, 6.4)}
EVAL_RESOLUTION = 64
RENDER_RESOLUTION = 256  # voxelization used only to RENDER the oblique view
IMAGE_SIZE = 512

# Fixed camera for condition (a) clean-crop oblique render.
CAM_AZIMUTH_DEG = 45.0
CAM_ELEVATION_DEG = 30.0

# Condition (b): the actual clean 96x96 top observation mask as the input image.
MASK_CONDITION_INDEX = 0  # "clean" row inside observation_masks.npy
MASK_TOP_INDEX = 0  # top view (index 1 is side)

SUBSET_PER_CELL = 5  # 5 per family-by-stratum cell -> 6 families x 2 strata x 5 = 60


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def cell_centers(axis: str, resolution: int):
    import numpy as np

    low, high = WORLD[axis]
    return np.linspace(low, high, resolution, endpoint=False, dtype=np.float64) + (high - low) / (2 * resolution)


def load_subset_manifest() -> dict:
    return load_json(WAVE_ROOT / "subset_manifest.json")


def load_case_actors() -> dict:
    actors: dict[str, dict] = {}
    with (DATA_TEST / "private_source_actors.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            actors[row["case_id"]] = row["actor"]
    return actors
