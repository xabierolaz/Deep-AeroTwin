#!/usr/bin/env python3
"""Validate projection convention against manual correspondences (portrait, full video)."""
import csv, math
import numpy as np

OUT = "tools/real_flight_replay/out"
R_EARTH = 6378137.0
A_BC = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=float)
TERR = 256.4

def rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[1,0,0],[0,c,-s],[0,s,c]])
def ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c,0,s],[0,1,0],[-s,0,c]])
def rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c,-s,0],[s,c,0],[0,0,1]])

traj = list(csv.DictReader(open(f"{OUT}/trajectory_m20_1rr.csv", encoding="utf-8")))
by_idx = {int(r["frame_idx"]): r for r in traj}

poles = {}
for line in open(f"{OUT}/tower_ground_truth.csv", encoding="utf-8"):
    if line.startswith("#") or line.startswith("id,") or not line.strip():
        continue
    p = line.split(",")
    poles[p[0]] = (float(p[1]), float(p[2]))

corr = [
    {"frame_idx": 1462, "pole_id": "P3", "u": 387, "v": 843, "h_m": 10.5},
    {"frame_idx": 1637, "pole_id": "P3", "u": 629, "v": 1010, "h_m": 10.5},
    {"frame_idx": 1871, "pole_id": "P3", "u": 1044, "v": 1554, "h_m": 10.5},
    {"frame_idx": 2105, "pole_id": "P3", "u": 1909, "v": 2460, "h_m": 10.5},
]

# portrait intrinsics from manual fit: fov_v 77 over H=3840
FV = math.radians(77.0)
fy = 3840.0 / (2 * math.tan(FV / 2))
fh = 2 * math.atan((2160.0 / 3840.0) * math.tan(FV / 2))
fx = 2160.0 / (2 * math.tan(fh / 2))
print(f"portrait fx={fx:.1f} fy={fy:.1f}")

lat0 = math.radians(42.1437)
M = (155.0, -37.0, 0.0)
for c in corr:
    r = by_idx[c["frame_idx"]]
    lat, lon, alt = float(r["lat"]), float(r["lon"]), float(r["alt_msl"])
    yaw, pit, rol = float(r["yaw"]), float(r["pitch"]), float(r["roll"])
    plat, plon = poles[c["pole_id"]]
    h_m = c.get("h_m", 0.0)
    r_n = np.array([math.radians(plat - lat) * R_EARTH,
                    math.radians(plon - lon) * R_EARTH * math.cos(lat0),
                    alt - (TERR + h_m)])  # NED down-positive: drone above pole head
    r_nb = rz(yaw) @ ry(pit) @ rx(rol)
    r_m = rz(M[0]) @ ry(M[1]) @ rx(M[2])
    r_c = A_BC.T @ r_m.T @ r_nb.T @ r_n
    if r_c[2] <= 0:
        print(c["frame_idx"], "behind camera")
        continue
    u = fx * r_c[0] / r_c[2] + 1080.0
    v = fy * r_c[1] / r_c[2] + 1920.0
    print(f"f{c['frame_idx']}: proj=({u:.0f},{v:.0f}) obs=({c['u']},{c['v']}) err=({u-c['u']:+.0f},{v-c['v']:+.0f})")
