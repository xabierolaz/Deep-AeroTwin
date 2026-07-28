from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Optional

try:
    import cv2
    import numpy as np
except Exception:  # pragma: no cover - exercised on minimal deployments.
    cv2 = None
    np = None

SILHOUETTE_SCHEMA = "SPPA-SILHOUETTE-0.1"


def finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def normalize_bbox_xyxy(bbox: Any) -> Optional[dict[str, float]]:
    if isinstance(bbox, dict):
        x1 = bbox.get("x1", bbox.get("left"))
        y1 = bbox.get("y1", bbox.get("top"))
        x2 = bbox.get("x2", bbox.get("right"))
        y2 = bbox.get("y2", bbox.get("bottom"))
    else:
        try:
            x1, y1, x2, y2 = bbox
        except Exception:
            return None
    vals = [finite_float(v) for v in (x1, y1, x2, y2)]
    if any(v is None for v in vals):
        return None
    x1f, y1f, x2f, y2f = [float(v) for v in vals]
    if x2f <= x1f or y2f <= y1f:
        return None
    return {"x1": x1f, "y1": y1f, "x2": x2f, "y2": y2f, "w": x2f - x1f, "h": y2f - y1f}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def polygon_area_px2(points: list[list[float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def _clip_bbox_to_image(bbox: dict[str, float], width: int, height: int) -> Optional[tuple[int, int, int, int]]:
    x1 = int(math.floor(clamp(bbox["x1"], 0.0, float(width - 1))))
    y1 = int(math.floor(clamp(bbox["y1"], 0.0, float(height - 1))))
    x2 = int(math.ceil(clamp(bbox["x2"], 0.0, float(width))))
    y2 = int(math.ceil(clamp(bbox["y2"], 0.0, float(height))))
    if x2 <= x1 + 1 or y2 <= y1 + 1:
        return None
    return x1, y1, x2, y2


def _expected_fraction(expected_mask_area_px: Optional[float], bbox_area_px: float) -> float:
    if expected_mask_area_px is None or expected_mask_area_px <= 0.0 or bbox_area_px <= 0.0:
        return 0.35
    return clamp(float(expected_mask_area_px) / float(bbox_area_px), 0.03, 0.85)


def _contrast_candidate(image, bbox_i: tuple[int, int, int, int], expected_fraction: float):
    x1, y1, x2, y2 = bbox_i
    h, w = image.shape[:2]
    pad = max(6, int(round(0.18 * max(x2 - x1, y2 - y1))))
    px1 = max(0, x1 - pad)
    py1 = max(0, y1 - pad)
    px2 = min(w, x2 + pad)
    py2 = min(h, y2 + pad)
    crop = image[py1:py2, px1:px2]
    if crop.size == 0:
        return None

    inner = (x1 - px1, y1 - py1, x2 - px1, y2 - py1)
    ix1, iy1, ix2, iy2 = inner
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB).astype("float32")
    bg_mask = np.ones(crop.shape[:2], dtype=bool)
    bg_mask[iy1:iy2, ix1:ix2] = False
    if int(bg_mask.sum()) < 16:
        bg_mask = np.zeros(crop.shape[:2], dtype=bool)
        bg_mask[0, :] = True
        bg_mask[-1, :] = True
        bg_mask[:, 0] = True
        bg_mask[:, -1] = True
    bg = np.median(lab[bg_mask], axis=0)
    score = np.linalg.norm(lab - bg.reshape((1, 1, 3)), axis=2)
    inside_score = score[iy1:iy2, ix1:ix2]
    if inside_score.size == 0:
        return None
    threshold = float(np.quantile(inside_score, 1.0 - expected_fraction))
    binary = (inside_score >= threshold).astype("uint8") * 255
    return _clean_binary(binary, "contrast_expected_area", x1, y1)


def _grabcut_candidate(image, bbox_i: tuple[int, int, int, int]):
    x1, y1, x2, y2 = bbox_i
    if x2 <= x1 + 3 or y2 <= y1 + 3:
        return None
    mask = np.zeros(image.shape[:2], np.uint8)
    rect = (x1, y1, x2 - x1, y2 - y1)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(image, mask, rect, bgd_model, fgd_model, 4, cv2.GC_INIT_WITH_RECT)
    except Exception:
        return None
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")
    return _clean_binary(fg[y1:y2, x1:x2], "grabcut_rect", x1, y1)


def _clean_binary(binary, method: str, offset_x: int, offset_y: int):
    if binary is None or binary.size == 0:
        return None
    kernel = np.ones((3, 3), np.uint8)
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel, iterations=1)
    area = int((cleaned > 0).sum())
    if area <= 2:
        return None
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    all_points = np.concatenate(contours, axis=0)
    if len(all_points) < 3:
        return None
    hull = cv2.convexHull(all_points)
    epsilon = max(1.0, 0.0125 * cv2.arcLength(hull, True))
    approx = cv2.approxPolyDP(hull, epsilon, True)
    points = []
    for item in approx.reshape((-1, 2)):
        points.append([round(float(item[0] + offset_x), 6), round(float(item[1] + offset_y), 6)])
    if len(points) < 3:
        return None
    return {
        "method": method,
        "polygon": points,
        "area_px2": float(area),
        "hull_area_px2": polygon_area_px2(points),
        "point_count": len(points),
    }


def _fallback_polygon(
    bbox: dict[str, float],
    expected_mask_area_px: Optional[float],
    label: Optional[str],
) -> dict[str, Any]:
    x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
    w, h = bbox["w"], bbox["h"]
    bbox_area = max(1.0, w * h)
    desired_area = float(expected_mask_area_px or (0.35 * bbox_area))
    label_text = str(label or "").lower()

    if "tower" in label_text or "pylon" in label_text:
        poly_h = 0.96 * h
        poly_w = clamp(desired_area / max(poly_h, 1.0), 0.08 * w, 0.75 * w)
    else:
        poly_w = 0.92 * w
        poly_h = clamp(desired_area / max(poly_w, 1.0), 0.12 * h, 0.85 * h)

    cx = (x1 + x2) * 0.5
    cy = (y1 + y2) * 0.5
    left = cx - poly_w * 0.5
    right = cx + poly_w * 0.5
    top = cy - poly_h * 0.5
    bottom = cy + poly_h * 0.5
    points = [
        [round(left, 6), round(top, 6)],
        [round(right, 6), round(top, 6)],
        [round(right, 6), round(bottom, 6)],
        [round(left, 6), round(bottom, 6)],
    ]
    return {
        "method": "area_matched_bbox_silhouette_proxy",
        "polygon": points,
        "area_px2": polygon_area_px2(points),
        "hull_area_px2": polygon_area_px2(points),
        "point_count": len(points),
    }


def _score_candidate(candidate: dict[str, Any], expected_mask_area_px: Optional[float], bbox_area_px: float) -> float:
    area = float(candidate.get("area_px2") or 0.0)
    hull_area = float(candidate.get("hull_area_px2") or area or 1.0)
    expected = float(expected_mask_area_px or 0.0)
    if expected > 0.0:
        area_match = 1.0 - min(1.0, abs(area - expected) / max(area, expected, 1.0))
    else:
        frac = area / max(bbox_area_px, 1.0)
        area_match = 1.0 - min(1.0, abs(frac - 0.35) / 0.35)
    fill = clamp(area / max(hull_area, 1.0), 0.0, 1.0)
    compactness = clamp(float(candidate.get("point_count") or 0) / 8.0, 0.0, 1.0)
    return round(clamp(0.50 * area_match + 0.25 * fill + 0.25 * compactness, 0.0, 1.0), 6)


def build_image_silhouette_proxy(
    *,
    image_path: str | Path,
    bbox: Any,
    expected_mask_area_px: Optional[float] = None,
    label: Optional[str] = None,
    max_points: int = 64,
) -> dict[str, Any]:
    """Derive a declared silhouette proxy from the image crop around a bbox.

    The output is evidence, not ground truth. It is suitable for SPPA footprint
    plumbing tests and should be reported as image-derived proxy segmentation.
    """
    bbox_xyxy = normalize_bbox_xyxy(bbox)
    if bbox_xyxy is None:
        return {
            "schema": SILHOUETTE_SCHEMA,
            "status": "failed",
            "failure": "invalid_bbox",
            "source": "no_silhouette_available",
            "polygon": None,
        }
    if cv2 is None or np is None:
        candidate = _fallback_polygon(bbox_xyxy, expected_mask_area_px, label)
        quality = _score_candidate(candidate, expected_mask_area_px, bbox_xyxy["w"] * bbox_xyxy["h"])
        return _build_payload(candidate, bbox_xyxy, expected_mask_area_px, quality, "fallback_without_cv2")

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        candidate = _fallback_polygon(bbox_xyxy, expected_mask_area_px, label)
        quality = _score_candidate(candidate, expected_mask_area_px, bbox_xyxy["w"] * bbox_xyxy["h"])
        return _build_payload(candidate, bbox_xyxy, expected_mask_area_px, quality, "fallback_image_unreadable")

    height, width = image.shape[:2]
    bbox_i = _clip_bbox_to_image(bbox_xyxy, width, height)
    if bbox_i is None:
        candidate = _fallback_polygon(bbox_xyxy, expected_mask_area_px, label)
        quality = _score_candidate(candidate, expected_mask_area_px, bbox_xyxy["w"] * bbox_xyxy["h"])
        return _build_payload(candidate, bbox_xyxy, expected_mask_area_px, quality, "fallback_bbox_outside_image")

    bbox_area = max(1.0, float((bbox_i[2] - bbox_i[0]) * (bbox_i[3] - bbox_i[1])))
    fraction = _expected_fraction(expected_mask_area_px, bbox_area)
    candidates = [
        _contrast_candidate(image, bbox_i, fraction),
        _grabcut_candidate(image, bbox_i),
    ]
    valid = [candidate for candidate in candidates if candidate is not None]
    if not valid:
        candidate = _fallback_polygon(bbox_xyxy, expected_mask_area_px, label)
        quality = _score_candidate(candidate, expected_mask_area_px, bbox_xyxy["w"] * bbox_xyxy["h"])
        return _build_payload(candidate, bbox_xyxy, expected_mask_area_px, quality, "fallback_segmentation_failed")

    scored = [
        (_score_candidate(candidate, expected_mask_area_px, bbox_area), candidate)
        for candidate in valid
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    quality, candidate = scored[0]
    polygon = candidate.get("polygon") or []
    if len(polygon) > max_points:
        step = max(1, int(math.ceil(len(polygon) / float(max_points))))
        candidate = dict(candidate)
        candidate["polygon"] = polygon[::step]
        candidate["point_count"] = len(candidate["polygon"])
    return _build_payload(candidate, bbox_xyxy, expected_mask_area_px, quality, "image_derived_silhouette_proxy")


def _build_payload(
    candidate: dict[str, Any],
    bbox_xyxy: dict[str, float],
    expected_mask_area_px: Optional[float],
    quality_score: float,
    source: str,
) -> dict[str, Any]:
    area = float(candidate.get("area_px2") or polygon_area_px2(candidate.get("polygon") or []))
    expected = finite_float(expected_mask_area_px)
    return {
        "schema": SILHOUETTE_SCHEMA,
        "status": "ok",
        "source": source,
        "method": candidate.get("method"),
        "polygon": candidate.get("polygon"),
        "point_count": int(candidate.get("point_count") or len(candidate.get("polygon") or [])),
        "area_px2": area,
        "hull_area_px2": candidate.get("hull_area_px2"),
        "expected_mask_area_px": expected,
        "area_ratio_to_expected": None if not expected else round(area / expected, 6),
        "bbox_xyxy": bbox_xyxy,
        "bbox_area_px2": round(float(bbox_xyxy["w"] * bbox_xyxy["h"]), 6),
        "quality_score": float(quality_score),
        "claim_boundary": (
            "This is an image-derived silhouette proxy inside a detector/review bbox, not a ground-truth mask "
            "and not necessarily the native detector segmentation."
        ),
    }
