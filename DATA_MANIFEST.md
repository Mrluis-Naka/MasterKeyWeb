# MasterKey — Data and Code Availability Package

This file is a guide to the other files in this upload, added to
`github.com/Mrluis-Naka/MasterKeyWeb` (the repository already serving `masterkeybtc.com` and
`VANITYKEYFOUND2.txt`), so that Section 9 of the study manuscript (`PAPER_LEDGER_EN.md`) can cite a
single, complete, resolvable location for everything it lists as data and code. **This is not the
repository's README** — that file already exists and describes `VANITYKEYFOUND2.txt`; do not
replace it with this one.

## What's already public here, before this upload — not duplicated

`VANITYKEYFOUND2.txt` (249,476 addresses at last check) is already live at the repo root and at
`masterkeybtc.com/VANITYKEYFOUND2.txt`. It is **Instance 2** of the five-instance main study below
— the only one of the five that kept collecting after the study's frozen cut, which is why its
current count (249,476) is larger than its frozen contribution (15,255) to the 50,995-address
total reported in Section 3.1. Nothing in this upload duplicates it.

## File map → manuscript reference

| File(s) | Content | Manuscript reference |
|---|---|---|
| `ENGINEERING_MANUSCRIPT_EN.md` | Engineering manuscript — architecture, validation, optimisation trajectory of the search engine | Reference [9] |
| `COMPARATIVE_AUDIT_FIVE_ENGINES_EN.md` | Comparative audit report, 5 tools, 24 defects | Reference [10] |
| `AUDIT_KEYHUNT_CPU_2026-08-05_EN.md`, `AUDIT_KEYHUNT_CUDA_2026-08-05_EN.md`, `AUDIT_BITCRACK_CUDA_2026-08-15_Port_EN.md`, `AUDIT_CUDACYCLONE_2026-08-15_EN.md`, `AUDIT_MASTERKEY_2026-08-16_EN.md` | The 5 individual per-tool audits behind the comparative report | Reference [10], Section 2.1.1 |
| `MAIN_STUDY_INSTANCE_1.txt`, `_3.txt`, `_4.txt`, `_5.txt` | Instances 1, 3, 4, 5 of the free-sampling main study — **byte-identical to the frozen counts reported** (17,770 / 5,732 / 6,348 / 5,890). Instance 2 is `VANITYKEYFOUND2.txt` (see above) | Section 3.1 (~50,995 total), Section 2.8 (confirmation set = instances 3+4+5) |
| `ACCUMULATED_CORPUS_1PWo3Je_PART1of2.txt`, `_PART2of2.txt` | All addresses collected for prefix `1PWo3Je` to date (511,131 at packaging time, split into two files of ~13.6 MB each to stay under GitHub's 25 MB web-upload limit; the manuscript's frozen figure is 504,183 — see note below). Simply concatenate the two files to recover the single original list. | Sections 3.1, 3.6.5, 3.8.4 |
| `VANITYKEYFOUND_1oeg42bit.txt`, `VANITYKEYFOUND_1MBX35bit.txt`, `VANITYKEYFOUND_13qZ35bit.txt`, `EXHAUSTIVE_CENSUS_20bit.txt` | Three independent prefix censuses + the fully exhaustive 20-bit census | Section 3.4 |
| `FIXED_BIT_LINE_SWEEP_RETEST_DATASET.txt` (+ its own `_README.md`), `FIXED_BIT_LINE_1PWo3JeB9_SUBSET.txt` | Raw sweep + deep-retest data (Section 3.8, Phases 1-2) and the `1PWo3JeB9`-prefix subset behind the formal test of §3.8.4 | Section 3.8 |
| `EC_SCALAR_MULT_TRACE_DATASET.jsonl` (+ its own `_README.md`) | Consolidated scalar-multiplication trace dataset behind the two exact identities | Section 4 |
| `PRE_REGISTERED_HYPOTHESIS.txt`, `PRE_REGISTERED_HYPOTHESIS.txt.ots` | The pre-registered hypothesis document (original, in Portuguese — its exact byte content is what the SHA-256 hash and OpenTimestamps proof anchor; **do not edit**) and the proof itself | Section 2.8 |
| `PRE_REGISTERED_HYPOTHESIS_EN_TRANSLATION.txt` | An English translation of the above, for readability only — carries no cryptographic standing of its own; verify against the original file, not this one | Section 2.8 (supporting) |
| `statistical_power_analysis.py` | Statistical power-analysis script (self-contained, no data file needed) | Section 2.7 |
| `base58check.py` | From-scratch Base58Check decoder (no third-party packages), used by the script below | Supports Section 3.6.2 |
| `section3_chi_square_reconstruction.py` | Reproduces the confirmatory test (§3.3), the three range-generalisation censuses and the encoding-boundary/Benford tests (§3.4-3.5) from the raw files above, cross-checked against `scipy` | Sections 3.3, 3.4, 3.5 |
| `section36_hash160_tests.py` | Reproduces the avalanche, collision and bit-correlation tests on the exhaustive census (§3.6.2), using `base58check.py` | Section 3.6.2 |

## Known gap: the accumulated corpus here is not byte-identical to the manuscript's frozen 504,183

Collection continued after the manuscript's data cut-off (2 September 2026, per Section 3.1).
The two `ACCUMULATED_CORPUS_1PWo3Je_PART*of2.txt` files together are the **current, larger** state of the same collection (511,131
addresses at packaging time), not a preserved historical snapshot at exactly 504,183 — no such
snapshot was saved separately at the time. This is disclosed rather than hidden: every re-analysis
in the manuscript that uses the accumulated corpus (Sections 3.6.5, 3.8.4) reproduces the same null
result at the frozen 504,183 cut, so a third party recomputing against this larger, current file
should expect either an identical or a slightly more powered version of the same conclusion — not
a different one.

## What this package does and does not cover

Four scripts here (`statistical_power_analysis.py`, `section3_chi_square_reconstruction.py`,
`section36_hash160_tests.py`, plus the `base58check.py` decoder they share) reproduce, from the raw
files in this same upload, the numbers in Sections 2.7, 3.3, 3.4, 3.5 and 3.6.2 — each
cross-checked against an independent implementation (own Pearson chi-square vs. `scipy.stats`) with
zero divergence. The remaining numbers reported in Section 3 (the rest of §3.2, §3.6.1, §3.6.3,
§3.6.4, §3.6.5, §3.8) are recomputable from the data files in this upload but do not yet have a
dedicated published script — Section 9 of the manuscript states this explicitly rather than
implying full coverage.

## Verification already performed while assembling this package (2026-09-12)

- Every key in `FIXED_BIT_LINE_SWEEP_RETEST_DATASET.txt` was checked against `[2^70, 2^71)`: 0 of
  13,838 outside the declared range.
- The two identities behind `EC_SCALAR_MULT_TRACE_DATASET.jsonl` were independently recomputed
  from the raw trace, not copied from the manuscript: 42,404/42,404 for both.
- `MAIN_STUDY_INSTANCE_{1,3,4,5}.txt` line counts (17,770 / 5,732 / 6,348 / 5,890) match the
  manuscript's own per-instance breakdown exactly, and the confirmatory test of Section 3.3,
  recomputed from instances 3+4+5, matches exactly (z=-2.4544, p=0.9929).
- The three range-generalisation census files sum to 924,268, matching the manuscript exactly.
- `section36_hash160_tests.py`'s three tests on the exhaustive census all match the manuscript
  exactly (avalanche, collision, bit-correlation).
