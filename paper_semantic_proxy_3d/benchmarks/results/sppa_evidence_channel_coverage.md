# SPPA Evidence-Channel Coverage

Evidence-channel coverage measures which SPPA inputs were actually consumed under each contract. It is not a 3D quality score, not a human-preference score, and not a visual image-to-3D SOTA ranking.

| Case | Mode | Semantic | Metric | Visual | Yaw | Material | Channels | Budget | Wall time (ms) | Tris | Descriptor B |
|---|---|---|---|---|---|---|---:|---|---:|---:|---:|
| biker | text | yes | - | - | - | - | 1 | pass | 5.840 | 1036 | 17238 |
| biker | det+metric | yes | yes | - | - | - | 2 | pass | 2.355 | 1036 | 19297 |
| biker | det+metric+visual | yes | yes | yes | yes | - | 4 | pass | 3.023 | 1056 | 31657 |
| tower | text | yes | - | - | - | - | 1 | pass | 1.561 | 396 | 15609 |
| tower | det+metric | yes | yes | - | - | - | 2 | pass | 3.047 | 396 | 17666 |
| tower | det+metric+visual | yes | yes | yes | yes | - | 4 | pass | 1.640 | 436 | 31029 |
| tractor | text | yes | - | - | - | - | 1 | pass | 2.394 | 1056 | 15179 |
| tractor | det+metric | yes | yes | - | - | - | 2 | pass | 2.491 | 1056 | 17188 |
| tractor | det+metric+visual | yes | yes | yes | yes | yes | 5 | pass | 2.702 | 1096 | 32287 |
| tractor_trailer | text | yes | - | - | - | - | 1 | pass | 3.490 | 1988 | 21448 |
| tractor_trailer | det+metric | yes | yes | - | - | - | 2 | pass | 3.074 | 1848 | 20967 |
| tractor_trailer | det+metric+visual | yes | yes | yes | yes | - | 4 | pass | 3.256 | 1872 | 27949 |
