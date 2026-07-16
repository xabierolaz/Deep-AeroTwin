# SPPA protocol amendment 02 — sealed held-out execution paths

Amendment date: 2026-07-15

This amendment adds executable gates that were absent from the first amended
freeze. It is prospective and does not alter the scientific endpoint, source
distributions, margin, or decision rule in Amendment 01. The prior freeze is
retained as an audit artifact; this amendment requires a new freeze before any
test pulse is obtained.

## B1. External authorization gate

The test commands refuse to run unless
`editorial_audits/20260715/PROTOCOL_AUDIT_PASS.json` declares `verdict: PASS`,
contains the three roles `methodology_statistics`,
`clean_clone_reproducibility`, and `target_journal_editor`, and names the exact
SHA-256 of the current `pretest_freeze.json`. A literature review does not
substitute for this protocol pass.

## B2. Seed-manifest gate

The seed command does not download data. After the external protocol pass, an
operator supplies the raw NIST Randomness Beacon JSON. The command records that
raw JSON and its hash, binds the manifest to the protocol-pass and pre-test
freeze hashes, and derives the ordered 240 case seeds as

`uint64(SHA256(UTF8(outputValue) || UTF8("SPPA-MVFIT-20260715") || UTF8(decimal_index))[0:8])`.

No raw pulse, seed manifest, or test case has been generated in this checkout.

## B3. Method-output sealing

`generate_test_data.py` writes public masks and a separate private actor file.
`run_test_methods.py` imports only the method package and reads only public
case metadata/masks. It writes packed predictions and a JSONL metadata table,
flushes them, and hashes both before the evaluator can open private GT.
`evaluate_test.py` refuses changed or unsealed prediction bytes, then computes
64-cubed metrics from the private source actors. `run_resolution_sensitivity.py`
implements the prespecified 48/64/80 check on five actors per family and
stratum.

## B4. Reproducibility boundary

`check_clean_clone_gate.py` is read-only and fails while required source files
are not tracked or have relevant working-tree changes. It never creates a clone
or mutates the checkout. A valid clean-clone audit must execute the package
from a fresh clone after the release commit, then independently verify the
hashes and test lock.

## B5. Status

This amendment is implementation-complete but **not externally approved**.
The current checkout has no protocol-pass record, no test seed, no private test
dataset, and no confirmatory result. Development results remain non-confirmatory.
