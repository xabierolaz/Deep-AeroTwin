# Pipeline B experimental support package

This folder contains reproducible support material for the Pipeline B / VRIH
paper. It is deliberately separated from the manuscript source so it can help
replace pending placeholders without forcing claims into the paper before the
physical validation exists.

## Status

This is a software-only preparatory package. It can support:

- `TBD-REPRO`: schemas, scripts, fixture data, configuration records.
- `TBD-BW`: semantic-telemetry bitrate estimates from actual JSON payloads.
- `TBD-LOSS`: deterministic packet-loss, jitter, delay, and outage simulations.
- `TBD-TRACK`: synthetic identity-switch, stale-duration, and fragmentation tests.
- `TBD-LAT`: software-only latency-budget simulation and instrumentation plan.
- `TBD-STAT`: human-study statistical-analysis plan.
- `TBD-ETHICS`: ethics and participant-safety preparation.

It cannot replace:

- HMD screenshots or videos.
- real source-to-HMD latency measurements.
- real geospatial ground truth.
- human-operator results.
- sensor validation in low visibility.

## Layout

| Folder | Purpose |
|---|---|
| `schemas/` | JSON contracts for `POST /api/obstacles` and `GET /api/ui/data`. |
| `replay/scenarios/` | Human-readable synthetic scenario definitions. |
| `replay/generated/` | Generated JSONL replay payloads and ground truth. |
| `configs/` | Benchmark profiles for network degradation and latency. |
| `scripts/` | Deterministic generators, validators, and benchmarks. |
| `outputs/` | Generated CSV/JSON/Markdown outputs. |
| `protocols/` | Human study, ethics, statistics, figure capture, and hardware checklists. |

## Reproducible command sequence

Run from this folder:

```powershell
rtk python scripts/pipeline_b_generate_replay.py
rtk python scripts/pipeline_b_validate_contract.py
rtk python scripts/pipeline_b_software_benchmark.py
```

The benchmark writes `outputs/pipeline_b_software_only_summary.md`. Any numbers
in that report are synthetic/software-only unless explicitly replaced by
physical or HMD measurements later.

## Rule for manuscript use

Do not copy synthetic output into the final paper as an experimental result
unless the caption and text state exactly what was simulated. The safest use is
to cite this package as the reproducibility scaffold and then replace each
placeholder with measured evidence when available.
