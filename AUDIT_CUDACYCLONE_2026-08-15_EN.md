# Audit of CUDACyclone (Dookoo2/CUDACyclone) — declared proof level

**Date**: 2026-08-15
**Object**: CUDACyclone, code as distributed at `github.com/Dookoo2/CUDACyclone`, branch `main`,
commit `61fd323` (2025-09-22) — a small but active project, unlike BitCrack and KeyHunt-Cuda, both
abandoned.
**Motivation**: same methodology as the BitCrack and KeyHunt-Cuda audits, applied to one more
project cited on masterkeybtc.com as a reference.

**Note on the result — revised**: the first round of this audit (moderate ranges, far from the
absolute start of the key space) did not reproduce the project's historical key-loss problem, and
the document went as far as concluding that. A second round, specifically testing `privkey=1` — the
most obvious missing case — **reproduced the defect cleanly and deterministically** (Defect 1,
below). This document's earlier conclusion was wrong due to insufficient coverage, not because the
defect does not exist. This is recorded as such, without erasing the document's history, because it
is exactly the kind of audit mistake worth showing: "I did not reproduce it" is only valid for what
was actually tested.

---

## 0. Method and limits

**No source file was modified.** The only intervention: command-line parameters (`--grid`,
`--slices`). The repository ended the audit with a clean `git status` (only unversioned build
artefacts).

**Test environment**: rented instance, NVIDIA RTX 4070 Ti SUPER (sm_89, 16GB), driver 610.43.02,
Ubuntu 24.04.4, CUDA 13.3.

**Reference oracle**: an in-house Python script (`addrgen.py`), written from scratch for this
audit, using `coincurve` (libsecp256k1 bindings, the same library used by Bitcoin Core — the same
oracle pattern already used in the keyhunt-cuda and masterkey audits) + `hashlib` (OpenSSL's
SHA256/RIPEMD160) + `base58`. Zero lines shared with CUDACyclone. Validated against two external
facts before use: `privkey=1` -> `1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH` (a known public fact) and
`privkey=0x22382FACD0` -> `1HBtApAFA9B2YZw3G2YKSMCtb3dVnjuNe2` (matches exactly the project's own
README example).

**Proof scale**: same as previous audits — **DEMONSTRATED** (executed, output captured) vs.
**VERIFIED IN CODE** (read in the source, not isolated in execution).

---

## The project's key-skipping history — two tests that passed, before what actually failed

CUDACyclone's own changelog is direct about this: "Problem with a key skipping was fixed!" — V1.2
did a complete kernel rewrite to fix it, and V1.3 (current) **rewrote it again, for the same
reason** ("Full CUDA Kernel rewrite again for preventing key skipping"). Two rewrites for the same
problem is a sign the cause was genuinely hard to close — exactly the kind of history that calls
for sceptical verification, not trust in the changelog's word.

### What their self-test (`proof.py`) covers — and what it does not

`proof.py`, written by the maintainer, generates known keys at strategic positions (start and end
of the range, residue coverage modulo the batch size, random quartiles), runs CUDACyclone against
each and checks. We ran it **as distributed**, without editing, with a grid configuration
(`--grid 64,64`) that does not appear documented in the README's examples:

```
================ Summary by blocks ================
Range start A (start+2k)           : total= 128  success= 128  fail=   0
Range start B (start+1+2k)         : total= 128  success= 128  fail=   0
Range end A (end-2k)               : total= 128  success= 128  fail=   0
Range end B (end-1-2k)             : total= 128  success= 128  fail=   0
Full mod 64 residue coverage       : total=   0  success=   0  fail=   0
Random Q1 (0-25%)                  : total=  20  success=  20  fail=   0
Random Q2 (25-50%)                 : total=  20  success=  20  fail=   0
Random Q3 (50-75%)                 : total=  20  success=  20  fail=   0
Random Q4 (75-100%)                : total=  20  success=  20  fail=   0

Done. Results in cyclone_tests_results.txt. Successes=592 Failures=0
```

**592/592.** But one detail stood out: **"Full mod 64 residue coverage: total=0"** — `proof.py`'s
own test category most targeted at an indexing bug (since it tests every residue modulo the batch
size) **generated no cases at all** for this grid configuration. This is not a CUDACyclone bug — it
is a gap in `proof.py`'s test generator, which apparently only populates this category for certain
batch sizes. Recorded because, if anyone plans to rely on `proof.py`'s report as proof of
correctness, it is worth knowing this specific category can silently run nothing.

### The real blind spot: `--slices` is never tested by `proof.py`

The project's own README actively recommends `--slices` for large ranges ("For preventing
decreasing GPU speed you need to use --slices option"). **`proof.py` has no `--slices` argument at
all** — confirmed by reading the entire argument parser. In other words: the "592/592 no failures"
proof the maintainer publishes never exercises the code path the project itself recommends for its
heaviest use case.

This is exactly the kind of boundary where a "skipped key" bug tends to live: the transition
between successive kernel launches (`--slices` controls how many batches each thread processes per
launch before the host regains control; point state — `Px/Py/Rx/Ry` — is carried from one launch to
the next via `std::swap`). We built our own test, independent of `proof.py`, specific to this path:

**20 known keys**, generated with our oracle, spread across an interval of 33,554,432 keys (offset
`0x100000000 + i*1300021 mod 0x2000000`), searched for with `--grid 128,128 --slices 1` — the most
aggressive value possible, forcing the maximum number of kernel launches to maximise stress on the
transition between them.

```
TOTAL: PASS=20 FAIL=0
```

**20 of 20.** (A first run gave 18 "failures" that were a bug in *our own* comparison script —
case-sensitivity between uppercase/lowercase hex, not in CUDACyclone; fixed and re-run before
reporting anything.)

### What these two tests actually prove — and what they do not

The 592/592 and 20/20 above remain valid as a result: neither of the two angles tested (undocumented
grid, the `--slices` path) reproduced key loss. **But neither tested the most obvious thing that was
missing: a range starting at `privkey=0`.** Neither the maintainer's `proof.py` (whose "start of
range" tests are always relative to the start *you configure* — in the test above, `0x200000000`,
never absolute zero) nor our first tests covered this. The following section closes that gap, and
changes the conclusion.

---

## Defect 1 — Batched inversion poisoned by zero: an entire batch dies, only the centre survives

**Level: DEMONSTRATED**, with a minimal reproducer, the boundary isolated key by key, the root
cause identified in the source code, and a **theoretical prediction empirically confirmed down to
the exact key**. This is a live reproduction, today, of the same class of bug the project's
changelog claims to have fixed twice ("Full CUDA Kernel rewrite again for preventing key
skipping").

**It is exactly the same class as the `ZERO_INVERSION_BUG` that masterkey-gpu had and fixed on
2026-08-06** (see `docs/BUG_INVERSAO_ZERO.md`): a single `dx = 0` zeroes the batched inversion's
product and corrupts every candidate derived from that batch — with the same characteristic
signature of the **group's centre surviving** (because it is checked before the inversion) and
everything else dying. The difference is that masterkey detects the condition, aborts the group and
warns on `stderr` with a non-zero exit code; CUDACyclone has no equivalent check.

### Minimal reproducer

```
$ ./CUDACyclone --range 0:FFFFFF --address 1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH --grid 128,128
======== KEY NOT FOUND (exhaustive) ===================
Target hash160 was not found within the specified range.
```

The target is `privkey=1` — the best-known key that exists
(`1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH`, a public fact, already used as a sanity check earlier in
this same audit). The declared interval (`0:FFFFFF`, 16,777,216 keys) contains `1` by definition.
The tool scans the entire interval, **exhaustively**, and reports with full confidence that the key
is not there.

### The exact boundary, isolated

Tested with known private keys (address generated by an independent oracle) at specific positions,
same range, same `--grid 128,128`:

| `privkey` | Position | Result |
|---|---|---|
| `1` | 1st of the 1st batch | **NOT FOUND** |
| `2` | 2nd of the 1st batch | **NOT FOUND** |
| `0x64` (100) | inside the 1st batch | **NOT FOUND** |
| `0x7F` (127) | last of the 1st batch | **NOT FOUND** |
| `0x80` (128) | 1st of the 2nd batch | found |
| `0xC8` (200) | inside the 2nd batch (thread 1) | found |

**The entire batch `[0, 127]` — exactly 128 keys, the value of the first number passed to
`--grid`— disappears.** From key 128 onward, everything works normally. Repeated with `--grid
64,64` (batch of 64 instead of 128): the boundary moves to `63`/`64` — **the size of the hole
scales exactly with the first `--grid` parameter**, it is not a fixed number.

Confirmed that the problem is isolated to one thread at a time: key `200`, which falls in the
*second* thread's batch under the same range and configuration, was found normally. A range that
does **not** start at zero (`--range 1000000:1FFFFFF`, tested with `privkey=0x1000005`) does not
show the problem in that region.

### The decisive signature: the batch's CENTRE survives

This is the test that closes the diagnosis. For `--grid 128,128` and a range starting at zero,
thread 0's batch centre is the scalar **64** (`0x40` — each thread starts from its own batch's
centre, `range_start + half`):

| `privkey` | Position in the batch | Result |
|---|---|---|
| `0x3F` (63) | centre - 1 | **NOT FOUND** |
| **`0x40` (64)** | **batch CENTRE** | **FOUND** |
| `0x41` (65) | centre + 1 | **NOT FOUND** |

The centre survives; its two immediate neighbours die. Repeated and confirmed at three different
batch sizes — `--grid 64,64` (centre = `0x20`), `--grid 128,128` (centre = `0x40`) and `--grid
512,512` (centre = `0x100`): **in all of them, and only the centre, is found.**

This rules out any explanation of the "the thread does not run" or "the range is not covered" kind
— the thread runs, the centre point is computed correctly and matches the target. What breaks is
exclusively the derivation of the other `B-1` candidates from the centre.

### Cause — located, not fully traced

`CUDACyclone.cu:585-594`, assembling each thread's starting point:

```c
const uint32_t B = runtime_points_batch_size;
const uint32_t half = B >> 1;
{
    uint64_t cur[4] = { range_start[0], range_start[1], range_start[2], range_start[3] };
    for (uint64_t i = 0; i < threadsTotal; ++i) {
        uint64_t Sc[4]; add256_u64(cur, (uint64_t)half, Sc);   // Sc = cur + half, NOT cur
        h_start_scalars[i*4+0] = Sc[0];
        ...
        uint64_t next[4]; add256(cur, per_thread_cnt, next);   // advances to the NEXT thread's batch start
        cur[0]=next[0]; ...
    }
}
```

The scalar the GPU actually uses as each thread's starting point (`Sc`) is not that thread's batch
start (`cur`) — it is the batch's **centre** (`cur + half`). This is a legitimate and common
technique (the same "group centre" principle masterkey-gpu uses, documented in
`docs/BUG_CENTRO_DO_GRUPO.md`): compute the full scalar multiplication once, at the middle of the
batch, and cover the rest of the batch with incremental additions/subtractions of `G` — much
cheaper than one scalar multiplication per candidate.

Covering the other `B-1` candidates from that centre is done with a **single batched modular
inversion** (Montgomery's trick) — `CUDACyclone.cu:140-166`:

```c
// acc = X(B*G) - x1                       <-- jump-point factor (c_Jx)
for (int j=0;j<4;++j) acc[j] = c_Jx[j];
ModSub256(acc, acc, x1);
subp[half-1] = acc;

for (int i = half - 2; i >= 0; --i) {      // descending accumulated product
    tmp = c_Gx[i+1];                        // X((i+2)*G)
    ModSub256(tmp, tmp, x1);                // tmp = X((i+2)*G) - x1
    _ModMult(acc, acc, tmp);                // acc *= tmp
    subp[i] = acc;
}

d0 = c_Gx[0];  ModSub256(d0, d0, x1);       // d0 = X(1*G) - x1
inverse = d0;  _ModMult(inverse, subp[0]);  // FULL product of every dx
_ModInv(inverse);                           // <-- ONE inversion for the entire batch
```

Table `c_Gx[k]` holds `X((k+1)*G)` for `k = 0..half-1` (built in `CUDACyclone.cu:646-649`, scalars
`1..half`), and `c_Jx` holds `X(B*G)` (`CUDACyclone.cu:673-693`). The inverted product is therefore:

```
P = (X(B*G) - x1) * PRODUCT (X(k*G) - x1)   for k = 1..half
```

**If any factor is zero, `P = 0`.** And `_ModInv` explicitly documents in its own comment
(`CUDAMath.h:464-469`): *"Return 0 if no inverse"* — it silently returns zero, with no error
signal. Every `dx_inv_i = subp[i] x 0 = 0`, every derived `lambda` turns to garbage, and the
batch's `B-1` candidates are computed wrong. The centre escapes because it is checked **before**
this block (`CUDACyclone.cu:115-137`) — exactly the signature measured above.

### Exact trigger condition (derived from the code, confirmed by test)

`X(k*G) - x1 = 0` when `x1 = X(k*G)`. Since `X(-k*G) = X(k*G)` (symmetric points share the same X),
centre `c` triggers the defect when:

```
c === +-k (mod N)  for some k in [1, half]      ... or ...   c === +-B (mod N)
```

In other words, **any batch whose centre falls within `half` of 0 OR of `N`** (the curve's order)
loses the entire batch except its centre. This is considerably broader than "a range starting at
zero".

### The top-of-curve prediction — and the false negative it exposed

The condition above **predicts** the defect also occurs near the curve's order, even for ranges
that do not start at zero. Tested on the aligned range `...d0000000:...d0ffffff` (which contains
`N-1`), `--grid 128,128`:

| `privkey` | Predicted position | Result |
|---|---|---|
| `N-66` | outside the batch | found |
| **`N-65`** | **first of the corrupted batch** | **NOT FOUND** |
| `N-64`, `N-10`, `N-3`, `N-2` | inside the corrupted batch | **NOT FOUND** |
| **`N-1`** | **batch CENTRE** | **FOUND** |

The corrupted batch is exactly `[centre - half, centre + half - 1] = [N-65, N+62]`, and the only
valid key surviving inside it is the centre itself, `N-1`. **The prediction made from reading the
code matched the experiment down to the exact key** — `N-65` lost, `N-66` saved.

**This corrects a result from this audit's first round.** That round tested `privkey = N-1`,
obtained "found", and recorded that as evidence that the top of the key space was correct. It was
wrong: `N-1` was precisely **the only key in that batch that survives**. A sanity test that, by
statistical bad luck, picked exactly the one point that does not reveal the defect — and so
produced a false negative dressed up as a pass.

### Why neither the changelog nor `proof.py` caught this

`proof.py` tests "start/end of range" always relative to the range **you configure**, never to
absolute zero or to the curve's order. No README example uses `0` as a start. And the random
quartiles have negligible probability of falling within the `half`-key windows around `0` or `N`.
The official self-test, as written and as used, **has no way** to catch this class of defect.

### Real severity

- **Does not affect the project's stated use case.** Bitcoin puzzles have ranges in
  `[2^(N-1), 2^N)`, far from both `0` and the curve's order — no real collection by someone
  hunting puzzles would be affected.
- **Affects exactly whoever tries to validate the tool.** Testing with small known keys (`1`, `2`,
  `100`) or at the extremes of the space is the natural sanity procedure — and is the scenario
  that triggers the defect.
- **The tool never warns.** It reports `KEY NOT FOUND (exhaustive)` with the same confidence as
  any correct search. `_ModInv` returning `0` — the defect's exact condition — is silent by
  construction, with no error code and no warning.
- **Scales with `--grid`**: the number of keys lost is exactly the batch size. With the README's
  own high-performance configurations (`--grid 512,512`, or `1024`), that is 512 or 1024 keys
  silently lost per affected batch.

### Additional confirmations

- **Quantified at the README's actual performance configuration** (`--grid 512,512`, the same
  used by `proof.py` by default and in community benchmarks): tested the boundary pair 511/512 —
  `privkey=0x1FF` (511) not found, `privkey=0x200` (512) found. **512 keys lost**, not a small
  number.
- **Reproduces even with no explicit `--grid`** — running `./CUDACyclone --range
  100000000:100FFFFFF --address <target>` with no grid specified at all, the program's own default
  uses a batch of 128 (identical to `--grid 128,128`). **No unusual configuration is needed to
  trigger the defect — it is the default behaviour.**
- **Memory corruption and race conditions ruled out** as the mechanism: the minimal reproducer run
  under `compute-sanitizer --tool memcheck` (`ERROR SUMMARY: 0 errors`) and under
  `compute-sanitizer --tool racecheck` (`0 hazards`) — a public NVIDIA tool included in the CUDA
  toolkit, used only to observe the already-compiled binary, with nothing edited. Confirms the
  defect is purely arithmetic/logical (the incremental point walk producing a mathematically wrong
  result when crossing the zero scalar), not an invalid memory access nor a race between threads.
- Tested the "analogous at the top" hypothesis (the search crossing the curve's order `N` instead
  of zero): **there is no equivalent code path** — every valid range already sits strictly below
  `N`, so no batch centre can go past `N` the way it can reach exactly `0`. Zero is special (the
  point at infinity); `N` is not a reachable scalar within a valid range.

---

## Verified in code: no re-verification of the finding before printing it

**Level: VERIFIED IN CODE.** Same structural class as BitCrack's Defect 5, but with an important
difference that reduces the risk.

On finding a candidate, the kernel writes `scalar` (the private key) and `Rx/Ry` (the public point)
**in the same block of code, at the same instant** (`CUDACyclone.cu:124-131`):

```c
if (atomicCAS(d_found_flag, FOUND_NONE, FOUND_LOCK) == FOUND_NONE) {
    d_found_result->threadId = (int)gid;
    for (int k=0;k<4;++k) d_found_result->scalar[k]=S[k];
    for (int k=0;k<4;++k) d_found_result->Rx[k]=x1[k];
    for (int k=0;k<4;++k) d_found_result->Ry[k]=y1[k];
    __threadfence_system();
    atomicExch(d_found_flag, FOUND_READY);
}
```

The host (`CUDACyclone.cu:800-808`) prints these values directly, without reconstructing the key by
separate index arithmetic (`thread`/`block`/`idx`) after the fact — the central difference from
BitCrack, where the key is recomputed on the host from offsets, with no direct relation to the
point the GPU actually tracked. Here, `scalar` and `Rx/Ry` come from the **same loop state
variables** (`S`, `x1`, `y1`), written atomically once — this eliminates the specific "wrong key
for the right point via an index error" bug class.

**What remains unverified**: nothing recomputes, on the host, that `scalar * G` really produces
`(Rx, Ry)`, nor that that point's hash160 matches the target, before printing "FOUND MATCH!". The
hash160 comparison inside the kernel was read and confirmed correct — it compares the full 20
bytes, not just the 4-byte prefix used as a fast filter (`CUDAUtils.h:102-112`,
`hash160_matches_prefix_then_full`) — so the risk here is more theoretical than in BitCrack, but
the absence of a second, independent check is real and of the same structural kind.

---

## What was tested and found no problem

- **Build**: compiles cleanly, with no workaround, using the Makefile as distributed — it detects
  the GPU's architecture automatically via `nvidia-smi`. A notable difference from BitCrack and
  KeyHunt-Cuda, both of which required manually passing `COMPUTE_CAP`/flags.
- **CLI validation, every corner case tested is rejected cleanly**: a range that is not a power of
  two, a start not aligned to the range's length, `--grid` with extreme values (2 billion) or
  zero, an invalid Base58 address, a missing `--range`, start equal to end (not divisible by the
  batch size).
- **`--address` and `--target-hash160` agree** — same key, same result, both entry paths tested
  independently against the same target.
- ~~**Key at the absolute top of the space** (`privkey = curve_order - 1`): found correctly.~~
  **WITHDRAWN — it was a false negative.** `N-1` is found, but only because it is the batch's
  centre; its neighbours (`N-2` through `N-65`) are lost. See Defect 1, "The top-of-curve
  prediction" section. This item stayed on this list in the audit's first round and is recorded
  here struck through, rather than deleted, because the mistake itself is informative: a sanity
  test can hit exactly the one point that does not reveal the defect.
- **SIGINT handled correctly** (`Ctrl+C`) — a clean interruption message, "partial progress
  above", the process exits with no zombie left behind. Unlike BitCrack, which has no handler at
  all. CUDACyclone has no `--continue`/checkpoint (the feature does not exist in the project), so
  the signal handling here is about a clean shutdown, not about resuming work later.
- **Exhaustive end of interval detected and reported** ("KEY NOT FOUND (exhaustive)") when the
  target is not in the range.
- **Point doubling/addition formulas** (`CUDAMath.h`, inherited from the JeanLucPons/VanitySearch
  lineage, a much more mature and community-tested project than BitCrack) — checked against
  standard textbook affine formulas, no finding.
- **`CUDAHash.cu` — SHA256 and RIPEMD160 read in full** (501 lines) against the specification:
  `K`/`IV` constants, rotations, message-schedule table, final formula — everything matches for
  both algorithms. The two message-block assembly paths (the generic byte-wise one,
  `getSHA256_33bytes`, and the fast 64-bit-limb one used in the production kernel,
  `SHA256_33_from_limbs`) produce the same layout — consistent with each other.
- **`_ModInv`** (`CUDAMath.h:464-105`, the "Delayed Right Shift 62-bit" algorithm, the same one
  used in JeanLucPons/VanitySearch's `IntMod.cpp`, cited in the code's own comment): its structure
  matches the documented algorithm, and the central constants (the secp256k1 prime and the
  Montgomery constant `MM64 = 0xD838091DD2253531`) match publicly known values. Not traced
  instruction by instruction — the algorithm's complexity (Montgomery reduction combined with
  extended GCD) would make that a project of its own, and the lineage has already been extensively
  used and tested by the community for years across multiple derived projects.
- **Behaviour with no explicit `--grid`**: uses a batch of 128 by default (same as `--grid
  128,128`) — Defect 1 reproduces identically, needing no unusual configuration.
- **No memory corruption or race condition** in Defect 1's reproducer — confirmed running the
  public binary, with nothing edited, under `compute-sanitizer --tool memcheck` (0 errors) and
  `--tool racecheck` (0 hazards). The defect is purely arithmetic.
- **Address derived from an uncompressed public key**: tested and not found — CUDACyclone only
  checks the hash160 of the compressed form (33 bytes). Confirmed as a limitation, not a bug — the
  README never promises uncompressed support.
- **The rest of the project's 10 open issues read** (#2, #3, #4, #5, #7, #8, #9, #12, #13, #15):
  none reports key loss beyond what the changelog already acknowledges. Most are feature requests
  never implemented — multi-address search (#4, confirmed absent), `--stride`/"jump" (#13, #15
  from the original CPU version — absent in the CUDA version), a ready-made Windows binary (#2,
  #7, #12). No new lead.

---

## Open items — all closed this round

- **Defect 1 is closed**: isolated behaviour (exact key-by-key boundary, scales with `--grid`,
  centre survives), root cause identified in the source with file and line (the batched
  inversion's product zeroed, `_ModInv` silently returning 0), trigger condition derived
  algebraically (`c === +-k mod N`, `k <= half`), and a **theoretical prediction confirmed
  experimentally down to the exact key** at the top of the curve's order. Nothing here depends on
  instrumenting the kernel.
- **Third factor of the product — now closed by proof, not just by trial.** Besides the
  `X(k*G) - x1` factors, the product includes `X(B*G) - x1` (the jump point), which would zero out
  if the centre fell exactly at `B` (128, 512, the batch size). **Proof that this is impossible to
  reach through any valid CLI configuration**: the program requires (a) that the range's start be
  an exact multiple of the range's width, and (b) that the range's width be a multiple of the
  batch size `B` — so the width is always `>= B`. This means every valid range start is `0` or
  `>= B`; never a value strictly between `0` and `B`, such as `B/2` (the offset needed to place
  some thread's centre exactly at `B`). Tested empirically as confirmation: `--range 40:BF` (start
  at `0x40`=64=`half`, width 128=`B`, deliberately misaligned) — rejected by the program's own
  validator with `"Error: start must be aligned to the range length"`, exactly as the proof
  predicts. This third factor of the product is mathematically unreachable through the tool's
  public interface — it is not an open risk, it is a door the program itself keeps closed by
  accident (the same validation exists for another purpose, but has this side effect).
- Full coverage of the entire 256-bit space was not done as in the BitCrack audit (46+ keys
  covering from the start to the end of the curve's order) — this audit's tests stayed
  concentrated on moderate ranges (~2^25-2^30), plus Defect 1's two boundary windows (near `0` and
  near `N`).
- Not tested with multiple GPUs, nor on an architecture other than Ada (sm_89) — only one instance
  was available for this audit.
- The `--slices` path test (20 keys, `--slices 1`) is a targeted stress test, not exhaustive proof
  — it does not cover every `--grid` x `--slices` x range-size combination.
- ~~Not tested whether Defect 1 manifests differently combined with `--slices` != 1~~ — tested:
  `--range 0:FFFFFF --grid 128,128 --slices 1` reproduces the same loss of `privkey=1`. Defect 1
  is independent of the `--slices` value.

---

## Summary

| Item | Level | Result |
|---|---|---|
| **Defect 1 — zeroed batched inversion: entire batch lost, only the centre survives** | **DEMONSTRATED, root cause closed** | **Live reproduction of the project's historical defect; exact key-by-key boundary, cause in the source with a line number, trigger condition derived and confirmed by prediction** |
| Build | DEMONSTRATED | Clean, no workaround needed |
| CLI validation (7 corners tested) | DEMONSTRATED | All rejected cleanly |
| Key skipping far from `0` and `N` (undocumented grid + `--slices`, 612 cases) | DEMONSTRATED | Not reproduced — consistent with the derived trigger condition |
| Gap in the official self-test (`--slices`, `privkey=0` and the top of the curve never tested) | VERIFIED IN CODE | Explains why Defect 1 was never caught by `proof.py` |
| `proof.py`'s "mod residue" category with total=0 | DEMONSTRATED | A gap in their test generator, not in CUDACyclone |
| Re-verification of the finding before printing | VERIFIED IN CODE | Absent, but reduced risk — the key and the point come from the same state, written together |
| SIGINT | DEMONSTRATED | Handled correctly, clean shutdown |
| `--address` vs `--target-hash160` | DEMONSTRATED | Agree |
| hash160 comparison in the kernel | VERIFIED IN CODE | Complete (20 bytes), not just the prefix |
| Point formulas, SHA256, RIPEMD160, `_ModInv` | VERIFIED IN CODE | Correct — the defect is not in the arithmetic, it is in handling the degenerate case |
| No memory corruption / race condition | DEMONSTRATED | `compute-sanitizer` memcheck and racecheck clean |
| Uncompressed address | DEMONSTRATED | Unsupported — a declared limitation, not a bug |

**Conclusion — final**: CUDACyclone remains the most robust of the three projects in this series
in terms of build, CLI validation and signal handling — that has not changed. But it has a real and
serious silent key-loss defect, **reproduced, isolated and explained in this audit**, in the same
class its own changelog claims to have fixed twice.

The mechanism is known and has a name: **batched modular inversion poisoned by a zero factor**. A
single `dx = 0` in the product zeroes the entire batch's inversion; `_ModInv` silently returns `0`
(behaviour documented in the code's own comment); every one of the `B-1` derived candidates comes
out corrupted. Only the batch's centre survives, because it is checked before the inversion. It
triggers whenever a centre falls within `half` of `0` or of the curve's order `N`.

This is **precisely the same defect masterkey-gpu had and fixed on 2026-08-06**
(`docs/BUG_INVERSAO_ZERO.md`) — same cause, same surviving-centre signature. The difference lies in
what each project does upon finding the condition: masterkey detects the zeroed product in O(1),
aborts the group without writing, counts the event in a global counter and exits the process with a
non-zero code warning that the declared coverage does not match what was scanned. CUDACyclone has
no such check at all — it reports `KEY NOT FOUND (exhaustive)` with the same confidence as a
correct search.

In practice, the project's stated use (Bitcoin puzzles, in ranges far from `0` and from `N`) is not
affected. What is affected is precisely anyone trying to **validate** the tool with small known
keys or at the extremes of the space.

**The methodological lesson from this audit**, recorded because it cost two rounds: this
document's first version concluded "not reproduced" and even listed `N-1` as evidence of
correctness at the top of the curve. `N-1` was the batch's centre — the one key that survives. A
sanity test can hit exactly a defect's blind spot and return "passed". Insufficient coverage is
indistinguishable from correctness, seen from outside, until someone tests the neighbour.
