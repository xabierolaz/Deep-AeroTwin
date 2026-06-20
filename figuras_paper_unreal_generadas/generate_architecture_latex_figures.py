from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


REPO = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
LATEX_IMAGES = (
    REPO
    / "paper"
    / "Path_Planning_and_Obstacle_Avoidance_Real_time_Collision_Evasion"
    / "Imagenes"
)
IEEE_LATEX_IMAGES = (
    REPO
    / "paper"
    / "Path_Planning_and_Obstacle_Avoidance_Real_time_Collision_Evasion"
    / "IEEE"
    / "TII-Articles-LaTeX-template"
    / "Imagenes"
)
LATEX_IMAGE_DIRS = (LATEX_IMAGES, IEEE_LATEX_IMAGES, REPO)

INK = "#17212b"
TEXT = "#24313f"
MUTED = "#617083"
GRID = "#dde4ea"
BLUE = "#2d638f"
GREEN = "#3f8b67"
AMBER = "#b7791f"
RED = "#a83e35"
PURPLE = "#765da8"
TEAL = "#21747b"
BG = "#f7f9fb"


def copy_to_latex_images(source: Path, filename: str) -> list[str]:
    copied = []
    for image_dir in LATEX_IMAGE_DIRS:
        image_dir.mkdir(parents=True, exist_ok=True)
        target = image_dir / filename
        shutil.copyfile(source, target)
        copied.append(str(target))
    return copied


def box(ax, xy, wh, title, body, color, *, light="#ffffff", lw=1.4, title_size=7.9, body_size=5.95):
    x, y = xy
    w, h = wh
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=lw,
        edgecolor=color,
        facecolor=light,
        transform=ax.transAxes,
        zorder=4,
    )
    ax.add_patch(patch)
    ax.text(
        x + 0.02,
        y + h - 0.038,
        title,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=title_size,
        fontweight="bold",
        color=color,
        zorder=5,
    )
    ax.text(
        x + 0.02,
        y + h - 0.088,
        body,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=body_size,
        color=TEXT,
        linespacing=1.12,
        zorder=5,
    )
    return patch


def arrow(ax, a, b, color=MUTED, *, rad=0.0, lw=1.25, style="-|>"):
    ax.add_patch(
        FancyArrowPatch(
            a,
            b,
            arrowstyle=style,
            mutation_scale=10.5,
            linewidth=lw,
            color=color,
            connectionstyle=f"arc3,rad={rad}",
            transform=ax.transAxes,
            zorder=3,
        )
    )


def label(ax, xy, text, color=MUTED):
    ax.text(
        xy[0],
        xy[1],
        text,
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=5.8,
        color=color,
        bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none", alpha=0.92),
        zorder=6,
    )


def title(ax, main, sub):
    ax.text(0.025, 0.965, main, transform=ax.transAxes, ha="left", va="top", fontsize=12.0, fontweight="bold", color=INK)
    ax.text(0.025, 0.92, sub, transform=ax.transAxes, ha="left", va="top", fontsize=7.2, color=MUTED)


def prepare_ax(figsize):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_facecolor(BG)
    fig.patch.set_facecolor(BG)
    return fig, ax


def build_system_workflow() -> dict:
    fig, ax = prepare_ax((8.1, 4.6))
    title(
        ax,
        "System Workflow",
        "Closed-loop evidence path used in the paper experiments",
    )

    y = 0.565
    w = 0.155
    h = 0.19
    xs = [0.035, 0.205, 0.375, 0.545, 0.715]
    stages = [
        ("Mission profile", "waypoints\nscenario\nclass filter", BLUE),
        ("Unreal scene", "Ejea terrain\npaper profile\ncamera view", TEAL),
        ("Vision YOLO", "frame capture\ntracking\npublished tracks", GREEN),
        ("PORCE planner", "reaction logic\nlocal A*\nsafety margins", RED),
        ("ArduPilot", "GUIDED updates\nmission resume\ntelemetry", PURPLE),
    ]
    for x, (head, body, color) in zip(xs, stages):
        box(ax, (x, y), (w, h), head, body, color)
    for x in xs[:-1]:
        arrow(ax, (x + w + 0.006, y + h * 0.55), (x + 0.164, y + h * 0.55))

    arrow(ax, (0.79, y - 0.025), (0.12, y - 0.025), AMBER, rad=0.18, lw=1.35)
    label(ax, (0.455, y - 0.062), "telemetry and camera-state feedback", AMBER)

    box(
        ax,
        (0.075, 0.15),
        (0.255, 0.17),
        "Runtime contracts",
        "MAVLink telemetry\n/api/state/latest\nvision events",
        AMBER,
        light="#fffaf0",
    )
    box(
        ax,
        (0.375, 0.15),
        (0.25, 0.17),
        "Zero-trust logs",
        "trajectory.csv\nevents.jsonl\nYOLO frames",
        GREEN,
        light="#f4fbf6",
    )
    box(
        ax,
        (0.67, 0.15),
        (0.245, 0.17),
        "Paper figures",
        "top-down sequences\nablation plots\naudited case study",
        BLUE,
        light="#f3f8fc",
    )
    arrow(ax, (0.20, 0.36), (0.50, 0.335), AMBER, rad=-0.08)
    arrow(ax, (0.50, 0.36), (0.79, 0.335), GREEN, rad=-0.08)
    label(ax, (0.355, 0.37), "state exposure", AMBER)
    label(ax, (0.65, 0.37), "reproducible artifacts", GREEN)

    out = OUT / "System Workflow.png"
    fig.savefig(out, dpi=320, bbox_inches="tight", pad_inches=0.08, facecolor=BG)
    plt.close(fig)
    return {"file": str(out), "latex_files": copy_to_latex_images(out, out.name)}


def build_pipeline_a() -> dict:
    fig, ax = prepare_ax((8.4, 4.9))
    title(
        ax,
        "Pipeline A",
        "Simulation workflow wiring for perception-triggered local replanning",
    )

    box(
        ax,
        (0.035, 0.68),
        (0.19, 0.17),
        "Scenario setup",
        "Ejea origin\nobstacle profile\nclass targets",
        BLUE,
        light="#f3f8fc",
    )
    box(
        ax,
        (0.285, 0.68),
        (0.19, 0.17),
        "Simulation core",
        "ArduPilot SITL\nMAVProxy\nmission upload",
        PURPLE,
        light="#f7f4fb",
    )
    box(
        ax,
        (0.535, 0.68),
        (0.19, 0.17),
        "Digital twin",
        "Unreal 5.7\nCesium terrain\nviewport camera",
        TEAL,
        light="#f2fbfb",
    )
    box(
        ax,
        (0.775, 0.68),
        (0.18, 0.17),
        "YOLO window",
        "paper overlay\ntracks\nconfidence",
        GREEN,
        light="#f4fbf6",
    )

    box(
        ax,
        (0.155, 0.405),
        (0.23, 0.17),
        "Perception bridge",
        "screen frames\nprojection\nfiltered detections",
        GREEN,
        light="#f4fbf6",
    )
    box(
        ax,
        (0.435, 0.405),
        (0.23, 0.17),
        "PORCE decision layer",
        "reaction threshold\nA* local route\nfailsafe policy",
        RED,
        light="#fff6f5",
    )
    box(
        ax,
        (0.715, 0.405),
        (0.22, 0.17),
        "Command output",
        "position targets\nroute completion\nwaypoint resume",
        AMBER,
        light="#fffaf0",
    )

    box(
        ax,
        (0.075, 0.12),
        (0.245, 0.16),
        "Telemetry log",
        "vehicle state\nobstacle count\nevasion flag",
        PURPLE,
        light="#f7f4fb",
    )
    box(
        ax,
        (0.38, 0.12),
        (0.245, 0.16),
        "Vision log",
        "raw boxes\npublished tracks\nframe images",
        GREEN,
        light="#f4fbf6",
    )
    box(
        ax,
        (0.685, 0.12),
        (0.245, 0.16),
        "Figure scripts",
        "manifest\nplots\nLaTeX images",
        BLUE,
        light="#f3f8fc",
    )

    arrow(ax, (0.225, 0.765), (0.285, 0.765))
    arrow(ax, (0.475, 0.765), (0.535, 0.765))
    arrow(ax, (0.725, 0.765), (0.775, 0.765))
    arrow(ax, (0.84, 0.675), (0.295, 0.58), GREEN, rad=0.05)
    arrow(ax, (0.385, 0.49), (0.435, 0.49))
    arrow(ax, (0.665, 0.49), (0.715, 0.49))
    arrow(ax, (0.825, 0.405), (0.38, 0.675), AMBER, rad=-0.18)

    arrow(ax, (0.27, 0.405), (0.20, 0.285), PURPLE, rad=0.05)
    arrow(ax, (0.55, 0.405), (0.50, 0.285), GREEN, rad=0.05)
    arrow(ax, (0.825, 0.405), (0.805, 0.285), BLUE, rad=0.05)
    arrow(ax, (0.32, 0.20), (0.38, 0.20), MUTED)
    arrow(ax, (0.625, 0.20), (0.685, 0.20), MUTED)

    label(ax, (0.57, 0.615), "viewport frames", GREEN)
    label(ax, (0.685, 0.615), "detections", GREEN)
    label(ax, (0.61, 0.655), "MAVLink feedback", AMBER)
    label(ax, (0.50, 0.315), "audit trail", MUTED)

    out = OUT / "Pipeline A.png"
    fig.savefig(out, dpi=320, bbox_inches="tight", pad_inches=0.08, facecolor=BG)
    plt.close(fig)
    return {"file": str(out), "latex_files": copy_to_latex_images(out, out.name)}


def main() -> None:
    for image_dir in LATEX_IMAGE_DIRS:
        image_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "system_workflow": build_system_workflow(),
        "pipeline_a": build_pipeline_a(),
    }
    (OUT / "architecture_manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
