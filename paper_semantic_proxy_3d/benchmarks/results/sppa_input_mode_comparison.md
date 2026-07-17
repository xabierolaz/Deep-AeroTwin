# SPPA Input Mode Comparison

This compares the same deterministic SPPA generator under three input contracts. Text-only uses a reviewed tag and no image. Detector modes use real YOLOE text plus declared metric replay; the visual mode adds agnostic image-space cues. It is not 3D ground truth, not measured flight localization, and not a visual SOTA leaderboard.

- Cases: 4
- Visual rows with applied visual evidence: 4/4
- Visual rows with shape conditioning: 4/4
- Visual rows with geometry delta vs detector+metric: 4/4
- Detector+metric rows with geometry delta vs text-only: 4/4
- Max wall time: 5.840 ms
- Max triangles: 1988
- Max descriptor bytes: 32287

| Case | Mode | Semantic label | Scale source | Dims m | Visual shape | Geom delta vs text | Geom delta vs metric | Tris | Wall ms |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| biker | text/tag only | biker | prior | 1.70x0.60x1.85 | False | False | True | 1036 | 5.840 |
| biker | YOLOE + metric | biker | vehicle-fused | 1.85x0.73x1.85 | False | True | False | 1036 | 2.355 |
| biker | YOLOE + metric + visual | biker | vehicle-fused | 1.85x0.73x1.85 | True | True | True | 1056 | 3.023 |
| tower | text/tag only | tower | prior | 1.20x1.20x6.00 | False | False | True | 396 | 1.561 |
| tower | YOLOE + metric | vertical_structure | height-fused | 5.60x2.89x28.00 | False | True | False | 396 | 3.047 |
| tower | YOLOE + metric + visual | vertical_structure | height-fused | 5.60x2.89x28.00 | True | True | True | 436 | 1.640 |
| tractor | text/tag only | tractor | prior | 3.80x2.00x2.40 | False | False | True | 1056 | 2.394 |
| tractor | YOLOE + metric | farm_vehicle | vehicle-fused | 4.52x2.38x2.60 | False | True | False | 1056 | 2.491 |
| tractor | YOLOE + metric + visual | farm_vehicle | vehicle-fused | 4.52x2.38x2.60 | True | True | True | 1096 | 2.702 |
| tractor_trailer | text/tag only | tractor_trailer | prior | 7.60x2.15x2.70 | False | False | True | 1988 | 3.490 |
| tractor_trailer | YOLOE + metric | articulated_vehicle | vehicle-fused | 13.98x3.54x3.40 | False | True | False | 1848 | 3.074 |
| tractor_trailer | YOLOE + metric + visual | articulated_vehicle | vehicle-fused | 13.98x3.54x3.40 | True | True | True | 1872 | 3.256 |
