# MasterKey

This repository serves <https://masterkeybtc.com> (`index.html`) and publishes the dataset below.

## Collected address set

249,476 Bitcoin P2PKH addresses starting with the prefix `1PWo3Je`, each published together with
the private key that generates it. Served directly at
<https://masterkeybtc.com/VANITYKEYFOUND2.txt>.

Every key was found by [MasterKey](https://masterkeybtc.com), a secp256k1 key-space search engine
written from scratch in CUDA. This repository exists so that the claim "the engine works" can be
checked rather than believed: derive each address from its key yourself and see whether the two
columns match.

---

## Why private keys are published here

These keys are worthless by construction, and that is the point.

They all live inside `[2^70, 2^71)` — the search interval of **Bitcoin puzzle #71**, a public
challenge that thousands of people have been scanning for years. The addresses in this file are
not the puzzle target; they are the incidental matches produced while sweeping that interval for
a text prefix. None of them has ever held a balance.

Publishing the keys is what makes the data verifiable. An address list alone proves nothing —
anyone can write down 249,476 strings that start with `1PWo3Je`. The key is the evidence, because
deriving the address from it is a one-way computation that either reproduces the published string
or does not.

**Do not send funds to any address in this file.** The private keys are public; anything sent
would be spendable by anyone.

---

## File format

`VANITYKEYFOUND2.txt`, one record per line:

```
1PWo3JePYN1PU8Kk1qbpfEuFvEtk5cPRgE: 66d1294250089662bc
<Base58Check address>            : <private key, hex, no leading zeros>
```

Keys are written as 18 hex digits — the natural width of a 71-bit integer. Pad to 64 digits to
get the conventional 32-byte private key.

---

## Verify it yourself

`verify.py` recomputes each address from its key and compares. It is deliberately self-contained:
no third-party packages, and not one line taken from the engine that produced the data. secp256k1
point arithmetic, Base58Check, and a RIPEMD-160 fallback (for systems where OpenSSL 3 hides it)
are implemented directly from the specifications, so a passing run says something about the data
rather than about a shared library.

```bash
python3 verify.py VANITYKEYFOUND2.txt 500     # first 500 records
python3 verify.py VANITYKEYFOUND2.txt         # all 249,476 (slow: pure Python)
```

Expected output:

```
verified   : 500
mismatched : 0
outside [2^70, 2^71) : 0
```

The script also re-derives RIPEMD-160 against the standard empty-string test vector on import,
so a broken hash implementation fails loudly instead of silently agreeing with itself.

Anything else you want to check is a shell one-liner. Confirm every key really sits inside the
puzzle interval — a 71-bit integer in hex begins with 4, 5, 6 or 7:

```bash
awk -F': ' '{print substr($2,1,1)}' VANITYKEYFOUND2.txt | sort | uniq -c
```

---

## Properties of this set

| | |
|---|---|
| Records | 249,476 |
| Unique addresses | 249,476 (no duplicates) |
| Unique private keys | 249,476 (no duplicates) |
| Key range | `[0x400000000000000000, 0x7fffffffffffffffff)` = `[2^70, 2^71)` |
| Prefix | `1PWo3Je`, all records |

Distribution of the leading hex digit, i.e. which quarter of the interval each key fell in:

```
4  62,579        6  62,215
5  62,352        7  62,330
```

Maximum deviation from an even split: 0.15%. The search draws each batch from a uniformly random
base inside the interval, and this is what that looks like from the outside.

**Address length is not constant** — 245,218 records are 34 characters and 4,258 are 33 (1.71%).
This is not an error. Base58Check maps a 25-byte payload to either 33 or 34 characters, so a
single text prefix corresponds to *two* disjoint hash160 byte ranges rather than one. Records of
the two lengths have completely unrelated leading hash160 bytes. An implementation that assumed a
single range would silently miss the 33-character family altogether.

---

## What this does and does not show

**Shows:** the engine derives correct secp256k1 public keys, correct Hash160 values and correct
Base58Check encodings, at scale, across a quarter-million independent cases — and that it samples
the declared interval without visible bias.

**Does not show:** anything about throughput (measure that yourself), and nothing about the
puzzle #71 target, which remains unsolved. Finding addresses that share a 7-character prefix with
something is not progress toward that something: at this prefix length one match occurs roughly
every 15.3 billion keys, while the interval holds 2^70 of them.

---

## Provenance

Collected in a single continuous production run on an RTX 4070 Ti SUPER at ~2,440 Mk/s, random
sampling mode, GLV endomorphism disabled so that every key stays inside the declared interval.
Every match was independently re-derived and re-checked by the engine before being written to
disk; this file is the raw output of that run, with no filtering or reordering.

Engine architecture, validation methodology and performance measurements: <https://masterkeybtc.com>

---

## Donations

`1MrLuisAQkctS18dZhXD2ak9vekzZ8A9T1`

This address is **not** part of the dataset above and its private key is not published anywhere.
The warning in the previous section applies only to the 249,476 keys in `VANITYKEYFOUND2.txt`.
