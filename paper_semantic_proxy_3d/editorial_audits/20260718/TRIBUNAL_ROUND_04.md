# External tribunal round 04 (2026-07-18) — CLEAR ACCEPT

Accept-check tribunal (Editor, Stats, Repro, Literature), read-only, on the
corrected submission candidate: main 34 pp + short supplement 4 pp (S1/S2),
working tree after commit `9f5c43f5` + round-03 response pass.

## Verdicts

| Role | Verdict |
|---|---|
| Editor-in-Chief (JGSA-like) | **ACCEPT** |
| Methodology/Statistics AE | **ACCEPT** |
| Reproducibility AE | **ACCEPT** |
| Literature AE | **ACCEPT** |

## Overall

**CLEAR ACCEPT.** All eight round-03 P0s verified closed with quoted evidence;
regression scans clean in all four roles. No P0 raised. Residual P1s are
camera-ready polish only (three one-line document fixes applied immediately
after the round; remainder explicitly optional).

## P0 closure evidence (round 03 → 04)

1. Cover letter now describes the real 34-page manuscript; title unified with
   the manuscript (`COVER_LETTER_DRAFT.md` == paper title lines 23–24);
   criteria scorecard removed; `JOURNAL_DECISION_20260716.md` line updated to
   the full restored version. Residual "(cut systems diary)" parenthetical and
   33→34 page drift fixed post-round.
2. Highlights bullet 4 now matches the sealed wave row (536 tris / 9.2 ms).
3. Six Unreal/HISM run-ID chronicles compressed to one synthesis paragraph
   pointing to Table `tab:unreal-selected` and the experiment artifact; no
   table duplication.
4. Five-sentence geovisualization/spatial-proxy paragraph closes the
   Introduction (`batty2018digitaltwins`, `ogc2023tiles`) + keyword
   "geovisualization of dynamic objects".
5. Calibration statement corrected: convention fitted on the first case of
   each family×stratum cell, inside the 60 evaluated cases, with the
   conservative-direction disclosure; "disjoint" occurs nowhere in tex/md.
6. In-text CI now [0.116, 0.144], matching the sealed artifact
   (0.11649–0.14360) and the secondary-deltas table.
7. SF3D exclusion harmonized across sections (py3.12 build failure after a
   py3.10 no-event timeout; no measured quality result in either attempt);
   exclusion notes moved into the committed tree
   (`benchmarks/neural_external_wave/exclusion_notes/`).
8. Competitor claims cited: `\cite{stability2024sf3d,sf3d2024,stability2025spar3d}`
   and `\cite{xiang2025trellis2}` attached at the two flagged sentences;
   measured-generator cites + checkpoint IDs added to the wave Protocol.

## Residual P1 (camera-ready only, non-blocking)

- Record exact ratio values in `sppa_neural_external_wave.json` (Stats).
- Optional lineage anchors `kerbl2023gaussian`, `liu2023zero123` (Literature,
  explicitly optional under the no-SOTA-claim framing).
- Commit mechanics: `benchmarks/neural_external_wave/exclusion_notes/` is
  untracked and MUST be included in the submission commit (Repro); re-run the
  clean-clone gate after committing.

## Package snapshot

- Main paper: 34 pages, 6 figures; supplement: 4 pages (S1/S2); bib 65 entries
  (65/65 cited, 0 orphans, 0 undefined)
- H1: PASS, mean Δ 0.190, CI [0.181, 0.199]; sealed hashes unchanged
- reproduce --strict: 0 blockers; clean-clone gate: passes after the
  corrections commit (currently flags exactly the 3 corrected files)
