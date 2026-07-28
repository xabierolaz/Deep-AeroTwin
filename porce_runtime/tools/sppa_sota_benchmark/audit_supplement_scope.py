#!/usr/bin/env python
"""Audit whether the SPPA technical supplement is submission material or an artifact log."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PAPER_DIR = ROOT.parent / "papers" / "semantic_proxy_3d"
DEFAULT_SUPPLEMENT = PAPER_DIR / "semantic_proxy_3d_technical_supplement.tex"
DEFAULT_JSON_OUT = PAPER_DIR / "SUPPLEMENT_TRIAGE.json"
DEFAULT_MD_OUT = PAPER_DIR / "SUPPLEMENT_TRIAGE.md"


SECTION_RE = re.compile(r"^\\(section|subsection|subsubsection)\{(.+?)\}")


def clean_latex(text: str) -> str:
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", " ", text)
    text = re.sub(r"[%].*", "", text)
    text = re.sub(r"[{}\\]", " ", text)
    return text


def word_count(lines: list[str]) -> int:
    text = clean_latex("\n".join(lines))
    return len(re.findall(r"[A-Za-z0-9_./:-]+", text))


def classify_section(title: str) -> tuple[str, str]:
    lower = title.lower()
    if lower in {"motivation", "core idea", "operational scope and non-claims", "contributions", "research question and hypotheses"}:
        return (
            "merge_or_delete_duplicate",
            "This belongs in the main manuscript if still needed; a supplement should not repeat the paper opening.",
        )
    if (
        "relation to" in lower
        or "human factors" in lower
        or "3d detection" in lower
        or "monocular" in lower
        or "animal pose" in lower
        or "primitive" in lower
        or "superquadric" in lower
        or "procedural actors" in lower
        or "lod" in lower
        or "scene graphs" in lower
    ):
        return (
            "merge_or_delete_duplicate",
            "Related-work context should stay compact in the main paper; long literature expansion is not submission evidence.",
        )
    if (
        lower
        in {
            "proposed runtime contract",
            "sppa specification",
            "operation inside a semantic-telemetry uav digital twin",
            "a different runtime contract from 3d generation",
        }
        or "semantic normalization" in lower
        or "bounded semantic-to-part compiler" in lower
        or "part graphs" in lower
        or "measurement extraction" in lower
        or "uncertainty-marked fallback" in lower
        or "pose and proportion fitting" in lower
        or "sppa objective" in lower
        or "role of a language model" in lower
        or "runtime output" in lower
        or "pseudocode" in lower
    ):
        return (
            "keep_as_main_or_appendix_summary",
            "This is part of the real contribution, but it should be a compact specification in the main paper or a short appendix.",
        )
    if "part-fitting" in lower or "scale" in lower or "truck" in lower:
        return (
            "keep_as_supporting_artifact",
            "Useful diagnostic evidence, especially for the truck decision, but the main paper needs only the distilled result.",
        )
    if "fast 3d generator" in lower or "sota" in lower:
        return (
            "keep_as_supporting_artifact",
            "Keep as input-alignment/protocol audit evidence; do not present as SOTA ranking until GT and metrics exist.",
        )
    if (
        "unreal" in lower
        or "payload" in lower
        or "http" in lower
        or "render benchmark" in lower
        or lower in {"prototype", "prototype timing and geometry complexity", "implementation status"}
    ):
        return (
            "artifact_log",
            "Detailed Unreal smoke/microbenchmark material is valuable for reproducibility, but too granular for a formal supplement.",
        )
    if (
        "descriptor" in lower
        or "update-packet" in lower
        or "scheduler" in lower
        or "link-budget" in lower
        or "material" in lower
        or "bounded label resolver" in lower
        or "negative-control" in lower
        or "track-lifecycle" in lower
        or "temporal update policy" in lower
    ):
        return (
            "artifact_log",
            "Implementation evidence should be archived with concise tables in the main paper, not carried as long prose.",
        )
    if "planned evaluation" in lower or "evidence needed" in lower or "limitations" in lower or "operational claim" in lower or "threats to validity" in lower:
        return (
            "main_roadmap_summary",
            "Keep only the four priority gates and hard limitations; avoid backlog-style planned-work pages.",
        )
    if "reproducibility" in lower:
        return (
            "short_artifact_index",
            "A formal supplement may include a short artifact index, but not raw command/log narration.",
        )
    if "conclusion" in lower:
        return (
            "delete_or_merge",
            "A supplement conclusion duplicates the paper conclusion and should be removed from formal submission material.",
        )
    return (
        "review_manually",
        "No explicit rule matched; inspect before deciding whether it belongs in main, appendix, or artifacts.",
    )


def parse_sections(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    markers: list[tuple[int, str, str]] = []
    for idx, line in enumerate(lines, start=1):
        match = SECTION_RE.match(line.strip())
        if match:
            markers.append((idx, match.group(1), match.group(2)))
    sections: list[dict[str, Any]] = []
    for pos, (start, level, title) in enumerate(markers):
        end = markers[pos + 1][0] - 1 if pos + 1 < len(markers) else len(lines)
        chunk = lines[start - 1 : end]
        decision, rationale = classify_section(title)
        sections.append(
            {
                "title": title,
                "level": level,
                "start_line": start,
                "end_line": end,
                "line_count": end - start + 1,
                "word_count_est": word_count(chunk),
                "decision": decision,
                "rationale": rationale,
            }
        )
    return sections


def build_report(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    sections = parse_sections(path) if path.exists() else []
    counts: dict[str, int] = {}
    words: dict[str, int] = {}
    for section in sections:
        decision = section["decision"]
        counts[decision] = counts.get(decision, 0) + 1
        words[decision] = words.get(decision, 0) + int(section["word_count_est"])
    top_sections = [section for section in sections if section["level"] == "section"]
    page_estimate = None
    pdf_path = path.with_suffix(".pdf")
    if pdf_path.exists():
        try:
            from pypdf import PdfReader

            page_estimate = len(PdfReader(str(pdf_path)).pages)
        except Exception:
            page_estimate = None
    return {
        "supplement": str(path),
        "exists": path.exists(),
        "tex_bytes": len(text.encode("utf-8")),
        "line_count": len(text.splitlines()),
        "word_count_est": word_count(text.splitlines()),
        "pdf_pages": page_estimate,
        "top_level_section_count": len(top_sections),
        "all_section_count": len(sections),
        "decision_counts": counts,
        "decision_word_counts": words,
        "recommendation": {
            "formal_supplement": "do_not_submit_current_38_page_file",
            "preferred_shape": "main_paper_plus_short_artifact_index",
            "max_formal_supplement_pages": 6,
            "reason": "The file duplicates main-paper framing, carries long Unreal/prototype logs, and includes roadmap material. Its valuable parts should be compressed into the main paper or archived as supporting artifacts.",
        },
        "keep_in_main": [
            "runtime contract and descriptor/update schema summary",
            "input-alignment audit with SOTA-readiness boundary",
            "real biker/tower input probes as detector/tag stress evidence",
            "truck role-preservation result as a compact diagnostic",
            "four priority gates for full experimental-paper readiness",
        ],
        "artifact_only": [
            "long Unreal Editor-Cmd/component/HTTP replay details",
            "packaged-render command/run logs",
            "link-budget model details",
            "legacy OBJ/MTL prototype timing tables",
            "planned evaluation backlog beyond the four priority gates",
        ],
        "sections": sections,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    rec = report["recommendation"]
    lines = [
        "# SPPA Supplement Triage",
        "",
        "Generated by `tools/sppa_sota_benchmark/audit_supplement_scope.py`.",
        "",
        "## Verdict",
        "",
        f"- Supplement exists: {report['exists']}",
        f"- TeX lines: {report['line_count']}",
        f"- Estimated words: {report['word_count_est']}",
        f"- PDF pages: {report['pdf_pages']}",
        f"- Top-level sections: {report['top_level_section_count']}",
        f"- All section headings: {report['all_section_count']}",
        f"- Formal supplement decision: `{rec['formal_supplement']}`",
        f"- Preferred submission shape: `{rec['preferred_shape']}`",
        f"- Max formal supplement pages if a venue requires one: {rec['max_formal_supplement_pages']}",
        f"- Reason: {rec['reason']}",
        "",
        "## Keep In Main Paper",
        "",
    ]
    lines.extend(f"- {item}" for item in report["keep_in_main"])
    lines += ["", "## Archive As Supporting Artifacts", ""]
    lines.extend(f"- {item}" for item in report["artifact_only"])
    lines += ["", "## Decision Counts", ""]
    for decision, count in sorted(report["decision_counts"].items()):
        words = report["decision_word_counts"].get(decision, 0)
        lines.append(f"- `{decision}`: {count} section(s), ~{words} words")
    lines += ["", "## Section Triage", ""]
    for section in report["sections"]:
        if section["level"] != "section":
            continue
        lines += [
            f"### {section['title']}",
            "",
            f"- Lines: {section['start_line']}-{section['end_line']} ({section['line_count']})",
            f"- Estimated words: {section['word_count_est']}",
            f"- Decision: `{section['decision']}`",
            f"- Rationale: {section['rationale']}",
            "",
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--supplement", type=Path, default=DEFAULT_SUPPLEMENT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--strict", action="store_true", help="Exit nonzero if the current supplement is too large for formal submission.")
    args = parser.parse_args()

    supplement = args.supplement if args.supplement.is_absolute() else ROOT / args.supplement
    report = build_report(supplement)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(args.md_out, report)
    print(
        json.dumps(
            {
                "json": str(args.json_out),
                "markdown": str(args.md_out),
                "pdf_pages": report["pdf_pages"],
                "line_count": report["line_count"],
                "formal_supplement": report["recommendation"]["formal_supplement"],
            },
            indent=2,
        )
    )
    if args.strict and (report["pdf_pages"] or 999) > report["recommendation"]["max_formal_supplement_pages"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
