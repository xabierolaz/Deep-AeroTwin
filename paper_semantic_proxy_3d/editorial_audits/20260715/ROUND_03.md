# SPPA independent editorial audit - round 03: amended protocol and executable freeze

Date: 2026-07-15

Milestone: amended protocol, executable method/source/analysis package,
development-only data, and pre-test freeze. Scope requested was read-only.
Each worker was launched independently and was not shown another worker's
verdict.

## Artifacts offered for review

- `SPPA_PROTOCOL_AMENDMENT_01_20260715.md`;
- `SPPA_CONTRIBUTION_SELECTION_20260715.md`;
- `SPPA_CLAIM_EVIDENCE_MATRIX_20260715.md`;
- `reproducibility/sppa_mvfit/protocol_config.json`;
- `reproducibility/sppa_mvfit/method/`;
- `reproducibility/sppa_mvfit/source/`;
- `reproducibility/sppa_mvfit/benchmark/`;
- `reproducibility/sppa_mvfit/tests/`;
- `reproducibility/sppa_mvfit/results/development/`;
- `reproducibility/sppa_mvfit/pretest_freeze.json`, SHA-256
  `D752892AFC2040038B12666C325374D0E6E9342B687661DE39A617BD89F5D48A`.

No held-out test seed, test source, test observations, or confirmatory result
was present or disclosed.

## Worker attempts

Three new independent workers were requested for the mandatory roles:

1. hostile methodology/statistics;
2. clean-clone reproducibility;
3. target-journal editor.

All three attempts failed before reading the artifacts with the platform error:

`The 'gpt-5.6-sol' model is not supported when using Codex with a ChatGPT account.`

The attempts returned no scientific or editorial assessment. They are not
counted as reviewers, and their platform failure is not evidence for or against
the protocol.

## Consolidated verdict

**ROUND 03 IS INCOMPLETE AND FAILS THE EXTERNAL-AUDIT GATE.** There are zero
valid independent reviews, below the required three. Consequently:

- the protocol is not externally approved;
- the NIST-beacon test seed must not be fetched;
- held-out test data must not be generated;
- the development result must not be described as confirmatory;
- the manuscript and submission bundle must not be described as ready.

The exact external dependency is access to three functioning, independent,
read-only reviewers capable of examining the frozen artifacts, including one
clean-clone reproduction. When that dependency is available, the same frozen
snapshot must be reviewed before any test-seed derivation. Any P0 change after
review requires a new freeze and a new audit round.
