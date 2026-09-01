#!/usr/bin/env python3
"""sdalign.py -- is the structure inside 00000001.TMP aligned to the disc, or to the file?

secmap.py shows that the file is not uniform: it has a 480-sector region in
which 16-sector runs of high-entropy data alternate with 32-sector runs of
zeros. Those numbers are all multiples of 16, which is the DVD ECC block, so
the obvious question is whether the pattern is aligned in *absolute* disc
coordinates or merely in file coordinates. Only the first would mean the
protection knew where on the disc it was going to land.

    python tools/sdalign.py E 286        (286 = the file's start LBA, from isodev)
"""
import collections
import math
import sys

SECTOR = 2048
drive = (sys.argv[1] if len(sys.argv) > 1 else "E").rstrip(":")
start = int(sys.argv[2]) if len(sys.argv) > 2 else 286
d = open(drive + ":/00000001.TMP", "rb").read()


def ent(b):
    c = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


row = []
for s in range(len(d) // SECTOR):
    blk = d[s * SECTOR:(s + 1) * SECTOR]
    row.append("." if blk.count(0) == SECTOR else "#")

runs = []
cur, k, st = row[0], 0, 0
for i, ch in enumerate(row):
    if ch == cur:
        k += 1
    else:
        runs.append((cur, st, k))
        cur, st, k = ch, i, 1
runs.append((cur, st, k))

print("00000001.TMP starts at LBA %d and is %d sectors long" % (start, len(row)))
print()
print("%-4s %10s %10s %8s %10s %10s" %
      ("kind", "file sect", "abs LBA", "length", "LBA mod16", "len mod16"))
for c, s, k in runs:
    print("%-4s %10d %10d %8d %10d %10d"
          % (c, s, start + s, k, (start + s) % 16, k % 16))
print()
aligned = sum(1 for c, s, k in runs if (start + s) % 16 == 0)
print("runs beginning on a 16-sector boundary in ABSOLUTE disc coordinates: %d of %d"
      % (aligned, len(runs)))
aligned_f = sum(1 for c, s, k in runs if s % 16 == 0)
print("runs beginning on a 16-sector boundary in FILE coordinates          : %d of %d"
      % (aligned_f, len(runs)))
print()
print("run lengths that are multiples of 16: %d of %d"
      % (sum(1 for c, s, k in runs if k % 16 == 0), len(runs)))
print()
mid = [r for r in runs if 1 <= runs.index(r) <= len(runs) - 2]
print("the structured region: file sectors %d..%d, absolute LBA %d..%d"
      % (runs[1][1], runs[-2][1] + runs[-2][2] - 1,
         start + runs[1][1], start + runs[-2][1] + runs[-2][2] - 1))
print("  period of the alternation: %d sectors (16 data + 32 zero)" % 48)
print("  data blocks in it        : %d" % sum(1 for c, s, k in runs[1:-1] if c == "#"))
print("  total zero sectors       : %d" % sum(k for c, s, k in runs if c == "."))
