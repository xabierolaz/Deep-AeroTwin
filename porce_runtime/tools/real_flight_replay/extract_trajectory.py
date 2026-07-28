#!/usr/bin/env python3
"""Extrae la trayectoria real de un log ArduPilot .bin alineada a los frames de un vídeo.

Salida:
  - CSV con una fila por frame de vídeo: pose interpolada (lat/lon/alt + roll/pitch/yaw).
  - JSON con metadatos y validaciones (cobertura, huecos, geografía).

Solo se extrae la ventana temporal cubierta por el vídeo (requisito del experimento
Pipeline B: no interesan más datos de vuelo que los del tiempo del vídeo).

Uso:
  python extract_trajectory.py \
      --bin "papers/pipeline_a_telemetry/data/2026-07-06 09-43-41.bin" \
      --video "papers/pipeline_a_telemetry/data/M_20_1RR_VIDEO/video_2026-07-06_09-38-48_253.mp4" \
      --video-json "papers/pipeline_a_telemetry/data/M_20_1RR_VIDEO/video_2026-07-06_09-38-48_253.json" \
      --out-csv out/trajectory_m20_1rr.csv --out-meta out/trajectory_m20_1rr.meta.json
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import sys
from pathlib import Path

import cv2
from pymavlink import DFReader

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_HOME_LAT = 42.229695
REPO_HOME_LON = -1.235085


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6378137.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def unwrap_deg(seq: list[float]) -> list[float]:
    """Desenvuelve una secuencia de ángulos en grados para interpolar sin saltos 0/360."""
    if not seq:
        return seq
    out = [seq[0]]
    for v in seq[1:]:
        prev = out[-1]
        dv = (v - prev + 180.0) % 360.0 - 180.0
        out.append(prev + dv)
    return out


class Series:
    """Serie temporal ordenada con interpolación lineal."""

    def __init__(self, ts: list[float], vs: list[float]) -> None:
        self.ts = ts
        self.vs = vs

    def interp(self, t: float) -> float:
        ts, vs = self.ts, self.vs
        if t <= ts[0]:
            return vs[0]
        if t >= ts[-1]:
            return vs[-1]
        i = bisect.bisect_left(ts, t)
        t0, t1 = ts[i - 1], ts[i]
        v0, v1 = vs[i - 1], vs[i]
        if t1 <= t0:
            return v0
        f = (t - t0) / (t1 - t0)
        return v0 + f * (v1 - v0)

    def max_gap_in(self, t0: float, t1: float) -> float:
        gaps = [b - a for a, b in zip(self.ts, self.ts[1:]) if a >= t0 and b <= t1]
        return max(gaps) if gaps else float("nan")


def read_log(bin_path: Path):
    gps_t, gps_lat, gps_lon, gps_alt, gps_spd = [], [], [], [], []
    att_t, att_roll, att_pitch, att_yaw = [], [], [], []
    log = DFReader.DFReader_binary(str(bin_path))
    while True:
        m = log.recv_msg()
        if m is None:
            break
        ts = getattr(m, "_timestamp", None)
        if ts is None:
            continue
        t = m.get_type()
        if t == "GPS":
            gps_t.append(ts)
            gps_lat.append(float(m.Lat))
            gps_lon.append(float(m.Lng))
            gps_alt.append(float(m.Alt))
            gps_spd.append(float(getattr(m, "Spd", 0.0) or 0.0))
        elif t == "ATT":
            att_t.append(ts)
            att_roll.append(float(m.Roll))
            att_pitch.append(float(m.Pitch))
            att_yaw.append(float(m.Yaw))
    if not gps_t or not att_t:
        raise SystemExit("Log sin mensajes GPS o ATT con timestamp.")
    return (gps_t, gps_lat, gps_lon, gps_alt, gps_spd), (att_t, att_roll, att_pitch, att_yaw)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bin", required=True, type=Path, help="Log dataflash .bin de ArduPilot")
    ap.add_argument("--video", required=True, type=Path, help="Vídeo mp4 grabado a bordo")
    ap.add_argument("--video-json", required=True, type=Path, help="JSON de sync con video_start_unix_ms")
    ap.add_argument("--out-csv", required=True, type=Path, help="CSV de salida (una fila por frame)")
    ap.add_argument("--out-meta", type=Path, default=None, help="JSON de metadatos/validaciones")
    args = ap.parse_args()

    sync = json.loads(args.video_json.read_text(encoding="utf-8"))
    t_video0 = float(sync["video_start_unix_ms"]) / 1000.0

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise SystemExit(f"No se pudo abrir el vídeo: {args.video}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    rotation = float(cap.get(cv2.CAP_PROP_ORIENTATION_META))
    cap.release()
    if fps <= 0 or n_frames <= 0:
        raise SystemExit("Vídeo sin fps/frames válidos.")
    t_video1 = t_video0 + n_frames / fps

    (gps_t, gps_lat, gps_lon, gps_alt, gps_spd), (att_t, att_roll, att_pitch, att_yaw) = read_log(args.bin)

    # Referencia de terreno: mediana de altitud GPS en suelo al arranque (baja velocidad).
    ground_alts = [a for a, s in zip(gps_alt[:200], gps_spd[:200]) if s < 1.0]
    ground_alts.sort()
    terrain_ref = ground_alts[len(ground_alts) // 2] if ground_alts else gps_alt[0]

    s_lat = Series(gps_t, gps_lat)
    s_lon = Series(gps_t, gps_lon)
    s_alt = Series(gps_t, gps_alt)
    s_roll = Series(att_t, unwrap_deg(att_roll))
    s_pitch = Series(att_t, unwrap_deg(att_pitch))
    s_yaw = Series(att_t, unwrap_deg(att_yaw))

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with args.out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["frame_idx", "t_rel_s", "t_unix", "lat", "lon", "alt_msl", "rel_alt", "roll", "pitch", "yaw"])
        for i in range(n_frames):
            t = t_video0 + i / fps
            lat = s_lat.interp(t)
            lon = s_lon.interp(t)
            alt = s_alt.interp(t)
            roll = s_roll.interp(t)
            pitch = s_pitch.interp(t)
            yaw = s_yaw.interp(t) % 360.0
            w.writerow([i, f"{i / fps:.6f}", f"{t:.3f}", f"{lat:.7f}", f"{lon:.7f}",
                        f"{alt:.2f}", f"{alt - terrain_ref:.2f}", f"{roll:.2f}", f"{pitch:.2f}", f"{yaw:.2f}"])
            rows += 1

    # Validaciones y metadatos
    clat = s_lat.interp((t_video0 + t_video1) / 2)
    clon = s_lon.interp((t_video0 + t_video1) / 2)
    dist_home = haversine_m(clat, clon, REPO_HOME_LAT, REPO_HOME_LON)
    path_len = 0.0
    for a, b in zip(zip(gps_lat, gps_lon, gps_t), zip(gps_lat[1:], gps_lon[1:], gps_t[1:])):
        if t_video0 <= a[2] <= t_video1 and t_video0 <= b[2] <= t_video1:
            path_len += haversine_m(a[0], a[1], b[0], b[1])

    meta = {
        "bin": str(args.bin),
        "video": str(args.video),
        "video_json": str(args.video_json),
        "fps": fps,
        "frames": n_frames,
        "width": width,
        "height": height,
        "rotation_deg": rotation,
        "video_window_unix": [t_video0, t_video1],
        "log_window_unix": [gps_t[0], gps_t[-1]],
        "video_inside_log": bool(gps_t[0] <= t_video0 and t_video1 <= gps_t[-1]),
        "terrain_ref_msl": terrain_ref,
        "centroid": {"lat": clat, "lon": clon},
        "dist_centroid_to_repo_home_m": dist_home,
        "path_length_in_window_m": path_len,
        "rows_written": rows,
        "gps_msgs": len(gps_t),
        "att_msgs": len(att_t),
        "gps_max_gap_s_in_window": s_lat.max_gap_in(t_video0, t_video1),
        "att_max_gap_s_in_window": s_roll.max_gap_in(t_video0, t_video1),
    }
    if args.out_meta:
        args.out_meta.parent.mkdir(parents=True, exist_ok=True)
        args.out_meta.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print("== extract_trajectory ==")
    print(f"vídeo: {n_frames} frames @ {fps:.3f} fps = {n_frames / fps:.1f} s, {width}x{height}, rot {rotation:.0f}°")
    print(f"ventana vídeo: [{t_video0:.1f}, {t_video1:.1f}]  dentro del log: {meta['video_inside_log']}")
    print(f"terreno ref: {terrain_ref:.1f} m MSL   centroide: {clat:.6f},{clon:.6f}")
    print(f"distancia centroide->home repo: {dist_home:.0f} m   recorrido en ventana: {path_len:.0f} m")
    print(f"filas CSV: {rows}   hueco máx GPS: {meta['gps_max_gap_s_in_window']:.2f} s   ATT: {meta['att_max_gap_s_in_window']:.2f} s")
    if not meta["video_inside_log"]:
        print("AVISO: la ventana del vídeo NO está cubierta por el log.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
