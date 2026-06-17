"""Analyze the D1 run to pick the bike case for Fig 4 and validate asset inputs."""
import json
from pathlib import Path

RUN = Path(r"D:\Deep-AeroTwin-UE57-Test\pipeline\logs\zero_trust\20260612_191245")
OUT = Path(r"D:\Deep-AeroTwin-UE57-Test\tmp\d1_case_analysis.json")

brain_events = []
for line in (RUN / "brain" / "events.jsonl").read_text(encoding="utf-8", errors="ignore").splitlines():
    try:
        brain_events.append(json.loads(line))
    except Exception:
        pass
vision_events = []
for line in (RUN / "vision" / "events.jsonl").read_text(encoding="utf-8", errors="ignore").splitlines():
    try:
        vision_events.append(json.loads(line))
    except Exception:
        pass

routes = [e for e in brain_events if e.get("kind") == "evasion_route_generated"]
completed = [e for e in brain_events if e.get("kind") == "evasion_completed"]
bike_routes = [e for e in routes if str(e.get("nearest_type", "")).lower() in ("bike", "biker")]

info = {
    "routes": len(routes),
    "completed": len(completed),
    "bike_routes": [
        {"ts": e["ts"], "nearest_m": e.get("nearest_distance_m"), "ids": e.get("planner_obs_ids"),
         "count": e.get("planner_obs_count"), "wp": e.get("wp_idx"), "route_points": e.get("route_points")}
        for e in bike_routes
    ],
    "completions": [{"ts": e["ts"]} for e in completed],
}

# For the best bike route (max planner obs), find nearby vision frames with published bikers
if bike_routes:
    best = max(bike_routes, key=lambda e: int(e.get("planner_obs_count", 0) or 0))
    t0 = float(best["ts"])
    info["best_bike_route_ts"] = t0
    near = []
    for evt in vision_events:
        if evt.get("kind") != "vision_frame":
            continue
        dt = float(evt["ts"]) - t0
        if abs(dt) > 1.5:
            continue
        outgoing = evt.get("outgoing") or []
        bikers = [o for o in outgoing if str(o.get("type", "")).lower() in ("bike", "biker")]
        near.append(
            {
                "frame": evt.get("frame"),
                "dt": round(dt, 3),
                "n_out": len(outgoing),
                "n_bikers": len(bikers),
                "biker_confs": [round(float(b.get("confidence", 0)), 2) for b in bikers],
                "has_bbox": all(b.get("bbox") for b in bikers),
            }
        )
    info["vision_frames_near_trigger"] = near
    # archived frames availability
    frames_dir = RUN / "vision" / "frames"
    info["archived_near"] = [
        f"yolo_{int(n['frame']):06d}.jpg"
        for n in near
        if (frames_dir / f"yolo_{int(n['frame']):06d}.jpg").exists()
    ]
# vision outgoing type sample
sample_types = set()
for evt in vision_events[:4000]:
    for o in (evt.get("outgoing") or []):
        sample_types.add(str(o.get("type")))
info["vision_outgoing_types"] = sorted(sample_types)

OUT.write_text(json.dumps(info, indent=2), encoding="utf-8")
print(json.dumps(info, indent=2)[:3000])
