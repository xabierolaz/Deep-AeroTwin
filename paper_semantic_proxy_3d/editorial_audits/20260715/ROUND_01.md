# SPPA independent editorial audit - round 01

Date: 2026-07-15

Scope: read-only review by four independent workers. No worker was allowed to
edit the repository. This file records the adverse findings that must be closed
before the manuscript can be described as submission-ready.

## Consolidated verdict

- Methodology/editorial decision: REJECT in the current form.
- Reproducibility decision: not reproducible from a clean checkout.
- Bibliographic integrity: failed; at least one entry has false identity data,
  YOLOE is uncited, and multiple recent entries need metadata corrections.
- Journal selection: plausible Q1 targets exist under UPNA agreements, but the
  manuscript does not yet meet their evidence bar.

An internal precheck with zero blockers is not equivalent to these external
editorial gates. The internal check currently verifies artifact presence and
contract consistency, not scientific novelty, independent validity, clean-clone
reproduction, or acceptance probability.

## Methodology/editor review

Simulated decision: REJECT, not major revision. The reviewer judged that the
current repository demonstrates substantial engineering but not yet a Q1-level
scientific contribution.

Critical findings:

1. Novelty is currently a UAV runtime contract around mature primitive and
   procedural modeling ideas, without an independently demonstrated algorithmic
   advance (`semantic_proxy_3d_paper.tex`, around lines 227-235).
2. The paper asks whether SPPA is useful but has no primary utility endpoint,
   formal hypothesis, or falsification criterion. The technical supplement's
   H1-H5 are not evaluated.
3. The four real-image probes have no 3D ground truth. Camera, altitude, pose,
   and dimensions are declared replay assumptions, not measured flight data.
4. The task-fit ranking is circular. The ranking script manually assigns SPPA
   contract/update capabilities to SPPA and assigns the opposite to competitors
   (`tools/sppa_sota_benchmark/make_sppa_task_fit_ranking.py`, around lines
   14-85). The resulting 6/6 versus 0/6 is not an independent measurement.
5. The neural-generator grid mixes tag, prompt, crop, and proxy-RGBA contracts
   without shared 3D ground truth or a common quality metric. Calling it a
   qualitative audit limits the claim but does not make it positive SOTA
   evidence.
6. Six objects and one generation per object are inadequate for comparative
   statistics. Unreal frame samples are temporally dependent and are not a
   substitute for independent experimental repetitions.
7. Text/tag selects a static ontology. The current visual route annotates or
   adds budgeted canonical cues to existing roles; it is not general image-to-
   primitive recovery. Counting consumed channels is not geometric accuracy.
8. Synthetic perfect reconstruction cases invert the same camera/projection
   process used to generate the masks. They validate plumbing, not estimation.
9. Open-label probes largely exercise known keywords/recipes and have no
   held-out open-set accuracy estimate.
10. Main paper and supplements contain inconsistent snapshots, including
    15/64 versus 23/95 archetype/check counts and different aggregate runtime
    figures.

Minimum scientific remediation:

- Define two or three hypotheses, a primary endpoint, secondary endpoints, and
  failure criteria before rerunning experiments.
- Replace the circular rank with measured baselines using the same input
  contract: bbox, capsule/ellipsoid, billboard, low-poly curated asset, simple
  procedural proxy, and occupancy/footprint where applicable.
- Freeze a held-out benchmark. Separate semantic normalization, geometry
  accuracy, runtime, persistence/update behavior, and operator interpretation.
- Measure relevant geometry endpoints such as BEV IoU, length/width/height/yaw
  error, containment, uncertainty calibration, semantic failure rate, and
  end-to-end cost.
- Use independent repetitions, confidence intervals, cold/warm separation,
  fixed seeds where possible, and raw timing data.
- If utility, readability, risk reduction, or safety remains a claim, add an
  operator experiment. Otherwise remove those outcome claims.
- A stronger research path is a genuine silhouette/multiview primitive-fitting
  method or a calibrated policy that selects bbox, SPPA, curated asset, or
  neural reconstruction based on uncertainty, budget, and track lifetime.

Related missing literature identified by the reviewer includes ISCO, PrITTI,
and 4D Primitive-Mache. These must be verified from primary sources before use.

## Reproducibility review

Verdict: NOT REPRODUCIBLE FROM A CLEAN CHECKOUT.

P0 findings:

1. The paper, tables, figures, scripts, and evidence currently do not correspond
   to `HEAD`. The worktree has extensive tracked modifications and thousands of
   untracked files.
2. The paper directory is a Windows junction to
   `D:\AYTE DOCTOR\SPPA_semantic_proxy_3d`. This is intentional for local use
   but cannot be a release-package assumption.
3. Inputs, runs, baseline repositories, model weights, PNG inputs, OBJ/GLB
   outputs, and raw packaged timing files are ignored or untracked.
4. Baseline runners contain machine-specific Python/venv paths. Baseline repo
   commits, model revisions, weight hashes, CUDA/Torch versions, and per-model
   locks are incomplete.
5. YOLOE weights and MobileCLIP weights have no release SHA-256. The runtime
   lock records Ultralytics 8.3.213 while a YOLOE artifact records 8.4.86.
6. Several paper numbers cannot be recalculated from files that would exist in
   a clone. Raw HISM/replay percentiles are especially vulnerable.
7. Real-image inputs have no auditable origin, license, capture date, or stable
   hash. There is no evidence that they were fabricated, but their authenticity
   cannot currently be certified.
8. The strict submission precheck itself is untracked, so the advertised gate
   does not exist at `HEAD`.

Required release work:

- Create a clean release commit/tag containing every manuscript source, table,
  figure, generator, verifier, and manifest used by the PDF.
- Publish raw inputs and outputs in Git LFS or a DOI-backed archive with hashes,
  licenses, provenance, and explicit `real`, `synthetic`, and
  `declared_replay` labels.
- Make all commands relative and pin baseline commits, models, environments,
  drivers, seeds, hardware, and executable/PAK hashes.
- Add one strict clean-clone command, for example
  `tools/reproduce_sppa_paper.ps1 -Strict`, that regenerates derived data,
  tables, figures, and the PDF.
- Add CI that rejects absolute paths, dirty provenance, missing inputs,
  obsolete figures, hash drift, and non-reproducible PDFs.

## Bibliographic integrity review

Critical corrections:

1. `hu2026sam3danimal` points to a real arXiv record but has a false title and
   false author list. Correct primary source:
   https://arxiv.org/abs/2605.07604
2. YOLOE is central to the experimental path but absent from the bibliography.
   Add the ICCV 2025 paper and separately document the exact Ultralytics
   `YOLOE-26S` checkpoint `yoloe-26s-seg.pt`:
   https://openaccess.thecvf.com/content/ICCV2025/html/Wang_YOLOE_Real-Time_Seeing_Anything_ICCV_2025_paper.html
   https://github.com/ultralytics/ultralytics/blob/main/docs/en/models/yoloe.md
3. HY3D-Bench is cited outside its primary scope. P3D-Bench is the more direct
   source for task/metric claims. Rewrite rather than overextend the citation.
4. The phrase `uncertainty-display literature` is unsupported by the cited
   SAGAT, Endsley, and NASA-TLX references.

Recent-reference metadata requiring correction includes SF3D, SPAR3D,
TripoSG, Direct3D-S2, TRELLIS, 3D-Fauna, DreamFusion, LGM, CRM, Unique3D,
ShapeCoder, Text2CAD, and CAD-Recode. Product claims for Tripo P1 and Rodin
Gen-2.5 require explicit product-page provenance and access dates.

Missing related work to verify includes CADCrafter, CADDreamer,
LocateAnything3D, and dedicated UAV digital-twin/telemetry-to-twin work.

## Visual PDF review by the main agent

- The PDF compiles to 32 A4 pages and has no clipping or overlap visible in the
  page montage.
- Figures on pages 11, 20, and 22 contain text and thumbnails that are not
  comfortably legible at normal page scale.
- The manuscript is still in a generic `article` layout, not a target-journal
  submission template.
- The PDF is untagged and has blank title/author metadata because the anonymous
  generic build does not populate document metadata.
- Three float-placement warnings remain. MiKTeX also reports that user and
  administrator updates are out of sync, although compilation succeeds.

## Round-01 exit rule

Round 01 remains failed until all P0 reproducibility issues are closed, the
ranking is replaced or removed, the bibliography criticals are corrected, and
the experimental design has a non-circular primary endpoint. Editorial wording
alone cannot close this round.

