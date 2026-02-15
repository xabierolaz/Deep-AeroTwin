import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Ultralytics writes settings under %APPDATA% by default, which can be locked down
# in some Windows environments. It honors YOLO_CONFIG_DIR as an override.
_default_yolo_cfg = REPO_ROOT / "pipeline" / "logs"
if "YOLO_CONFIG_DIR" not in os.environ:
    _default_yolo_cfg.mkdir(parents=True, exist_ok=True)
    os.environ["YOLO_CONFIG_DIR"] = str(_default_yolo_cfg)

from ultralytics import YOLO  # noqa: E402

DEFAULTS = [
    REPO_ROOT / "pipeline" / "weights" / "yolo_3d_dome_v1_best.pt",
    REPO_ROOT / "yolo11n.pt",
    REPO_ROOT / "3d_to_dataset_xabi" / "yolo11n.pt",
]


def _resolve_model_path(argv: list[str]) -> Path:
    # Allow passing an explicit model path: `python tools/inspect_model.py path/to/model.pt`
    if len(argv) > 1 and argv[1].strip():
        return Path(argv[1].strip())

    for cand in DEFAULTS:
        if cand.exists():
            return cand

    raise SystemExit("No model (.pt) found.")


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else sys.argv
    model_path = _resolve_model_path(argv)

    print(f"--- INSPECTING: {model_path} ---")

    try:
        model = YOLO(str(model_path))
        print("\nTRAINED CLASSES:")
        print(model.names)

        # Quick verification.
        names = model.names
        if isinstance(names, dict) and "tower" in names.values():
            print("\n[VERDICT] -> Custom model (contains 'tower').")
        elif isinstance(names, dict) and "cow" in names.values() and "person" in names.values():
            print("\n[VERDICT] -> Base YOLO COCO model.")
            print("It will detect cows/persons but not towers specifically.")
        else:
            print("\n[VERDICT] -> Unknown model.")
    except Exception as e:
        print(f"Error loading model: {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

