# SPPA independent editorial audit - round 04: literature and bibliography

Date: 2026-07-15

Milestone: bibliography metadata, cited prior art, and support for literature
claims. The mandatory fourth literature worker was requested independently,
read-only, and was not shown another worker's verdict.

## Audited artifacts

- `semantic_proxy_3d_references.bib`, 58 entries, SHA-256
  `C67198DECAF2A2002EB9D158F97625614550E428B0628DC50C00B03B3F9CBC01`;
- `editorial_audits/20260715/bibliography/bibliography_audit.json`, SHA-256
  `8C3B45E127124EBB080D5838B2B8F1B430C5F81C49F45B4CB124BC8105FE248A`;
- `editorial_audits/20260715/bibliography/bibliography_manual_checks.json`,
  SHA-256
  `7D896063C18FF51CBD236977DC29799D094B2F35F15C41A3385E2ED0C2B0942C`;
- `editorial_audits/20260715/bibliography/BIBLIOGRAPHY_AUDIT.md`;
- `tools/audit_bibliography.py`.

## Internal primary-source audit

The reproducible audit parsed every BibTeX entry and queried the official arXiv
API or Crossref where an identifier existed. URL-only entries were checked
manually on the primary CVF, OGC, Epic, PyTorch, Stability AI, GitHub, or vendor
page. Result:

- 52 entries verified against primary metadata;
- 2 official-documentation entries verified;
- 1 official-standard entry verified;
- 1 software-repository entry verified;
- 1 vendor announcement verified as vendor metadata only;
- 1 vendor product page verified as vendor material only;
- zero unresolved identifiers or metadata mismatches.

Corrections included the false SAM 3D Animal title/authors, exact YOLOE and
primitive-fitting prior art, SF3D and TripoSG personal authors, the spelling of
Pascal M{\"u}ller, NASA-TLX DOI, current Nanite document title, and a versioned
PyTorch documentation URL. Three unused hardware-market references were removed.
The rolling Steam survey had already advanced to June 2026 and could not
reproduce the former May percentages; the quantitative hardware-population
claim was therefore removed from both main and technical-supplement prose.

This audit verifies metadata and source type. It is not an independent judgment
that the review is complete or that every citation supports the surrounding
claim.

## Independent literature-worker attempt

The dedicated fourth worker failed before reading any artifact with the
platform error:

`The 'gpt-5.6-sol' model is not supported when using Codex with a ChatGPT account.`

It returned no literature verdict and is not counted as an external reviewer.

## Consolidated verdict

**ROUND 04 IS INTERNALLY CLEAN BUT FAILS THE EXTERNAL LITERATURE-AUDIT GATE.**
There is primary-source metadata evidence for all 58 retained entries, but no
valid independent fourth-worker review. The bibliography may be built and
machine-checked; the paper must not be described as having passed its mandatory
external literature audit.

The remaining external dependency is one functioning read-only literature
reviewer who can assess omission, relevance, and claim-to-citation fit on this
frozen bibliography snapshot. Any P0 correction requires regeneration of the
audit hashes and a new round.
