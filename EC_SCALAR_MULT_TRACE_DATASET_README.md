# EC Scalar Multiplication Trace Dataset — companion to Section 4

This file (`EC_SCALAR_MULT_TRACE_DATASET.jsonl`) is a consolidated, reviewer-facing export of the
42,404 instrumented `double-and-add` scalar-multiplication traces underlying the two closed
identities reported in Section 4 of the study manuscript (`PAPER_LEDGER_EN.md` /
`PAPER_CONDITIONAL_UNIFORMITY_EN.md`).

**Source of truth**: the full raw traces (42,404 cases, ~11 GB, one JSON per case with every
individual `ec_add`/`ec_double` step and its intermediate field-arithmetic values) live in
`ml_lab/ml_memory_ec_scalar_mult/mech_knowledge_base/`, produced by
`ml_lab/generate_ec_scalar_mult_cases.py` from `resultados_vanity/VANITYKEYFOUND2.txt` (explicit
user authorisation on record, 2026-07-25, to use these project-owned vanity-search keys for this
purpose). This `.jsonl` file is a lossy-by-design extraction of exactly the fields needed to
independently re-verify both identities, without requiring the full 11 GB archive.

## Format

One JSON object per line, 42,404 lines, UTF-8, no external dependencies to parse. Fields:

| Field | Meaning |
|---|---|
| `case_id` | Case identifier, matches the filename in the raw archive |
| `privkey_hex` | The private key for this case (256-bit hex, zero-padded; value is in `[2^70, 2^71)`) |
| `bit_length_medido` | `int(privkey_hex, 16).bit_length()`, computed independently from the key |
| `hamming_weight_medido` | Popcount of the key, computed independently from the key |
| `n_ec_add_medido` | Count of `ec_add` steps in the actual recorded trace |
| `n_ec_double_medido` | Count of `ec_double` steps in the actual recorded trace |
| `n_estados_total_medido` | `n_ec_add_medido + n_ec_double_medido` |
| `n_estados_previsto_bl_plus_hw` | `bit_length_medido + hamming_weight_medido` (Identity 1's prediction) |
| `identidade1_bate` | `n_estados_previsto_bl_plus_hw == n_estados_total_medido` |
| `maior_run_double_medido` | Longest run of consecutive `ec_double` steps actually observed in the trace |
| `maior_run_zero_previsto_da_chave` | Predicted from the key alone (Identity 2's closed rule, Section 4.1) |
| `identidade2_bate` | `maior_run_double_medido == maior_run_zero_previsto_da_chave` |

## Independent re-verification (done during this export, 2026-09-12)

Both identities were recomputed from scratch against the raw trace — not copied from any
previously reported figure — as part of producing this export:

- **Identity 1** (`n_estados = bit_length(key) + Hamming_weight(key)`): **42,404/42,404** match.
- **Identity 2** (longest run of 0 bits ⇄ longest run of `ec_double`): **42,404/42,404** match,
  after correcting a bug in the first extraction pass (see below).

Both figures reproduce the manuscript's published counts exactly.

**Bug found and fixed during this export**: the first extraction attempt scored Identity 2 at
41,969/42,404 (435 mismatches). Cause: the leading-run branch of the identity ("the initial run
of 0 bits before the first 1 bit") was implemented against the most-significant end of the key
(`bin(v)` leading zeros — always 0 for a positive integer, so the branch was silently inert).
The engine processes bits **LSB-first** (`double-and-add` starting at bit 0, confirmed by the
`origin: "bit 0"` field on the first trace state), so "before the first 1 bit" refers to the
**trailing** zero bits of the key (its 2-adic valuation), not the leading zeros of its MSB-first
representation. Recomputing that branch as the count of trailing zero bits made the identity
match exhaustively. This is recorded here, in the open, per this project's standing policy of
reporting negative/failed intermediate steps with the same rigor as the final result.

## Why this file and not the full 11 GB archive

The raw archive stores the complete causal chain per case — every intermediate field-arithmetic
value of every `ec_add`/`ec_double` step (~256 KB/case) — which is what the project's own
mechanistic-query tooling (`ml_lab/mathematician.py`) needs, but is far more than a reviewer needs
to check the two identities of Section 4. This file keeps exactly the private key and the measured
operation counts, which is sufficient for full independent recomputation, at ~17 MB instead of
~11 GB. The raw archive remains available on request and can be added to the same Zenodo deposit
as a secondary, non-default download if a reviewer wants the full mechanistic trace rather than
the aggregate counts.
