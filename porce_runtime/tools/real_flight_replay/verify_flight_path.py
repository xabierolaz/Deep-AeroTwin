#!/usr/bin/env python3
"""Verificacion cuantitativa: el dron en Unreal hace el mismo vuelo que la
trayectoria de referencia del .bin (Pipeline B, replay M_20_1RR).

Compara tres series del flight_path_log.jsonl del driver:
  - referencia: offsets N/E de la trayectoria CSV respecto a la fila 0
  - comandada:  world_m que el Brain publico (lo que el driver ordeno)
  - real:       posicion leida del marcador en Unreal (readback)

Salida: out/flight_path_check.png + estadisticas por consola.

Uso:
  python verify_flight_path.py [--log out/flight_path_log.jsonl]
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


def nearest_error(point, path):
    """Distancia minima del punto a la polilinea (cross-track, m)."""
    px, py = point
    best = float("inf")
    for (x1, y1), (x2, y2) in zip(path, path[1:]):
        dx, dy = x2 - x1, y2 - y1
        seg2 = dx * dx + dy * dy
        if seg2 < 1e-9:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg2))
        ex, ey = x1 + t * dx, y1 + t * dy
        best = min(best, math.hypot(px - ex, py - ey))
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path, default=OUT / "flight_path_log.jsonl")
    ap.add_argument("--trajectory", type=Path, default=OUT / "trajectory_m20_1rr.csv")
    args = ap.parse_args()

    traj = list(csv.DictReader(args.trajectory.open(encoding="utf-8")))
    lat0, lon0 = float(traj[0]["lat"]), float(traj[0]["lon"])
    ref = []
    for r in traj:
        n = math.radians(float(r["lat"]) - lat0) * R_EARTH
        e = math.radians(float(r["lon"]) - lon0) * R_EARTH * math.cos(math.radians(lat0))
        ref.append((n, e))

    cmds, reads = [], []
    for line in args.log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["type"] == "cmd":
            cmds.append((rec["north"], rec["east"]))
        else:
            reads.append((rec["x"] / 100.0, rec["y"] / 100.0))

    print(f"referencia: {len(ref)} puntos   comandada: {len(cmds)}   readback: {len(reads)}")
    if not cmds or not reads:
        print("sin datos suficientes")
        return 1

    err_cmd = [nearest_error(p, ref) for p in cmds]
    err_read = [nearest_error(p, cmds) for p in reads]
    err_read_ref = [nearest_error(p, ref) for p in reads]

    def stats(name, errs):
        errs = sorted(errs)
        n = len(errs)
        mean = sum(errs) / n
        p95 = errs[int(0.95 * (n - 1))]
        return f"{name}: n={n} mean={mean:.2f} m  p95={p95:.2f} m  max={errs[-1]:.2f} m"

    print("\n== errores ==")
    print(stats("comandada (Brain world_m) vs referencia (.bin)", err_cmd))
    print(stats("real (marcador UE) vs comandada", err_read))
    print(stats("real (marcador UE) vs referencia", err_read_ref))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 7.0), dpi=140)
    ax.plot([p[1] for p in ref], [p[0] for p in ref], "-", color="#888888", lw=1.6, label="referencia (.bin)")
    ax.plot([p[1] for p in cmds], [p[0] for p in cmds], "-", color="#1f4e79", lw=1.0, alpha=0.7, label="comandada (Brain world_m)")
    ax.plot([p[1] for p in reads], [p[0] for p in reads], ".", color="#b02a20", ms=3.5, label="marcador en Unreal")
    ax.plot(ref[0][1], ref[0][0], "g^", ms=9, label="inicio (home)")
    ax.set_xlabel("Este (m)")
    ax.set_ylabel("Norte (m)")
    ax.set_title("Replay M_20_1RR: vuelo en Unreal vs trayectoria de referencia")
    ax.legend(loc="best", fontsize=8)
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.3)
    out_png = OUT / "flight_path_check.png"
    fig.tight_layout()
    fig.savefig(out_png)
    print(f"\nfigura: {out_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
