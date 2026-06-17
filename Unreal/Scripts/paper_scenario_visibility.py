import json
import re

import unreal


CONTROLLED_GROUPS = ("towers", "cows", "bikers", "peloton")
PAPER_WP1_WP2_TOWER = {
    "label": "t0",
    "lat": 42.22904865463611,
    "lon": -1.234404232738992,
    "east_m": 56.05096609440895,
    "north_m": -71.87032532501878,
    "progress_wp1_wp2": 0.56,
    "lateral_m": 8.0,
}

PROFILES = {
    "paper_static_tower": {
        "description": "Figure 1 static obstacle: tower visible; cows, bikers and peloton hidden.",
        "visible": {
            "towers": True,
            "cows": False,
            "bikers": False,
            "peloton": False,
        },
        "recommended_vision_targets": "tower",
    },
    "paper_wp1_wp2_tower": {
        "description": "Figure 1 controlled sequence: one tower (t0) on WP1->WP2; all other paper obstacles hidden.",
        "visible": {
            "towers": False,
            "cows": False,
            "bikers": False,
            "peloton": False,
        },
        "selected_visible": {
            "towers": [PAPER_WP1_WP2_TOWER["label"]],
        },
        "move_to_llh": {
            PAPER_WP1_WP2_TOWER["label"]: {
                "lat": PAPER_WP1_WP2_TOWER["lat"],
                "lon": PAPER_WP1_WP2_TOWER["lon"],
                "height": None,
            }
        },
        "paper_waypoint_context": dict(PAPER_WP1_WP2_TOWER),
        "recommended_vision_targets": "tower",
    },
    "paper_moving_peloton": {
        "description": "Moving-obstacle paper case: bikers/peloton visible; towers and cows hidden.",
        "visible": {
            "towers": False,
            "cows": False,
            "bikers": True,
            "peloton": True,
        },
        "recommended_vision_targets": "biker",
    },
    "paper_all_obstacles": {
        "description": "Debug/reset profile: all paper obstacle groups visible.",
        "visible": {
            "towers": True,
            "cows": True,
            "bikers": True,
            "peloton": True,
        },
        "recommended_vision_targets": "biker,cow,tower",
    },
    "paper_no_obstacles": {
        "description": "Debug/control profile: all paper obstacle groups hidden.",
        "visible": {
            "towers": False,
            "cows": False,
            "bikers": False,
            "peloton": False,
        },
        "recommended_vision_targets": "",
    },
    "paper_static_cow": {
        "description": "Extra control case: cows visible; tower, bikers and peloton hidden.",
        "visible": {
            "towers": False,
            "cows": True,
            "bikers": False,
            "peloton": False,
        },
        "recommended_vision_targets": "cow",
    },
}


def _actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _all_actors():
    subsystem = _actor_subsystem()
    return list(subsystem.get_all_level_actors())


def _safe_text(value):
    if value is None:
        return ""
    return str(value)


def _actor_label(actor):
    try:
        return _safe_text(actor.get_actor_label())
    except Exception:
        return _safe_text(actor.get_name())


def _actor_folder(actor):
    try:
        folder = actor.get_folder_path()
    except Exception:
        return ""
    if folder is None:
        return ""
    return _safe_text(folder)


def _actor_class(actor):
    try:
        return _safe_text(actor.get_class().get_name())
    except Exception:
        return ""


def _actor_location(actor):
    try:
        loc = actor.get_actor_location()
    except Exception:
        return None
    return {
        "x": round(float(loc.x), 3),
        "y": round(float(loc.y), 3),
        "z": round(float(loc.z), 3),
    }


def _actor_llh(actor):
    try:
        components = actor.get_components_by_class(unreal.ActorComponent)
    except Exception:
        components = []
    for component in components:
        try:
            if component.get_class().get_name() != "CesiumGlobeAnchorComponent":
                continue
            llh = component.get_longitude_latitude_height()
            return {
                "lon": float(llh.x),
                "lat": float(llh.y),
                "height": float(llh.z),
            }
        except Exception:
            continue
    return None


def classify_actor(actor):
    label = _actor_label(actor)
    name = _safe_text(actor.get_name())
    class_name = _actor_class(actor)
    folder = _actor_folder(actor)
    text = " ".join([label, name, class_name, folder]).lower()
    folder_l = folder.lower()

    if "peloton" in text:
        return "peloton"
    if folder_l == "bikers" or "ciclista" in text or "biker" in text:
        return "bikers"
    if folder_l == "cows" or "cow" in text:
        return "cows"
    if folder_l == "towers" or "tower" in text or re.fullmatch(r"t\d+", label.lower()):
        return "towers"
    return None


def _component_set_visibility(component, visible):
    changed = []
    hidden = not visible
    if hasattr(component, "set_visibility"):
        try:
            component.set_visibility(visible, True)
            changed.append("set_visibility")
        except TypeError:
            component.set_visibility(visible)
            changed.append("set_visibility")
        except Exception as exc:
            changed.append("set_visibility_error:%s" % exc)

    if hasattr(component, "set_hidden_in_game"):
        try:
            component.set_hidden_in_game(hidden, True)
            changed.append("set_hidden_in_game")
        except TypeError:
            component.set_hidden_in_game(hidden)
            changed.append("set_hidden_in_game")
        except Exception as exc:
            changed.append("set_hidden_in_game_error:%s" % exc)

    for prop, value in (("visible", visible), ("hidden_in_game", hidden)):
        try:
            component.set_editor_property(prop, value)
            changed.append(prop)
        except Exception:
            pass
    return changed


def _actor_visibility_state(actor):
    state = {}
    for prop in ("hidden",):
        try:
            state[prop] = bool(actor.get_editor_property(prop))
        except Exception:
            state[prop] = None
    for method_name in ("is_temporarily_hidden_in_editor", "is_hidden_ed"):
        method = getattr(actor, method_name, None)
        if callable(method):
            try:
                state[method_name] = bool(method())
            except Exception:
                state[method_name] = None
    return state


def set_actor_paper_visibility(actor, visible, dry_run=False):
    hidden = not visible
    before = _actor_visibility_state(actor)
    component_count = 0
    component_changes = []

    if dry_run:
        return {
            "before": before,
            "after": before,
            "component_count": 0,
            "component_changes": [],
        }

    try:
        actor.modify()
    except Exception:
        pass

    if hasattr(actor, "set_actor_hidden_in_game"):
        actor.set_actor_hidden_in_game(hidden)
    else:
        actor.set_editor_property("hidden", hidden)

    if hasattr(actor, "set_is_temporarily_hidden_in_editor"):
        actor.set_is_temporarily_hidden_in_editor(hidden)

    try:
        actor.set_actor_tick_enabled(visible)
    except Exception:
        pass

    try:
        components = actor.get_components_by_class(unreal.ActorComponent)
    except Exception:
        components = []
    for component in components:
        changes = _component_set_visibility(component, visible)
        if changes:
            component_count += 1
            component_changes.append(
                {
                    "component": _safe_text(component.get_name()),
                    "class": _safe_text(component.get_class().get_name()),
                    "changes": changes,
                }
            )

    return {
        "before": before,
        "after": _actor_visibility_state(actor),
        "component_count": component_count,
        "component_changes": component_changes,
    }


def collect_scene_groups():
    groups = {group: [] for group in CONTROLLED_GROUPS}
    unclassified = []
    for actor in _all_actors():
        group = classify_actor(actor)
        row = {
            "label": _actor_label(actor),
            "name": _safe_text(actor.get_name()),
            "class": _actor_class(actor),
            "folder": _actor_folder(actor),
            "location": _actor_location(actor),
            "llh": _actor_llh(actor),
            "visibility": _actor_visibility_state(actor),
        }
        if group in groups:
            groups[group].append(row)
        elif group is None:
            unclassified.append(row)
    return groups, unclassified


def describe_scene(include_unclassified=False, include_actors=True):
    world = unreal.EditorLevelLibrary.get_editor_world()
    groups, unclassified = collect_scene_groups()
    visibility = {}
    for group, items in groups.items():
        hidden_count = 0
        for item in items:
            state = item.get("visibility", {})
            if state.get("hidden") or state.get("is_temporarily_hidden_in_editor") or state.get("is_hidden_ed"):
                hidden_count += 1
        visibility[group] = {
            "visible": len(items) - hidden_count,
            "hidden": hidden_count,
        }
    summary = {
        "world": world.get_name() if world else None,
        "controlled_counts": {group: len(items) for group, items in groups.items()},
        "controlled_visibility": visibility,
    }
    if include_actors:
        summary["controlled_groups"] = groups
    if include_unclassified:
        summary["unclassified_count"] = len(unclassified)
        if include_actors:
            summary["unclassified"] = unclassified
    return summary


def list_profiles():
    return {
        name: {
            "description": profile["description"],
            "visible": dict(profile["visible"]),
            "selected_visible": dict(profile.get("selected_visible", {})),
            "move_to_llh": dict(profile.get("move_to_llh", {})),
            "paper_waypoint_context": dict(profile.get("paper_waypoint_context", {})),
            "recommended_vision_targets": profile.get("recommended_vision_targets", ""),
        }
        for name, profile in sorted(PROFILES.items())
    }


def _move_actor_to_llh(actor, target, dry_run=False):
    before = {
        "location": _actor_location(actor),
        "llh": _actor_llh(actor),
    }
    height = target.get("height")
    if height is None and before.get("llh"):
        height = before["llh"].get("height")
    if height is None:
        height = 0.0
    planned = {
        "lon": float(target["lon"]),
        "lat": float(target["lat"]),
        "height": float(height),
    }
    if dry_run:
        return {
            "before": before,
            "planned": planned,
            "after": before,
            "moved": False,
        }

    try:
        actor.modify()
    except Exception:
        pass
    try:
        components = actor.get_components_by_class(unreal.ActorComponent)
    except Exception:
        components = []
    anchor = None
    for component in components:
        try:
            if component.get_class().get_name() == "CesiumGlobeAnchorComponent":
                anchor = component
                break
        except Exception:
            continue
    if anchor is None:
        raise RuntimeError("Actor %s has no CesiumGlobeAnchorComponent" % _actor_label(actor))
    anchor.move_to_longitude_latitude_height(
        unreal.Vector(float(planned["lon"]), float(planned["lat"]), float(planned["height"]))
    )
    return {
        "before": before,
        "planned": planned,
        "after": {
            "location": _actor_location(actor),
            "llh": _actor_llh(actor),
        },
        "moved": True,
    }


def apply_profile(profile_name, dry_run=False, include_details=True, include_actors=True):
    if profile_name not in PROFILES:
        raise ValueError("Unknown profile '%s'. Available: %s" % (profile_name, ", ".join(sorted(PROFILES))))

    profile = PROFILES[profile_name]
    groups, _ = collect_scene_groups()
    selected_visible = {
        group: set(str(item) for item in labels)
        for group, labels in profile.get("selected_visible", {}).items()
    }
    moves_by_label = profile.get("move_to_llh", {})
    result = {
        "profile": profile_name,
        "description": profile["description"],
        "dry_run": bool(dry_run),
        "recommended_vision_targets": profile.get("recommended_vision_targets", ""),
        "paper_waypoint_context": dict(profile.get("paper_waypoint_context", {})),
        "groups": {},
        "moves": {},
    }

    all_actors_by_name = {actor.get_name(): actor for actor in _all_actors()}

    for group in CONTROLLED_GROUPS:
        group_default_visible = bool(profile["visible"][group])
        group_rows = []
        for row in groups[group]:
            actor = all_actors_by_name.get(row["name"])
            if actor is None:
                continue
            visible = bool(group_default_visible or row["label"] in selected_visible.get(group, set()))
            change = set_actor_paper_visibility(actor, visible, dry_run=dry_run)
            move = None
            if row["label"] in moves_by_label:
                move = _move_actor_to_llh(actor, moves_by_label[row["label"]], dry_run=dry_run)
                result["moves"][row["label"]] = move
            if include_actors:
                group_rows.append(
                    {
                        "label": row["label"],
                        "name": row["name"],
                        "class": row["class"],
                        "folder": row["folder"],
                        "target_visible": visible,
                        "move": move,
                        "change": change if include_details else {
                            "before": change["before"],
                            "after": change["after"],
                            "component_count": change["component_count"],
                        },
                    }
                )
        result["groups"][group] = {
            "target_visible": group_default_visible,
            "selected_visible": sorted(selected_visible.get(group, set())),
            "count": len(groups[group]),
        }
        if include_actors:
            result["groups"][group]["actors"] = group_rows

    return result


def print_json(payload):
    print(json.dumps(payload, indent=2, sort_keys=True))


if globals().get("_PAPER_AUTO_RUN", False):
    action = globals().get("_PAPER_ACTION", "apply")
    if action == "list":
        print_json(list_profiles())
    elif action == "describe":
        print_json(
            describe_scene(
                include_unclassified=bool(globals().get("_PAPER_INCLUDE_UNCLASSIFIED", False)),
                include_actors=bool(globals().get("_PAPER_INCLUDE_ACTORS", True)),
            )
        )
    else:
        print_json(
            apply_profile(
                globals().get("_PAPER_PROFILE_NAME", "paper_all_obstacles"),
                dry_run=bool(globals().get("_PAPER_DRY_RUN", True)),
                include_details=bool(globals().get("_PAPER_INCLUDE_DETAILS", False)),
                include_actors=bool(globals().get("_PAPER_INCLUDE_ACTORS", True)),
            )
        )
