# external sanity check (exploratory, post-hoc)
"""Build per-family QC contact sheets from per-case QC pngs."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common


def main() -> int:
    manifest = common.load_manifest()
    by_family: dict[str, list[dict]] = {}
    for cand in manifest["candidates"]:
        if cand["status"] == "prepared":
            by_family.setdefault(cand["family"], []).append(cand)
    for family, cands in by_family.items():
        cands.sort(key=lambda c: c["case_id"])
        n = len(cands)
        cols = 5
        rows = math.ceil(n / cols)
        fig, axes = plt.subplots(rows, cols, figsize=(4.2 * cols, 4.2 * rows))
        axes = axes.flat if n > 1 else [axes]
        for ax, cand in zip(axes, cands):
            img = mpimg.imread(common.OUTPUT_ROOT / manifest["cases"][cand["case_id"]]["qc_png"])
            ax.imshow(img)
            short = cand["case_id"].replace(f"ext-{family}-", "")
            prob = cand.get("sanity_problems") or []
            ax.set_title(short + ("\n!! " + ";".join(prob[:2]) if prob else ""), fontsize=7, color="red" if prob else "black")
            ax.axis("off")
        for ax in list(axes)[n:]:
            ax.axis("off")
        fig.suptitle(f"{family} ({n} prepared)", fontsize=12)
        fig.tight_layout()
        out = common.QC_DIR / f"sheet_{family}.png"
        fig.savefig(out, dpi=85)
        plt.close(fig)
        print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
