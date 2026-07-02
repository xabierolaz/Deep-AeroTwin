import csv
import copy
import gc
import hashlib
import http.server
import json
import os
import platform
import random
import socketserver
import statistics
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import unreal

REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
TEMP_PREFIX = "DAT_SPPA_HttpReplay_"


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


def utc_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def stable_payload(payload_obj):
    return json.dumps(payload_obj, sort_keys=True)


def payload_hash(payload_obj):
    return stable_hash_text(stable_payload(payload_obj))


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
        "descriptor_id": "sppa-inline-http-replay-car",
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
    return 1.5, 1.0, 1.0


def build_shape_packet(descriptor, multiplier):
    length, width, height = descriptor_dims(descriptor)
    source_scale = descriptor.get("scale") or {}
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
        "resolver": descriptor.get("resolver"),
        "semantic": descriptor.get("semantic"),
        "track": descriptor.get("track"),
        "action": "shape_param_update",
        "reason": "shape_param_update_from_replay_fixture",
        "uncertainty": descriptor.get("uncertainty"),
        "scale": {
            "dims_m": {"length": length * multiplier, "width": width * multiplier, "height": height},
            "scale_source": source_scale.get("scale_source", "template_prior"),
            "scale_uncertainty": source_scale.get("scale_uncertainty"),
        },
        "parts": parts,
    }


def build_pose_packet(descriptor):
    return {
        "packet_schema": "SPPA-UPD-0.2",
        "descriptor_id": descriptor.get("descriptor_id", "unknown_descriptor"),
        "resolver": descriptor.get("resolver"),
        "semantic": descriptor.get("semantic"),
        "track": descriptor.get("track"),
        "action": "pose_update",
        "reason": "pose_update_from_replay_fixture",
        "uncertainty": descriptor.get("uncertainty"),
        "pose": descriptor.get("pose"),
        "scale": descriptor.get("scale"),
    }


def world_for_index(index, step=0):
    return {
        "north": float((index % 25) * 3.0 + step * 0.05),
        "east": float((index // 25) * 3.0),
        "up": 0.0,
    }


def create_obstacle(descriptor, index, phase, step=0):
    obstacle = {
        "entity_id": f"http_replay_{index:05d}",
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


def nested_get(obj, keys, default=None):
    current = obj
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def boolish(value):
    return int(bool(value))


def normalize_match_type(value):
    text = str(value or "").strip()
    if text == "exact_class":
        return "exact"
    if text == "keyword_archetype":
        return "keyword"
    if text.startswith("fallback"):
        return "fallback_unknown"
    return text


def descriptor_action_payload(obstacle, fallback_action):
    descriptor = obstacle.get("sppa_descriptor") or {}
    packet = obstacle.get("sppa_update_packet") or {}
    payload = descriptor if descriptor else packet
    runtime_policy = descriptor.get("runtime_policy") or {}
    semantic = payload.get("semantic") or descriptor.get("semantic") or {}
    resolver = descriptor.get("resolver") or {}
    uncertainty = payload.get("uncertainty") or descriptor.get("uncertainty") or {}
    pose = payload.get("pose") or descriptor.get("pose") or {}
    scale = payload.get("scale") or descriptor.get("scale") or {}
    action = payload.get("action") or runtime_policy.get("action") or fallback_action
    reason = payload.get("reason") or runtime_policy.get("action_reason") or ""
    return {
        "descriptor_id": payload.get("descriptor_id") or descriptor.get("descriptor_id") or "",
        "previous_descriptor_id": nested_get(descriptor, ["track", "previous_descriptor_id"], ""),
        "track_id": nested_get(descriptor, ["track", "track_id"], "") or obstacle.get("entity_id", ""),
        "action": str(action or fallback_action),
        "reason": str(reason or ""),
        "confidence": semantic.get("class_confidence", obstacle.get("confidence", "")),
        "unknown_label": boolish(semantic.get("unknown_label") or uncertainty.get("fallback_unknown")),
        "yaw_ambiguous": boolish(uncertainty.get("yaw_ambiguous") or pose.get("yaw_ambiguous")),
        "shape_low_confidence": boolish(uncertainty.get("shape_low_confidence")),
        "match_type": normalize_match_type(resolver.get("match_type") or semantic.get("match_type") or semantic.get("resolution_status") or ""),
        "archetype": resolver.get("archetype_id") or semantic.get("archetype") or "",
        "resolver_source": resolver.get("resolver_source") or "",
        "scale_source": scale.get("scale_source") or uncertainty.get("shape_source") or "",
        "material_source": uncertainty.get("material_source") or ("fallback_unknown" if uncertainty.get("fallback_unknown") else "semantic_prior"),
        "payload_kind": "descriptor" if descriptor else ("update_packet" if packet else "class_only"),
    }


def trace_update_rows(baseline, condition, action_name, pose_step, payload_hash_value, obstacles, before_state, after_state, elapsed_ms, start_utc, end_utc):
    rows = []
    for obstacle in obstacles:
        entity_id = str(obstacle.get("entity_id") or obstacle.get("object_id") or "")
        before = before_state.get(entity_id, {})
        after = after_state.get(entity_id, {})
        before_count = int(before.get("component_count", 0) or 0)
        after_count = int(after.get("component_count", 0) or 0)
        payload_meta = descriptor_action_payload(obstacle, action_name)
        rows.append({
            "seed": condition["seed"],
            "condition_id": condition["condition_id"],
            "group_order": condition["group_order"],
            "condition_order": condition["condition_order"],
            "baseline_order_index": condition["baseline_order_index"],
            "baseline": baseline,
            "count": condition["count"],
            "repetition": condition["repetition"],
            "phase": action_name,
            "pose_step": "" if pose_step is None else pose_step,
            "entity_id": entity_id,
            "track_id": payload_meta["track_id"],
            "descriptor_id": payload_meta["descriptor_id"],
            "previous_descriptor_id": payload_meta["previous_descriptor_id"],
            "action": payload_meta["action"],
            "reason": payload_meta["reason"],
            "confidence": payload_meta["confidence"],
            "unknown_label": payload_meta["unknown_label"],
            "yaw_ambiguous": payload_meta["yaw_ambiguous"],
            "shape_low_confidence": payload_meta["shape_low_confidence"],
            "match_type": payload_meta["match_type"],
            "archetype": payload_meta["archetype"],
            "resolver_source": payload_meta["resolver_source"],
            "scale_source": payload_meta["scale_source"],
            "material_source": payload_meta["material_source"],
            "payload_kind": payload_meta["payload_kind"],
            "components_before": before_count,
            "components_after": after_count,
            "components_created": max(0, after_count - before_count),
            "components_destroyed": max(0, before_count - after_count),
            "components_reused": min(before_count, after_count),
            "scale_before": json.dumps(before.get("scale", [1.0, 1.0, 1.0]), separators=(",", ":")),
            "scale_after": json.dumps(after.get("scale", [1.0, 1.0, 1.0]), separators=(",", ":")),
            "actor_descriptor_id_after": after.get("descriptor_id", ""),
            "actor_descriptor_action_after": after.get("descriptor_action", ""),
            "actor_resolver_match_after": after.get("resolver_match", ""),
            "actor_archetype_after": after.get("archetype", ""),
            "actor_scale_source_after": after.get("scale_source", ""),
            "actor_material_source_after": after.get("material_source", ""),
            "actor_yaw_ambiguous_tag_after": after.get("yaw_ambiguous_tag", 0),
            "actor_shape_low_confidence_tag_after": after.get("shape_low_confidence_tag", 0),
            "actor_fallback_unknown_tag_after": after.get("fallback_unknown_tag", 0),
            "start_utc": start_utc,
            "end_utc": end_utc,
            "elapsed_ms": elapsed_ms,
            "payload_hash": payload_hash_value,
        })
    return rows


class ReplayHttpState:
    def __init__(self):
        self.lock = threading.Lock()
        self.payload = b'{"obstacles":[]}'
        self.request_count = 0
        self.last_path = ""

    def set_payload(self, payload_obj):
        payload = stable_payload(payload_obj).encode("utf-8")
        with self.lock:
            self.payload = payload

    def snapshot(self):
        with self.lock:
            return self.payload, self.request_count, self.last_path

    def mark_request(self, path):
        with self.lock:
            self.request_count += 1
            self.last_path = str(path)
            return self.payload


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_http_server(state):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            payload = state.mark_request(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, name="sppa-http-replay", daemon=True)
    thread.start()
    return server, thread


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
        tags = [str(tag) for tag in getattr(actor, "tags", [])]
        if actor_label(actor).startswith(TEMP_PREFIX) or "PORCE_TWIN_MANAGED" in tags:
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


def actor_tags(actor):
    return [str(tag) for tag in getattr(actor, "tags", [])]


def component_tags(component):
    return [str(tag) for tag in getattr(component, "component_tags", [])]


def parse_tag_value(tags, prefix):
    for tag in tags:
        if tag.startswith(prefix):
            return tag[len(prefix):]
    return ""


def parse_descriptor_id_tag(tags):
    for tag in tags:
        if tag.startswith("PORCE_DESCRIPTOR_") and not tag.startswith("PORCE_DESCRIPTOR_ACTION_"):
            return tag[len("PORCE_DESCRIPTOR_"):]
    return ""


def actor_relative_scale(actor):
    try:
        root = actor.get_root_component()
        scale = root.get_relative_scale3d()
        return [float(scale.x), float(scale.y), float(scale.z)]
    except Exception:
        pass
    try:
        scale = actor.get_actor_scale3d()
        return [float(scale.x), float(scale.y), float(scale.z)]
    except Exception:
        return [1.0, 1.0, 1.0]


def managed_actor_state_by_entity():
    states = {}
    for actor in managed_actors():
        tags = actor_tags(actor)
        entity_id = parse_tag_value(tags, "PORCE_ENTITY_")
        if not entity_id:
            continue
        components = static_mesh_components(actor)
        all_component_tags = sorted({tag for component in components for tag in component_tags(component)})
        states[entity_id] = {
            "actor_label": actor_label(actor),
            "component_count": len(components),
            "scale": actor_relative_scale(actor),
            "descriptor_id": parse_descriptor_id_tag(tags),
            "descriptor_action": parse_tag_value(tags, "PORCE_DESCRIPTOR_ACTION_"),
            "class_tag": parse_tag_value(tags, "PORCE_CLASS_"),
            "archetype": parse_tag_value(tags, "PORCE_ARCHETYPE_"),
            "resolver_match": parse_tag_value(tags, "PORCE_RESOLVER_MATCH_"),
            "resolver_source": parse_tag_value(tags, "PORCE_RESOLVER_SOURCE_"),
            "scale_source": parse_tag_value(tags, "PORCE_SCALE_SOURCE_"),
            "material_source": parse_tag_value(tags, "PORCE_MATERIAL_SOURCE_"),
            "yaw_ambiguous_tag": int("PORCE_UNCERTAINTY_YAW_AMBIGUOUS" in tags),
            "shape_low_confidence_tag": int("PORCE_UNCERTAINTY_SHAPE_LOW_CONFIDENCE" in tags),
            "fallback_unknown_tag": int("PORCE_UNCERTAINTY_FALLBACK_UNKNOWN" in tags),
            "material_role_tags": [tag for tag in all_component_tags if tag.startswith("SPPA_MATERIAL_ROLE_")],
            "evidence_source_tags": [tag for tag in all_component_tags if tag.startswith("SPPA_EVIDENCE_SOURCE_")],
            "uncertainty_style_tags": [tag for tag in all_component_tags if tag.startswith("SPPA_UNCERTAINTY_STYLE_")],
        }
    return states


def signature_hash(signature):
    return stable_hash_text(json.dumps(signature, sort_keys=True))


def create_component(component_cls, backend_enum_cls, proxy_cls, backend_name, endpoint_url, timeout_s):
    owner = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.Actor, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
    if owner is None:
        raise RuntimeError("Could not spawn HTTP replay owner")
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
    component.set_editor_property("EndpointUrl", endpoint_url)
    component.set_editor_property("RequestTimeoutS", float(timeout_s))
    component.set_editor_property("PollRateHz", 0.0)
    component.set_editor_property("DefaultObstacleActorClass", unreal.StaticMeshActor)
    component.set_editor_property("BikerActorClass", unreal.StaticMeshActor)
    component.set_editor_property("CowActorClass", unreal.StaticMeshActor)
    component.set_editor_property("TowerActorClass", unreal.StaticMeshActor)
    component.set_editor_property("SemanticProxyActorClass", proxy_cls)
    try:
        component.set_editor_property("bBenchmarkDisableActorSpawning", backend_name == "no_render")
    except Exception:
        if backend_name == "no_render":
            raise
    backend = enum_value(backend_enum_cls, "PROXY" if backend_name == "semantic_proxy" else "ASSET")
    if backend is None:
        raise RuntimeError("Could not resolve backend enum for %s" % backend_name)
    setter = getattr(component, "set_spawn_backend", None) or getattr(component, "SetSpawnBackend", None)
    if setter is not None:
        setter(backend)
    else:
        component.set_editor_property("SpawnBackend", backend)
    return owner, component


def poll_payload(component, state, obstacles, timeout_s):
    payload_obj = {"obstacles": obstacles}
    state.set_payload(payload_obj)
    method = getattr(component, "poll_now_blocking_for_test", None) or getattr(component, "PollNowBlockingForTest", None)
    if method is None:
        raise RuntimeError("PorceTelemetryComponent missing PollNowBlockingForTest")
    payload_bytes = len(stable_payload(payload_obj).encode("utf-8"))
    ok = bool(method(float(timeout_s)))
    return ok, payload_bytes, payload_hash(payload_obj)


def collect_garbage_for_benchmark():
    gc.collect()
    unreal_collected = False
    try:
        unreal.SystemLibrary.collect_garbage()
        unreal_collected = True
    except Exception:
        unreal_collected = False
    return unreal_collected


def build_condition_schedule(counts, repetitions, baselines, seed):
    rng = random.Random(int(seed))
    count_rep_pairs = [(count, repetition) for count in counts for repetition in range(repetitions)]
    schedule = []
    condition_order = 0
    for group_order, (count, repetition) in enumerate(count_rep_pairs):
        count_index = counts.index(count)
        rotation = (count_index + repetition + rng.randrange(len(baselines))) % len(baselines)
        ordered_baselines = list(baselines[rotation:]) + list(baselines[:rotation])
        if rng.randrange(2) == 1:
            ordered_baselines = list(reversed(ordered_baselines))
        for baseline_order_index, baseline in enumerate(ordered_baselines):
            schedule.append({
                "seed": int(seed),
                "condition_id": f"seed{int(seed)}_count{count}_rep{repetition}_{baseline}",
                "group_order": group_order,
                "condition_order": condition_order,
                "baseline_order_index": baseline_order_index,
                "count": count,
                "repetition": repetition,
                "baseline": baseline,
                "schedule_design": "seeded count/repetition groups with rotated/reversed baseline order",
            })
            condition_order += 1
    return schedule


def schedule_action_rows(condition_schedule, descriptors, updates_per_actor):
    rows = []
    scheduled_order = 0
    for condition in condition_schedule:
        count = int(condition["count"])
        selected = [descriptors[i % len(descriptors)] for i in range(count)]
        action_specs = [("create", None, [create_obstacle(descriptor, index, "create", 0) for index, descriptor in enumerate(selected)])]
        for step in range(updates_per_actor):
            action_specs.append(("pose_poll", step, [create_obstacle(descriptor, index, "pose", step + 1) for index, descriptor in enumerate(selected)]))
        action_specs.append(("shape", None, [create_obstacle(descriptor, index, "shape", updates_per_actor + 1) for index, descriptor in enumerate(selected)]))
        for action, pose_step, obstacles in action_specs:
            payload_obj = {"obstacles": obstacles}
            rows.append({
                "seed": condition["seed"],
                "condition_id": condition["condition_id"],
                "group_order": condition["group_order"],
                "condition_order": condition["condition_order"],
                "baseline_order_index": condition["baseline_order_index"],
                "scheduled_order": scheduled_order,
                "count": condition["count"],
                "repetition": condition["repetition"],
                "baseline": condition["baseline"],
                "action": action,
                "pose_step": pose_step,
                "cold_or_warm": "unseparated",
                "gc_collect_before": int(action == "create"),
                "payload_hash": payload_hash(payload_obj),
                "payload_bytes": len(stable_payload(payload_obj).encode("utf-8")),
            })
            scheduled_order += 1
    return rows


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


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

def bootstrap_mean_ci(values, seed_key, iterations=1000):
    values = [float(value) for value in values]
    if len(values) < 2:
        value = values[0] if values else None
        return value, value
    seed = int(hashlib.sha256(str(seed_key).encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)
    means = []
    for _ in range(iterations):
        sample = [values[rng.randrange(len(values))] for _ in values]
        means.append(statistics.mean(sample))
    means.sort()
    low_index = max(0, int(0.025 * (len(means) - 1)))
    high_index = min(len(means) - 1, int(0.975 * (len(means) - 1)))
    return means[low_index], means[high_index]


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

def build_batch_summary_rows(rows, pose_poll_rows, baselines, counts):
    summary_rows = []
    for baseline in baselines:
        for count in counts:
            matching_rows = [row for row in rows if row["baseline"] == baseline and row["count"] == count]
            matching_pose_polls = [row for row in pose_poll_rows if row["baseline"] == baseline and row["count"] == count]
            actions = [
                (
                    "create",
                    [row["create_total_ms"] for row in matching_rows],
                    [row["components_after_create"] for row in matching_rows],
                    [row["create_payload_bytes"] for row in matching_rows],
                    len(matching_rows),
                ),
                (
                    "pose_poll",
                    [row["pose_poll_total_ms"] for row in matching_pose_polls],
                    [row["components_after_pose"] for row in matching_pose_polls],
                    [row["payload_bytes"] for row in matching_pose_polls],
                    len(matching_pose_polls),
                ),
                (
                    "shape",
                    [row["shape_update_total_ms"] for row in matching_rows],
                    [row["components_after_shape"] for row in matching_rows],
                    [row["shape_payload_bytes"] for row in matching_rows],
                    len(matching_rows),
                ),
            ]
            for action, totals, components, payload_bytes, http_requests in actions:
                total_summary = summarize(totals)
                per_actor_summary = summarize([value / max(count, 1) for value in totals])
                summary_rows.append({
                    "baseline": baseline,
                    "count": count,
                    "action": action,
                    "n": total_summary["n"],
                    "batch_total_ms_mean": total_summary.get("mean"),
                    "batch_total_ms_p50": total_summary["p50"],
                    "batch_total_ms_p95": total_summary["p95"],
                    "batch_total_ms_max": total_summary["max"],
                    "per_actor_ms_p50": per_actor_summary["p50"],
                    "per_actor_ms_p95": per_actor_summary["p95"],
                    "http_requests": http_requests,
                    "components_after_action": max(components) if components else 0,
                    "payload_bytes_mean": statistics.mean(payload_bytes) if payload_bytes else 0.0,
                })
    return summary_rows

def build_incremental_delta_rows(rows, pose_poll_rows, counts):
    comparisons = [
        ("unreal_assets_minus_no_render", "unreal_assets", "no_render"),
        ("semantic_proxy_minus_no_render", "semantic_proxy", "no_render"),
        ("semantic_proxy_minus_unreal_assets", "semantic_proxy", "unreal_assets"),
    ]
    action_configs = [
        ("create", rows, ("count", "repetition"), "create_total_ms", "components_after_create", "create_payload_bytes"),
        ("pose_poll", pose_poll_rows, ("count", "repetition", "pose_step"), "pose_poll_total_ms", "components_after_pose", "payload_bytes"),
        ("shape", rows, ("count", "repetition"), "shape_update_total_ms", "components_after_shape", "shape_payload_bytes"),
    ]
    delta_rows = []
    for comparison, target_baseline, reference_baseline in comparisons:
        for count in counts:
            for action, source_rows, key_fields, total_field, components_field, payload_field in action_configs:
                target_rows = {}
                reference_rows = {}
                for row in source_rows:
                    if row["count"] != count:
                        continue
                    key = tuple(row[field] for field in key_fields)
                    if row["baseline"] == target_baseline:
                        target_rows[key] = row
                    elif row["baseline"] == reference_baseline:
                        reference_rows[key] = row
                deltas = []
                per_actor_deltas = []
                component_deltas = []
                payload_deltas = []
                for key in sorted(set(target_rows.keys()) & set(reference_rows.keys())):
                    target = target_rows[key]
                    reference = reference_rows[key]
                    delta = float(target[total_field]) - float(reference[total_field])
                    deltas.append(delta)
                    per_actor_deltas.append(delta / max(count, 1))
                    component_deltas.append(int(target[components_field]) - int(reference[components_field]))
                    payload_deltas.append(float(target[payload_field]) - float(reference[payload_field]))
                delta_summary = summarize(deltas)
                per_actor_summary = summarize(per_actor_deltas)
                ci_low, ci_high = bootstrap_mean_ci(deltas, f"{comparison}:{count}:{action}")
                delta_rows.append({
                    "comparison": comparison,
                    "target_baseline": target_baseline,
                    "reference_baseline": reference_baseline,
                    "count": count,
                    "action": action,
                    "n": delta_summary["n"],
                    "delta_batch_ms_mean": delta_summary.get("mean"),
                    "delta_batch_ms_p50": delta_summary["p50"],
                    "delta_batch_ms_p95": delta_summary["p95"],
                    "delta_batch_ms_max": delta_summary["max"],
                    "delta_batch_ms_mean_ci95_low": ci_low,
                    "delta_batch_ms_mean_ci95_high": ci_high,
                    "delta_per_actor_ms_p50": per_actor_summary["p50"],
                    "delta_per_actor_ms_p95": per_actor_summary["p95"],
                    "components_delta": max(component_deltas) if component_deltas else 0,
                    "payload_bytes_delta_mean": statistics.mean(payload_deltas) if payload_deltas else 0.0,
                })
    return delta_rows


def build_runtime_update_summary(trace_rows):
    summary = {}
    for row in trace_rows:
        baseline = row["baseline"]
        action = row["action"]
        bucket = summary.setdefault(baseline, {}).setdefault(action, {
            "rows": 0,
            "unknown_label_rows": 0,
            "yaw_ambiguous_rows": 0,
            "shape_low_confidence_rows": 0,
            "components_created": 0,
            "components_destroyed": 0,
            "components_reused": 0,
            "fallback_actor_tag_rows": 0,
            "yaw_ambiguous_actor_tag_rows": 0,
            "shape_low_confidence_actor_tag_rows": 0,
            "match_type_counts": {},
            "scale_source_counts": {},
            "material_source_counts": {},
        })
        bucket["rows"] += 1
        bucket["unknown_label_rows"] += int(row.get("unknown_label", 0) or 0)
        bucket["yaw_ambiguous_rows"] += int(row.get("yaw_ambiguous", 0) or 0)
        bucket["shape_low_confidence_rows"] += int(row.get("shape_low_confidence", 0) or 0)
        bucket["components_created"] += int(row.get("components_created", 0) or 0)
        bucket["components_destroyed"] += int(row.get("components_destroyed", 0) or 0)
        bucket["components_reused"] += int(row.get("components_reused", 0) or 0)
        bucket["fallback_actor_tag_rows"] += int(row.get("actor_fallback_unknown_tag_after", 0) or 0)
        bucket["yaw_ambiguous_actor_tag_rows"] += int(row.get("actor_yaw_ambiguous_tag_after", 0) or 0)
        bucket["shape_low_confidence_actor_tag_rows"] += int(row.get("actor_shape_low_confidence_tag_after", 0) or 0)
        for source_field, target_field in [
            ("match_type", "match_type_counts"),
            ("scale_source", "scale_source_counts"),
            ("material_source", "material_source_counts"),
        ]:
            key = str(row.get(source_field) or "unspecified")
            bucket[target_field][key] = bucket[target_field].get(key, 0) + 1
    return summary


def run_git(args):
    try:
        completed = subprocess.run(["git", "-C", str(REPO)] + list(args), check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        return completed.stdout.strip()
    except Exception:
        return ""


def run_benchmark(out_dir, counts, repetitions, updates_per_actor, timeout_s, schedule_seed):
    ensure_world()
    cleanup_temp_actors()
    component_cls = get_unreal_type("PorceTelemetryComponent")
    proxy_cls = get_unreal_type("PorceSemanticProxyActor")
    backend_enum_cls = get_unreal_type("PorceTwinSpawnBackend", "EPorceTwinSpawnBackend")
    if component_cls is None or proxy_cls is None or backend_enum_cls is None:
        raise RuntimeError("Required PORCE/SPPA Unreal types are missing")

    descriptors = load_descriptors(max(counts))
    with (out_dir / "input_descriptors.jsonl").open("w", encoding="utf-8") as handle:
        for descriptor in descriptors:
            handle.write(json.dumps(descriptor, sort_keys=True) + "\n")

    state = ReplayHttpState()
    server, thread = start_http_server(state)
    endpoint_url = "http://127.0.0.1:%d/api/ui/data" % int(server.server_address[1])
    rows = []
    pose_poll_rows = []
    identity_trace_rows = []
    runtime_update_trace_rows = []
    failures = []
    baselines = ["no_render", "unreal_assets", "semantic_proxy"]
    condition_schedule = build_condition_schedule(counts, repetitions, baselines, schedule_seed)
    condition_groups = {}
    for condition in condition_schedule:
        condition_groups.setdefault((condition["count"], condition["repetition"]), []).append(condition)
    action_schedule_rows = schedule_action_rows(condition_schedule, descriptors, updates_per_actor)
    action_schedule_lookup = {
        (row["condition_id"], row["action"], row["pose_step"]): row
        for row in action_schedule_rows
    }
    order_trace_rows = []
    order_trace_fields = [
        "seed",
        "condition_id",
        "group_order",
        "condition_order",
        "baseline_order_index",
        "scheduled_order",
        "count",
        "baseline",
        "action",
        "repetition",
        "pose_step",
        "start_utc",
        "end_utc",
        "cold_or_warm",
        "gc_collect_before",
        "unreal_gc_collect_before",
        "payload_hash",
        "payload_bytes",
        "result_row_id",
        "ok",
        "elapsed_ms",
        "http_requests_delta",
    ]
    write_jsonl(out_dir / "http_poll_replay_schedule.jsonl", action_schedule_rows)

    def append_order_trace(meta, start_utc, end_utc, result_row_id, ok, elapsed_ms, request_delta, unreal_gc_collected=0):
        order_trace_rows.append({
            "seed": meta["seed"],
            "condition_id": meta["condition_id"],
            "group_order": meta["group_order"],
            "condition_order": meta["condition_order"],
            "baseline_order_index": meta["baseline_order_index"],
            "scheduled_order": meta["scheduled_order"],
            "count": meta["count"],
            "baseline": meta["baseline"],
            "action": meta["action"],
            "repetition": meta["repetition"],
            "pose_step": "" if meta["pose_step"] is None else meta["pose_step"],
            "start_utc": start_utc,
            "end_utc": end_utc,
            "cold_or_warm": meta["cold_or_warm"],
            "gc_collect_before": meta["gc_collect_before"],
            "unreal_gc_collect_before": int(unreal_gc_collected),
            "payload_hash": meta["payload_hash"],
            "payload_bytes": meta["payload_bytes"],
            "result_row_id": result_row_id,
            "ok": int(ok),
            "elapsed_ms": elapsed_ms,
            "http_requests_delta": request_delta,
        })
    try:
        for count in counts:
            selected = [descriptors[i % len(descriptors)] for i in range(count)]
            for repetition in range(repetitions):
                for condition in condition_groups[(count, repetition)]:
                    baseline = condition["baseline"]
                    cleanup_temp_actors()
                    owner = None
                    create_ok = pose_ok = shape_ok = False
                    try:
                        row_id = f"{condition['condition_id']}:summary"
                        unreal_gc_collected = collect_garbage_for_benchmark()
                        owner, component = create_component(component_cls, backend_enum_cls, proxy_cls, baseline, endpoint_url, timeout_s)
                        create_meta = action_schedule_lookup[(condition["condition_id"], "create", None)]
                        create_obstacles = [create_obstacle(descriptor, index, "create", 0) for index, descriptor in enumerate(selected)]
                        create_before_state = managed_actor_state_by_entity()
                        start_requests = state.snapshot()[1]
                        create_start_utc = utc_iso()
                        start = time.perf_counter()
                        create_ok, create_payload_bytes, create_payload_hash = poll_payload(component, state, create_obstacles, timeout_s)
                        create_ms = (time.perf_counter() - start) * 1000.0
                        create_end_utc = utc_iso()
                        create_end_requests = state.snapshot()[1]
                        append_order_trace(create_meta, create_start_utc, create_end_utc, row_id, create_ok, create_ms, create_end_requests - start_requests, unreal_gc_collected)
                        actors_after_create = managed_actors()
                        create_signature = actor_signature(actors_after_create)
                        components_after_create = component_count(actors_after_create)
                        create_after_state = managed_actor_state_by_entity()
                        runtime_update_trace_rows.extend(trace_update_rows(
                            baseline,
                            condition,
                            "create",
                            None,
                            create_payload_hash,
                            create_obstacles,
                            create_before_state,
                            create_after_state,
                            create_ms,
                            create_start_utc,
                            create_end_utc,
                        ))
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
                        pose_start = time.perf_counter()
                        pose_poll_ms_values = []
                        pose_payload_hashes = []
                        pose_ok = True
                        for step in range(updates_per_actor):
                            pose_meta = action_schedule_lookup[(condition["condition_id"], "pose_poll", step)]
                            pose_obstacles = [create_obstacle(descriptor, index, "pose", step + 1) for index, descriptor in enumerate(selected)]
                            pose_before_state = managed_actor_state_by_entity()
                            pose_start_requests = state.snapshot()[1]
                            pose_start_utc = utc_iso()
                            pose_poll_start = time.perf_counter()
                            ok, payload_bytes, pose_hash = poll_payload(component, state, pose_obstacles, timeout_s)
                            pose_poll_ms = (time.perf_counter() - pose_poll_start) * 1000.0
                            pose_end_utc = utc_iso()
                            pose_end_requests = state.snapshot()[1]
                            append_order_trace(pose_meta, pose_start_utc, pose_end_utc, f"{condition['condition_id']}:pose:{step}", ok, pose_poll_ms, pose_end_requests - pose_start_requests, 0)
                            pose_poll_ms_values.append(pose_poll_ms)
                            pose_payload_bytes += payload_bytes
                            pose_payload_hashes.append(pose_hash)
                            pose_ok = pose_ok and ok
                            pose_after_state = managed_actor_state_by_entity()
                            runtime_update_trace_rows.extend(trace_update_rows(
                                baseline,
                                condition,
                                "pose_update",
                                step,
                                pose_hash,
                                pose_obstacles,
                                pose_before_state,
                                pose_after_state,
                                pose_poll_ms,
                                pose_start_utc,
                                pose_end_utc,
                            ))
                            pose_poll_rows.append({
                                "row_id": f"{condition['condition_id']}:pose:{step}",
                                "seed": int(schedule_seed),
                                "condition_id": condition["condition_id"],
                                "group_order": condition["group_order"],
                                "condition_order": condition["condition_order"],
                                "baseline_order_index": condition["baseline_order_index"],
                                "scheduled_order": pose_meta["scheduled_order"],
                                "baseline": baseline,
                                "count": count,
                                "repetition": repetition,
                                "pose_step": step,
                                "updates_per_actor": updates_per_actor,
                                "pose_poll_total_ms": pose_poll_ms,
                                "pose_poll_per_actor_ms": pose_poll_ms / max(count, 1),
                                "payload_bytes": payload_bytes,
                                "payload_hash": pose_hash,
                                "ok": int(ok),
                            })
                        pose_ms = (time.perf_counter() - pose_start) * 1000.0
                        actors_after_pose = managed_actors()
                        pose_signature = actor_signature(actors_after_pose)
                        components_after_pose = component_count(actors_after_pose)
                        for pose_row in pose_poll_rows[-updates_per_actor:]:
                            pose_row["actors_after_pose"] = len(actors_after_pose)
                            pose_row["components_after_pose"] = components_after_pose
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
                        shape_before_state = managed_actor_state_by_entity()
                        shape_meta = action_schedule_lookup[(condition["condition_id"], "shape", None)]
                        shape_start_requests = state.snapshot()[1]
                        shape_start_utc = utc_iso()
                        start = time.perf_counter()
                        shape_ok, shape_payload_bytes, shape_payload_hash = poll_payload(component, state, shape_obstacles, timeout_s)
                        shape_ms = (time.perf_counter() - start) * 1000.0
                        shape_end_utc = utc_iso()
                        shape_end_requests = state.snapshot()[1]
                        append_order_trace(shape_meta, shape_start_utc, shape_end_utc, row_id, shape_ok, shape_ms, shape_end_requests - shape_start_requests, 0)
                        actors_after_shape = managed_actors()
                        shape_signature = actor_signature(actors_after_shape)
                        components_after_shape = component_count(actors_after_shape)
                        shape_after_state = managed_actor_state_by_entity()
                        runtime_update_trace_rows.extend(trace_update_rows(
                            baseline,
                            condition,
                            "shape_param_update",
                            None,
                            shape_payload_hash,
                            shape_obstacles,
                            shape_before_state,
                            shape_after_state,
                            shape_ms,
                            shape_start_utc,
                            shape_end_utc,
                        ))
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

                        end_requests = state.snapshot()[1]
                        row = {
                            "row_id": row_id,
                            "seed": int(schedule_seed),
                            "condition_id": condition["condition_id"],
                            "group_order": condition["group_order"],
                            "condition_order": condition["condition_order"],
                            "baseline_order_index": condition["baseline_order_index"],
                            "create_scheduled_order": create_meta["scheduled_order"],
                            "shape_scheduled_order": shape_meta["scheduled_order"],
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
                            "create_payload_hash": create_payload_hash,
                            "pose_payload_hashes": ";".join(pose_payload_hashes),
                            "shape_payload_hash": shape_payload_hash,
                            "http_requests": end_requests - start_requests,
                            "create_ok": int(create_ok),
                            "pose_ok": int(pose_ok),
                            "shape_ok": int(shape_ok),
                            "mode": "HTTP poll replay via PollNowBlockingForTest",
                        }
                        rows.append(row)
                        expected_actor_count = 0 if baseline == "no_render" else count
                        if len(actors_after_create) != expected_actor_count or len(actors_after_shape) != expected_actor_count:
                            failures.append("%s count=%d rep=%d actor count mismatch create=%d shape=%d expected=%d" % (baseline, count, repetition, len(actors_after_create), len(actors_after_shape), expected_actor_count))
                        if not (create_ok and pose_ok and shape_ok):
                            failures.append("%s count=%d rep=%d returned false from HTTP poll" % (baseline, count, repetition))
                        expected_requests = updates_per_actor + 2
                        if row["http_requests"] != expected_requests:
                            failures.append("%s count=%d rep=%d expected %d HTTP requests, saw %d" % (baseline, count, repetition, expected_requests, row["http_requests"]))
                    except Exception as exc:
                        failures.append("%s count=%d rep=%d failed: %s" % (baseline, count, repetition, exc))
                    finally:
                        if owner is not None:
                            destroy_actor(owner)
                        cleanup_temp_actors()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)

    summary = {}
    summary_by_count = {}
    batch_summary_rows = build_batch_summary_rows(rows, pose_poll_rows, baselines, counts)
    incremental_delta_rows = build_incremental_delta_rows(rows, pose_poll_rows, counts)
    runtime_update_summary = build_runtime_update_summary(runtime_update_trace_rows)
    for baseline in baselines:
        summary[baseline] = {}
        for key in ["create_per_actor_ms", "pose_update_per_actor_update_ms", "shape_update_per_actor_ms"]:
            summary[baseline][key] = summarize([row[key] for row in rows if row["baseline"] == baseline])
        summary_by_count[baseline] = {}
        for count in counts:
            summary_by_count[baseline][str(count)] = {}
            for key in ["create_per_actor_ms", "pose_update_per_actor_update_ms", "shape_update_per_actor_ms"]:
                summary_by_count[baseline][str(count)][key] = summarize([row[key] for row in rows if row["baseline"] == baseline and row["count"] == count])

    write_csv(out_dir / "http_poll_replay_rows.csv", rows, list(rows[0].keys()) if rows else [])
    write_csv(out_dir / "http_poll_replay_pose_poll_rows.csv", pose_poll_rows, list(pose_poll_rows[0].keys()) if pose_poll_rows else [])
    write_csv(out_dir / "http_poll_replay_order_trace.csv", order_trace_rows, order_trace_fields)
    write_csv(out_dir / "sppa_runtime_update_trace.csv", runtime_update_trace_rows, list(runtime_update_trace_rows[0].keys()) if runtime_update_trace_rows else [])
    write_csv(
        out_dir / "http_poll_replay_batch_summary_by_count.csv",
        batch_summary_rows,
        list(batch_summary_rows[0].keys()) if batch_summary_rows else [],
    )
    write_csv(
        out_dir / "http_poll_replay_incremental_deltas_by_count.csv",
        incremental_delta_rows,
        list(incremental_delta_rows[0].keys()) if incremental_delta_rows else [],
    )
    with (out_dir / "component_identity_trace.jsonl").open("w", encoding="utf-8") as handle:
        for row in identity_trace_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    write_jsonl(out_dir / "sppa_runtime_update_trace.jsonl", runtime_update_trace_rows)
    (out_dir / "http_poll_replay_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "http_poll_replay_summary_by_count.json").write_text(json.dumps(summary_by_count, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "http_poll_replay_batch_summary_by_count.json").write_text(json.dumps(batch_summary_rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "http_poll_replay_incremental_deltas_by_count.json").write_text(json.dumps(incremental_delta_rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "sppa_runtime_update_summary.json").write_text(json.dumps(runtime_update_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "created_utc": utc_now(),
        "mode": "HTTP poll replay via PollNowBlockingForTest",
        "claim_scope": "Preliminary HTTP polling replay using the /api/ui/data path through Unreal HTTP module; local loopback server, Editor-Cmd, not packaged build, not render-thread, not VR frame-time.",
        "repo": str(REPO),
        "git_head": run_git(["rev-parse", "HEAD"]),
        "git_dirty": bool(run_git(["status", "--short"])),
        "engine_version": str(unreal.SystemLibrary.get_engine_version()),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "endpoint_url": endpoint_url,
        "counts": counts,
        "repetitions": repetitions,
        "updates_per_actor": updates_per_actor,
        "schedule_seed": int(schedule_seed),
        "schedule_design": "seeded count/repetition groups with counterbalanced rotated/reversed baseline order; create/pose/shape remain track-lifecycle ordered inside each condition",
        "poll_timeout_s": timeout_s,
        "baselines": baselines,
        "descriptor_count_loaded": len(descriptors),
        "descriptor_input_hash": stable_hash_text("\n".join(json.dumps(item, sort_keys=True) for item in descriptors)),
        "failures": failures,
        "artifacts": [
            "run_manifest.json",
            "input_descriptors.jsonl",
            "http_poll_replay_schedule.jsonl",
            "http_poll_replay_order_trace.csv",
            "http_poll_replay_rows.csv",
            "http_poll_replay_pose_poll_rows.csv",
            "component_identity_trace.jsonl",
            "sppa_runtime_update_trace.csv",
            "sppa_runtime_update_trace.jsonl",
            "sppa_runtime_update_summary.json",
            "http_poll_replay_summary.json",
            "http_poll_replay_summary_by_count.json",
            "http_poll_replay_batch_summary_by_count.csv",
            "http_poll_replay_batch_summary_by_count.json",
            "http_poll_replay_incremental_deltas_by_count.csv",
            "http_poll_replay_incremental_deltas_by_count.json",
        ],
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main():
    out_env = os.environ.get("PORCE_SPPA_HTTP_REPLAY_OUT_DIR", "").strip()
    if out_env:
        out_dir = Path(out_env)
    else:
        out_dir = REPO / "experiments" / "sppa_unreal_http_poll_replay" / f"{utc_now()}_http_poll_replay"
    if out_dir.exists():
        existing = [item.name for item in out_dir.iterdir()]
        allowed_preexisting = {"http_poll_replay.log"}
        if any(name not in allowed_preexisting for name in existing):
            raise RuntimeError(f"Output directory already exists and is non-empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = parse_int_list(os.environ.get("PORCE_SPPA_HTTP_REPLAY_COUNTS"), [10, 50, 100])
    repetitions = max(1, int(os.environ.get("PORCE_SPPA_HTTP_REPLAY_REPETITIONS", "3")))
    updates_per_actor = max(1, int(os.environ.get("PORCE_SPPA_HTTP_REPLAY_UPDATES", "5")))
    timeout_s = max(0.1, float(os.environ.get("PORCE_SPPA_HTTP_REPLAY_TIMEOUT_S", "2.0")))
    schedule_seed = int(os.environ.get("PORCE_SPPA_HTTP_REPLAY_SEED", "20260702"))
    manifest = run_benchmark(out_dir, counts, repetitions, updates_per_actor, timeout_s, schedule_seed)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    if manifest["failures"]:
        raise RuntimeError("SPPA HTTP poll replay benchmark completed with failures: %s" % manifest["failures"][:5])
    print("SPPA_HTTP_POLL_REPLAY_BENCHMARK_OK")


main()
