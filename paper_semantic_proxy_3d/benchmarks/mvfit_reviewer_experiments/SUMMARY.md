# SUMMARY — mvfit reviewer experiments

**Scope:** six exploratory post-hoc analyses (not confirmatory) around the
sealed SPPA-MVFit held-out benchmark. Everything lives under
`benchmarks/mvfit_reviewer_experiments/`; the sealed package
(`reproducibility/sppa_mvfit/`) was only ever read or imported — never
written, never re-run. All configuration changes were in-memory
monkeypatches, documented per experiment.

**Common protocol:** n = 240 held-out actors (6 families × 2 strata × 20),
clean condition, voxel IoU at 64³ vs `voxelize_source` GT; stratified paired
bootstrap, cells (family, stratum), 10 000 resamples, seed 77157 (the sealed
analysis scheme). Every script that recomputes a sealed quantity validated it
bit-exactly against `results/test/raw_metrics.csv` first (max abs err 0.0).

Anchors (sealed, confirmed): SPPA-MVFit 0.557 · Generic-MVFit 0.367 ·
visual hull 0.522 · AABB 0.248.

## E1 — Wrong-family token (PRIORITY) ✅

240 actors × 6 tokens = 1 440 fits (1 200 off-diagonal), deterministic.

| Variant | Mean IoU |
|---|---|
| Correct token (= sealed SPPA) | 0.557 |
| **Wrong token (mean of 5)** | **0.205** |
| Wrong token (best of 5 per actor) | 0.361 |
| Generic-MVFit | 0.367 |

- **Wrong − generic = −0.162 [CI95 −0.167, −0.158], p < 1e-4** — a wrong
  family token is far worse than NO family prior. 98.3 % of actors fall below
  their own generic fit; even the per-actor *best* wrong token (0.361) does
  not beat generic on average.
- Wrong − correct = −0.353 [−0.362, −0.343]. Holds in both strata
  (csg_id −0.144, implicit_ood −0.181).
- 6×6 matrix strongly diagonal-dominant; worst confusions: compact →
  branching_vertical 0.063, branching → rider_cycle 0.060.

## E2 — View ablation (top-only / side-only) ✅

Replica of the frozen optimizer with single-view objectives + single-view
init (isotropic prior for the unobserved axis), correct family token, n=240.

| Fit | Mean IoU | Δ vs dual | CI95 |
|---|---|---|---|
| Dual (= sealed) | 0.557 | — | — |
| Top-only | 0.458 | −0.100 | [−0.112, −0.088], p < 1e-4 |
| Side-only | 0.545 | −0.012 | [−0.021, −0.004], p = 0.006 |

Strong asymmetry: the side (x–z) view carries most 3D information; the top
view still adds a small significant increment — the 0.5/0.5 objective is
justified post-hoc.

## E3 — OBB baseline ✅

`cv2.minAreaRect` on the top silhouette + gap-midpoint support refinement +
z from the side mask, analytic voxelization; self-check on a known-yaw box:
reconstruction IoU 0.948 (threshold 0.90).

| Method | Mean IoU |
|---|---|
| AABB (sealed) | 0.248 |
| **OBB (new)** | **0.252** |
| Visual hull (sealed) | 0.522 |
| SPPA-MVFit (sealed) | 0.557 |

OBB − AABB = +0.004 [0.003, 0.005] (actors are axis-aligned by construction,
so orientation buys nothing); SPPA − OBB = +0.306 [0.297, 0.314]. A stronger
geometric box prior is not a competitive alternative. Median 0.43 ms/case.

## E4 — Optimizer budget sweep ✅

In-memory `STEP_FRACTIONS` patch (budget-31 arm validated bit-exact vs seal).

| Budget | Mean IoU | Mean ms |
|---|---|---|
| 11 | 0.528 | 3.57 |
| 21 | 0.547 | 7.59 |
| 31 (sealed) | 0.557 | 12.57 |
| 61 | 0.560 | 24.03 |

61 − 31 = +0.003 [−0.001, +0.006], p = 0.108 (n.s.); 11 − 31 = −0.029 and
21 − 31 = −0.011 (both significant). The sealed budget sits exactly at the
knee — defensible accuracy/latency point.

## E5 — Generic-graph sensitivity ✅

Design criteria frozen in `GENERIC_VARIANTS.md` BEFORE measurement; three
pre-registered variants (G2 box/cylinder chassis, G3 vertical stack + legs,
G4 slot-wise family mean, rule-reverified against `graphs.json`).

| Variant | Mean IoU | Δ SPPA − variant | Gap closed |
|---|---|---|---|
| G1 sealed generic | 0.367 | 0.190 | — |
| G2 | 0.339 | 0.219 | −15.2 % |
| G3 | 0.282 | 0.276 | −45.0 % |
| G4 | 0.330 | 0.228 | −19.8 % |

**Surprise:** every alternative generic is significantly *worse* than the
sealed one (p < 1e-4). Family-shaped generics help the families they resemble
(G2 wins on both vehicle families) and hurt the rest; the symmetric ellipsoid
generic is already the best single compromise.

## E6 — Role-aware IoU ✅

Mapping frozen ex-ante (`ROLE_MAPPING_FROZEN.md`); restricted to csg_id
(120 actors, 920 matched pairs); sealed θ, no refitting.

- Overall role coverage 0.545, role IoU 0.319.
- Controls: cyclic shuffle 0.017, random shuffle 0.053 → true − random =
  **+0.265 [+0.250, +0.281], p < 1e-4** — slot-role alignment is real.
- Best aligned: quadruped 0.423, compact 0.413; weakest: branching_vertical
  0.187, lattice_tower 0.231 — matching the global family difficulty ranking.

## Answers to the two reviewer questions

**(a) Does a wrong family token hurt more than the generic graph?**
Yes, decisively. Wrong-token mean IoU 0.205 vs generic 0.367: paired
Δ = −0.162, CI95 [−0.167, −0.158], p < 1e-4, n = 240 (1 200 wrong fits).
98.3 % of actors are worse with a wrong token than with no family prior, and
even the best-of-5 wrong tokens (0.361) stays below generic. The risk of
family-token errors is therefore asymmetric and severe — motivation for
token-uncertainty handling, not a benign degradation.

**(b) How much does the Δ fall with better-designed generic graphs?**
It does not fall — it grows. Across three pre-registered alternative generic
designs, Δ(SPPA − generic) ranges 0.219–0.276 vs the sealed 0.190, i.e., the
gap *closes* by a negative amount (−15 % to −45 %). The hand-crafted
symmetric-ellipsoid generic is already the strongest of the four candidates
tested, so the reported SPPA advantage is, if anything, conservative.

## Surprises worth a sentence in the paper

1. Wrong-token collapse is *below* the no-prior floor (E1) — prior errors are
   not graceful.
2. Side-view-only nearly matches dual-view (E2) — view contribution is
   strongly asymmetric.
3. Orientation-aware boxes add ~nothing over AABB here (E3) — SPPA's margin
   is structural, not orientational.
4. The budget curve's knee is exactly the sealed 31 (E4).
5. Alternative generics make the gap *larger* (E5) — the baseline is strong,
   not weak.
6. Role alignment is far above chance but family-dependent (E6) — supports
   the "semantic proxy" claim descriptively.

## Pending / limitations

- E1–E5 cover the clean condition only (as tasked); corrupted-condition
  versions of E1 are a natural extension.
- E6 restricted to csg_id by ex-ante decision; implicit_ood role mapping was
  judged not defensible and remains open.
- No new seeds beyond the fixed bootstrap seed (mirrors the seal).
- Timing numbers (E3/E4) are wall-clock on this machine, not sealed.

## Reproduce

Each folder `e1_…`–`e6_…` contains its runner, JSON payload, booktabs `.tex`
and README. Run from `benchmarks/mvfit_reviewer_experiments/` with the user
Python 3.12, e.g.:
`PYTHONUTF8=1 python e1_wrong_family/run_e1_wrong_family.py`
