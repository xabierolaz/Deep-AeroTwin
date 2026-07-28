from __future__ import annotations

from typing import Any

SPECIFICITY = {
    "power_tower": 1.00,
    "farm_vehicle": 0.95,
    "two_wheeled_rider": 0.94,
    "articulated_vehicle": 0.90,
    "heavy_vehicle": 0.88,
    "bus": 0.86,
    "motorcycle": 0.82,
    "biker": 0.82,
    "built_structure": 0.81,
    "quadruped": 0.80,
    "cow": 0.79,
    "light_vehicle": 0.72,
    "vegetation": 0.66,
    "bush": 0.62,
    "generic_vehicle": 0.58,
    "uav_aircraft": 0.57,
    "industrial_vehicle": 0.56,
    "storage_container": 0.54,
    "safety_marker": 0.48,
    "agricultural_bale": 0.46,
    "person": 0.55,
    "bicycle": 0.50,
    "unknown": 0.20,
}

OBSERVATION_REFINER_VERSION = "SPPA-SEMANTIC-OBS-REFINE-0.1"

REVIEWED_FLIGHT_LABELS = {"biker", "cow", "tower", "person", "bicycle"}

VISUAL_ARTIFACT_CONTEXT_TOKENS = {
    "drawing",
    "icon",
    "image",
    "logo",
    "model",
    "painting",
    "photo",
    "picture",
    "poster",
    "print",
    "printed",
    "reflection",
    "shadow",
    "silhouette",
    "statue",
    "sticker",
    "toy",
}

NON_PERSON_EQUIPMENT_TOKENS = {
    "boot",
    "glove",
    "hardhat",
    "hat",
    "helmet",
    "shoe",
    "vest",
}


def _label(row: dict[str, Any]) -> str:
    return str(row.get("class_name") or row.get("detector_label") or "").strip().lower()


def _score(row: dict[str, Any], sppa_tag: str) -> float:
    return float(row.get("confidence") or 0.0) * float(SPECIFICITY.get(sppa_tag, 0.5))


def _finite_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out


def _metric_dims(metric_dims_m: Any) -> dict[str, float] | None:
    if not isinstance(metric_dims_m, dict):
        return None
    length = _finite_float(metric_dims_m.get("length", metric_dims_m.get("length_m")))
    width = _finite_float(metric_dims_m.get("width", metric_dims_m.get("width_m")))
    height = _finite_float(metric_dims_m.get("height", metric_dims_m.get("height_m")))
    if length is None or width is None or height is None:
        return None
    length, width = max(length, width), min(length, width)
    if length <= 0.0 or width <= 0.0 or height <= 0.0:
        return None
    return {"length": length, "width": width, "height": height}


def _candidate(
    row: dict[str, Any],
    *,
    sppa_tag: str,
    runtime_archetype_id: str,
    runtime_archetypes: list[str],
    rule: str,
    claim_status: str,
    conservative: bool = False,
) -> dict[str, Any]:
    label = str(row.get("class_name") or row.get("detector_label") or "")
    return {
        "detector_label": label,
        "confidence": float(row.get("confidence") or 0.0),
        "sppa_tag": sppa_tag,
        "runtime_archetype_id": runtime_archetype_id,
        "runtime_archetypes": runtime_archetypes,
        "normalization_rule": rule,
        "claim_status": claim_status,
        "conservative": conservative,
        "score": _score(row, sppa_tag),
    }


def refine_normalized_with_observation(
    normalized: dict[str, Any] | None,
    metric_dims_m: Any,
    uncertainty: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Refine a normalized detector family using metric observation evidence.

    This function intentionally refines only toward conservative runtime
    families. It never turns a weak label into an exact object identity; for
    example, a generic `vehicle` can become an `articulated_vehicle` proxy when
    the observed footprint is clearly long and heavy, but it is not called a
    tractor or tanker unless the detector/text evidence says so.
    """
    if normalized is None:
        return None
    out = dict(normalized)
    dims = _metric_dims(metric_dims_m)
    if dims is None:
        out["observation_refinement"] = {
            "version": OBSERVATION_REFINER_VERSION,
            "applied": False,
            "reason": "missing_metric_dims",
        }
        return out

    aspect = dims["length"] / max(0.01, dims["width"])
    label = str(out.get("detector_label") or "").strip().lower()
    tag = str(out.get("sppa_tag") or "").strip()
    runtime = str(out.get("runtime_archetype_id") or "").strip()
    shape_low_confidence = bool((uncertainty or {}).get("shape_low_confidence"))
    can_refine_generic_vehicle = (
        tag == "generic_vehicle"
        or runtime in {"heavy_vehicle", "generic_vehicle"}
        or label == "vehicle"
    )
    long_articulated = dims["length"] >= 9.0 and dims["height"] >= 2.4 and aspect >= 2.20
    very_long_low_conf = dims["length"] >= 11.0 and dims["height"] >= 2.4 and aspect >= 1.95 and shape_low_confidence
    if can_refine_generic_vehicle and (long_articulated or very_long_low_conf):
        previous = {
            "sppa_tag": out.get("sppa_tag"),
            "runtime_archetype_id": out.get("runtime_archetype_id"),
            "normalization_rule": out.get("normalization_rule"),
            "claim_status": out.get("claim_status"),
        }
        out.update(
            {
                "sppa_tag": "articulated_vehicle",
                "runtime_archetype_id": "articulated_vehicle",
                "runtime_archetypes": ["articulated_vehicle", "heavy_vehicle"],
                "normalization_rule": "metric_long_footprint_articulated_proxy",
                "claim_status": "geometry_refined_family",
                "conservative": True,
                "score": float(out.get("confidence") or 0.0) * SPECIFICITY["articulated_vehicle"],
                "observation_refinement": {
                    "version": OBSERVATION_REFINER_VERSION,
                    "applied": True,
                    "reason": "generic_vehicle_long_metric_footprint",
                    "previous": previous,
                    "dims_m": dims,
                    "aspect": round(aspect, 6),
                    "shape_low_confidence": shape_low_confidence,
                    "claim_boundary": (
                        "Metric evidence refines a weak vehicle family to a conservative articulated proxy; "
                        "it does not identify an exact tractor, truck model, or trailer type."
                    ),
                },
            }
        )
        return out

    out["observation_refinement"] = {
        "version": OBSERVATION_REFINER_VERSION,
        "applied": False,
        "reason": "family_or_metric_not_specific_enough",
        "dims_m": dims,
        "aspect": round(aspect, 6),
    }
    return out


def _forced_fallback_reason(tokens: set[str]) -> str | None:
    if tokens & VISUAL_ARTIFACT_CONTEXT_TOKENS:
        return "fallback_visual_artifact_context"
    if (tokens & NON_PERSON_EQUIPMENT_TOKENS) and not (tokens & {"person", "human", "pedestrian"}):
        return "fallback_object_part_or_equipment_context"
    return None


def normalize_single_detection(row: dict[str, Any]) -> dict[str, Any]:
    text = _label(row)
    tokens = set(text.replace("-", " ").replace("_", " ").split())
    fallback_reason = _forced_fallback_reason(tokens)
    if fallback_reason:
        return _candidate(
            row,
            sppa_tag="unknown",
            runtime_archetype_id="unknown",
            runtime_archetypes=["unknown"],
            rule=fallback_reason,
            claim_status="unknown",
            conservative=True,
        )

    if any(key in text for key in ("electric pylon", "power transmission tower", "transmission tower")):
        return _candidate(
            row,
            sppa_tag="power_tower",
            runtime_archetype_id="vertical_structure",
            runtime_archetypes=["tower", "vertical_structure"],
            rule="specific_power_infrastructure_label",
            claim_status="specific_family",
        )
    if tokens & {"tower", "pylon", "pole", "mast", "post", "sign", "antenna"}:
        return _candidate(
            row,
            sppa_tag="vertical_structure",
            runtime_archetype_id="vertical_structure",
            runtime_archetypes=["tower", "vertical_structure"],
            rule="vertical_structure_label",
            claim_status="family",
        )
    if tokens & {"building", "house", "shed", "barn", "warehouse", "bridge", "wall", "fence"} or "built structure" in text:
        return _candidate(
            row,
            sppa_tag="built_structure",
            runtime_archetype_id="built_structure",
            runtime_archetypes=["built_structure"],
            rule="built_structure_label",
            claim_status="family",
        )
    if "agricultural vehicle" in text or "farm tractor" in text or tokens & {"tractor", "harvester"}:
        return _candidate(
            row,
            sppa_tag="farm_vehicle",
            runtime_archetype_id="farm_vehicle",
            runtime_archetypes=["tractor", "farm_vehicle"],
            rule="farm_vehicle_label",
            claim_status="specific_family",
        )
    if tokens & {"crane"}:
        return _candidate(
            row,
            sppa_tag="vertical_structure",
            runtime_archetype_id="vertical_structure",
            runtime_archetypes=["tower", "vertical_structure"],
            rule="crane_as_vertical_structure_label",
            claim_status="family",
            conservative=True,
        )
    if tokens & {"trailer", "semi", "lorry", "truck", "excavator", "bulldozer", "loader"}:
        return _candidate(
            row,
            sppa_tag="heavy_vehicle",
            runtime_archetype_id="heavy_vehicle",
            runtime_archetypes=["truck", "heavy_vehicle"],
            rule="heavy_or_trailer_vehicle_label",
            claim_status="family",
            conservative=True,
        )
    if "fork lift" in text or tokens & {"forklift"}:
        return _candidate(
            row,
            sppa_tag="industrial_vehicle",
            runtime_archetype_id="forklift",
            runtime_archetypes=["forklift", "industrial_vehicle"],
            rule="open_label_forklift_verified_recipe_candidate",
            claim_status="open_label_family",
            conservative=True,
        )
    if "traffic cone" in text or "road cone" in text:
        return _candidate(
            row,
            sppa_tag="safety_marker",
            runtime_archetype_id="traffic_cone",
            runtime_archetypes=["traffic_cone", "safety_marker"],
            rule="open_label_traffic_cone_verified_recipe_candidate",
            claim_status="open_label_family",
            conservative=True,
        )
    if "water tank" in text or "storage tank" in text:
        return _candidate(
            row,
            sppa_tag="storage_container",
            runtime_archetype_id="water_tank",
            runtime_archetypes=["water_tank", "storage_container"],
            rule="open_label_water_tank_verified_recipe_candidate",
            claim_status="open_label_family",
            conservative=True,
        )
    if tokens & {"barrel", "drum"}:
        return _candidate(
            row,
            sppa_tag="storage_container",
            runtime_archetype_id="barrel",
            runtime_archetypes=["barrel", "storage_container"],
            rule="open_label_barrel_verified_recipe_candidate",
            claim_status="open_label_family",
            conservative=True,
        )
    if "shipping container" in text or "cargo container" in text or "freight container" in text:
        return _candidate(
            row,
            sppa_tag="storage_container",
            runtime_archetype_id="shipping_container",
            runtime_archetypes=["shipping_container", "storage_container"],
            rule="open_label_shipping_container_verified_recipe_candidate",
            claim_status="open_label_family",
            conservative=True,
        )
    if tokens & {"drone", "quadcopter", "uav"}:
        return _candidate(
            row,
            sppa_tag="uav_aircraft",
            runtime_archetype_id="quadcopter",
            runtime_archetypes=["quadcopter", "uav_aircraft"],
            rule="open_label_uav_aircraft_verified_recipe_candidate",
            claim_status="open_label_family",
            conservative=True,
        )
    if "hay bale" in text or "bale of hay" in text:
        return _candidate(
            row,
            sppa_tag="agricultural_bale",
            runtime_archetype_id="hay_bale",
            runtime_archetypes=["hay_bale", "agricultural_bale"],
            rule="open_label_hay_bale_verified_recipe_candidate",
            claim_status="open_label_family",
            conservative=True,
        )
    if tokens & {"bus", "coach", "minibus"}:
        return _candidate(
            row,
            sppa_tag="bus",
            runtime_archetype_id="bus",
            runtime_archetypes=["bus"],
            rule="bus_label",
            claim_status="specific_family",
        )
    if tokens & {"motorcycle", "motorbike", "moped", "scooter"}:
        return _candidate(
            row,
            sppa_tag="motorcycle",
            runtime_archetype_id="motorcycle",
            runtime_archetypes=["motorcycle"],
            rule="two_wheel_motor_vehicle_label",
            claim_status="family",
        )
    if tokens & {"biker", "cyclist", "rider"}:
        return _candidate(
            row,
            sppa_tag="two_wheeled_rider",
            runtime_archetype_id="biker",
            runtime_archetypes=["biker"],
            rule="rider_label",
            claim_status="specific_family",
        )
    if tokens & {"bicycle", "bike"}:
        return _candidate(
            row,
            sppa_tag="bicycle",
            runtime_archetype_id="bicycle",
            runtime_archetypes=["bicycle"],
            rule="bicycle_label",
            claim_status="component",
        )
    if tokens & {"cow", "cattle", "vaca", "bull"}:
        return _candidate(
            row,
            sppa_tag="cow",
            runtime_archetype_id="quadruped",
            runtime_archetypes=["cow", "quadruped"],
            rule="cow_or_cattle_label",
            claim_status="specific_family",
        )
    if tokens & {"tree", "plant", "vegetation", "forest", "canopy", "trunk"}:
        return _candidate(
            row,
            sppa_tag="vegetation",
            runtime_archetype_id="vegetation",
            runtime_archetypes=["tree", "vegetation"],
            rule="vegetation_label",
            claim_status="family",
        )
    if tokens & {"bush", "shrub", "hedge"}:
        return _candidate(
            row,
            sppa_tag="bush",
            runtime_archetype_id="bush",
            runtime_archetypes=["bush", "vegetation"],
            rule="bush_label",
            claim_status="family",
        )
    if tokens & {"horse", "sheep", "goat", "deer", "dog", "animal"}:
        return _candidate(
            row,
            sppa_tag="quadruped",
            runtime_archetype_id="quadruped",
            runtime_archetypes=["cow", "quadruped"],
            rule="quadruped_label",
            claim_status="family",
        )
    if tokens & {"car", "suv", "taxi"}:
        return _candidate(
            row,
            sppa_tag="light_vehicle",
            runtime_archetype_id="light_vehicle",
            runtime_archetypes=["car", "light_vehicle"],
            rule="specific_light_vehicle_label",
            claim_status="family",
        )
    if text == "vehicle" or tokens == {"vehicle"}:
        return _candidate(
            row,
            sppa_tag="generic_vehicle",
            runtime_archetype_id="heavy_vehicle",
            runtime_archetypes=["truck", "heavy_vehicle"],
            rule="generic_vehicle_conservative_proxy",
            claim_status="generic_family",
            conservative=True,
        )
    if "vehicle" in tokens:
        return _candidate(
            row,
            sppa_tag="generic_vehicle",
            runtime_archetype_id="heavy_vehicle",
            runtime_archetypes=["truck", "heavy_vehicle"],
            rule="compound_vehicle_conservative_proxy",
            claim_status="generic_family",
            conservative=True,
        )
    if tokens & {"person", "pedestrian", "human"}:
        return _candidate(
            row,
            sppa_tag="person",
            runtime_archetype_id="person",
            runtime_archetypes=["person"],
            rule="person_label",
            claim_status="family",
        )
    return _candidate(
        row,
        sppa_tag="unknown",
        runtime_archetype_id="unknown",
        runtime_archetypes=["unknown"],
        rule="fallback_unknown_label",
        claim_status="unknown",
        conservative=True,
    )


def normalize_detection_set(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None

    candidates = [normalize_single_detection(row) for row in rows]
    person = max((c for c in candidates if c["sppa_tag"] == "person"), key=lambda c: c["confidence"], default=None)
    two_wheel = max(
        (c for c in candidates if c["sppa_tag"] in {"motorcycle", "bicycle", "two_wheeled_rider"}),
        key=lambda c: c["confidence"],
        default=None,
    )
    if person and two_wheel:
        combo_conf = max(float(person["confidence"]), float(two_wheel["confidence"]))
        detector_label = f"{person['detector_label']} + {two_wheel['detector_label']}"
        composed = {
            "detector_label": detector_label,
            "confidence": combo_conf,
            "sppa_tag": "two_wheeled_rider",
            "runtime_archetype_id": "biker",
            "runtime_archetypes": ["biker"],
            "normalization_rule": "composed_person_plus_two_wheel",
            "claim_status": "specific_family_composed",
            "conservative": False,
            "score": combo_conf * SPECIFICITY["two_wheeled_rider"],
            "component_evidence": [person, two_wheel],
        }
        candidates.append(composed)

    priority = {
        "power_tower": 8,
        "farm_vehicle": 7,
        "two_wheeled_rider": 7,
        "heavy_vehicle": 6,
        "bus": 6,
        "uav_aircraft": 5,
        "industrial_vehicle": 5,
        "generic_vehicle": 5,
        "built_structure": 5,
        "storage_container": 4,
        "motorcycle": 4,
        "biker": 4,
        "quadruped": 4,
        "cow": 4,
        "vegetation": 4,
        "bush": 4,
        "safety_marker": 3,
        "agricultural_bale": 3,
        "light_vehicle": 3,
        "bicycle": 3,
        "person": 2,
        "unknown": 0,
    }
    selected = max(
        candidates,
        key=lambda c: (
            priority.get(str(c["sppa_tag"]), 0),
            float(c["score"]),
            float(c["confidence"]),
        ),
    )
    selected = dict(selected)
    selected["candidate_count"] = len(candidates)
    ranked = sorted(
        candidates,
        key=lambda c: (priority.get(str(c["sppa_tag"]), 0), float(c["score"]), float(c["confidence"])),
        reverse=True,
    )[:8]
    selected["normalization_candidates"] = [
        {k: v for k, v in candidate.items() if k not in {"normalization_candidates"}}
        for candidate in ranked
    ]
    return selected


def runtime_label_from_normalized(normalized: dict[str, Any], canonical_label: str | None = None) -> str:
    canonical = str(canonical_label or "").strip()
    if canonical.lower() in REVIEWED_FLIGHT_LABELS:
        return canonical
    runtime = str(normalized.get("runtime_archetype_id") or "").strip()
    if runtime:
        return runtime
    tag = str(normalized.get("sppa_tag") or "").strip()
    return tag or canonical or "unknown"


def normalize_runtime_detection(row: dict[str, Any], canonical_label: str | None = None) -> dict[str, Any]:
    normalized = normalize_single_detection(row)
    out = dict(normalized)
    out["runtime_label"] = runtime_label_from_normalized(normalized, canonical_label)
    if canonical_label:
        out["canonical_label"] = str(canonical_label)
    return out
