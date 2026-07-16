# SPPA protocol amendment 01

Amendment date: 2026-07-15

Reason: round-02 protocol audit reported P0 flaws. This file supersedes the
affected clauses prospectively. It does not modify or erase the original
protocol. No held-out test was generated or executed before this amendment.

## A1. Revised scientific question and terminology

The method is renamed **family-conditioned SPPA-MVFit**. `Class-agnostic`,
`open-set fitting`, and `general primitive fitting` are prohibited descriptions.

Revised question: when two representations receive identical calibrated top
and side silhouettes, the same five tunable parameters, the same initialization
rule, and the same optimization budget, does a frozen semantic-family part
graph improve 3D occupancy over an eight-part nonsemantic graph?

The knowledge representation under test is the family-conditioned part graph.
The optimizer itself is deliberately simple and is not claimed as a novel
primitive-fitting algorithm.

## A2. Revised hypotheses and estimands

### H1: confirmatory input-matched comparison

Comparator: `generic_mvfit`, an eight-part family-independent graph fitted with
the identical optimizer, parameter count, objective, bounds, initialization,
and 31-candidate budget as `sppa_mvfit`.

Primary observations are **clean masks only**. The analysis unit is one source
actor. The test contains 240 actors: 20 per family in each of two source strata.

For actor `i`, let `d_i` be clean 64-cubed voxel IoU of `sppa_mvfit` minus clean
voxel IoU of `generic_mvfit`. The confirmatory hypotheses are:

- H0: population mean paired difference is less than or equal to +0.030;
- H1: population mean paired difference is greater than +0.030.

The superiority claim passes only if the lower endpoint of a two-sided 95%
stratified actor-bootstrap percentile interval exceeds +0.030. Resampling is
within the 12 family-by-source strata, with equal stratum weight, 10,000
resamples, and seed 77157. Ties are retained. Non-finite/exception outputs score
IoU zero.

The +0.030 margin is the prespecified minimum practically relevant improvement:
on a 64-cubed grid it is larger than the expected one-voxel boundary sensitivity
established by the resolution check in A7. With paired-difference SD 0.12, 240
actors provide approximately 90% normal-approximation power to distinguish a
true mean +0.055 from the +0.030 margin at the two-sided 95% interval rule. The
achieved development SD will be reported before test but will not change n,
margin, or the decision rule.

### H2: shared-generator evidence ablation

`sppa_mvfit` versus `sppa_text_only` is secondary. It tests the addition of
silhouette evidence to the same family graph and shared actor generator. It is
not the competitive primary endpoint.

### H3: other representations

All pairwise clean-IoU differences between `sppa_mvfit` and the prespecified
`bbox`, `ellipsoid`, `capsule`, `billboard`, `nonsemantic_visual_hull`, and
`sppa_text_only` baselines receive stratified paired percentile intervals with
Holm correction across this family of six comparisons. No comparator is chosen
after inspecting test means. Visual hull is treated as a high-complexity
geometry reference, not a lightweight actor.

### H4: local cost

The original warm CPU thresholds remain secondary engineering gates. For every
timed method/case, the statistic is the median of 20 recorded warm calls after
five warm-ups. Aggregate median and p95 are taken across the 60 prespecified
actor medians, not across pooled calls. Raw calls are retained. Method order is
rotated deterministically by case. The log records logical/physical cores,
affinity, power plan when queryable, background process count, Python/packages,
and resolution. One fresh-process cold call per timed actor is reported
descriptively. Scaling runs at fitting grids 32, 48, and 64 and at 4, 8, and 12
primitives are descriptive.

## A3. Source strata and OOD boundary

The 240-actor test is balanced across six morphology families and two source
strata:

1. `csg_id`: unions of boxes, ellipsoids, and finite cylinders with sampled
   family topology;
2. `implicit_ood`: occupancy from superelliptic profile extrusions, taper/twist,
   toroidal sections, and spline-distance tubes. It must not import, call, or
   reuse any SPPA/template builder or CSG source primitive list.

Development contains 144 `csg_id` actors (24 per family). No `implicit_ood`
actor is used to choose optimizer constants. Test contains 120 actors from each
source stratum (20 per family). H1 is reported in aggregate with equal stratum
weight and separately for both strata. Passing the aggregate while the OOD
stratum's point estimate is non-positive is explicitly reported and prohibits a
cross-generator generalization claim.

Source and SPPA modules may share only the metric coordinate convention and
binary array schema. A static verifier rejects imports between the two module
trees and hashes both trees separately.

This remains synthetic internal evidence. It does not establish real-world or
geospatial validity.

## A4. Test-seed leakage control

Development seeds remain 110000--110143. Literal test seeds in the original
protocol are withdrawn before use and were never generated.

The complete method, templates, baselines, metric code, analysis, environment
lock, and development report are frozen and hashed first. Test seeds are then
derived from a public NIST Randomness Beacon pulse obtained after that freeze:

`seed_i = uint64(SHA256(pulse_output || "SPPA-MVFIT-20260715" || i)[0:8])`

for ordered case index `i`. The pulse URL, timestamp, signature status, raw JSON,
SHA-256, method freeze hash, and derivation script are stored. The test command
first writes a sealed method-output table, then releases GT to the evaluator.
The seed source prevents case-specific tuning before the method freeze; it does
not make the known source distributions externally blinded.

## A5. Exact observation contract

World/evaluation domain, shared by every source and method:

- x (length): [-4.8, +4.8] m;
- y (width): [-3.2, +3.2] m;
- z (height): [0.0, 6.4] m.

Input masks are 96x96 orthographic binary arrays sampled at cell centers over
the corresponding full-domain top (x,y) and side (x,z) rectangles. A pixel is
occupied when any 256-cubed source supersample within its ray is occupied, then
the mask is downsampled by max pooling. This renderer is source-only and is not
used to render SPPA candidates.

Primary input is the clean mask. Secondary deterministic perturbations are:

- `mild_morphology`: one binary erosion or dilation, choice from case hash,
  3x3 square element;
- `moderate_morphology`: two iterations with the same rule;
- `partial_occlusion`: zero a case-hash-selected rectangle covering 12% of the
  occupied-mask bounding-box area, constrained to intersect occupancy;
- `mask_corruption`: flip 0.5% of bounding-box pixels and add one filled radius-2
  false component outside the largest component, using the case seed.

Perturbations are applied independently to top and side masks. Empty perturbed
masks are valid and produce a recorded method failure, never exclusion.

## A6. Frozen family graphs and optimizer

Every semantic family graph and the nonsemantic graph contains exactly eight
primitive slots. Slots are axis-aligned boxes, ellipsoids, or finite cylinders
with frozen normalized centers, dimensions, type, and a binary
`secondary_group` flag. Graph files, not code branches, contain all
family-specific structure. Text-only and MVFit call the same
`build_actor(graph, theta)` function; MVFit changes only `theta`.

The five parameters are:

1. `log_scale_x` in [log(0.55), log(1.80)];
2. `log_scale_y` in [log(0.55), log(1.80)];
3. `log_scale_z` in [log(0.55), log(1.80)];
4. `secondary_scale` in [0.65, 1.35];
5. `secondary_offset_x` in [-0.35, +0.35] normalized actor length.

Initialization sets the three log scales from robust largest-component mask
extents divided by the graph's default extents, clipped to bounds;
`secondary_scale=1` and `secondary_offset_x=0`. Empty masks use the default
vector and set `empty_observation=true`.

Candidates are rendered on a 48-cubed fixed world grid. The minimized objective
is

`0.5*(1-IoU_top) + 0.5*(1-IoU_side) + 0.01*sum(log_scale^2) + 0.005*(secondary_scale-1)^2 + 0.005*secondary_offset_x^2`.

Deterministic coordinate search evaluates the initialization once, then in
parameter order evaluates minus and plus steps at normalized bound fractions
0.20, 0.10, and 0.05, accepting the lowest objective after each coordinate.
The total budget is 31 candidates. Ties within 1e-12 choose the smaller
regularizer, then the lexicographically smaller parameter vector. No stochastic
search or uncertainty output is used or claimed.

`generic_mvfit` uses the same builder, five parameters, initialization,
objective, and 31-candidate search, with one frozen eight-slot graph for all
families and no access to the family token.

## A7. Exact evaluation metrics

Evaluation occupancy uses the fixed A5 world domain at 64x64x64 cell centers.
A cell is occupied when its center is inside any predicted primitive/source
implicit field. Predictions are bounded by A6 and the source distributions are
validated to lie inside A5; no clipping-dependent case is permitted. Empty/empty
IoU is 1; exactly one empty is 0. BEV is max occupancy over z.

Surface voxels are occupied cells with at least one 6-connected empty or
out-of-domain neighbor. Symmetric Chamfer is the mean of each surface's nearest
cell-center distance to the other surface, averaged in both directions and
divided by the A5 domain diagonal. Empty-surface cases score diagonal distance.

Four held-out silhouette views are side projections after nearest-neighbor
rotations about z at azimuth 45, 135, 225, and 315 degrees. They are secondary.
Volume, containment, and robustness definitions in the original protocol are
retained but secondary/exploratory.

Resolution sensitivity recomputes clean voxel IoU at 48, 64, and 80 cubed on a
prespecified 60-actor stratified subset. The +0.030 practical margin is valid
only if the maximum absolute method-difference change between 64 and 80 is below
0.015; otherwise H1 is reported as resolution-sensitive and cannot support the
central claim even if its interval passes.

## A8. Baseline access and complexity

Every method receives the case id, clean/perturbed top and side masks, world
calibration, and family token. `generic_mvfit`, bbox, ellipsoid, capsule,
billboard, and visual hull ignore the token by definition. `sppa_text_only`
ignores masks. Access differences are explicit ablations, not hidden input
equivalence.

`curated_family_template` is removed as a separate row because it is identical
to `sppa_text_only`; the alias is recorded once in metadata.

`lightweight` is descriptive only for outputs with at most 12 primitives, 2,000
triangle-equivalents under the frozen tessellation, and a serialized descriptor
under 8 KiB. Visual hull is outside that category. Geometry and cost remain
separate tables; no weighted score or ordinal task-fit rank is permitted.

## A9. Freeze and rerun policy

Before any test pulse is fetched, the release writes an immutable freeze record
containing SHA-256 for this amendment, source modules/configs, SPPA modules and
graphs, baseline/metric/analysis code, environment lock, development raw data
and report, and repository diff snapshot. The record is timestamped and copied
unchanged into the final manifest.

Any code or parameter change after the pulse invalidates confirmatory status.
An implementation failure may be corrected only by preserving the failed run,
adding a regression test and explicit amendment 02, and labeling the corrected
run post-confirmatory. An unfavorable valid result is never rerun.

## A10. Journal gate

Neither AEI nor JGSA is approved by this amendment. Even a passing synthetic
test leaves external validity unresolved. The final bundle must either add an
independent real metric task obtained without fabrication or choose a journal
whose scope accepts a narrowly bounded synthetic representation study. Target
fit is an editorial gate, not something H1 can prove.

