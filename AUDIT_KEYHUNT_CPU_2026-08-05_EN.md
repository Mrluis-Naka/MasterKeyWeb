# Audit — keyhunt (CPU, albertobsd) v0.2.230519 — 2026-08-05

**Finding:** the interval declared via `-r START:END` (and via `-b BITS`) **does not bound the work
performed**. The end-of-range check runs before a thread reserves a work block, but the block has a
fixed size of 2^32 keys and is never trimmed to the interval's end.

Three consequences, all measured in this audit:

1. The scan overruns the declared `END` by up to `nthreads x 2^32` keys.
2. Private keys **outside** the declared interval are reported to the user, unmarked.
3. For any interval smaller than 2^32, **all threads but one exit immediately** — parallelism is
   silently disabled.

The combined cost, measured on the same interval with the same 8 threads: **2.1 seconds against
~795 seconds**, a factor of 378x.

---

## 1. Test conditions

**No source file was modified.** Compiled with the upstream `Makefile`, without changing a single
flag: `-Ofast -ftree-vectorize -flto -march=native -mtune=native -mssse3`.

| Item | Value |
|---|---|
| Tool | keyhunt `0.2.230519 Satoshi Quest`, albertobsd |
| CPU | AMD Ryzen 7 7735HS, 8 cores / 16 threads |
| OS | Ubuntu under WSL2 |
| Compiler | g++ 15.2.0 |
| Targets | `tests/1to32.txt` distributed with the tool (32 puzzle addresses) |
| Verification | secp256k1, SHA-256, RIPEMD-160 and Base58Check reimplemented from the specifications — no keyhunt code and no masterkey-gpu code |

---

## 2. The mechanism, in the code

Work-block acquisition, `keyhunt.cpp:2552-2568`:

```c
if(n_range_start.IsLower(&n_range_end))	{
    pthread_mutex_lock(&write_random);
    key_mpz.Set(&n_range_start);
    n_range_start.Add(N_SEQUENTIAL_MAX);
    pthread_mutex_unlock(&write_random);
}
else	{
    continue_flag = 0;
}
```

Inner loop consuming the block, `keyhunt.cpp:2501` and `keyhunt.cpp:3094`:

```c
}while(count < N_SEQUENTIAL_MAX && continue_flag);
```

Block size, `keyhunt.cpp:271`:

```c
uint64_t N_SEQUENTIAL_MAX = 0x100000000;    // 4,294,967,296 = 2^32
```

**The condition `n_range_start < n_range_end` is evaluated before the block is reserved.** Once
reserved, the block is consumed in full: the inner loop counts up to `N_SEQUENTIAL_MAX` with no
comparison against `n_range_end` at all. If a single key remains before the end of the interval,
the thread still scans 2^32 keys.

The `n_range_start` cursor advances by 2^32 at a time. For any interval smaller than that, the
first thread exhausts the cursor by itself, and the remaining threads find `n_range_start >=
n_range_end` on their first iteration — they receive `continue_flag = 0` and finish having
processed nothing.

---

## 3. Consequence A — the scan overruns the declared interval

### A.1 With `-b 20`

```bash
./keyhunt -m address -f tests/1to32.txt -b 20 -l compress -t 4
```

The tool prints the interval it will scan:

```
[+] Bit Range 20
[+] -- from : 0x80000
[+] -- to   : 0x100000
```

Declared width: **524,288 keys**.

After 120 s, still running:

```
[+] Total 623181824 keys in 120 seconds: ~5 Mkeys/s
```

**623,181,824 keys scanned — 1,188x the declared interval**, and not yet finished.

### A.2 With an explicit `-r START:END`

```bash
./keyhunt -m address -f tests/1to32.txt -r 1:1000000 -l compress -t 8
```

```
[+] -- from : 0x1
[+] -- to   : 0x1000000
```

Declared width: **16,777,215 keys**.

After 210 s, still running:

```
[+] Total 1121892352 keys in 210 seconds: ~5 Mkeys/s
```

**1,121,892,352 keys — 67x the interval**, and not yet finished.

This rules out the hypothesis that the behaviour is a peculiarity of `-b`: it occurs equally with
an explicitly given interval.

---

## 4. Consequence B — keys outside the interval are reported

In run A.2, with an interval ending at `0x1000000` (16,777,216), the output file contains:

```
Private Key: 17e2551e     =    400,708,894    (puzzle 29)
Private Key: 6ac3875      =    111,949,941    (puzzle 27)
Private Key: 340326e      =     54,538,862    (puzzle 26)
Private Key: 1fa5ee5      =     33,185,509    (puzzle 25)
```

All above the `END` the tool itself printed at startup. Nothing in the output file distinguishes
these lines from ones inside the interval.

**The keys themselves are correct.** Verified one by one with an independent implementation: 29 of
29 derive exactly the declared address, and all 29 addresses belong to the target list. Zero
discrepancies. The defect is not one of arithmetic correctness — it is one of contract.

---

## 5. Consequence C — parallelism is disabled on small intervals

Prediction derived from the mechanism, before measuring: if the first thread consumes the entire
cursor, intervals smaller than 2^32 should yield the same speed with 1 or with 8 threads.

Controlled experiment, 45 s per configuration, same machine, same binary:

| interval | width | `-t 1` | `-t 8` | gain |
|---|---|---|---|---|
| `1:1000000` | 16,777,215 | 5,502,771 keys/s | 5,322,410 keys/s | **1.0x (none)** |
| `400000000000:800000000000` | 70,368,744,177,664 | 5,340,091 keys/s | 22,901,350 keys/s | **4.3x** |

On an interval smaller than 2^32, passing 8 threads **produces no gain** — the 8-thread
measurement is even marginally slower than the 1-thread one. On an interval much larger than 2^32,
the same tool scales normally.

This confirms the mechanism via a route independent of reading the code.

---

## 6. The cost — the same scan, 378x slower

The `-n` parameter changes `N_SEQUENTIAL_MAX`. Shrinking the block, the same interval is now
scanned correctly:

```bash
./keyhunt -m address -f tests/1to32.txt -r 1:1000000 -l compress -t 8 -n 0x10000
```

| | default block (2^32) | `-n 0x10000` (65,536) |
|---|---|---|
| time to finish | ~795 s (projected) | **2.1 s (measured)** |
| active threads | 1 | 8 |
| keys scanned | 4,294,967,296 | 16,777,215 |
| keys reported | 29 | 24 |
| outside the interval | 5 | **0** |
| finishes with `End` | not observed | yes |

With the block trimmed, the tool scans exactly the requested interval, finds exactly the 24
puzzles whose keys belong to `[1, 2^24)`, prints `End` and finishes.

Independent verification of these 24: **24 of 24** derive the correct address, **24 of 24** are on
the target list, **0** outside the interval. Largest key found: `0xdc2a04` = 14,428,676, against
the 16,777,216 limit.

The 795 s of the default block is a direct projection: 2^32 keys / 5.4 Mkeys/s measured on a single
thread. The ratio against the 2.1 s measured is **378x**.

**Note on `-n`:** the tool's help text describes the parameter as
*"Check for N sequential numbers before the random chosen, this only works with -R option"*
(`keyhunt.cpp:5756`). In the tests above it was decisive in **sequential mode**, without `-R`. The
documentation and the behaviour diverge.

---

## 7. What is correct — and bounds the finding

Recorded so the scope of the criticism is clear:

- **Arithmetic correctness: intact.** 53 keys verified in total across this audit (29 + 24), every
  one deriving exactly the declared address, every one belonging to the target list. No wrong
  result, no fabricated address.
- **Coverage: complete.** Within what was actually scanned, nothing was skipped. All 24 puzzles in
  `[1, 2^24)` were found.
- **Sampling respects the start of the interval.** `rangeStart` is honoured; the problem is
  strictly at the end.
- **Default build: correct.** The distributed `Makefile`'s `-Ofast -flto` does **not** reproduce
  the miscompilation found in KeyHunt-Cuda. Tested with a known-key control (puzzle 20, `d2c55`):
  found and written with the exact address and hash160. Hypothesis raised and ruled out.
- **Parity negation is not a defect.** In vanity mode it produces keys outside the interval (49.6%
  among compressed matches, measured over 558 matches), but the keys are mathematically correct.
  In puzzle mode the negated variant never matches, by arithmetic construction: it would require
  `n - k = k0`, i.e. scanning `k approx 2^256`. Confirmed empirically: zero `ffffff` keys across
  every `-m address` run.

---

## 8. Workaround

For anyone who needs the interval to be respected, `-n` with a block sized to the interval's width
fixes all three symptoms at once — it bounds the overrun, restores parallelism, and makes the tool
finish. Practical rule: block no larger than `width / nthreads`.

This is not a fix for the defect; it is a manual adjustment of a parameter whose default value is
unsuited to any interval smaller than 2^32.

---

## 9. Limits — what was NOT proven

- **The 795 s of the default block is a projection**, not a direct measurement. It derives from
  2^32 / 5.4 Mkeys/s measured on a single thread. The default-block runs were interrupted by
  timeout before finishing.
- **Modes not exercised:** `bsgs`, `minikeys`, `xpoint`, `rmd160` and `eth`. The audit covered
  `address` and `vanity`. The block-acquisition section is shared, but that is a reading of the
  code, not an execution.
- **Behaviour under `-R` (random mode) was not measured** for interval overrun.
- **Not verified**: whether the default value of `N_SEQUENTIAL_MAX` is deliberate — it may be a
  design choice aimed at large intervals, where 2^32 is a reasonable granularity. The defect lies
  in the absence of trimming, not necessarily in the value itself.
