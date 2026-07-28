from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw

from probe_agnostic_silhouette_parts import (
    DEFAULT_PAPER_RESULTS,
    DEFAULT_REPLAY_JSON,
    ROOT,
    analyze_row as analyze_mask_only_row,
    crop_box,
    detection_polygons,
    fit_tile,
    labeled_tile,
    load_font,
    rasterize_polygons,
    render_mask_tile,
    render_proposal_tile,
    root_path,
)

DEFAULT_RUN_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_agnostic_shape_fitting" / "20260704_real_image_cues"
DEFAULT_FIGURE = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_agnostic_mask_vs_image_cues_grid.png"


def local_bbox(row: dict[str, Any], crop: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    left, top, _, _ = crop
    x1, y1, x2, y2 = [float(v) for v in row.get("bbox_xyxy") or [0, 0, 0, 0]]
    return (
        int(round(x1 - left)),
        int(round(y1 - top)),
        int(round(x2 - left)),
        int(round(y2 - top)),
    )


def make_roi(mask: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    height, width = mask.shape[:2]
    roi = np.zeros((height, width), dtype=np.uint8)
    bx1, by1, bx2, by2 = bbox
    bx1, by1 = max(0, bx1), max(0, by1)
    bx2, by2 = min(width, bx2), min(height, by2)
    if bx2 > bx1 and by2 > by1:
        roi[by1:by2, bx1:bx2] = 255
    if np.any(mask > 0):
        radius = max(4, int(round(min(height, width) * 0.055)))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
        dilated = cv2.dilate((mask > 0).astype(np.uint8) * 255, kernel)
        roi = cv2.bitwise_or(roi, dilated)
    return roi


def edge_map(crop_img: Image.Image, roi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rgb = np.array(crop_img.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    equalized = clahe.apply(gray)
    blurred = cv2.GaussianBlur(equalized, (3, 3), 0)
    roi_pixels = blurred[roi > 0]
    median = float(np.median(roi_pixels)) if roi_pixels.size else float(np.median(blurred))
    lower = max(12, int(0.55 * median))
    upper = min(230, max(lower + 20, int(1.35 * median)))
    edges = cv2.Canny(blurred, lower, upper)
    edges = cv2.bitwise_and(edges, roi)
    return gray, edges


def circle_edge_metrics(edges: np.ndarray, cx: float, cy: float, radius: float, bins_count: int = 16) -> dict[str, float]:
    samples = max(32, int(round(2.0 * math.pi * max(4.0, radius))))
    hits = 0
    bins = [0 for _ in range(bins_count)]
    height, width = edges.shape[:2]
    for idx in range(samples):
        angle = 2.0 * math.pi * idx / samples
        x = int(round(cx + math.cos(angle) * radius))
        y = int(round(cy + math.sin(angle) * radius))
        if 1 <= x < width - 1 and 1 <= y < height - 1:
            if np.any(edges[y - 1 : y + 2, x - 1 : x + 2] > 0):
                hits += 1
                bins[min(bins_count - 1, int(idx * bins_count / samples))] += 1
    max_empty_run = 0
    current_empty_run = 0
    for value in bins + bins:
        if value == 0:
            current_empty_run += 1
            max_empty_run = max(max_empty_run, current_empty_run)
        else:
            current_empty_run = 0
    max_empty_run = min(max_empty_run, bins_count)
    return {
        "support": round(hits / float(samples), 4),
        "angular_coverage": round(sum(1 for value in bins if value > 0) / float(bins_count), 4),
        "max_empty_arc_fraction": round(max_empty_run / float(bins_count), 4),
    }


def circle_edge_support(edges: np.ndarray, cx: float, cy: float, radius: float) -> float:
    return circle_edge_metrics(edges, cx, cy, radius)["support"]


def dedupe_circles(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda item: item["score"], reverse=True):
        cx, cy = candidate["center_xy"]
        radius = candidate["radius_px"]
        duplicate = False
        for other in kept:
            ox, oy = other["center_xy"]
            distance = math.hypot(cx - ox, cy - oy)
            if distance < max(radius, other["radius_px"]) * 0.55:
                duplicate = True
                break
        if not duplicate:
            kept.append(candidate)
    return kept[:8]


def mirror_circle_candidates(candidates: list[dict[str, Any]], width: int) -> list[dict[str, Any]]:
    mirrored: list[dict[str, Any]] = []
    for candidate in candidates:
        item = dict(candidate)
        cx, cy = [float(v) for v in item["center_xy"]]
        item["center_xy"] = [round(float(width - 1) - cx, 3), round(cy, 3)]
        mirrored.append(item)
    return mirrored


def hough_circles(gray: np.ndarray, edges: np.ndarray, roi: np.ndarray) -> list[dict[str, Any]]:
    height, width = gray.shape[:2]
    shortest = max(1, min(height, width))
    scale = 2 if shortest < 180 else 1
    work = gray.copy()
    fill = int(np.median(gray[roi > 0])) if np.any(roi > 0) else int(np.median(gray))
    work[roi == 0] = fill
    if scale > 1:
        work = cv2.resize(work, (width * scale, height * scale), interpolation=cv2.INTER_CUBIC)
    work = cv2.GaussianBlur(work, (5, 5), 0)
    min_radius = max(3, int(round(shortest * 0.035 * scale)))
    max_radius = max(min_radius + 2, int(round(shortest * 0.28 * scale)))
    min_dist = max(8, int(round(shortest * 0.14 * scale)))
    candidates: list[dict[str, Any]] = []
    for param2 in (18, 14, 10, 7):
        circles = cv2.HoughCircles(
            work,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=min_dist,
            param1=85,
            param2=param2,
            minRadius=min_radius,
            maxRadius=max_radius,
        )
        if circles is None:
            continue
        for raw in np.squeeze(circles, axis=0):
            cx = float(raw[0]) / scale
            cy = float(raw[1]) / scale
            radius = float(raw[2]) / scale
            ix, iy = int(round(cx)), int(round(cy))
            if not (0 <= ix < width and 0 <= iy < height):
                continue
            if roi[iy, ix] == 0:
                continue
            metrics = circle_edge_metrics(edges, cx, cy, radius)
            support = metrics["support"]
            if support < 0.08:
                continue
            candidates.append(
                {
                    "method": "hough_circle",
                    "center_xy": [round(cx, 3), round(cy, 3)],
                    "radius_px": round(radius, 3),
                    "score": round(float(support), 4),
                    "angular_coverage": metrics["angular_coverage"],
                    "max_empty_arc_fraction": metrics["max_empty_arc_fraction"],
                }
            )
        if candidates:
            break
    return dedupe_circles(candidates)


def circle_intensity_views(gray: np.ndarray) -> list[tuple[str, np.ndarray]]:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    normalized = cv2.normalize(clahe, None, 0, 255, cv2.NORM_MINMAX)
    normalized_blur = cv2.GaussianBlur(normalized, (3, 3), 0)
    return [
        ("raw", gray),
        ("clahe", clahe),
        ("clahe_norm", normalized),
        ("clahe_norm_blur", normalized_blur),
    ]


def contour_round_candidates(edges: np.ndarray, roi: np.ndarray) -> list[dict[str, Any]]:
    contours, _ = cv2.findContours((edges > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    height, width = edges.shape[:2]
    area_limit = width * height
    candidates: list[dict[str, Any]] = []
    for contour in contours:
        if len(contour) < 8:
            continue
        area = float(cv2.contourArea(contour))
        perim = float(cv2.arcLength(contour, True))
        if area < max(8.0, area_limit * 0.0009) or perim <= 0:
            continue
        circularity = 4.0 * math.pi * area / (perim * perim)
        x, y, w, h = cv2.boundingRect(contour)
        compactness = min(w / float(max(1, h)), h / float(max(1, w)))
        if circularity < 0.18 or compactness < 0.42:
            continue
        (cx, cy), radius = cv2.minEnclosingCircle(contour)
        ix, iy = int(round(cx)), int(round(cy))
        if not (0 <= ix < width and 0 <= iy < height) or roi[iy, ix] == 0:
            continue
        metrics = circle_edge_metrics(edges, cx, cy, radius)
        support = metrics["support"]
        if support < 0.06:
            continue
        candidates.append(
            {
                "method": "edge_contour_roundness",
                "center_xy": [round(float(cx), 3), round(float(cy), 3)],
                "radius_px": round(float(radius), 3),
                "score": round(max(float(circularity), support), 4),
                "circularity": round(float(circularity), 4),
                "compactness": round(float(compactness), 4),
                "angular_coverage": metrics["angular_coverage"],
                "max_empty_arc_fraction": metrics["max_empty_arc_fraction"],
            }
        )
    return dedupe_circles(candidates)


def round_candidates(gray: np.ndarray, edges: np.ndarray, roi: np.ndarray) -> list[dict[str, Any]]:
    height, width = gray.shape[:2]
    mirror_edges = cv2.flip(edges, 1)
    mirror_roi = cv2.flip(roi, 1)
    hough_candidates: list[dict[str, Any]] = []
    for view_name, view_gray in circle_intensity_views(gray):
        direct = hough_circles(view_gray, edges, roi)
        mirror_gray = cv2.flip(view_gray, 1)
        mirrored = mirror_circle_candidates(hough_circles(mirror_gray, mirror_edges, mirror_roi), width)
        for candidate in direct:
            item = dict(candidate)
            item["intensity_view"] = view_name
            item["method"] = f"{candidate['method']}:{view_name}"
            hough_candidates.append(item)
        for candidate in mirrored:
            item = dict(candidate)
            item["intensity_view"] = f"{view_name}_mirror"
            item["method"] = f"{candidate['method']}:{view_name}_mirror"
            hough_candidates.append(item)
    hough = dedupe_circles(hough_candidates)
    if len(hough) >= 2:
        return hough
    contour = contour_round_candidates(edges, roi) + mirror_circle_candidates(
        contour_round_candidates(mirror_edges, mirror_roi), width
    )
    return dedupe_circles(hough + contour)


def mirror_line_candidates(candidates: list[dict[str, Any]], width: int) -> list[dict[str, Any]]:
    mirrored: list[dict[str, Any]] = []
    for candidate in candidates:
        x1, y1, x2, y2 = [int(v) for v in candidate["xyxy"]]
        mx1 = int(round(float(width - 1) - float(x1)))
        mx2 = int(round(float(width - 1) - float(x2)))
        length = math.hypot(mx2 - mx1, y2 - y1)
        angle = math.degrees(math.atan2(y2 - y1, mx2 - mx1))
        mirrored.append(
            {
                "xyxy": [mx1, y1, mx2, y2],
                "length_px": round(float(length), 3),
                "angle_deg": round(float(angle), 3),
            }
        )
    return mirrored


def dedupe_lines(candidates: list[dict[str, Any]], width: int, height: int) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    distance_tol = max(3.0, min(width, height) * 0.035)
    for candidate in sorted(candidates, key=lambda item: item["length_px"], reverse=True):
        x1, y1, x2, y2 = [float(v) for v in candidate["xyxy"]]
        mid_x = (x1 + x2) * 0.5
        mid_y = (y1 + y2) * 0.5
        duplicate = False
        for other in kept:
            ox1, oy1, ox2, oy2 = [float(v) for v in other["xyxy"]]
            other_mid_x = (ox1 + ox2) * 0.5
            other_mid_y = (oy1 + oy2) * 0.5
            angle_delta = angle_delta_deg(float(candidate["angle_deg"]), float(other["angle_deg"]))
            length_ratio = abs(float(candidate["length_px"]) - float(other["length_px"])) / max(
                1.0, float(other["length_px"])
            )
            if math.hypot(mid_x - other_mid_x, mid_y - other_mid_y) <= distance_tol and angle_delta <= 7.5 and length_ratio <= 0.25:
                duplicate = True
                break
        if not duplicate:
            kept.append(candidate)
        if len(kept) >= 16:
            break
    return kept


def line_candidates(edges: np.ndarray) -> list[dict[str, Any]]:
    height, width = edges.shape[:2]
    shortest = max(1, min(height, width))
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180.0,
        threshold=max(8, int(round(shortest * 0.08))),
        minLineLength=max(8, int(round(shortest * 0.16))),
        maxLineGap=max(3, int(round(shortest * 0.045))),
    )
    candidates: list[dict[str, Any]] = []
    if lines is None:
        return candidates
    for raw in np.squeeze(lines, axis=1):
        x1, y1, x2, y2 = [int(v) for v in raw]
        length = math.hypot(x2 - x1, y2 - y1)
        if length < shortest * 0.14:
            continue
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        candidates.append(
            {
                "xyxy": [x1, y1, x2, y2],
                "length_px": round(float(length), 3),
                "angle_deg": round(float(angle), 3),
            }
        )
    return sorted(candidates, key=lambda item: item["length_px"], reverse=True)[:16]


def symmetric_line_candidates(edges: np.ndarray) -> list[dict[str, Any]]:
    height, width = edges.shape[:2]
    direct = line_candidates(edges)
    mirrored = mirror_line_candidates(line_candidates(cv2.flip(edges, 1)), width)
    return dedupe_lines(direct + mirrored, width, height)


def _line_record(x1: float, y1: float, x2: float, y2: float, source: str) -> dict[str, Any] | None:
    length = math.hypot(float(x2) - float(x1), float(y2) - float(y1))
    if length <= 1.0:
        return None
    angle = math.degrees(math.atan2(float(y2) - float(y1), float(x2) - float(x1)))
    return {
        "xyxy": [int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))],
        "length_px": round(float(length), 3),
        "angle_deg": round(float(angle), 3),
        "source": source,
    }


def canonical_geometry_lines(mask: np.ndarray, bbox: tuple[int, int, int, int], mask_pca: dict[str, Any]) -> list[dict[str, Any]]:
    height, width = mask.shape[:2]
    bx1, by1, bx2, by2 = bbox
    bx1, by1 = max(0, bx1), max(0, by1)
    bx2, by2 = min(width - 1, bx2), min(height - 1, by2)
    if bx2 <= bx1 or by2 <= by1:
        return []
    cx = (bx1 + bx2) * 0.5
    cy = (by1 + by2) * 0.5
    bbox_w = max(1.0, float(bx2 - bx1))
    bbox_h = max(1.0, float(by2 - by1))
    raw: list[dict[str, Any] | None] = [
        _line_record(bx1, by1, bx2, by1, "bbox_top_edge"),
        _line_record(bx1, by2, bx2, by2, "bbox_bottom_edge"),
        _line_record(bx1, by1, bx1, by2, "bbox_left_edge"),
        _line_record(bx2, by1, bx2, by2, "bbox_right_edge"),
        _line_record(bx1, by1, bx2, by2, "bbox_diagonal_down"),
        _line_record(bx1, by2, bx2, by1, "bbox_diagonal_up"),
        _line_record(bx1, cy, bx2, cy, "bbox_center_horizontal"),
        _line_record(cx, by1, cx, by2, "bbox_center_vertical"),
    ]
    centroid = mask_pca.get("centroid_xy") if isinstance(mask_pca, dict) else None
    angle = mask_pca.get("angle_deg") if isinstance(mask_pca, dict) else None
    if isinstance(centroid, list) and len(centroid) == 2 and angle is not None:
        pcx, pcy = float(centroid[0]), float(centroid[1])
        major = max(bbox_w, bbox_h) * 0.52
        minor = min(bbox_w, bbox_h) * 0.40
        theta = math.radians(float(angle))
        dx = math.cos(theta) * major
        dy = math.sin(theta) * major
        pdx = math.cos(theta + math.pi * 0.5) * minor
        pdy = math.sin(theta + math.pi * 0.5) * minor
        raw.extend(
            [
                _line_record(pcx - dx, pcy - dy, pcx + dx, pcy + dy, "mask_pca_major_axis"),
                _line_record(pcx - pdx, pcy - pdy, pcx + pdx, pcy + pdy, "mask_pca_minor_axis"),
            ]
        )
    return [line for line in raw if line is not None]


def angle_delta_deg(a: float, b: float) -> float:
    delta = abs((a - b + 90.0) % 180.0 - 90.0)
    return float(delta)


def line_coherence(lines: list[dict[str, Any]]) -> dict[str, Any]:
    if not lines:
        return {
            "dominant_angle_deg": None,
            "dominant_weight_fraction": 0.0,
            "orientation_order": 0.0,
            "orientation_bin_count": 0,
            "multi_orientation_structure": False,
            "dominant_count": 0,
            "long_line_count": 0,
            "max_line_length_px": 0.0,
            "coherent": False,
        }
    bin_size = 15.0
    bins: dict[int, dict[str, float]] = {}
    total_weight = 0.0
    for line in lines:
        angle = (float(line["angle_deg"]) + 180.0) % 180.0
        weight = float(line["length_px"])
        idx = int(angle // bin_size)
        item = bins.setdefault(idx, {"weight": 0.0, "count": 0.0, "angle_weight": 0.0})
        item["weight"] += weight
        item["count"] += 1.0
        item["angle_weight"] += angle * weight
        total_weight += weight
    best_idx, best = max(bins.items(), key=lambda pair: pair[1]["weight"])
    fraction = best["weight"] / max(1e-9, total_weight)
    angle = best["angle_weight"] / max(1e-9, best["weight"])
    max_line_length = max(float(line["length_px"]) for line in lines)
    long_line_count = sum(1 for line in lines if float(line["length_px"]) >= 45.0)
    vec_x = 0.0
    vec_y = 0.0
    for line in lines:
        angle_rad = math.radians((float(line["angle_deg"]) + 180.0) % 180.0)
        weight = float(line["length_px"])
        vec_x += weight * math.cos(2.0 * angle_rad)
        vec_y += weight * math.sin(2.0 * angle_rad)
    orientation_order = math.hypot(vec_x, vec_y) / max(1e-9, total_weight)
    circular_angle = (math.degrees(math.atan2(vec_y, vec_x)) * 0.5) % 180.0
    return {
        "dominant_angle_deg": round(float(circular_angle), 3),
        "dominant_bin_angle_deg": round(float(angle), 3),
        "dominant_weight_fraction": round(float(fraction), 4),
        "orientation_order": round(float(orientation_order), 4),
        "orientation_bin_count": len(bins),
        "multi_orientation_structure": bool(len(lines) >= 10 and len(bins) >= 4 and fraction <= 0.58 and long_line_count >= 4),
        "dominant_count": int(best["count"]),
        "long_line_count": int(long_line_count),
        "max_line_length_px": round(float(max_line_length), 3),
        "coherent": bool(orientation_order >= 0.62 and len(lines) >= 5),
        "bin_size_deg": bin_size,
        "bin_index": int(best_idx),
    }


def validate_round_pairs(circles: list[dict[str, Any]], mask_pca: dict[str, Any]) -> list[dict[str, Any]]:
    raw_pairs: list[dict[str, Any]] = []
    pca_angle = float(mask_pca.get("angle_deg") or 0.0)
    elongation = float(mask_pca.get("elongation") or 0.0)
    for left_idx, left in enumerate(circles):
        for right_idx in range(left_idx + 1, len(circles)):
            right = circles[right_idx]
            lx, ly = [float(v) for v in left["center_xy"]]
            rx, ry = [float(v) for v in right["center_xy"]]
            lr = float(left["radius_px"])
            rr = float(right["radius_px"])
            avg_radius = (lr + rr) * 0.5
            distance = math.hypot(rx - lx, ry - ly)
            if avg_radius <= 0 or distance <= 0:
                continue
            radius_ratio = max(lr, rr) / max(1e-6, min(lr, rr))
            sep_ratio = distance / avg_radius
            if radius_ratio > 1.85:
                continue
            if sep_ratio < 1.85 or sep_ratio > 14.0:
                continue
            angular_coverage_mean = (
                float(left.get("angular_coverage") or 0.0) + float(right.get("angular_coverage") or 0.0)
            ) * 0.5
            if angular_coverage_mean < 0.68:
                continue
            pair_angle = math.degrees(math.atan2(ry - ly, rx - lx))
            axis_delta = angle_delta_deg(pair_angle, pca_angle)
            vertical_pair_fraction = abs(ry - ly) / max(distance, 1e-9)
            if axis_delta > 40.0:
                continue
            if elongation >= 2.5 and axis_delta < 25.0 and vertical_pair_fraction > 0.65:
                continue
            score = min(float(left["score"]), float(right["score"]))
            score *= max(0.0, 1.0 - (radius_ratio - 1.0) / 1.35)
            score *= min(1.0, sep_ratio / 4.0)
            score *= min(1.0, angular_coverage_mean / 0.85)
            if score < 0.08:
                continue
            raw_pairs.append(
                {
                    "circle_indices": [left_idx, right_idx],
                    "centers_xy": [left["center_xy"], right["center_xy"]],
                    "radii_px": [lr, rr],
                    "distance_px": round(float(distance), 3),
                    "radius_ratio": round(float(radius_ratio), 4),
                    "separation_radius_ratio": round(float(sep_ratio), 4),
                    "pair_axis_angle_deg": round(float(pair_angle), 3),
                    "mask_axis_delta_deg": round(float(axis_delta), 3),
                    "pair_angular_coverage_mean": round(float(angular_coverage_mean), 4),
                    "vertical_pair_fraction": round(float(vertical_pair_fraction), 4),
                    "score": round(float(score), 4),
                    "strength": "strong" if score >= 0.35 else "weak",
                }
            )
    pairs: list[dict[str, Any]] = []
    used: set[int] = set()
    for pair in sorted(raw_pairs, key=lambda item: item["score"], reverse=True):
        idx_a, idx_b = pair["circle_indices"]
        if idx_a in used or idx_b in used:
            continue
        pairs.append(pair)
        used.update([idx_a, idx_b])
        if len(pairs) >= 4:
            break
    return pairs


def line_dominant_structure(lines: list[dict[str, Any]], line_summary: dict[str, Any], edge_density: float) -> bool:
    edge_supported_multi = bool(line_summary.get("multi_orientation_structure") and edge_density >= 0.05)
    coherent_long_structure = bool(
        edge_density >= 0.05
        and len(lines) >= 8
        and line_summary.get("coherent")
        and (
            int(line_summary.get("long_line_count") or 0) >= 6
            or float(line_summary.get("max_line_length_px") or 0.0) >= 80.0
        )
    )
    return bool(
        (edge_supported_multi or coherent_long_structure)
        and (
            line_summary.get("coherent")
            or int(line_summary.get("long_line_count") or 0) >= 8
            or float(line_summary.get("max_line_length_px") or 0.0) >= 80.0
        )
    )


def high_confidence_round_structure(round_pairs: list[dict[str, Any]]) -> bool:
    strong_scores = [float(pair.get("score") or 0.0) for pair in round_pairs if pair.get("strength") == "strong"]
    return bool(len(strong_scores) >= 2 and max(strong_scores, default=0.0) >= 0.75)


def contextualize_round_pairs(
    round_pairs: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    line_summary: dict[str, Any],
    edge_density: float,
) -> list[dict[str, Any]]:
    if not line_dominant_structure(lines, line_summary, edge_density) or high_confidence_round_structure(round_pairs):
        return round_pairs
    adjusted: list[dict[str, Any]] = []
    for pair in round_pairs:
        item = dict(pair)
        if item.get("strength") == "strong":
            item["strength"] = "weak"
            item["contextual_strength_adjustment"] = "downgraded_inside_line_dominant_structure"
        adjusted.append(item)
    return adjusted


def image_cue_scope(
    round_pairs: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    line_summary: dict[str, Any],
    mask_scope: str,
    edge_density: float,
) -> str:
    strong_round_scores = [float(pair.get("score") or 0.0) for pair in round_pairs if pair.get("strength") == "strong"]
    edge_supported_multi = bool(line_summary.get("multi_orientation_structure") and edge_density >= 0.05)
    line_dominant = line_dominant_structure(lines, line_summary, edge_density)
    high_confidence_round = high_confidence_round_structure(round_pairs)
    if line_dominant and not high_confidence_round:
        return "multi_line_structure_candidate"
    if edge_supported_multi and not strong_round_scores:
        return "multi_line_structure_candidate"
    if strong_round_scores:
        return "round_part_pair_candidate"
    if round_pairs:
        return "weak_round_pair_candidate"
    if line_summary.get("coherent") and len(lines) >= 5:
        return "multi_line_structure_candidate"
    if edge_supported_multi:
        return "multi_line_structure_candidate"
    if len(lines) >= 1 and mask_scope != "weak_single_blob_envelope_only":
        return "image_edge_axis_candidate"
    return "mask_envelope_only"


def image_cue_grade(scope: str, edge_density: float, mask_flags: list[str]) -> str:
    if scope in {"round_part_pair_candidate", "mixed_round_linear_part_candidate", "multi_line_structure_candidate"}:
        if edge_density >= 0.006 and len(mask_flags) <= 3:
            return "experimental_image_part_candidate"
        return "experimental_image_cue_weak"
    if scope == "weak_round_pair_candidate":
        return "experimental_image_cue_weak"
    if scope == "image_edge_axis_candidate":
        return "experimental_image_axis_candidate"
    return "experimental_envelope_only"


def analyze_image_cues(
    crop_img: Image.Image,
    mask: np.ndarray,
    bbox: tuple[int, int, int, int],
    mask_scope: str,
    mask_flags: list[str],
    mask_pca: dict[str, Any],
) -> dict[str, Any]:
    roi = make_roi(mask, bbox)
    gray, edges = edge_map(crop_img, roi)
    circles = round_candidates(gray, edges, roi)
    visual_lines = symmetric_line_candidates(edges)
    lines = dedupe_lines(
        visual_lines + canonical_geometry_lines(mask, bbox, mask_pca),
        edges.shape[1],
        edges.shape[0],
    )
    line_summary = line_coherence(visual_lines)
    edge_pixels = int((edges > 0).sum())
    roi_pixels = int((roi > 0).sum())
    edge_density = round(edge_pixels / float(max(1, roi_pixels)), 5)
    round_pairs = contextualize_round_pairs(validate_round_pairs(circles, mask_pca), visual_lines, line_summary, edge_density)
    strong_round_pair_count = sum(1 for pair in round_pairs if pair.get("strength") == "strong")
    scope = image_cue_scope(round_pairs, lines, line_summary, mask_scope, edge_density)
    return {
        "raw_image_pixels_used": True,
        "label_used": False,
        "roi_source": "detector_bbox_union_dilated_unlabeled_mask",
        "edge_pixel_count": edge_pixels,
        "roi_pixel_count": roi_pixels,
        "edge_density": edge_density,
        "round_primitive_candidates": circles,
        "round_primitive_count": len(circles),
        "validated_round_part_pairs": round_pairs,
        "validated_round_part_pair_count": len(round_pairs),
        "validated_strong_round_part_pair_count": strong_round_pair_count,
        "line_primitive_candidates": lines,
        "line_primitive_count": len(lines),
        "visual_line_primitive_count": len(visual_lines),
        "line_coherence": line_summary,
        "scope": scope,
        "grade": image_cue_grade(scope, edge_density, mask_flags),
        "claim_boundary": (
            "Generic image-space cue extraction from pixels, detector bbox, and unlabeled mask only. "
            "It detects primitive cues such as circles and lines, but does not assign semantic part names."
        ),
    }


def render_image_cues_tile(crop_img: Image.Image, mask: np.ndarray, cues: dict[str, Any], bbox: tuple[int, int, int, int]) -> Image.Image:
    base = crop_img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    roi = make_roi(mask, bbox)
    _, edges = edge_map(crop_img, roi)
    edge_y, edge_x = np.nonzero(edges > 0)
    for x, y in zip(edge_x[::2], edge_y[::2]):
        draw.point((int(x), int(y)), fill=(0, 210, 255, 160))

    alpha = Image.fromarray(np.where(mask > 0, 35, 0).astype(np.uint8))
    mask_color = Image.new("RGBA", base.size, (255, 230, 0, 35))
    overlay.alpha_composite(Image.composite(mask_color, Image.new("RGBA", base.size, (0, 0, 0, 0)), alpha))

    bx1, by1, bx2, by2 = bbox
    draw.rectangle((bx1, by1, bx2, by2), outline=(255, 255, 255, 190), width=1)
    for line in cues.get("line_primitive_candidates") or []:
        x1, y1, x2, y2 = line["xyxy"]
        draw.line((x1, y1, x2, y2), fill=(220, 50, 255, 220), width=2)
    for circle in cues.get("round_primitive_candidates") or []:
        cx, cy = circle["center_xy"]
        radius = max(4.0, float(circle["radius_px"]))
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(35, 255, 120, 90), width=1)
        draw.line((cx - 4, cy, cx + 4, cy), fill=(35, 255, 120, 245), width=2)
        draw.line((cx, cy - 4, cx, cy + 4), fill=(35, 255, 120, 245), width=2)
    used_circle_indices: set[int] = set()
    for pair in cues.get("validated_round_part_pairs") or []:
        idx_a, idx_b = pair["circle_indices"]
        used_circle_indices.update([idx_a, idx_b])
        centers = pair["centers_xy"]
        draw.line((centers[0][0], centers[0][1], centers[1][0], centers[1][1]), fill=(35, 255, 120, 245), width=2)
    raw_circles = cues.get("round_primitive_candidates") or []
    for idx in used_circle_indices:
        if idx >= len(raw_circles):
            continue
        circle = raw_circles[idx]
        cx, cy = circle["center_xy"]
        radius = max(4.0, float(circle["radius_px"]))
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(35, 255, 120, 255), width=4)
    base.alpha_composite(overlay)
    return base.convert("RGB")


def audit_tile(report: dict[str, Any], size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGB", size, (252, 252, 252))
    draw = ImageDraw.Draw(canvas)
    title = load_font(16, bold=True)
    small = load_font(12)
    cues = report["image_space_cues"]
    draw.text((10, 8), str(report["case_id"]), font=title, fill=(25, 25, 25))
    lines = [
        f"label used: {str(report['label_used_by_fitter']).lower()}",
        f"mask scope: {report['proposal_scope']}",
        f"image scope: {cues['scope']}",
        f"round raw: {cues['round_primitive_count']}  pairs: {cues['validated_round_part_pair_count']}",
        f"lines: {cues['line_primitive_count']}  coherent: {str(cues['line_coherence']['coherent']).lower()}",
        f"edge density: {cues['edge_density']:.5f}",
        f"grade: {cues['grade']}",
    ]
    y = 40
    for line in lines:
        fill = (170, 35, 35) if "weak" in line else (55, 55, 55)
        draw.text((10, y), line, font=small, fill=fill)
        y += 20
    flags = report.get("quality_flags") or []
    draw.text((10, y + 2), "flags: " + (", ".join(flags[:3]) if flags else "none"), font=small, fill=(110, 75, 35) if flags else (55, 55, 55))
    draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline=(220, 220, 220), width=1)
    return canvas


def build_grid(rows: list[dict[str, Any]], tiles: dict[str, tuple[Image.Image, Image.Image, Image.Image, Image.Image]], out: Path) -> None:
    cell_w = 245
    cell_h = 226
    header_h = 54
    columns = [
        ("Crop", "real pixels"),
        ("Mask", "detector evidence"),
        ("Mask fit", "bbox/mask only"),
        ("Image cues", "pixels+bbox+mask, no label"),
        ("Audit", "anti-bias metrics"),
    ]
    canvas = Image.new("RGB", (cell_w * len(columns), header_h + cell_h * len(rows) + 32), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    for idx, (title, subtitle) in enumerate(columns):
        x = idx * cell_w + 8
        draw.text((x, 8), title, font=load_font(17, bold=True), fill=(20, 20, 20))
        draw.text((x, 31), subtitle, font=load_font(11), fill=(80, 80, 80))
    for row_idx, report in enumerate(rows):
        y = header_h + row_idx * cell_h
        crop_img, mask_img, mask_fit_img, image_cues_img = tiles[str(report["case_id"])]
        body = [
            labeled_tile(crop_img, str(report["case_id"]), "source crop", (cell_w, cell_h)),
            labeled_tile(mask_img, str(report["case_id"]), "unlabeled masks", (cell_w, cell_h)),
            labeled_tile(mask_fit_img, str(report["case_id"]), "geometry-only mask fit", (cell_w, cell_h)),
            labeled_tile(image_cues_img, str(report["case_id"]), "generic primitive cues", (cell_w, cell_h)),
            labeled_tile(audit_tile(report, (cell_w, cell_h - 46)), str(report["case_id"]), "no semantic fitter input", (cell_w, cell_h)),
        ]
        for col_idx, tile in enumerate(body):
            canvas.paste(tile, (col_idx * cell_w, y))
    note = "Agnostic probe: labels/tags are audit-only; primitive cues are extracted from pixels, detector bbox, and unlabeled masks for every object."
    draw.text((8, canvas.height - 24), note, font=load_font(12), fill=(45, 45, 45))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=95)


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# SPPA Agnostic Image-Space Parts Probe",
        "",
        report["claim_boundary"],
        "",
        f"- Rows: {len(report['rows'])}",
        f"- Figure: `{report['figure']}`",
        f"- Labels used by fitter: {any(row['label_used_by_fitter'] for row in report['rows'])}",
        "",
        "| Case | Mask-only scope | Image cue scope | Round raw | Round pairs | Lines | Coherent lines | Edge density | Grade | Flags |",
        "|---|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in report["rows"]:
        cues = row["image_space_cues"]
        flags = ", ".join(row.get("quality_flags") or []) or "none"
        lines.append(
            f"| {row['case_id']} | {row['proposal_scope']} | {cues['scope']} | "
            f"{cues['round_primitive_count']} | {cues['validated_round_part_pair_count']} | "
            f"{cues['line_primitive_count']} | {str(cues['line_coherence']['coherent']).lower()} | {cues['edge_density']:.5f} | "
            f"{cues['grade']} | {flags} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "This probe tests the user's desired bridge from real detection to proxy primitives without using class-specific rules. The image-space path is more ambitious than mask-only fitting because it can expose generic visual primitives that the detector mask may erase. It is still not a claim of perfect arbitrary reconstruction: circles and lines remain unnamed primitive candidates until SPPA assigns conservative semantics through a separate audited normalizer.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def analyze_row(row: dict[str, Any]) -> tuple[dict[str, Any], tuple[Image.Image, Image.Image, Image.Image, Image.Image]]:
    base_report, crop_img, _, proposal_img = analyze_mask_only_row(row)
    image_path = root_path(row.get("image"))
    bbox = row.get("bbox_xyxy") or []
    if image_path is None or not image_path.exists() or len(bbox) != 4:
        raise FileNotFoundError(f"missing image or bbox for {row.get('case_id')}")
    image = Image.open(image_path).convert("RGB")
    crop = crop_box(image.size, bbox)
    polygons = detection_polygons(row)
    mask, _ = rasterize_polygons(polygons, crop)
    bbox_crop = local_bbox(row, crop)
    cues = analyze_image_cues(
        crop_img,
        mask,
        bbox_crop,
        base_report["proposal_scope"],
        base_report.get("quality_flags") or [],
        base_report.get("pca") or {},
    )
    mask_img = render_mask_tile(crop_img, mask, polygons, crop)
    image_cues_img = render_image_cues_tile(crop_img, mask, cues, bbox_crop)
    report = dict(base_report)
    report["algorithm"] = "SPPA-AGNOSTIC-IMAGE-SPACE-PARTS-0.1"
    report["visual_inputs_used_by_fitter"] = [
        "real_image_crop_pixels",
        "detector_bbox_xyxy",
        "unlabeled_detector_mask_polygons",
    ]
    report["semantic_inputs_used_by_fitter"] = []
    report["label_used_by_fitter"] = False
    report["image_space_cues"] = cues
    report["claim_boundary"] = (
        "Agnostic image-space proposal from real pixels, detector bbox, and unlabeled mask geometry only. "
        "It does not use the object label to select parts and does not assign semantic part names."
    )
    return report, (crop_img, mask_img, proposal_img, image_cues_img)


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe agnostic image-space part cues from real detections.")
    parser.add_argument("--replay-json", type=Path, default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--figure", type=Path, default=DEFAULT_FIGURE)
    args = parser.parse_args()

    replay_json = args.replay_json if args.replay_json.is_absolute() else ROOT / args.replay_json
    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    figure = args.figure if args.figure.is_absolute() else ROOT / args.figure
    data = json.loads(replay_json.read_text(encoding="utf-8"))
    reports: list[dict[str, Any]] = []
    tiles: dict[str, tuple[Image.Image, Image.Image, Image.Image, Image.Image]] = {}
    for row in data.get("rows") or []:
        row_report, row_tiles = analyze_row(row)
        reports.append(row_report)
        tiles[str(row_report["case_id"])] = row_tiles

    run_dir.mkdir(parents=True, exist_ok=True)
    build_grid(reports, tiles, figure)
    claim_boundary = (
        "Experimental agnostic image-space shape-fitting probe. It uses real pixels, detector bbox, and unlabeled mask "
        "geometry only; detector labels and SPPA tags are retained only for audit. The same fitter is applied to every "
        "detector crop and reports visible generic primitive cues rather than class-specific part templates. It tests "
        "whether generic visual primitive cues improve over mask-only fitting before any SPPA production integration."
    )
    report = {
        "schema": "SPPA-AGNOSTIC-IMAGE-SPACE-PARTS-PROBE-0.1",
        "claim_boundary": claim_boundary,
        "replay_json": str(replay_json),
        "figure": str(figure),
        "rows": reports,
    }
    json_out = run_dir / "sppa_agnostic_image_space_parts_probe.json"
    md_out = run_dir / "sppa_agnostic_image_space_parts_probe.md"
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_out, report)
    paper_json = DEFAULT_PAPER_RESULTS / "sppa_agnostic_image_space_parts_probe.json"
    paper_md = DEFAULT_PAPER_RESULTS / "sppa_agnostic_image_space_parts_probe.md"
    paper_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(paper_md, report)
    print(
        json.dumps(
            {
                "json": str(json_out),
                "markdown": str(md_out),
                "paper_json": str(paper_json),
                "figure": str(figure),
                "rows": len(reports),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
