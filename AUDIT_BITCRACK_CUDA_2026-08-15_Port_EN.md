# Audit of BitCrack (brichard19/BitCrack) — twelve defects, with a declared proof level

**Date**: 2026-08-15
**Object**: BitCrack, code as distributed at `github.com/brichard19/BitCrack`, branch `master`,
commit `6bf8059ef075eb1622298395866b0bd02375e1` (the project's last commit, 2020-01-27 — no
activity since).
**Motivation**: a request for a full audit of the CUDA build, following the same methodology as
the KeyHunt-Cuda audit (`AUDIT_KEYHUNT_CUDA_2026-08-05_EN.md`), including a search for a defect of
the same severity class.

**Why the bar of proof is higher here**: BitCrack is not an obscure project. It has **~1,000 stars
and 659 forks on GitHub**, a dedicated thread on bitcointalk.org ("BitCrack - A tool for
brute-forcing private keys", Development & Technical Discussion) with community members posting
real usage questions, and is cited as an **established reference for GPU address scanning** on the
lower-difficulty puzzles of the Bitcoin challenge, alongside keyhunt and Kangaroo. For that reason
every defect below comes with an exact command, captured output and, where one exists, the
file+line of the cause — nothing here is inferred purely from reading the code without attempting
to reproduce it, except where the **VERIFIED IN CODE** level says so explicitly.

---

## 0. Method and limits

**No source file was modified in the audited repository.** The only interventions were compiler
command-line flags (`COMPUTE_CAP`, `CXXFLAGS`) and the choice of how many targets to pass on the
CLI — neither alters the audited logic. One attempt to edit `CudaKeySearchDevice/Makefile` to
confirm a hypothesis was corrected midway through the session and reverted with
`git checkout -- .` + `git clean -fdx`; the clone's final state is identical to upstream (clean
`git status`).

**Test environment**: rented instance, NVIDIA RTX 4070 Ti (sm_89, 12GB), driver 595.84, Ubuntu
24.04.4, CUDA 13.2. Instance security checked before any build (`~/.ssh` permissions 700/600, no
extra local accounts, no password set on any account).

**Reference oracle**: `AddrGen/addrgen`, the project's own address-generation tool
(`privkey -> pubkey -> hash160 -> address`), used only to GENERATE (key, address) pairs known in
advance — never to check a result BitCrack had already produced. The guarantee does not come from
"two parts of the same project agreeing", it comes from **construction**: we chose the private key
ourselves, computed the corresponding address with a deterministic tool, and only then asked
BitCrack whether it can find that key within the right interval. If the returned value does not
match what we chose, that is direct proof of a defect, not inference.

**Proof scale used in this document**: same as the KeyHunt-Cuda audit — **DEMONSTRATED**
(reproduced in a real run, output captured) vs. **VERIFIED IN CODE** (read in the source, with
file and line, not isolated in execution).

---

## 0.1 What the community has ALREADY reported — and what this audit does NOT explain

A survey conducted on 2026-08-15 of the project's issue tracker, before publishing anything.
**Nothing here is claimed as an original discovery without first checking.**

### Already publicly known (not novel to this audit)

| Subject | Where | Status |
|---|---|---|
| Build fails due to CUDA architecture (`compute_30` and the like) | [#70](https://github.com/brichard19/BitCrack/issues/70), [#154](https://github.com/brichard19/BitCrack/issues/154), [#286](https://github.com/brichard19/BitCrack/issues/286), [#376](https://github.com/brichard19/BitCrack/issues/376), [#595](https://github.com/brichard19/BitCrack/issues/595) | Recurring since 2018, the standard reply is "edit the Makefile by hand". Never fixed in the project |
| Bloom filter breaks above 15/16 addresses | [PR #419](https://github.com/brichard19/BitCrack/pull/419) (Oct 2024) | A correct fix, with the same diagnosis as this audit. **Never merged** |
| `--stride` (old bugs, different from Defect 8) | [#94](https://github.com/brichard19/BitCrack/issues/94), [#107](https://github.com/brichard19/BitCrack/issues/107), [#115](https://github.com/brichard19/BitCrack/issues/115) | Fixed in v0.27 (~2019) |

### Apparently new in this audit

No public issue or PR was found addressing these points: Defect 2 (`-dlink` with no architecture),
Defect 5 (`verifyKey` as dead code), Defect 8 (`stride` written in hex and read as decimal — the
old stride issues are a different bug), Defect 11 (crash from extreme `-b`/`-t`/`-p`) and Defect 12
(absence of signal handling). "Not found" is not the same as "does not exist" — the search covered
GitHub's tracker and a web search, not the full bitcointalk history.

### The most serious cluster — UNRESOLVED reports of keys not being found

There is a large, old set of user reports saying BitCrack **does not find keys that are inside the
declared interval**. None was diagnosed, none was answered by the maintainer:

| Issue | Report | Backend |
|---|---|---|
| [#81](https://github.com/brichard19/BitCrack/issues/81) | "clBitCrack simply skips the correct private key and continues the search" — found puzzles #1 and #4, skipped #9 | OpenCL |
| [#128](https://github.com/brichard19/BitCrack/issues/128) | Added their own address to the list, pointed the start at the right HEX, it was not reported as found | not stated |
| [#217](https://github.com/brichard19/BitCrack/issues/217) (2020) | Same interval, same 160 addresses: **CUDA finds 28, OpenCL finds 18**, both saying "Reached end of keyspace" | both |
| [#337](https://github.com/brichard19/BitCrack/issues/337) | An interval ending in `...790000` finds 2 keys; ending in `...780000` finds none | not stated |
| [#378](https://github.com/brichard19/BitCrack/issues/378) | Key `25b00000cccccc111` inside the interval `25b0000000c8cc110:25b00000cccccc112` was not found | OpenCL |
| [#628](https://github.com/brichard19/BitCrack/issues/628) (Oct 2025) | "Fails to find private keys in medium-sized ranges, even when the keys definitely exist there" — the same keys turn up immediately if the range is split into smaller chunks. Puzzle #40 | OpenCL (AMD) — **tested on CUDA in this audit, not reproduced: see below** |

**This audit did not reproduce any of these cases and does not explain them.** Every correctness
test here (46+ known keys across the full 256-bit space, byte-for-byte agreement with a second
independent tool) was done on the **CUDA backend** and produced not a single wrong or missing
result. Five of the six reports above are on **OpenCL**, which in this audit does not even compile
(Defect 10) and so could not be tested end to end.

**Exception: #628 was tested directly, with its exact command, on CUDA.** Same `--keyspace`, same
`--compression BOTH`, same target address (puzzle #40, `0xE9AE4933D6` ->
`1EeAxcprB2PpCnr34VfZdFrkUWuxyiNEFv`), **without** `--share` — the minimal variation is the backend
(CUDA here, OpenCL/AMD gfx90c in the original report). Result:

```
[Info] Found key for address '1EeAxcprB2PpCnr34VfZdFrkUWuxyiNEFv'. Written to '/root/p40full.txt'
[Info] No targets remaining
```

Found in ~19 minutes (453,697,601,536 keys scanned, ~396 Mk/s, throughput stable start to finish,
no stagnation and no odd counting) — the position matches what is expected from the key's offset
within the interval. **No anomaly on CUDA.** This does not prove #628 is exclusively an OpenCL bug
— one repetition does not, by definition, reproduce an intermittent bug — but it is real, direct
evidence against the hypothesis that it was a range-math problem shared between the two backends.
It reinforces the reading that the not-found-key report cluster is concentrated on OpenCL.

**The honest conclusion is uncomfortable and needs to be stated as such**: the fact that this audit
did not find key loss **does not clear** BitCrack of the reports above. What can be stated is: on
the CUDA backend, on the version and hardware tested, with the cases tested, there was no wrong
result. None of that covers what those users reported — and #628's pattern ("does not find in the
large interval, finds in the small chunk") is **exactly** the behavioural signature that motivated
the KeyHunt-Cuda audit, where it turned out to reveal a real defect. This remains an open, priority
question for anyone with AMD/OpenCL hardware available.

---

## Defect 1 — Default build does not compile with the current toolchain

**Level: DEMONSTRATED.**

The project's `Makefile` declares `COMPUTE_CAP=30` (Kepler, 2012) as the default. CUDA 13.2 no
longer accepts that architecture:

```
nvcc fatal   : Unsupported gpu architecture 'compute_30'
```

Five `.cu` files fail for this reason; the entire build aborts before producing any CUDA binary.
Worked around with `make BUILD_CUDA=1 COMPUTE_CAP=89` (a command-line parameter, not a file edit).

---

## Defect 2 — Device-link step with no explicit architecture

**Level: DEMONSTRATED**, but **correctness was not compromised in the test performed.**

`CudaKeySearchDevice/Makefile`:

```make
${NVCC} -dlink -o cuda_libs.o *.cu.o -lcudadevrt -lcudart
```

No `-gencode`/`-arch`. The device-code linking step (`-rdc=true` + `-dlink`) falls back to the
toolkit's internal default — `sm_75` on this CUDA 13.2 — even though the individual `.cu.o` files
were compiled with `COMPUTE_CAP=89`. Confirmed with `cuobjdump --list-elf`:

```
ELF file    1: cuBitCrack.1.sm_75.cubin
```

Adding `-gencode=arch=compute_89,code="sm_89"` to the dlink step (only for testing, reverted
afterward) makes the embedded cubin correctly become `sm_89`, without changing the search result.
**In other words: the packaging defect is real and reproducible, but in this audit's tests it did
not go on to produce an incorrect result** — the binary with the mislabelled cubin still found the
correct key in the single-key reproducer used as a baseline in this audit
(`privkey = 0x3039`, address `12vieiAHxBe4qCUrwvfb2kRkDuc8kQ2VZ2`), independently before and after
the fix. Not tested whether this fails on newer/more distant architectures than sm_75 (e.g.
Blackwell) or on much larger batches.

---

## Defect 3 — Search with more than 16 addresses fails (on the CUDA 13.2 tested)

**Level: DEMONSTRATED in this configuration.** Breaks the project's own stated primary use case.
**Read the version caveat in the "Version scope" section below before citing this defect** — the
behaviour depends on the CUDA version, and there is a public 2020 report where 160 addresses ran
without this error.

BitCrack presents itself as a tool for the **Bitcoin puzzle transaction — 32 addresses**. Loading
more than 16 addresses at once (`-i file.txt`), in the tested environment (CUDA 13.2), **always
fails**:

```
[Info] Loading addresses from '/root/targets17.txt'
[Info] 17 addresses loaded (0.0MB)
[Info] Allocating bloom filter (0.0MB)
[Info] Error: invalid argument
```

Real exit code (not masked by a pipe): **1**. No results file is written.

### Minimal reproducer

30 addresses generated with `addrgen` from private keys we chose, offsets
`0x100000000 + i*47301 mod 1310720` for `i=0..29`:

| Targets loaded | Result |
|---|---|
| 16 (`targets16.txt`) | search runs normally, 16/16 found |
| 17 (`targets17.txt`) | hangs immediately, `exit=1`, zero results |

### Cause — `CudaKeySearchDevice/CudaHashLookup.cu`

```c
#define MAX_TARGETS_CONSTANT_MEM 16                      // line 16

if(targets.size() <= MAX_TARGETS_CONSTANT_MEM) {         // line 225
    return setTargetConstantMemory(targets);
} else {
    return setTargetBloomFilter(targets);                 // path for >16 targets
}
```

Inside `setTargetBloomFilter`, when the computed Bloom filter ends up at 32 bits or fewer (the
normal case for any address list up to ~27 million):

```c
__constant__ unsigned int _BLOOM_FILTER_MASK[1];                          // 4 bytes, declared at the top of the file

err = cudaMemcpyToSymbol(_BLOOM_FILTER_MASK, &bloomFilterMask,
                          sizeof(unsigned int *));                        // line 191 -- copies 8 bytes
```

`bloomFilterMask` is `unsigned long long` (8 bytes). The destination `_BLOOM_FILTER_MASK` is
`unsigned int[1]` — **4 bytes**. `sizeof(unsigned int *)` is the size of a pointer (8 bytes on any
64-bit Linux), not the size of the value that should be copied. It is a copy-paste error from the
line immediately above (which copies an actual pointer, where `sizeof(unsigned int *)` makes
sense). `cudaMemcpyToSymbol` validates bounds against the destination symbol's real size and
refuses the copy — hence `cudaErrorInvalidValue`, reported as "Error: invalid argument".

The sibling path, for filters above 32 bits, **does not have the same bug**:

```c
__constant__ unsigned long long _BLOOM_FILTER_MASK64[1];                  // 8 bytes
err = cudaMemcpyToSymbol(_BLOOM_FILTER_MASK64, &bloomFilterMask,
                          sizeof(unsigned long long *));                   // 8 bytes -- matches by coincidence
```

Here `sizeof(unsigned long long *)` also equals 8 bytes on 64-bit Linux — the same conceptual error
(copying `sizeof(pointer)` instead of `sizeof(the data type)`), but by a coincidence of sizes the
result matches and there is no crash. **The 32-bit bug only spares the 64-bit path because, on this
platform, a pointer and an `unsigned long long` are the same size — not because the 64-bit code is
correct by design.**

### Mechanism isolated outside BitCrack

To separate "BitCrack fails" from "the cause is exactly this wrong-sized copy", we wrote a minimal
CUDA program **from scratch** (not part of the audited repository), reproducing only the three
lines in question:

```
CUDA runtime 13020, driver 13020
sizeof(unsigned int)=4  sizeof(unsigned int*)=8  sizeof(unsigned long long)=8  sizeof(unsigned long long*)=8

A) 32-bit path, sizeof(unsigned int*)  = 8 bytes into 4-byte symbol : invalid argument
B) 32-bit path, sizeof(unsigned int)   = 4 bytes into 4-byte symbol : cudaSuccess
C) 64-bit path, sizeof(unsigned ll*)   = 8 bytes into 8-byte symbol : cudaSuccess
```

(A) is the line exactly as it stands in BitCrack and produces **exactly** the `invalid argument`
the tool reports; (B) is the same line as fixed by PR #419; (C) confirms the 64-bit branch escapes
only because the sizes coincide. The root cause is isolated and does not depend on any other part
of BitCrack.

### Version scope — an important caveat

The claim "fails" holds for what was measured: **CUDA 13.2**. It **cannot** be generalised to
every CUDA version, and there is public evidence against that generalisation: issue
[#217](https://github.com/brichard19/BitCrack/issues/217) (February 2020) reports a user running
**cuBitCrack with 160 addresses** — far above 16 — with no such error, completing the scan. So on
some CUDA of that era, the same malformed copy was **not** rejected.

**Update — partially tested with CUDA 12.5.** We installed CUDA 12.5's `nvcc` (~mid-2024)
alongside 13.2, without touching the active toolkit, and recompiled the isolation program with it:

```
CUDA runtime 12050, driver 13020
A) 32-bit path, sizeof(unsigned int*)  = 8 bytes into 4-byte symbol : invalid argument
```

**Rejected the same way.** The bounds check is not exclusive to CUDA 13.x — it already held at
least since 12.5. This pushes the "old CUDA let it through" window further back in time, but
**does not close the question**: this instance's package repository only has CUDA 12.5 onward,
nothing from 2020 (when issue #217 was posted, the version in use was likely CUDA 10.x/11.0). Also,
this test varied only the **toolkit/compiler** — the machine's *driver* remains the same (595.84,
the most recent one compatible with this Ada GPU), and `cudaMemcpyToSymbol`'s validation may depend
on the driver, not only on which `nvcc` compiled the binary. A complete test would require a 2020
driver **and** toolkit, which this GPU (released later) does not support. This remains a partially
weakened but not yet closed hypothesis.

### Practical consequence

In the tested environment, any address list with more than 16 entries — including the full list of
32 Bitcoin puzzle addresses, the project's own stated reason to exist according to its README —
**does not run**. This is not degradation, it is total and immediate refusal.

### External confirmation, independent of this audit

There is an open pull request on the official repository —
**[PR #419](https://github.com/brichard19/BitCrack/pull/419)**, "Fix bloom filter when adding more
than 15 addresses", submitted in October 2024 by a community user, **with no connection to this
session**. Its diff ([changed file](https://github.com/brichard19/BitCrack/pull/419/files))
changes exactly `CudaHashLookup.cu`, swapping `sizeof(unsigned int *)` for
`sizeof(unsigned int)` on the 32-bit case's line **and** `sizeof(unsigned long long *)` for
`sizeof(unsigned long long)` on the 64-bit one — the same file, the same root cause, the same fix
this audit reached independently (including treating the 64-bit branch as a real bug, not just "a
size coincidence with no effect", the same conclusion reached here). The PR was never merged by the
maintainer, but it confirms the defect is real, reproducible, and had already been found by someone
else, through a different route, before this audit.

---

## Defect 4 — Results buffer with no bounds check (verified, not demonstrated)

**Level: VERIFIED IN CODE.** Not demonstrated in execution — see why, below.

`CudaKeySearchDevice/CudaAtomicList.cu`:

```c
__device__ void atomicListAdd(void *info, unsigned int size)
{
    unsigned int count = atomicAdd(_LIST_SIZE[0], 1);          // line 15 -- no ceiling
    unsigned char *ptr = (unsigned char *)(_LIST_BUF[0]) + count * size;
    memcpy(ptr, info, size);                                    // writes with no check of count < maxItems
}
```

Compared to KeyHunt-Cuda, which at least has `if (pos < maxFound) { write }` before writing (Defect
4 of that audit — silent loss, but no memory overrun), BitCrack **has no check at all**. The buffer
is allocated with a fixed capacity of **16 items**
(`CudaKeySearchDevice.cpp:89`: `_resultList.init(sizeof(CudaDeviceResult), 16)`). If a single
kernel launch produces more than 16 real matches, the kernel writes **past the allocated buffer**,
in pinned memory shared between host and device — this is not data loss, it is an out-of-bounds
write.

**Why it was not demonstrated**: producing more than 16 real matches in a single batch would
require more than 16 targets loaded simultaneously — and that already hangs due to Defect 3 before
any kernel runs, for any list below ~27 million addresses (the ceiling where the Bloom filter
calculation switches to the 64-bit path, which does not have Defect 3's bug). Bloom-filter false
positives are not enough to compensate: the false-positive parameter is fixed at `1.0e-9` per
query, so the expected number of false positives per batch (262,144 keys) stays far below 1 even
for lists of millions of targets.

**Honest conclusion**: the defect exists in the code, unambiguously, and is structurally worse than
KeyHunt-Cuda's (it writes out of bounds rather than just discarding). But, with the CLI as
distributed, Defect 3 blocks the only practical path to reach it. If Defect 3 were fixed in
isolation without also fixing this one, Defect 4 would become reachable by any search with more
than 16 addresses genuinely present in the same 262,144-key batch — a plausible scenario for
searches over large lists (e.g. a list of "rich" addresses), not for the puzzle use case (32
addresses, but spread over a gigantic key space, where 16 collisions in the same 262-thousand-key
batch is practically impossible).

---

## Defect 5 — No re-verification of the finding (the key is never re-checked against the point)

**Level: VERIFIED IN CODE + a targeted test that found NO counter-example** (see the "What was
checked and is correct" section).

`CudaKeySearchDevice.cpp` declares and implements `verifyKey()` (lines 269-299) — it recomputes
`privkey * G` and the hash160, and compares them against the result returned by the GPU. **The
function is never called anywhere else in the project** (confirmed by searching the entire
repository: only the declaration and the definition appear, no call site).

On the real path (`getResultsInternal()`), the reported private key is computed entirely on the
**host**, by offset arithmetic from `(thread, block, idx)`:

```c
secp256k1::uint256 offset = (secp256k1::uint256((uint64_t)_blocks * _threads * _pointsPerThread * _iterations)
                              + secp256k1::uint256(getPrivateKeyOffset(rPtr->thread, rPtr->block, rPtr->idx))) * _stride;
secp256k1::uint256 privateKey = secp256k1::addModN(_startExponent, offset);
```

Nothing re-confirms that this reconstructed `privateKey` actually multiplies to the point
`(rPtr->x, rPtr->y)` the GPU returned. If `getPrivateKeyOffset` had any indexing error, the defect
would be **worse than KeyHunt-Cuda's**: the printed address would match the target (computed from
the correct `x,y` coming from the GPU, not from the reconstructed key), but the announced private
key would be wrong — silently, with no warning, and just looking at the tool's output nobody would
notice.

This is, in this audit, the closest candidate to a defect of the same class as KeyHunt-Cuda's
Defect 1 (finding and delivering something wrong with no warning) — but here it is not about
discarding, it is about reporting a possibly wrong key for a correct address.

---

## Defect 6 — The end of the interval is overrun by up to one full batch

**Level: DEMONSTRATED.**

`KeyFinderLib/KeyFinder.cpp::run()` **does check** the end of the interval at every step (unlike
KeyHunt-Cuda, which never checks):

```c
if(_device->getNextKey().cmp(_endKey) >= 0 || _device->getNextKey().cmp(_startKey) < 0) {
    Logger::log(LogLevel::Info, "Reached end of keyspace");
    _running = false;
}
```

But the check only happens **between** batches — every `doStep()` always processes an entire batch
(262,144 keys, by default `256 threads x 32 blocks x 32 points/thread`) before the check runs.
Demonstrated with a declared interval of 5 keys, target placed 11 positions past the declared end:

```
--keyspace 200000000:200000005
target at key 0x200000010  (16 beyond the start, 11 beyond the declared end)

[Info] Found key for address '1Dq5TsUuS7a72u2K2vreXWpezU3d9mzcJr'. Written to '/root/overshoot.txt'
[Info] Reached end of keyspace
```

The key was found and accepted, outside the declared interval. **Central difference from
KeyHunt-Cuda's Defect 2**: there, the overrun measured up to 25,157x (a loop with no check at all,
running until found or an error). Here the overrun is **bounded by the size of one batch** (up to
262,144 keys by default, configurable via `-b/-t/-p`) — the same class of defect as masterkey's
(rounding to a multiple of the group size), not KeyHunt-Cuda's uncontrolled class. Relevant to
`--share M/N`: adjacent keyspace divisions can process up to one batch of keys in common
(duplicated work, not lost).

---

## Defect 7 — The project's self-test does not compile as distributed

**Level: DEMONSTRATED.**

`CLUnitTests/Makefile`:

```make
CPPSRC:=$(wildcard *.cpp)                                  # line 2 -- evaluated when the Makefile is parsed

all:
	cat ../clMath/secp256k1.cl secp256k1test.cl > cltest.cl
	${BINDIR}/embedcl cltest.cl cltest.cpp _secp256k1_test_cl    # generates cltest.cpp HERE
	${CXX} -o clunittest.bin ${CPPSRC} ...                        # CPPSRC no longer includes cltest.cpp
```

`$(wildcard *.cpp)` is evaluated by `make` **before** any recipe runs — at that point only
`main.cpp` exists in the directory; `cltest.cpp` is only created afterward, inside the `all` recipe
itself, by the `embedcl` utility. The final link does not include `cltest.cpp`, so the symbol it
would define (`_secp256k1_test_cl`, the byte array holding the test kernel) is left undefined:

```
undefined reference to `_secp256k1_test_cl'
collect2: error: ld returned 1 exit status
make: *** [Makefile:113: dir_clunittest] Error 2
```

Confirmed with `make BUILD_OPENCL=1` (a full build, with no file edited): the main product
(`clBitCrack`) compiles normally; only the test target fails. **Nobody ran this self-test from the
Makefile as distributed, at least not with this toolchain.**

Even if it compiled, the self-test (see the contents of `secp256k1test.cl`) covers only 3 fixed
field-arithmetic vectors (addition, multiplication, inverse — with no stated source for the
expected values, no point/curve/hash/scalar-mult test), runs 1 thread, and exists only for the
**OpenCL** path — the CUDA path, which is what is audited here and the most used, **has no
self-test at all**, not even a broken one.

---

## Defect 8 — Checkpoint corrupts `stride`, can hang in an infinite loop with no progress

**Level: DEMONSTRATED.** Found in a second round of tests, covering `--continue`/checkpoint (not
tested in the first round).

`_config.stride` is `secp256k1::uint256` (`KeyFinder/main.cpp:55`). `writeCheckpoint()` writes it
with `.toString()`:

```c
tmp << "stride=" << _config.stride.toString();
```

`secp256k1::uint256::toString(int base)` **ignores the `base` parameter** and always returns plain
hex, 64 characters, with no `0x` prefix (`secp256k1lib/secp256k1.cpp:616-627`, eight
`sprintf(hex, "%.8X", ...)` calls in sequence).

`readCheckpointFile()` reads it back with:

```c
_config.stride = util::parseUInt64(entries["stride"].value);
```

`util::parseUInt64` (`util/util.cpp:93`) only treats the string as hex if it starts with `0x` or
ends with `h` — otherwise it parses it as **decimal** via `sscanf(s.c_str(), "%lld", &val)`. A hex
string with no prefix, like the one `toString()` writes, always falls into the decimal branch.

### Reproducer

A checkpoint built with `stride=10` (a valid value, correctly rejected by the direct CLI via
`--stride 10` if typed manually — the validation exists, it just does not apply to the checkpoint
path). In hexadecimal, 10 = `...000a` — contains a letter, incompatible with the decimal parser.

```
$ ./cuBitCrack --continue chk_stride10.txt <address>
...
[Info] Counting by: 0000000000000000000000000000000000000000000000000000000000000000
```

`stride` became **0**. Confirmed that the direct CLI cleanly rejects `--stride 0`
(`[Error] Error --stride: argument is out of range`) — but this check only exists in the argument
parsing path, not in `readCheckpointFile()`, which assigns the value without validating it.

### Consequence

With `stride=0`, `generateStartingPoints()` (`CudaKeySearchDevice.cpp:95-130`) generates all
262,144 starting points **identically** (`privKey = privKey.add(_stride)` never changes the value),
and `getNextKey()` (`CudaKeySearchDevice.cpp:311-316`) always returns `_startExponent`, because the
advance term is multiplied by `_stride=0`. `KeyFinder::run()` only leaves the loop when
`getNextKey() >= _endKey` — a condition that **never becomes true**. Result: an **infinite loop**,
running at ~540 Mk/s (measured), re-examining the same key without ever advancing, with the "total"
counter on screen climbing continuously and giving the false impression of real progress. It only
ends via Ctrl+C, an external timeout, or finding the target by coincidence (if it happens to sit
exactly at the stuck position).

### When this occurs in practice

Any `stride` whose hex representation contains an `a`-`f` digit incorrectly survives the checkpoint
round-trip — which covers the overwhelming majority of `--stride` values other than 1 (multiples of
10 upward already have a good chance). It is only reachable by combining `--continue` with a
`--stride` != 1 (the default is 1, which survives the bug by coincidence, since "1" is a valid
digit in both systems).

### Historical context — not the first time this area of the code has broken

Version 0.27's changelog (~2019, [see releases](https://github.com/brichard19/BitCrack/releases))
records: "Fixed `--continue` bug where correct stride value wasn't stored in checkpoint file".
**This is not the same bug.** Back then `stride` simply was not written to the checkpoint at all —
the fix was adding the `stride=...` line to the write path. This audit's bug is different and more
subtle: `stride` **is** written, only in the wrong format (hex with no prefix, read as decimal).
Most likely it was introduced *by the 0.27 fix itself*, unnoticed since. The old stride issues that
exist on the tracker ([#94](https://github.com/brichard19/BitCrack/issues/94),
[#107](https://github.com/brichard19/BitCrack/issues/107),
[#115](https://github.com/brichard19/BitCrack/issues/115)) are from 2018-2019 and cover the
**earlier** bugs (stride overflowing the maximum key, 256-bit stride) — none describes the
hex/decimal round-trip documented here.

---

## Defect 9 — The same unchecked results buffer, reimplemented on the OpenCL path

**Level: VERIFIED IN CODE.** `CLKeySearchDevice/keysearch.cl:195-197`:

```c
void atomicListAdd(__global CLDeviceResult *results, __global unsigned int *numResults, CLDeviceResult *r)
{
    unsigned int count = atomic_add(numResults, 1);   // no ceiling
    ...
}
```

Buffer allocated with a fixed size at `CLKeySearchDevice.cpp:172`:
`_deviceResults = _clContext->malloc(128 * sizeof(CLDeviceResult));` — 128 slots, with no check of
`count < 128` before writing. This is Defect 4 (CUDA) reimplemented independently on the OpenCL
backend — the two backends share no code here, and both have exactly the same absence of
protection. This is not an isolated typo, it is a pattern missing from the entire project: neither
backend ever protects the results list against overflow.

**Partial good news**: OpenCL's **target** path (not results) is more robust than CUDA's —
`setTargetsList`/`setBloomFilter` (`CLKeySearchDevice.cpp:262-298`) use dynamic allocation
(`_clContext->malloc(5 * sizeof(unsigned int) * count)`), not fixed-size `__constant__` memory.
**Defect 3 (hangs above 16 targets) is specific to the CUDA backend** — OpenCL avoids the bug by
having a structurally different implementation, not by having fixed the same code.

---

## Defect 10 — The OpenCL backend does not compile on ANY device on this toolchain

**Level: DEMONSTRATED.** More serious than Defect 7 — it is not just the self-test failing to
compile, it is the **product** (`clBitCrack`) that compiles as a C++ binary but fails to build the
kernel at runtime, on every device.

`clBitCrack` (the host binary) compiles normally (`make BUILD_OPENCL=1 dir_keyfinder`, with no file
touched). But when run — on **two completely different devices**, an NVIDIA GPU and a CPU via pocl
(Portable OpenCL) — the kernel fails to compile at runtime:

```
[Info] Compiling OpenCL kernels...
2 errors generated.
[Info] Error: <kernel>:1935:34: error: passing '__generic unsigned int *' to parameter of
       type 'unsigned int *' changes address space of pointer
           ripemd160sha256NoFinal(hash, digestOut);
                                        ^~~~~~~~~
       <kernel>:1555:67: note: passing argument to parameter 'digest' here
       void ripemd160sha256NoFinal(const unsigned int x[8], unsigned int digest[5])
```

Same error, same function (`ripemd160sha256NoFinal`), on both devices — this is not a driver
peculiarity, it is the kernel's source code (`CLKeySearchDevice/*.cl`) violating an address-space
rule that modern Clang-based OpenCL C compilers (both NVIDIA's driver compiler and pocl's) now
enforce and that was not enforced when the project was written (2019-2020, likely a more permissive
OpenCL C 1.x/2.0 on this point).

**At least it fails cleanly**: `exit=1`, the compiler's error message shown, nothing hangs or gets
corrupted — unlike most of the other defects here, this one deceives nobody.

**Consequence**: in this audit, BitCrack's OpenCL backend is **completely unusable**, on either of
the two devices available on the test instance. Even if Defect 7 (self-test does not compile) were
fixed, the self-test would keep failing — because it shares the same `secp256k1.cl` the real
product uses, and that file has the same address-space defect.

---

## Defect 11 — `-b`/`-t`/`-p` with no upper bound: crash from an uncaught exception

**Level: DEMONSTRATED.**

No upper bound is validated for `-b` (blocks), `-t` (threads) or `-p` (points-per-thread).
`CudaKeySearchDevice::generateStartingPoints()` builds a
`std::vector<secp256k1::uint256> exponents` of size `blocks x threads x points`, with no check of
whether this is even a plausible amount of memory.

```
$ ./cuBitCrack -t 100000000 --keyspace 3000:3100 <address>
...
[Info] Generating 102,400,000,000 starting points (3906250.0MB)
terminate called after throwing an instance of 'std::bad_alloc'
```

Requesting ~3.9 PB of RAM fails, as expected — the problem is **how** it fails: `std::bad_alloc` is
caught nowhere. `run()` (`KeyFinder/main.cpp:410-424`) only has `catch(KeySearchException ex)` —
no safety `catch(...)`. The exception propagates up to `main()` with no handler,
`std::terminate()` is called, the process aborts with `SIGABRT` (**exit 134**), not a clean error
(`exit 1` with a message, as on every other error path in the program).

**With truly extreme values, the defect worsens**: `-b 2000000000 -t 2000000000 -p 2000000000`
makes the point-count computation itself overflow (an intermediate multiplication appears to use a
signed type somewhere in the calculation/formatting):

```
[Info] Generating -,106,958,398,427,234,304 starting points (13512046944256.0MB)
```

A **negative** number printed as the count of "points to generate" — evidence of integer overflow
before even attempting the allocation.

### Severity

Limited impact: this is local command-line input, not a remote surface — someone crashing their
own process with an absurd `-t` only affects themselves. But it is a real robustness failure, easy
to trigger by accident (for example, a typo adding extra digits to a value), and it breaks the
error pattern the rest of the program expects (a clean message + `exit=1`) exactly here.

---

## Defect 12 — No signal handling at all: stopping the process always loses up to 60s of progress

**Level: DEMONSTRATED.** Specifically relevant to long-duration use (days/weeks), such as
searching for a single Bitcoin puzzle target.

`KeyFinder/main.cpp` installs no signal handler — confirmed by searching the entire file
(`signal`/`SIGINT`/`SIGTERM`/`atexit`: no occurrence). The checkpoint is only written inside the
periodic status callback, every `checkpointInterval` (60000 ms, fixed — see Defect 8).

### Test

Process started with `--continue`, killed with `kill -INT` (the same signal `Ctrl+C` sends) before
completing 60 seconds of execution:

```
$ ps -p <pid>
    PID TTY          TIME CMD
(empty -- the process no longer exists)

$ ls chk_sig2.txt
ls: cannot access 'chk_sig2.txt': No such file or directory
```

The signal **brings the process down immediately** (the OS's default action for `SIGINT`, since
nothing was set up to intercept it) and **no checkpoint was written** — the file never even comes
into existence.

### What this means in practice

- **Every time the process needs to stop** — manual `Ctrl+C`, `kill` without `-9`,
  service/systemd restart, container shutdown, power loss, spot-instance preemption — up to 60
  seconds of the most recent work is lost, because there is no checkpoint write on shutdown, only
  the periodic one.
- This **does not worsen over time** — the 60s interval is fixed from the start to the end of any
  run, days or months. The risk per stop is always the same, small one (up to 60s of ~24 billion
  keys examined per day at ~525 Mk/s is a negligible fraction).
- **The real risk is for anyone NOT using `--continue`.** Without that flag, there is no checkpoint
  at all — any interruption (planned or not) loses 100% of that run's progress, and anyone running
  for weeks would need to manually track where they stopped (outside the tool) to avoid starting
  from zero.
- **Combined with Defect 8**: if `--continue` is used together with a `--stride` other than 1 (a
  common technique for splitting work across several instances without overlap), any resumption
  hangs forever (it is no longer "loses up to 60s", it is "never makes progress again").

---

## Additional tests that found NO problem

For the record, tested with no counter-example:

- Private keys near the top of the secp256k1 curve's order (`N - 2,000,000` through `N`): 16/16
  correct — no carry bug in high bits.
- `privkey = 1` and `privkey = N - 1`: correct.
- Uncompressed mode (`-u`): correct.
- `--compression BOTH`: correctly finds both forms (compressed and uncompressed) of the same key
  pair.
- Empty targets file: exits cleanly, `exit=0`, no hang (though it wastes GPU initialisation before
  realising there is nothing to do).
- Invalid address in the middle of a target list: rejected with `exit=1` and a message pointing to
  the exact line.
- `-O0` vs `-O2`: identical output, no sensitivity to compiler optimisation.
- `-d` with a non-existent device ID: clean error, no crash.
- `--keyspace` with an end past the secp256k1 curve's order: rejected with a clean error.
- **`--continue` resumption with `stride=1` (the common case)**: tested with a real checkpoint (not
  hand-built) — a real 75s search, checkpoint written at 58s, resumed with two targets, one 1,000
  keys before the saved position and another 1,000 after. The later target was found almost
  immediately; the earlier one never appeared. The resumption neither repeats work backward nor
  skips keys forward — correct for the common case (no explicit `--stride`).
- **`secp256k1lib` — SHA256 and RIPEMD160**: read line by line against the specification (FIPS
  180-4 and the reference RFC/paper for RIPEMD-160). `K`/`IV` constants, rotation tables, the final
  combination formula — everything matches. It is the standard reference implementation of
  RIPEMD-160 (the same one copied into nearly every project that uses the algorithm), correctly
  transcribed.
- **`secp256k1lib` — point doubling/addition and scalar multiplication**: `doublePoint`,
  `addPoints` and `multiplyPoint` (`secp256k1.cpp:658-733`) implement the standard textbook affine
  formulas (`s=3x^2/2y`, `s=(y1-y2)/(x1-x2)`, `rx=s^2-x1-x2`, `ry=s(x1-rx)-y1`, bit-by-bit
  double-and-add) — all correct, including `addPoints`'s edge cases (same point -> doubles; same X
  -> point at infinity; either side at infinity -> identity).
- **`secp256k1lib` — `invModP` (modular inverse)**: implements the extended binary Euclidean
  algorithm (the same type masterkey-gpu validates as "binary-GCD modinv" in its own tests),
  tracking the cofactors' sign in a separate integer (`x1Signed`/`x2Signed`) because the low-level
  `uint256` is magnitude only. Its structure matches the standard algorithm — the outer loop ends
  when `u` or `v` reaches 1, the inner loops strip factors of 2 by adjusting the cofactor (adding
  `P` before dividing when odd, a standard technique), a final step normalises the sign back to
  `[0, P)`. Not traced bit by bit by hand (the state has too much depth for that to be reliable
  without executing it), but the structure is the correct one, and the function is already
  exercised indirectly tens of thousands of times in this audit's black-box tests (every point
  doubling/addition calls `invModP`), with not a single incorrect result.
- **`secp256k1lib` — `multiplyModP` (fast reduction for the secp256k1 prime)**: implements the
  standard two-pass technique using `p = 2^256 - 2^32 - 977` (folding the high words of the 512-bit
  product by `2^32+977` and adding back, twice, because the first fold can itself overflow 256
  bits). On a first reading, this audit misread the order of operations and concluded the second
  pass read already-zeroed data — reading it again carefully, the real order is: the product's
  high words are zeroed **before** the first addition, so the second pass does in fact reuse the
  first pass's real *carry*, not zero. Correct, it is the standard technique. The misreading is
  recorded here on purpose: it avoids reporting a false positive and documents why the final
  conclusion is "correct" rather than "suspect".
- **`CryptoUtil/Rng.cpp` — the random generator used by default** (when `addrgen`/`-n` generate a
  key with no explicit argument): seeded from `/dev/urandom` on Linux (`BCryptGenRandom` on
  Windows) — cryptographically adequate OS entropy sources — then expanded via SHA256 in counter
  mode (automatic reseed every 2^32 calls). A solid, standard construction for generating random
  bytes from a seed — nothing to do with the weak `rand()` found in the dead function during the
  earlier reading; the contrast reinforces that that `rand()` really was an isolated leftover, not
  the project's real pattern.
- **Cosmetic note, no practical impact**: there is a second `generatePrivateKey()` function in
  global scope (`secp256k1.cpp:734`, without the `secp256k1::` prefix every other function in the
  file uses), using `rand()` — a weak PRNG — instead of the `_rng.get()` the correct version uses.
  It is only called from inside `generateKeyPairsBulk(unsigned int count, ...)`, and that function
  **is called from nowhere in the project** (confirmed by searching the entire repository) — dead
  code duplicating dead code, with no real execution path. Not an active defect, but the kind of
  oversight (a forgotten global `rand()` sitting next to a namespaced, safe version) that becomes a
  real problem if someone reactivates that function later without noticing the difference.

---

## What was checked and is CORRECT

Recorded so the account is fair:

- **End of interval is checked** (unlike KeyHunt-Cuda) — it only overruns by up to one batch, it
  does not run indefinitely.
- **No finding is recomputed-and-discarded.** The result path accepts what the GPU returns without
  trying to re-derive and compare Base58 — KeyHunt-Cuda's Defect 1 class (a checksum corrupted by
  optimisation, the finding thrown away) does not apply here by construction: the match is by
  hash160 compared on the device, the Base58 address is only assembled on the host for display,
  from the `x,y` the GPU itself returned — there is no Base58 on the decision path.
- **No sensitivity to optimisation flags, tested.** A rebuild with `CXXFLAGS="-O0 -std=c++11"`
  (via a `make` parameter, with no Makefile edit) reproduced exactly the same results as the
  default `-O2` build, byte for byte, in two independent tests (a single key and a batch of 16
  targets). Unlike KeyHunt-Cuda, here the hypothesis was raised and **ruled out by testing**, not
  just by a structural argument.
- **Private-key reconstruction arithmetic matched in every case tested.** 16 private keys we chose,
  spread across an interval of 5 iterations (~1.3M keys, crossing several
  `thread`/`block`/`idx` combinations), were compared programmatically against the original value:
  **16 of 16 matched exactly.** This does not prove the absence of Defect 5's risk (the
  cross-check function is still never called), but it is real evidence that, in the cases tested,
  the offset arithmetic is correct.
- **No random mode on the CLI.** `--keyspace` is always sequential/deterministic (`START:END`,
  `START:+COUNT`, or sliced with `--share M/N`). KeyHunt-Cuda's Defect 3 class (`Rand()` ignoring
  the start of the interval) has nowhere to manifest — BitCrack has no such mode.
- **Test-instance security**: correct permissions, no suspicious local accounts — checked before
  any build, separately from the code audit itself.

---

## Summary

| # | Defect | Level | Severity |
|---|---|---|---|
| 1 | Default build does not compile (`COMPUTE_CAP=30` obsolete) | DEMONSTRATED | Blocks the build, no documented workaround |
| 2 | `dlink` with no explicit architecture, mislabelled cubin | DEMONSTRATED | Did not break correctness in the tests performed |
| 3 | **Search with >16 addresses fails (CUDA 13.2)** | DEMONSTRATED on this version | **Serious — breaks the project's primary use.** See the version caveat: in 2020, with an older CUDA, 160 addresses ran ([#217](https://github.com/brichard19/BitCrack/issues/217)) |
| 4 | Results buffer with no bounds check | VERIFIED IN CODE | Serious in theory; blocked in practice by Defect 3 |
| 5 | Reported private key never re-checked (`verifyKey` dead) | VERIFIED IN CODE + a test with no counter-example | Structural risk, not confirmed active |
| 6 | End of interval overrun by up to 1 batch | DEMONSTRATED | Moderate — bounded, not uncontrolled |
| 7 | Self-test does not compile as distributed | DEMONSTRATED | Second order — nobody runs the quality gate |
| 8 | Checkpoint corrupts `stride` != 1 into 0 -> infinite loop with no progress | DEMONSTRATED | Serious — a silent denial of service, only when used with `--continue` + `--stride` |
| 9 | Results buffer with no check, also on the OpenCL backend | VERIFIED IN CODE | Same class as Defect 4, an independent backend |
| 10 | OpenCL kernel does not compile on ANY device tested (GPU or CPU) | DEMONSTRATED | **Serious — the entire OpenCL backend is unusable on this toolchain** |
| 11 | `-b`/`-t`/`-p` with no upper bound -> uncaught overflow/`std::bad_alloc`, `SIGABRT` | DEMONSTRATED | Moderate — only affects whoever types the command themselves, but breaks the rest of the program's clean-error pattern |
| 12 | No signal handling at all — every stop loses up to 60s, without `--continue` loses everything | DEMONSTRATED | **Serious for real use (long-duration searches) — exactly the scenario of someone hunting the Bitcoin puzzle** |

---

## Practical guide — is it reliable to use for searching the Bitcoin puzzle targets?

This section exists because a report of 12 defects, by itself, does not answer the question that
matters to someone who will actually use the tool. Direct answer, with the scope caveat already
given in Section 0.1: **within what this audit tested** (CUDA backend, a single key or a small
list, default parameters), every result produced was correct. Outside that narrow use, or in
prolonged use without care, the program tends to hang, stop progressing or refuse to run — not to
lie about what it found. And there are old, unresolved reports (Section 0.1) this audit could
neither reproduce nor rule out, mostly on the OpenCL backend.

### Safe to use, under these conditions

- **A single address, or a small list (<=16 addresses).** Above that it always hangs on the CUDA
  13.2 tested (Defect 3) — though issue
  [#217](https://github.com/brichard19/BitCrack/issues/217) suggests this may vary by CUDA version
  (see the version caveat in Defect 3).
- **NVIDIA GPU (CUDA), not AMD/Intel (OpenCL).** The OpenCL path did not compile on any device
  tested in this audit (Defect 10), and that is precisely where most of the unresolved not-found
  key reports come from (Section 0.1).
- **Compiled with the right GPU architecture.** The `Makefile` ships with a 2012 architecture
  (`compute_30`); `COMPUTE_CAP` needs to be changed at compile time to the GPU's number (e.g.
  `sm_89` for Ada, `sm_86` for Ampere).
- **`--stride` at the default (do not use a custom value).**
- **`-b`/`-t`/`-p` at the values the program itself suggests**, without typing large manual values.

### For long-duration searches (the real puzzle use case) — additional rules

- **Always use `--continue`.** Without this flag, any interruption — planned or not — loses 100%
  of that run's progress (Defect 12).
- **Never combine `--continue` with a `--stride` other than 1.** This is the combination that
  corrupts the checkpoint and hangs the search in an infinite loop that never ends, with no
  warning (Defect 8). With `--continue` and `stride=1` (the default), resumption works correctly —
  tested with a real checkpoint in this audit.
- **A normal stop always costs up to 60 seconds of work**, even doing everything right — the
  checkpoint is only written periodically, never on shutdown (Defect 12). Irrelevant over a
  weeks-long search, but not zero.
- **Occasionally check that the Mk/s counter is really advancing**, not just "running" — Defect 8's
  infinite loop does not hang the process, it just stops making progress, and from the outside it
  looks normal.

### Do not use if

- You need to search **a large list of addresses** at once (for example, all 32 Bitcoin puzzle
  addresses together) — in the tested environment, this simply does not run.
- You only have an **AMD or Intel GPU** — that is precisely where the unresolved not-found-key
  reports concentrate (Section 0.1), and the OpenCL backend did not even compile on either of the
  two devices tested in this audit.

### The weak point that remains open even in the recommended use

Nowhere in the code is there a second, internal check confirming the printed private key really is
the one that generates the found address (Defect 5). In every test in this audit that never failed
— but "never failed in the tests someone ran" is a weaker guarantee than "the code proves it is
correct", which is the standard used, for example, in masterkey-gpu's engine (mandatory
re-verification before writing any finding). Anyone relying on a BitCrack result to publicly claim
they solved a puzzle should independently re-check the key with a separate tool before announcing
it.

---

## Direct comparison with KeyHunt-Cuda (same methodology, `AUDIT_KEYHUNT_CUDA_2026-08-05_EN.md`)

| mechanism | KeyHunt-Cuda v1.07 | BitCrack |
|---|---|---|
| Finding not verified | discards 100% of findings (default build) | accepts without re-verifying the key (does not discard, but also does not check) |
| End of interval | never checked, overrun up to 25,157x | checked between batches, overrun up to ~262 thousand keys |
| Start in random mode | ignored | no random mode exists |
| Results buffer | truncates with a missing warning, but does NOT overrun memory | **no check at all — can write out of bounds** |
| Multi-target | works (correct Bloom filter) | **hangs above 16 targets** |
| Self-test | fails 3/8 out of the box, but compiles and runs | does not compile as distributed |
| Build with the current toolchain | does not compile without a workaround | does not compile without a workaround |

Neither project would pass, today, a CI pipeline requiring "compiles clean and self-test green" —
and neither has such a pipeline.

---

## Open items

- **The most important one**: the user reports in Section 0.1 (keys inside the interval not found
  — #81, #128, #217, #337, #378, #628) remain **unexplained**. **#628 was tested in this audit
  with its exact command, on CUDA — did not reproduce** (found the correct key, no anomaly, in
  ~19 minutes). The other five (all OpenCL) remain untested, because OpenCL does not compile on
  this toolchain (Defect 10). Anyone with an AMD GPU and a working OpenCL should repeat #628's
  exact command on that backend first — it is the most recent case (Oct 2025), with a known target
  and a ready-made reproducer; now that CUDA is ruled out as the explanation, suspicion
  concentrates entirely on the OpenCL path.
- **Hypothesis about Defect 3 on old CUDA — partially tested, still open.** CUDA 12.5 rejects the
  same way as 13.2 (tested). Still missing: CUDA 10.x/11.x (issue #217's era) **and** a driver from
  the same era — this GPU (Ada) does not run a 2020 driver. See "Version scope" under Defect 3.
- Defect 4 (unchecked buffer, CUDA) was not demonstrated in execution — it would require more than
  16 targets genuinely in the same batch, and Defect 3 prevents setting up that scenario without
  editing code (prohibited in this audit). This remains a code-level finding, not an execution one.
  The same applies to Defect 9 (the same class on OpenCL) — not tested in execution in this audit
  (OpenCL was not compiled/run end to end, only read).
- `--share M/N`: overlap between adjacent partitions **demonstrated** (see the body of the
  document). `--continue`/checkpoint: tested, resulting in Defect 8 (`stride` corruption) **and**
  a positive confirmation — position resumption itself (`next=`), with `stride=1`, works correctly
  (tested with a real checkpoint, not hand-built).
- A complete line-by-line audit of the OpenCL path (`CLKeySearchDevice`) was not done beyond the
  specific points verified (self-test, target limit, results buffer) — no known-key reproducer was
  run on the `clBitCrack` binary.
- Not tested on another GPU architecture (only Ada sm_89 this session) nor on a CUDA version other
  than 13.2.
- Defect 5 (missing verification) was tested with 16+16 scatter keys across two different regions
  of the space (near 2^32 and near the curve's order) — this is not exhaustive proof of
  `getPrivateKeyOffset`'s arithmetic for every possible `threads/blocks/points/iterations`
  combination.
- `secp256k1lib`/`CryptoUtil` — this audit's code-reading coverage was complete for: SHA256,
  RIPEMD160, big-int `add`/`sub`/`multiply`, `doublePoint`/`addPoints`/`multiplyPoint`, `invModP`,
  `multiplyModP` and `Rng.cpp`. No functional finding in any of them — only the cosmetic note about
  the dead `generatePrivateKey()` and a comment inconsistency in `lessThanEqualTo`. Not read line by
  line: `reduceModN`/`multiplyModN` (Barrett reduction for the curve's order, used only in
  `--stride` and key combination, a path little exercised in this audit's tests) and
  `bulkInversionModP`/`generateKeyPairsBulk` (not used by the production binary, already confirmed
  dead code). Confidence in the main arithmetic now comes from two independent, mutually
  reinforcing sources: large-scale black-box testing (46+ known keys covering the entire 256-bit
  space, plus byte-for-byte agreement with masterkey on 25 independent addresses) **and**
  line-by-line code reading against the specification, with no divergence between the two.
- `--compression BOTH`, an empty target file and an invalid address were tested with no finding.
