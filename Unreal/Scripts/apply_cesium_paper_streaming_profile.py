import json

import unreal


PAPER_PROFILE = {
    "MaximumScreenSpaceError": 8.0,
    "PreloadAncestors": True,
    "PreloadSiblings": True,
    "ForbidHoles": True,
    "MaximumSimultaneousTileLoads": 96,
    "MaximumCachedBytes": 8 * 1024 * 1024 * 1024,
    "LoadingDescendantLimit": 0,
    "EnableFrustumCulling": False,
    "EnableFogCulling": False,
    "EnforceCulledScreenSpaceError": True,
    "CulledScreenSpaceError": 16.0,
    "EnableOcclusionCulling": False,
    "DelayRefinementForOcclusion": False,
    "UseLodTransitions": False,
    "LodTransitionLength": 1.0,
    "SuspendUpdate": False,
    "UpdateInEditor": True,
    "UnloadEditorTilesInPlayMode": False,
}

RUNTIME_CACHE_PROFILE = {
    "ScaleLevelOfDetailByDPI": False,
    "RequestsPerCachePrune": 50000,
    "MaxCacheItems": 200000,
}


def _actor_label(actor):
    try:
        return str(actor.get_actor_label())
    except Exception:
        return str(actor.get_name())


def _get(actor, name):
    for candidate in (name, name[0].lower() + name[1:]):
        try:
            value = actor.get_editor_property(candidate)
            if hasattr(value, "value"):
                value = value.value
            return value
        except Exception:
            pass
    return None


def _set(actor, name, value):
    actor.modify()
    last_error = None
    for candidate in (name, name[0].lower() + name[1:]):
        try:
            actor.set_editor_property(candidate, value)
            return candidate
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not set {name}: {last_error}")


def _is_tileset(actor):
    return actor.get_class().get_name() == "Cesium3DTileset"

def _apply_runtime_cache_profile():
    settings_class = getattr(unreal, "CesiumRuntimeSettings", None)
    if settings_class is None:
        return {"available": False}
    try:
        settings = unreal.get_default_object(settings_class)
    except Exception:
        try:
            settings = settings_class.get_default_object()
        except Exception:
            return {"available": True, "default_object": None}

    changed = {}
    for key, value in RUNTIME_CACHE_PROFILE.items():
        previous = _get(settings, key)
        if previous != value:
            try:
                used_property = _set(settings, key, value)
                changed[key] = {"from": previous, "to": value, "property": used_property}
            except Exception as exc:
                changed[key] = {"from": previous, "to": value, "error": str(exc)}
    try:
        settings.save_config()
    except Exception:
        pass
    return {
        "available": True,
        "changed": changed,
        "after": {key: _get(settings, key) for key in RUNTIME_CACHE_PROFILE},
    }


subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
rows = []
camera_managers = []
runtime_cache = _apply_runtime_cache_profile()
for actor in subsystem.get_all_level_actors():
    if actor.get_class().get_name() == "CesiumCameraManager":
        manager_changes = {}
        for key, value in {
            "UsePlayerCameras": True,
            "UseEditorCameras": True,
            "UseSceneCapturesInLevel": True,
        }.items():
            previous = _get(actor, key)
            if previous != value:
                used_property = _set(actor, key, value)
                manager_changes[key] = {
                    "from": previous,
                    "to": value,
                    "property": used_property,
                }
        camera_managers.append(
            {
                "label": _actor_label(actor),
                "name": str(actor.get_name()),
                "changed": manager_changes,
                "after": {
                    "UsePlayerCameras": _get(actor, "UsePlayerCameras"),
                    "UseEditorCameras": _get(actor, "UseEditorCameras"),
                    "UseSceneCapturesInLevel": _get(actor, "UseSceneCapturesInLevel"),
                },
            }
        )

    if not _is_tileset(actor):
        continue

    before = {key: _get(actor, key) for key in PAPER_PROFILE}
    changed = {}
    for key, value in PAPER_PROFILE.items():
        previous = before[key]
        if previous != value:
            used_property = _set(actor, key, value)
            changed[key] = {
                "from": previous,
                "to": value,
                "property": used_property,
            }

    try:
        actor.refresh_tileset()
    except Exception as exc:
        unreal.log_warning(f"Could not refresh tileset {_actor_label(actor)}: {exc}")

    after = {key: _get(actor, key) for key in PAPER_PROFILE}
    rows.append(
        {
            "label": _actor_label(actor),
            "name": str(actor.get_name()),
            "changed": changed,
            "after": after,
        }
    )

saved = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(
    save_map_packages=True,
    save_content_packages=True,
)

print(json.dumps({"profile": "paper_streaming_no_popping", "runtime_cache": runtime_cache, "tilesets": rows, "camera_managers": camera_managers, "saved": saved}, indent=2, sort_keys=True))
