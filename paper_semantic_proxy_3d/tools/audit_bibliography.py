#!/usr/bin/env python
"""Audit the SPPA BibTeX file against primary metadata endpoints.

The script never edits the bibliography. It records exact endpoint responses,
machine comparisons, and items that still require a human primary-source check.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


PAPER_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BIB = PAPER_ROOT / "semantic_proxy_3d_references.bib"
DEFAULT_OUT = PAPER_ROOT / "editorial_audits" / "20260715" / "bibliography"
DEFAULT_MANUAL = DEFAULT_OUT / "bibliography_manual_checks.json"
USER_AGENT = "SPPA-bibliography-audit/1.0 (metadata verification; no scraping corpus)"


def balanced_end(text: str, opening: int) -> int:
    depth = 0
    quoted = False
    escaped = False
    for pos in range(opening, len(text)):
        char = text[pos]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            quoted = not quoted
        if quoted:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return pos
    raise ValueError(f"unbalanced BibTeX entry at byte {opening}")


def parse_value(body: str, pos: int) -> tuple[str, int]:
    if body[pos] == "{":
        end = balanced_end(body, pos)
        return body[pos + 1 : end].strip(), end + 1
    if body[pos] == '"':
        end = pos + 1
        escaped = False
        while end < len(body):
            if body[end] == '"' and not escaped:
                return body[pos + 1 : end].strip(), end + 1
            escaped = body[end] == "\\" and not escaped
            if body[end] != "\\":
                escaped = False
            end += 1
        raise ValueError("unterminated quoted BibTeX value")
    end = body.find(",", pos)
    end = len(body) if end < 0 else end
    return body[pos:end].strip(), end


def parse_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    pos = body.find(",") + 1
    while pos > 0 and pos < len(body):
        while pos < len(body) and (body[pos].isspace() or body[pos] == ","):
            pos += 1
        match = re.match(r"([A-Za-z][A-Za-z0-9_-]*)\s*=\s*", body[pos:])
        if not match:
            break
        name = match.group(1).lower()
        pos += match.end()
        value, pos = parse_value(body, pos)
        fields[name] = value
    return fields


def parse_bib(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    entries: list[dict[str, Any]] = []
    for match in re.finditer(r"(?m)^@([A-Za-z]+)\s*\{\s*([^,\s]+)\s*,", text):
        opening = text.find("{", match.start())
        end = balanced_end(text, opening)
        body = text[opening + 1 : end]
        entries.append(
            {
                "type": match.group(1).lower(),
                "key": match.group(2),
                "fields": parse_fields(body),
                "line": text.count("\n", 0, match.start()) + 1,
            }
        )
    return entries


def plain(value: str) -> str:
    value = re.sub(r"\{\\[\"'`^~=.uvHck]\s*([A-Za-z])\}", r"\1", value)
    value = re.sub(r"\\[A-Za-z]+\s*", " ", value)
    value = value.replace("{", "").replace("}", "")
    value = html.unescape(value)
    value = "".join(char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", value).strip()


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", plain(value).lower()).strip()


def title_similarity(left: str, right: str) -> float:
    return round(SequenceMatcher(None, normalized(left), normalized(right)).ratio(), 4)


def arxiv_id(fields: dict[str, str]) -> str | None:
    eprint = fields.get("eprint", "")
    match = re.fullmatch(r"\s*(\d{4}\.\d{4,5})(?:v\d+)?\s*", eprint, re.I)
    if match:
        return match.group(1)
    url = fields.get("url", "")
    match = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?", url, re.I)
    if match:
        return match.group(1)
    doi = fields.get("doi", "")
    match = re.search(r"10\.48550/arxiv\.(\d{4}\.\d{4,5})(?:v\d+)?", doi, re.I)
    if match:
        return match.group(1)
    return None


def fetch_arxiv(ids: list[str]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    namespace = {"a": "http://www.w3.org/2005/Atom"}
    records: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for start in range(0, len(ids), 25):
        batch = ids[start : start + 25]
        try:
            response = requests.get(
                "https://export.arxiv.org/api/query",
                params={"id_list": ",".join(batch), "max_results": len(batch)},
                headers={"User-Agent": USER_AGENT},
                timeout=45,
            )
            response.raise_for_status()
            root = ET.fromstring(response.content)
            for item in root.findall("a:entry", namespace):
                identifier = item.findtext("a:id", default="", namespaces=namespace).rsplit("/", 1)[-1]
                identifier = re.sub(r"v\d+$", "", identifier)
                records[identifier] = {
                    "title": re.sub(r"\s+", " ", item.findtext("a:title", default="", namespaces=namespace)).strip(),
                    "authors": [
                        author.findtext("a:name", default="", namespaces=namespace)
                        for author in item.findall("a:author", namespace)
                    ],
                    "published": item.findtext("a:published", default="", namespaces=namespace),
                    "source_url": item.findtext("a:id", default="", namespaces=namespace),
                }
        except Exception as exc:  # exact failure is evidence in the report
            errors.append(f"arXiv batch {','.join(batch)}: {type(exc).__name__}: {exc}")
        time.sleep(0.35)
    return records, errors


def fetch_crossref(doi: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = requests.get(
            f"https://api.crossref.org/works/{quote(doi, safe='')}",
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        message = response.json()["message"]
        dates = message.get("published-print") or message.get("published-online") or message.get("issued") or {}
        parts = dates.get("date-parts") or []
        return {
            "title": (message.get("title") or [""])[0],
            "authors": [
                " ".join(part for part in [row.get("given", ""), row.get("family", "")] if part).strip()
                for row in message.get("author", [])
            ],
            "year": parts[0][0] if parts and parts[0] else None,
            "source_url": message.get("URL", ""),
        }, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def author_surnames(value: str) -> list[str]:
    people = re.split(r"\s+and\s+", plain(value), flags=re.I)
    surnames = []
    for person in people:
        person = person.strip()
        if not person:
            continue
        surname = person.split(",", 1)[0] if "," in person else person.split()[-1]
        surnames.append(normalized(surname))
    return surnames


def source_surnames(people: list[str]) -> list[str]:
    return [normalized(person.split()[-1]) for person in people if person.strip()]


def audit(entries: list[dict[str, Any]], manual_checks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    arxiv_ids = sorted({identifier for entry in entries if (identifier := arxiv_id(entry["fields"]))})
    arxiv, endpoint_errors = fetch_arxiv(arxiv_ids)
    rows: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        fields = entry["fields"]
        identifier = arxiv_id(fields)
        doi = fields.get("doi", "").strip()
        source_kind = "arxiv" if identifier else "crossref" if doi else "url_only"
        source_record: dict[str, Any] | None = None
        source_error: str | None = None
        if identifier:
            source_record = arxiv.get(identifier)
            if source_record is None:
                source_error = "arXiv id not returned by primary API"
        elif doi:
            source_record, source_error = fetch_crossref(doi)
            time.sleep(0.16)

        title = fields.get("title", "")
        year_text = re.sub(r"[^0-9]", "", fields.get("year", ""))[:4]
        expected_year = int(year_text) if year_text else None
        similarity = title_similarity(title, source_record.get("title", "")) if source_record else None
        source_year: int | None = None
        if source_record:
            published = str(source_record.get("published", ""))
            source_year = int(published[:4]) if published[:4].isdigit() else source_record.get("year")
        bib_authors = author_surnames(fields.get("author", ""))
        primary_authors = source_surnames(source_record.get("authors", [])) if source_record else []
        author_prefix_match = bool(bib_authors and primary_authors and bib_authors[: min(3, len(bib_authors))] == primary_authors[: min(3, len(bib_authors))])

        issues: list[str] = []
        manual = manual_checks.get(entry["key"])
        if source_kind == "url_only" and manual:
            status = manual["status"]
            issues.extend(manual.get("issues", []))
        elif source_kind == "url_only":
            status = "manual_primary_url_check"
            issues.append("no arXiv id or DOI; primary URL metadata requires manual verification")
        elif source_record is None:
            status = "unresolved_primary_metadata"
            issues.append(source_error or "primary metadata unavailable")
        else:
            if similarity is not None and similarity < 0.9:
                issues.append(f"title similarity {similarity:.4f} < 0.9000")
            # Conference bibliography years normally follow the archival venue,
            # while arXiv's primary API reports the first preprint year.
            if expected_year and source_year and expected_year != source_year and entry["type"] != "inproceedings":
                issues.append(f"bibliography year {expected_year} != primary year {source_year}")
            if bib_authors and primary_authors and not author_prefix_match:
                issues.append("first author surnames do not match primary metadata")
            status = "metadata_mismatch" if issues else "verified_primary_metadata"

        rows.append(
            {
                "index": index,
                "key": entry["key"],
                "entry_type": entry["type"],
                "line": entry["line"],
                "source_kind": source_kind,
                "identifier": identifier or doi or fields.get("url", ""),
                "status": status,
                "bib_title": plain(title),
                "primary_title": source_record.get("title", "") if source_record else "",
                "title_similarity": similarity,
                "bib_year": expected_year,
                "primary_year": source_year,
                "bib_author_surnames": bib_authors,
                "primary_author_surnames": primary_authors,
                "author_prefix_match": author_prefix_match if source_record else None,
                "primary_source_url": source_record.get("source_url", "") if source_record else fields.get("url", ""),
                "issues": issues,
                "manual_checked_at": manual.get("checked_at") if manual else None,
                "manual_basis": manual.get("basis", "") if manual else "",
            }
        )
    counts = {status: sum(row["status"] == status for row in rows) for status in sorted({row["status"] for row in rows})}
    return {
        "schema": "sppa-bibliography-audit-v1",
        "bibliography": str(DEFAULT_BIB.relative_to(PAPER_ROOT)).replace("\\", "/"),
        "entry_count": len(rows),
        "counts": counts,
        "endpoint_errors": endpoint_errors,
        "rows": rows,
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bibliography_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    fieldnames = [
        "index", "key", "entry_type", "line", "source_kind", "identifier", "status", "bib_title",
        "primary_title", "title_similarity", "bib_year", "primary_year", "bib_author_surnames",
        "primary_author_surnames", "author_prefix_match", "primary_source_url", "issues", "manual_checked_at",
        "manual_basis",
    ]
    with (out_dir / "bibliography_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in report["rows"]:
            writer.writerow({**row, "bib_author_surnames": ";".join(row["bib_author_surnames"]), "primary_author_surnames": ";".join(row["primary_author_surnames"]), "issues": "; ".join(row["issues"])})

    lines = [
        "# SPPA bibliography primary-source audit",
        "",
        f"Entries: {report['entry_count']}.",
        "",
        "This is a metadata audit, not a relevance endorsement. arXiv records are checked against the official arXiv API; DOI records against Crossref. URL-only records remain manual until checked on their primary page.",
        "",
        "## Counts",
        "",
        *[f"- `{key}`: {value}" for key, value in sorted(report["counts"].items())],
        "",
    ]
    if report["endpoint_errors"]:
        lines += ["## Endpoint errors", "", *[f"- {item}" for item in report["endpoint_errors"]], ""]
    for heading, statuses in [
        ("Blocking mismatches or non-reproducible sources", {"metadata_mismatch", "unresolved_primary_metadata", "dynamic_source_not_reproducible"}),
        ("Unchecked primary URLs", {"manual_primary_url_check"}),
    ]:
        lines += [f"## {heading}", ""]
        selected = [row for row in report["rows"] if row["status"] in statuses]
        if not selected:
            lines.append("None.")
        for row in selected:
            issues = "; ".join(row["issues"]) or row["manual_basis"] or "manual check"
            lines.append(f"- `{row['key']}` (BibTeX line {row['line']}): {issues}. Primary: {row['primary_source_url'] or row['identifier']}")
        lines.append("")
    lines += ["## Manual primary-source decisions", ""]
    for row in report["rows"]:
        if not row["manual_basis"]:
            continue
        lines.append(f"- `{row['key']}` — `{row['status']}`: {row['manual_basis']} Primary: {row['primary_source_url']}")
    lines.append("")
    (out_dir / "BIBLIOGRAPHY_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bib", type=Path, default=DEFAULT_BIB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--manual", type=Path, default=DEFAULT_MANUAL)
    args = parser.parse_args()
    entries = parse_bib(args.bib)
    manual_payload = json.loads(args.manual.read_text(encoding="utf-8")) if args.manual.exists() else {"checks": []}
    checked_at = manual_payload.get("checked_at")
    manual_checks = {
        row["key"]: {**row, "checked_at": row.get("checked_at", checked_at)}
        for row in manual_payload.get("checks", [])
    }
    report = audit(entries, manual_checks)
    write_outputs(report, args.out)
    print(json.dumps({"entries": report["entry_count"], "counts": report["counts"], "endpoint_errors": report["endpoint_errors"], "out": str(args.out)}, indent=2))


if __name__ == "__main__":
    main()
