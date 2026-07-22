# Pipeline B software-only synthetic benchmark summary

**Status:** synthetic/software-only. These values do not replace flight, HMD, geospatial, or human-operator validation.

## Bandwidth

- Payloads: 600
- Duration: 59.90 s
- Mean semantic telemetry: 91.45 kbps
- P95 one-second semantic telemetry: 103.07 kbps
- Mean payload size: 1141.2 bytes

## Network degradation

| Profile | Drop rate | Visible recall | False freshness | Stale rate | Fragmentation | ID switches |
|---|---:|---:|---:|---:|---:|---:|
| nominal | 0.000 | 1.000 | 0.018 | 0.036 | 1 | 2 |
| mild_loss_5pct_jitter_50ms | 0.050 | 0.949 | 0.018 | 0.036 | 1 | 2 |
| degraded_loss_15pct_jitter_200ms | 0.157 | 0.843 | 0.017 | 0.036 | 3 | 2 |
| short_outage_5s | 0.102 | 0.898 | 0.012 | 0.060 | 4 | 2 |

## Latency budget

| Profile | Samples | Mean ms | P95 ms | P99 ms |
|---|---:|---:|---:|---:|
| nominal | 600 | 95.4 | 149.7 | 162.9 |
| mild_loss_5pct_jitter_50ms | 570 | 145.2 | 201.8 | 218.4 |
| degraded_loss_15pct_jitter_200ms | 506 | 276.3 | 382.2 | 416.4 |
| short_outage_5s | 539 | 168.2 | 234.0 | 247.4 |

## Manuscript use

Use these files to replace `TBD-BW`, `TBD-LOSS`, `TBD-TRACK`, and software-only parts of `TBD-LAT` only if the paper explicitly labels them as synthetic/software-only. Do not present them as hardware or operator evidence.
