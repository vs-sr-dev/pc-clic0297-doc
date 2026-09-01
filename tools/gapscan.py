#!/usr/bin/env python3
"""gapscan.py -- read every unallocated sector on the disc and say what is in it.

The extent map produced by `isodev.py --extents` names 126 gaps totalling 2,096
sectors. This reads all of them off the raw device and classifies each sector:
all zero, all one byte value, low/medium/high entropy. Any gap that is not
entirely zero is dumped.

    python tools/gapscan.py E notes/isodev-extents.txt
    python tools/gapscan.py E notes/isodev-extents.txt --hex

The point is that "the gaps are empty" is a claim that costs one pass over
4.2 MB to check, and nobody should write it without checking.
"""
import argparse
import collections
import hashlib
import math
import re
import sys

SECTOR = 2048
ZERO = bytes(SECTOR)
GAP = re.compile(r"GAP of (\d+) sectors \(LBA (\d+)\.\.(\d+)\)")


def ent(b):
    c = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive")
    ap.add_argument("extents")
    ap.add_argument("--hex", action="store_true")
    a = ap.parse_args()

    gaps = []
    for line in open(a.extents, encoding="utf-8", errors="replace"):
        m = GAP.search(line)
        if m:
            gaps.append((int(m.group(2)), int(m.group(1)), int(m.group(3))))
    print("%d gaps, %d sectors total" % (len(gaps), sum(g[1] for g in gaps)))

    dev = chr(92) * 2 + "." + chr(92) + a.drive.rstrip(":") + ":"
    fh = open(dev, "rb", buffering=0)

    kinds = collections.Counter()
    nonzero = []
    sector_hashes = collections.Counter()
    total = 0
    for start, n, end in gaps:
        fh.seek(start * SECTOR)
        d = fh.read(n * SECTOR)
        if len(d) != n * SECTOR:
            print("  short read at LBA %d: %d of %d bytes" % (start, len(d), n * SECTOR))
        nz = 0
        for s in range(len(d) // SECTOR):
            blk = d[s * SECTOR:(s + 1) * SECTOR]
            total += 1
            sector_hashes[hashlib.sha1(blk).hexdigest()] += 1
            if blk == ZERO:
                kinds["zero"] += 1
            elif len(set(blk)) == 1:
                kinds["one value, not zero"] += 1
                nz += 1
            else:
                e = ent(blk)
                kinds["entropy %.0f-%.0f" % (int(e), int(e) + 1)] += 1
                nz += 1
        if nz:
            nonzero.append((start, n, nz, d))

    print()
    print("sector classification (%d sectors read):" % total)
    for k, v in kinds.most_common():
        print("  %-22s %6d  %6.2f %%" % (k, v, 100.0 * v / total))

    print()
    print("distinct sector contents among the gaps: %d" % len(sector_hashes))
    for h, c in sector_hashes.most_common(5):
        print("  %s  x%d" % (h, c))

    print()
    if not nonzero:
        print("every unallocated sector on this disc is 2048 zero bytes.")
    else:
        print("%d gaps contain at least one non-zero sector:" % len(nonzero))
        for start, n, nz, d in nonzero:
            print("  LBA %d..%d (%d sectors): %d non-zero" % (start, start + n - 1, n, nz))
            if a.hex:
                for s in range(n):
                    blk = d[s * SECTOR:(s + 1) * SECTOR]
                    if blk != ZERO:
                        print("    sector %d, first 64 bytes:" % (start + s))
                        for o in range(0, 64, 16):
                            r = blk[o:o + 16]
                            print("      %4d  %-47s  %s" % (
                                o, " ".join("%02x" % x for x in r),
                                "".join(chr(x) if 32 <= x < 127 else "." for x in r)))


if __name__ == "__main__":
    main()
