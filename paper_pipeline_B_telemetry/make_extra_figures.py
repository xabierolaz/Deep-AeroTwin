#!/usr/bin/env python3
"""Generate additional data figures for the Pipeline B VRIH paper.

All numbers come from the sealed audit artifacts of the real-flight replay
(tools/real_flight_replay/out/). No synthetic data.

Outputs (paper_pipeline_B_telemetry/figures/):
  - fig_detection_grid.png : 2x2 grid of real recorded frames with detector output
  - fig_latency_hist.png   : detection->Brain latency histogram (n=649)
  - fig_bandwidth.png      : semantic telemetry vs H.264/H.265 video bitrates
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.executable).parent.parent.parent))
from daimon_runtime import setup_plot  # noqa: E402

setup_plot()
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).parent.absolute()          # paper_pipeline_B_telemetry/ (no resolve: it is a junction)
REPO = ROOT.parent
OUT = REPO / "tools/real_flight_replay/out"
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)

RUN_TS_MIN = 1784639260.0  # clean portrait run (same filter as compute_replay_metrics.py)


def fig_detection_grid() -> None:
    """Real frames with detector output; files store content rotated 90 deg, fix with ROTATE_270."""
    eval_dir = OUT / "eval_frames"
    panels = [("t20", 20, 0.43), ("t25", 25, 0.55), ("t28", 28, 0.53), ("t32", 32, 0.35)]
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 9.6))
    for ax, (tag, t_s, conf) in zip(axes.flat, panels):
        im = Image.open(eval_dir / f"eval_{tag}.jpg").transpose(Image.ROTATE_270)
        ax.imshow(im)
        ax.set_title(f"t = {t_s} s, conf {conf:.2f}", fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])
    for ax, label in zip(axes.flat, ["(a)", "(b)", "(c)", "(d)"]):
        ax.set_xlabel(label, fontsize=11)
    fig.suptitle("Detector output on recorded real-flight frames (power-line support)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(FIGS / "fig_detection_grid.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIGS / "fig_detection_grid.png")


def load_latencies_ms() -> np.ndarray:
    # Sealed window: the clean 187.9 s replay run (554 POSTs) starting at the first
    # obstacle_ingest after RUN_TS_MIN. The audit file kept recording for hours
    # afterwards (14 GB), so we stop at the end of the sealed window.
    lat = []
    first = None
    with open(OUT / "audit_replay/brain/events.jsonl", encoding="utf-8") as f:
        for line in f:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("kind") != "obstacle_ingest":
                continue
            ts = ev.get("ts")
            if ts is None or float(ts) < RUN_TS_MIN:
                continue
            if first is None:
                first = float(ts)
            if float(ts) > first + 187.896:
                break
            for s in ev.get("sample", []) or []:
                sts = s.get("source_timestamp_s")
                brts = s.get("brain_receive_timestamp_s")
                if sts and brts:
                    lat.append(1000.0 * (float(brts) - float(sts)))
    return np.array(lat)


def fig_latency_hist() -> None:
    lat = load_latencies_ms()
    n = len(lat)
    mean = float(lat.mean())
    p95 = float(np.sort(lat)[int(0.95 * (n - 1))])
    print(f"latency: n={n} mean={mean:.1f} ms p95={p95:.1f} ms max={lat.max():.1f} ms")
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.hist(lat, bins=np.arange(0, 800, 10), color="#2c7fb8", edgecolor="white", linewidth=0.3)
    ax.set_yscale("log")
    ax.axvline(mean, color="#d7301f", lw=1.6, label=f"mean = {mean:.1f} ms")
    ax.axvline(p95, color="#252525", lw=1.4, ls="--", label=f"p95 = {p95:.1f} ms")
    ax.set_xlabel("Detection $\\rightarrow$ Brain latency (ms)")
    ax.set_ylabel("Observations (log scale)")
    ax.set_title(f"Measured semantic-telemetry latency, real-flight replay (n = {n}, max = {lat.max():.0f} ms)")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIGS / "fig_latency_hist.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIGS / "fig_latency_hist.png")


def fig_bandwidth() -> None:
    metrics = json.loads((OUT / "replay_metrics.json").read_text(encoding="utf-8"))
    sem_kbps = metrics["semantic"]["bitrate_kbps"]                    # 615.8 as emitted (187.9 s wall)
    total_bytes = metrics["semantic"]["total_bytes"]
    mission_s = 69.221529                                             # actual mission duration (video segment)
    sem_norm_kbps = 8.0 * total_bytes / mission_s / 1000.0            # 1671 normalised to real-time mission
    h264 = metrics["video_baseline"]["h264_crf_kbps"]                 # 10427
    h265 = metrics["video_baseline"]["h265_crf_kbps"]                 # 5648
    print(f"semantic={sem_kbps:.1f} norm={sem_norm_kbps:.1f} h264={h264:.1f} h265={h265:.1f} kbps")
    print(f"reductions: vs H.264 {100*(1-sem_norm_kbps/h264):.1f}%  vs H.265 {100*(1-sem_norm_kbps/h265):.1f}%")

    labels = ["Semantic\n(as emitted)", "Semantic\n(real-time mission)", "H.264\n(CRF 28)", "H.265\n(CRF 30)"]
    vals = [sem_kbps, sem_norm_kbps, h264, h265]
    colors = ["#41ab5d", "#74c476", "#969696", "#525252"]
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    bars = ax.bar(labels, vals, color=colors, width=0.62)
    ax.set_yscale("log")
    ax.set_ylabel("Bitrate (kbps, log scale)")
    ax.set_title("Semantic object telemetry vs compressed-video baselines, same flight segment")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v * 1.12, f"{v:,.0f}", ha="center", va="bottom", fontsize=9)
    ax.annotate("$-$84.0% vs H.264\n$-$70.4% vs H.265", xy=(0.69, sem_norm_kbps * 1.02), xytext=(0.55, 6200),
                fontsize=9, ha="left",
                arrowprops=dict(arrowstyle="->", color="#252525", lw=1.0))
    ax.set_ylim(300, 30000)
    fig.tight_layout()
    fig.savefig(FIGS / "fig_bandwidth.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIGS / "fig_bandwidth.png")


if __name__ == "__main__":
    fig_detection_grid()
    fig_latency_hist()
    fig_bandwidth()
