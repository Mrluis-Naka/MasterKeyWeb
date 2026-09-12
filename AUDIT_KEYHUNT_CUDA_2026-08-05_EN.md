# Audit of KeyHunt-Cuda v1.07 — six defects, with a declared proof level

**Date**: 2026-08-05
**Object**: KeyHunt-Cuda v1.07, code as distributed (`KeyHunt-Cuda-main` repository)
**Motivation**: a user observation that a scan of puzzle #38 with the exact range did not find the
key, and only found it after the range was widened.

---

## 0. Method and limits

**No source file was modified.** This is a test condition: a defect only counts if it appears in
the code as distributed. The only interventions were compiler command-line flags and the choice of
CUDA toolkit version — neither alters the audited logic. Integrity confirmed by hash: `Timer.h` on
the instance has md5 `5ec1aedafeba63f89a82329699226f20`, identical to the local copy.

**Test environment**: rented instance, NVIDIA RTX 4070 Ti (sm_89), driver 595.84, Ubuntu 24.04,
g++ 13.3.0, CUDA 12.9 (the system's 13.2 does not compile the project — see Defect 6).

**Reference target**: puzzle #20, private key `0xd2c55`, address
`1HsMJxNiV7TLxmoF6uJNkydxPFDog4NQum`. Key previously double-verified in the project's archive and
re-checked here with an independent implementation (secp256k1, SHA-256, RIPEMD-160 and Base58Check
reimplemented from the specifications, with no line from either KeyHunt-Cuda or masterkey-gpu).

**Proof scale used in this document**:

| Level | Meaning |
|---|---|
| **DEMONSTRATED** | reproduced in a real run this session, output captured |
| **VERIFIED IN CODE** | read in the source, with file and line; not executed in isolation |

---

## Defect 1 — The project's default build makes the tool discard the key it found

**Level: DEMONSTRATED.** This is the most serious defect and explains the observation that
triggered the audit.

Compiled with the flags the `Makefile` itself prescribes (`-O2 -mssse3`), the Base58Check encoder
produces an **invalid checksum on every address generated**. Since the resulting address does not
match the target being searched for, `checkPrivKey` concludes the key is wrong, prints a warning
and **discards the hit**.

### Evidence A — before and after

Same source, same command, same target, same range. Only the flags change.

Default build (`-O2 -mssse3`):
```
Warning, wrong private key generated !
  PivK :D2C55
  Addr :1HsMJxNiV7TLxmoF6uJNkydxPFDohQzunL
  PubX :3C4A45CBD643FF97D77F41EA37E843648D50FD894B864B0D52FEBC62F6454F7C
```
No output file written.

Build with `-O0` (or `-O2 -fno-strict-aliasing`):
```
PubAddress: 1HsMJxNiV7TLxmoF6uJNkydxPFDog4NQum
Priv (WIF): p2pkh:KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rHfuE2Tg4nJW
Priv (HEX): D2C55
PubK (HEX): 033C4A45CBD643FF97D77F41EA37E843648D50FD894B864B0D52FEBC62F6454F7C
```
Written correctly to `Found.txt`.

**Key `D2C55` is the correct key for puzzle #20 in both cases.** The default build found it and
rejected it.

### Evidence B — the error isolated byte by byte

Decoding the two Base58 addresses:

```
                     version  hash160                                    checksum
true                 00       b907c3a2a3b27789dfb509b730dd47703c272868   2e201588  OK
KeyHunt (-O2)        00       b907c3a2a3b27789dfb509b730dd47703c272868   6329796d  INVALID
```

Identical version byte. **Identical hash160.** The public key's X coordinate as printed by the
tool is identical to the independently computed one. In other words: the elliptic-curve arithmetic
is correct, the hash160 is correct, and the error lies exclusively in the 4 checksum bytes.

### Evidence C — the tool's own built-in self-test

`./KeyHunt -c` runs known vectors. Result by compile configuration:

| Flags | Failed | Passed |
|---|---|---|
| **`-O2 -mssse3` (project default)** | **8** | **0** |
| `-O1 -mssse3` | 3 | 5 |
| `-O0 -mssse3` | 3 | 5 |
| `-O2 -mssse3 -fno-strict-aliasing` | 3 | 5 |
| `-O0 -mssse3 -fno-strict-aliasing` | 3 | 5 |

Only the default configuration fails everything. The 3 failures that persist across every
configuration are of a different nature — see Defect 5.

### Cause

A strict-aliasing rule violation in the source, exploited by modern g++ from `-O2` upward.
Demonstrated by the fact that `-fno-strict-aliasing` restores the 5 P2PKH vectors while keeping
`-O2`.

### Practical consequence

Anyone compiling the project today, on Linux, following its instructions, gets a binary that
**finds and throws away**. The search keeps running as if nothing happened. There is no error
code, no output file — just a warning in the middle of the status stream.

---

## Defect 2 — There is no end-of-range check

**Level: DEMONSTRATED**, twice, on different builds and modes.

The main loop terminates only when a key is found or on error (`KeyHunt.cpp:987-991`):

```c
while (ok && !endOfSearch) {
    ... launches kernel ...
    for (int i = 0; i < nbThread; i++)
        keys[i].Add((uint64_t)STEP_SIZE);
}
```

Every thread advances indefinitely. Nothing compares the current position against `rangeEnd`.

Measured, with a declared range of **10,001 keys** (`d18cd:d3fdd`):

| Mode | Keys scanned | Overrun | Tool's own counter |
|---|---|---|---|
| GPU | 251,658,240 | **25,157x** | `[C: 2516582.400000 %]` |
| CPU | 3,508,224 | **350x** | `[C: 35082.240000 %]` |

The completion percentage above 100% is the tool declaring, in its own status line, that it left
the requested interval. Independent of compile flags.

---

## Defect 3 — Random mode ignores the start of the range

**Level: VERIFIED IN CODE.** Not empirically demonstrated this session.

`Int::Rand(Int* randMax)` (`Int.cpp:1021`) returns a value uniform on `[0, randMax)`:

```c
void Int::Rand(Int* randMax) {
    int b = randMax->GetBitLength();
    Int r;  r.Rand(b);
    Int q(&r), rem;
    q.Div(randMax, &rem);
    Set(&rem);                 // result in [0, randMax)
}
```

`Int.h:160-161` shows only two overloads exist — `Rand(int nbit)` and `Rand(Int*)`. **There is no
two-argument (minimum, maximum) version.**

Both call sites pass the interval's **end**:

```c
KeyHunt.cpp:548   getCPUStartingKey(Int& tRangeStart, Int& tRangeEnd, ...)
                      key.Rand(&tRangeEnd);        // tRangeStart received and never used

KeyHunt.cpp:828   getGPUStartingKeys(...)
                      keys[i].Rand(&tRangeEnd2);   // tRangeEnd2 is absolute, not relative
```

On the CPU path, `tRangeStart` arrives as a parameter and is ignored in the random branch.

### Quantification

For a puzzle range `[2^(N-1), 2^N)`, where the start equals the width:

- **CPU**: uniform draw on `[0, rangeEnd)` -> **50% of restarts start below the range**.
- **GPU**: thread `i` draws on `[0, rangeStart + (i+1)*chunk)`. Integrating over the threads, the
  useful fraction is `1 - ln2 approx 30.7%` -> **69.3% of draws fall below the range**, and the
  search is **3.26x slower** than declared.

### Behavioural signature

Since the effective space is `[0, rangeEnd)` rather than `[rangeStart, rangeEnd)`, **widening the
range increases the useful fraction of the draws**. In a correct implementation, widening the
range can only make search time worse. This inversion is diagnostic and matches the report that
triggered the audit.

---

## Defect 4 — Silent truncation of the results buffer

**Level: VERIFIED IN CODE.**

The kernel always increments the counter, but only writes if there is room
(`GPU/GPUCompute.h:112`):

```c
uint32_t pos = atomicAdd(out, 1);
if (pos < maxFound) { ... writes ... }
```

The host then clips the counter without warning, at four points
(`GPU/GPUEngine.cu:691, 743, 790, 843`):

```c
uint32_t nbFound = outputBufferPinned[0];
if (nbFound > maxFound) {
    nbFound = maxFound;      // no warning, no error code
}
```

`maxFound = 1024 * 64 = 65,536` (`Main.cpp:219`), per kernel launch. Anything beyond that is
silently lost. The limit is reachable in multi-address mode, where **false positives from the
Bloom filter also consume a slot**, since the write happens before any check on the host.

This is not memory corruption: the bounds check exists and is correct. It is silent data loss.

---

## Defect 5 — The self-test is distributed already failing

**Level: DEMONSTRATED.**

Under any compile configuration, 3 of the 8 address checks fail:

```
Adress : 3CyQYcByvcWK8BkYJabBS82yDLNWt6rWSx Failed !          (P2SH)
Adress : 31to1KQe67YjoDfYnwFJThsGeQcFhVDM5Q Failed !          (P2SH)
Adress : bc1q6tqytpg06uhmtnhn9s4f35gkt8yya5a24dptmn Failed !  (Bech32)
```

These are address types the tool does not implement — for them it returns a P2PKH. Taken in
isolation this is a known limitation, not a defect.

**The second-order problem is serious:** a self-test that always fails trains the user to ignore
its output. This is the most likely explanation for Defect 1 never having been noticed — anyone
running `-c` would see failures and treat them as the usual ones.

---

## Defect 6 — Does not build on Linux with the current toolchain

**Level: DEMONSTRATED** (blocked the build until worked around with a flag).

1. `Timer.h:37` declares `static uint32_t getSeed32();` but the file includes only `<time.h>` and
   `<string>` — never `<cstdint>`. On Windows, `<windows.h>` supplies the type; on Linux with g++
   13 the whole declaration is dropped and `Main.cpp` fails with "`getSeed32` is not a member of
   `Timer`".

2. `GPU/GPUEngine.cu:464` uses `cudaDeviceProp::computeMode`, removed in CUDA 13. Ironically this
   sits in a function that only prints the device list (`-l`), yet it brings down the entire
   build.

The README does not document building on Linux — every example uses `KeyHunt-Cuda.exe`. Anyone
building on Linux depends on the `Makefile`, whose default is exactly what triggers Defect 1.

---

## What was checked and is CORRECT

Recorded so the account is fair and the scope of the criticism is bounded:

- **Elliptic-curve arithmetic**: the X coordinate printed by the tool is identical, digit for
  digit, to the one computed by an independent implementation.
- **hash160**: identical to the independent one (`b907c3a2...`), even in the defective build.
- **Sign of the `incr` offset**: suspected a sign error and **ruled it out** — the values passed
  range from 0 to 2047, always non-negative.
- **Per-thread group coverage**: contiguous and complete, `B+0` to `B+2047`, correctly joining
  with the following `STEP_SIZE`. No gap between launches.
- **Bounds check before writing to the buffer**: present and correct. There is no memory
  corruption.

---

## Summary

| # | Defect | Level | Build-dependent? |
|---|---|---|---|
| 1 | Default build discards the found key | DEMONSTRATED | Yes (`-O2`) |
| 2 | No end-of-range check | DEMONSTRATED | No |
| 3 | Random mode ignores `rangeStart` | VERIFIED IN CODE | No |
| 4 | Silent truncation at 65,536/launch | VERIFIED IN CODE | No |
| 5 | Distributed self-test already failing | DEMONSTRATED | No |
| 6 | Does not build with the current toolchain | DEMONSTRATED | — |

---

## Open item

The exact scenario reported for puzzle #38 (not found with the exact range, found after widening
it) was not reproduced. The hypothesis consistent with Defects 1 and 3 is that the tool found and
discarded the key; the "found after widening" part remains without a closed explanation and should
not be stated publicly without reproduction.

Defects 3 and 4 were also not empirically demonstrated — the code evidence is direct and checkable,
but an isolated run would make them unassailable.
