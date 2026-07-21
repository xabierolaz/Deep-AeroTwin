# SPPA open-vocabulary detector probe

- Profile: `yoloe26s_universal_prompt_probe`
- Model: `yoloe-26s-seg.pt`
- Ultralytics task: `segment`
- Image size: `640`
- Confidence: `0.05`
- Device requested: `cpu`
- CUDA available: `True`
- CUDA device: `None`

## Results

| Image | Detections | Detector evidence | SPPA tag | Runtime archetype | Confidence | Elapsed ms | Model inference ms | Annotation |
|---|---:|---|---|---|---:|---:|---:|---|
| `rea_flight_data/real_photos/tower.png` | 1 | `electric pylon` | `power_tower` | `vertical_structure` | 0.490 | 59.7 | 52.9 | `experiments/sppa_detection_reference/20260721_real_flight_photos_yoloe26s_cpu/tower_yoloe26s_open_vocab.png` |
| `rea_flight_data/real_photos/tractor.png` | 2 | `two-wheeled vehicle` | `generic_vehicle` | `heavy_vehicle` | 0.479 | 60.0 | 53.4 | `experiments/sppa_detection_reference/20260721_real_flight_photos_yoloe26s_cpu/tractor_yoloe26s_open_vocab.png` |

## Claim Boundary

Broad prompt stress-test for SPPA. It is useful for showing approximate universal semantic intake, but it is not the preferred flight profile because broader vocabularies can increase latency and false-positive opportunities. SPPA must normalize weak labels into reviewed family proxies or unknown conservative fallback geometry.

## Prompt Classes

`person`, `cyclist`, `bicycle`, `two-wheeled vehicle`, `motorcycle`, `vehicle`, `car`, `truck`, `bus`, `van`, `pickup truck`, `tractor`, `agricultural vehicle`, `trailer`, `construction vehicle`, `excavator`, `bulldozer`, `forklift`, `crane`, `power transmission tower`, `electric pylon`, `utility pole`, `antenna tower`, `road sign`, `building`, `house`, `barn`, `shed`, `warehouse`, `bridge`, `wall`, `fence`, `cow`, `cattle`, `horse`, `dog`, `sheep`, `animal`, `tree`, `bush`, `vegetation`, `rock`, `boulder`, `container`, `shipping container`, `water tank`, `barrel`, `traffic cone`, `drone`, `quadcopter`, `UAV`, `hay bale`
