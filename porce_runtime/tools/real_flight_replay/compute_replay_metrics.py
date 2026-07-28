#!/usr/bin/env python3
"""Metricas del replay M_20_1RR para el paper (Pipeline B).

Calcula desde el audit del Brain (corrida portrait limpia):
  1. Bandwidth de telemetria semantica REAL (bytes de los POST /api/obstacles).
  2. Latencia extremo a extremo: t_deteccion (source) -> t_recepcion Brain
     (+ periodo de poll del componente Unreal ~200 ms -> proxy visible).
  3. Comparacion con baseline de video (H.264/H.265 del propio clip).

Uso:
  python compute_replay_metrics.py
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
AUDIT = OUT / "audit_replay/brain/events.jsonl"
VIDEO = ROOT.parent.parent.parent / "papers/pipeline_a_telemetry/data/M_20_1RR_VIDEO/video_2026-07-06_09-38-48_253.mp4"
RUN_TS_MIN = 1784639260.0  # corrida portrait limpia (15:08+)


def semantic_stats():
    posts = []
    for line in AUDIT.read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("kind") != "obstacle_ingest":
            continue
        ts = ev.get("ts")
        if ts is None or float(ts) < RUN_TS_MIN:
            continue
        posts.append(ev)
    posts.sort(key=lambda e: float(e["ts"]))
    if not posts:
        return None
    # bytes reales del cuerpo de cada POST (reconstruido del payload auditado)
    sizes = []
    lat_det_brain = []
    for ev in posts:
        payload = {"obstacles": ev.get("sample", [])}
        sizes.append(len(json.dumps(payload).encode("utf-8")))
        for s in ev.get("sample", []) or []:
            sts = s.get("source_timestamp_s")
            brts = s.get("brain_receive_timestamp_s")
            if sts and brts:
                lat_det_brain.append(float(brts) - float(sts))
    t0, t1 = float(posts[0]["ts"]), float(posts[-1]["ts"])
    dur = t1 - t0
    total_bytes = sum(sizes)
    return {
        "posts": len(posts),
        "duration_s": dur,
        "total_bytes": total_bytes,
        "mean_payload_bytes": total_bytes / max(1, len(posts)),
        "bitrate_kbps": (8.0 * total_bytes / dur) / 1000.0 if dur > 0 else 0.0,
        "posts_per_s": len(posts) / dur if dur > 0 else 0.0,
        "lat_det_to_brain_ms": {
            "n": len(lat_det_brain),
            "mean": 1000 * sum(lat_det_brain) / max(1, len(lat_det_brain)),
            "p95": 1000 * sorted(lat_det_brain)[int(0.95 * max(0, len(lat_det_brain) - 1))] if lat_det_brain else None,
        },
    }


def video_baseline():
    st = VIDEO.stat().st_size
    # duracion ~69.22 s
    dur = 69.221529
    orig_kbps = 8.0 * st / dur / 1000.0
    results = {"original_mp4_bytes": st, "original_kbps": orig_kbps}
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        for codec, args in (("h264", ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28"]),
                            ("h265", ["-c:v", "libx265", "-preset", "veryfast", "-crf", "30"])):
            out = OUT / f"baseline_{codec}.mp4"
            if not out.exists():
                subprocess.run([exe, "-y", "-i", str(VIDEO), "-t", "69.3"] + args + [str(out)],
                               capture_output=True, timeout=600)
            if out.exists():
                sz = out.stat().st_size
                results[f"{codec}_crf_bytes"] = sz
                results[f"{codec}_crf_kbps"] = 8.0 * sz / dur / 1000.0
    except Exception as e:
        results["baseline_error"] = str(e)
    return results


def main() -> int:
    sem = semantic_stats()
    vid = video_baseline()
    poll_s = 0.2  # poll del componente ~5 Hz (conservador)
    render_s = 0.05  # estimacion conservadora spawn+render frame

    print("== Telemetria semantica REAL (corrida portrait) ==")
    if sem:
        print(f"POST /api/obstacles: {sem['posts']} en {sem['duration_s']:.0f} s ({sem['posts_per_s']:.1f}/s)")
        print(f"payload medio: {sem['mean_payload_bytes']:.0f} B   total: {sem['total_bytes'] / 1000:.0f} kB")
        print(f"** bitrate semantico real: {sem['bitrate_kbps']:.1f} kbps **")
        lb = sem["lat_det_to_brain_ms"]
        if lb["n"]:
            print(f"latencia deteccion->Brain: n={lb['n']} mean={lb['mean']:.0f} ms p95={lb['p95']:.0f} ms")
    print("\n== Baseline video ==")
    for k, v in vid.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.1f}")
        else:
            print(f"  {k}: {v}")
    print("\n== Latencia E2E estimada (deteccion -> proxy visible) ==")
    if sem and sem["lat_det_to_brain_ms"]["n"]:
        e2e_mean = sem["lat_det_to_brain_ms"]["mean"] + 1000 * (poll_s / 2 + render_s)
        e2e_p95 = (sem["lat_det_to_brain_ms"]["p95"] or 0) + 1000 * (poll_s + render_s)
        print(f"media ~{e2e_mean:.0f} ms   p95 ~{e2e_p95:.0f} ms (det->Brain + poll UE/2 + spawn)")
    print("\n== Comparacion (RQ1) ==")
    if sem and "h264_crf_kbps" in vid:
        red_h264 = (vid["h264_crf_kbps"] - sem["bitrate_kbps"]) / vid["h264_crf_kbps"]
        print(f"semantico {sem['bitrate_kbps']:.1f} kbps vs H.264 {vid['h264_crf_kbps']:.0f} kbps -> reduccion {100 * red_h264:.1f}%")
        if "h265_crf_kbps" in vid:
            red_h265 = (vid["h265_crf_kbps"] - sem["bitrate_kbps"]) / vid["h265_crf_kbps"]
            print(f"semantico {sem['bitrate_kbps']:.1f} kbps vs H.265 {vid['h265_crf_kbps']:.0f} kbps -> reduccion {100 * red_h265:.1f}%")

    metrics = {"semantic": sem, "video_baseline": vid,
               "e2e_latency_ms": {"mean": e2e_mean if sem else None, "p95": e2e_p95 if sem else None,
                                  "model": "det->Brain (audit) + pollUE/2 + spawn(50ms)"}}
    (OUT / "replay_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"\nescrito: {OUT / 'replay_metrics.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
