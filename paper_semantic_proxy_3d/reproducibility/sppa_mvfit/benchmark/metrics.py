from __future__ import annotations

import math

import numpy as np
from scipy import ndimage


def binary_iou(a: np.ndarray, b: np.ndarray) -> float:
    union = int(np.count_nonzero(a | b))
    if union == 0:
        return 1.0
    return float(np.count_nonzero(a & b) / union)


def voxel_iou(gt: np.ndarray, pred: np.ndarray) -> float:
    return binary_iou(gt, pred)


def bev_iou(gt: np.ndarray, pred: np.ndarray) -> float:
    return binary_iou(np.any(gt, axis=2), np.any(pred, axis=2))


def volume_error(gt: np.ndarray, pred: np.ndarray) -> float:
    gt_count = int(np.count_nonzero(gt))
    pred_count = int(np.count_nonzero(pred))
    if gt_count == 0:
        return 0.0 if pred_count == 0 else 1.0
    return abs(pred_count - gt_count) / gt_count


def containment_errors(gt: np.ndarray, pred: np.ndarray) -> tuple[float, float]:
    gt_count = int(np.count_nonzero(gt))
    pred_count = int(np.count_nonzero(pred))
    gt_outside = int(np.count_nonzero(gt & ~pred)) / max(gt_count, 1)
    pred_outside = int(np.count_nonzero(pred & ~gt)) / max(pred_count, 1)
    return float(gt_outside), float(pred_outside)


def surface_mask(occupancy: np.ndarray) -> np.ndarray:
    eroded = ndimage.binary_erosion(occupancy, structure=ndimage.generate_binary_structure(3, 1), border_value=0)
    return occupancy & ~eroded


def normalized_symmetric_chamfer(gt: np.ndarray, pred: np.ndarray, world_diagonal: float) -> float:
    gt_surface = surface_mask(gt)
    pred_surface = surface_mask(pred)
    if not np.any(gt_surface) and not np.any(pred_surface):
        return 0.0
    if not np.any(gt_surface) or not np.any(pred_surface):
        return 1.0
    distance_to_pred = ndimage.distance_transform_edt(~pred_surface)
    distance_to_gt = ndimage.distance_transform_edt(~gt_surface)
    resolution = gt.shape[0]
    cell_diagonal_units = world_diagonal / (math.sqrt(3.0) * resolution)
    a = float(distance_to_pred[gt_surface].mean() * cell_diagonal_units)
    b = float(distance_to_gt[pred_surface].mean() * cell_diagonal_units)
    return 0.5 * (a + b) / world_diagonal


def heldout_silhouette_iou(gt: np.ndarray, pred: np.ndarray) -> float:
    values: list[float] = []
    for angle in (45.0, 135.0, 225.0, 315.0):
        gt_rot = ndimage.rotate(gt.astype(np.uint8), angle, axes=(0, 1), reshape=False, order=0, mode="constant", cval=0, prefilter=False).astype(bool)
        pred_rot = ndimage.rotate(pred.astype(np.uint8), angle, axes=(0, 1), reshape=False, order=0, mode="constant", cval=0, prefilter=False).astype(bool)
        values.append(binary_iou(np.any(gt_rot, axis=1), np.any(pred_rot, axis=1)))
    return float(np.mean(values))


def evaluate_geometry(gt: np.ndarray, pred: np.ndarray, include_expensive: bool, world_diagonal: float) -> dict[str, float]:
    gt_outside, pred_outside = containment_errors(gt, pred)
    row = {
        "voxel_iou": voxel_iou(gt, pred),
        "bev_iou": bev_iou(gt, pred),
        "volume_error": volume_error(gt, pred),
        "gt_outside_prediction": gt_outside,
        "prediction_outside_gt": pred_outside,
    }
    if include_expensive:
        row["normalized_symmetric_chamfer"] = normalized_symmetric_chamfer(gt, pred, world_diagonal)
        row["heldout_silhouette_iou"] = heldout_silhouette_iou(gt, pred)
    else:
        row["normalized_symmetric_chamfer"] = math.nan
        row["heldout_silhouette_iou"] = math.nan
    return row

