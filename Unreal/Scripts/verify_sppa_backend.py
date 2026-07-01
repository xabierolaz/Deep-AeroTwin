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

def verify_proxy_generation(proxy_cls):
    expected_min_parts = {
        "bike": 6,
        "cow": 7,
        "tower": 4,
        "unknown": 3,
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
            rows.append(
                {
                    "class_name": class_name,
                    "confirmed": confirmed,
                    "component_count": len(components),
                    "mesh_component_count": mesh_count,
                    "collision_enabled_count": collision_count,
                    "tags": tags,
                }
            )

            if mesh_count < expected_min:
                failures.append(
                    "SPPA proxy %s generated %d mesh parts, expected at least %d"
                    % (class_name, mesh_count, expected_min)
                )
            if "PORCE_SPPA_PROXY" not in tags:
                failures.append("SPPA proxy %s missing PORCE_SPPA_PROXY tag" % class_name)
            if confirmed and collision_count < 1:
                failures.append("Confirmed SPPA proxy %s did not enable collision on any part" % class_name)
            if not confirmed and collision_count != 0:
                failures.append("Tentative SPPA proxy %s enabled collision unexpectedly" % class_name)
    finally:
        for actor in actors:
            destroy_actor(actor)
        cleanup_temp_actors()

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
            ],
        )
        failures.extend(
            "PorceTelemetryComponent missing property: " + item
            for item in component_property_check["missing"]
        )

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
            ["ConfigureProxy"],
        )
        failures.extend(
            "PorceSemanticProxyActor missing method: " + item
            for item in proxy_method_check["missing"]
        )

    enum_text = " ".join(enum_names).upper()
    if backend_enum_cls is not None and ("ASSET" not in enum_text or "PROXY" not in enum_text):
        failures.append("PorceTwinSpawnBackend enum does not expose both asset and proxy modes")

    proxy_generation = {"rows": [], "failures": []}
    if proxy_cls is not None and not proxy_method_check.get("missing"):
        try:
            proxy_generation = verify_proxy_generation(proxy_cls)
            failures.extend(proxy_generation["failures"])
        except Exception as exc:
            failures.append("SPPA proxy generation smoke failed: %s" % exc)

    payload = {
        "ok": len(failures) == 0,
        "component_python_name": component_py_name,
        "proxy_python_name": proxy_py_name,
        "backend_enum_python_name": backend_enum_py_name,
        "backend_enum_values": enum_names,
        "component_properties": component_property_check,
        "component_methods": component_method_check,
        "proxy_properties": proxy_property_check,
        "proxy_methods": proxy_method_check,
        "proxy_generation": proxy_generation,
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
