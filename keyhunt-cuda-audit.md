# KeyHunt-Cuda v1.07 — audit findings

**Date:** 2026-08-05
**Subject:** KeyHunt-Cuda v1.07, source exactly as distributed
**Why this exists:** MasterKey was validated against independent cryptographic oracles rather than
against existing tools. This document is the concrete reason that decision was right.

---

## Check your own binary first

If you use KeyHunt-Cuda, this takes ten seconds and answers the question for your specific build:

```
./KeyHunt -c
```

Look at the five P2PKH vectors — the ones whose addresses start with `1`:

```
Adress : 15t3Nt1zyMETkHbjJTTshxLnqPzQvAtdCe OK!
Adress : 1BoatSLRHtKNngkdXEeobR76b53LETtpyT OK!
Adress : 1Test6BNjSJC5qwYXsjwKVLvz7DpfLehy OK!
Adress : 16S5PAsGZ8VFM1CRGGLqm37XHrp46f6CTn OK!
Adress : 1Tst2RwMxZn9cYY5mQhCdJic3JJrK7Fq7 OK!
```

**If any of those five say `Failed`, your binary generates invalid addresses.** It will find the
correct private key and reject it as wrong. Read Finding 1.

Three other vectors (two `3...` P2SH, one `bc1...` Bech32) fail in *every* build — those address
types are simply not implemented. Their permanent failure is itself part of the problem: it trains
users to ignore self-test output, which is the most likely reason Finding 1 went unnoticed.

---

## Test conditions

No source file was modified. That is a condition of the test: a defect only counts if it is
present in the code as distributed. The only interventions were compiler command-line flags and
the CUDA toolkit version — neither changes the logic under audit. File integrity was confirmed by
hash before building.

Hardware: NVIDIA RTX 4070 Ti (sm_89), driver 595.84, Ubuntu 24.04, g++ 13.3.0, CUDA 12.9.

**Version audited:** <https://github.com/Qalander/KeyHunt-Cuda>, branch `main`, as of 2026-08-05
(190 stars, 172 forks, last pushed 2025-09-30). Every file cited below — `KeyHunt.cpp`, `Int.cpp`,
`Int.h`, `Main.cpp`, `Timer.h`, `GPU/GPUEngine.cu`, `GPU/GPUCompute.h` — was byte-for-byte
compared against that branch and is identical to the copy tested. The `Makefile` is identical
too, including the `-O2 -mssse3` defaults that trigger Finding 1. These are not stale findings
against an abandoned fork.

Reference target: Bitcoin puzzle #20, private key `0xd2c55`, address
`1HsMJxNiV7TLxmoF6uJNkydxPFDog4NQum`. Independently re-derived here with secp256k1, SHA-256,
RIPEMD-160 and Base58Check reimplemented from their specifications — no code from KeyHunt-Cuda and
none from MasterKey.

---

## Finding 1 — The project's default build discards the key it just found

**Status: demonstrated, with before/after capture.**

Built with the flags the project's own `Makefile` prescribes (`-O2 -mssse3`), the Base58Check
encoder produces an **invalid checksum on every address tested** — all eight built-in self-test
vectors plus the puzzle #20 address, nine for nine. The resulting string does not match the target
being searched for, so `checkPrivKey` concludes the key is wrong, prints a warning, and **throws
the hit away**.

Same source, same command, same target, same range. Only the compiler flags differ.

Default build (`-O2 -mssse3`):

```
Warning, wrong private key generated !
  PivK :D2C55
  Addr :1HsMJxNiV7TLxmoF6uJNkydxPFDohQzunL
  PubX :3C4A45CBD643FF97D77F41EA37E843648D50FD894B864B0D52FEBC62F6454F7C
```

No output file written.

Same binary rebuilt with `-O0`, or with `-O2 -fno-strict-aliasing`:

```
PubAddress: 1HsMJxNiV7TLxmoF6uJNkydxPFDog4NQum
Priv (WIF): p2pkh:KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rHfuE2Tg4nJW
Priv (HEX): D2C55
PubK (HEX): 033C4A45CBD643FF97D77F41EA37E843648D50FD894B864B0D52FEBC62F6454F7C
```

Written correctly to `Found.txt`. **`D2C55` is the correct key for puzzle #20 in both runs.** The
default build found it and rejected it.

### The error, isolated byte by byte

Decoding both Base58 strings:

```
                  version   hash160                                    checksum
correct           00        b907c3a2a3b27789dfb509b730dd47703c272868   2e201588   valid
KeyHunt (-O2)     00        b907c3a2a3b27789dfb509b730dd47703c272868   6329796d   INVALID
```

Same version byte. **Same hash160.** The public-key X coordinate the tool printed is identical to
the independently computed one. The elliptic-curve arithmetic is correct, the hash160 is correct,
and the entire error is confined to the four checksum bytes.

### Self-test result by build configuration

| Flags | Failed | Passed |
|---|---|---|
| **`-O2 -mssse3` (project default)** | **8** | **0** |
| `-O1 -mssse3` | 3 | 5 |
| `-O0 -mssse3` | 3 | 5 |
| `-O2 -mssse3 -fno-strict-aliasing` | 3 | 5 |
| `-O0 -mssse3 -fno-strict-aliasing` | 3 | 5 |

Only the default configuration fails everything. `-fno-strict-aliasing` restoring the five P2PKH
vectors while keeping `-O2` points to a strict-aliasing violation in the source that modern
compilers are entitled to exploit.

### Scope of this finding

This is build-dependent. A prebuilt Windows binary, or a build with an older compiler, may be
unaffected — which is exactly why the ten-second self-test above matters more than any claim made
here. What is certain: **building on Linux today, following the project's own Makefile, produces a
tool that silently rejects its own correct results.**

---

## Finding 2 — There is no range-end check

**Status: demonstrated, twice, in different builds and modes. Build-independent.**

The main loop terminates only when a key is found or on error (`KeyHunt.cpp:913`, advance at
`KeyHunt.cpp:988`):

```c
while (ok && !endOfSearch) {
    ... launch kernel ...
    for (int i = 0; i < nbThread; i++)
        keys[i].Add((uint64_t)STEP_SIZE);
}
```

Nothing compares the current position against `rangeEnd`. Measured with a declared range of
**10,001 keys**:

| Mode | Keys scanned | Overscan | Tool's own counter |
|---|---|---|---|
| GPU | 251,658,240 | **25,157×** | `[C: 2516582.400000 %]` |
| CPU | 3,508,224 | **350×** | `[C: 35082.240000 %]` |

A completion percentage above 100% is the tool stating, in its own status line, that it left the
interval you asked for.

---

## Finding 3 — Random mode ignores the start of your range

**Status: verified in source. Build-independent.**

`Int::Rand(Int* randMax)` (`Int.cpp:1021`) returns a uniform value in `[0, randMax)`:

```c
void Int::Rand(Int* randMax) {
    int b = randMax->GetBitLength();
    Int r;  r.Rand(b);
    Int q(&r), rem;
    q.Div(randMax, &rem);
    Set(&rem);                 // result in [0, randMax)
}
```

`Int.h` declares only two overloads — `Rand(int nbit)` and `Rand(Int*)`. There is no
two-argument (min, max) form. Both callers pass the **end** of the interval:

```c
KeyHunt.cpp:548   void KeyHunt::getCPUStartingKey(Int& tRangeStart, Int& tRangeEnd, ...)
KeyHunt.cpp:554       key.Rand(&tRangeEnd);        // tRangeStart received, never used

KeyHunt.cpp:828   void KeyHunt::getGPUStartingKeys(...)
KeyHunt.cpp:852       keys[i].Rand(&tRangeEnd2);   // tRangeEnd2 is absolute, not relative
```

In the CPU path, `tRangeStart` arrives as a parameter and is ignored in the random branch.

For a puzzle range `[2^(N-1), 2^N)`, where the start equals the width:

- **CPU:** uniform over `[0, rangeEnd)` → **50% of restarts begin below your range.**
- **GPU:** thread *i* draws from `[0, rangeStart + (i+1)·chunk)`. Integrated across threads, the
  useful fraction is `1 − ln2 ≈ 30.7%` → **69.3% of draws land below your range**, making the
  search **3.26× slower** than declared.

**Diagnostic signature:** because the effective space is `[0, rangeEnd)` rather than
`[rangeStart, rangeEnd)`, *widening* your range increases the useful fraction of draws. In a
correct implementation, widening a range can only make the search slower. That inversion is a
symptom worth watching for.

---

## Finding 4 — Results are truncated silently at 65,536 per launch

**Status: verified in source.**

The kernel always increments the counter but only writes if there is room
(`GPU/GPUCompute.h:112`):

```c
uint32_t pos = atomicAdd(out, 1);
if (pos < maxFound) { ... write ... }
```

The host then clamps the count with no warning, at four separate sites
(`GPU/GPUEngine.cu:691, 743, 790, 843`):

```c
uint32_t nbFound = outputBufferPinned[0];
if (nbFound > maxFound) {
    nbFound = maxFound;      // no warning, no error code
}
```

`maxFound = 1024 * 64 = 65,536` per kernel launch (`Main.cpp:219`). Everything beyond that is
lost silently. The limit is reachable in multi-address mode, where **Bloom-filter false positives
also consume slots** — the kernel writes before any host-side verification.

This is not memory corruption: the bounds check is present and correct. It is silent data loss.

---

## Finding 5 — It does not build on a current Linux toolchain

**Status: demonstrated — both errors blocked the build until worked around by flags.**

1. `Timer.h` declares `static uint32_t getSeed32();` while including only `<time.h>` and
   `<string>` — never `<cstdint>`. On Windows `<windows.h>` supplies the type; on Linux with
   g++ 13 the declaration is discarded and the build fails with
   *"`getSeed32` is not a member of `Timer`"*.

2. `GPU/GPUEngine.cu:464` uses `cudaDeviceProp::computeMode`, removed in CUDA 13. It sits in a
   function that only prints the device list, but it breaks the whole build.

The README documents no Linux build procedure — every example invokes `KeyHunt-Cuda.exe`. Anyone
building on Linux depends on the `Makefile`, whose defaults are exactly what triggers Finding 1.

---

## What was checked and found correct

Stated so the scope of the criticism is clear:

- **Elliptic-curve arithmetic** — the X coordinate the tool printed matches an independent
  implementation digit for digit.
- **hash160** — identical to the independent computation, even in the defective build.
- **Offset sign handling** — suspected to be a sign-extension bug, checked, and **ruled out**:
  offsets run 0 to 2047 and are never negative.
- **Per-thread group coverage** — contiguous and complete, `B+0` through `B+2047`, joining
  correctly with the following step. No gaps between launches.
- **Kernel bounds check before writing** — present and correct. No memory corruption.

Two of these were suspected defects that did not survive verification.

---

## Open item

The scenario that prompted this audit — a puzzle #38 sweep that failed with the exact range and
succeeded with a widened one — was **not reproduced here**. Findings 1 and 3 are each consistent
with the first half of that report. The "found it after widening" half remains unexplained and is
not claimed as established.
