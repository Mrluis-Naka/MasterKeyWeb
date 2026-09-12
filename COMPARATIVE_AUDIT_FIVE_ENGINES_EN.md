# Five Search Engines — Comparative Audit

**2026-08-16.** Four public Bitcoin key-search tools and this project's engine, put to the same
question: **does the tool lose findings, or claim coverage it did not achieve?**

| | |
|---|---|
| Tools audited | 5 |
| Defects demonstrated | 24 |
| Period | 2026-08-05 to 2026-08-16 |
| Method | minimal reproducer + independent-implementation verification |

Full audits, one per tool, in `masterkey-gpu/docs/`:
`AUDITORIA_KEYHUNT_CPU_2026-08-05.md` · `AUDITORIA_KEYHUNT_CUDA_2026-08-05.md` ·
`AUDITORIA_BITCRACK_CUDA_2026-08-15_Port.md` · `AUDITORIA_CUDACYCLONE_2026-08-15.md` ·
`AUDITORIA_MASTERKEY_2026-08-16.md`

Browsable version of this report: <https://claude.ai/code/artifact/7b3588d0-beae-45c2-adf9-311f3e96f674>

---

## 1. The scoreboard

Each row is a mechanism that decides whether a finding survives from kernel to disk. Wherever a
number appears, it was **measured**, not estimated.

Legend: ✅ correct · ⚠️ known limitation · ❌ loses a finding or lies about coverage

| Mechanism | keyhunt CPU | KeyHunt-Cuda | BitCrack | CUDACyclone | **MasterKey** |
|---|---|---|---|---|---|
| Re-verifies the finding before writing | ✅ yes | ❌ discards 100% | ⚠️ `verifyKey` dead | ⚠️ absent | ✅ always |
| Writes to file with durability | ✅ immediate `fclose` | ✅ yes | ✅ yes | ❌ **never writes** | ✅ `flush` per finding |
| Respects the declared range | ❌ **51.3% outside** | ❌ up to 25,157x | ⚠️ 1 batch of overshoot | ✅ yes | ✅ 0 of 659 |
| Random mode respects the range start | ✅ yes | ❌ draws from `[0,end)` | — | ✅ yes | ✅ yes |
| Reported rate is honest | ❌ **inflates 2x** | ✅ yes | ✅ yes | ✅ yes | ✅ exact count |
| Full results buffer | — | ❌ truncates silently | ❌ no check | ✅ ok | ✅ warns + `exit≠0` |
| Batched inversion with a zero factor | — | — | — | ❌ **loses the batch** | ✅ aborts + `exit≠0` |
| Multi-target search | ✅ works | ✅ works | ❌ **hangs above 16** | — | ⚠️ refuses |
| Signal handling (Ctrl+C) | ✅ ok | not tested | ❌ none | ✅ clean | ✅ clean |
| Project's own self-test | ⚠️ nonexistent | ❌ fails 3/8 | ❌ does not build | ✅ runs | ✅ 16/17 |
| Builds on the current toolchain | ✅ clean | ❌ does not build | ❌ does not build | ✅ clean | ✅ clean |

---

## 2. The defect classes

Grouped by which mechanism fails, not by tool — because the same failure reappears in projects
that **share not one line of code**.

### The key is found and then discarded — hits 1 of 5

The kernel gets it right, the correct key reaches the host, and a defective re-verification throws
it away. In KeyHunt-Cuda the default build activates this exact path: the Base58 encoding comes
out invalid and the finding is discarded — 100% of findings, in the only mode the project offers.

- ❌ **KeyHunt-Cuda** — default build
- ⚠️ BitCrack — does not re-verify (`verifyKey` dead)
- ⚠️ CUDACyclone — does not re-verify

### The finding never reaches disk — hits 1 of 5

CUDACyclone prints the finding to the screen and **writes it to no file at all**. A multi-day
search that hits while nobody is watching, in a terminal that scrolled away or closed, loses the
result. BitCrack does write, but handles no signal: stopping the search costs up to 60 s and,
without `--continue`, all progress.

- ❌ **CUDACyclone** — screen only
- ❌ **BitCrack** — no signal handling

### The output does not respect the requested interval — hits 3 of 5

You declare a range and receive keys outside it. They are mathematically correct — they generate
the addresses the tool claims — but do not belong to the requested interval, and in keyhunt CPU
they are 256-bit keys where 71 were requested. Measured over 74 h and 3.57 trillion keys: **128 of
263 findings outside**. There is no option to turn this off.

- ❌ **keyhunt CPU** — 51.3%, no opt-out
- ❌ **KeyHunt-Cuda** — up to 25,157x
- ⚠️ BitCrack — up to 1 batch

### One degenerate case wipes the entire batch — hits 2 of 5

Batched modular inversion multiplies every `dx` into a single product. If any one of them is zero,
the product zeroes out, the inversion silently returns zero, and every candidate derived from it
comes out corrupted — only the batch's center survives, because it is compared before the
inversion. **Same defect in both projects; what differs is the reaction.**

- ❌ **CUDACyclone** — no check, reports `KEY NOT FOUND (exhaustive)`
- ✅ **MasterKey** — detects it in O(1), aborts the group, global counter, `exit≠0` (fixed 2026-08-06)

### The quality gate does not work — hits 4 of 5

The most widespread class, and the one that explains all the others.

- ❌ **BitCrack** — self-test does not build as distributed
- ❌ **KeyHunt-Cuda** — self-test already fails 3 of 8 out of the box
- ⚠️ **CUDACyclone** — self-test runs, but never exercises `--slices`, where the defect lives
- ⚠️ **MasterKey** — was building 17 tests while registering none; `ctest` reported
  *"No tests were found!!!"* and exited 0 (fixed 2026-08-16)

---

## 3. Per-tool record

### keyhunt (CPU) — commit `2134a20`, v0.2.230519, audited 2026-08-05

Finds and writes safely, but lies about what it swept and about where the keys are.

- **51.3% of output outside the range**, with no option to disable it
- **Rate inflated 2x** in compressed mode (`keyhunt.cpp:2185`): counts two hash checks as two keys
- Durable write confirmed — survived a `kill -9` in testing
- Positive control passed: finds and writes known keys

### KeyHunt-Cuda v1.07 — audited 2026-08-05

The only one in the series whose main defect hits 100% of findings in the only mode it offers.

- **Default build discards the found key**
- No end-of-range check — up to 25,157x beyond
- Random mode ignores the range start
- Truncates the buffer at 65,536 per launch, without warning
- Distributed self-test already failing 3 of 8
- Does not build with the current toolchain

### BitCrack — audited 2026-08-15 (12 defects)

Fails at the exact use case it claims to serve: the 32-address puzzle.

- **Hangs above 16 addresses** on the CUDA build tested (see version caveat in the full report:
  in 2020, with an older CUDA, 160 addresses ran)
- OpenCL backend does not build on any device tested
- Checkpoint corrupts `stride` != 1 into 0 → infinite loop with no progress
- No signal handling in multi-day searches
- Results buffer with no bounds check (CUDA and OpenCL)
- Default build does not build (`COMPUTE_CAP=30` obsolete)

### CUDACyclone — audited 2026-08-15

The best-built of the four — and the fastest. With one real silent loss.

- **Batched inversion poisoned by zero**: entire batch lost, reported as an exhaustive search
- **Writes to no file** — the finding exists only on screen
- Clean build, rigorous CLI validation, correct SIGINT handling
- Clean under `compute-sanitizer` memcheck and racecheck
- Faster than MasterKey on equivalent hardware (numbers published by the authors)

### MasterKey (this project) — audited 2026-08-16

The five defects found in the others were deliberately provoked on the GPU and **none appeared**.
The six findings below are its own.

- Truncation exited with `exit=0` on 4 of 4 search paths — **fixed**
- Write without `flush` on 2 of 4 paths — **fixed**
- `ctest` was running none of the 17 tests — **fixed**
- Kernel error misattributed to the wrong launch — **fixed**
- `--fix-bits` could generate a key outside the range — **fixed**
- **Still open:** none of the 4 search functions has an automated test

---

## 4. What backs MasterKey's result

Every defect found in the other tools was reproduced as a test on the RTX 5060, with production
search paused. Numbers measured, not inferred.

| Check | Result |
|---|---|
| Planted known key — found, verified, and written | 1 / 1 |
| Findings within the declared range (production configuration) | 3,795 / 3,795 |
| Keys surviving a `kill -9` mid-search | 68,248 |
| Sample re-derived by an independent secp256k1 (Python) | 200 / 200 |
| Declared vs. reported count, exhaustive sweep | 17,179,869,184 = 17,179,869,184 |
| Real production holdings outside the range | 0 / 659 |
| Regression after the fixes — sha256 vs. a 6-architecture reference | identical |

---

## 5. Where this report is fragile

### Auditor and audited are the same, in one of the five cases

The four third-party tools were audited on someone else's code, without access to the authors'
intent, in **one session each**. MasterKey was audited by the person who wrote it, with weeks of
context and the ability to fix what was found — five of the six findings were fixed before this
report existed. **This is not a comparison between equals**, and no conclusion here should be read
as if it were.

The available counterweight was applying to its own code the same tests that failed the others,
with a minimal reproducer and independent-implementation verification — and recording its own
findings with the same severity, including the `ctest` that ran nothing at all.

### Other caveats

- **MasterKey's default is not safe.** The range guarantee depends on passing `--no-glv`. Without
  the flag, two-thirds of the output falls outside the interval. The discipline has held for
  months — the real holdings are 659 keys and none outside — but the operator guarantees it, not
  the program.
- **Multi-target was solved by closing the door.** MasterKey started refusing more than one target
  instead of fixing the loop. The right call for a project searching for one address, but less
  capability than keyhunt and KeyHunt-Cuda offer.
- **This is not a performance comparison.** CUDACyclone is faster than MasterKey on equivalent
  hardware. Measured per-GPU throughput numbers are in `HANDOFF_v20.md` §2.
- **Frozen versions.** Each tool was audited at a specific version and toolchain. Build defects in
  particular age fast.
- **Absence of a defect is not proof of correctness.** The five defects found in the others were
  provoked and did not appear in MasterKey — which says nothing about defects nobody has looked
  for yet.
- **The empirical tests ran on a single GPU** (RTX 5060, Blackwell sm_120, CUDA 13.0).

---

## 6. The pattern that repeats

The five tools share no code, and yet three of them fail the same way: there is a path where the
program **stops working and does not say so**. It is not an arithmetic failure — in every one, the
cryptography was correct. It is a failure at the boundary between the kernel and the disk: in what
happens when the rare case occurs.

The most common class is not technical, it is procedural: **four of the five had a broken quality
gate** — a self-test that does not build, that already fails out of the box, that never exercises
the option where the defect lives, or that was never registered with `ctest`. Every serious defect
in this series lives exactly in the blind spot of the project's own testing.

The line that separates a trustworthy tool from a dangerous one, in this sample, is not who finds
more keys. It is what the tool does when it **cannot** deliver what it promised: report "exhaustive
search complete" with the same confidence as always, or exit with an error code saying the
declared coverage does not match what was actually swept.
