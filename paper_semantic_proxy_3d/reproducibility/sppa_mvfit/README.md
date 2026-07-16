# SPPA-MVFit reproducibility package

This directory is the compact, synthetic-only evidence package for the
family-conditioned SPPA-MVFit study. Its scope and decision rules are fixed by
`../../SPPA_PREREGISTRATION_20260715.md` and
`../../SPPA_PROTOCOL_AMENDMENT_01_20260715.md`.

Important boundaries:

- all benchmark GT and masks are `synthetic_geometry`;
- no real image, declared replay, detector result, or measured flight is used
  in the metric benchmark;
- `method/` never imports `source/` and `source/` never imports `method/`;
- text-only and silhouette-fitted SPPA call the same graph builder;
- no test seed or test result is present until the method freeze and external
  protocol gate pass;
- the historical task-fit ranking is not consumed.

Development-only commands from the repository root:

```powershell
python paper_semantic_proxy_3d/reproducibility/sppa_mvfit/benchmark/run_benchmark.py generate-development
python paper_semantic_proxy_3d/reproducibility/sppa_mvfit/benchmark/run_benchmark.py run-development
python paper_semantic_proxy_3d/reproducibility/sppa_mvfit/benchmark/run_benchmark.py analyze-development
python paper_semantic_proxy_3d/reproducibility/sppa_mvfit/benchmark/verify_package.py --development
```

The final strict wrapper will call these with the pinned interpreter and will
add the sealed test stages only after the protocol audit passes.

## Sealed confirmatory status (2026-07-16)

Held-out execution completed once after Amendment 03 local triple-role PASS.

- H1: **PASS** — mean Δ IoU 0.190, 95% CI [0.181, 0.199], n=240
- Strata: CSG-ID 0.209, implicit-OOD 0.172 (both positive)
- NIST pulse artifact: `data/nist_pulse_raw.json`
- Results: `results/test/confirmatory_summary.json` and `raw_metrics.csv`
- Paper tables: `python .../benchmark/export_paper_tables.py`
- Submission gate: `python paper_semantic_proxy_3d/tools/reproduce_sppa_mvfit_paper.py --strict`

Do **not** re-run method optimization to improve scores. Re-analysis from sealed
`raw_metrics.csv` is allowed for tables.

Historical locked command sequence (already executed for this snapshot):

```powershell
python paper_semantic_proxy_3d/reproducibility/sppa_mvfit/benchmark/prepare_test_seed_manifest.py --pulse-json paper_semantic_proxy_3d/reproducibility/sppa_mvfit/data/nist_pulse_raw.json
python paper_semantic_proxy_3d/reproducibility/sppa_mvfit/benchmark/generate_test_data.py
python paper_semantic_proxy_3d/reproducibility/sppa_mvfit/benchmark/run_test_methods.py
python paper_semantic_proxy_3d/reproducibility/sppa_mvfit/benchmark/evaluate_test.py
python paper_semantic_proxy_3d/reproducibility/sppa_mvfit/benchmark/run_resolution_sensitivity.py
python paper_semantic_proxy_3d/reproducibility/sppa_mvfit/benchmark/analyze_test.py
```

`run_test_methods.py` reads only public case metadata and observation masks. It
seals prediction bytes and a hash manifest before `evaluate_test.py` opens the
private source actors.
