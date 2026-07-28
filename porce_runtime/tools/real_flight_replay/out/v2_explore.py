#!/usr/bin/env python3
"""Exploratory geometry check for camera_mount_v2 fit (read-only wrt inputs)."""
import csv, json, math
import numpy as np

OUT = "tools/real_flight_replay/out"
R_EARTH = 6378137.0
A_BC = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=float)
FX = FY = 1421.0
CX, CY = 640.0, 480.0
TERR = 256.38

def rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[1,0,0],[0,c,-s],[0,s,c]])
def ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c,0,s],[0,1,0],[-s,0,c]])
def rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c,-s,0],[s,c,0],[0,0,1]])

# load trajectory
traj = list(csv.DictReader(open(f"{OUT}/trajectory_video_final.csv", encoding="utf-8")))
T = {k: np.array([float(r[k]) for r in traj]) for k in ("t_unix","lat","lon","alt_msl","roll","pitch","yaw")}

# poles
poles = {}
for line in open(f"{OUT}/tower_ground_truth.csv", encoding="utf-8"):
    if line.startswith("#") or line.startswith("id,") or not line.strip():
        continue
    p = line.split(",")
    poles[p[0]] = (float(p[1]), float(p[2]))

lat0 = math.radians(T["lat"].mean())
def ll_to_ne(lat, lon, latr, lonr):
    return np.array([math.radians(lat - latr) * R_EARTH,
                     math.radians(lon - lonr) * R_EARTH * math.cos(lat0)])

def project(mount_ypr, drone_ypr, r_n):
    r_nb = rz(drone_ypr[0]) @ ry(drone_ypr[1]) @ rx(drone_ypr[2])
    r_m = rz(mount_ypr[0]) @ ry(mount_ypr[1]) @ rx(mount_ypr[2])
    r_c = A_BC.T @ r_m.T @ r_nb.T @ r_n
    if r_c[2] <= 1e-6:
        return None
    return np.array([FX * r_c[0] / r_c[2] + CX, FY * r_c[1] / r_c[2] + CY])

mounts = {
    "manual(155,-37,0)": (155.0, -37.0, 0.0),
    "selfcalib(83,-68.8,-13.3)": (83.04, -68.75, -13.29),
    "vf(100,-58.4,-15)": (100.0, -58.4, -15.0),
}

# frames with tower-ish detections
dets = {}
for line in open("experiments/sppa_detection_reference/20260721_video_final_yoloe26s/detections.jsonl"):
    d = json.loads(line)
    for det in d["detections"]:
        if det["class_name"] in ("electric pylon","power transmission tower","utility pole","antenna tower","bicycle"):
            dets.setdefault(d["frame"], []).append((det["class_name"], det["xyxy"]))

print("yaw range: %.1f .. %.1f deg" % (T["yaw"].min(), T["yaw"].max()))
print("alt rel range: %.1f .. %.1f" % ((T["alt_msl"]-TERR).min(), (T["alt_msl"]-TERR).max()))
print("lat range: %.6f..%.6f  lon: %.6f..%.6f" % (T["lat"].min(), T["lat"].max(), T["lon"].min(), T["lon"].max()))

for name, m in mounts.items():
    print("\n=== mount", name)
    vis = {p: 0 for p in poles}
    for i in range(0, len(traj), 20):
        lat, lon = T["lat"][i], T["lon"][i]
        alt = T["alt_msl"][i]
        ypr = (T["yaw"][i], T["pitch"][i], T["roll"][i])
        row = []
        for pid, (plat, plon) in poles.items():
            r_n = np.array([*ll_to_ne(plat, plon, lat, lon), alt - TERR])
            uv = project(m, ypr, r_n)
            dist = np.hypot(r_n[0], r_n[1])
            if uv is not None and -100 <= uv[0] <= 1380 and -100 <= uv[1] <= 1060:
                vis[pid] += 1
                row.append(f"{pid}@({uv[0]:.0f},{uv[1]:.0f})d{dist:.0f}")
        det_str = ""
        if i in dets:
            det_str = " DET:" + ",".join(f"{c[:4]}({b[0]:.0f},{b[1]:.0f},{b[2]:.0f},{b[3]:.0f})" for c, b in dets[i])
        print(f"f{i:3d} yaw={ypr[0]:6.1f}: " + " ".join(row) + det_str)
    print("visible counts (sampled):", vis)
