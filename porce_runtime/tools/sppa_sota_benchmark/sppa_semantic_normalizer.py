from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.sppa_semantic_normalizer import (  # noqa: E402,F401
    SPECIFICITY,
    normalize_detection_set,
    normalize_runtime_detection,
    normalize_single_detection,
    refine_normalized_with_observation,
    runtime_label_from_normalized,
)
