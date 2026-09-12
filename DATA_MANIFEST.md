# MasterKey — Data and Code Availability Package

This package is meant to be added to `github.com/Mrluis-Naka/MasterKeyWeb` (the repository already
serving `masterkeybtc.com` and `VANITYKEYFOUND2.txt`), so that Section 9 of the study manuscript
(`PAPER_LEDGER_EN.md`) can cite a single, complete, resolvable location for everything it currently
lists as "prepared, to be added." Folder names mirror the manuscript's own vocabulary so a reviewer
can go from a citation directly to the right file.

## What's already public, elsewhere in the same repo — not duplicated here

`VANITYKEYFOUND2.txt` (249,476 addresses at last check) is already live at the repo root and at
`masterkeybtc.com/VANITYKEYFOUND2.txt`. It is **Instance 2** of the five-instance main study below
— the only one of the five that kept collecting after the study's frozen cut, which is why its
current count (249,476) is larger than its frozen contribution (15,255) to the 50,995-address
total reported in Section 3.1. Nothing here duplicates it.

## Folder map → manuscript reference

| Folder | Content | Manuscript reference |
|---|---|---|
| `engineering/` | Engineering manuscript, comparative audit report, and the 5 individual per-tool audits (all English) | References [9] and [10] |
| `data/main_study_five_instances/` | Instances 1, 3, 4, 5 of the free-sampling main study — **byte-identical to the frozen counts reported** (17,770 / 5,732 / 6,348 / 5,890). Instance 2 is `VANITYKEYFOUND2.txt` (see above). | Section 3.1 (~50,995 total), Section 2.8 (confirmation set = instances 3+4+5) |
| `data/accumulated_corpus/` | All addresses collected for prefix `1PWo3Je` to date (511,131 at packaging time; the manuscript's frozen figure is 504,183 — see note below) | Sections 3.1, 3.6.5, 3.8.4 |
| `data/range_generalization_censuses/` | Three independent prefix censuses (`1oeg`, `1MBX`, `13qZ`) + the fully exhaustive 20-bit census | Section 3.4 |
| `data/fixed_bit_line/` | Raw sweep + deep-retest data (Section 3.8, Phases 1-2) and the `1PWo3JeB9`-prefix subset behind the formal test of §3.8.4 | Section 3.8 |
| `data/section4_trace/` | Consolidated scalar-multiplication trace dataset behind the two exact identities | Section 4 |
| `pre_registration/` | The pre-registered hypothesis document and its OpenTimestamps proof | Section 2.8 |
| `scripts/` | Statistical power-analysis script | Section 2.7 |

## Known gap: the accumulated corpus here is not byte-identical to the manuscript's frozen 504,183

Collection continued after the manuscript's data cut-off (2 September 2026, per Section 3.1). The
file in `data/accumulated_corpus/` is the **current, larger** state of the same collection (511,131
addresses at packaging time), not a preserved historical snapshot at exactly 504,183 — no such
snapshot was saved separately at the time. This is disclosed rather than hidden: every re-analysis
in the manuscript that uses the accumulated corpus (Sections 3.6.5, 3.8.4) reproduces the same null
result at the frozen 504,183 cut, so a third party recomputing against this larger, current file
should expect either an identical or a slightly more powered version of the same conclusion — not
a different one. If exact reproduction of the published 504,183-row statistic matters more than
this note allows for, that specific historical cut has not been located and may not exist as a
separate artifact.

## Still not in this package

The statistical analysis scripts that produce the chi-square and Monte Carlo numbers reported in
Section 3 (as opposed to the power-analysis script in `scripts/`, which is a self-contained
calculation, not a data-consuming pipeline) were not found as a standalone, publishable artifact
during preparation of this package. This is recorded here rather than silently omitted; closing it
requires either locating the original computation or reconstructing it from the published data
above.

## Verification already performed while assembling this package (2026-09-12)

- Every file in `data/fixed_bit_line/` was checked key-by-key against `[2^70, 2^71)`: 0 of 13,838
  outside the declared range.
- The two identities in `data/section4_trace/` were independently recomputed from the raw trace,
  not copied from the manuscript: 42,404/42,404 for both.
- `data/main_study_five_instances/instance{1,3,4,5}.txt` line counts (17,770 / 5,732 / 6,348 /
  5,890) match the manuscript's own per-instance breakdown exactly.
- The three range-generalisation census files sum to 924,268, matching the manuscript exactly.
