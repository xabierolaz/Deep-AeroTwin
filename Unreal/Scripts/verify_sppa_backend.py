import json
import re
from pathlib import Path

import unreal

REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
OUT = REPO / "pipeline" / "logs" / "sppa_backend_verify_latest.json"


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
