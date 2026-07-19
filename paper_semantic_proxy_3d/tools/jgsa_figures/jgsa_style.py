"""Shared JGSA figure style: Okabe-Ito colorblind-safe palette, 300 dpi,
white background, column-legible typography. Import from every chart script.
"""
from __future__ import annotations

import matplotlib as mpl

# Okabe-Ito palette (colorblind safe)
OI = {
    "orange": "#E69F00",
    "sky_blue": "#56B4E9",
    "bluish_green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "reddish_purple": "#CC79A7",
    "black": "#000000",
    "gray": "#7F7F7F",
    "light_gray": "#BBBBBB",
}

FAMILIES = (
    "articulated_vehicle",
    "branching_vertical",
    "compact_vehicle",
    "lattice_tower",
    "quadruped",
    "rider_cycle",
)
FAMILY_LABELS = {
    "articulated_vehicle": "Articulated vehicle",
    "branching_vertical": "Branching vertical",
    "compact_vehicle": "Compact vehicle",
    "lattice_tower": "Lattice tower",
    "quadruped": "Quadruped",
    "rider_cycle": "Rider cycle",
}
STRATA = ("csg_id", "implicit_ood")
STRATUM_LABELS = {"csg_id": "CSG-ID", "implicit_ood": "Implicit-OOD"}

METHOD_COLORS = {
    "sppa_mvfit": OI["blue"],
    "generic_mvfit": OI["vermillion"],
    "nonsemantic_visual_hull": OI["bluish_green"],
    "sppa_text_only": OI["sky_blue"],
    "bbox": OI["gray"],
    "ellipsoid": OI["orange"],
    "capsule": OI["reddish_purple"],
    "billboard": OI["light_gray"],
}
METHOD_LABELS = {
    "sppa_mvfit": "SPPA-MVFit",
    "generic_mvfit": "Generic-MVFit",
    "nonsemantic_visual_hull": "Visual hull (non-semantic)",
    "sppa_text_only": "SPPA text-only",
    "bbox": "Axis-aligned box",
    "ellipsoid": "Ellipsoid",
    "capsule": "Capsule",
    "billboard": "Billboard",
}

MARGIN_IOT = 0.030  # preregistered H1 superiority margin


def apply_style() -> None:
    """Journal style: white bg, sans-serif, sizes legible at column width."""
    mpl.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 300,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#333333",
            "axes.linewidth": 0.8,
            "axes.grid": True,
            "grid.color": "#DDDDDD",
            "grid.linewidth": 0.6,
            "axes.axisbelow": True,
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.titlesize": 9.5,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "legend.frameon": False,
            "xtick.color": "#333333",
            "ytick.color": "#333333",
            "text.color": "#1A1A1A",
            "axes.labelcolor": "#1A1A1A",
            "errorbar.capsize": 2.5,
        }
    )


def save(fig, path: str) -> None:
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    print(f"saved {path}")
