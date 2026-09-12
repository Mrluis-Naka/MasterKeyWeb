# MasterKey GPU: A Bitcoin Key Search Engine in CUDA Built from Scratch — Architecture, Validation and a ~320x Throughput Optimisation Trajectory

**Author**: Luis Felipe da Silva Martins — Computer Science, Universidade Federal da Fronteira Sul (UFFS), Chapecó Campus
**Category**: Systems engineering / high-performance GPU computing (HPC)
**Status**: engine in continuous production operation. This document consolidates the complete engineering trajectory, from the initial prototype (~7.72 M/s) to the current production state (~2.46 G/s), including two additional optimisation cycles carried out after the work's first consolidation.

---

## Abstract

We describe the from-scratch development of a GPU (CUDA) Bitcoin private-key search engine — "MasterKey GPU" — built to serve as the data-collection instrument for an independent statistical study (treated in a separate manuscript, see Section 9). Three community-established tools (Keyhunt, BitCrack, KeyHunt-Cuda) were used exclusively as **reading references** during development — never as a base to copy or fork — with every adopted technique independently re-validated before acceptance. Every mathematical layer (field arithmetic, secp256k1 elliptic-curve operations, the Hash160 pipeline, Base58Check) was validated bit-exactly against independent cryptographic oracles (GMP, libsecp256k1, FIPS 180-4 vectors) before any performance optimisation was considered. Starting from a first functionally correct version (~7.72 million candidates/s), a disciplined hypothesis→isolated implementation→real measurement sequence raised throughput to ~1.59 billion candidates/s in sequential mode (~206x), closing most of the gap against the fastest known reference of its kind (from ~4.9x initially to ~1.22-1.34x). Two further optimisation cycles, carried out after this work's initial consolidation and motivated by a comparison against a more recent community tool (CUDACyclone, ~3.17 Gkeys/s reported on the same GPU class), raised random-mode production throughput from ~1.3 to **~2.46 billion candidates/s** (+~89%): (1) elimination of one full redundant scalar multiplication per candidate in random-mode center generation, replaced by an offset table pre-computed once (isolated stage gain of ~12x, ~1.7-1.8x end-to-end throughput); (2) reorganising the center buffer from array-of-structs to struct-of-arrays, improving warp memory-access coalescing (+2.3-2.6% validated in an isolated, controlled benchmark). As an unplanned side effect, the historical performance gap between the sequential and random search modes — internally documented at ~34% — fell to ~3-4%. The entire optimisation history is reported with negative-result discipline: hypotheses tested and refuted by real measurement are documented with the same rigor as those that worked, including the tests conducted in this most recent round (binary-GCD modular inversion, a new `GROUP_SIZE` configuration sweep).

---

## 1. Introduction

### 1.1 Motivation and scope

A Bitcoin P2PKH address is derived from a 256-bit private key through elliptic-curve scalar multiplication (secp256k1), followed by a hash chain (SHA-256→RIPEMD-160, "hash160") and Base58Check encoding. Searching for private keys whose encoding matches a chosen text prefix ("vanity search") — or, more generally, whose hash output matches a known target or list of targets — is an embarrassingly parallel brute-force search problem, well suited to GPUs.

This work does not aim to contribute a new cryptographic technique; it is a **systems engineering** contribution: how to structure, validate, and optimise a search engine of this kind on a modern GPU (Ada Lovelace architecture, CUDA), documenting rigorously what worked, what did not, and why — so that the work is reproducible and the decision history is auditable.

### 1.2 Why build from scratch instead of using existing tools

Mature tools already existed (Keyhunt, BitCrack, KeyHunt-Cuda) when this project began. The decision to build a proprietary engine from scratch was motivated by three factors: (a) the need for full instrumentation and control over the sampling process for the statistical study that motivated the project (Section 9) — in particular, guaranteeing independent RNG seeds, independent verification of every match, and the ability to instrument sampling-process details (hop index, per-match timestamp) not exposed by existing tools; (b) pedagogical and quality-control value — every mathematical line validated against an independent oracle, not inherited from a third-party implementation whose correctness had not been audited by the author; (c) the opportunity, over the course of the process, to produce a genuinely reusable engineering record (this document).

The three reference tools were used under one disciplined principle, followed throughout the project: **read the actual source code to understand the technique, never copy or transcribe passages directly**. Every adopted technique was reimplemented with independent reasoning and independently re-validated.

---

## 2. Architecture

### 2.1 Pipeline overview

```
private key k (256 bits, restricted to a range of interest [2^N, 2^N+1))
      ↓  secp256k1 scalar multiplication (P = k·G)
EC point P = (x, y)
      ↓  hash160FromXCompressedFast (SHA-256 → RIPEMD-160, __byte_perm)
hash160 (20 bytes)
      ↓  match check (Bloom filter + binary search, or byte range, depending on mode)
      ↓  Base58Check encode (only on match, amortised cost)
Bitcoin address (string)
```

Three search modes share ~90% of the same kernel (the grouped "hop", Section 2.2), differing only in the final match-check function:

- **Hash160/address**: Bloom filter (cheap pre-filter) + binary search over a sorted list of target hash160 values — designed for large target-address lists.
- **XPoint**: identical, but against the raw X coordinate of the point, with no hashing at all — used when the target is already known as an EC point.
- **Vanity**: byte-range comparison (`[lo,hi]`) against the computed hash160 — no Bloom filter, suited to the small number of ranges a text prefix produces (Section 2.5 of the study manuscript).

### 2.2 The grouped "hop" mechanism — the engine's central unit of work

The engine's central unit of work is a **hop**: a kernel launch in which each of millions of threads processes a **group** of `GROUP_SIZE` consecutive candidates (production: 128), using a single center per thread and a walk of ±64 steps around it via affine point additions. The central technique that makes this efficient is **batched modular inversion** (Montgomery's trick, adopted by reading KeyHunt-Cuda): affine point addition requires one modular division (`1/Δx`) per candidate, an expensive operation; by grouping `GROUP_SIZE/2+1` divisions into a single amortised inversion (accumulate products, invert once, distribute), the per-candidate cost drops from one full inversion to a fraction of one modular multiplication. This is the same central technique used by `mkp224o` (a vanity address generator for Tor v3/ed25519 hidden services) — an independent engineering convergence on the same conditioned elliptic-curve search problem, confirmed by reading that project's source code.

The modular inversion itself uses binary GCD (safegcd-style, 62-bit divsteps), ported by reading KeyHunt-Cuda and validated 1,000,000/1,000,000 against GMP golden vectors.

### 2.3 Sequential mode vs. random mode

The engine operates in two hop-advancement modes, with structurally distinct performance implications (Section 6.3):

- **Sequential**: each hop advances the set of centers by a fixed "jump" vector (`GROUP_SIZE × numThreads × G`), pre-computed once at the start of the search. No center is ever rebuilt from scratch on any subsequent hop.
- **Random**: each hop starts from a base drawn uniformly within the search range (via `std::random_device`, an independent seed per process), covering a contiguous window of `GROUP_SIZE × numThreads` candidates per hop before drawing the next base. Historically (Section 6.3), this mode paid the cost of rebuilding **all** centers from scratch on every hop.

Random mode is the one used for the associated statistical study's data collection — every hop covers an exhaustive, contiguous window, but the *base* of each window is independently and uniformly drawn, guaranteeing unbiased coverage of the range without systematic territory repetition.

### 2.4 Fixed-bit mode and the low-bit safety margin in the walk mechanism

Beyond the three search modes of Section 2.1, the engine supports a fixed-bit mode (`--fix-bits`), used in the associated statistical study's bit-dependency probe to force chosen private-key bit positions to a fixed value while the walk searches the remaining free bits. This mode surfaced a real precondition of the walk mechanism — found through a production validation failure, not through design review, and documented here because it is exactly the constraint the study manuscript's fixed-bit section cites this document for.

Because the ±64-step walk around each `GROUP_SIZE`-candidate center advances through **elliptic-point addition on real point coordinates**, not through addition on the compact bit-string representation of the key, it does not automatically respect an arbitrary set of fixed bit positions: a step can carry across a boundary and disturb a fixed bit if that bit sits too close to bit 0 — the direction in which the ±64 excursion actually displaces the point.

**How it was found.** An early version of the multi-configuration fixed-bit kernel selected free bit positions uniformly at random across all 70 candidate positions, with no restriction. Across 30 production rounds, 3 of the resulting matches failed independent re-verification — the reconstructed address did not match the target prefix. Brute-force diagnosis against all 1,056 active configurations ruled out an indexing bug; the actual cause was that unrestricted random selection had, in those 3 cases, left one or more of bits 0-6 fixed instead of free — exactly the range the walk's carry can reach at `GROUP_SIZE=128`.

**Fix and validation.** Bit positions 0-9 (a safety margin beyond the 0-6 directly implicated) were reserved as always-free in the fixed-bit kernel; only positions at bit 10 or above are eligible to be fixed. Revalidated over 30 rounds: 1 match, 1/1 independently re-verified, zero failures.

**Consequence for the associated statistical study.** This is the origin of the "bits 10-68" (59 candidate bits) range used in that study's fixed-bit probe: the exclusion of bits 0-9 is this engineering constraint, not a statistical decision — recorded here so the citation resolves to an actual explanation rather than a pointer with nothing behind it.

---

## 3. Validation methodology

A principle followed rigorously throughout the project: **no performance optimisation is accepted before bit-exact correctness is confirmed against an independent oracle** — never against the reference tools themselves (which could also carry undiscovered bugs), but against audited, widely trusted implementations.

| Layer | Validation oracle | Coverage |
|---|---|---|
| Field arithmetic (`Int256`, 32- and 64-bit) | GMP | 1,000,000+ cases/operation, 100% parity |
| Elliptic-point operations | libsecp256k1 v0.7.1 (Bitcoin Core's curve library) | 1,000,000+ cases, including `privkey=1` and `privkey=order−1` |
| Hash160 pipeline | FIPS 180-4 vectors | Standard golden vectors |
| Base58Check | Publicly known Bitcoin puzzle addresses | Byte-by-byte re-verification |
| Binary-GCD modular inversion | GMP | 1,000,000/1,000,000 |
| GLV endomorphism (β/λ) | Independent curve arithmetic in Python (from scratch) + GPU bridge kernel | 20,000/20,000 |
| Offset-table center generation (Section 6.1) | Byte-by-byte comparison against the reference method (full scalarMult) | 4,325,376/4,325,376 identical centers |
| SoA center-buffer layout (Section 6.2) | Parity suite + 1,070,753 matches with no re-verification failure + external cryptographic verification (Python, `ecdsa` library, no code from this project) | See Section 6.2 |

Every row of the optimisation table (Section 4) was validated by this process **before** any performance measurement was accepted as a result.

---

## 4. Optimisation trajectory — first phase (correctness → ~1.59 G/s sequential)

Starting from a first functionally correct version (~7.72 million candidates/s), a disciplined hypothesis, isolated implementation, and real-measurement sequence produced the following gains:

| Optimisation | Origin | Measured gain |
|---|---|---|
| Kernel split (EC vs. hash) | Own diagnosis via `cudaEvent` | ~3.8x |
| Candidate grouping (batched modular inversion, Montgomery) | KeyHunt-Cuda, ported with independent arithmetic | ~17.6x |
| Compressed-only mode | Scope decision | ~1.66-1.83x |
| Dedicated squaring | KeyHunt-Cuda (`_ModSqr`) | +2.7% |
| Field arithmetic in native 64-bit limbs | Independent rewrite | +26.6% (largest isolated gain of this phase) |
| `__noinline__` on hash/match functions | KeyHunt-Cuda | +22.1% |
| SHA-256 message construction via `__byte_perm` | KeyHunt-Cuda, transcribed *verbatim* and independently validated | +8.9% |
| Modular inversion via binary GCD (safegcd/divstep62) | KeyHunt-Cuda | +2.05% |
| Device-side key generation and center reconstruction (random mode, 1st round) | Own diagnosis (`std::chrono`) | +38.3% and +14.5% |
| Block size (256→128 threads/block) | Occupancy calculation via `nvcc -Xptxas -v` + measurement | ~14-15% |

One methodological correction on record: the initial KeyHunt-Cuda reference figure ("~2.77 billion/s") compared against a different mode (compressed-only, versus this project's compressed+uncompressed mode at the time). Once the comparison was redone fairly (same mode/grid/target), the real gap was ~1.83x, further reduced by subsequent optimisations to ~1.22-1.34x.

### 4.1 Negative-result experiments (phase 1)

Documented with the same rigor as the ones that worked: batched modular inversion across threads (block level: 7x slower; warp level: 17x slower, counter-intuitively); manual inline PTX (7.6% slower than `nvcc`-generated `uint64_t`); GLV endomorphism applied to `scalarMult` (≈0 gain on this architecture, `scalarMult` stopped being the hot path after grouping — note: the GLV endomorphism was later successfully repurposed for a *different* goal, multiplying already-computed-point match variants rather than accelerating `scalarMult`; see `docs/roadmap.md`); splitting EC and hashing into two already-grouped kernels (nearly 2x slower, loss of coalescing); `cudaFuncCachePreferL1` (no real effect); a table of multiples of G in `__constant__` (noise, phase 1); `__launch_bounds__` forcing fewer registers (spill negated the occupancy gain); a pre-negated Y table (trading a cheap register subtraction for an extra global-memory read was a bad trade).

### 4.2 Real bugs caught by bit-exact validation

None found by visual inspection — all isolated by automated test failure: a transcription error in the 256-bit constant of the generator point `G` (100% test failure, isolated by comparison against operations using arbitrary points — occurred **twice**, independently, over the course of the project, reinforcing the policy of never transcribing 256-bit constants by hand); a structural bug in a manual PTX carry chain (incorrect interleaving of two carries through the same hardware flag); an "overscan" bug in the production range mode; a bug in the "jump" calculation between sequential batches, causing overlap instead of coverage of new territory; a fixed per-hop result buffer (`kMaxResults=256`) silently discarding matches beyond the 256th within a single hop — isolated while investigating a collection rate ~27x below the expected value for a high-frequency prefix.

---

## 5. First-phase final result

~1.59 billion candidates/s in sequential mode (~206x over the baseline) and ~1.2-1.3 billion/s per GPU in random mode, final gap ~1.22-1.34x against the fastest known reference (KeyHunt-Cuda, compressed-only mode, same grid/config).

---

## 6. Second optimisation phase — motivated by comparison with a more recent community tool

### 6.1 Context and external-reference verification

An external report (not produced by this project) pointed to a more recent community tool, **CUDACyclone**, reporting **3,170 Mkeys/s** on an RTX 4070 Ti Super — the same GPU class used in this work. Before treating that number as a target, it was verified against its primary source (the project's public repository): the value is indeed present in the tool's own benchmark table, labelled as a "community report" (a user submission, not a measurement controlled by the tool's author). A plausibility check by architectural scale was carried out: the same tool reports 6,038-6,214 Mkeys/s on an RTX 4090 (128 SMs, versus 66 SMs on the RTX 4070 Ti Super — ratio 1.939). Scaling linearly by SM count, the predicted interval (3,114-3,204 Mkeys/s) contains almost exactly the value reported for the smaller card — an internal consistency that raises confidence in the number, despite it being a single, unreplicated submission. It was also confirmed, by reading the tool's documentation, that it performs the same kind of per-candidate work (full EC point + full hash160 + comparison against a specific target address/hash, brute-force range search) — not a fundamentally cheaper algorithm (such as Kangaroo/Pollard, which would not compute hash160 per candidate).

Other figures from the same external report were checked and **did not** hold up: a "~3.24 Bkeys/s" figure attributed to an aggregate of puzzle mining pools showed, at its primary source, unresolved ambiguity over whether it represents a single GPU or the sum of multiple GPUs — discarded as an unreliable reference. This verification process is recorded here because it exemplifies the same "measure before believing" discipline applied to third-party claims, not only to internal hypotheses.

### 6.2 Diagnosing the largest remaining bottleneck

Stage-level measurement (via `cudaEvent`, without needing profiler access — Nsight Compute remained permission-blocked on every cloud instance used in this and prior work) of the random-mode hop revealed: center generation (a full `scalarMult64` per candidate) consuming **32.1%** of total hop time; the search walk + hash160 + verification consuming the remaining **67.3%**.

The cause: every random-mode hop recomputed, via full scalar multiplication (double-and-add, 256 iterations), **all** centers from scratch — even though `center[t] = (base + t·GROUP_SIZE + GROUP_SIZE/2)·G = base·G + (t·GROUP_SIZE + GROUP_SIZE/2)·G`, where the second term **does not depend on `base`** and is therefore identical on every hop.

### 6.3 Optimisation 1 — center generation via a pre-computed offset table

**Implementation**: the second term of the equation above (`offset[t]`) is pre-computed **once per process** (one full `scalarMult` pass, amortised over the entire run). On every subsequent hop, the engine computes only `base·G` (**a single** `scalarMult`, not `numThreads` of them) and adds that point against the pre-computed offset table via the same batched inversion already used in the main walk — trading `numThreads` full scalar multiplications for **one** scalar multiplication plus `numThreads` cheap affine additions.

**Correctness validation**: byte-by-byte comparison against the reference method (full scalarMult per center, the previous behaviour) — **4,325,376/4,325,376 identical centers**, on two distinct physical GPUs.

**Measured result — isolated stage**: 173.4 ms → 14.3 ms per hop (**12.1x**), reproduced on a second GPU at **9.80x**.

**Measured result — end-to-end throughput**: controlled A/B test (same instance, alternating the two paths in immediate sequence, 3 repetitions): **~1,105 → ~1,891 Mk/s (1.71x)** on a GPU with a capped power limit (180 W, with no adjustment option available in the cloud environment used). Deployed in continuous production (separate instance, 285 W uncapped): **~1,304 → ~2,322 Mk/s (~1.81x)** — the larger absolute gain on that GPU reflects the higher available power/clock ceiling, not a different optimisation.

### 6.4 Optimisation 2 — center-buffer memory layout (Array-of-Structs → Struct-of-Arrays)

**Hypothesis**: unlike the walk table (read by every thread of a warp at the *same* position on every iteration — a *broadcast* access pattern, already effectively free via L1/L2 cache), the center buffer is read and written by **each thread at its own, distinct position** on every hop. In the original layout (array-of-structs, AoS: each center occupies 64 contiguous bytes), 32 threads of a warp accessing their own centers touch 32 addresses each 64 bytes apart from its neighbour — an uncoalesced pattern. A struct-of-arrays layout (SoA: 8 separate `uint64_t` arrays, one per 64-bit limb of each coordinate) would make those same 32 threads touch 256 contiguous bytes — coalesced.

**Negative-control note**: an earlier test applying `__constant__` to the walk table (the *broadcast* pattern, not the center pattern) measured null gain (+0.4-0.5%, within thermal noise between measurements) — consistent with the hypothesis that that access was already effectively free, reinforcing that the correct target for memory-layout optimisation was the center buffer, not the table.

**Correctness validation**: production parity suite (match variants, all three independently verified) unchanged; a real smoke test against a trivially common target (`-v 1`) producing 1,070,753 matches, **zero internal re-verification failures**; one real key found via the new path, verified fully independently (Python `ecdsa` library, no code from this project) — reproduces the expected address exactly.

**Measured result — isolated, controlled benchmark** (3 repeated runs, same direction and magnitude in all of them, unlike a `GROUP_SIZE` hypothesis tested in parallel that proved noisy and non-reproducible — Section 6.5): **+2.3-2.6%**, consistent.

**Deployed in production**: real throughput measured before/after the swap, ~2,322.8 → ~2,462-2,464 Mk/s (~+6.1% in this specific measurement — larger than the isolated controlled benchmark; the likely explanation is accumulated session/thermal drift over a day of intensive testing on the same instance, not evidence that the layout alone is worth 6%. The number to trust as the layout's pure effect is the controlled benchmark's, +2.3-2.6%).

### 6.5 Hypotheses tested this round and refuted by measurement — negative-result discipline maintained

- **Optimise the modular-inversion algorithm**: the hypothesis that binary-GCD inversion, unchanged since the original port (Section 4), was a residual bottleneck left unaddressed since the migration to 64-bit arithmetic. An isolated benchmark, comparing the real inversion against a "stub" version (same chain of batched multiplications, inversion replaced by a trivial passthrough), at the production group size, showed the REAL version **consistently ~9% faster** than the STUB — a counter-intuitive result investigated in depth: the local-array access traffic that batched inversion requires (65 elements, ~4KB/thread, confirmed via `nvcc -Xptxas -v` as local-memory allocation, not register spill) already dominates the stage's time at this group size; the real inversion's extra computation, being register arithmetic with multiple independent operations, helps hide that access latency via instruction-level parallelism rather than adding visible cost. **Confirmed from a second angle**: varying the group size (`kHalf` from 4 to 64), a clean crossover appears between `kHalf`=16 and 32 — below that point, the REAL version is visibly slower (up to +81% at `kHalf`=4); above it, faster — consistent with the hypothesis that array traffic hides the inversion's cost only at sufficiently large group sizes. **Conclusion**: do not optimise the inversion algorithm — it is already effectively free of cost at the production group size.
- **`GROUP_SIZE` re-sweep**: the production choice (`GROUP_SIZE=128`) was originally set before all the recent optimisation work (64-bit arithmetic, GCD inversion, offset-table center generation, SoA layout) — the hop's cost balance has changed substantially since then, motivating a re-sweep. An initial test suggested `GROUP_SIZE=64` was ~5.2% faster; **repeated 3 times**, the result proved unstable (±10% variation between runs, including one round where `GROUP_SIZE=64` was the **worst** of all candidates tested) — while the other values (96-256) remained stable (<0.5% variation between rounds). **Conclusion**: `GROUP_SIZE=128` remains a reasonable choice; no candidate tested consistently and reproducibly beat it.

### 6.6 Unplanned side effect — near-complete closure of the sequential vs. random gap

A performance gap between the sequential and random modes, internally documented in an earlier phase of this work at **~34%** (~1.34x) and explicitly attributed, at the time it was measured, to the same root cause as Section 6.2 ("random mode always redoes a full `scalarMult64` on every hop; sequential mode never rebuilds centers, it only advances a jump" — requiring, per the record from that time, "rethinking the random mode's architecture itself" to be closed), was remedied by the Section 6.3-6.4 optimisations, without closing this specific gap being a direct goal of the work carried out.

**Controlled measurement** (3 rounds, sequential→random in immediate sequence, same instance, same target/range/batch size):

| Round | Sequential | Random | Gap |
|---|---|---|---|
| 1 | ~1,874 Mk/s | ~1,860-1,867 Mk/s | ~0.6% |
| 2 | ~1,897-1,904 Mk/s | ~1,827 Mk/s | ~3.8% |
| 3 | ~1,904-1,913 Mk/s | ~1,826 Mk/s | ~4.3% |

The gap fell from ~34% to ~3-4% — a coherent structural explanation: sequential mode never paid the cost that was eliminated (it gained nothing from the recent optimisations, having always been fast by nature); random mode was the only one paying that cost, and it was exactly the one that received the ~1.89x gain (Section 7), catching up to sequential. The remaining ~3-4% residual is consistent with the single `scalarMult` (for `base·G`) that random mode still pays per hop and sequential mode never pays — a small, expected structural difference, not an unidentified bottleneck.

---

## 7. Final performance result — current production state

| Milestone | Production throughput (random mode) |
|---|---|
| First functionally correct version | ~7.72 M/s |
| End of first optimisation phase (Section 4) | ~1.2-1.3 G/s |
| + Offset-table center generation (Section 6.3) | ~2.32 G/s |
| + SoA center-buffer layout (Section 6.4) | **~2.46 G/s** |

Total accumulated gain since the first functional version: **~320x**. Second-phase optimisation gain in isolation: **~1.89x**.

Every production binary swap was executed without data loss: a graceful interrupt signal to the prior process (native mode handler, without truncating the in-progress results file), file-integrity confirmation up to the last record, and the new binary started under the same output tag (same results file, no duplication).

---

## 8. Discussion

The pattern that emerges across the entire optimisation trajectory — both in the initial phase and in the most recent round — is that **engineering intuition does not substitute for controlled measurement**, in both directions: optimisations that seemed obvious (a table of multiples of G in constant memory, a smaller `GROUP_SIZE`, forcing fewer registers) measured null or negative; and a result that seemed counter-intuitive at first glance (the "more complete" version of a computation being faster than a simplified one, Section 6.5) proved real and reproducible on deeper investigation, with a coherent GPU-architecture explanation (local-memory latency hidden by instruction-level parallelism). The discipline of reporting negative results with the same detail as positive ones — maintained consistently from this work's first phase through its most recent — has direct practical value: it prevents future work from reinvesting effort in paths already ruled out by real measurement, and documents the complete reasoning behind every final architecture decision.

Verifying a third-party performance claim (Section 6.1) before adopting it as a target is another instance of the same discipline applied to external information, not only to internal hypotheses — a practice we believe should be standard when evaluating any independently unreplicated benchmark comparison.

The remaining gap against the most recent external reference (CUDACyclone, ~3.17 Gkeys/s vs. the current ~2.46 G/s, ~1.3x headroom) remains open. Two concrete hypotheses were tested and refuted by real measurement (Section 6.5); the kernel launch configuration used by that tool (grid/block reported as "512,1024") differs substantially from the one used in this work ("128,128" dynamic grid), suggesting a potentially different batching strategy not yet investigated. The biggest practical obstacle to further diagnosis remains the absence of real profiler access (Nsight Compute permission-blocked on every cloud instance tested) — all stage-level diagnostic work in this document was done via `cudaEvent`/`std::chrono` and controlled A/B comparison, a functional but slower and less precise approach than direct profiling.

---

## 9. Relation to the associated statistical study

This engine was built to serve as the collection instrument for an independent statistical study on the conditional uniformity of Bitcoin addresses under vanity-prefix filtering, reported in a separate manuscript. Without the engineering work described here, collection at the scale that study required — hundreds of trillions of candidates tested, tens of thousands of samples — would not have been feasible in reasonable time or cost. The study manuscript references this document as infrastructure used, without repeating implementation details.

---

## 10. Ethical considerations and dual use

This work describes, in considerable technical detail, how to close most of the performance gap against the fastest known Bitcoin private-key search tools of their kind. A high-performance search engine for the Bitcoin private-key space is dual-use technology: the same mechanism that enables data collection for research (searching within a restricted, already-delimited range, unrelated to addresses holding real balances) could, in principle, be repurposed to attempt to force keys of addresses holding real funds.

Mitigating factors: the range and prefixes used in the associated collection have no known relation to funded addresses; the declared and sole purpose of this development is to serve as a statistical-research instrument; a security audit was conducted over all cloud infrastructure used (filesystem permissions, authorised SSH keys, absence of third-party access confirmed on every instance); the source code itself is not published — a final decision, declared here explicitly rather than omitted.

This document publishes the engineering detail in full: the architecture, the validation methodology, and the complete optimisation trajectory, including every hypothesis tested and refuted. What remains withheld is the source code alone — the same distinction the associated study manuscript draws in its own data-availability section (Section 9 there): open data and open method, closed instrument.

---

## 11. Limitations

1. **Partial hardware diversity**: all optimisation and measurement work was conducted on NVIDIA GPUs of the Ada Lovelace architecture (RTX 4070 Ti / Ti Super, RTX 4080). A different architecture generation (AMD/OpenCL, or pre-Ada NVIDIA) was not tested — relevant for ruling out dependence on architecture-specific numerical or scheduler behaviour, even though the fixed-point arithmetic used should not, in principle, be sensitive to this.
2. **Absence of real profiler access** (Nsight Compute permission-blocked in every cloud environment used) forced all stage-level diagnosis to rely on manual instrumentation (`cudaEvent`, `std::chrono`) and A/B comparison — functional, but unable to isolate instruction-level causes (e.g., warp divergence, a specific cache hit rate) the way direct profiling would allow.
3. **No independent implementation replica exists**: all validation was against mathematical oracles (GMP, libsecp256k1) and cross-verification with an independent Python library for specific cases — there is no second GPU search engine, written fully independently, arriving at the same performance numbers or the same matches.
4. **Throughput measurements subject to not-fully-characterised session/thermal variation**: observed directly in Section 6.4 (production-measured gain larger than the controlled benchmark) and in Section 6.6/6.5 (variation between repeated runs of the same test). The immediate-sequence, same-instance comparison methodology mitigates but does not eliminate this effect — no single, unrepeated throughput measurement is treated as conclusive in this work.
5. **Remaining gap against the most recent external reference not fully explained** (Section 8) — two concrete hypotheses tested and refuted; a diagnostic gap remains without profiler access.

---

## 12. Future work

1. Investigate the kernel launch configuration that diverges from the external reference (Section 8) as a possible source of the remaining gap.
2. Obtain access to an environment with a working profiler (Nsight Compute) for stage-level diagnosis at a precision greater than the current manual instrumentation allows.
3. Extend the SoA layout optimisation (Section 6.4), today scoped exclusively to vanity mode without fixed bits, to the hash160/xpoint modes and to fixed-bit mode (`--fix-bits`) — not done in this round as a scope decision, not because of an identified technical limitation.
4. Replicate on a different GPU architecture generation (Limitation 1).

---

## References

Public repositories consulted as source-code reading references during development (reverse-engineering reading, never direct copying; not formal publications, no conventional bibliographic entry): KeyHunt-Cuda, BitCrack, Keyhunt (albertobsd/keyhunt), CUDACyclone (Dookoo2/CUDACyclone), mkp224o (cathugger/mkp224o).

Validation oracles: GNU Multiple Precision Arithmetic Library (GMP); libsecp256k1 v0.7.1 (Bitcoin Core); FIPS 180-4 (Secure Hash Standard); Python `ecdsa` library (independent cross-verification, no code from this project).
