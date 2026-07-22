"""Generate deterministic synthetic replay data for Pipeline B.

The output is software-only support material. It is useful for schema,
bandwidth, loss/jitter and tracking tests, but it is not flight or HMD
evidence.
"""

from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "replay" / "scenarios" / "degraded_link_operator_scene.json"
OUT_JSONL = ROOT / "replay" / "generated" / "pipeline_b_degraded_link_replay.jsonl"
OUT_TRUTH = ROOT / "replay" / "generated" / "pipeline_b_replay_ground_truth.csv"


def load_scenario() -> dict:
    return json.loads(SCENARIO.read_text(encoding="utf-8"))


def in_windows(t: float, windows: list[dict]) -> bool:
    return any(float(w["start_s"]) <= t < float(w["end_s"]) for w in windows)


def active_source_id(obj: dict, t: float) -> int:
    for sw in obj.get("id_switches", []):
        if float(sw["start_s"]) <= t < float(sw["end_s"]):
            return int(sw["source_id"])
    return int(obj["source_id"])


def world_position(obj: dict, t: float) -> dict:
    dt = max(0.0, float(t) - float(obj["start_s"]))
    initial = obj["initial_world_m"]
    velocity = obj["velocity_mps"]
    return {
        "north": float(initial["north"]) + float(velocity["north"]) * dt,
        "east": float(initial["east"]) + float(velocity["east"]) * dt,
        "up": float(initial.get("up", 0.0)) + float(velocity.get("up", 0.0)) * dt,
    }


def latlon_from_ne(home: dict, north_m: float, east_m: float) -> tuple[float, float]:
    # Equirectangular approximation, sufficient for local synthetic fixtures.
    radius_m = 6378137.0
    lat0 = math.radians(float(home["lat"]))
    dlat = north_m / radius_m
    dlon = east_m / (radius_m * max(1e-9, math.cos(lat0)))
    return (
        float(home["lat"]) + math.degrees(dlat),
        float(home["lon"]) + math.degrees(dlon),
    )


def make_bbox(obj_type: str, rng: random.Random) -> dict:
    base = {
        "bike": (58, 34),
        "cow": (72, 48),
        "tower": (38, 110),
    }.get(obj_type, (50, 50))
    return {
        "cx": round(640 + rng.uniform(-80, 80), 2),
        "cy": round(360 + rng.uniform(-45, 45), 2),
        "w": round(base[0] + rng.uniform(-5, 5), 2),
        "h": round(base[1] + rng.uniform(-5, 5), 2),
    }


def main() -> None:
    scenario = load_scenario()
    rng = random.Random(int(scenario["seed"]))
    duration_s = float(scenario["duration_s"])
    rate_hz = float(scenario["rate_hz"])
    n_frames = int(duration_s * rate_hz)
    home = scenario["home"]

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_TRUTH.parent.mkdir(parents=True, exist_ok=True)

    with OUT_JSONL.open("w", encoding="utf-8", newline="\n") as jf, OUT_TRUTH.open(
        "w", encoding="utf-8", newline=""
    ) as tf:
        truth_writer = csv.DictWriter(
            tf,
            fieldnames=[
                "scenario_id",
                "frame_id",
                "timestamp_s",
                "truth_id",
                "type",
                "active",
                "visible_to_detector",
                "source_id",
                "world_north_m",
                "world_east_m",
                "world_up_m",
            ],
        )
        truth_writer.writeheader()

        for frame_id in range(n_frames):
            t = frame_id / rate_hz
            obstacles = []

            for obj in scenario["objects"]:
                active = float(obj["start_s"]) <= t < float(obj["end_s"])
                pos = world_position(obj, t)
                occluded = active and in_windows(t, obj.get("occlusions_s", []))
                visible = bool(active and not occluded)
                source_id = active_source_id(obj, t)
                truth_writer.writerow(
                    {
                        "scenario_id": scenario["scenario_id"],
                        "frame_id": frame_id,
                        "timestamp_s": f"{t:.3f}",
                        "truth_id": obj["truth_id"],
                        "type": obj["type"],
                        "active": int(active),
                        "visible_to_detector": int(visible),
                        "source_id": source_id if visible else "",
                        "world_north_m": f"{pos['north']:.3f}",
                        "world_east_m": f"{pos['east']:.3f}",
                        "world_up_m": f"{pos['up']:.3f}",
                    }
                )

                if not visible:
                    continue

                noisy = {
                    "north": pos["north"] + rng.gauss(0.0, 0.35),
                    "east": pos["east"] + rng.gauss(0.0, 0.35),
                    "up": pos["up"] + rng.gauss(0.0, 0.10),
                }
                lat, lon = latlon_from_ne(home, noisy["north"], noisy["east"])
                distance = math.sqrt(noisy["north"] ** 2 + noisy["east"] ** 2 + noisy["up"] ** 2)
                conf = max(0.05, min(0.99, float(obj["confidence"]) + rng.gauss(0.0, 0.035)))
                yaw_deg = math.degrees(math.atan2(float(obj["velocity_mps"]["east"]), float(obj["velocity_mps"]["north"])))
                obstacle = {
                    "id": source_id,
                    "source_id": source_id,
                    "source": "replay",
                    "type": obj["type"],
                    "confidence": round(conf, 4),
                    "distance": round(distance, 3),
                    "lat": round(lat, 8),
                    "lon": round(lon, 8),
                    "world_m": {
                        "north": round(noisy["north"], 3),
                        "east": round(noisy["east"], 3),
                        "up": round(noisy["up"], 3),
                    },
                    "yaw_deg": round(yaw_deg, 2),
                    "bbox": make_bbox(obj["type"], rng),
                    "uncertainty": {
                        "position_sigma_m": 0.55,
                        "radius_95_m": 1.1,
                        "source": "synthetic_fixture",
                    },
                    "timestamp_s": round(t, 3),
                    "truth_id": obj["truth_id"],
                }
                obstacles.append(obstacle)

            payload = {
                "scenario_id": scenario["scenario_id"],
                "status": "synthetic_software_only",
                "timestamp_s": round(t, 3),
                "frame_id": frame_id,
                "obstacles": obstacles,
            }
            jf.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")

    print(f"wrote {OUT_JSONL}")
    print(f"wrote {OUT_TRUTH}")


if __name__ == "__main__":
    main()
