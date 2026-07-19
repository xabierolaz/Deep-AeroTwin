# External tribunal round 03 (2026-07-17) — MINOR_REVISION

Post-prune final-version tribunal (Editor, Stats, Repro, Literature), read-only,
on the exact submission candidate: main 33 pp + short supplement 4 pp (S1/S2),
commit `9f5c43f5`.

## Verdicts

| Role | Verdict |
|---|---|
| Editor-in-Chief (JGSA-like) | **MINOR_REVISION** |
| Methodology/Statistics AE | **MINOR_REVISION** |
| Reproducibility AE | **ACCEPT** |
| Literature AE | **MINOR_REVISION** |

## Overall

**MINOR_REVISION.** No P0 touches the sealed science: H1 stands, claim
discipline rated "exemplary", all four sealed hashes verify, clean-clone gate
PASS, strict 0 blockers. All eight P0s are one-pass editorial/textual fixes;
no new experiments, no re-sealing, no re-analysis.

## Consolidated P0 (must fix for Accept)

1. **Submission documents describe the wrong manuscript** (Editor).
   `COVER_LETTER_DRAFT.md` advertises the "cut systems diary" version and
   `JOURNAL_DECISION_20260716.md` still targets "~10–12 pages"; the actual
   submission is 33 pp with the full secondary block. Fix cover letter to
   describe the real manuscript; unify the title (cover-letter title ≠
   manuscript title). Retire the stale 10–12-page line.
2. **Highlights contain stale numbers** (Editor). Bullet 4 claims
   "~685 tris, ~0.22 ms local build"; no current table supports it. Align to
   sealed rows (e.g. 536 tris / 9.2 ms, or the appropriate table row).
3. **Residual run-ID diary prose, paper lines 1401–1471** (Editor). Six
   Unreal/HISM run-ID chronicles re-narrate what Table `tab:unreal-selected`
   already summarizes. Compress to one synthesis paragraph + the table; move
   the chronology to the supplement/artifact. Last open stretch of R1-P0.2.
4. **JGSA spatial-proxy framing missing in the manuscript itself** (Editor).
   Intro/keywords never name geovisualization/spatial analysis (framing lives
   only in the cover letter). Add a 3–5-sentence anchoring paragraph
   (dynamic-object geovisualization in 3D spatial twins) + one keyword.
   Partial regression of R1-P0.3.
5. **False "twelve disjoint calibration cases" statement** (Stats). Paper
   lines 634–635 and `sppa_neural_external_wave.md` claim the frozen frame
   convention was calibrated on disjoint cases; verified programmatically that
   all 12 calibration cases (first case per family×stratum cell) are INSIDE
   the 60 evaluated cases (12/12 overlap). Correct the statement and disclose
   the overlap plus its conservative direction (any selection bias inflates
   neural IoU, i.e. disfavors SPPA).
6. **In-text secondary CI contradicts the sealed artifact** (Stats). Paper
   line 598 reports SPPA−text-only CI [0.117, 0.143]; sealed
   `confirmatory_summary.json` / `sppa_mvfit_secondary_deltas.tex` give
   [0.116, 0.144]. One-word fix.
7. **SF3D exclusion reason contradictory across sections** (Literature).
   Neural-wave subsection says "install failure" (py3.12 stack); the
   Benchmark-Alignment section says py3.10 environment timed out with no
   benchmark event. Harmonize to one accurate sentence covering both.
8. **Two competitor-performance sentences lack citations** (Literature).
   Line 814 "external sources report sub-second generation" (SF3D/SPAR3D) and
   line 816 "TRELLIS.2 reports fast low-resolution H100 timings". Bib keys
   already exist (`sf3d2024`, `stability2025spar3d`, `xiang2025trellis2`) —
   attach them at those sentences.

## Consolidated P1 (optional, camera-ready polish)

- Compress the qualitative stress-test narrative (lines 743–821) now
  superseded by the measured wave; keep table + one paragraph (Editor).
- Consider moving 2–3 of the nine standalone audit tables to the supplement
  (Editor). Reorder forward reference at line 620 (Editor).
- Annotate Hunyuan3D(a) n=58 in the wave caption; state deltas/ratios are
  computed on unrounded per-case values (Stats).
- Qualify 9.4/10.6 ms as single-call descriptive times near line 603 (Stats).
- "Holms-style" → "Holm-style" (Stats/Editor); state Holm-adjusted p<0.001
  or label Table `mvfit-secondary` intervals as unadjusted (Stats).
- Supplement wording: reproduce command only works from repo root/junction
  (Repro). Move SF3D/SPAR3D exclusion notes from git-ignored `runs/` into the
  committed tree (Repro). Clarify `.gitignore` regeneration note (Repro).
- Add 1–2 geospatial digital-twin citations (Cesium/digital-twin currently
  uncited); cite measured methods + checkpoint IDs at point of measurement;
  `epic2024nanite` year mismatch; payload factor 10³–10⁴ understates ~3.2×10⁴
  max (Literature).
- Record correction: the review brief claimed "147 refs"; the actual bib/bbl
  holds 64 entries, machine-verified 64/64 cited, zero orphans (Literature).

## Package snapshot

- Main paper: 33 pages, 6 figures; short supplement: 4 pages (S1/S2)
- H1: PASS, mean Δ 0.190, CI [0.181, 0.199]; strata 0.209 / 0.172
- Neural wave: SPPA 0.561 IoU / 536 tris / 9.2 ms vs TripoSR 0.128–0.231,
  Hunyuan3D 0.157–0.171 (28k–3.1M tris, 1.9–4.7 GB VRAM)
- clean_clone_gate: pass; reproduce --strict: 0 blockers; commit `9f5c43f5`

## Response plan

Execute the minimum change set in one pass (8 P0s; P1s at author discretion),
recompile, re-run gates, then reconvene for round 04 accept check.
