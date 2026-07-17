# SPPA open-vocabulary detector decision

Date: 2026-07-03

## Selected profiles

We select `YOLOE-26s-seg` as the SPPA image-side detector model, with two prompt profiles:

1. `yoloe26s_edge_open_vocab`: the controlled edge/runtime profile.
2. `yoloe26s_universal_prompt_probe`: a broader paper stress-test profile.

- Weights: `yoloe-26s-seg.pt`
- Text encoder asset: `mobileclip2_b.ts`
- Runtime package: `ultralytics==8.4.86`
- Edge config: `tools/sppa_sota_benchmark/sppa_open_vocab_detector_config.json`
- Universal stress config: `tools/sppa_sota_benchmark/sppa_open_vocab_detector_universal_config.json`
- Runner: `tools/sppa_sota_benchmark/run_sppa_open_vocab_detector.py`
- Semantic normalizer: `tools/sppa_sota_benchmark/sppa_semantic_normalizer.py`
- Edge probe report: `experiments/sppa_detection_reference/20260703_yoloe26s_open_vocab/sppa_open_vocab_detector_probe.md`
- Edge CPU probe report: `experiments/sppa_detection_reference/20260703_yoloe26s_open_vocab_cpu/sppa_open_vocab_detector_probe.md`
- Universal probe report: `experiments/sppa_detection_reference/20260703_yoloe26s_universal_open_vocab/sppa_open_vocab_detector_probe.md`
- Universal CPU probe report: `experiments/sppa_detection_reference/20260703_yoloe26s_universal_open_vocab_cpu/sppa_open_vocab_detector_probe.md`
- Normalizer verification: `experiments/sppa_detection_reference/20260703_yoloe26s_open_vocab/sppa_semantic_normalizer_verify.json`

## Rationale

The installed project detector is a narrow custom YOLO11n model with only `biker`, `cow`, and `tower` classes. It is not suitable as a universal image-side source for the SPPA paper.

Closed-set COCO YOLO models are stronger general detectors, but COCO's fixed 80-class vocabulary does not include every UAV-relevant object. For the paper, the important capability is not fine-grained recognition of every object name; it is the ability to produce compact semantic detections that map into reviewed SPPA proxy archetypes.

YOLOE-26s is a better fit because it keeps the YOLO-family deployment shape while supporting text-prompted open-vocabulary detection/segmentation. The selected `s` size is a practical compromise for a real UAV pipeline: more universal than the 3-class custom YOLO, much lighter than heavyweight open-world transformer detectors, and aligned with edge deployment claims.

Prompt scope is itself part of the system design. The edge profile keeps a shorter vocabulary to reduce the false-positive surface for runtime. The universal profile intentionally probes a wider vocabulary, including vehicles, structures, vegetation, animals, construction equipment, and generic objects. That profile is not a promise of exact recognition; it is a stress-test of SPPA's ability to route approximate labels into reviewed families or conservative unknown fallback geometry.

The paper-facing SPPA layer should not copy the detector's top-1 label. It should normalize detector evidence into a hierarchical proxy tag and a reviewed runtime archetype:

1. Use composition when multiple detections explain the object, e.g. `person + motorcycle` -> `two_wheeled_rider`.
2. Preserve useful specificity, e.g. `electric pylon` -> `power_tower`.
3. Use conservative families for weak labels, e.g. `vehicle` -> `generic_vehicle` rendered with a `heavy_vehicle` footprint.
4. Route common new families such as `building`, `bridge`, `wall`, and `fence` into `built_structure`.
5. Fall back to `unknown` conservative geometry for labels outside the reviewed ontology.

## Local probe result

Edge profile, GPU auto device on the desktop workstation:

| Input | Detector evidence | SPPA tag | Runtime archetype | Confidence | Inference ms |
|---|---|---|---|---:|---:|
| Cyclist road image | `person + motorcycle` | `two_wheeled_rider` | `biker` | 0.422 | 11.6 |
| Mountain tower image | `electric pylon` | `power_tower` | `vertical_structure` | 0.458 | 12.0 |
| Mountain tractor image | `agricultural vehicle` | `farm_vehicle` | `farm_vehicle` | 0.522 | 41.6 |
| Tractor with trailer image | `vehicle` | `generic_vehicle` | `heavy_vehicle` | 0.471 | 40.7 |

Forced CPU on the same workstation gave 42.3-73.4 ms model inference across the same four images at `imgsz=640`.

Universal prompt stress profile, GPU auto device on the same workstation:

| Input | Detector evidence | SPPA tag | Runtime archetype | Confidence | Inference ms |
|---|---|---|---|---:|---:|
| Cyclist road image | `person + motorcycle` | `two_wheeled_rider` | `biker` | 0.422 | 11.7 |
| Mountain tower image | `electric pylon` | `power_tower` | `vertical_structure` | 0.458 | 11.4 |
| Mountain tractor image | `agricultural vehicle` | `farm_vehicle` | `farm_vehicle` | 0.522 | 37.2 |
| Tractor with trailer image | `vehicle` | `generic_vehicle` | `heavy_vehicle` | 0.471 | 36.2 |

Forced CPU with the universal prompt set gave 123.4-263.7 ms model inference. The CPU result is the clearest warning: broad prompt universality has a real runtime cost and should not be treated as the default flight configuration without target-hardware validation.

This is good enough for the SPPA argument: the detector does not need to identify every object at human-label specificity. It needs to provide compact evidence that SPPA can translate into a stable, conservative proxy class or an explicit unknown fallback.

## Claim boundary

The paper should not claim that YOLOE-26s solves universal object recognition or that the detector always recovers the exact object class. The defensible claim is:

> SPPA can consume compact semantic tags and regions from an edge-oriented open-vocabulary detector, normalize approximate and sometimes ambiguous labels into hierarchical reviewed proxy archetypes or conservative unknown fallbacks, and render lightweight 3D scene proxies when image-to-3D reconstruction is brittle, slow, or visually unstable.

## Sources

- Ultralytics YOLOE: https://docs.ultralytics.com/models/yoloe/
- Ultralytics YOLO26 / YOLOE-26: https://docs.ultralytics.com/models/yolo26/
- Ultralytics YOLO-World: https://docs.ultralytics.com/models/yolo-world/
- Grounding DINO 1.5: https://arxiv.org/html/2405.10300v1
