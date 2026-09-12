#!/usr/bin/env python3
"""
section3_chi_square_reconstruction.py -- reconstructs, from the published raw data, the
chi-square tests of Section 3 of the paper (conditional uniformity of Bitcoin addresses).

Each test is computed in TWO independent ways: (1) an in-house implementation of Pearson's
chi-square (with no library dependency) and (2) scipy.stats.chisquare / chi2_contingency, the
same validation protocol already described in Section 2.6.1 of the paper. The two must agree.

Usage: python section3_chi_square_reconstruction.py
No arguments -- file paths are fixed, relative to this script's own directory (all the data
files this script reads ship alongside it in the same repository).
"""
import math
from collections import Counter

from scipy import stats

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
assert len(BASE58_ALPHABET) == 58

DIGITS = set("123456789")
UPPER = set(c for c in BASE58_ALPHABET if c.isupper())
LOWER = set(c for c in BASE58_ALPHABET if c.islower())


def load_pairs(path):
    """Reads (address, key) pairs from a VANITYKEYFOUND*.txt-style file. Robust to two real
    variations found in the archive: (1) an instrumented format used by some instances
    ("<hop_index> <timestamp_ms> <address>: <key>", e.g. the instance-5 file) -- read from the
    last TWO whitespace-separated tokens, not from the line's first ':'; (2) trailing NUL
    bytes from disk pre-allocation (found in the instance-2 file) -- stripped before parsing."""
    pairs = []
    n_skipped = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.replace("\x00", "").strip()
            if not line or ":" not in line:
                continue
            parts = line.split()
            if len(parts) < 2:
                n_skipped += 1
                continue
            addr_tok, priv_tok = parts[-2], parts[-1]
            if not addr_tok.endswith(":"):
                n_skipped += 1
                continue
            addr = addr_tok[:-1]
            try:
                priv = int(priv_tok, 16)
            except ValueError:
                n_skipped += 1
                continue
            pairs.append((addr, priv))
    if n_skipped:
        print(f"  [warning] {path}: {n_skipped} line(s) dropped due to unexpected format")
    return pairs


def chi_square_own(observed, expected):
    """Pearson's chi-square, own implementation: sum((O-E)^2/E)."""
    return sum((o - e) ** 2 / e for o, e in zip(observed, expected))


def spatial_distribution_test(pairs, range_lo, range_hi, n_bands=20, label=""):
    """Spatial distribution: the private key's position within the range, in n_bands equal
    bands. Chi-square goodness-of-fit to uniform, df = n_bands - 1."""
    width = range_hi - range_lo
    band_width = width / n_bands
    counts = [0] * n_bands
    for _, k in pairs:
        pos = k - range_lo
        band = min(int(pos / band_width), n_bands - 1)
        counts[band] += 1

    n = len(pairs)
    expected = [n / n_bands] * n_bands

    chi2_own = chi_square_own(counts, expected)
    chi2_scipy, p_scipy = stats.chisquare(counts, f_exp=expected)
    df = n_bands - 1
    crit95 = stats.chi2.ppf(0.95, df)

    print(f"  [{label}] Spatial distribution ({n_bands} bands, n={n}):")
    print(f"    own:      chi2={chi2_own:.4f}")
    print(f"    scipy:    chi2={chi2_scipy:.4f}  p={p_scipy:.4f}")
    print(f"    95% critical (df={df}): {crit95:.2f}")
    print(f"    own-vs-scipy divergence: {abs(chi2_own - chi2_scipy):.6f}")
    return chi2_scipy, p_scipy


def character_class_test(pairs, char_position, label=""):
    """Character class at a fixed address position (digit/uppercase/lowercase). Chi-square
    against the Base58 alphabet's theoretical proportions (9/58, 24/58, 25/58), df=2."""
    counts = {"digit": 0, "upper": 0, "lower": 0}
    n_total = 0
    for addr, _ in pairs:
        if len(addr) <= char_position:
            continue
        ch = addr[char_position]
        n_total += 1
        if ch in DIGITS:
            counts["digit"] += 1
        elif ch in UPPER:
            counts["upper"] += 1
        elif ch in LOWER:
            counts["lower"] += 1
        else:
            raise ValueError(f"character outside the Base58 alphabet: {ch!r} in {addr}")

    observed = [counts["digit"], counts["upper"], counts["lower"]]
    p_theory = [len(DIGITS) / 58, len(UPPER) / 58, len(LOWER) / 58]
    expected = [n_total * p for p in p_theory]

    chi2_own = chi_square_own(observed, expected)
    chi2_scipy, p_scipy = stats.chisquare(observed, f_exp=expected)
    df = 2
    crit95 = stats.chi2.ppf(0.95, df)

    print(f"  [{label}] Character class at position {char_position} (n={n_total}):")
    print(f"    observed: digit={observed[0]} upper={observed[1]} lower={observed[2]}")
    print(f"    expected: digit={expected[0]:.1f} upper={expected[1]:.1f} lower={expected[2]:.1f}")
    print(f"    own:      chi2={chi2_own:.4f}")
    print(f"    scipy:    chi2={chi2_scipy:.4f}  p={p_scipy:.4f}")
    print(f"    95% critical (df={df}): {crit95:.2f}")
    print(f"    own-vs-scipy divergence: {abs(chi2_own - chi2_scipy):.6f}")
    return chi2_scipy, p_scipy


def full_alphabet_frequency_test(pairs, char_position, label=""):
    """Frequency of each of the 58 Base58 characters at a fixed address position. Chi-square
    goodness-of-fit to uniform (1/58 each), df=57. Used in Section 3.5 (position 2, Benford
    effect) and reusable for any other position of any dataset."""
    counts = Counter()
    n_total = 0
    for addr, _ in pairs:
        if len(addr) <= char_position:
            continue
        ch = addr[char_position]
        counts[ch] += 1
        n_total += 1

    observed = [counts.get(c, 0) for c in BASE58_ALPHABET]
    expected = [n_total / 58] * 58

    chi2_own = chi_square_own(observed, expected)
    chi2_scipy, p_scipy = stats.chisquare(observed, f_exp=expected)
    df = 57
    crit95 = stats.chi2.ppf(0.95, df)

    print(f"  [{label}] Frequency of the 58 characters at position {char_position} (n={n_total}):")
    print(f"    own:      chi2={chi2_own:.4f}")
    print(f"    scipy:    chi2={chi2_scipy:.4f}  p={p_scipy:.6f}")
    print(f"    95% critical (df={df}): {crit95:.2f}")
    print(f"    own-vs-scipy divergence: {abs(chi2_own - chi2_scipy):.6f}")
    low = "123456789"
    n_low = sum(counts.get(c, 0) for c in low)
    n_high_sample = counts.get("Z", 0)
    print(f"    scale check (Benford): sum of digits 1-9 = {n_low}, "
          f"isolated count of 'Z' = {n_high_sample}")
    return chi2_scipy, p_scipy


def block_subblock_coverage_test(pairs, hex_width=18, label=""):
    """Block/sub-block coverage: the 1st/2nd hex digit of the private key (the two MOST
    significant digits, not the last two), 64 possible categories (Section 3.2) -- the 1st
    digit can only be 4-7 (range [2^70,2^71)), the 2nd is free (0-f), 4x16=64. Reports how many
    categories are populated (the paper only states "64/64 populated", with no associated
    chi-square)."""
    counts = Counter()
    for _, k in pairs:
        hexstr = format(k, "0" + str(hex_width) + "x")
        block = hexstr[:2]
        counts[block] += 1
    n_categories_populated = len(counts)
    n = len(pairs)
    print(f"  [{label}] Block/sub-block coverage (64 possible categories, n={n}):")
    print(f"    populated categories: {n_categories_populated}/64")
    if counts:
        min_c = min(counts.values())
        max_c = max(counts.values())
        print(f"    min/max count per category: {min_c} / {max_c}")


def confirmatory_test(pairs, prefix_len, target_char, label=""):
    """Pre-registered confirmatory test (Section 3.3): frequency of a specific character at
    the position immediately after the prefix, one-tailed z-test (H1: p > 1/58)."""
    n = 0
    observed = 0
    for addr, _ in pairs:
        if len(addr) <= prefix_len:
            continue
        n += 1
        if addr[prefix_len] == target_char:
            observed += 1

    p0 = 1 / 58
    expected = n * p0
    p_hat = observed / n
    se = math.sqrt(p0 * (1 - p0) / n)
    z = (p_hat - p0) / se
    # H1: p > 1/58 (one-tailed, right) -> p-value = P(Z >= z_observed) = stats.norm.sf(z).
    # A strongly negative z (a deficit) yields a p-value close to 1 -- correct: there is no
    # evidence of an EXCESS when what is observed is a deficit.
    p_value = stats.norm.sf(z)
    relative_excess = (p_hat - p0) / p0

    print(f"  [{label}] Confirmatory test (n={n}):")
    print(f"    observed '{target_char}': {observed}")
    print(f"    expected under H0 (n/58): {expected:.2f}")
    print(f"    observed proportion: {100*p_hat:.4f}%  (H0: {100*p0:.4f}%)")
    print(f"    relative excess/deficit: {100*relative_excess:+.2f}%")
    print(f"    z: {z:.4f}")
    print(f"    p-value (one-tailed, H1: p>1/58): {p_value:.4f}")
    # cross-check via exact binomial test
    binom = stats.binomtest(observed, n, p0, alternative="greater")
    print(f"    exact binomial (cross-check): p={binom.pvalue:.4f}")
    return z, p_value


def main():
    print("=" * 90)
    print("SECTION 3.3 RECONSTRUCTION -- pre-registered confirmatory test")
    print("Confirmation set = instances 3+4+5 (17,970 addresses), guaranteed free of")
    print("contamination with the generating set (instances 1+2).")
    print("Published figures for comparison: observed '2'=267, expected=309.83,")
    print("proportion 1.4858%, excess -13.82%, z=-2.4544, p=0.9929 (H1: p>1/58)")
    print("=" * 90)
    confirmation_pairs = (load_pairs("MAIN_STUDY_INSTANCE_3.txt")
                          + load_pairs("MAIN_STUDY_INSTANCE_4.txt")
                          + load_pairs("MAIN_STUDY_INSTANCE_5.txt"))
    confirmatory_test(confirmation_pairs, prefix_len=7, target_char="2",
                      label="confirmation (inst. 3+4+5)")

    print()
    print("=" * 90)
    print("SECTION 3.2 RECONSTRUCTION -- main study (PARTIAL -- see note)")
    print("PROVENANCE NOTE: the original freeze used instance 2 at a historical cut")
    print("(15,255 addresses), not preserved separately. Here instance 2 is used in its")
    print("CURRENT state (much larger), so the numbers below do NOT reproduce the paper's")
    print("exactly -- they serve as a check that the conclusion (uniformity) holds on a")
    print("larger corpus, in the same spirit as the robustness re-analyses already present")
    print("in the paper (Sections 3.6.5 and 3.8.4).")
    print("Published figures (original frozen set, n=50,995): spatial chi2=13.88")
    print("(df=19, p=0.7906); character class at position 7, chi2=1.74 (df=2, p=0.4190)")
    print("=" * 90)
    main_study_current = (load_pairs("MAIN_STUDY_INSTANCE_1.txt")
                          + load_pairs("VANITYKEYFOUND2.txt")
                          + load_pairs("MAIN_STUDY_INSTANCE_3.txt")
                          + load_pairs("MAIN_STUDY_INSTANCE_4.txt")
                          + load_pairs("MAIN_STUDY_INSTANCE_5.txt"))
    print(f"\n  current n (5 instances, instance 2 at its current state): {len(main_study_current)}")
    spatial_distribution_test(main_study_current, 2**70, 2**71, n_bands=20,
                              label="main study (current corpus)")
    character_class_test(main_study_current, char_position=7, label="main study (current corpus)")
    block_subblock_coverage_test(main_study_current, label="main study (current corpus)")

    print()
    print("=" * 90)
    print("SECTION 3.4 RECONSTRUCTION -- three range-generalisation censuses")
    print("Published figures for comparison:")
    print("  1oeg: spatial chi2=24.12 (p=0.19)   class chi2=0.25 (p=0.88)")
    print("  1MBX: spatial chi2=17.16 (p=0.58)   class chi2=0.05")
    print("  13qZ: spatial chi2=25.71 (p=0.14)   class chi2=2.64")
    print("=" * 90)

    censuses = [
        ("VANITYKEYFOUND_1oeg42bit.txt", "1oeg", 4, 2**41, 2**42),
        ("VANITYKEYFOUND_1MBX35bit.txt", "1MBX", 4, 2**34, 2**35),
        ("VANITYKEYFOUND_13qZ35bit.txt", "13qZ", 4, 2**34, 2**35),
    ]

    for path, label, prefix_len, lo, hi in censuses:
        print(f"\n--- {label} ---")
        pairs = load_pairs(path)
        spatial_distribution_test(pairs, lo, hi, n_bands=20, label=label)
        character_class_test(pairs, prefix_len, label=label)

    print()
    print("=" * 90)
    print("SECTION 3.5 RECONSTRUCTION -- exhaustive census, encoding boundary effect")
    print("Confirmed index convention: 'position N' in the paper = string index N")
    print("(0-based), i.e. position N == addr[N]. Position 1 = the encoded body's 1st")
    print("digit (right after the mandatory '1' of the version byte, index 0).")
    print("Published figures for comparison: position 1 (~60x, the raw effect, not tested")
    print("by chi-square in the paper for being trivially extreme); position 2, chi2=469.61")
    print("(critical 75.6); positions 3-11 uniform.")
    print("=" * 90)
    exhaustive_pairs = load_pairs("EXHAUSTIVE_CENSUS_20bit.txt")
    print("\n  -- position 1 (the raw effect, for the record only -- not the cited number) --")
    full_alphabet_frequency_test(exhaustive_pairs, char_position=1, label="exhaustive 20bit, pos.1")
    print("\n  -- position 2 (the number cited in the paper: chi2=469.61) --")
    full_alphabet_frequency_test(exhaustive_pairs, char_position=2, label="exhaustive 20bit, pos.2")
    print("\n  -- positions 3-11 (should be uniform) --")
    for idx in range(3, 12):
        chi2, p = full_alphabet_frequency_test(exhaustive_pairs, char_position=idx,
                                               label=f"exhaustive 20bit, pos.{idx}")
        status = "uniform" if p > 0.05 else "NOT uniform"
        print(f"    -> {status}")


if __name__ == "__main__":
    main()
