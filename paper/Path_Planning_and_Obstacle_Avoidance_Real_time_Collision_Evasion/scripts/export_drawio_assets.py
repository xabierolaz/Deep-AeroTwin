from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "figures"

DRAWIO_FILES = [
    FIGURES / "pipeline_a_architecture.drawio",
    FIGURES / "porce_method_flow.drawio",
    FIGURES / "porce_detection_montage.drawio",
    FIGURES / "porce_case_trajectory.drawio",
]

NPX = "npx.cmd" if os.name == "nt" else "npx"


def flatten_png(path: Path) -> None:
    with Image.open(path) as img:
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        merged = Image.alpha_composite(bg, rgba).convert("RGB")
        merged.save(path)


def export_one(drawio_path: Path) -> Path:
    png_path = drawio_path.with_suffix(".png")
    tmp_path = png_path.with_name(f"{drawio_path.stem}.from_drawio.tmp.png")
    cmd = [NPX, "draw.io-export", str(drawio_path), "-o", str(tmp_path)]
    subprocess.run(cmd, check=True, cwd=ROOT)
    flatten_png(tmp_path)
    tmp_path.replace(png_path)
    return png_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export drawio figures to PNG with white background flattening.")
    parser.add_argument("files", nargs="*", help="Optional drawio filenames or stems to export")
    return parser.parse_args()


def resolve_targets(file_args: list[str]) -> list[Path]:
    if not file_args:
        return DRAWIO_FILES
    mapping: dict[str, Path] = {}
    for path in DRAWIO_FILES:
        mapping[path.name] = path
        mapping[path.stem] = path
    targets: list[Path] = []
    for arg in file_args:
        if arg not in mapping:
            raise SystemExit(f"Unknown drawio target: {arg}")
        targets.append(mapping[arg])
    return targets


def main() -> int:
    args = parse_args()
    targets = resolve_targets(args.files)
    missing = [path for path in targets if not path.exists()]
    if missing:
        for path in missing:
            print(f"Missing drawio file: {path}")
        return 1

    for drawio_path in targets:
        png_path = export_one(drawio_path)
        print(f"Exported {drawio_path.name} -> {png_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
