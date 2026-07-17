# SPPA submission handoff

Prepared: 2026-07-15

## Mission

Bring SPPA to the strongest honest submission package supported by reproducible
evidence. The provisional primary target is Advanced Engineering Informatics.
Journal of Geovisualization and Spatial Analysis is the strongest fast Q1
alternative if the final contribution is better framed and evaluated as
geovisualization. Do not submit merely because an internal precheck passes.

There is no guarantee of acceptance. The current independent editorial verdict
is REJECT. The new task must convert that verdict through evidence and
reproducibility, not by softening claims or adding defensive prose.

## Canonical workspace

- Repository root: `D:\Deep-AeroTwin-UE57-Test`
- Canonical paper directory: `D:\AYTE DOCTOR\SPPA_semantic_proxy_3d`
- Repository access path: `D:\Deep-AeroTwin-UE57-Test\paper_semantic_proxy_3d`
- The repository access path is a Windows junction to the canonical directory.
  Keep one canonical paper copy. Do not duplicate the paper directory.
- Current branch/commit: `main`, `9461d2b` (`Finalize SPPA paper and benchmark evidence`)

## Snapshot at handoff

- Worktree: dirty and not release-ready.
- Tracked modifications reported by `git diff --stat`: 39 files, about 8,959
  insertions and 2,992 deletions.
- Untracked files: 4,679.
- Git LFS reports an unpushed `Unreal/Content/SPPABenchmark.umap` object.
- `git fsck --no-reflogs` did not finish inside the 60-second diagnostic timeout;
  this is incomplete, not evidence of corruption.
- Main source: `semantic_proxy_3d_paper.tex`, 85,068 bytes before this handoff.
- Main PDF: 32 A4 pages, 4,963,128 bytes.
- Main figures directory: 22 files.
- Bibliography: 57 entries.
- Short submission supplement: 3 pages.
- Long technical supplement: 38 pages and explicitly not suitable as the formal
  supplement in its current diary/artifact-log form.

Current frozen hashes after the 2026-07-15 verification build:

- Main TeX SHA-256:
  `2303BD444730F8DCBCFB2FEEF9CB03CD7D4622B4A08A7571E01FC04DFCFB536E`
- Main PDF SHA-256:
  `2DC41D52A96B5956173304A9239D6201B0475D2D3F121483CC4BBE763C310D3B`
- Bibliography SHA-256:
  `16D6ABFAD7E3A9EED77D349640191510EE5334CEC5DF0FCDEA83EBD16C7EBC09`
- Short supplement PDF SHA-256:
  `63AFE132350E26C7151236E09C26577F5855A5CD4F28919CDA897F2575F6FEF9`

These hashes identify only this local snapshot. Rebuilds change the PDF hash and
must create a new release manifest.

## Verification already run

- `rtk python tools/sppa_sota_benchmark/verify_sppa_submission_precheck.py --strict`
  completed with zero internal blockers.
- `rtk powershell -NoProfile -ExecutionPolicy Bypass -File tools/verify_papers.ps1 -SkipPipelineB`
  passed and rebuilt the 32-page PDF.
- Python syntax checks for the core SPPA generator/benchmark scripts passed in
  the previous working session.
- PDF visual QA rendered all 32 pages to PNG and inspected a full contact sheet
  plus pages 10, 11, 12, 16, 18, 20, 22, and 25.

Important distinction: these checks show local consistency. They do not show
clean-clone reproducibility, novelty, statistical validity, or Q1 readiness.

## Current honest system statement

SPPA is one deterministic generator with two evidence modes:

1. Text/tag-only selects a reviewed semantic family/profile and prior
   dimensions.
2. Detector/metric/visual evidence can refine the same generator with bounded
   scale, pose, yaw, color, or generic image-space cues when those observations
   are available.

The runtime path does not call an LLM. Offline language/ontology assistance may
draft a recipe, but the present artifacts do not record a specific model,
prompt, response, or hash. Do not imply live question-answer anatomy generation.

YOLOE is an approximate open-vocabulary evidence source, not universal object
recognition. SPPA is not universal correct text-to-3D or image-to-3D. Unknown or
weak evidence must remain an explicit conservative fallback.

The user-supplied cyclist, tower, tractor, and tractor-trailer images are real
image inputs in the limited sense that they are not rendered by this pipeline.
Their flight telemetry, camera state, altitude, and metric dimensions are
declared replay assumptions, not measured flight telemetry. They have no 3D
ground truth. Never label the replay geometry as a real flight measurement.

The cow and every other text-only object must be generated from the declared
input through the shared generator. Do not hand-edit a class output, cherry-pick
an old mesh, or keep a legacy SPPA fallback hidden behind the current name.

## Independent audit baseline

Read before changing claims:

- `editorial_audits/20260715/ROUND_01.md`
- `editorial_audits/20260715/JOURNAL_SHORTLIST.md`

Round 01 found three classes of P0 blocker:

1. Scientific: no primary hypothesis/endpoint, no independent 3D/spatial ground
   truth, circular task-fit ranking, inadequate sample size, and no held-out
   open-set evaluation.
2. Reproducibility: dirty/non-portable workspace, ignored inputs/runs/weights,
   absolute environment paths, missing hashes/locks/raw timings, and no
   clean-clone reproduction command.
3. Integrity/presentation: at least one false bibliography identity, missing
   YOLOE citation, inconsistent main/supplement snapshots, and several figures
   unreadable at normal journal scale.

## Non-negotiable honesty rules

- Never invent flight, camera, telemetry, ground truth, timings, user-study
  observations, detector outputs, or journal metrics.
- `Real image`, `synthetic geometry`, `declared replay`, and `measured flight`
  are separate provenance states. Never collapse them.
- A visual audit is not a SOTA ranking.
- A consumed evidence channel is not a geometry-quality score.
- Synthetic projection inversion is a contract regression, not estimation
  accuracy.
- A reviewed/whitelisted label set is not universal open-vocabulary geometry.
- A clean proxy is not evidence of safety, operator benefit, or uncertainty
  calibration.
- Curated assets are allowed to win when they exist. SPPA addresses missing or
  mismatched assets.
- Do not preserve a result because it looks favorable. Preserve it only if its
  protocol, input contract, provenance, and raw data are auditable.

## Research redesign required before manuscript polishing

The first workstream is experimental design, not another narrative rewrite.

1. Write a preregistration-style protocol inside the repo with hypotheses,
   primary and secondary endpoints, exclusion rules, fixed cases/splits,
   baselines, repetitions, seeds, and failure criteria.
2. Remove or replace the circular 6/6 task-fit ranking.
3. Build a measured representation benchmark using equivalent input contracts.
   At minimum include bbox, capsule/ellipsoid, billboard, curated low-poly asset
   where available, a simple non-semantic procedural proxy, and SPPA.
4. Separate four tasks:
   - semantic normalization/fallback correctness;
   - geometry/footprint approximation;
   - runtime, memory, draw-call, and update persistence;
   - human interpretation, only if a human-factors claim remains.
5. Freeze a held-out dataset. Prefer a licensable public UAV/aerial dataset plus
   a simulator or measured source with valid metric/pose ground truth. Do not
   retrofit the four development images as held-out evidence.
6. Add independent repeated runs, raw data, confidence intervals, failure cases,
   and hardware/environment metadata.
7. Decide whether the ambitious contribution is:
   - a genuine generic silhouette/multiview primitive-fitting algorithm;
   - a calibrated representation-selection policy under uncertainty/budget;
   - or a public semantic-telemetry-to-actor benchmark.
   Do not claim all three without implementing and evaluating them.

If live flight, operator study, or new ground truth cannot be obtained, narrow
the paper and target accordingly. Do not manufacture substitutes.

## Reproducibility release gate

Before calling the paper submission-ready:

- Create a clean release branch/tag from the exact reviewed workspace.
- Version all necessary TeX, figures, tables, scripts, manifests, and small raw
  data. Put large legal artifacts in LFS or a DOI-backed archive.
- Record origin, license, capture/source date, and SHA-256 for every image,
  weight, model, executable, PAK, and baseline output used in a paper result.
- Pin baseline repository commit, model revision, Python, package lock, Torch,
  CUDA, driver, hardware, prompt, seed, and command.
- Replace absolute user/machine paths with relative configuration.
- Preserve raw timing samples required to recompute every reported percentile.
- Add `tools/reproduce_sppa_paper.ps1 -Strict` and run it from a clean clone.
- Add CI checks for dirty state, absolute paths, missing provenance, stale
  figures, inconsistent snapshots, hash drift, and PDF build failure.
- Produce a release manifest that maps every table cell and figure to its raw
  artifact and generating command.

## Manuscript and submission gate

After the evidence freeze:

- Choose one target journal and adapt the paper to its exact current guide.
- Rebuild the abstract around the tested hypothesis and measured primary result.
- Remove unsupported `useful`, `safety-oriented`, universal, and SOTA language.
- Correct every critical reference and verify all 57 entries against primary
  sources. Add YOLOE and current directly related work.
- Reconcile every repeated number between main paper, short supplement, long
  artifact log, README, and generated reports.
- Redesign multi-panel figures so all text and relevant geometry are legible at
  final print width. Pages 11, 20, and 22 are the first known failures.
- Add keywords, data/code availability, funding, competing interests, author
  contributions, AI-use disclosure as required, ethics/consent if applicable,
  and an anonymous title-page workflow.
- Create a target-specific cover letter and submission checklist.
- Render the final PDF page by page after every meaningful manuscript update.

## External editor protocol

Run independent audits at these milestones:

1. Protocol freeze.
2. Dataset and baseline freeze.
3. Results freeze.
4. Full manuscript rewrite.
5. Final submission bundle.

At each milestone spawn at least three read-only workers with disjoint roles:

- hostile methodology/statistics reviewer;
- reproducibility/artifact reviewer using clean-clone criteria;
- target-journal editor checking scope, novelty, policy, and presentation.

For literature-heavy milestones add a fourth bibliography-integrity reviewer.
Workers must not edit files, must cite file/line evidence, must declare
incomplete checks, and should not see one another's verdict before submitting.
Store each round under `editorial_audits/YYYYMMDD/ROUND_NN.md`.

Do not declare readiness while any worker reports a P0 issue. A major issue may
be accepted only if the manuscript explicitly removes the affected claim and
the target editor agrees that the narrowed paper remains publishable.

## Provisional journal strategy

Primary: Advanced Engineering Informatics, conditional on a real knowledge-
representation contribution and rigorous generality/scalability experiments.

Alternative: Journal of Geovisualization and Spatial Analysis, conditional on a
measured spatial/geovisualization task. Its exact Springer/CRUE eligibility,
UPNA impact row, JIF, continuous publication, and official six-day median first
decision were checked on 2026-07-15.

See `editorial_audits/20260715/JOURNAL_SHORTLIST.md` for the evidence and
submission-day checks. Confirm final APC eligibility with the UPNA library;
publisher agreements and capacity can change.

## Immediate execution order for the new task

1. Read this handoff and both round-01 audit files.
2. Reinspect `git status`, ignored evidence, and all current snapshot
   inconsistencies without deleting or reverting user work.
3. Create the preregistration-style experimental protocol and a claim-to-
   evidence matrix.
4. Decide the single strongest implementable novelty path based on available
   ground truth and compute; record why alternatives were rejected.
5. Implement the benchmark/algorithm and continuously test it against the
   preregistered endpoints.
6. Run the next independent audit before rewriting the results narrative.
7. Build the clean reproduction package, then the target-specific manuscript
   and final submission bundle.

Do not stop at a plan. Continue through implementation, verification, external
audit, manuscript regeneration, PDF visual QA, and a final honest readiness
decision. If completion becomes impossible only because genuinely new physical
data, author identity, ethics approval, or institutional confirmation is
required, finish every non-blocked artifact and document the exact external
dependency without fabricating it.
