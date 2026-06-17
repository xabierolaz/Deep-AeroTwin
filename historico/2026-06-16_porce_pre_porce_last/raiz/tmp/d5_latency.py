"""D5: detection -> track publish -> replan latency from zero-trust logs."""
import json
import statistics
from pathlib import Path

RUN = Path(r"D:\Deep-AeroTwin-UE57-Test\pipeline\logs\zero_trust\20260612_214341")
OUT = Path(r"D:\Deep-AeroTwin-UE57-Test\paper\Path_Planning_and_Obstacle_Avoidance_Real_time_Collision_Evasion\data\latency_metrics.json")

vision_events = []
for line in (RUN / "vision" / "events.jsonl").read_text(encoding="utf-8", errors="ignore").splitlines():
    try:
        vision_events.append(json.loads(line))
    except Exception:
        pass
brain_events = []
for line in (RUN / "brain" / "events.jsonl").read_text(encoding="utf-8", errors="ignore").splitlines():
    try:
        brain_events.append(json.loads(line))
    except Exception:
        pass

# first publish ts per vision track id
first_pub: dict[int, float] = {}
frame_ts: list[float] = []
for evt in vision_events:
    if evt.get("kind") != "vision_frame":
        continue
    frame_ts.append(float(evt["ts"]))
    out = evt.get("outgoing")
    if not isinstance(out, list):
        continue
    for obs in out:
        if not isinstance(obs, dict):
            continue
        oid = obs.get("id")
        if oid is None:
            continue
        oid = int(oid)
        if oid not in first_pub:
            first_pub[oid] = float(evt["ts"])

# vision frame period (capture+inference+publish loop)
periods = [b - a for a, b in zip(frame_ts, frame_ts[1:]) if 0 < b - a < 1.0]

# replan latency: for each route event, newest planner obstacle's first-publish -> route ts
lat_new_track_to_replan = []
seen_ids: set[str] = set()
for evt in brain_events:
    if evt.get("kind") != "evasion_route_generated":
        continue
    ids = evt.get("planner_obs_ids") or []
    ts = float(evt["ts"])
    fresh = [i for i in ids if i not in seen_ids]
    seen_ids.update(ids)
    for ide in fresh:
        if not str(ide).startswith("vision:"):
            continue
        try:
            vid = int(str(ide).split(":", 1)[1])
        except ValueError:
            continue
        t_pub = first_pub.get(vid)
        if t_pub is None:
            continue
        dt = ts - t_pub
        if 0 <= dt < 30:
            lat_new_track_to_replan.append(dt)

# replan cadence while engaged
route_ts = [float(e["ts"]) for e in brain_events if e.get("kind") == "evasion_route_generated"]
replan_gaps = [b - a for a, b in zip(route_ts, route_ts[1:]) if 0 < b - a < 5.0]


def stats(vals):
    if not vals:
        return None
    vals = sorted(vals)
    return {
        "n": len(vals),
        "median_s": round(statistics.median(vals), 3),
        "p95_s": round(vals[int(0.95 * (len(vals) - 1))], 3),
        "mean_s": round(statistics.fmean(vals), 3),
    }


result = {
    "run": RUN.name,
    "vision_frame_period": stats(periods),
    "vision_fps_median": round(1.0 / statistics.median(periods), 1) if periods else None,
    "first_publish_to_replan": stats(lat_new_track_to_replan),
    "replan_interval_while_engaged": stats(replan_gaps),
}
OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
