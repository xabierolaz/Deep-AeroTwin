# SPPA independent editorial audit - round 02: protocol freeze

Date: 2026-07-15

Milestone: initial protocol, claim-to-evidence matrix, and contribution
selection. Scope was read-only. Reviewers were instructed not to edit files and
were not shown another reviewer's verdict before returning their own.

## Artifacts reviewed

- `SPPA_PREREGISTRATION_20260715.md`, SHA-256
  `513747BB801E089F75E305DCF7D0A751953DC4D2CB924F6CD3317E529B86AB7F`;
- `SPPA_CONTRIBUTION_SELECTION_20260715.md`, SHA-256
  `DED3807F97DDB0ABB6F0B903F8C6A1E34CAE76197A461EF0DE6D6BAD71337CDA`;
- `SPPA_CLAIM_EVIDENCE_MATRIX_20260715.md`, SHA-256
  `14089A8EEEFF84C1057D5EB6F8D11822D2CCFEDDB6C61EDD872F36000DAE76AA`;
- round-01 audit and journal shortlist.

## Valid independent verdicts

### Hostile methodology/statistics reviewer: MAJOR

P0 findings:

1. The method, source distributions, corruptions, optimizer, baselines, and
   voxelizer were not executable or frozen when the prose protocol was hashed
   (`SPPA_PREREGISTRATION_20260715.md:17-24`, `121-130`, `159-163`).
2. A union-of-primitives GT generator and a primitive actor remain structurally
   model-matched even when placed in separate files; an OOD generator using a
   different representation is required (`SPPA_PREREGISTRATION_20260715.md:68-87`).
3. Published test seeds plus generation of GT before the method hash permit
   human leakage (`SPPA_PREREGISTRATION_20260715.md:89-102`, `214-221`).
4. Selecting the best comparator on test excludes eligible semantic/template
   baselines and invalidates an ordinary paired interval after selection
   (`SPPA_PREREGISTRATION_20260715.md:52-57`, `143-152`).
5. The primary 64-cubed grid lacks an exact domain, rasterization, clipping,
   empty-case, and aliasing contract (`SPPA_PREREGISTRATION_20260715.md:159-163`).

P1 findings included no prospective power/MDE rationale, ambiguity between a
positive-effect hypothesis and a +0.030 superiority margin, an arbitrary equal
mixture of clean/corrupt conditions, insufficient timing policy, unspecified
bootstrap interval type, unsupported `class-agnostic` wording, and an
uncertainty output without calibration endpoint.

The reviewer explicitly accepted the actor-level analysis unit, paired
falsifiable endpoint, no data-dependent exclusions, removal of the circular
ranking, and strict provenance/claim boundaries.

Incomplete checks: no implementation, GT independence, method identity,
baseline equivalence, hashes, raw timing, or result could yet be verified.

### Target-journal editor: REJECT

P0 findings:

1. H1 compares a mask-consuming method with a template that ignores the masks;
   it is an information ablation, not sufficient competitive evidence
   (`SPPA_PREREGISTRATION_20260715.md:36-48`, `115-119`). A preselected
   input-matched, equal-budget nonsemantic optimizer is required.
2. `strongest non-oracle baseline` is false when candidates are omitted, and
   post-selection inference on test is invalid
   (`SPPA_PREREGISTRATION_20260715.md:52-57`, `143-148`).
3. A method using family tokens and family-specific graphs is
   family-conditioned, not class-agnostic (`SPPA_PREREGISTRATION_20260715.md:17-24`,
   `75-87`, `109-119`). A primary-source prior-art matrix is required.
4. Developer-held-out synthetic unions of solids do not establish external
   engineering or geospatial validity (`SPPA_PREREGISTRATION_20260715.md:68-105`,
   `234-238`). A structurally different OOD generator is the minimum internal
   repair; a real metric task remains necessary for strong target fit.
5. Objective, bounds, initialization, stopping, parameter semantics, and source
   distributions were not frozen (`SPPA_PREREGISTRATION_20260715.md:17-24`,
   `68-70`, `214-226`).
6. Neither provisional journal currently meets its own hard fit condition:
   AEI lacks measured engineering value/generalization and JGSA lacks a real
   geospatial task (`JOURNAL_SHORTLIST.md:44-50`, `63-67`).

P1 findings included missing power justification, mandatory clean-stratum
reporting, no equal-budget nonsemantic fitting baseline, incomplete voxel-grid
definition, unevaluated uncertainty, and insufficient cold/warm/scaling timing.

The editor explicitly accepted falsifiability, actor-level inference, removal
of the circular ranking, claim/provenance limits, and prospective rerun rules.

Incomplete checks: no implementation, results, clean clone, bibliography,
figures, PDF, or current web policy was verified.

## Invalid worker attempts and audit completeness

The reproducibility/clean-clone role did not return a scientific review. Five
attempts (`protocol_reproducibility`, `protocol_reproducibility_b`,
`protocol_artifact`, `protocol_cleanclone`, and an isolated subworker request)
failed before reading files with the platform error:

`The 'gpt-5.6-sol' model is not supported when using Codex with a ChatGPT account.`

These attempts are not counted as reviewers and their failure is not evidence
about the paper.

## Consolidated verdict

**ROUND 02 FAILS.** It contains only two valid independent reviews, below the
required three, and both report P0 blockers. No held-out test may be executed
from this protocol snapshot.

Required exit work:

- preserve the original protocol and create an explicit amendment;
- make the primary comparator input-matched and equal-budget;
- preselect comparisons before test and specify simultaneous inference;
- use family-conditioned wording;
- add a structurally different OOD synthetic stratum;
- freeze exact source distributions, observations, fitting algorithm, metrics,
  power rationale, and timing policy;
- freeze method/analysis before deriving test seeds;
- rerun the protocol milestone with at least three valid read-only workers,
  including a clean-clone reviewer.

