import csv
import copy
import hashlib
import json
import os
import platform
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import unreal

REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
TEMP_PREFIX = "DAT_SPPA_ComponentReplay_"

def utc_now():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def parse_int_list(raw, default):
    if not raw:
        return default
    values = []
    for item in str(raw).replace(";", ",").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            value = int(item)
        except ValueError:
            continue
        if value > 0:
            values.append(value)
    return values or default

def stable_hash_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

def read_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def load_descriptors(max_items):
    sources = [
        REPO / "experiments" / "sppa_descriptor_update" / "20260702_descriptor_v04_atomic" / "descriptor_smoke_samples.jsonl",
        REPO / "experiments" / "sppa_descriptor_update" / "20260702_descriptor_v04_atomic" / "synthetic_descriptor_samples.jsonl",
    ]
    descriptors = []
    for source in sources:
        for row in read_jsonl(source):
            if row.get("descriptor_schema") == "SPPA-DESC-0.2" and row.get("parts"):
                descriptors.append(row)
                if len(descriptors) >= max_items:
                    return descriptors
    if descriptors:
        return descriptors
    return [{
        "descriptor_schema": "SPPA-DESC-0.2",
        "descriptor_id": "sppa-inline-component-replay-car",
        "input": {"normalized_label": "car", "confidence": 0.9},
        "semantic": {"normalized_label": "car", "class_confidence": 0.9},
        "runtime_policy": {"action": "create"},
        "scale": {"dims_m": {"length": 2.4, "width": 1.2, "height": 1.3}},
        "parts": [
            {"role": "body", "primitive": "box", "local_pose": {"center": [0, 0, 0.7], "axis": "z"}, "scale": [2.4, 1.2, 0.5], "material_role": "vehicle_body", "evidence_source": "semantic_prior"},
            {"role": "cab", "primitive": "box", "local_pose": {"center": [0.35, 0, 1.1], "axis": "z"}, "scale": [0.8, 0.9, 0.45], "material_role": "vehicle_cab", "evidence_source": "semantic_prior"},
        ],
    }]

def descriptor_label(descriptor):
    semantic = descriptor.get("semantic") or {}
    input_obj = descriptor.get("input") or {}
    return str(semantic.get("normalized_label") or input_obj.get("normalized_label") or input_obj.get("raw_label") or "unknown")

def descriptor_confidence(descriptor):
    semantic = descriptor.get("semantic") or {}
    input_obj = descriptor.get("input") or {}
    try:
        return float(semantic.get("class_confidence", input_obj.get("confidence", 1.0)))
    except Exception:
        return 1.0

def descriptor_dims(descriptor):
    dims = ((descriptor.get("scale") or {}).get("dims_m") or {})
    try:
        length = float(dims.get("length"))
        width = float(dims.get("width"))
        height = float(dims.get("height"))
        if length > 0 and width > 0 and height > 0:
            return length, width, height
    except Exception:
        pass
    extent = (((descriptor.get("mesh") or {}).get("template_bounds") or {}).get("extent") or [])
    if len(extent) >= 3:
        try:
            return max(float(extent[0]), 0.1), max(float(extent[1]), 0.1), max(float(extent[2]), 0.1)
        except Exception:
            pass
    return 1.5, 1.0, 1.0

def build_shape_packet(descriptor, multiplier):
    length, width, height = descriptor_dims(descriptor)
    parts = copy.deepcopy(descriptor.get("parts") or [])
    for part in parts:
        role = str(part.get("role") or part.get("material_role") or "").lower()
        scale = part.get("scale")
        if isinstance(scale, list) and len(scale) >= 3 and ("body" in role or "vehicle" in role):
            scale[0] = float(scale[0]) * multiplier
            part["scale"] = scale
    return {
        "packet_schema": "SPPA-UPD-0.2",
        "descriptor_id": descriptor.get("descriptor_id", "unknown_descriptor"),
        "action": "shape_param_update",
        "scale": {"dims_m": {"length": length * multiplier, "width": width * multiplier, "height": height}},
        "parts": parts,
    }

def build_pose_packet(descriptor):
    return {
        "packet_schema": "SPPA-UPD-0.2",
        "descriptor_id": descriptor.get("descriptor_id", "unknown_descriptor"),
        "action": "pose_update",
    }

def world_for_index(index, step=0):
    return {
        "north": float((index % 25) * 3.0 + step * 0.05),
        "east": float((index // 25) * 3.0),
        "up": 0.0,
    }

def create_obstacle(descriptor, index, phase, step=0):
    obstacle = {
        "entity_id": f"component_replay_{index:05d}",
        "object_type": descriptor_label(descriptor),
        "confidence": descriptor_confidence(descriptor),
        "world_m": world_for_index(index, step),
        "yaw_deg": float((index * 7 + step) % 360),
    }
    if phase == "create":
        obstacle["sppa_descriptor"] = descriptor
    elif phase == "pose":
        obstacle["sppa_update_packet"] = build_pose_packet(descriptor)
    elif phase == "shape":
        obstacle["sppa_update_packet"] = build_shape_packet(descriptor, 1.05 if index % 2 == 0 else 0.95)
    return obstacle

def actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def ensure_world():
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        if world is not None:
            return world
    except Exception:
        pass
    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
        if world is not None:
            return world
    except Exception:
        pass
    unreal.EditorLoadingAndSavingUtils.load_map("/Game/Ejea")
    return unreal.EditorLevelLibrary.get_editor_world()

def actor_label(actor):
    try:
        return str(actor.get_actor_label())
    except Exception:
        return str(actor.get_name())

def set_actor_label(actor, label):
    try:
        actor.set_actor_label(label)
    except Exception:
        pass

def destroy_actor(actor):
    if actor is None:
        return
    try:
        actor_subsystem().destroy_actor(actor)
    except Exception:
        try:
            actor.destroy_actor()
        except Exception:
            pass

def cleanup_temp_actors():
    try:
        actors = list(actor_subsystem().get_all_level_actors())
    except Exception:
        return
    for actor in actors:
        label = actor_label(actor)
        tags = [str(tag) for tag in getattr(actor, "tags", [])]
        if label.startswith(TEMP_PREFIX) or str(actor.get_name()).startswith(TEMP_PREFIX) or "PORCE_TWIN_MANAGED" in tags:
            destroy_actor(actor)

def get_unreal_type(*names):
    for name in names:
        value = getattr(unreal, name, None)
        if value is not None:
            return value
    return None

def enum_value(enum_cls, needle):
    needle = needle.upper()
    for item in list(enum_cls):
        if needle in str(item).upper():
            return item
    return None

def static_mesh_components(actor):
    try:
        return list(actor.get_components_by_class(unreal.StaticMeshComponent))
    except Exception:
        return []

def managed_actors():
    result = []
    for actor in actor_subsystem().get_all_level_actors():
        tags = [str(tag) for tag in getattr(actor, "tags", [])]
        if "PORCE_TWIN_MANAGED" in tags:
            result.append(actor)
    return result

def component_count(actors):
    return sum(len(static_mesh_components(actor)) for actor in actors)

def actor_signature(actors):
    rows = []
    for actor in actors:
        names = []
        for component in static_mesh_components(actor):
            try:
                names.append(str(component.get_name()))
            except Exception:
                names.append(str(component))
        rows.append([actor_label(actor), sorted(names)])
    return sorted(rows, key=lambda item: item[0])

def signature_hash(signature):
    return stable_hash_text(json.dumps(signature, sort_keys=True))

def create_component(component_cls, backend_enum_cls, proxy_cls, backend_name):
    owner = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.Actor, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
    if owner is None:
        raise RuntimeError("Could not spawn component replay owner")
    set_actor_label(owner, f"{TEMP_PREFIX}owner_{backend_name}")
    add_component = getattr(owner, "add_component_by_class", None)
    if add_component is not None:
        component = add_component(component_cls, False, unreal.Transform(), False)
    else:
        component = unreal.new_object(component_cls, outer=owner)
    if component is None:
        raise RuntimeError("Could not create PorceTelemetryComponent")
    register_component = getattr(component, "register_component", None)
    if register_component is not None:
        register_component()
    component.set_editor_property("bShowSpawnBackendSwitchUI", False)
    component.set_editor_property("DefaultObstacleActorClass", unreal.StaticMeshActor)
    component.set_editor_property("BikerActorClass", unreal.StaticMeshActor)
    component.set_editor_property("CowActorClass", unreal.StaticMeshActor)
    component.set_editor_property("TowerActorClass", unreal.StaticMeshActor)
    component.set_editor_property("SemanticProxyActorClass", proxy_cls)
    backend = enum_value(backend_enum_cls, "PROXY" if backend_name == "semantic_proxy" else "ASSET")
    if backend is None:
        raise RuntimeError("Could not resolve backend enum for %s" % backend_name)
    setter = getattr(component, "set_spawn_backend", None) or getattr(component, "SetSpawnBackend", None)
    if setter is not None:
        setter(backend)
    else:
        component.set_editor_property("SpawnBackend", backend)
    return owner, component

def apply_payload(component, obstacles):
    payload = json.dumps({"obstacles": obstacles}, sort_keys=True)
    method = getattr(component, "apply_obstacle_batch_json", None) or getattr(component, "ApplyObstacleBatchJson", None)
    if method is None:
        raise RuntimeError("PorceTelemetryComponent missing ApplyObstacleBatchJson")
    return bool(method(payload)), len(payload.encode("utf-8"))

def summarize(values):
    if not values:
        return {"n": 0, "p50": None, "p95": None, "p99": None, "max": None}
    values = sorted(float(v) for v in values)
    def pct(p):
        if len(values) == 1:
            return values[0]
        index = min(len(values) - 1, max(0, int(round((p / 100.0) * (len(values) - 1)))))
        return values[index]
    return {"n": len(values), "p50": pct(50), "p95": pct(95), "p99": pct(99), "max": values[-1], "mean": statistics.mean(values)}

def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

def run_git(args):
    try:
        completed = subprocess.run(["git", "-C", str(REPO)] + list(args), check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        return completed.stdout.strip()
    except Exception:
        return ""

def run_benchmark(out_dir, counts, repetitions, updates_per_actor):
    ensure_world()
    cleanup_temp_actors()
    component_cls = get_unreal_type("PorceTelemetryComponent")
    proxy_cls = get_unreal_type("PorceSemanticProxyActor")
    backend_enum_cls = get_unreal_type("PorceTwinSpawnBackend", "EPorceTwinSpawnBackend")
    if component_cls is None or proxy_cls is None or backend_enum_cls is None:
        raise RuntimeError("Required PORCE/SPPA Unreal types are missing")

    descriptors = load_descriptors(max(counts))
    rows = []
    identity_trace_rows = []
    failures = []
    baselines = ["unreal_assets", "semantic_proxy"]
    with (out_dir / "input_descriptors.jsonl").open("w", encoding="utf-8") as handle:
        for descriptor in descriptors:
            handle.write(json.dumps(descriptor, sort_keys=True) + "\n")

    for baseline in baselines:
        for count in counts:
            selected = [descriptors[i % len(descriptors)] for i in range(count)]
            for repetition in range(repetitions):
                cleanup_temp_actors()
                owner = None
                create_ok = pose_ok = shape_ok = False
                try:
                    owner, component = create_component(component_cls, backend_enum_cls, proxy_cls, baseline)
                    create_obstacles = [create_obstacle(descriptor, index, "create", 0) for index, descriptor in enumerate(selected)]
                    start = time.perf_counter()
                    create_ok, create_payload_bytes = apply_payload(component, create_obstacles)
                    create_ms = (time.perf_counter() - start) * 1000.0
                    actors_after_create = managed_actors()
                    create_signature = actor_signature(actors_after_create)
                    components_after_create = component_count(actors_after_create)
                    identity_trace_rows.append({
                        "baseline": baseline,
                        "count": count,
                        "repetition": repetition,
                        "phase": "create",
                        "actor_count": len(actors_after_create),
                        "component_count": components_after_create,
                        "signature_hash": signature_hash(create_signature),
                        "signature": create_signature,
                    })

                    pose_payload_bytes = 0
                    start = time.perf_counter()
                    pose_ok = True
                    for step in range(updates_per_actor):
                        pose_obstacles = [create_obstacle(descriptor, index, "pose", step + 1) for index, descriptor in enumerate(selected)]
                        ok, payload_bytes = apply_payload(component, pose_obstacles)
                        pose_payload_bytes += payload_bytes
                        pose_ok = pose_ok and ok
                    pose_ms = (time.perf_counter() - start) * 1000.0
                    actors_after_pose = managed_actors()
                    pose_signature = actor_signature(actors_after_pose)
                    components_after_pose = component_count(actors_after_pose)
                    identity_trace_rows.append({
                        "baseline": baseline,
                        "count": count,
                        "repetition": repetition,
                        "phase": "pose",
                        "actor_count": len(actors_after_pose),
                        "component_count": components_after_pose,
                        "signature_hash": signature_hash(pose_signature),
                        "signature": pose_signature,
                    })

                    shape_obstacles = [create_obstacle(descriptor, index, "shape", updates_per_actor + 1) for index, descriptor in enumerate(selected)]
                    start = time.perf_counter()
                    shape_ok, shape_payload_bytes = apply_payload(component, shape_obstacles)
                    shape_ms = (time.perf_counter() - start) * 1000.0
                    actors_after_shape = managed_actors()
                    shape_signature = actor_signature(actors_after_shape)
                    components_after_shape = component_count(actors_after_shape)
                    identity_trace_rows.append({
                        "baseline": baseline,
                        "count": count,
                        "repetition": repetition,
                        "phase": "shape",
                        "actor_count": len(actors_after_shape),
                        "component_count": components_after_shape,
                        "signature_hash": signature_hash(shape_signature),
                        "signature": shape_signature,
                    })

                    row = {
                        "baseline": baseline,
                        "count": count,
                        "repetition": repetition,
                        "updates_per_actor": updates_per_actor,
                        "create_total_ms": create_ms,
                        "create_per_actor_ms": create_ms / max(count, 1),
                        "pose_update_total_ms": pose_ms,
                        "pose_update_per_actor_update_ms": pose_ms / max(count * updates_per_actor, 1),
                        "shape_update_total_ms": shape_ms,
                        "shape_update_per_actor_ms": shape_ms / max(count, 1),
                        "actors_after_create": len(actors_after_create),
                        "actors_after_pose": len(actors_after_pose),
                        "actors_after_shape": len(actors_after_shape),
                        "components_after_create": components_after_create,
                        "components_after_pose": components_after_pose,
                        "components_after_shape": components_after_shape,
                        "component_names_reused_during_pose": int(pose_signature == create_signature),
                        "component_names_reused_during_shape": int(shape_signature == pose_signature),
                        "create_payload_bytes": create_payload_bytes,
                        "pose_payload_bytes_total": pose_payload_bytes,
                        "shape_payload_bytes": shape_payload_bytes,
                        "create_ok": int(create_ok),
                        "pose_ok": int(pose_ok),
                        "shape_ok": int(shape_ok),
                        "mode": "Component payload replay via ApplyObstacleBatchJson",
                    }
                    rows.append(row)
                    if len(actors_after_create) != count or len(actors_after_shape) != count:
                        failures.append("%s count=%d rep=%d actor count mismatch create=%d shape=%d" % (baseline, count, repetition, len(actors_after_create), len(actors_after_shape)))
                    if not (create_ok and pose_ok and shape_ok):
                        failures.append("%s count=%d rep=%d returned false from payload application" % (baseline, count, repetition))
                except Exception as exc:
                    failures.append("%s count=%d rep=%d failed: %s" % (baseline, count, repetition, exc))
                finally:
                    if owner is not None:
                        destroy_actor(owner)
                    cleanup_temp_actors()

    summary = {}
    summary_by_count = {}
    for baseline in baselines:
        summary[baseline] = {}
        for key in ["create_per_actor_ms", "pose_update_per_actor_update_ms", "shape_update_per_actor_ms"]:
            summary[baseline][key] = summarize([row[key] for row in rows if row["baseline"] == baseline])
        summary_by_count[baseline] = {}
        for count in counts:
            summary_by_count[baseline][str(count)] = {}
            for key in ["create_per_actor_ms", "pose_update_per_actor_update_ms", "shape_update_per_actor_ms"]:
                summary_by_count[baseline][str(count)][key] = summarize([row[key] for row in rows if row["baseline"] == baseline and row["count"] == count])

    write_csv(out_dir / "component_replay_rows.csv", rows, list(rows[0].keys()) if rows else [])
    with (out_dir / "component_identity_trace.jsonl").open("w", encoding="utf-8") as handle:
        for row in identity_trace_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "component_replay_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "component_replay_summary_by_count.json").write_text(json.dumps(summary_by_count, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "created_utc": utc_now(),
        "mode": "Component payload replay via ApplyObstacleBatchJson",
        "claim_scope": "Preliminary component lifecycle replay using the /api/ui/data payload shape but bypassing HTTP; not packaged build, not render-thread, not VR frame-time.",
        "repo": str(REPO),
        "git_head": run_git(["rev-parse", "HEAD"]),
        "git_dirty": bool(run_git(["status", "--short"])),
        "engine_version": str(unreal.SystemLibrary.get_engine_version()),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "counts": counts,
        "repetitions": repetitions,
        "updates_per_actor": updates_per_actor,
        "baselines": baselines,
        "descriptor_count_loaded": len(descriptors),
        "descriptor_input_hash": stable_hash_text("\n".join(json.dumps(item, sort_keys=True) for item in descriptors)),
        "failures": failures,
        "artifacts": [
            "run_manifest.json",
            "input_descriptors.jsonl",
            "component_replay_rows.csv",
            "component_identity_trace.jsonl",
            "component_replay_summary.json",
            "component_replay_summary_by_count.json",
        ],
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest

def main():
    out_env = os.environ.get("PORCE_SPPA_COMPONENT_REPLAY_OUT_DIR", "").strip()
    if out_env:
        out_dir = Path(out_env)
    else:
        out_dir = REPO / "experiments" / "sppa_unreal_component_replay" / f"{utc_now()}_component_payload_replay"
    if out_dir.exists():
        existing = [item.name for item in out_dir.iterdir()]
        allowed_preexisting = {"component_replay.log"}
        if any(name not in allowed_preexisting for name in existing):
            raise RuntimeError(f"Output directory already exists and is non-empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = parse_int_list(os.environ.get("PORCE_SPPA_COMPONENT_REPLAY_COUNTS"), [10, 50, 100])
    repetitions = max(1, int(os.environ.get("PORCE_SPPA_COMPONENT_REPLAY_REPETITIONS", "3")))
    updates_per_actor = max(1, int(os.environ.get("PORCE_SPPA_COMPONENT_REPLAY_UPDATES", "5")))
    manifest = run_benchmark(out_dir, counts, repetitions, updates_per_actor)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    if manifest["failures"]:
        raise RuntimeError("SPPA component replay benchmark completed with failures: %s" % manifest["failures"][:5])
    print("SPPA_COMPONENT_REPLAY_BENCHMARK_OK")

main()
