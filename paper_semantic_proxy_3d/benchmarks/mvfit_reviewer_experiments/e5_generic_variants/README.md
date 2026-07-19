# E5 — Generic-graph design sensitivity

**Label:** exploratory post-hoc analysis (not confirmatory).

## Question

The sealed generic graph (8 symmetric ellipsoids) is hand-crafted. Reviewer
question: how much of the SPPA−generic gap (Δ = 0.190) is an artifact of a
weak generic baseline? Would a better-designed generic shrink it?

## Pre-registered design (BEFORE any measurement)

See `GENERIC_VARIANTS.md` (frozen first) and `generic_variants.json`:

- **G2** — box/cylinder chassis (mechanical-object generic).
- **G3** — vertical ellipsoid stack + box legs (organic-object generic).
- **G4** — slot-wise mean of the six family graphs, fully mechanical rule
  (majority type/axis/secondary, mean center/size; the runner re-derives it
  from the sealed `graphs.json` and aborts on drift).

Monkeypatch (documented): `mv.GRAPHS["generic"] = <variant>` in memory inside
try/finally; the sealed `graphs.json` is never written. G1 control re-runs the
sealed generic graph and is validated bit-exactly against
`results/test/raw_metrics.csv` (max abs err 0.0).

n = 240 actors, clean, voxel IoU at 64³, paired bootstrap (10 000, seed
77157).

## Headline numbers (pooled voxel IoU, n = 240)

| Variant | Mean IoU | Δ SPPA − variant | Gap closed |
|---|---|---|---|
| G1 sealed generic (control) | 0.367 | 0.190 | — |
| G2 box/cylinder chassis | 0.339 | 0.219 | −15.2 % |
| G3 vertical stack + legs | 0.282 | 0.276 | −45.0 % |
| G4 slot-wise family mean | 0.330 | 0.228 | −19.8 % |
| SPPA-MVFit (sealed) | 0.557 | 0.000 | 100 % |

All three alternatives are significantly **below** the sealed generic
(p < 1e-4 each): G2 −0.029 [−0.034, −0.023], G3 −0.085 [−0.091, −0.080],
G4 −0.038 [−0.043, −0.032].

Per family: G2 wins on the two vehicle families (compact 0.686 vs G1 0.644;
articulated 0.531 vs 0.471) but collapses on quadruped (0.353 vs 0.465) and
branching_vertical (0.218 vs 0.328). G3 slightly helps lattice_tower and
rider_cycle but is catastrophic on vehicles. G4 is middling everywhere.

## Answer to reviewer question (b)

The Δ does **not** shrink with alternative generic designs — it *grows* by
0.03–0.09 (Δ ranges 0.219–0.276 vs sealed 0.190). Every family-shaped generic
helps the families it resembles and hurts the others; the sealed symmetric
ellipsoid generic is already the best single compromise among the
pre-registered options, so the reported SPPA advantage is, if anything,
conservative.

## Files

- `GENERIC_VARIANTS.md` — design criteria frozen before measurement.
- `generic_variants.json` — the three variant graphs (G4 rule-verified).
- `run_e5_generic_variants.py` — runner (exactly reproducible).
- `generic_graph_sensitivity.json` — full numeric payload.
- `generic_graph_sensitivity_table.tex` — booktabs table.

## Seeds / determinism

Fits deterministic; bootstrap seed 77157, 10 000 resamples.
