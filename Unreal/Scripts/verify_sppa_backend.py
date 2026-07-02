import json
import re
from pathlib import Path

import unreal

REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
OUT = REPO / "pipeline" / "logs" / "sppa_backend_verify_latest.json"
TEMP_PREFIX = "DAT_SPPA_Verify_"


def snake_case(name):
    step1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    step2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", step1)
    return step2.lower()


def get_unreal_type(*names):
    for name in names:
        value = getattr(unreal, name, None)
        if value is not None:
            return value, name
    return None, None


def has_property(obj, name):
    for candidate in (name, name[0].lower() + name[1:], snake_case(name)):
        try:
            obj.get_editor_property(candidate)
            return True, candidate
        except Exception:
            pass
    return False, None


def get_property_value(obj, name):
    for candidate in (name, name[0].lower() + name[1:], snake_case(name)):
        try:
            return obj.get_editor_property(candidate), candidate
        except Exception:
            pass
    return None, None

def has_method(cls, name):
    for candidate in (name, name[0].lower() + name[1:], snake_case(name)):
        if hasattr(cls, candidate):
            return True, candidate
    return False, None


def default_object(cls):
    try:
        return unreal.get_default_object(cls)
    except Exception:
        try:
            return cls.get_default_object()
        except Exception:
            return None


def check_properties(label, obj, required):
    rows = {}
    missing = []
    for name in required:
        ok, used = has_property(obj, name)
        rows[name] = {"ok": ok, "property": used}
        if not ok:
            missing.append(name)
    return {"label": label, "properties": rows, "missing": missing}


def check_component_defaults(component_cdo):
    rows = {}
    failures = []
    expected = {
        "SpawnBackend": "ASSET",
        "EndpointUrl": "/api/ui/data",
        "bEnabled": True,
        "bShowSpawnBackendSwitchUI": True,
    }

    for name, expected_value in expected.items():
        value, property_name = get_property_value(component_cdo, name)
        text = str(value)
        if isinstance(expected_value, bool):
            ok = bool(value) is expected_value
        else:
            ok = expected_value.upper() in text.upper()
        rows[name] = {
            "property": property_name,
            "value": text,
            "expected": str(expected_value),
            "ok": ok,
        }
        if not ok:
            failures.append("PorceTelemetryComponent default %s expected %s, got %s" % (name, expected_value, text))

    poll_rate, poll_property = get_property_value(component_cdo, "PollRateHz")
    try:
        poll_ok = float(poll_rate) > 0.0
    except Exception:
        poll_ok = False
    rows["PollRateHz"] = {
        "property": poll_property,
        "value": str(poll_rate),
        "expected": ">0",
        "ok": poll_ok,
    }
    if not poll_ok:
        failures.append("PorceTelemetryComponent default PollRateHz must be > 0, got %s" % poll_rate)

    return {"label": "PorceTelemetryComponent", "defaults": rows, "failures": failures}

def check_methods(label, cls, required):
    rows = {}
    missing = []
    for name in required:
        ok, used = has_method(cls, name)
        rows[name] = {"ok": ok, "method": used}
        if not ok:
            missing.append(name)
    return {"label": label, "methods": rows, "missing": missing}


def enum_values(enum_cls):
    if enum_cls is None:
        return []
    values = []
    for name in dir(enum_cls):
        if name.startswith("_"):
            continue
        if "ASSET" in name.upper() or "PROXY" in name.upper() or "SEMANTIC" in name.upper():
            values.append(name)
    return sorted(values)


def actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def editor_world():
    subsystem_class = getattr(unreal, "UnrealEditorSubsystem", None)
    if subsystem_class is not None:
        try:
            subsystem = unreal.get_editor_subsystem(subsystem_class)
            if subsystem is not None:
                world = subsystem.get_editor_world()
                if world is not None:
                    return world
        except Exception:
            pass
    try:
        return unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        return None

def ensure_editor_world():
    world = editor_world()
    if world is not None:
        return world
    unreal.EditorLoadingAndSavingUtils.load_map("/Game/Ejea")
    world = editor_world()
    if world is None:
        raise RuntimeError("Could not obtain an editor world for SPPA proxy spawn smoke")
    return world

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

def actor_label(actor):
    try:
        return str(actor.get_actor_label())
    except Exception:
        return str(actor.get_name())

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

def spawn_proxy_actor(proxy_cls, label):
    ensure_editor_world()
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        proxy_cls,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
    )
    if actor is None:
        raise RuntimeError("spawn_actor_from_class returned None for PorceSemanticProxyActor")
    try:
        actor.set_actor_label(label)
    except Exception:
        pass
    return actor

def static_mesh_components(actor):
    try:
        return list(actor.get_components_by_class(unreal.StaticMeshComponent))
    except Exception:
        return []

def component_has_mesh(component):
    try:
        return component.get_static_mesh() is not None
    except Exception:
        try:
            return component.get_editor_property("static_mesh") is not None
        except Exception:
            return False

def component_tags(component):
    try:
        return [str(tag) for tag in getattr(component, "component_tags", [])]
    except Exception:
        try:
            return [str(tag) for tag in component.get_editor_property("component_tags")]
        except Exception:
            return []


def collision_text(component):
    try:
        return str(component.get_collision_enabled())
    except Exception:
        try:
            value = component.get_editor_property("collision_enabled")
            if hasattr(value, "value"):
                value = value.value
            return str(value)
        except Exception:
            return ""

def has_enabled_collision(component):
    return "NO_COLLISION" not in collision_text(component).upper()

def configure_proxy(actor, class_name, confidence, confirmed):
    method = getattr(actor, "configure_proxy", None)
    if method is None:
        method = getattr(actor, "ConfigureProxy", None)
    if method is None:
        raise RuntimeError("PorceSemanticProxyActor instance has no configure_proxy method")
    method(class_name, float(confidence), bool(confirmed))

def configure_proxy_from_descriptor_json(actor, descriptor_json, confirmed):
    method = getattr(actor, "configure_proxy_from_descriptor_json", None)
    if method is None:
        method = getattr(actor, "ConfigureProxyFromDescriptorJson", None)
    if method is None:
        raise RuntimeError("PorceSemanticProxyActor instance has no configure_proxy_from_descriptor_json method")
    return bool(method(str(descriptor_json), bool(confirmed)))

def apply_proxy_update_packet_json(actor, update_packet_json, confirmed):
    method = getattr(actor, "apply_proxy_update_packet_json", None)
    if method is None:
        method = getattr(actor, "ApplyProxyUpdatePacketJson", None)
    if method is None:
        raise RuntimeError("PorceSemanticProxyActor instance has no apply_proxy_update_packet_json method")
    return bool(method(str(update_packet_json), bool(confirmed)))

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

def load_descriptor_fixture():
    fixture = REPO / "experiments" / "sppa_descriptor_update" / "20260702_descriptor_v04_atomic" / "descriptor_smoke_samples.jsonl"
    if fixture.exists():
        for line in fixture.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            descriptor = json.loads(line)
            if descriptor.get("descriptor_schema") == "SPPA-DESC-0.2" and descriptor.get("parts"):
                return descriptor, str(fixture)
    descriptor = {
        "descriptor_schema": "SPPA-DESC-0.2",
        "descriptor_id": "sppa-inline-verify",
        "input": {"normalized_label": "verification_vehicle", "confidence": 0.9},
        "semantic": {
            "normalized_label": "verification_vehicle",
            "class_confidence": 0.9,
            "unknown_label": False,
            "resolution_status": "inline_fixture",
        },
        "uncertainty": {"confidence": 0.9, "fallback_unknown": False},
        "runtime_policy": {"action": "create"},
        "parts": [
            {
                "role": "vehicle_body",
                "primitive": "box",
                "local_pose": {"center": [0.0, 0.0, 0.6], "axis": "z"},
                "scale": [2.0, 1.0, 0.5],
                "material_role": "vehicle_body",
                "evidence_source": "semantic_prior",
            },
            {
                "role": "vehicle_tire",
                "primitive": "cylinder",
                "local_pose": {"center": [0.7, 0.55, 0.25], "axis": "y"},
                "scale": [0.2, 0.2, 0.12],
                "material_role": "vehicle_tire",
                "evidence_source": "semantic_prior",
            },
        ],
    }
    return descriptor, "inline"

def verify_proxy_descriptor_ingestion(proxy_cls):
    failures = []
    actor = None
    try:
        cleanup_temp_actors()
        descriptor, source = load_descriptor_fixture()
        descriptor_json = json.dumps(descriptor, sort_keys=True)
        actor = spawn_proxy_actor(proxy_cls, TEMP_PREFIX + "descriptor_ingestion")
        ok = configure_proxy_from_descriptor_json(actor, descriptor_json, True)
        components = static_mesh_components(actor)
        mesh_count = sum(1 for component in components if component_has_mesh(component))
        expected_count = len(descriptor.get("parts", []))
        tags = [str(tag) for tag in getattr(actor, "tags", [])]
        all_component_tags = sorted({tag for component in components for tag in component_tags(component)})
        material_role_tags = [tag for tag in all_component_tags if tag.startswith("SPPA_MATERIAL_ROLE_")]
        evidence_source_tags = [tag for tag in all_component_tags if tag.startswith("SPPA_EVIDENCE_SOURCE_")]
        uncertainty_style_tags = [tag for tag in all_component_tags if tag.startswith("SPPA_UNCERTAINTY_STYLE_")]

        if not ok:
            failures.append("ConfigureProxyFromDescriptorJson returned false for a valid SPPA-DESC fixture")
        if mesh_count != expected_count:
            failures.append("Descriptor ingestion generated %d mesh parts, expected exactly %d" % (mesh_count, expected_count))
        if "PORCE_SPPA_DESCRIPTOR" not in tags:
            failures.append("Descriptor-ingested proxy missing PORCE_SPPA_DESCRIPTOR actor tag")
        if "PORCE_SPPA_PROXY" not in tags:
            failures.append("Descriptor-ingested proxy missing PORCE_SPPA_PROXY actor tag")
        if not material_role_tags:
            failures.append("Descriptor-ingested proxy generated no material-role component tags")
        if not evidence_source_tags:
            failures.append("Descriptor-ingested proxy generated no evidence-source component tags")
        if not uncertainty_style_tags:
            failures.append("Descriptor-ingested proxy generated no uncertainty-style component tags")

        invalid_ok = configure_proxy_from_descriptor_json(actor, "{not-valid-json", True)
        after_invalid_count = sum(1 for component in static_mesh_components(actor) if component_has_mesh(component))
        if invalid_ok:
            failures.append("ConfigureProxyFromDescriptorJson accepted invalid JSON")
        if after_invalid_count != mesh_count:
            failures.append("Invalid descriptor changed existing proxy part count from %d to %d" % (mesh_count, after_invalid_count))

        smaller = json.loads(descriptor_json)
        smaller["descriptor_id"] = "sppa-inline-reconfigure-smaller"
        smaller["parts"] = smaller.get("parts", [])[:1]
        smaller_ok = configure_proxy_from_descriptor_json(actor, json.dumps(smaller, sort_keys=True), True)
        smaller_count = sum(1 for component in static_mesh_components(actor) if component_has_mesh(component))
        if not smaller_ok:
            failures.append("ConfigureProxyFromDescriptorJson returned false for smaller reconfigure descriptor")
        if smaller_count != 1:
            failures.append("Descriptor reconfigure generated %d mesh parts, expected 1" % smaller_count)

        noop_packet = {
            "packet_schema": "SPPA-UPD-0.2",
            "descriptor_id": "sppa-inline-reconfigure-smaller",
            "action": "pose_update",
        }
        noop_ok = apply_proxy_update_packet_json(actor, json.dumps(noop_packet, sort_keys=True), True)
        noop_count = sum(1 for component in static_mesh_components(actor) if component_has_mesh(component))
        if not noop_ok:
            failures.append("pose_update packet was not accepted for an existing descriptor proxy")
        if noop_count != smaller_count:
            failures.append("pose_update packet changed part count from %d to %d" % (smaller_count, noop_count))

        wrong_id_packet = {
            "packet_schema": "SPPA-UPD-0.2",
            "descriptor_id": "sppa-wrong-descriptor-id",
            "action": "pose_update",
        }
        wrong_id_ok = apply_proxy_update_packet_json(actor, json.dumps(wrong_id_packet, sort_keys=True), True)
        wrong_id_count = sum(1 for component in static_mesh_components(actor) if component_has_mesh(component))
        if wrong_id_ok:
            failures.append("pose_update packet with mismatched descriptor_id was accepted")
        if wrong_id_count != noop_count:
            failures.append("mismatched pose_update packet changed part count from %d to %d" % (noop_count, wrong_id_count))

        inferred_shape_packet = {
            "packet_schema": "SPPA-UPD-0.2",
            "descriptor_id": "sppa-inline-reconfigure-smaller",
            "action": "shape_param_update",
            "scale": {"dims_m": {"length": 3.0, "width": 1.5, "height": 0.8}},
        }
        inferred_shape_update_ok = apply_proxy_update_packet_json(actor, json.dumps(inferred_shape_packet, sort_keys=True), True)
        inferred_shape_update_count = sum(1 for component in static_mesh_components(actor) if component_has_mesh(component))
        inferred_shape_update_scale = actor_relative_scale(actor)
        if inferred_shape_update_ok:
            failures.append("shape_param_update without replacement parts was accepted")
        if inferred_shape_update_count != wrong_id_count:
            failures.append("rejected shape_param_update changed part count from %d to %d" % (wrong_id_count, inferred_shape_update_count))
        if not all(0.98 <= value <= 1.02 for value in inferred_shape_update_scale):
            failures.append("rejected shape_param_update changed actor root scale: %s" % inferred_shape_update_scale)

        shape_descriptor = json.loads(descriptor_json)
        shape_descriptor["descriptor_id"] = "sppa-inline-shape-reference"
        shape_descriptor["scale"] = {"dims_m": {"length": 2.0, "width": 1.0, "height": 1.0}}
        shape_descriptor["parts"] = shape_descriptor.get("parts", [])[:2]
        shape_reference_ok = configure_proxy_from_descriptor_json(actor, json.dumps(shape_descriptor, sort_keys=True), True)
        shape_reference_count = sum(1 for component in static_mesh_components(actor) if component_has_mesh(component))
        shape_packet = {
            "packet_schema": "SPPA-UPD-0.2",
            "descriptor_id": "sppa-inline-shape-reference",
            "action": "shape_param_update",
            "scale": {"dims_m": {"length": 3.0, "width": 1.5, "height": 1.0}},
            "parts": shape_descriptor.get("parts", []),
        }
        shape_packet["parts"][0]["scale"] = [3.0, 1.0, 1.0]
        shape_update_ok = apply_proxy_update_packet_json(actor, json.dumps(shape_packet, sort_keys=True), True)
        shape_update_count = sum(1 for component in static_mesh_components(actor) if component_has_mesh(component))
        shape_update_scale = actor_relative_scale(actor)
        if not shape_reference_ok:
            failures.append("shape reference descriptor was not accepted")
        if not shape_update_ok:
            failures.append("shape_param_update packet was not accepted for matching descriptor")
        if shape_update_count != shape_reference_count:
            failures.append("shape_param_update changed part count from %d to %d" % (shape_reference_count, shape_update_count))
        if not all(0.98 <= value <= 1.02 for value in shape_update_scale):
            failures.append("shape_param_update changed actor root scale instead of part parameters: %s" % shape_update_scale)

        return {
            "fixture_source": source,
            "descriptor_id": descriptor.get("descriptor_id"),
            "expected_part_count": expected_count,
            "mesh_component_count": mesh_count,
            "part_count_after_invalid": after_invalid_count,
            "part_count_after_reconfigure": smaller_count,
            "part_count_after_pose_update": noop_count,
            "mismatched_pose_update_accepted": wrong_id_ok,
            "part_count_after_mismatched_pose_update": wrong_id_count,
            "inferred_reference_shape_param_update_accepted": inferred_shape_update_ok,
            "part_count_after_inferred_reference_shape_param_update": inferred_shape_update_count,
            "scale_after_inferred_reference_shape_param_update": inferred_shape_update_scale,
            "shape_param_update_accepted": shape_update_ok,
            "part_count_after_shape_param_update": shape_update_count,
            "scale_after_shape_param_update": shape_update_scale,
            "tags": tags,
            "component_tags": all_component_tags,
            "failures": failures,
        }
    finally:
        destroy_actor(actor)
        cleanup_temp_actors()

def verify_proxy_generation(proxy_cls):
    expected_min_parts = {
        'bike': 6,
        'cow': 7,
        'tower': 4,
        'car': 7,
        'ambulance': 7,
        'tree': 5,
        'antenna': 4,
        'mystery_object': 3,
        'unknown': 3,
    }
    rows = []
    failures = []
    actors = []
    try:
        cleanup_temp_actors()
        for class_name, expected_min in expected_min_parts.items():
            actor = spawn_proxy_actor(proxy_cls, TEMP_PREFIX + class_name)
            actors.append(actor)
            confirmed = class_name != "unknown"
            configure_proxy(actor, class_name, 0.95 if confirmed else 0.25, confirmed)
            components = static_mesh_components(actor)
            mesh_count = sum(1 for component in components if component_has_mesh(component))
            collision_count = sum(1 for component in components if has_enabled_collision(component))
            tags = [str(tag) for tag in getattr(actor, "tags", [])]
            all_component_tags = sorted({tag for component in components for tag in component_tags(component)})
            material_role_tags = [tag for tag in all_component_tags if tag.startswith("SPPA_MATERIAL_ROLE_")]
            evidence_source_tags = [tag for tag in all_component_tags if tag.startswith("SPPA_EVIDENCE_SOURCE_")]
            uncertainty_style_tags = [tag for tag in all_component_tags if tag.startswith("SPPA_UNCERTAINTY_STYLE_")]
            rows.append(
                {
                    "class_name": class_name,
                    "confirmed": confirmed,
                    "component_count": len(components),
                    "mesh_component_count": mesh_count,
                    "collision_enabled_count": collision_count,
                    "tags": tags,
                    "component_tags": all_component_tags,
                    "material_role_tag_count": len(material_role_tags),
                    "evidence_source_tag_count": len(evidence_source_tags),
                    "uncertainty_style_tag_count": len(uncertainty_style_tags),
                }
            )

            if mesh_count < expected_min:
                failures.append(
                    "SPPA proxy %s generated %d mesh parts, expected at least %d"
                    % (class_name, mesh_count, expected_min)
                )
            if "PORCE_SPPA_PROXY" not in tags:
                failures.append("SPPA proxy %s missing PORCE_SPPA_PROXY tag" % class_name)
            if not any(tag.startswith("PORCE_MATERIAL_POLICY_") for tag in tags):
                failures.append("SPPA proxy %s missing material policy actor tag" % class_name)
            if mesh_count > 0 and not material_role_tags:
                failures.append("SPPA proxy %s generated parts without material role tags" % class_name)
            if mesh_count > 0 and not evidence_source_tags:
                failures.append("SPPA proxy %s generated parts without evidence source tags" % class_name)
            if mesh_count > 0 and not uncertainty_style_tags:
                failures.append("SPPA proxy %s generated parts without uncertainty style tags" % class_name)
            if confirmed and collision_count < 1:
                failures.append("Confirmed SPPA proxy %s did not enable collision on any part" % class_name)
            if not confirmed and collision_count != 0:
                failures.append("Tentative SPPA proxy %s enabled collision unexpectedly" % class_name)
    finally:
        for actor in actors:
            destroy_actor(actor)
        cleanup_temp_actors()

    return {"rows": rows, "failures": failures}

def verify_proxy_reconfigure(proxy_cls):
    failures = []
    actor = None
    try:
        cleanup_temp_actors()
        actor = spawn_proxy_actor(proxy_cls, TEMP_PREFIX + "reconfigure")
        configure_proxy(actor, "bike", 0.95, True)
        bike_mesh_count = sum(1 for component in static_mesh_components(actor) if component_has_mesh(component))
        configure_proxy(actor, "cow", 0.95, True)
        components = static_mesh_components(actor)
        cow_mesh_count = sum(1 for component in components if component_has_mesh(component))
        tags = [str(tag) for tag in getattr(actor, "tags", [])]

        if "PORCE_CLASS_bike" in tags:
            failures.append("SPPA proxy reconfigure retained stale PORCE_CLASS_bike tag")
        if "PORCE_CLASS_cow" not in tags:
            failures.append("SPPA proxy reconfigure did not add PORCE_CLASS_cow tag")
        if cow_mesh_count < 7:
            failures.append("SPPA proxy reconfigure cow mesh count %d, expected at least 7" % cow_mesh_count)
        if cow_mesh_count > 8:
            failures.append("SPPA proxy reconfigure appears to accumulate mesh components: %d after bike count %d" % (cow_mesh_count, bike_mesh_count))

        return {
            "bike_mesh_component_count": bike_mesh_count,
            "cow_mesh_component_count": cow_mesh_count,
            "tags_after_reconfigure": tags,
            "failures": failures,
        }
    finally:
        destroy_actor(actor)
        cleanup_temp_actors()

def verify_proxy_unknown_fallback(proxy_cls):
    failures = []
    actor = None
    try:
        cleanup_temp_actors()
        actor = spawn_proxy_actor(proxy_cls, TEMP_PREFIX + "unknown_fallback")
        configure_proxy(actor, "", 0.10, False)
        tags = [str(tag) for tag in getattr(actor, "tags", [])]
        components = static_mesh_components(actor)
        mesh_count = sum(1 for component in components if component_has_mesh(component))
        collision_count = sum(1 for component in components if has_enabled_collision(component))
        all_component_tags = sorted({tag for component in components for tag in component_tags(component)})

        if "PORCE_CLASS_unknown" not in tags:
            failures.append("SPPA empty class fallback did not tag PORCE_CLASS_unknown")
        if "PORCE_CLASS_" in tags:
            failures.append("SPPA empty class fallback retained blank PORCE_CLASS_ tag")
        if mesh_count < 3:
            failures.append("SPPA empty class fallback generated %d mesh parts, expected at least 3" % mesh_count)
        if collision_count != 0:
            failures.append("SPPA empty tentative fallback enabled collision unexpectedly")
        if "SPPA_EVIDENCE_SOURCE_fallback_unknown" not in all_component_tags:
            failures.append("SPPA empty class fallback missing fallback_unknown evidence tag")
        if "SPPA_UNCERTAINTY_STYLE_warning_marker" not in all_component_tags:
            failures.append("SPPA empty class fallback missing warning_marker uncertainty tag")

        return {
            "mesh_component_count": mesh_count,
            "collision_enabled_count": collision_count,
            "tags": tags,
            "component_tags": all_component_tags,
            "failures": failures,
        }
    finally:
        destroy_actor(actor)
        cleanup_temp_actors()

def backend_enum_value(enum_cls, *tokens):
    if enum_cls is None:
        return None
    wanted = [token.upper() for token in tokens]
    for name in dir(enum_cls):
        upper = name.upper()
        if all(token in upper for token in wanted):
            return getattr(enum_cls, name)
    return None

def get_component_backend(component):
    method = getattr(component, "get_spawn_backend", None)
    if method is None:
        method = getattr(component, "GetSpawnBackend", None)
    if method is not None:
        return method()
    try:
        return component.get_editor_property("SpawnBackend")
    except Exception:
        return None

def is_component_using_proxy(component):
    method = getattr(component, "is_using_semantic_proxy_backend", None)
    if method is None:
        method = getattr(component, "IsUsingSemanticProxyBackend", None)
    if method is not None:
        return bool(method())
    backend = get_component_backend(component)
    return "PROXY" in str(backend).upper()

def call_component_backend_method(component, name, *args):
    method = getattr(component, snake_case(name), None)
    if method is None:
        method = getattr(component, name, None)
    if method is None:
        raise RuntimeError("PorceTelemetryComponent instance has no %s method" % name)
    return method(*args)

def verify_component_backend_switch(component_cls, backend_enum_cls):
    rows = []
    failures = []
    unreal_assets = backend_enum_value(backend_enum_cls, "ASSET")
    semantic_proxy = backend_enum_value(backend_enum_cls, "PROXY")
    if unreal_assets is None or semantic_proxy is None:
        return {
            "rows": rows,
            "failures": ["Could not resolve backend enum values for component switch smoke"],
        }

    try:
        component = unreal.new_object(component_cls)
    except Exception as exc:
        return {
            "rows": rows,
            "failures": ["Could not create transient PorceTelemetryComponent: %s" % exc],
        }

    try:
        call_component_backend_method(component, "SetSpawnBackend", unreal_assets)
        rows.append({"action": "set_assets", "backend": str(get_component_backend(component)), "is_proxy": is_component_using_proxy(component)})
        if is_component_using_proxy(component):
            failures.append("SetSpawnBackend(UnrealAssets) left component in proxy mode")

        call_component_backend_method(component, "SetSpawnBackend", semantic_proxy)
        rows.append({"action": "set_proxy", "backend": str(get_component_backend(component)), "is_proxy": is_component_using_proxy(component)})
        if not is_component_using_proxy(component):
            failures.append("SetSpawnBackend(SemanticProxy) did not switch component to proxy mode")

        call_component_backend_method(component, "ToggleSpawnBackend")
        rows.append({"action": "toggle_to_assets", "backend": str(get_component_backend(component)), "is_proxy": is_component_using_proxy(component)})
        if is_component_using_proxy(component):
            failures.append("ToggleSpawnBackend() did not switch proxy -> assets")

        call_component_backend_method(component, "ToggleSpawnBackend")
        rows.append({"action": "toggle_to_proxy", "backend": str(get_component_backend(component)), "is_proxy": is_component_using_proxy(component)})
        if not is_component_using_proxy(component):
            failures.append("ToggleSpawnBackend() did not switch assets -> proxy")
    except Exception as exc:
        failures.append("Component backend switch smoke failed: %s" % exc)

    return {"rows": rows, "failures": failures}

def main():
    component_cls, component_py_name = get_unreal_type("PorceTelemetryComponent")
    proxy_cls, proxy_py_name = get_unreal_type("PorceSemanticProxyActor")
    backend_enum_cls, backend_enum_py_name = get_unreal_type("PorceTwinSpawnBackend", "EPorceTwinSpawnBackend")

    failures = []
    if component_cls is None:
        failures.append("PorceTelemetryComponent is not exposed to Unreal Python")
    if proxy_cls is None:
        failures.append("PorceSemanticProxyActor is not exposed to Unreal Python")
    if backend_enum_cls is None:
        failures.append("PorceTwinSpawnBackend enum is not exposed to Unreal Python")

    component_cdo = default_object(component_cls) if component_cls is not None else None
    proxy_cdo = default_object(proxy_cls) if proxy_cls is not None else None
    if component_cls is not None and component_cdo is None:
        failures.append("PorceTelemetryComponent default object is unavailable")
    if proxy_cls is not None and proxy_cdo is None:
        failures.append("PorceSemanticProxyActor default object is unavailable")

    component_property_check = {"missing": []}
    component_default_check = {"failures": []}
    proxy_property_check = {"missing": []}
    component_method_check = {"missing": []}
    proxy_method_check = {"missing": []}
    enum_names = enum_values(backend_enum_cls)

    if component_cdo is not None:
        component_property_check = check_properties(
            "PorceTelemetryComponent",
            component_cdo,
            [
                "SpawnBackend",
                "SemanticProxyActorClass",
                "bShowSpawnBackendSwitchUI",
                "BikerActorClass",
                "CowActorClass",
                "TowerActorClass",
                "DefaultObstacleActorClass",
                "EndpointUrl",
                "AuthToken",
                "bEnabled",
                "PollRateHz",
            ],
        )
        failures.extend(
            "PorceTelemetryComponent missing property: " + item
            for item in component_property_check["missing"]
        )
        component_default_check = check_component_defaults(component_cdo)
        failures.extend(component_default_check["failures"])

    if component_cls is not None:
        component_method_check = check_methods(
            "PorceTelemetryComponent",
            component_cls,
            [
                "SetSpawnBackend",
                "ToggleSpawnBackend",
                "GetSpawnBackend",
                "IsUsingSemanticProxyBackend",
                "PollNow",
                "SendNow",
                "ApplyObstacleBatchJson",
            ],
        )
        failures.extend(
            "PorceTelemetryComponent missing method: " + item
            for item in component_method_check["missing"]
        )

    if proxy_cdo is not None:
        proxy_property_check = check_properties(
            "PorceSemanticProxyActor",
            proxy_cdo,
            [
                "bEnableCollisionForConfirmed",
                "ConfirmedColor",
                "TentativeColor",
                "UnknownColor",
                "bUseEvidenceCalibratedMaterials",
                "DescriptorMetersToCentimeters",
                "MaxDescriptorParts",
            ],
        )
        failures.extend(
            "PorceSemanticProxyActor missing property: " + item
            for item in proxy_property_check["missing"]
        )

    if proxy_cls is not None:
        proxy_method_check = check_methods(
            "PorceSemanticProxyActor",
            proxy_cls,
            ["ConfigureProxy", "ConfigureProxyFromDescriptorJson", "ApplyProxyUpdatePacketJson"],
        )
        failures.extend(
            "PorceSemanticProxyActor missing method: " + item
            for item in proxy_method_check["missing"]
        )

    enum_text = " ".join(enum_names).upper()
    if backend_enum_cls is not None and ("ASSET" not in enum_text or "PROXY" not in enum_text):
        failures.append("PorceTwinSpawnBackend enum does not expose both asset and proxy modes")

    component_switch = {"rows": [], "failures": []}
    if component_cls is not None and backend_enum_cls is not None and not component_method_check.get("missing"):
        component_switch = verify_component_backend_switch(component_cls, backend_enum_cls)
        failures.extend(component_switch["failures"])

    proxy_generation = {"rows": [], "failures": []}
    proxy_descriptor_ingestion = {"failures": []}
    proxy_reconfigure = {"failures": []}
    proxy_unknown_fallback = {"failures": []}
    if proxy_cls is not None and not proxy_method_check.get("missing"):
        try:
            proxy_descriptor_ingestion = verify_proxy_descriptor_ingestion(proxy_cls)
            failures.extend(proxy_descriptor_ingestion["failures"])
        except Exception as exc:
            failures.append("SPPA descriptor ingestion smoke failed: %s" % exc)
        try:
            proxy_generation = verify_proxy_generation(proxy_cls)
            failures.extend(proxy_generation["failures"])
        except Exception as exc:
            failures.append("SPPA proxy generation smoke failed: %s" % exc)
        try:
            proxy_reconfigure = verify_proxy_reconfigure(proxy_cls)
            failures.extend(proxy_reconfigure["failures"])
        except Exception as exc:
            failures.append("SPPA proxy reconfigure smoke failed: %s" % exc)
        try:
            proxy_unknown_fallback = verify_proxy_unknown_fallback(proxy_cls)
            failures.extend(proxy_unknown_fallback["failures"])
        except Exception as exc:
            failures.append("SPPA proxy unknown fallback smoke failed: %s" % exc)

    payload = {
        "ok": len(failures) == 0,
        "component_python_name": component_py_name,
        "proxy_python_name": proxy_py_name,
        "backend_enum_python_name": backend_enum_py_name,
        "backend_enum_values": enum_names,
        "component_properties": component_property_check,
        "component_defaults": component_default_check,
        "component_methods": component_method_check,
        "component_switch": component_switch,
        "proxy_properties": proxy_property_check,
        "proxy_methods": proxy_method_check,
        "proxy_descriptor_ingestion": proxy_descriptor_ingestion,
        "proxy_generation": proxy_generation,
        "proxy_reconfigure": proxy_reconfigure,
        "proxy_unknown_fallback": proxy_unknown_fallback,
        "failures": failures,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True)
    OUT.write_text(text + "\n", encoding="utf-8")
    print(text)

    if failures:
        raise RuntimeError("; ".join(failures))
    print("SPPA_BACKEND_VERIFY_OK")


main()
