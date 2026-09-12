#!/usr/bin/env python3
"""
base58check.py -- an independent Base58Check decoder, written from scratch against the
specification, with no line taken from the search engine (masterkey-gpu) or from any
third-party Base58 library. Uses only `hashlib` from the standard library (SHA-256), the same
"independent oracle" pattern already used in the project's audits.

Decodes a Bitcoin P2PKH address back to (version_byte, hash160, checksum), verifying the
checksum in the process -- sufficient for the tests in Section 3.6 of the paper (which operate
on the hash160, not on the Base58 address string itself).
"""
import hashlib

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_INDEX = {c: i for i, c in enumerate(BASE58_ALPHABET)}


def base58_decode(s):
    """Decodes a Base58 string (without checksum) to bytes, preserving leading zeros
    (each leading '1' becomes a 0x00 byte -- the same rule used by the encoder)."""
    n = 0
    for ch in s:
        n = n * 58 + _INDEX[ch]

    n_leading_ones = 0
    for ch in s:
        if ch == "1":
            n_leading_ones += 1
        else:
            break

    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n > 0 else b""
    return b"\x00" * n_leading_ones + body


def sha256d(data):
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def decode_address(address):
    """Returns (version_byte, hash160_bytes, ok_checksum). hash160_bytes is 20 bytes."""
    raw = base58_decode(address)
    if len(raw) < 25:
        raw = raw.rjust(25, b"\x00")
    payload, checksum = raw[:-4], raw[-4:]
    version = payload[0:1]
    hash160 = payload[1:21]
    ok = sha256d(payload)[:4] == checksum
    return version, hash160, ok


def self_test():
    """Structural validation: the Base58Check checksum is a 4-byte double-SHA256 over the
    payload -- it only matches by chance with probability ~1 in 4 billion, so a valid
    checksum on several distinct public addresses is strong, independent evidence that the
    whole decoder (Base58 -> bytes -> version/hash160/checksum) is correct, without relying on
    transcribing a hash160 from memory (exactly the kind of fragile mistake to avoid)."""
    known_addresses = [
        "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",  # privkey=1, public fact
        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # genesis block address, public fact
    ]
    for addr in known_addresses:
        version, hash160, ok = decode_address(addr)
        assert ok, f"invalid checksum for {addr} -- decoder is broken"
        assert version == b"\x00", f"wrong version byte for {addr}"
        assert len(hash160) == 20, f"wrong hash160 length for {addr}: {len(hash160)} bytes"
        print(f"self_test OK: {addr} -> version=00, hash160={hash160.hex()}, checksum valid")

    # Additional check: an address with a deliberately corrupted checksum (last character
    # swapped) must FAIL -- confirms the checksum check recognises a wrong payload instead of
    # just blindly accepting everything.
    corrupted = known_addresses[0][:-1] + ("A" if known_addresses[0][-1] != "A" else "B")
    _, _, ok_corrupted = decode_address(corrupted)
    assert not ok_corrupted, "decoder accepted a corrupted checksum -- serious false negative"
    print("self_test OK: address with a corrupted checksum was correctly rejected")


if __name__ == "__main__":
    self_test()
