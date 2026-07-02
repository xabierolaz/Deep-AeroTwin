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
TEMP_PREFIX = "DAT_SPPA_Bench_"


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


def read_jsonl(path, limit=None):
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
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
    return [
        {
            "descriptor_schema": "SPPA-DESC-0.2",
            "descriptor_id": "sppa-inline-bench-car",
            "input": {"normalized_label": "car", "confidence": 0.9},
            "semantic": {"normalized_label": "car", "class_confidence": 0.9, "unknown_label": False},
            "uncertainty": {"confidence": 0.9, "fallback_unknown": False},
            "runtime_policy": {"action": "create"},
            "scale": {"dims_m": {"length": 2.4, "width": 1.2, "height": 1.3}},
            "parts": [
                {"role": "body", "primitive": "box", "local_pose": {"center": [0, 0, 0.7], "axis": "z"}, "scale": [2.4, 1.2, 0.5], "material_role": "vehicle_body", "evidence_source": "semantic_prior"},
                {"role": "cab", "primitive": "box", "local_pose": {"center": [0.35, 0, 1.1], "axis": "z"}, "scale": [0.8, 0.9, 0.45], "material_role": "vehicle_cab", "evidence_source": "semantic_prior"},
            ],
        }
    ]


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
        length = float(dims.get("length", 1.5))
        width = float(dims.get("width", 1.0))
        height = float(dims.get("height", 1.0))
    except Exception:
        length, width, height = 1.5, 1.0, 1.0
    return max(length, 0.1), max(width, 0.1), max(height, 0.1)


def descriptor_triangle_count(descriptor):
    try:
        return int((descriptor.get("mesh") or {}).get("triangles", 0))
    except Exception:
        return 0


def actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def editor_world():
    subsystem_class = getattr(unreal, "UnrealEditorSubsystem", None)
    if subsystem_class is not None:
        try:
            subsystem = unreal.get_editor_subsystem(subsystem_class)
            world = subsystem.get_editor_world()
            if world is not None:
                return world
        except Exception:
            pass
    try:
        return unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        return None


def ensure_world():
    world = editor_world()
    if world is not None:
        return world
    unreal.EditorLoadingAndSavingUtils.load_map("/Game/Ejea")
    world = editor_world()
    if world is None:
        raise RuntimeError("Could not obtain editor world for SPPA benchmark")
    return world


def actor_label(actor):
    try:
        return str(actor.get_actor_label())
    except Exception:
        return str(actor.get_name())


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
        name = str(actor.get_name())
        if label.startswith(TEMP_PREFIX) or name.startswith(TEMP_PREFIX):
            destroy_actor(actor)


def set_actor_label(actor, label):
    try:
        actor.set_actor_label(label)
    except Exception:
        pass


def load_asset(path):
    try:
        return unreal.load_object(None, path)
    except Exception:
        return None


CUBE_MESH = load_asset("/Engine/BasicShapes/Cube.Cube")
SPHERE_MESH = load_asset("/Engine/BasicShapes/Sphere.Sphere")
BASIC_MATERIAL = load_asset("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial")


def spawn_static_mesh_actor(mesh, label, location, scale):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.StaticMeshActor, location, unreal.Rotator(0.0, 0.0, 0.0))
    if actor is None:
        raise RuntimeError("StaticMeshActor spawn returned None")
    set_actor_label(actor, label)
    component = actor.static_mesh_component
    if mesh is not None:
        component.set_static_mesh(mesh)
    if BASIC_MATERIAL is not None:
        component.set_material(0, BASIC_MATERIAL)
    actor.set_actor_scale3d(scale)
    return actor


def spawn_text_actor(label, text, location):
    text_cls = getattr(unreal, "TextRenderActor", None)
    if text_cls is None:
        return spawn_static_mesh_actor(CUBE_MESH, label, location, unreal.Vector(0.15, 0.15, 0.15))
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(text_cls, location, unreal.Rotator(0.0, 0.0, 0.0))
    if actor is None:
        raise RuntimeError("TextRenderActor spawn returned None")
    set_actor_label(actor, label)
    try:
        actor.text_render.set_text(str(text))
        actor.text_render.set_world_size(40.0)
    except Exception:
        pass
    return actor


def get_unreal_type(*names):
    for name in names:
        value = getattr(unreal, name, None)
        if value is not None:
            return value
    return None


def configure_proxy(actor, label, confidence, confirmed):
    method = getattr(actor, "configure_proxy", None) or getattr(actor, "ConfigureProxy", None)
    if method is None:
        raise RuntimeError("PorceSemanticProxyActor missing configure_proxy")
    method(str(label), float(confidence), bool(confirmed))


def configure_descriptor(actor, descriptor_json, confirmed):
    method = getattr(actor, "configure_proxy_from_descriptor_json", None) or getattr(actor, "ConfigureProxyFromDescriptorJson", None)
    if method is None:
        raise RuntimeError("PorceSemanticProxyActor missing configure_proxy_from_descriptor_json")
    return bool(method(str(descriptor_json), bool(confirmed)))


def apply_update(actor, packet_json, confirmed):
    method = getattr(actor, "apply_proxy_update_packet_json", None) or getattr(actor, "ApplyProxyUpdatePacketJson", None)
    if method is None:
        raise RuntimeError("PorceSemanticProxyActor missing apply_proxy_update_packet_json")
    return bool(method(str(packet_json), bool(confirmed)))


def static_mesh_components(actor):
    try:
        return list(actor.get_components_by_class(unreal.StaticMeshComponent))
    except Exception:
        return []


def component_count(actors):
    total = 0
    for actor in actors:
        total += len(static_mesh_components(actor))
    return total

def component_signature(actors):
    signature = []
    for actor in actors:
        component_names = []
        for component in static_mesh_components(actor):
            try:
                component_names.append(str(component.get_name()))
            except Exception:
                component_names.append(str(component))
        signature.append([actor_label(actor), sorted(component_names)])
    return sorted(signature, key=lambda item: item[0])


def location_for_index(index):
    x = float((index % 25) * 300.0)
    y = float((index // 25) * 300.0)
    return unreal.Vector(x, y, 0.0)


def mutate_location(actor, index, step):
    actor.set_actor_location(location_for_index(index) + unreal.Vector(float(step * 5), 0.0, 0.0), False, False)


def dims_scale_vector(descriptor, multiplier=1.0):
    length, width, height = descriptor_dims(descriptor)
    return unreal.Vector(float(length * multiplier), float(width * multiplier), float(height * multiplier))


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
        "scale": {
            "dims_m": {
                "length": length * multiplier,
                "width": width * multiplier,
                "height": height,
            }
        },
        "parts": parts,
    }


def build_pose_packet(descriptor):
    return {
        "packet_schema": "SPPA-UPD-0.2",
        "descriptor_id": descriptor.get("descriptor_id", "unknown_descriptor"),
        "action": "pose_update",
    }


def build_noop_packet(descriptor):
    return {
        "packet_schema": "SPPA-UPD-0.2",
        "descriptor_id": descriptor.get("descriptor_id", "unknown_descriptor"),
        "action": "no_op",
    }


def summarize(values):
    if not values:
        return {"n": 0, "p50": None, "p95": None, "p99": None, "max": None}
    values = sorted(float(v) for v in values)
    def pct(p):
        if len(values) == 1:
            return values[0]
        index = min(len(values) - 1, max(0, int(round((p / 100.0) * (len(values) - 1)))))
        return values[index]
    return {
        "n": len(values),
        "p50": pct(50),
        "p95": pct(95),
        "p99": pct(99),
        "max": values[-1],
        "mean": statistics.mean(values),
    }


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_git(args):
    try:
        completed = subprocess.run(
            ["git", "-C", str(REPO)] + list(args),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return completed.stdout.strip()
    except Exception:
        return ""


def run_benchmark(out_dir, counts, repetitions, updates_per_actor):
    ensure_world()
    cleanup_temp_actors()
    proxy_cls = get_unreal_type("PorceSemanticProxyActor")
    if proxy_cls is None:
        raise RuntimeError("PorceSemanticProxyActor is not exposed to Unreal Python")

    max_count = max(counts)
    descriptors = load_descriptors(max_count)
    descriptor_jsons = [json.dumps(item, sort_keys=True) for item in descriptors]
    baselines = ["no_render", "billboard_label", "box_proxy", "ellipsoid_proxy", "legacy_semantic_proxy", "sppa_desc"]
    rows = []
    trace_rows = []
    actor_trace_rows = []
    failures = []
    with (out_dir / "input_descriptors.jsonl").open("w", encoding="utf-8") as handle:
        for descriptor in descriptors:
            handle.write(json.dumps(descriptor, sort_keys=True) + "\n")

    for baseline in baselines:
        for count in counts:
            selected = [descriptors[i % len(descriptors)] for i in range(count)]
            selected_jsons = [descriptor_jsons[i % len(descriptor_jsons)] for i in range(count)]
            for repetition in range(repetitions):
                cleanup_temp_actors()
                actors = []
                created_components = 0
                create_failures = 0
                create_start = time.perf_counter()
                logical_state = {}
                for index, descriptor in enumerate(selected):
                    location = location_for_index(index)
                    label = descriptor_label(descriptor)
                    confidence = descriptor_confidence(descriptor)
                    confirmed = confidence >= 0.65
                    try:
                        if baseline == "no_render":
                            logical_state[index] = {
                                "label": label,
                                "confidence": confidence,
                                "location": [location.x, location.y, location.z],
                            }
                            continue
                        if baseline == "billboard_label":
                            actor = spawn_text_actor(f"{TEMP_PREFIX}{baseline}_{index}", label, location)
                        elif baseline == "box_proxy":
                            actor = spawn_static_mesh_actor(CUBE_MESH, f"{TEMP_PREFIX}{baseline}_{index}", location, dims_scale_vector(descriptor))
                        elif baseline == "ellipsoid_proxy":
                            actor = spawn_static_mesh_actor(SPHERE_MESH, f"{TEMP_PREFIX}{baseline}_{index}", location, dims_scale_vector(descriptor))
                        elif baseline == "legacy_semantic_proxy":
                            actor = unreal.EditorLevelLibrary.spawn_actor_from_class(proxy_cls, location, unreal.Rotator(0.0, 0.0, 0.0))
                            set_actor_label(actor, f"{TEMP_PREFIX}{baseline}_{index}")
                            configure_proxy(actor, label, confidence, confirmed)
                        elif baseline == "sppa_desc":
                            actor = unreal.EditorLevelLibrary.spawn_actor_from_class(proxy_cls, location, unreal.Rotator(0.0, 0.0, 0.0))
                            set_actor_label(actor, f"{TEMP_PREFIX}{baseline}_{index}")
                            if not configure_descriptor(actor, selected_jsons[index], confirmed):
                                create_failures += 1
                        else:
                            continue
                        actors.append(actor)
                    except Exception as exc:
                        create_failures += 1
                        failures.append(f"{baseline} create failed at index {index}: {exc}")
                create_ms = (time.perf_counter() - create_start) * 1000.0
                created_components = component_count(actors)
                created_component_signature = component_signature(actors)

                pose_start = time.perf_counter()
                pose_failures = 0
                for step in range(updates_per_actor):
                    for index, actor in enumerate(actors):
                        try:
                            mutate_location(actor, index, step + 1)
                            if baseline == "sppa_desc":
                                apply_update(actor, json.dumps(build_pose_packet(selected[index]), sort_keys=True), True)
                        except Exception as exc:
                            pose_failures += 1
                            failures.append(f"{baseline} pose_update failed at index {index}: {exc}")
                    if baseline == "no_render":
                        for index in range(count):
                            logical_state[index]["location"][0] += float((step + 1) * 5)
                pose_ms = (time.perf_counter() - pose_start) * 1000.0
                components_after_pose = component_count(actors)
                pose_component_signature = component_signature(actors)

                shape_start = time.perf_counter()
                shape_failures = 0
                for index, actor in enumerate(actors):
                    try:
                        multiplier = 1.05 if (index % 2 == 0) else 0.95
                        if baseline == "sppa_desc":
                            packet = build_shape_packet(selected[index], multiplier)
                            if not apply_update(actor, json.dumps(packet, sort_keys=True), True):
                                shape_failures += 1
                        elif baseline in ("box_proxy", "ellipsoid_proxy"):
                            actor.set_actor_scale3d(dims_scale_vector(selected[index], multiplier))
                        elif baseline == "legacy_semantic_proxy":
                            actor.set_actor_scale3d(unreal.Vector(multiplier, multiplier, 1.0))
                        elif baseline == "no_render":
                            logical_state[index]["shape_multiplier"] = multiplier
                    except Exception as exc:
                        shape_failures += 1
                        failures.append(f"{baseline} shape_update failed at index {index}: {exc}")
                shape_ms = (time.perf_counter() - shape_start) * 1000.0
                components_after_shape = component_count(actors)
                shape_component_signature = component_signature(actors)

                no_op_start = time.perf_counter()
                no_op_failures = 0
                if baseline == "sppa_desc":
                    for index, actor in enumerate(actors):
                        try:
                            apply_update(actor, json.dumps(build_noop_packet(selected[index]), sort_keys=True), True)
                        except Exception as exc:
                            no_op_failures += 1
                            failures.append(f"{baseline} no_op failed at index {index}: {exc}")
                no_op_ms = (time.perf_counter() - no_op_start) * 1000.0

                destroy_start = time.perf_counter()
                for actor in actors:
                    destroy_actor(actor)
                destroy_ms = (time.perf_counter() - destroy_start) * 1000.0

                descriptor_bytes = sum(len(text.encode("utf-8")) for text in selected_jsons) if baseline == "sppa_desc" else 0
                estimated_triangles = sum(descriptor_triangle_count(item) for item in selected) if baseline == "sppa_desc" else None
                row = {
                    "baseline": baseline,
                    "count": count,
                    "repetition": repetition,
                    "updates_per_actor": updates_per_actor,
                    "create_total_ms": create_ms,
                    "create_per_object_ms": create_ms / max(count, 1),
                    "pose_update_total_ms": pose_ms,
                    "pose_update_per_object_ms": pose_ms / max(count * updates_per_actor, 1),
                    "shape_update_total_ms": shape_ms,
                    "shape_update_per_object_ms": shape_ms / max(count, 1),
                    "no_op_total_ms": no_op_ms,
                    "no_op_per_object_ms": no_op_ms / max(count, 1),
                    "destroy_total_ms": destroy_ms,
                    "destroy_per_object_ms": destroy_ms / max(count, 1),
                    "actor_count": count if baseline == "no_render" else len(actors),
                    "components_after_create": created_components,
                    "components_after_pose": components_after_pose,
                    "components_after_shape": components_after_shape,
                    "components_created_approx": created_components,
                    "components_destroyed_approx": components_after_shape,
                    "components_reused_during_pose": int(components_after_pose == created_components),
                    "components_reused_during_shape": int(components_after_shape == components_after_pose),
                    "component_names_reused_during_pose": int(pose_component_signature == created_component_signature),
                    "component_names_reused_during_shape": int(shape_component_signature == pose_component_signature),
                    "descriptor_bytes": descriptor_bytes,
                    "triangles_estimated": estimated_triangles,
                    "create_failures": create_failures,
                    "pose_failures": pose_failures,
                    "shape_failures": shape_failures,
                    "no_op_failures": no_op_failures,
                    "mode": "Editor-Cmd actor microbenchmark",
                }
                rows.append(row)
                actor_trace_rows.append({
                    "baseline": baseline,
                    "count": count,
                    "repetition": repetition,
                    "actor_count": row["actor_count"],
                    "components_after_create": created_components,
                    "components_after_pose": components_after_pose,
                    "components_after_shape": components_after_shape,
                    "components_reused_during_pose": bool(row["components_reused_during_pose"]),
                    "components_reused_during_shape": bool(row["components_reused_during_shape"]),
                    "component_names_reused_during_pose": bool(row["component_names_reused_during_pose"]),
                    "component_names_reused_during_shape": bool(row["component_names_reused_during_shape"]),
                    "create_failures": create_failures,
                    "pose_failures": pose_failures,
                    "shape_failures": shape_failures,
                    "no_op_failures": no_op_failures,
                })

                for action, total_ms, denom in [
                    ("create", create_ms, count),
                    ("pose_update", pose_ms, count * updates_per_actor),
                    ("shape_param_update", shape_ms, count),
                    ("no_op", no_op_ms, count),
                    ("destroy", destroy_ms, count),
                ]:
                    trace_rows.append({
                        "baseline": baseline,
                        "count": count,
                        "repetition": repetition,
                        "action": action,
                        "total_ms": total_ms,
                        "per_object_ms": total_ms / max(denom, 1),
                        "components_after_shape": components_after_shape,
                    })

                cleanup_temp_actors()

    summary = {}
    for baseline in baselines:
        summary[baseline] = {}
        for action_key in ["create_per_object_ms", "pose_update_per_object_ms", "shape_update_per_object_ms", "no_op_per_object_ms", "destroy_per_object_ms"]:
            summary[baseline][action_key] = summarize([row[action_key] for row in rows if row["baseline"] == baseline])
    row_failure_totals = {
        "create_failures": sum(int(row["create_failures"]) for row in rows),
        "pose_failures": sum(int(row["pose_failures"]) for row in rows),
        "shape_failures": sum(int(row["shape_failures"]) for row in rows),
        "no_op_failures": sum(int(row["no_op_failures"]) for row in rows),
    }
    if any(value > 0 for value in row_failure_totals.values()):
        failures.append("Nonzero row failure counters: %s" % row_failure_totals)

    fieldnames = list(rows[0].keys()) if rows else []
    write_csv(out_dir / "unreal_actor_microbenchmark_rows.csv", rows, fieldnames)
    write_csv(out_dir / "unreal_actor_microbenchmark_action_trace.csv", trace_rows, list(trace_rows[0].keys()) if trace_rows else [])
    with (out_dir / "actor_component_trace.jsonl").open("w", encoding="utf-8") as handle:
        for row in actor_trace_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "unreal_actor_microbenchmark_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "created_utc": utc_now(),
        "mode": "Editor-Cmd actor microbenchmark",
        "claim_scope": "Preliminary actor-level Unreal timings only; not /api/ui/data replay, not packaged build, not VR frame-time.",
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
        "row_failure_totals": row_failure_totals,
        "failures": failures,
        "artifacts": [
            "run_manifest.json",
            "input_descriptors.jsonl",
            "actor_component_trace.jsonl",
            "unreal_actor_microbenchmark_rows.csv",
            "unreal_actor_microbenchmark_action_trace.csv",
            "unreal_actor_microbenchmark_summary.json",
        ],
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main():
    out_env = os.environ.get("PORCE_SPPA_UNREAL_BENCH_OUT_DIR", "").strip()
    if out_env:
        out_dir = Path(out_env)
    else:
        out_dir = REPO / "experiments" / "sppa_unreal_backend" / f"{utc_now()}_editor_actor_microbenchmark"
    if out_dir.exists():
        existing = [item.name for item in out_dir.iterdir()]
        allowed_preexisting = {"unreal_actor_microbenchmark.log"}
        if any(name not in allowed_preexisting for name in existing):
            raise RuntimeError(f"Output directory already exists and is non-empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = parse_int_list(os.environ.get("PORCE_SPPA_UNREAL_BENCH_COUNTS"), [10, 50, 100])
    repetitions_raw = os.environ.get("PORCE_SPPA_UNREAL_BENCH_REPETITIONS", "3")
    updates_raw = os.environ.get("PORCE_SPPA_UNREAL_BENCH_UPDATES", "5")
    repetitions = max(1, int(repetitions_raw))
    updates_per_actor = max(1, int(updates_raw))
    manifest = run_benchmark(out_dir, counts, repetitions, updates_per_actor)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    if manifest["failures"]:
        raise RuntimeError("SPPA Unreal benchmark completed with failures: %s" % manifest["failures"][:5])
    print("SPPA_UNREAL_BACKEND_BENCHMARK_OK")


main()
