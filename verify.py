#!/usr/bin/env python3
"""
Independent verification of the published address/key list.

Self-contained on purpose: no third-party packages, and not a single line borrowed
from the engine that produced the data. secp256k1 point arithmetic, Base58Check and
(if the system OpenSSL hides it) RIPEMD-160 are all implemented here from the specs,
so a passing run is evidence about the data, not about a shared library.

Usage:
    python3 verify.py VANITYKEYFOUND2.txt          # verify every record
    python3 verify.py VANITYKEYFOUND2.txt 500      # verify the first 500 only
"""

import hashlib
import sys

# ----------------------------------------------------------------- secp256k1
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8


def point_add(p, q):
    if p is None:
        return q
    if q is None:
        return p
    (x1, y1), (x2, y2) = p, q
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if p == q:
        lam = (3 * x1 * x1) * pow(2 * y1, P - 2, P) % P
    else:
        lam = (y2 - y1) * pow(x2 - x1, P - 2, P) % P
    x3 = (lam * lam - x1 - x2) % P
    return (x3, (lam * (x1 - x3) - y1) % P)


def scalar_mult(k, point):
    result, addend = None, point
    while k:
        if k & 1:
            result = point_add(result, addend)
        addend = point_add(addend, addend)
        k >>= 1
    return result


# ------------------------------------------------------------- RIPEMD-160
# hashlib exposes it only when the OpenSSL legacy provider is enabled, which is off
# by default on OpenSSL 3.x. The fallback keeps this script runnable everywhere.
try:
    hashlib.new("ripemd160")

    def ripemd160(data):
        return hashlib.new("ripemd160", data).digest()

except ValueError:
    _R = [
        list(range(16)),
        [7, 4, 13, 1, 10, 6, 15, 3, 12, 0, 9, 5, 2, 14, 11, 8],
        [3, 10, 14, 4, 9, 15, 8, 1, 2, 7, 0, 6, 13, 11, 5, 12],
        [1, 9, 11, 10, 0, 8, 12, 4, 13, 3, 7, 15, 14, 5, 6, 2],
        [4, 0, 5, 9, 7, 12, 2, 10, 14, 1, 3, 8, 11, 6, 15, 13],
    ]
    _RP = [
        [5, 14, 7, 0, 9, 2, 11, 4, 13, 6, 15, 8, 1, 10, 3, 12],
        [6, 11, 3, 7, 0, 13, 5, 10, 14, 15, 8, 12, 4, 9, 1, 2],
        [15, 5, 1, 3, 7, 14, 6, 9, 11, 8, 12, 2, 10, 0, 4, 13],
        [8, 6, 4, 1, 3, 11, 15, 0, 5, 12, 2, 13, 9, 7, 10, 14],
        [12, 15, 10, 4, 1, 5, 8, 7, 6, 2, 13, 14, 0, 3, 9, 11],
    ]
    _S = [
        [11, 14, 15, 12, 5, 8, 7, 9, 11, 13, 14, 15, 6, 7, 9, 8],
        [7, 6, 8, 13, 11, 9, 7, 15, 7, 12, 15, 9, 11, 7, 13, 12],
        [11, 13, 6, 7, 14, 9, 13, 15, 14, 8, 13, 6, 5, 12, 7, 5],
        [11, 12, 14, 15, 14, 15, 9, 8, 9, 14, 5, 6, 8, 6, 5, 12],
        [9, 15, 5, 11, 6, 8, 13, 12, 5, 12, 13, 14, 11, 8, 5, 6],
    ]
    _SP = [
        [8, 9, 9, 11, 13, 15, 15, 5, 7, 7, 8, 11, 14, 14, 12, 6],
        [9, 13, 15, 7, 12, 8, 9, 11, 7, 7, 12, 7, 6, 15, 13, 11],
        [9, 7, 15, 11, 8, 6, 6, 14, 12, 13, 5, 14, 13, 13, 7, 5],
        [15, 5, 8, 11, 14, 14, 6, 14, 6, 9, 12, 9, 12, 5, 15, 8],
        [8, 5, 12, 9, 12, 5, 14, 6, 8, 13, 6, 5, 15, 13, 11, 11],
    ]
    _K = [0x00000000, 0x5A827999, 0x6ED9EBA1, 0x8F1BBCDC, 0xA953FD4E]
    _KP = [0x50A28BE6, 0x5C4DD124, 0x6D703EF3, 0x7A6D76E9, 0x00000000]

    def _f(j, x, y, z):
        if j < 16:
            return x ^ y ^ z
        if j < 32:
            return (x & y) | (~x & z)
        if j < 48:
            return (x | ~y) ^ z
        if j < 64:
            return (x & z) | (y & ~z)
        return x ^ (y | ~z)

    def _rol(v, n):
        v &= 0xFFFFFFFF
        return ((v << n) | (v >> (32 - n))) & 0xFFFFFFFF

    def ripemd160(data):
        msg = bytearray(data)
        ml = len(msg) * 8
        msg.append(0x80)
        while len(msg) % 64 != 56:
            msg.append(0)
        msg += (ml & 0xFFFFFFFFFFFFFFFF).to_bytes(8, "little")
        h = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0]
        for off in range(0, len(msg), 64):
            x = [int.from_bytes(msg[off + 4 * i: off + 4 * i + 4], "little") for i in range(16)]
            a, b, c, d, e = h
            ap, bp, cp, dp, ep = h
            for j in range(80):
                r = j // 16
                t = _rol(a + _f(j, b, c, d) + x[_R[r][j % 16]] + _K[r], _S[r][j % 16]) + e
                a, e, d, c, b = e, d, _rol(c, 10), b, t & 0xFFFFFFFF
                tp = _rol(ap + _f(79 - j, bp, cp, dp) + x[_RP[r][j % 16]] + _KP[r], _SP[r][j % 16]) + ep
                ap, ep, dp, cp, bp = ep, dp, _rol(cp, 10), bp, tp & 0xFFFFFFFF
            t = (h[1] + c + dp) & 0xFFFFFFFF
            h = [
                t,
                (h[2] + d + ep) & 0xFFFFFFFF,
                (h[3] + e + ap) & 0xFFFFFFFF,
                (h[4] + a + bp) & 0xFFFFFFFF,
                (h[0] + b + cp) & 0xFFFFFFFF,
            ]
        return b"".join(v.to_bytes(4, "little") for v in h)


# Self-test on import. Without this, a wrong RIPEMD-160 would be used consistently on both
# sides of every comparison and the script would happily report "all verified" while proving
# nothing. Vector from the RIPEMD-160 reference specification.
assert ripemd160(b"").hex() == "9c1185a5c5e9fc54612808977ee8f548b2258d31", \
    "RIPEMD-160 self-test failed -- do not trust this run"
assert ripemd160(b"abc").hex() == "8eb208f7e05d987a9b044a8e98c6b087f15a0bfc", \
    "RIPEMD-160 self-test failed -- do not trust this run"


# --------------------------------------------------------------- Base58Check
_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58check(payload):
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    num = int.from_bytes(payload + checksum, "big")
    out = ""
    while num:
        num, rem = divmod(num, 58)
        out = _ALPHABET[rem] + out
    return "1" * (len(payload + checksum) - len((payload + checksum).lstrip(b"\x00"))) + out


def address_from_key(k):
    x, y = scalar_mult(k, (GX, GY))
    pubkey = bytes([2 + (y & 1)]) + x.to_bytes(32, "big")
    return b58check(b"\x00" + ripemd160(hashlib.sha256(pubkey).digest()))


# ---------------------------------------------------------------------- main
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None

    ok = bad = 0
    lo, hi = 2 ** 70, 2 ** 71
    out_of_range = 0

    with open(path, encoding="utf-8", errors="replace") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            if limit and ok + bad >= limit:
                break
            try:
                addr, hexkey = line.split(":")
                addr, k = addr.strip(), int(hexkey.strip(), 16)
            except ValueError:
                print(f"line {lineno}: malformed, skipped")
                continue
            if not (lo <= k < hi):
                out_of_range += 1
            if address_from_key(k) == addr:
                ok += 1
            else:
                bad += 1
                print(f"line {lineno}: MISMATCH  {addr}")
            if (ok + bad) % 100 == 0:
                print(f"  {ok + bad} checked...", end="\r", flush=True)

    print(f"\nverified   : {ok}")
    print(f"mismatched : {bad}")
    print(f"outside [2^70, 2^71) : {out_of_range}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
