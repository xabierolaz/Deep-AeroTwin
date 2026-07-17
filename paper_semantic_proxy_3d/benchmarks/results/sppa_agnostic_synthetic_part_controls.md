# SPPA Agnostic Synthetic Part Controls

Synthetic controls for the agnostic image-space primitive-cue fitter. They test primitive-cue behavior under known geometry, not detector quality or real-world semantic correctness.

- Status: pass
- Controls: 5
- Failures: 0

| Case | Expected | Scope | Round pairs | Strong pairs | Line structure | Edge density | Status |
|---|---|---|---:|---:|---:|---:|---|
| synthetic_round_pair | round_part_pair_candidate | round_part_pair_candidate | 1 | 1 | true | 0.03794 | pass |
| synthetic_elongated_round_pair | round_part_pair_candidate | round_part_pair_candidate | 4 | 3 | true | 0.06587 | pass |
| synthetic_line_structure | multi_line_structure_candidate | multi_line_structure_candidate | 0 | 0 | true | 0.11967 | pass |
| synthetic_blank_mask_negative | not round_part_pair_candidate,multi_line_structure_candidate | mask_envelope_only | 0 | 0 | false | 0.00000 | pass |
| synthetic_texture_negative | not round_part_pair_candidate | mask_envelope_only | 0 | 0 | false | 0.00000 | pass |

## Interpretation

These are synthetic geometry controls, not detector benchmarks. They evaluate whether the agnostic image-space fitter responds to known primitive evidence and avoids strong part claims on blank or texture-only masks, without semantic labels.
