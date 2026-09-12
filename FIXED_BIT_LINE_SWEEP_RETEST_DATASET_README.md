# Fixed-Bit Line Dataset (Section 3.8, Phases 1-2) — companion file

`FIXED_BIT_LINE_SWEEP_RETEST_DATASET.txt` consolidates the raw address:key output of the two
phases of the fixed-bit experimental line described in Section 3.8 of the study manuscript
(`PAPER_LEDGER_EN.md` / `PAPER_CONDITIONAL_UNIFORMITY_EN.md`): the 42-bit exploratory sweep
(§3.8.2) and the 4-notable-bit deep retest (§3.8.3). It does **not** include the separate
`1PWo3JeB9`-prefix subset used for the formal test of §3.8.4 — that one is published as
`FIXED_BIT_LINE_1PWo3JeB9_SUBSET.txt`.

## Provenance

- **Design**: `bits 70,69` permanently fixed (the range-defining bit plus the one bit found common
  to the three known rare addresses that motivated the line), a third candidate bit swept
  automatically, one at a time, 30 min/bit, no prior hypothesis about which bit would matter.
  Full narrative: `varredura_terceiro_bit_resultados.txt` (repo root).
- **Phase 1** (`§3.8.2`, 42 bits, positions 10-51): three RTX 4070 Ti Super instances, non-overlapping
  ranges (`sweepA` 10-23, `sweepB` 24-37, `sweepC` 38-51), `--no-glv`, 2026-07-18/19. Raw files:
  `resultados_vanity/VANITYKEYFOUNDsweep{A,B,C}b<bit>.txt`, 42 files, 7,138 lines.
- **Phase 2** (`§3.8.3`, 4 notable bits retested at ~10x volume, 5h each): bits 29, 30 (`deepA`
  instance) and 16, 50 (`deepB` instance). Raw files: `resultados_vanity/VANITYKEYFOUNDdeep{A,B}b<bit>.txt`,
  4 files, 6,700 lines.
- **This file**: the 46 raw files concatenated, one line per address:key pair, each tagged with a
  trailing `# segment=<sweepX|deepX>b<bit>` comment identifying which fixed-bit configuration
  produced it — needed to reproduce the per-bit percentage table in §3.8.3, not present in the raw
  files themselves (segment membership was previously tracked only by which physical file a line
  lived in).

## Independent verification done while preparing this export (2026-09-12)

- **Total count**: 13,838 lines across the 46 files — matches the sum of the manuscript's own
  stated per-phase counts (7,138 + 6,700 = 13,838) exactly.
- **Correction found and applied**: the manuscript's abstract and §3.1 previously stated "~16,327"
  for this line, which does not match the sum of its own reported phase components. This was a
  stale figure never reconciled against the final per-bit files; both `PAPER_LEDGER_EN.md` and
  `PAPER_LEDGER_PT.md` were corrected to 13,838 on 2026-09-12, with the correction noted in place.
  `PAPER_CONDITIONAL_UNIFORMITY_EN.md` (the original, non-Ledger manuscript) was **not** modified,
  per this project's standing policy of never editing that file.
- **Range compliance**: every one of the 13,838 private keys was independently checked against
  `[2^70, 2^71)`. Result: **0 of 13,838 outside the declared range.** This check specifically
  matters because `docs/BUG_FIXBITS_RANGE.md` documents a real, deliberately-unfixed defect in the
  engine's `--fix-bits` range guard (an OR-after-add can in principle push a key past `end`). That
  document's own analysis argues the defect cannot manifest when the fixed bits sit below the
  range's leading bit — true for every configuration in this line (fixed bits were always in
  10-51, the range boundary is bit 70) — and this export confirms that analysis empirically rather
  than resting on it by argument alone.
- **No cross-segment duplicate addresses**: 13,838 lines, 13,838 distinct addresses. Unlike the
  later, unrelated 35-simultaneous-bit combinatorial experiment (`docs/TESTE_MASSIVO_35_BITS.txt`),
  where sequential consumption of the combinadic rank caused massive address rediscovery, each
  segment here fixes a different *single* bit position, so the sampled subspaces do not overlap
  in a way that produces repeat findings.

## Note on a related, separate experiment

`docs/TESTE_MASSIVO_35_BITS.txt` documents a later, more ambitious fixed-bit experiment (35 bits
fixed simultaneously, combinatorial coverage via a rank-to-combination bijection) that is **not**
part of Section 3.8 and is not included in this dataset. It is a distinct research line with its
own real methodological finding (75.3% duplicate rate from sequential combinadic enumeration,
fixed by a Weyl-sequence rank scramble) and is not currently referenced by the study manuscript.
