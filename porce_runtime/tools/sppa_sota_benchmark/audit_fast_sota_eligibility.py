from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT_JSON = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sota_fast_method_eligibility.json"
OUT_MD = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sota_fast_method_eligibility.md"


METHODS: list[dict[str, Any]] = [
    {
        "method": "SPPA",
        "input_mode": "tag/text or normalized detector state",
        "external_speed_claim": "not applicable",
        "local_status": "measured",
        "local_result": "0.0016 s median in the local finite-archetype stress table",
        "fast_candidate": True,
        "numeric_table_eligible": True,
        "fairness_decision": "eligible_runtime_proxy",
    },
    {
        "method": "TripoSR",
        "input_mode": "RGBA crop",
        "external_speed_claim": "fast feed-forward single-image reconstruction",
        "local_status": "measured",
        "local_result": "0.4604 s warm local run in the stress table",
        "fast_candidate": True,
        "numeric_table_eligible": True,
        "fairness_decision": "eligible_fast_image_to_3d_baseline",
    },
    {
        "method": "Hunyuan3D-2mini Turbo",
        "input_mode": "RGBA crop",
        "external_speed_claim": "fast/turbo variant of the Hunyuan image-to-3D family",
        "local_status": "measured",
        "local_result": "1.5042 s warm local run, but very high polygon counts and unstable orientation on real probes",
        "fast_candidate": True,
        "numeric_table_eligible": True,
        "fairness_decision": "eligible_but_not_lightweight_runtime_proxy",
    },
    {
        "method": "Stable Fast 3D",
        "input_mode": "single image / RGBA crop",
        "external_speed_claim": "0.5 s per object reported by Stability AI",
        "local_status": "attempted_timeout",
        "local_result": "Python 3.10 install succeeded, but no benchmark event was emitted in the previous 20 min run; a 2026-07-04 one-case 512px rerun also emitted no event before 4 min timeout",
        "fast_candidate": True,
        "numeric_table_eligible": False,
        "fairness_decision": "fast_candidate_but_not_reproduced_locally",
    },
    {
        "method": "SPAR3D",
        "input_mode": "single image / RGBA crop",
        "external_speed_claim": "0.7 s per object reported in the CVPR paper and under one second in Stability's announcement",
        "local_status": "attempted_weights_gated",
        "local_result": "Local install completed, but model loading failed before inference because Hugging Face access to stabilityai/stable-point-aware-3d was gated",
        "fast_candidate": True,
        "numeric_table_eligible": False,
        "fairness_decision": "fast_candidate_but_not_reproduced_locally",
    },
    {
        "method": "TRELLIS.2",
        "input_mode": "single image",
        "external_speed_claim": "3 s at 512^3, 17 s at 1024^3, 60 s at 1536^3 on NVIDIA H100",
        "local_status": "not_installed",
        "local_result": "Not run under the local 6 GB portable-profile protocol",
        "fast_candidate": "conditional",
        "numeric_table_eligible": False,
        "fairness_decision": "fast_on_h100_but_not_reproduced_or_portable_profile",
    },
    {
        "method": "Hunyuan3D 2.1",
        "input_mode": "single image / text",
        "external_speed_claim": "high-fidelity PBR asset generation; no official sub-second runtime claim used here",
        "local_status": "not_run",
        "local_result": "Not rerun under the frozen four-real-image protocol",
        "fast_candidate": False,
        "numeric_table_eligible": False,
        "fairness_decision": "visual_sota_context_not_fast_runtime_baseline",
    },
    {
        "method": "Pixal3D",
        "input_mode": "single image",
        "external_speed_claim": "high-fidelity pixel-aligned image-to-3D; no official runtime claim found for the paper audit",
        "local_status": "not_installed",
        "local_result": "Not run locally",
        "fast_candidate": False,
        "numeric_table_eligible": False,
        "fairness_decision": "visual_sota_context_not_fast_runtime_baseline",
    },
    {
        "method": "TripoSG / Tripo P1",
        "input_mode": "single image / service or foundation model",
        "external_speed_claim": "high-fidelity rectified-flow/foundation-model generation; not treated as a sub-second local baseline here",
        "local_status": "not_installed_or_not_api_run",
        "local_result": "Only TripoSR was reproduced locally",
        "fast_candidate": False,
        "numeric_table_eligible": False,
        "fairness_decision": "visual_sota_context_not_reproduced_fast_baseline",
    },
    {
        "method": "Direct3D-S2",
        "input_mode": "image-conditioned high-resolution 3D generation",
        "external_speed_claim": "reports efficiency/speedups for sparse attention, not a local per-object real-time claim for this audit",
        "local_status": "not_installed",
        "local_result": "Not run locally",
        "fast_candidate": False,
        "numeric_table_eligible": False,
        "fairness_decision": "visual_sota_context_not_fast_runtime_baseline",
    },
    {
        "method": "PartCrafter",
        "input_mode": "structured part-aware 3D generation",
        "external_speed_claim": "structured/high-fidelity part generation; no fast runtime claim used here",
        "local_status": "not_installed",
        "local_result": "Not run locally",
        "fast_candidate": False,
        "numeric_table_eligible": False,
        "fairness_decision": "related_work_for_structure_not_fast_baseline",
    },
    {
        "method": "Rodin Gen-2.5",
        "input_mode": "commercial image/text-to-3D",
        "external_speed_claim": "commercial service with speed/quality modes, not locally reproducible offline",
        "local_status": "not_api_run",
        "local_result": "No local or API-run provenance in this artifact",
        "fast_candidate": "unknown",
        "numeric_table_eligible": False,
        "fairness_decision": "commercial_context_not_reproducible_local_baseline",
    },
]


def main() -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    fast_candidates = [row for row in METHODS if row["fast_candidate"] is True]
    eligible = [row for row in METHODS if row["numeric_table_eligible"] is True]
    report = {
        "schema": "SPPA-FAST-SOTA-ELIGIBILITY-0.1",
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "fairness_rule": (
            "A method may enter the numeric fast-runtime comparison only if it is plausibly fast for the target "
            "operating point and has a successful local run under the same frozen input/resource protocol. External "
            "speed claims alone are not enough."
        ),
        "target_profile": "portable/UAV-adjacent stress profile, not an H100 offline asset-generation benchmark",
        "fast_candidate_count": len(fast_candidates),
        "numeric_table_eligible_count": len(eligible),
        "methods": METHODS,
    }
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Fast SOTA Eligibility Audit",
        "",
        "Generated by `tools/sppa_sota_benchmark/audit_fast_sota_eligibility.py`.",
        "",
        f"- Fairness rule: {report['fairness_rule']}",
        f"- Target profile: {report['target_profile']}",
        f"- Fast candidates: {report['fast_candidate_count']}",
        f"- Numeric-table eligible now: {report['numeric_table_eligible_count']}",
        "",
        "| Method | Fast candidate | Local status | Numeric table? | Decision |",
        "|---|---:|---|---:|---|",
    ]
    for row in METHODS:
        lines.append(
            f"| {row['method']} | {row['fast_candidate']} | `{row['local_status']}` | "
            f"{row['numeric_table_eligible']} | `{row['fairness_decision']}` |"
        )
    lines += [
        "",
        "## Boundary",
        "",
        "SF3D and SPAR3D remain the main missing fast baselines. TRELLIS.2 is fast on H100 at low resolution, "
        "but it is not yet a reproduced portable-profile baseline here. The remaining methods are important "
        "visual SOTA context, but they should not be mixed into the fast-runtime table without local timings.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"json": str(OUT_JSON), "markdown": str(OUT_MD), "eligible": len(eligible)}, indent=2))


if __name__ == "__main__":
    main()
