import json
from pathlib import Path

import unreal


LEVEL_PATH = "/Game/Ejea"
REPO = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).parent
OUT = REPO / "pipeline" / "logs" / "cesium_streaming_state_latest.json"

TILESET_PROPERTIES = [
    "TilesetSource",
    "Url",
    "IonAssetID",
    "MaximumScreenSpaceError",
    "PreloadAncestors",
    "PreloadSiblings",
    "ForbidHoles",
    "MaximumSimultaneousTileLoads",
    "MaximumCachedBytes",
    "LoadingDescendantLimit",
    "EnableFrustumCulling",
    "EnableFogCulling",
    "EnforceCulledScreenSpaceError",
    "CulledScreenSpaceError",
    "EnableOcclusionCulling",
    "DelayRefinementForOcclusion",
    "UseLodTransitions",
    "LodTransitionLength",
    "SuspendUpdate",
    "UpdateInEditor",
    "UnloadEditorTilesInPlayMode",
    "CreatePhysicsMeshes",
]

CAMERA_MANAGER_PROPERTIES = [
    "UsePlayerCameras",
    "UseEditorCameras",
    "UseSceneCapturesInLevel",
]

RUNTIME_SETTINGS_PROPERTIES = [
    "ScaleLevelOfDetailByDPI",
    "RequestsPerCachePrune",
    "MaxCacheItems",
]


def safe_text(value):
    if value is None:
        return None
    if hasattr(value, "value"):
        value = value.value
    return str(value)


def actor_label(actor):
    try:
        return str(actor.get_actor_label())
    except Exception:
        return str(actor.get_name())


def get_prop(obj, name):
    for candidate in (name, name[0].lower() + name[1:]):
        try:
            value = obj.get_editor_property(candidate)
            if hasattr(value, "value"):
                value = value.value
            if isinstance(value, (str, int, float, bool)) or value is None:
                return value
            if isinstance(value, (list, tuple)):
                return [safe_text(item) for item in value]
            return safe_text(value)
        except Exception:
            pass
    return None


def get_additional_cameras(actor):
    for candidate in ("AdditionalCameras", "additionalCameras", "additional_cameras"):
        try:
            value = actor.get_editor_property(candidate)
            count = len(value)
            sample = []
            for index, item in enumerate(value):
                if index >= 3:
                    break
                sample.append(safe_text(item))
            return {"count": int(count), "sample": sample}
        except Exception:
            pass
    return {"count": 0, "sample": []}


def int_or_zero(value):
    try:
        return int(value)
    except Exception:
        return 0


def load_progress(actor):
    try:
        method = getattr(actor, "get_load_progress")
        return float(method())
    except Exception:
        return get_prop(actor, "LoadProgress")


def runtime_settings():
    cls = getattr(unreal, "CesiumRuntimeSettings", None)
    if cls is None:
        return {"available": False}
    try:
        obj = unreal.get_default_object(cls)
    except Exception:
        try:
            obj = cls.get_default_object()
        except Exception:
            return {"available": True, "default_object": None}
    payload = {"available": True}
    for name in RUNTIME_SETTINGS_PROPERTIES:
        payload[name] = get_prop(obj, name)
    return payload


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(LEVEL_PATH)
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    tilesets = []
    camera_managers = []
    for actor in actors:
        cls = actor.get_class().get_name()
        if cls == "Cesium3DTileset":
            row = {
                "label": actor_label(actor),
                "name": str(actor.get_name()),
                "class": cls,
                "load_progress": load_progress(actor),
            }
            for prop in TILESET_PROPERTIES:
                row[prop] = get_prop(actor, prop)
            tilesets.append(row)
        if cls == "CesiumCameraManager":
            row = {
                "label": actor_label(actor),
                "name": str(actor.get_name()),
                "class": cls,
            }
            for prop in CAMERA_MANAGER_PROPERTIES:
                row[prop] = get_prop(actor, prop)
            row["AdditionalCameras"] = get_additional_cameras(actor)
            camera_managers.append(row)

    settings = runtime_settings()

    payload = {
        "ok": bool(tilesets),
        "level": LEVEL_PATH,
        "runtime_settings": settings,
        "tilesets": tilesets,
        "camera_managers": camera_managers,
        "diagnosis": {
            "has_tileset": bool(tilesets),
            "streaming_profile_applied": all(
                int_or_zero(row.get("MaximumCachedBytes")) >= 8 * 1024 * 1024 * 1024
                for row in tilesets
            ),
            "request_cache_large_enough": int_or_zero(settings.get("MaxCacheItems")) >= 100000,
            "additional_route_cameras": sum(
                int((row.get("AdditionalCameras") or {}).get("count", 0))
                for row in camera_managers
            ),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True)
    OUT.write_text(text + "\n", encoding="utf-8")
    print(text)
    if not payload["ok"]:
        raise RuntimeError("No Cesium3DTileset actors found")


main()
