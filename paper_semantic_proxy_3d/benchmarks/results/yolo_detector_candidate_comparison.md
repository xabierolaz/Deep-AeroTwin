# YOLO detector candidate comparison

This is a local probe over the user-supplied tractor images. It is not a COCO/LVIS benchmark; it checks whether each detector can produce a usable image-side tag/box for the SPPA dual-input path.

## Installed model

- Path: `yolo/weights/yolo_unreal_unrealScene_v1_best_e23_2026-02-18.pt`
- Task: `detect`
- YAML: `yolo11n.yaml`
- Classes: `{'0': 'biker', '1': 'cow', '2': 'tower'}`

## Results

| Candidate | Case | Detections | ROI detections | Strict tractor/trailer hit | Weak vehicle hit | Best ROI label | Best ROI conf | Notes |
|---|---:|---:|---:|---:|---:|---|---:|---|
| `installed_custom_yolo11n_3class` | `tractor_real_mountain` | 3 | 1 | no | no | `tower` | 0.013 | Installed project model; fixed classes are biker/cow/tower. |
| `installed_custom_yolo11n_3class` | `tractor_trailer_real_mountain` | 2 | 0 | no | no | `-` | 0.000 | Installed project model; fixed classes are biker/cow/tower. |
| `yolo11x_coco_closed_set` | `tractor_real_mountain` | 6 | 2 | no | yes | `truck` | 0.732 | Large closed-set YOLO11 COCO detector; COCO has 80 classes and no tractor class. |
| `yolo11x_coco_closed_set` | `tractor_trailer_real_mountain` | 11 | 8 | no | yes | `train` | 0.408 | Large closed-set YOLO11 COCO detector; COCO has 80 classes and no tractor class. |
| `yolov8x_worldv2_open_vocab` | `tractor_real_mountain` | 10 | 2 | yes | yes | `tractor with trailer` | 0.415 | YOLO-World open-vocabulary detector with SPPA target prompts. |
| `yolov8x_worldv2_open_vocab` | `tractor_trailer_real_mountain` | 1 | 1 | no | yes | `vehicle` | 0.046 | YOLO-World open-vocabulary detector with SPPA target prompts. |
| `yoloe_11s_seg_open_vocab` | `tractor_real_mountain` | 18 | 10 | yes | yes | `tractor` | 0.044 | YOLOE open-vocabulary segmentation/detection checkpoint with SPPA target prompts. |
| `yoloe_11s_seg_open_vocab` | `tractor_trailer_real_mountain` | 0 | 0 | no | no | `-` | 0.000 | YOLOE open-vocabulary segmentation/detection checkpoint with SPPA target prompts. |
| `yoloe_26s_seg_open_vocab` | `tractor_real_mountain` | 7 | 1 | no | yes | `agricultural vehicle` | 0.701 | YOLOE-26s open-vocabulary segmentation/detection checkpoint selected as the edge-oriented SPPA profile. |
| `yoloe_26s_seg_open_vocab` | `tractor_trailer_real_mountain` | 4 | 4 | no | yes | `vehicle` | 0.015 | YOLOE-26s open-vocabulary segmentation/detection checkpoint selected as the edge-oriented SPPA profile. |
| `yoloe_11l_seg_open_vocab` | `tractor_real_mountain` | 8 | 3 | yes | no | `tractor with trailer` | 0.827 | Larger YOLOE open-vocabulary segmentation/detection checkpoint with SPPA target prompts. |
| `yoloe_11l_seg_open_vocab` | `tractor_trailer_real_mountain` | 0 | 0 | no | no | `-` | 0.000 | Larger YOLOE open-vocabulary segmentation/detection checkpoint with SPPA target prompts. |

## Interpretation

- A strict hit means the detector output label contains `tractor` or `trailer` on a box overlapping the manual ROI.
- A weak vehicle hit means the detector produced a nearby generic vehicle-like label such as `truck`, `vehicle`, `car`, or `train`.
- For the paper claim, weak vehicle hits are not enough: they can help cropping, but they cannot support a truthful tractor-class detector claim.
