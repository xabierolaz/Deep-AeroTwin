"""fig_probes_grid.png — Real-input probes grid: four real YOLOE detector
cases (biker, tower, tractor, tractor+trailer) with input crop, detector mask
evidence, SPPA complete proxy and the reproduced image/text-to-3D baselines
(Shap-E, Point-E, TripoSR, Hunyuan3D). Non-reproduced commercial/gated columns
of the source audit grid are cropped out.

Source: figures/sppa_real_input_probe_grid.png (2858x1030; grid columns of
~190.5 px starting at x = 184; first 7 data columns retained:
Input evidence | Detector probe | SPPA | Shap-E | Point-E | TripoSR | Hunyuan3D).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

REPO = Path(r"D:\AYTE DOCTOR\SPPA_semantic_proxy_3d")
SRC = REPO / "figures" / "sppa_real_input_probe_grid.png"
OUT = REPO / "figures" / "fig_probes_grid.png"

# grid geometry measured on the source image (see MANIFEST.md)
LEFT = 0
COL0_EDGE = 184
COL_W = 190.5
N_COLS = 7  # keep Input evidence .. Hunyuan3D (drops "not reproduced" red boxes)
BOTTOM = 986  # drop the source footnote line: it was laid out for the full
              # 2858 px width and is clipped mid-word at the cropped width


def main() -> None:
    im = Image.open(SRC).convert("RGB")
    right = int(round(COL0_EDGE + COL_W * N_COLS)) + 2
    crop = im.crop((LEFT, 0, right, min(BOTTOM, im.height)))
    crop.save(OUT, dpi=(300, 300))
    print(f"saved {OUT} {crop.size}")


if __name__ == "__main__":
    main()
