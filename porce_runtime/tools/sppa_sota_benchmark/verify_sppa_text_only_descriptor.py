#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

from sppa_runtime_descriptor import build_sppa_descriptor_payload  # noqa: E402


def main() -> int:
    out_dir = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_geometric_projection" / "20260703_text_only_descriptor"
    out_dir.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    payload = build_sppa_descriptor_payload(
        label="cow",
        confidence=1.0,
        max_descriptor_bytes=30000,
    )
    descriptor_json = payload.get("sppa_descriptor_json")
    descriptor = json.loads(descriptor_json) if descriptor_json else {}

    if not descriptor_json:
        failures.append(f"descriptor_missing:{payload.get('sppa_descriptor_error')}")
    if payload.get("sppa_scale_source") not in {"template_prior", "semantic_prior_dims"}:
        failures.append(f"unexpected_scale_source:{payload.get('sppa_scale_source')}")
    if payload.get("sppa_metric_dims_m") is None:
        failures.append("text_only_should_emit_semantic_prior_dims")
    if descriptor.get("input", {}).get("normalized_label") != "cow":
        failures.append(f"unexpected_normalized_label:{descriptor.get('input')}")
    scale = descriptor.get("scale", {})
    if scale.get("effective_dims_m") is None:
        failures.append(f"descriptor_should_emit_effective_prior_dims:{scale}")
    if scale.get("metric_dims_source") != "semantic_prior_dims":
        failures.append(f"text_only_dims_must_be_semantic_prior:{scale}")
    if scale.get("scale_source") not in {"template_prior", "semantic_prior_dims"}:
        failures.append(f"text_only_should_not_claim_observed_scale:{scale}")
    if len(descriptor.get("parts") or []) < 4:
        failures.append(f"too_few_parts:{len(descriptor.get('parts') or [])}")
    evidence_sources = descriptor.get("evidence", {}).get("evidence_sources") or []
    if evidence_sources != ["semantic_label"]:
        failures.append(f"unexpected_evidence_sources:{evidence_sources}")

    report = {
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "descriptor_id": payload.get("sppa_descriptor_id"),
        "scale_source": payload.get("sppa_scale_source"),
        "shape_policy": payload.get("sppa_shape_policy"),
        "part_count": len(descriptor.get("parts") or []),
        "evidence_sources": evidence_sources,
        "claim_boundary": (
            "Text/tag-only SPPA descriptor regression. It proves SPPA can generate a controllable proxy "
            "from semantic label priors, but it deliberately does not claim observed metric scale or pose."
        ),
    }
    (out_dir / "sppa_text_only_descriptor_summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "sppa_text_only_descriptor_summary.md").write_text(
        "\n".join(
            [
                "# SPPA Text-Only Descriptor",
                "",
                f"- Status: {report['status']}",
                f"- Scale source: {report['scale_source']}",
                f"- Parts: {report['part_count']}",
                "",
                "Boundary: semantic prior dimensions are allowed; observed metric scale or pose is not claimed.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
