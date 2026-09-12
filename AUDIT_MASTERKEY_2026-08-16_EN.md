# Audit — masterkey-gpu (this project's own code) — 2026-08-16

Scope: `cli/search_runner_cuda.cu` (the four search paths), `gpu/host/bloom_filter.cu`,
`gpu/kernels/bloom_ops.cuh`, and `tests/parity/` coverage. Applies the **same rubric** used in this
project's audits of third-party tools (`AUDIT_KEYHUNT_CPU_2026-08-05_EN.md`,
`AUDIT_KEYHUNT_CUDA_2026-08-05_EN.md`, `AUDIT_CUDACYCLONE_2026-08-15_EN.md`,
`AUDIT_BITCRACK_CUDA_2026-08-15_Port_EN.md`) plus the 10-item test-rigor checklist.

The central question is the same one put to the others: **does the tool lose findings, or claim
coverage it did not achieve?**

Two-layer method: reading the code (§1-§3) and then **running on the GPU with production paused**
(§3-B), reproducing the test that failed each third-party tool. The second layer exists because the
first, alone, is what let the two defects in §1 slip through for months.

## Summary

**None of the five defects found in third-party tools exists here** — each was deliberately
provoked on the GPU and did not appear (§3-B).

Six own findings, **five fixed this session**:

| # | Finding | State |
|---|---|---|
| 1.1 | Result truncation exited with `exit=0` on all 4 paths (one of them, in total silence) | fixed |
| 1.2 | Write without `flush` on 2 of the 4 paths | fixed |
| 2.0 | `ctest` reported "No tests were found!!!" and exited with success | fixed |
| 2.2 | Kernel error attributed to the wrong launch | fixed |
| 2.3 | `--fix-bits` could generate a key outside the range | fixed |
| 2.4 | Multi-target silently returned an incomplete result | door closed |
| **2.1** | **None of the 4 search functions is covered by an automated test** | **open** |

Regression checked after all fixes: the agreement protocol gave a **sha256 identical** to the
six-architecture reference (15,366 findings, byte for byte) — no key changed.

---

## 1. Findings fixed this session

### 1.1 Result truncation exited with `exit=0` — on all four paths

When a hop finds more matches than fit in the buffer (`kMaxResults`), the excess is discarded. The
code detected this and warned on stderr — the original comment already said *"real data loss for
this hop"* — but none of that reached the exit code. The process ended with `exit=0`, and the file
path still printed `[+] SUCCESS`.

This is exactly item 6 of the rubric this project applies to others: *"correct exit code on
failure — never `exit=0` claiming coverage that did not happen"*. Anyone orchestrating by script
(supervisord, cron, dashboard) had no way to distinguish "scanned everything" from "scanned and
threw part of it away".

**Aggravating factor found during the fix:** `runVanitySearchMultiConfig` was the only one of the
four that truncated in **total silence** — `std::min(foundCount, kMaxResults)` discarded the excess
without even the stderr warning the other three had. It did not surface on the initial reading;
only by walking all four paths applying the same pattern.

**Fix:** a truncation flag that reaches the `return` (alongside `anyVerificationFailed` and the
degenerate-group counter, which already did this), an explicit `[E] INCOMPLETE` message, and
`SUCCESS` only when the scan was complete.

**How this was tested (not a simulated test):** compiled a variant with `kMaxResults = 4` and ran
it against prefix `1PWo` (short enough to overflow), which produced real overflows of 70, 52, 72,
37 and 64 matches per hop. Verified:

| | |
|---|---|
| warning fired | yes, with the real count of discarded items |
| `[E] INCOMPLETE` printed | yes |
| **exit code with truncation** | **1** (before: 0) |
| **control: without truncation** | **0** (did not break the normal path) |

Source restored and checked by md5 after the test; `build_trunc/` deleted.

### 1.2 Write without `flush` on two of the four paths

`runFileBasedSearch` and `runFileBasedSearchMultiConfig` wrote the finding to the `ofstream` and
relied on the destructor to persist it. A `kill -9` (or power loss) between finding and finishing
would lose a key **already found and verified**.

The vanity path already did this correctly, with an explicit comment — *"durability: survive a
kill/crash right after this line"*. The same criterion applied to keyhunt (where a real `kill -9`
was tested and the file survived) and that failed CUDACyclone (which writes to no file at all) was
applied here. The two missing paths were brought in line.

---

## 2. Test-infrastructure and contract findings

One remains open (2.1); the other four were fixed this session.

### 2.0 `ctest` reported "No tests were found!!!" with exit code 0 — FIXED

Discovered while trying to run the full suite. Both ends were missing: `enable_testing()` at the
root and `add_test()` in `tests/parity/CMakeLists.txt`. The 17 tests were compiled, but none were
registered — anyone running `ctest` to validate the project got silence and **apparent success**.

Severity: this is the purest version of the defect this project holds others to — a verification
tool that reports "everything is fine" without having verified anything.

**Fix:** `enable_testing()` at the root, `add_test()` for all 17, `TIMEOUT 600` and
`WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}`.

> Pitfall found on the first attempt, recorded so it does not repeat: without
> `WORKING_DIRECTORY`, 9 of the 17 failed with `Could not open tests/vectors/data/...` — the tests
> open data by a **relative** path, and ctest runs them from inside the build directory. The same 9
> passed when run by hand from the root. A careless registration would have turned 17 good tests
> into 9 phantom failures.

**Final state: 16 of 17 pass.** The one failure, `test_group_ops`, is pre-existing and **not a
regression**: the `GROUP_SIZE=4096` case uses local arrays of ~131 KB per thread
(`Int256 dx[half+1]` + `scratch[half+1]`) and overflows the 8 GB RTX 5060's memory. Confirmed with
the **GPU 100% free**, which rules out contention with production as the cause. The 128/256/1024
cases pass with a perfect match, and **128 is the only instantiation used in production**. Tagged
`needs_lots_of_vram` to allow `ctest -LE needs_lots_of_vram` on a smaller machine.

### 2.1 None of the four search functions is invoked by any test — OPEN

Verified by an exhaustive search of the entire repository: **no test calls `runVanitySearch`,
`runVanitySearchMultiConfig`, `runFileBasedSearch` or `runFileBasedSearchMultiConfig`**. Every
occurrence outside `cli/` is a comment (in `gpu/kernels/`, `scripts/` and one test's header).

The closest test, `test_file_search_multiconfig.cu`, describes itself as a *"correctness gate for
the runFileBasedSearchMultiConfig code path"* and **replicates** the pipeline
(`...ScatterMultiDiverse -> masterkeyLaunchScalarMult64 -> ...FastHash160`) rather than calling the
function. This validates the kernels and the reconstruction formula — not the function that
orchestrates them.

The consequence is more serious for `runVanitySearch`, which is the path for **100% of
production** and the only one without even a replica-style test of that kind.

An important qualification, so as not to overstate the finding: **the kernels it calls are heavily
tested** (13 parity tests, ~3,700 lines, against independent oracles — GMP, a pinned libsecp256k1,
OpenSSL). And the function **is** validated end to end by the agreement protocol
(`ARCHITECTURE_AGREEMENT_REFERENCE.md`), which runs the actual binary and compares the sha256 of
the sorted result — six (architecture, toolkit) combinations agree byte for byte.

What does **not** exist is automated regression of the orchestration layer: the hop loop, the
final-hop clamp, key reconstruction from the offset, GLV reconstruction, writing and exit codes. A
refactor of this layer would not be caught by `ctest` — it would depend on someone remembering to
run the agreement protocol by hand.

**The §2.0 fix does not resolve this.** Registering the 17 tests with `ctest` made the existing
suite actually run, but it remains a suite of *kernels and primitives*: none of the 17 calls a
search function. These are different problems — one was "the suite does not run", this one is "the
suite does not cover this layer".

Concrete evidence that this gap hides a real defect: the two fixes in §1 (truncation with no effect
on the exit code, write without flush) **live exactly in this layer** and survived all 13 parity
tests and six rounds of the agreement protocol — because neither one exercises the buffer-overflow
path or kills the process mid-write.

This is item 5 of the rubric ("fix the test's blind spot, not just the code") applied to this
project's own code. It is the same class of gap that `AUDIT_VANITY_MODE.txt` §7 already recorded
for `rmd160`/`address`/`xpoint`, and that `BUG_MULTITARGET_STOPS_AT_FIRST_HOP.md` later confirmed
was exactly where a real defect was hiding.

### 2.2 ~~Kernel error attributed to the wrong launch~~ — FIXED this session

The center-construction kernels (`masterkeyLaunchBuildCenterPrivkeys`,
`masterkeyLaunchScalarMult64`, `masterkeyLaunchAddBaseToOffsets*`) were launched without a
`cudaGetLastError()` right after. CUDA errors are sticky, so they were not lost — but they surfaced
at the next check, **attributed to the search kernel**: a real error, in the wrong place.

**Fix:** six center-construction points gained a check with its own label (`"center build (fast
soa)"`, `"offset table build"`, `"center build (scatter)"`, `"center build (multi-config)"` etc.).

**Verification caveat:** checked by code review and a clean compile, **not** by forcing a real
kernel failure — that would require deliberately corrupting a launch in a disposable build,
disproportionate to the size of the gain. Recorded here so this is not counted as "tested" when it
was not.

### 2.3 ~~`--fix-bits` outside the range~~ — FIXED this session

`BUG_FIXBITS_RANGE.md` described it: the fixed-bit mask is applied via OR **after** the addition,
and can push the value above the range's ceiling. It was left open by explicit decision (the option
unused), reopened at the user's request this session.

**Fix:** candidate rejection. The value is accepted only if, **after** applying the mask, it is
still within `[start, end)`; otherwise it is redrawn. This preserves uniformity over the valid set
(introduces no bias) and never returns a value outside the contract. If the range+mask combination
is degenerate, it fails loudly with an explanatory message instead of silently returning an invalid
value.

Production pays nothing: without `--fix-bits` the mask is zero and the check passes on the first
attempt.

**Tested with the document's exact counter-example** (`range [0,24)`, bit 3 fixed — which used to
produce 31): 6 distinct bases drawn, **0 outside the range, 0 without the fixed bit**.

### 2.4 Multi-target — door closed instead of the loop restructured

`BUG_MULTITARGET_STOPS_AT_FIRST_HOP.md`: with N targets, the search stops at the first hop with any
finding and prints "SUCCESS" — real reproducer: 30 targets, 25 found, the 5 missing exactly the
ones that fell after the first hop's boundary.

The user confirmed this session that **the project works with a single address**. Restructuring the
loop for a capability nobody uses is not justified; leaving it accepting and silently returning a
subset is even less so. **Fix adopted: refuse more than one target**, with a message explaining why
and pointing to the document. The silent incomplete result is no longer reachable.

Tested: 2 targets -> `exit=1` with the message; 1 target -> `exit=0`, search runs normally.

---

## 3. What was checked and passed

Recorded because "found no defect here" is a result, not an absence of work — and because each item
below is a **real** defect found in one of the third-party tools audited.

| Check | Result | Contrast |
|---|---|---|
| **Reported rate is honest** | `totalScanned` sums real candidates per hop | keyhunt inflates 2x (`total.Mult(2)`, `keyhunt.cpp:2185`) |
| **A found key is never discarded** | verified on the host before writing, and writes what it verified | KeyHunt-Cuda discards the correct key on Base58 re-verification |
| **Writes to file with durability** | `flush()` per finding on all four paths (after §1.2) | CUDACyclone writes to no file at all |
| **Respects the declared range** | guaranteed by `--no-glv`; used in every production search | keyhunt CPU reports 51.3% outside the range, with no flag to disable it |
| **Bloom filter has no false negative** | host and device use an identical formula (`(a + b*i) % bits`, same seed) — a bit set by the host is always found by the device | — |
| **Base draw is unbiased** | classic rejection sampling in `randomInRange`; with `--fix-bits` off, `or256(x,0)` is the identity | KeyHunt-Cuda draws on `[0, end)`, ignoring `rangeStart` |
| **Vanity ranges have no false negative** | see §4 — tested empirically | — |
| **Every `cuda*` call is checked** | yes (`checkCuda` on 100% of them) | — |
| **Correct signal handler** | `volatile std::sig_atomic_t`, the handler only assigns | — |
| **Incomplete coverage reaches the exit code** | already true for degenerate groups; now also for truncation | — |

---

## 3-B. EMPIRICAL audit: every third-party defect, reproduced on the GPU

The table in §3 came from reading the code. This section **runs**, on the RTX 5060 with production
paused, exactly the test that failed each third-party tool — the question is not "does the code
look right?", it is "does the defect appear when I try to provoke it?".

### Test A — "finds the key and throws it away" (KeyHunt-Cuda's defect)

Private key `0x400000000000001234` planted within a 4,096-key range; hash160 obtained by
independent derivation in Python.

```
privkey=0x400000000000001234 matched target #0 [compressed] independently VERIFIED
[+] 1 match(es) appended to KEYFOUNDKEYFOUNDplant.txt
content: 14oWNHeVVEH1rNDz2ZRGPMEN3TQfKAZUy3: 400000000000001234
```

**Found, verified and WRITTEN.** KeyHunt-Cuda discarded the correct key on Base58 re-verification.

### Test B — keys outside the declared range (keyhunt CPU's defect: 51.3%)

Same sequential range (17.2 billion keys), prefix `1PWo3`, two runs:

| Configuration | Findings | Outside the range | % |
|---|---|---|---|
| **With `--no-glv`** (production) | 3,795 | **0** | **0.0%** |
| Without `--no-glv` | 11,432 | 7,637 | 66.8% |

The test that failed keyhunt at 51.3% gives **zero** on the production configuration. And the
66.8% without the flag confirms, with a measured number, that `--no-glv` is **a structural load,
not a recommendation**: it is 2 of the 3 GLV variants (lambda and lambda^2) that leave the
interval, exactly 2/3 as theory predicts.

**Neither row of this table is comparable to the other, nor to keyhunt** — and the first draft of
this section got that wrong, suggesting "masterkey does worse than keyhunt". keyhunt's 51.3% is its
**default** behaviour, with no option to disable it; the 66.8% here required **deliberately
removing** a flag present in every documented command of the project.

**Verification on real data, not a synthetic test:** the production `1PWo3JeB` archive was checked
key by key on 2026-08-16 — **659 keys, 0 outside the range**. No key outside the interval has ever
been delivered at any point in the project's life.

The legitimate finding, therefore, is not about the output: it is that **the default is not safe**.
The range guarantee depends on someone remembering the flag, not on the program. See §4 of the
comparative audit.

### Test C — durability under `kill -9` (CUDACyclone's defect)

A short prefix to accumulate findings fast, `kill -9` with no chance of a clean shutdown:

```
lines in the file BEFORE the kill : 68,212
lines in the file AFTER the kill  : 68,248
```

Nothing stuck in a buffer. A sample of 200 keys re-derived by an independent secp256k1
(`ecdsa`/Python): **200 correct, 0 wrong, 0 outside the range**. CUDACyclone writes to no file at
all — the finding exists only on screen.

### Test D — is the reported rate honest? (keyhunt inflates 2x)

Exhaustive sequential scan of a known size:

```
declared range   : 0x400000000 = 17,179,869,184 keys
program reported : 17179869184 keys in 24.6s (699.26 Mkeys/s)
time measured EXTERNALLY: 24.97 s
```

Count **exactly equal** to the range's size — keyhunt would have reported 34,359,738,368 here
(`total.Mult(2)`, `keyhunt.cpp:2185`). Internal and external time consistent.

### Test E — does random mode ignore `rangeStart`? (KeyHunt-Cuda's defect #3)

A narrow and **high** range (`[0x7ffffff000000000, 0x7fffffffffffffff)`) — if `rangeStart` were
ignored, the bases would fall near zero:

```
distinct bases: 12    OUTSIDE the range: 0
smallest: 0x7ffffff024464a47    largest: 0x7fffffff6802b068
```

All inside. KeyHunt-Cuda draws on `[0, rangeEnd)`, ignoring the start.

### Empirical summary

| Third-party defect | Present in masterkey? |
|---|---|
| Finds the key and discards it (KeyHunt-Cuda) | **No** |
| Reports a key outside the range (keyhunt CPU) | **No**, with `--no-glv`; without the flag, 66.8% (documented and measured) |
| Does not write / loses it in the buffer (CUDACyclone) | **No** — 68,248 survived `kill -9` |
| Rate inflated 2x (keyhunt CPU) | **No** — exact count |
| Random mode ignores `rangeStart` (KeyHunt-Cuda) | **No** |
| Multi-target stops at the 1st hop (BitCrack) | Existed; **door closed** this session (§2.4) |

---

## 4. New test: do the vanity ranges lose valid addresses?

This was the question with the highest stakes for production. If `computeVanityBounds` produced a
**false negative** — a hash160 whose address begins with the prefix but that falls outside every
`[lo,hi]` range — production would be silently discarding valid keys, and nothing in the system
would flag it.

**Mathematical proof:** the Base58Check payload is `V = 0x00 || hash160 || checksum`, i.e.
`V = hash160 * 2^32 + checksum`. The ranges are `lo = floor(V_lo / 2^32)` and
`hi = floor(V_hi / 2^32)`. Since `floor(.)` is monotonic, `V in [V_lo, V_hi] => hash160 in [lo,
hi]`. **A false negative is impossible.** (The converse does not hold — there are false positives
at the boundary, but those are eliminated by the host check, `address.rfind(target, 0) == 0`.)

**Empirical confirmation**, with an independent implementation in Python (`scratchpad/`, algorithm
rewritten from scratch, using no code from the project): 400,000 random hash160 values, 281 whose
address begins with `1PW`, **281 within the ranges, 0 false negatives**.

---

## 5. Limits — what this audit did NOT prove

Stated explicitly, item 10 of the rubric.

- **The CUDA kernels were not audited line by line.** Confidence in them comes from the 13 parity
  tests against independent oracles and from the agreement protocol, not from my own reading of
  device code this session.
- **Behaviour under a real GPU failure was not tested** (ECC, "unspecified launch failure", the
  device disappearing — which has genuinely happened on a 4060 in this project). The error path
  exists and is checked, but it was not exercised.
- **Write concurrency between two processes with the same `--out-tag` was not verified.** The
  project's practice is to use distinct tags per GPU; append-mode writes of short lines are atomic
  on Linux, but this was not tested here.
- **The claim in §2.1 is about automated testing**, not about "untested": the function has
  end-to-end validation documented and reproduced across six architecture/toolkit combinations.
- **The kernel-error fix (§2.2) was not exercised.** Checked by review and a clean compile; forcing
  a real kernel failure would require deliberately corrupting a launch.
- **The empirical tests in §3-B ran on a single GPU** (RTX 5060, Blackwell sm_120, CUDA 13.0). The
  range-containment and durability numbers do not depend on architecture, but were not repeated on
  another card this session.
- **`test_group_ops` with `GROUP_SIZE=4096` still does not pass on this machine** (§2.0). That it
  would pass on a GPU with more VRAM is an inference from the measured cause, not an observation —
  no larger GPU was tested after the finding.
- **The four search paths were not exercised equally.** The focus was vanity (production);
  `rmd160`/`address`/`xpoint` were read, but only the truncation and the flush were tested on them.
