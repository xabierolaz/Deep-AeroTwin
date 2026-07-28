from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = ROOT.parent / "papers" / "semantic_proxy_3d" / "experiments_root" / "sppa_sota_benchmark" / "runs" / "20260704_real_all_sppa_unified"
OUT_JSON = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sppa_connector_constraints.json"
OUT_MD = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sppa_connector_constraints.md"
OUT_TEX = ROOT.parent / "papers" / "semantic_proxy_3d" / "benchmarks" / "results" / "sppa_connector_constraints.tex"


CASES = {
    "biker": {
        "min_connectors": 9,
        "required_roles": {"bike_frame", "rider_skin", "rider_clothing"},
        "models": ("sppa",),
    },
    "tower": {
        "min_connectors": 6,
        "required_roles": {"vertical_structure_metal"},
        "models": ("sppa",),
    },
    "tractor": {
        "min_connectors": 2,
        "required_roles": {"vehicle_metal_or_hub"},
        "models": ("sppa",),
    },
    "tractor_trailer": {
        "min_connectors": 6,
        "required_roles": {"vehicle_metal_or_hub"},
        "models": ("sppa",),
    },
}


def connector_length(part: dict[str, Any]) -> float:
    endpoints = part.get("connector_endpoints") or []
    if len(endpoints) != 2:
        return 0.0
    a, b = endpoints
    return math.sqrt(sum((float(b[i]) - float(a[i])) ** 2 for i in range(3)))


def inspect_descriptor(model: str, case_id: str) -> dict[str, Any]:
    path = RUN_DIR / "outputs" / model / case_id / f"{case_id}.descriptor.json"
    if not path.exists():
        return {
            "case_id": case_id,
            "model": model,
            "descriptor": str(path),
            "status": "missing_descriptor",
            "failures": [f"missing descriptor: {path}"],
        }
    descriptor = json.loads(path.read_text(encoding="utf-8"))
    connectors = [
        part for part in descriptor.get("parts", [])
        if part.get("primitive") == "cylinder_connector"
    ]
    lengths = [connector_length(part) for part in connectors]
    roles = {str(part.get("role")) for part in connectors}
    spec = CASES[case_id]
    failures: list[str] = []
    if len(connectors) < int(spec["min_connectors"]):
        failures.append(f"connector_count {len(connectors)} < {spec['min_connectors']}")
    missing_roles = sorted(set(spec["required_roles"]) - roles)
    if missing_roles:
        failures.append(f"missing connector roles: {', '.join(missing_roles)}")
    if any(length <= 1e-5 for length in lengths):
        failures.append("degenerate connector length")
    return {
        "case_id": case_id,
        "model": model,
        "descriptor": str(path),
        "connector_count": len(connectors),
        "connector_roles": sorted(roles),
        "connector_length_min": round(min(lengths), 6) if lengths else 0.0,
        "connector_length_max": round(max(lengths), 6) if lengths else 0.0,
        "status": "passed" if not failures else "failed",
        "failures": failures,
    }


def latex_escape(value: Any) -> str:
    text = str(value)
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
    return "".join(replacements.get(char, char) for char in text)


def display_case(case_id: Any) -> str:
    return {
        "tractor_trailer": "tractor+trailer",
    }.get(str(case_id), str(case_id))


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# SPPA Connector Constraint Regression",
        "",
        report["claim_boundary"],
        "",
        "| Case | Model | Connectors | Roles | Length range | Status |",
        "|---|---:|---:|---|---:|---|",
    ]
    for row in report["rows"]:
        length_range = f"{row.get('connector_length_min', 0.0)}-{row.get('connector_length_max', 0.0)} m"
        lines.append(
            f"| {display_case(row['case_id'])} | {row['model']} | {row.get('connector_count', 0)} | "
            f"{', '.join(row.get('connector_roles', []))} | {length_range} | {row['status']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_tex(path: Path, report: dict[str, Any]) -> None:
    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\footnotesize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\renewcommand{\arraystretch}{1.08}",
        (
            r"\caption{SPPA connector-constraint regression. "
            r"Explicit lightweight connectors are required for semantic parts that should touch; "
            r"this is a connectivity contract, not a photorealistic reconstruction claim.}"
        ),
        r"\label{tab:sppa-connector-constraints}",
        r"\begin{tabularx}{\linewidth}{@{}L{0.19\linewidth}r L{0.31\linewidth}L{0.20\linewidth}Y@{}}",
        r"\toprule",
        r"Case & Connectors & Roles & Length range & Status \\",
        r"\midrule",
    ]
    for row in report["rows"]:
        roles = ", ".join(str(role).replace("_", " ") for role in row.get("connector_roles", []))
        length_range = f"{row.get('connector_length_min', 0.0):.3f}--{row.get('connector_length_max', 0.0):.3f} m"
        lines.append(
            f"{latex_escape(display_case(row['case_id']))} & {int(row.get('connector_count', 0))} & "
            f"{latex_escape(roles)} & {latex_escape(length_range)} & {latex_escape(row.get('status', ''))} \\\\"
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabularx}",
            r"\end{table}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = []
    for case_id, spec in CASES.items():
        for model in spec["models"]:
            rows.append(inspect_descriptor(model, case_id))
    failures = [failure for row in rows for failure in row.get("failures", [])]
    report = {
        "status": "passed" if not failures else "failed",
        "claim_boundary": (
            "Connector-constraint regression. This proves that SPPA descriptors "
            "contain explicit lightweight connectors for semantic parts that should "
            "touch, but it does not claim photorealistic reconstruction."
        ),
        "run_dir": str(RUN_DIR),
        "rows": rows,
        "failed": len(failures),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
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
                "failed": len(failures),
            },
            indent=2,
        )
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
