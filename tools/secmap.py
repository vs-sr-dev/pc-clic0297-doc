#!/usr/bin/env python3
"""secmap.py -- per-sector entropy map of any file on the disc.

    python tools/secmap.py E:/00000001.TMP
    python tools/secmap.py E:/00000002.TMP --width 100

Classifies every 2048-byte sector into one of four buckets and prints the file
as a picture, then run-length encodes the picture. The buckets:

    .   all 2048 bytes are zero
    -   low entropy, under 4.0 bits/byte
    +   middle, 4.0 to 7.0
    #   high, 7.0 and above (compressed or encrypted)

Also prints, for every boundary between runs, the sector number, so that a run
length can be checked against the disc's other numbers rather than eyeballed.
"""
import argparse
import collections
import hashlib
import math
import sys

SECTOR = 2048


def ent(b):
    c = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def bucket(blk):
    if blk.count(0) == len(blk):
        return "."
    e = ent(blk)
    if e < 4.0:
        return "-"
    if e < 7.0:
        return "+"
    return "#"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--width", type=int, default=64)
    a = ap.parse_args()

    with open(a.path, "rb") as f:
        d = f.read()

    n = len(d) // SECTOR
    tail = len(d) % SECTOR
    print("%s" % a.path)
    print("  %d bytes = %d sectors%s" % (len(d), n, "" if not tail else " + %d bytes" % tail))
    print("  sha1 %s" % hashlib.sha1(d).hexdigest())
    print()

    row = [bucket(d[s * SECTOR:(s + 1) * SECTOR]) for s in range(n)]
    for i in range(0, n, a.width):
        print("  %6d  %s" % (i, "".join(row[i:i + a.width])))
    print()

    counts = collections.Counter(row)
    print("  buckets: %s" % "  ".join("%s=%d" % (k, counts[k]) for k in ".-+#" if counts[k]))

    runs = []
    cur, k = row[0], 0
    start = 0
    for i, ch in enumerate(row):
        if ch == cur:
            k += 1
        else:
            runs.append((cur, start, k))
            cur, start, k = ch, i, 1
    runs.append((cur, start, k))
    print()
    print("  runs (symbol, first sector, length):")
    for c, s, k in runs:
        print("    %s  %7d  x%d" % (c, s, k))

    print()
    print("  whole file: entropy %.4f, %d distinct byte values, %d zero bytes (%.2f %%)"
          % (ent(d), len(set(d)), d.count(0), 100.0 * d.count(0) / len(d)))


if __name__ == "__main__":
    main()
