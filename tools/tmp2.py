#!/usr/bin/env python3
"""tmp2.py -- 00000002.TMP measured against pc-harrypotter1-doc's published
measurement of the file with the same name and the same length.

HP1 published: 317,440 bytes, Shannon entropy -0.0000 bits/byte, one distinct
byte value out of 256, 100 % zero. That is enough to reconstruct the file
exactly without having the disc: it is 317,440 zero bytes. This tool builds
that file in memory, hashes it, and compares.

    python tools/tmp2.py E

Prints the two hashes, the byte-level difference, and a per-sector map of which
sectors are zero and which are not, because "not identical" is a weaker
statement than "identical up to sector N and then not".
"""
import collections
import hashlib
import math
import sys

SECTOR = 2048
LEN = 317440


def ent(b):
    if not b:
        return 0.0
    c = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def main():
    drive = (sys.argv[1] if len(sys.argv) > 1 else "E").rstrip(":")
    path = drive + ":/00000002.TMP"
    with open(path, "rb") as f:
        d = f.read()

    print("this disc : %s" % path)
    print("  length        : %d bytes" % len(d))
    print("  sha1          : %s" % hashlib.sha1(d).hexdigest())
    print("  md5           : %s" % hashlib.md5(d).hexdigest())
    print("  entropy       : %.4f bits/byte" % ent(d))
    print("  distinct bytes: %d of 256" % len(set(d)))
    print("  zero bytes    : %d (%.2f %%)" % (d.count(0), 100.0 * d.count(0) / len(d)))

    hp1 = b"\x00" * LEN
    print()
    print("pc-harrypotter1-doc's 00000002.TMP, reconstructed from its published")
    print("measurement (317,440 bytes, entropy -0.0000, 1 distinct value, 100 % zero):")
    print("  length        : %d bytes" % len(hp1))
    print("  sha1          : %s" % hashlib.sha1(hp1).hexdigest())
    print("  md5           : %s" % hashlib.md5(hp1).hexdigest())

    print()
    print("verdict")
    print("  same length   : %s" % (len(d) == len(hp1)))
    print("  same bytes    : %s" % (d == hp1))
    if d != hp1:
        diff = sum(1 for a, b in zip(d, hp1) if a != b)
        print("  bytes differing: %d of %d (%.2f %%)" % (diff, LEN, 100.0 * diff / LEN))
        first = next(i for i, (a, b) in enumerate(zip(d, hp1)) if a != b)
        print("  first difference at offset %d (sector %d, +%d)"
              % (first, first // SECTOR, first % SECTOR))

    print()
    print("per-sector map (155 sectors, . = all zero, # = has non-zero data)")
    row = []
    zero_sectors = 0
    for s in range(len(d) // SECTOR):
        blk = d[s * SECTOR:(s + 1) * SECTOR]
        if blk.count(0) == SECTOR:
            row.append(".")
            zero_sectors += 1
        else:
            row.append("#")
    for i in range(0, len(row), 64):
        print("  %5d  %s" % (i, "".join(row[i:i + 64])))
    print("  zero sectors: %d of %d" % (zero_sectors, len(row)))

    runs = []
    cur = row[0]
    n = 0
    for ch in row:
        if ch == cur:
            n += 1
        else:
            runs.append((cur, n))
            cur, n = ch, 1
    runs.append((cur, n))
    print("  runs: %s" % " ".join("%s x%d" % (c, k) for c, k in runs))

    print()
    print("entropy of the non-zero part only")
    nz = b"".join(d[s * SECTOR:(s + 1) * SECTOR] for s in range(len(row)) if row[s] == "#")
    print("  %d bytes, entropy %.4f bits/byte, %d distinct values"
          % (len(nz), ent(nz), len(set(nz))))
    print("  zero bytes inside it: %d (%.2f %%)"
          % (nz.count(0), 100.0 * nz.count(0) / len(nz)))


if __name__ == "__main__":
    main()
