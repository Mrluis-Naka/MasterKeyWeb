#!/usr/bin/env python3
"""
section36_hash160_tests.py -- reconstructs the tests in Section 3.6 of the paper (direct
private-key -> hash160 relation) over the fully exhaustive 20-bit census (524,288 keys, no
prefix filter). Depends on `base58check.py` (own decoder, already self-tested) to extract the
hash160 of each address -- no need to recompute the elliptic curve, because the hash160 is
already encoded in the published address itself.

Usage: python section36_hash160_tests.py
"""
import math

import numpy as np
from scipy import stats

from base58check import decode_address, self_test as base58_self_test


def load_census(path="EXHAUSTIVE_CENSUS_20bit.txt"):
    keys = []
    hash160s = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if ":" not in line:
            continue
        addr, priv = line.split(":", 1)
        _, h160, ok = decode_address(addr)
        assert ok, f"invalid checksum for {addr} -- corrupted data?"
        keys.append(int(priv.strip(), 16))
        hash160s.append(h160)
    return keys, hash160s


def avalanche_test(keys, hash160s):
    """Hamming distance between hash160(k) and hash160(k+1) for CONSECUTIVE keys (the census
    is exhaustive and already sorted -- confirmed before running this).
    Published figure: mean 79.9913 bits (theoretical 80.0000), z=-0.9918, p=0.3213."""
    assert keys == sorted(keys), "census is not sorted -- test precondition violated"
    assert all(keys[i + 1] - keys[i] == 1 for i in range(len(keys) - 1)), \
        "keys are not consecutive -- test precondition violated"

    n_pairs = len(keys) - 1
    distances = np.empty(n_pairs, dtype=np.int32)
    for i in range(n_pairs):
        xor = int.from_bytes(hash160s[i], "big") ^ int.from_bytes(hash160s[i + 1], "big")
        distances[i] = bin(xor).count("1")

    mean_dist = distances.mean()
    theoretical = 80.0
    # variance of a single Hamming distance under Binomial(160, 0.5) is 160*0.25=40
    se = math.sqrt(40 / n_pairs)
    z = (mean_dist - theoretical) / se
    p_two_tailed = 2 * stats.norm.sf(abs(z))

    print("Avalanche effect between consecutive keys:")
    print(f"  n pairs: {n_pairs}")
    print(f"  observed mean distance: {mean_dist:.4f} bits (theoretical: {theoretical:.4f})")
    print(f"  z: {z:.4f}   p (two-tailed): {p_two_tailed:.4f}")
    print("  published: mean=79.9913, z=-0.9918, p=0.3213")


def collision_test(hash160s):
    """0 collisions expected among 524,288 160-bit hash160 values -- bijection confirmed."""
    n = len(hash160s)
    n_unique = len(set(hash160s))
    print(f"\nCollision check: {n} hash160 values, {n_unique} unique, "
          f"{n - n_unique} collisions (published: 0 collisions)")


def bit_correlation_test(keys, hash160s, n_variable_bits=19):
    """Bit-by-bit correlation: the key's variable bits (excluding the bit fixed by the range)
    x all 160 hash160 bits. Published: 3,040 pairs (19x160), 134 pairs with nominal p<0.05
    (expected ~152 under H0), none survives Bonferroni/FDR."""
    base = min(keys)
    n = len(keys)
    key_bits = np.zeros((n, n_variable_bits), dtype=np.uint8)
    for i, k in enumerate(keys):
        offset = k - base
        for b in range(n_variable_bits):
            key_bits[i, b] = (offset >> b) & 1

    hash_bits = np.zeros((n, 160), dtype=np.uint8)
    for i, h in enumerate(hash160s):
        val = int.from_bytes(h, "big")
        for b in range(160):
            hash_bits[i, b] = (val >> b) & 1

    n_sig = 0
    n_total = 0
    alpha = 0.05
    p_values = []
    for kb in range(n_variable_bits):
        x = key_bits[:, kb].astype(np.float64)
        for hb in range(160):
            y = hash_bits[:, hb].astype(np.float64)
            if x.std() == 0 or y.std() == 0:
                continue
            r = np.corrcoef(x, y)[0, 1]
            # correlation-significance test (Student's t approximation), df=n-2
            t = r * math.sqrt((n - 2) / (1 - r ** 2)) if abs(r) < 1 else float("inf")
            p = 2 * stats.t.sf(abs(t), df=n - 2)
            p_values.append(p)
            n_total += 1
            if p < alpha:
                n_sig += 1

    expected_by_chance = n_total * alpha
    # Bonferroni and FDR (Benjamini-Hochberg) correction
    p_values_sorted = sorted(p_values)
    bonferroni_survivors = sum(1 for p in p_values if p < alpha / n_total)
    m = len(p_values_sorted)
    fdr_survivors = 0
    for i, p in enumerate(p_values_sorted, start=1):
        if p <= (i / m) * alpha:
            fdr_survivors = i
    print(f"\nBit-by-bit correlation ({n_variable_bits} variable bits x 160 hash160 bits "
          f"= {n_total} pairs):")
    print(f"  pairs with nominal p < 0.05: {n_sig}  (expected under H0: {expected_by_chance:.0f})")
    print(f"  survivors under Bonferroni: {bonferroni_survivors}")
    print(f"  survivors under FDR (Benjamini-Hochberg): {fdr_survivors}")
    print("  published: 134 nominal pairs (expected ~152), none survives "
          "Bonferroni/FDR")


def main():
    print("=" * 90)
    print("Base58Check decoder self-test")
    print("=" * 90)
    base58_self_test()

    print()
    print("=" * 90)
    print("SECTION 3.6.2 RECONSTRUCTION -- exhaustive census, key->hash160 relation")
    print("=" * 90)
    keys, hash160s = load_census()
    print(f"loaded: {len(keys)} key/hash160 pairs")

    avalanche_test(keys, hash160s)
    collision_test(hash160s)
    bit_correlation_test(keys, hash160s)


if __name__ == "__main__":
    main()
