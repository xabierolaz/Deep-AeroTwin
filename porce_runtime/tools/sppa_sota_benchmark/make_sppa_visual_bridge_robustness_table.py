from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results"
OUT_JSON = RESULTS / "sppa_visual_bridge_robustness_table.json"
OUT_MD = RESULTS / "sppa_visual_bridge_robustness_table.md"
OUT_TEX = RESULTS / "sppa_visual_bridge_robustness_table.tex"


def load_json(name: str) -> dict[str, Any]:
    path = RESULTS / f"{name}.json"
    if not path.exists():
        return {"missing": True, "path": str(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def metric(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def status_text(data: dict[str, Any]) -> str:
    if data.get("missing"):
        return "missing"
    status = str(data.get("status") or "")
    if status == "pass":
        return "passed"
    return status or "unknown"


def latex_escape(value: Any) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in str(value))


def row(name: str, artifact: str, scope: str, cases: Any, metric_summary: str, limit: str) -> dict[str, Any]:
    data = load_json(artifact)
    return {
        "check": name,
        "artifact": artifact,
        "scope": scope,
        "cases_or_variants": cases(data) if callable(cases) else cases,
        "metric": metric_summary(data) if callable(metric_summary) else metric_summary,
        "status": status_text(data),
        "warnings": len(data.get("audit_warnings") or []),
        "failures": len(data.get("failures") or []),
        "limit": limit,
        "claim_boundary": data.get("claim_boundary"),
    }


def build_report() -> dict[str, Any]:
    rows = [
        row(
            "Cue extraction",
            "sppa_agnostic_image_space_parts_verify",
            "real crops",
            lambda d: d.get("rows_checked", 0),
            "4 frozen real probes",
            "Checks descriptor/export consistency, not primitive correctness.",
        ),
        row(
            "Label invariance",
            "sppa_agnostic_label_invariance",
            "real crops",
            lambda d: d.get("rows_checked", 0),
            "geometry hash unchanged",
            "Guards label/tag shortcuts only.",
        ),
        row(
            "Identity invariance",
            "sppa_agnostic_identity_invariance",
            "real crops",
            lambda d: d.get("rows_checked", 0),
            "geometry hash unchanged",
            "Guards case-name hardcoding only.",
        ),
        row(
            "Path invariance",
            "sppa_agnostic_path_invariance",
            "real crops",
            lambda d: d.get("rows_checked", 0),
            "geometry hash unchanged",
            "Guards filename/path shortcuts only.",
        ),
        row(
            "Detector representation",
            "sppa_agnostic_detection_representation_invariance",
            "real crops",
            lambda d: d.get("variants_checked", 0),
            "mask order/duplicates unchanged",
            "Guards representation-only side channels.",
        ),
        row(
            "Combined side channels",
            "sppa_agnostic_side_channel_invariance",
            "real crops",
            lambda d: d.get("rows_checked", 0),
            "geometry hash unchanged",
            "Does not prove primitive correctness.",
        ),
        row(
            "Mirror equivariance",
            "sppa_agnostic_mirror_equivariance",
            "real crops",
            lambda d: d.get("rows_checked", 0),
            lambda d: f"primary stable, {len(d.get('audit_warnings') or [])} secondary warnings",
            "Secondary line/weak-pair drift remains recorded.",
        ),
        row(
            "Photometric stability",
            "sppa_agnostic_photometric_stability",
            "real crops",
            lambda d: d.get("variants_checked", 0),
            lambda d: f"primary stable, {len(d.get('audit_warnings') or [])} secondary warnings",
            "Deterministic perturbations only, not real illumination coverage.",
        ),
        row(
            "Synthetic controls",
            "sppa_agnostic_synthetic_part_controls",
            "synthetic",
            lambda d: d.get("control_count", len(d.get("rows", []))),
            "all controls passed",
            "Known geometry controls, not detector quality.",
        ),
        row(
            "Synthetic sweep",
            "sppa_agnostic_synthetic_sweep",
            "synthetic",
            lambda d: (d.get("summary") or {}).get("case_count"),
            lambda d: (
                f"acc={metric((d.get('summary') or {}).get('primary_scope_accuracy'))}, "
                f"round F1={metric(((d.get('summary') or {}).get('round_pair') or {}).get('f1'))}, "
                f"line F1={metric(((d.get('summary') or {}).get('line_structure') or {}).get('f1'))}"
            ),
            "Synthetic primitive behavior only.",
        ),
        row(
            "Synthetic fuzz",
            "sppa_agnostic_synthetic_fuzz",
            "synthetic",
            lambda d: (d.get("summary") or {}).get("case_count"),
            lambda d: (
                f"4 seeds, acc={metric((d.get('summary') or {}).get('primary_scope_accuracy'))}, "
                f"round/line F1={metric(((d.get('summary') or {}).get('round_pair') or {}).get('f1'))}/"
                f"{metric(((d.get('summary') or {}).get('line_structure') or {}).get('f1'))}"
            ),
            "Randomized synthetic cues, not real UAV rates.",
        ),
    ]
    failures = [
        f"{item['check']}:{item['status']}"
        for item in rows
        if item["status"] not in {"passed"}
    ]
    return {
        "status": "passed" if not failures else "failed",
        "claim_boundary": (
            "This table summarizes the agnostic visual-primitive bridge robustness battery. "
            "It supports anti-shortcut and regression claims for the frozen probes and synthetic controls; "
            "it does not claim universal real-world primitive correctness or visual image-to-3D SOTA."
        ),
        "rows": rows,
        "failures": failures,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# SPPA Visual Bridge Robustness Battery",
        "",
        report["claim_boundary"],
        "",
        f"- Status: {report['status']}",
        f"- Failures: {report['failures'] or 'none'}",
        "",
        "| Check | Scope | Cases/variants | Metric | Status | Warnings | Limit |",
        "|---|---|---:|---|---|---:|---|",
    ]
    for item in report["rows"]:
        lines.append(
            f"| {item['check']} | {item['scope']} | {item['cases_or_variants']} | "
            f"{item['metric']} | {item['status']} | {item['warnings']} | {item['limit']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_tex(path: Path, report: dict[str, Any]) -> None:
    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{2.5pt}",
        r"\renewcommand{\arraystretch}{1.06}",
        (
            r"\caption{Agnostic visual-bridge robustness battery. "
            r"These checks support anti-shortcut and regression claims for the frozen real probes and synthetic controls; "
            r"they do not claim universal real-world primitive correctness.}"
        ),
        r"\label{tab:sppa-visual-bridge-robustness}",
        r"\begin{tabularx}{\linewidth}{@{}L{0.19\linewidth}L{0.11\linewidth}rL{0.26\linewidth}L{0.10\linewidth}rY@{}}",
        r"\toprule",
        r"Check & Scope & N & Metric & Status & Warn. & Boundary \\",
        r"\midrule",
    ]
    for item in report["rows"]:
        lines.append(
            f"{latex_escape(item['check'])} & {latex_escape(item['scope'])} & "
            f"{latex_escape(item['cases_or_variants'])} & {latex_escape(item['metric'])} & "
            f"{latex_escape(item['status'])} & {int(item['warnings'])} & {latex_escape(item['limit'])} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabularx}", r"\end{table}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    report = build_report()
    OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(OUT_MD, report)
    write_tex(OUT_TEX, report)
    print(
        json.dumps(
            {
                "json": str(OUT_JSON),
                "markdown": str(OUT_MD),
                "tex": str(OUT_TEX),
                "status": report["status"],
                "failures": report["failures"],
            },
            indent=2,
        )
    )
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
