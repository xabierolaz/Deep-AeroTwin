# SPPA Agnostic Image-Space Probe Verification

- Status: pass
- Rows checked: 4
- Failures: 0

| Case | Scope | Pair score | Coherent lines | Multi-orientation lines | Status |
|---|---|---:|---:|---:|---|
| biker | round_part_pair_candidate | 0.9390 | true | true | pass |
| tower | multi_line_structure_candidate | 0.0000 | true | false | pass |
| tractor | round_part_pair_candidate | 0.9437 | false | false | pass |
| tractor_trailer | multi_line_structure_candidate | 0.2079 | true | false | pass |

## Boundary

This verification checks that the image-space fitter declares no semantic label input and that strong primitive claims are backed by their own geometry metrics.
