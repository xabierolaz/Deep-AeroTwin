#!/usr/bin/env python3
"""Analisis de validacion geoespacial del replay (Pipeline B, M_20_1RR).

Lee los eventos obstacle_ingest del audit zero-trust del Brain (posiciones de
torre publicadas desde el video real) y las compara con el ground truth PNOA
de los apoyos. Produce:
  - out/validation_errors.csv (por observacion: error 2D, componentes N/E, rango)
  - out/validation_report.md (estadisticas por rango + globales)
  - out/validation_map.png (GT vs posiciones publicadas)
  - out/validation_error_vs_range.png

Uso:
  python analyze_replay.py [--audit-dir out/audit_replay]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

R_EARTH = 6378137.0
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"


def load_gt():
    poles = []
    for line in (OUT / "tower_ground_truth.csv").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or line.startswith("id,") or not line.strip():
            continue
        p = line.split(",")
        poles.append({"id": p[0].strip(), "lat": float(p[1]), "lon": float(p[2])})
    return poles


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-dir", type=Path, default=OUT / "audit_replay")
    ap.add_argument("--max-match-m", type=float, default=200.0)
    args = ap.parse_args()

    poles = load_gt()
    events_path = args.audit_dir / "events.jsonl"
    if not events_path.exists():
        raise SystemExit(f"sin eventos: {events_path}")

    obs = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("kind") != "obstacle_ingest":
            continue
        for s in ev.get("sample", []) or []:
            lat, lon = s.get("lat"), s.get("lon")
            if lat is None or lon is None:
                continue
            typ = str(s.get("canonical_type") or s.get("detector_type") or s.get("type") or "")
            if typ and typ != "tower":
                continue
            obs.append({
                "lat": float(lat),
                "lon": float(lon),
                "confidence": float(s.get("confidence", 0.0) or 0.0),
                "distance": float(s.get("distance", 0.0) or 0.0),
                "entity_id": str(s.get("entity_id", "")),
                "source_timestamp_s": s.get("source_timestamp_s"),
                "brain_ts": ev.get("ts"),
            })
    print(f"observaciones de torre: {len(obs)}")

    rows = []
    for o in obs:
        best = None
        for p in poles:
            dn = math.radians(p["lat"] - o["lat"]) * R_EARTH
            de = math.radians(p["lon"] - o["lon"]) * R_EARTH * math.cos(math.radians(o["lat"]))
            d = math.hypot(dn, de)
            if best is None or d < best[0]:
                best = (d, dn, de, p)
        dist, dn, de, pole = best
        if dist > args.max_match_m:
            continue
        rows.append({
            "entity_id": o["entity_id"],
            "pole_id": pole["id"],
            "err_2d_m": dist,
            "err_n_m": -dn,
            "err_e_m": -de,
            "distance_m": o["distance"],
            "confidence": o["confidence"],
            "lat": o["lat"],
            "lon": o["lon"],
            "source_timestamp_s": o["source_timestamp_s"],
        })
    print(f"emparejadas con GT (<{args.max_match_m:.0f} m): {len(rows)}")

    errs = sorted(r["err_2d_m"] for r in rows)
    csv_path = OUT / "validation_errors.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)

    def stats(errs):
        n = len(errs)
        if n == 0:
            return "n=0"
        mean = sum(errs) / n
        return f"n={n} mean={mean:.1f} m  p50={errs[n // 2]:.1f} m  p95={errs[int(0.95 * (n - 1))]:.1f} m  max={errs[-1]:.1f} m"

    report = ["# Validacion geoespacial replay M_20_1RR", ""]
    report.append(f"- Observaciones de torre publicadas: {len(obs)}")
    report.append(f"- Emparejadas con GT PNOA (<{args.max_match_m:.0f} m): {len(rows)}")
    report.append(f"- Error 2D global: {stats(errs)}")
    report.append("")
    report.append("## Por apoyo")
    for pid in sorted({r["pole_id"] for r in rows}):
        sub = sorted(r["err_2d_m"] for r in rows if r["pole_id"] == pid)
        report.append(f"- {pid}: {stats(sub)}")
    report.append("")
    report.append("## Por rango de distancia de vuelo")
    for lo, hi in ((0, 60), (60, 100), (100, 160), (160, 250)):
        sub = sorted(r["err_2d_m"] for r in rows if lo <= r["distance_m"] < hi)
        if sub:
            report.append(f"- {lo}-{hi} m: {stats(sub)}")
    report.append("")
    en_mean = sum(abs(r["err_n_m"]) for r in rows) / max(1, len(rows))
    ee_mean = sum(abs(r["err_e_m"]) for r in rows) / max(1, len(rows))
    report.append(f"Componentes: |N| medio={en_mean:.1f} m  |E| medio={ee_mean:.1f} m")
    bias_n = sum(r["err_n_m"] for r in rows) / max(1, len(rows))
    bias_e = sum(r["err_e_m"] for r in rows) / max(1, len(rows))
    report.append(f"Bias sistematico: N={bias_n:+.1f} m  E={bias_e:+.1f} m")

    (OUT / "validation_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))

    # figuras
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 7), dpi=140)
    for p in poles:
        ax.plot(p["lon"], p["lat"], "k^", ms=10)
        ax.annotate(p["id"], (p["lon"], p["lat"]), textcoords="offset points", xytext=(6, 6), fontsize=9)
    if rows:
        ax.scatter([r["lon"] for r in rows], [r["lat"] for r in rows], s=6, c="#b02a20", alpha=0.5, label="publicada")
    ax.set_xlabel("lon")
    ax.set_ylabel("lat")
    ax.set_title("Apoyos GT (triangulos) vs posiciones publicadas (puntos)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "validation_map.png")

    fig2, ax2 = plt.subplots(figsize=(7, 4.5), dpi=140)
    if rows:
        ax2.scatter([r["distance_m"] for r in rows], [r["err_2d_m"] for r in rows], s=8, alpha=0.5)
    ax2.set_xlabel("distancia de vuelo al apoyo (m)")
    ax2.set_ylabel("error 2D (m)")
    ax2.set_title("Error de georreferenciacion vs distancia")
    ax2.grid(True, alpha=0.3)
    fig2.tight_layout()
    fig2.savefig(OUT / "validation_error_vs_range.png")
    print(f"\nfiguras: {OUT/'validation_map.png'} , {OUT/'validation_error_vs_range.png'}")
    print(f"csv: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
