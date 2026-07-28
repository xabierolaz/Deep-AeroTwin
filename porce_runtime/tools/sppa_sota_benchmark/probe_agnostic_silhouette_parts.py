from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPLAY_JSON = (
    ROOT.parent
    / "papers"
    / "semantic_proxy_3d"
    / "benchmarks"
    / "results"
    / "real_image_assumed_flight_replay.json"
)
DEFAULT_RUN_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_agnostic_shape_fitting" / "20260704_real_masks"
DEFAULT_PAPER_RESULTS = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"
DEFAULT_FIGURE = ROOT.parent / "papers" / "semantic_proxy_3d" / "figures" / "sppa_agnostic_silhouette_parts_grid.png"


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = [
        "arialbd.ttf" if bold else "arial.ttf",
        "calibrib.ttf" if bold else "calibri.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
    ]
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def root_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def crop_box(image_size: tuple[int, int], bbox: list[float], pad_ratio: float = 0.28) -> tuple[int, int, int, int]:
    width, height = image_size
    x1, y1, x2, y2 = [float(v) for v in bbox]
    bw = max(1.0, x2 - x1)
    bh = max(1.0, y2 - y1)
    pad = max(bw, bh) * pad_ratio
    return (
        max(0, int(math.floor(x1 - pad))),
        max(0, int(math.floor(y1 - pad))),
        min(width, int(math.ceil(x2 + pad))),
        min(height, int(math.ceil(y2 + pad))),
    )


def polygon_area(poly: list[list[float]]) -> float:
    if len(poly) < 3:
        return 0.0
    area = 0.0
    for idx, point in enumerate(poly):
        x1, y1 = float(point[0]), float(point[1])
        x2, y2 = float(poly[(idx + 1) % len(poly)][0]), float(poly[(idx + 1) % len(poly)][1])
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def polygon_signature(poly: list[list[float]], ndigits: int = 2) -> tuple[tuple[float, float], ...]:
    rounded = [(round(float(x), ndigits), round(float(y), ndigits)) for x, y in poly]
    if not rounded:
        return tuple()
    rotations = [tuple(rounded[idx:] + rounded[:idx]) for idx in range(len(rounded))]
    reversed_points = list(reversed(rounded))
    rotations += [tuple(reversed_points[idx:] + reversed_points[:idx]) for idx in range(len(reversed_points))]
    return min(rotations)


def polygon_centroid(poly: list[list[float]]) -> tuple[float, float]:
    if not poly:
        return (0.0, 0.0)
    xs = [float(x) for x, _ in poly]
    ys = [float(y) for _, y in poly]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def detection_polygons(row: dict[str, Any]) -> list[dict[str, Any]]:
    polygons: list[dict[str, Any]] = []
    for det_idx, det in enumerate(row.get("used_detections") or []):
        polygon = det.get("mask_polygon_px") or []
        if len(polygon) >= 3:
            polygons.append(
                {
                    "source": "used_detection_mask_polygon",
                    "index": det_idx,
                    "polygon": polygon,
                    "area_px2": polygon_area(polygon),
                    "confidence": det.get("confidence"),
                }
            )
    if polygons:
        unique: dict[tuple[tuple[float, float], ...], dict[str, Any]] = {}
        for item in polygons:
            signature = polygon_signature(item["polygon"])
            previous = unique.get(signature)
            if previous is None or float(item.get("area_px2") or 0.0) > float(previous.get("area_px2") or 0.0):
                unique[signature] = item
        ordered = sorted(
            unique.values(),
            key=lambda item: (
                -float(item.get("area_px2") or 0.0),
                polygon_centroid(item["polygon"])[0],
                polygon_centroid(item["polygon"])[1],
            ),
        )
        for stable_idx, item in enumerate(ordered):
            item["index"] = stable_idx
        return ordered
    native = row.get("native_detector_mask") or {}
    polygon = native.get("polygon") or []
    if len(polygon) >= 3:
        polygons.append(
            {
                "source": "native_detector_mask_polygon",
                "index": 0,
                "polygon": polygon,
                "area_px2": polygon_area(polygon),
                "confidence": native.get("quality_score"),
            }
        )
    return polygons


def rasterize_polygons(polygons: list[dict[str, Any]], crop: tuple[int, int, int, int]) -> tuple[np.ndarray, list[np.ndarray]]:
    left, top, right, bottom = crop
    width, height = max(1, right - left), max(1, bottom - top)
    union = np.zeros((height, width), dtype=np.uint8)
    masks: list[np.ndarray] = []
    for item in polygons:
        pts = np.array(
            [[[float(x) - left, float(y) - top] for x, y in item["polygon"]]],
            dtype=np.float32,
        )
        pts = np.rint(pts).astype(np.int32)
        mask = np.zeros_like(union)
        cv2.fillPoly(mask, pts, 255)
        masks.append(mask)
        union = cv2.bitwise_or(union, mask)
    return union, masks


def connected_components(mask: np.ndarray, min_area: int = 8) -> list[dict[str, Any]]:
    count, labels, stats, centroids = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
    components: list[dict[str, Any]] = []
    for label_idx in range(1, count):
        area = int(stats[label_idx, cv2.CC_STAT_AREA])
        if area < min_area:
            continue
        x = int(stats[label_idx, cv2.CC_STAT_LEFT])
        y = int(stats[label_idx, cv2.CC_STAT_TOP])
        w = int(stats[label_idx, cv2.CC_STAT_WIDTH])
        h = int(stats[label_idx, cv2.CC_STAT_HEIGHT])
        cx, cy = centroids[label_idx]
        fill = area / float(max(1, w * h))
        components.append(
            {
                "area_px": area,
                "bbox_xywh": [x, y, w, h],
                "centroid_xy": [float(cx), float(cy)],
                "fill_ratio": round(fill, 4),
            }
        )
    return sorted(components, key=lambda item: item["area_px"], reverse=True)


def pca_features(mask: np.ndarray) -> dict[str, Any]:
    ys, xs = np.nonzero(mask > 0)
    if len(xs) < 3:
        return {
            "centroid_xy": [0.0, 0.0],
            "angle_deg": 0.0,
            "elongation": 0.0,
            "eigenvalues": [0.0, 0.0],
        }
    points = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
    centroid = points.mean(axis=0)
    centered = points - centroid
    cov = np.cov(centered, rowvar=False)
    values, vectors = np.linalg.eigh(cov)
    order = np.argsort(values)[::-1]
    values = values[order]
    vectors = vectors[:, order]
    main = vectors[:, 0]
    angle = math.degrees(math.atan2(float(main[1]), float(main[0])))
    elongation = math.sqrt(float(values[0]) / max(float(values[1]), 1e-9))
    return {
        "centroid_xy": [round(float(centroid[0]), 3), round(float(centroid[1]), 3)],
        "angle_deg": round(angle, 3),
        "elongation": round(elongation, 3),
        "eigenvalues": [round(float(values[0]), 3), round(float(values[1]), 3)],
    }


def mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask > 0)
    if len(xs) == 0:
        return (0, 0, 0, 0)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def projection_segments(values: np.ndarray, threshold: float, min_width: int = 3) -> list[tuple[int, int, float]]:
    active = values >= threshold
    segments: list[tuple[int, int, float]] = []
    start: int | None = None
    for idx, on in enumerate(active.tolist() + [False]):
        if on and start is None:
            start = idx
        if not on and start is not None:
            end = idx
            if end - start >= min_width:
                segments.append((start, end, float(values[start:end].sum())))
            start = None
    return sorted(segments, key=lambda item: item[2], reverse=True)


def support_candidates(mask: np.ndarray, box: tuple[int, int, int, int]) -> list[dict[str, Any]]:
    x1, y1, x2, y2 = box
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    lower_y = int(round(y1 + height * 0.58))
    lower = np.zeros_like(mask)
    lower[lower_y:y2, x1:x2] = mask[lower_y:y2, x1:x2]
    components = connected_components(lower, min_area=max(8, int(mask.sum() / 255 * 0.01)))
    candidates: list[dict[str, Any]] = []
    for component in components[:4]:
        bx, by, bw, bh = component["bbox_xywh"]
        aspect = bw / float(max(1, bh))
        compactness = min(aspect, 1.0 / max(aspect, 1e-6))
        if bw < width * 0.04 or bh < height * 0.04:
            continue
        if compactness < 0.55:
            continue
        candidates.append(
            {
                "method": "lower_connected_component",
                "center_xy": [round(component["centroid_xy"][0], 3), round(component["centroid_xy"][1], 3)],
                "radius_px": round(max(bw, bh) * 0.5, 3),
                "bbox_xywh": [bx, by, bw, bh],
                "area_px": component["area_px"],
                "compactness": round(float(compactness), 3),
            }
        )

    projection = (lower[:, x1:x2] > 0).sum(axis=0).astype(np.float64)
    if projection.size and projection.max() > 0:
        kernel = np.ones(5, dtype=np.float64) / 5.0
        smooth = np.convolve(projection, kernel, mode="same")
        segments = projection_segments(smooth, max(2.0, smooth.max() * 0.30), min_width=max(3, int(width * 0.035)))
        for start, end, mass in segments[:4]:
            gx1, gx2 = x1 + start, x1 + end
            sub = lower[lower_y:y2, gx1:gx2]
            ys, xs = np.nonzero(sub > 0)
            if len(xs) < 8:
                continue
            cx = gx1 + float(xs.mean())
            cy = lower_y + float(ys.mean())
            radius = max((gx2 - gx1) * 0.5, float(ys.max() - ys.min() + 1) * 0.5)
            peak_w = max(1, gx2 - gx1)
            peak_h = max(1, int(ys.max() - ys.min() + 1))
            compactness = min(peak_w / float(peak_h), peak_h / float(peak_w))
            if compactness < 0.55 or radius > max(width, height) * 0.32:
                continue
            duplicate = any(abs(cx - cand["center_xy"][0]) < radius * 0.35 for cand in candidates)
            if not duplicate:
                candidates.append(
                    {
                        "method": "lower_projection_peak",
                        "center_xy": [round(cx, 3), round(cy, 3)],
                        "radius_px": round(radius, 3),
                        "bbox_xywh": [int(gx1), int(lower_y), int(gx2 - gx1), int(y2 - lower_y)],
                        "area_px": int(len(xs)),
                        "compactness": round(float(compactness), 3),
                    }
                )
    candidates = sorted(candidates, key=lambda item: (item["center_xy"][1], item["area_px"]), reverse=True)
    return candidates[:4]


def component_proposals(component_masks: list[np.ndarray]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for idx, component_mask in enumerate(component_masks):
        area = int((component_mask > 0).sum())
        if area < 8:
            continue
        pca = pca_features(component_mask)
        rect = min_area_rect(component_mask)
        proposals.append(
            {
                "component_index": idx,
                "area_px": area,
                "pca": pca,
                "min_area_rect": rect,
            }
        )
    return sorted(proposals, key=lambda item: item["area_px"], reverse=True)


def proposal_scope(
    component_count: int,
    support_count: int,
    pca: dict[str, Any],
    flags: list[str],
) -> str:
    if support_count >= 2:
        return "lower_support_part_candidate"
    if component_count >= 2:
        return "unlabeled_component_candidate"
    if float(pca.get("elongation") or 0.0) >= 2.0:
        return "axis_aligned_envelope_only"
    if len(flags) >= 3:
        return "weak_single_blob_envelope_only"
    return "single_blob_envelope_only"


def evidence_grade(scope: str, flags: list[str]) -> str:
    if scope in {"lower_support_part_candidate", "unlabeled_component_candidate"} and len(flags) <= 2:
        return "experimental_part_candidate"
    if "weak" in scope or len(flags) >= 3:
        return "experimental_weak"
    return "experimental_envelope_only"


def upper_mass(mask: np.ndarray, box: tuple[int, int, int, int]) -> dict[str, Any] | None:
    x1, y1, x2, y2 = box
    height = max(1, y2 - y1)
    upper_y2 = int(round(y1 + height * 0.48))
    upper = np.zeros_like(mask)
    upper[y1:upper_y2, x1:x2] = mask[y1:upper_y2, x1:x2]
    ys, xs = np.nonzero(upper > 0)
    if len(xs) < 8:
        return None
    return {
        "center_xy": [round(float(xs.mean()), 3), round(float(ys.mean()), 3)],
        "area_px": int(len(xs)),
        "bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
    }


def min_area_rect(mask: np.ndarray) -> dict[str, Any] | None:
    contours, _ = cv2.findContours((mask > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rect)
    return {
        "center_xy": [round(float(rect[0][0]), 3), round(float(rect[0][1]), 3)],
        "size_wh": [round(float(rect[1][0]), 3), round(float(rect[1][1]), 3)],
        "angle_deg": round(float(rect[2]), 3),
        "corners_xy": [[round(float(x), 3), round(float(y), 3)] for x, y in box],
    }


def quality_flags(mask: np.ndarray, row: dict[str, Any], supports: list[dict[str, Any]], pca: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    area = int((mask > 0).sum())
    bbox = row.get("bbox_xyxy") or []
    image_path = root_path(row.get("image"))
    bbox_area_pct = 0.0
    if len(bbox) == 4 and image_path and image_path.exists():
        with Image.open(image_path) as image:
            iw, ih = image.size
        bbox_area_pct = 100.0 * max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1]) / float(iw * ih)
    confidence = float(row.get("detector_confidence") or 0.0)
    if confidence < 0.50:
        flags.append("low_detector_confidence")
    if bbox_area_pct < 1.0:
        flags.append("small_image_evidence")
    if area < 500:
        flags.append("small_mask_area")
    if len(supports) < 2:
        flags.append("weak_lower_support_separation")
    if float(pca.get("elongation") or 0.0) < 1.4:
        flags.append("weak_principal_axis")
    return flags


def analyze_row(row: dict[str, Any]) -> tuple[dict[str, Any], Image.Image, Image.Image, Image.Image]:
    image_path = root_path(row.get("image"))
    bbox = row.get("bbox_xyxy") or []
    if image_path is None or not image_path.exists() or len(bbox) != 4:
        raise FileNotFoundError(f"missing image or bbox for {row.get('case_id')}")
    image = Image.open(image_path).convert("RGB")
    crop = crop_box(image.size, bbox)
    polygons = detection_polygons(row)
    mask, component_masks = rasterize_polygons(polygons, crop)
    box = mask_bbox(mask)
    pca = pca_features(mask)
    components = connected_components(mask, min_area=12)
    unlabeled_components = component_proposals(component_masks)
    supports = support_candidates(mask, box)
    upper = upper_mass(mask, box)
    rect = min_area_rect(mask)
    flags = quality_flags(mask, row, supports, pca)
    scope = proposal_scope(len(unlabeled_components), len(supports), pca, flags)
    area_px = int((mask > 0).sum())
    x1, y1, x2, y2 = box
    bbox_area = max(1, (x2 - x1) * (y2 - y1))
    report = {
        "case_id": row.get("case_id"),
        "algorithm": "SPPA-AGNOSTIC-SILHOUETTE-PARTS-0.1",
        "label_used_by_fitter": False,
        "semantic_inputs_used_by_fitter": [],
        "visual_inputs_used_by_fitter": [
            "real_image_crop_for_visualization_only",
            "detector_bbox_xyxy",
            "unlabeled_detector_mask_polygons",
        ],
        "detector_confidence_used_as_quality_only": True,
        "detector_label_for_audit_only": row.get("detector_label"),
        "reviewed_semantic_tag_for_audit_only": row.get("reviewed_semantic_tag"),
        "crop_xyxy": list(crop),
        "unlabeled_mask_polygon_count": len(polygons),
        "unlabeled_detector_component_count": len(component_masks),
        "raster_connected_component_count": len(components),
        "mask_area_px": area_px,
        "mask_bbox_xyxy_crop": [x1, y1, x2, y2],
        "mask_fill_ratio": round(area_px / float(bbox_area), 4),
        "pca": pca,
        "min_area_rect": rect,
        "unlabeled_component_proposals": unlabeled_components,
        "upper_mass": upper,
        "support_candidates": supports,
        "support_candidate_count": len(supports),
        "proposal_scope": scope,
        "quality_flags": flags,
        "evidence_grade": evidence_grade(scope, flags),
        "claim_boundary": (
            "Agnostic image-space proposal from bbox/mask geometry only. It does not use the object label to place parts "
            "and does not claim ground-truth segmentation, 3D reconstruction, or final SPPA integration."
        ),
    }
    crop_img = image.crop(crop)
    mask_img = render_mask_tile(crop_img, mask, polygons, crop)
    proposal_img = render_proposal_tile(crop_img, mask, pca, rect, unlabeled_components, upper, supports)
    return report, crop_img, mask_img, proposal_img


def render_mask_tile(crop_img: Image.Image, mask: np.ndarray, polygons: list[dict[str, Any]], crop: tuple[int, int, int, int]) -> Image.Image:
    base = crop_img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    alpha = Image.fromarray(np.where(mask > 0, 88, 0).astype(np.uint8))
    color = Image.new("RGBA", base.size, (255, 220, 0, 88))
    overlay.alpha_composite(Image.composite(color, Image.new("RGBA", base.size, (0, 0, 0, 0)), alpha))
    left, top, _, _ = crop
    for item in polygons:
        pts = [(float(x) - left, float(y) - top) for x, y in item["polygon"]]
        if len(pts) >= 3:
            od.line(pts + [pts[0]], fill=(255, 240, 0, 255), width=3)
    base.alpha_composite(overlay)
    return base.convert("RGB")


def draw_cross(draw: ImageDraw.ImageDraw, xy: list[float], color: tuple[int, int, int], radius: int = 5) -> None:
    x, y = float(xy[0]), float(xy[1])
    draw.line((x - radius, y, x + radius, y), fill=color, width=3)
    draw.line((x, y - radius, x, y + radius), fill=color, width=3)


def render_proposal_tile(
    crop_img: Image.Image,
    mask: np.ndarray,
    pca: dict[str, Any],
    rect: dict[str, Any] | None,
    component_proposals_: list[dict[str, Any]],
    upper: dict[str, Any] | None,
    supports: list[dict[str, Any]],
) -> Image.Image:
    base = crop_img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    alpha = Image.fromarray(np.where(mask > 0, 50, 0).astype(np.uint8))
    mask_color = Image.new("RGBA", base.size, (255, 230, 0, 50))
    overlay.alpha_composite(Image.composite(mask_color, Image.new("RGBA", base.size, (0, 0, 0, 0)), alpha))

    if rect:
        pts = [tuple(pt) for pt in rect["corners_xy"]]
        od.line(pts + [pts[0]], fill=(255, 60, 60, 230), width=3)

    for component in component_proposals_[:4]:
        component_rect = component.get("min_area_rect")
        if not component_rect:
            continue
        pts = [tuple(pt) for pt in component_rect["corners_xy"]]
        od.line(pts + [pts[0]], fill=(255, 150, 25, 230), width=2)
        draw_cross(od, component["pca"]["centroid_xy"], (255, 150, 25), radius=4)

    cx, cy = pca["centroid_xy"]
    angle = math.radians(float(pca["angle_deg"]))
    length = max(base.size) * 0.45
    dx, dy = math.cos(angle) * length, math.sin(angle) * length
    od.line((cx - dx, cy - dy, cx + dx, cy + dy), fill=(0, 210, 255, 255), width=3)
    draw_cross(od, [cx, cy], (0, 210, 255), radius=6)

    upper_xy = upper.get("center_xy") if upper else None
    if upper_xy:
        ux, uy = upper_xy
        od.ellipse((ux - 10, uy - 10, ux + 10, uy + 10), outline=(30, 150, 255, 255), width=4)
    for support in supports:
        sx, sy = support["center_xy"]
        radius = max(8.0, float(support["radius_px"]))
        od.ellipse((sx - radius, sy - radius, sx + radius, sy + radius), outline=(255, 235, 0, 255), width=4)
        draw_cross(od, [sx, sy], (255, 235, 0), radius=4)
        if upper_xy:
            od.line((sx, sy, upper_xy[0], upper_xy[1]), fill=(30, 220, 95, 245), width=3)
    if len(supports) >= 2:
        ordered = sorted(supports, key=lambda item: item["center_xy"][0])
        for left, right in zip(ordered, ordered[1:]):
            od.line(
                (
                    left["center_xy"][0],
                    left["center_xy"][1],
                    right["center_xy"][0],
                    right["center_xy"][1],
                ),
                fill=(30, 220, 95, 220),
                width=3,
            )

    base.alpha_composite(overlay)
    return base.convert("RGB")


def fit_tile(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGB", size, (250, 250, 250))
    im = image.convert("RGB")
    im.thumbnail(size, Image.Resampling.LANCZOS)
    canvas.paste(im, ((size[0] - im.width) // 2, (size[1] - im.height) // 2))
    return canvas


def text_tile(report: dict[str, Any], size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGB", size, (252, 252, 252))
    draw = ImageDraw.Draw(canvas)
    title = load_font(17, bold=True)
    small = load_font(13)
    draw.text((12, 10), str(report["case_id"]), font=title, fill=(25, 25, 25))
    lines = [
        f"label used: {str(report['label_used_by_fitter']).lower()}",
        f"mask polys: {report['unlabeled_mask_polygon_count']}  comps: {report['raster_connected_component_count']}",
        f"area: {report['mask_area_px']} px  fill: {report['mask_fill_ratio']}",
        f"PCA angle: {report['pca']['angle_deg']:.1f}  elong: {report['pca']['elongation']:.2f}",
        f"supports: {report['support_candidate_count']}  det-comps: {report['unlabeled_detector_component_count']}",
        f"scope: {report['proposal_scope']}",
        f"grade: {report['evidence_grade']}",
    ]
    y = 44
    for line in lines:
        fill = (170, 35, 35) if "weak" in line else (55, 55, 55)
        draw.text((12, y), line, font=small, fill=fill)
        y += 22
    flags = report.get("quality_flags") or []
    flag_text = ", ".join(flags[:3]) if flags else "none"
    draw.text((12, y + 4), f"flags: {flag_text}", font=small, fill=(120, 80, 35) if flags else (55, 55, 55))
    draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline=(220, 220, 220), width=1)
    return canvas


def labeled_tile(image: Image.Image, title: str, subtitle: str, size: tuple[int, int]) -> Image.Image:
    width, height = size
    out = Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(out)
    draw.text((8, 6), title, font=load_font(16, bold=True), fill=(20, 20, 20))
    draw.text((8, 27), subtitle, font=load_font(12), fill=(80, 80, 80))
    body = fit_tile(image, (width, height - 46))
    out.paste(body, (0, 46))
    draw.rectangle((0, 46, width - 1, height - 1), outline=(225, 225, 225), width=1)
    return out


def build_grid(rows: list[dict[str, Any]], tiles: dict[str, tuple[Image.Image, Image.Image, Image.Image]], out: Path) -> None:
    cell_w = 270
    cell_h = 238
    header_h = 54
    columns = [
        ("Crop", "real pixels"),
        ("Mask", "unlabeled detector evidence"),
        ("Agnostic proposals", "no semantic tag used"),
        ("Audit", "geometry-only metrics"),
    ]
    canvas = Image.new("RGB", (cell_w * len(columns), header_h + cell_h * len(rows) + 30), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    for idx, (title, subtitle) in enumerate(columns):
        x = idx * cell_w + 8
        draw.text((x, 8), title, font=load_font(18, bold=True), fill=(20, 20, 20))
        draw.text((x, 32), subtitle, font=load_font(12), fill=(80, 80, 80))
    for row_idx, report in enumerate(rows):
        y = header_h + row_idx * cell_h
        crop_img, mask_img, proposal_img = tiles[str(report["case_id"])]
        body = [
            labeled_tile(crop_img, str(report["case_id"]), "source crop", (cell_w, cell_h)),
            labeled_tile(mask_img, str(report["case_id"]), "mask/bbox only", (cell_w, cell_h)),
            labeled_tile(proposal_img, str(report["case_id"]), "generic geometric fit", (cell_w, cell_h)),
            labeled_tile(text_tile(report, (cell_w, cell_h - 46)), str(report["case_id"]), "unbiased audit", (cell_w, cell_h)),
        ]
        for col_idx, tile in enumerate(body):
            canvas.paste(tile, (col_idx * cell_w, y))
    note = "Agnostic probe: part proposals are computed from detector mask/bbox geometry only; labels are shown only for row identity/audit."
    draw.text((8, canvas.height - 24), note, font=load_font(13), fill=(45, 45, 45))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=95)


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# SPPA Agnostic Silhouette Parts Probe",
        "",
        report["claim_boundary"],
        "",
        f"- Rows: {len(report['rows'])}",
        f"- Figure: `{report['figure']}`",
        f"- Labels used by fitter: {any(row['label_used_by_fitter'] for row in report['rows'])}",
        "",
        "| Case | Grade | Scope | Mask polys | Components | Supports | PCA angle | Elongation | Flags |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["rows"]:
        flags = ", ".join(row.get("quality_flags") or []) or "none"
        lines.append(
            f"| {row['case_id']} | {row['evidence_grade']} | {row['proposal_scope']} | "
            f"{row['unlabeled_mask_polygon_count']} | {row['raster_connected_component_count']} | {row['support_candidate_count']} | "
            f"{row['pca']['angle_deg']:.1f} | {row['pca']['elongation']:.2f} | {flags} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "This is deliberately not a SPPA production path yet. It tests whether the mask contains enough geometry to propose parts without using the semantic label. `experimental_envelope_only` means the image supports a coarse oriented proxy but not reliable internal parts. `experimental_part_candidate` means the geometry exposes either unlabeled detector components or multiple compact supports. A weak grade means the visual evidence should not be over-interpreted; SPPA should keep a conservative family-level proxy or high uncertainty.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe agnostic image-space part proposals from real detector masks.")
    parser.add_argument("--replay-json", type=Path, default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--figure", type=Path, default=DEFAULT_FIGURE)
    args = parser.parse_args()

    replay_json = args.replay_json if args.replay_json.is_absolute() else ROOT / args.replay_json
    run_dir = args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir
    figure = args.figure if args.figure.is_absolute() else ROOT / args.figure
    data = json.loads(replay_json.read_text(encoding="utf-8"))
    rows = list(data.get("rows") or [])
    reports: list[dict[str, Any]] = []
    tiles: dict[str, tuple[Image.Image, Image.Image, Image.Image]] = {}
    for row in rows:
        row_report, crop_img, mask_img, proposal_img = analyze_row(row)
        reports.append(row_report)
        tiles[str(row_report["case_id"])] = (crop_img, mask_img, proposal_img)

    run_dir.mkdir(parents=True, exist_ok=True)
    build_grid(reports, tiles, figure)
    claim_boundary = (
        "Experimental agnostic shape-fitting probe. It uses detector bbox/mask geometry only, not semantic labels, "
        "to test whether image-space evidence can support part proposals before SPPA recipe integration. "
        "It is not a ground-truth segmentation, not a 3D reconstruction metric, and not a production claim."
    )
    report = {
        "schema": "SPPA-AGNOSTIC-SILHOUETTE-PARTS-PROBE-0.1",
        "claim_boundary": claim_boundary,
        "replay_json": str(replay_json),
        "figure": str(figure),
        "rows": reports,
    }
    json_out = run_dir / "sppa_agnostic_silhouette_parts_probe.json"
    md_out = run_dir / "sppa_agnostic_silhouette_parts_probe.md"
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_out, report)
    paper_json = DEFAULT_PAPER_RESULTS / "sppa_agnostic_silhouette_parts_probe.json"
    paper_md = DEFAULT_PAPER_RESULTS / "sppa_agnostic_silhouette_parts_probe.md"
    paper_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(paper_md, report)
    print(json.dumps({"json": str(json_out), "markdown": str(md_out), "paper_json": str(paper_json), "figure": str(figure), "rows": len(reports)}, indent=2))


if __name__ == "__main__":
    main()
