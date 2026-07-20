# E10 — Measured mode routing on the real detector stream — FROZEN PROTOCOL

**Status:** exploratory post-hoc, NOT sealed. Frozen on 2026-07-19 **before any
routing outcome was computed**. Only descriptive facts already published in E7
(`README.md`, `e7_analysis.json`) and data-shape checks (row/case counts,
confidence range, signal derivations) existed at freeze time; no `reproj_iou`
value has been sliced by any routing signal before this freeze.

Reads `results.jsonl` **read-only**; writes only `e10_*` files in this folder.
Nothing under `reproducibility/` is touched.

## 0. Research question

The paper prescribes deployment-time **routing between the footprint-only
(SPPA top-only operational) mode and a box-proxy mode**, using detector-token
confidence (and, by extension, prior-mismatch) as the routing signal. This was
never measured. E10 measures it on the real-stream cases of E7.

## 1. Arms (routed modes)

- **A = SPPA-MVFit** — the operational top-only + height-anchor arm
  (`method == "sppa_mvfit"` rows of `results.jsonl`).
- **B = best box proxy** — declared from the *already published* E7 main table
  (frozen prior to E10, not selected on E10 outcomes): box proxies are OBB
  (0.446) and AABB (0.330) median 2D reproj. IoU → **B = `obb`**.

Case table: the 1902 `sppa_mvfit` rows (signals are identical across methods
within a case); `obb` rows joined by `case_id` for the arm-B outcome.

## 2. Routing signals (declared candidates)

1. `s_conf` = detector `confidence` (range 0.1004–0.7700).
   **Declared: confidence is used as a ROUTING signal only, never as fitter
   input — the sealed preregistered protocol forbids detector confidence as an
   input to the fitter, and E10 does not refit anything.**
2. `s_mm` = `|ln(obs_height_m / H_family)|` — absolute log prior-mismatch of
   the monocular height estimate against the family prior.
   `H_family` is **derived from the frozen graphs**
   (`reproducibility/sppa_mvfit/method/graphs.json`, read-only) at nominal θ:
   z-extent of the 8-slot graph in graph units × the declared E7 metric scale
   (`FAMILY_SCALE_M_PER_UNIT` in `e7_common.py`). Derived values:

   | family_token   | z-extent (units) | scale (m/unit) | H_family (m) |
   |---|---|---|---|
   | lattice_tower  | 4.800 | 5.2083 | 25.0 |
   | quadruped      | 1.810 | 0.8287 | 1.5  |
   | rider_cycle    | 2.610 | 0.6897 | 1.8  |

   (By construction these equal the E7 declared nominal heights; the
   derivation path is documented here for auditability.)
3. Secondary, ROC arm only: `obs_height_m` raw.

## 3. Outcomes

- **Primary:** per-case `reproj_iou` of the routed method (2D reprojection
  IoU vs the real detector bbox; exists for all 1902 cases).
  `footprint_iou` is NOT used (degenerate ~0 under the ~33 m observation bias;
  documented in E7).
- **Secondary:** separability of the wrong-token flag on the 217 GT-matched
  cases (138 wrong token, 79 correct token).

## 4. Routing policies (frozen grid)

Let `y_A`, `y_B` be per-case `reproj_iou` of arms A and B.

- `always_sppa`: all cases → A.
- `always_proxy`: all cases → B.
- `oracle`: per-case argmax(y_A, y_B); ties → A. (Upper bound, not deployable.)
- `conf_t`: `s_conf < τ` → B, else A; τ ∈ 15 evenly spaced values on
  [0.10, 0.77] (declared literal grid).
- `mismatch_m`: `s_mm > μ` → B, else A; μ ∈ 15 evenly spaced values over the
  empirical range of `s_mm` on the 1902 cases (the *rule* is frozen here; the
  signal range is computed blind to outcomes).
- `and_best`: (`s_conf < τ*`) AND (`s_mm > μ*`) → B, else A.
- `or_best`: (`s_conf < τ*`) OR (`s_mm > μ*`) → B, else A.

`τ*`, `μ*` = grid maximizers of the median primary outcome within `conf_t` /
`mismatch_m` respectively. **Best-policy selection on the point estimate is
part of the frozen procedure and is reported as such** (exploratory; no
multiplicity control).

## 5. Statistics

- Case-level **paired bootstrap**: 10,000 resamples over the 1902 cases
  (seed = 20260719, numpy `default_rng`); 95% percentile CIs on the median
  `reproj_iou` of every policy (oracle included).
- Paired **median-difference** bootstrap CIs: best routed policy vs
  `always_sppa` and vs `always_proxy`.
- **McNemar-style win/tie/lose** per-case counts on `reproj_iou` for the best
  routed policy and the oracle vs both always-X baselines
  (tie: |Δ| ≤ 1e-12).

## 6. Wrong-token arm (217 GT-matched cases)

- ROC/AUC of two wrong-token scores, declared directions:
  `score = −s_conf` (low confidence predicts wrong token) and
  `score = +s_mm` (large mismatch predicts wrong token). AUC by the
  rank (Mann–Whitney) statistic; ROC points from pooled sorted scores.
  AUC < 0.5 means the signal points the other way — reported as-is.
- Wrong-token rate above/below the routing-optimal threshold τ* (conf side)
  and, for completeness, μ* (mismatch side), on the 217 matched cases.

## 7. Token–routing interaction (refit join)

- Join the 138 `sppa_mvfit_correct_token` refit rows by `case_id`
  (assert 138/138 join).
- Among the 138 wrong-token cases, split by the **best routed policy**
  (the non-oracle policy — one of `conf_t*`, `mismatch_m*`, `and_best`,
  `or_best` — with the highest median primary outcome; selection frozen as
  above):
  - fraction routed AWAY from SPPA (token risk avoided by routing);
  - among those routed TO SPPA: paired real-token vs correct-token refit
    `reproj_iou` — medians and paired bootstrap CI of the median difference
    (same seed). Reported in whichever direction it comes out
    (E7 showed the correct-token refit *collapses* reprojection IoU, so a
    negative "hurt" is expected; the number is reported as measured).

## 8. Sanity checks (script asserts)

- Exactly 1902 unique cases; 1902 rows for `sppa_mvfit` and `obb`.
- No NaN/inf in `confidence`, `obs_height_m`, `reproj_iou` (both arms);
  `obs_height_m > 0` (log safety).
- 217 GT-matched cases = 138 wrong-token + 79 correct-token.
- Print the head of the aggregated per-case frame.

## 9. Outputs

- `e10_routing.json` — all numbers (grid results, CIs, ROC/AUC, token arm,
  interaction arm, sanity).
- `e10_routing_table.tex` — booktabs, paper pattern: always-SPPA,
  always-proxy, oracle, best-conf, best-mismatch, best-AND, best-OR, with
  median + 95% CI + routing coverage (fraction → SPPA).
- `fig_e10_routing.png` — 2 panels, JGSA style (Okabe-Ito, 300 dpi):
  (a) median reproj. IoU vs routing threshold for both signals + oracle and
  always-X reference lines; (b) ROC curves for wrong-token separation.

## 10. Honesty clause

The grid above is frozen. No signal, threshold range, or statistic is tuned
after outcomes are seen. Any observation made after the freeze is reported
labelled as post-hoc exploratory. Null or negative routing gains are reported
as-is.
