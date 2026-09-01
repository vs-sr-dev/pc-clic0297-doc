#!/usr/bin/env python3
"""gapstruct.py -- the shape of the readable part of the unallocated hole.

LBA 107..754 is inside the ISO layout's 10,000-sector hole but the drive reads
it. It is not empty and it is not uniform: it alternates runs of all-zero
sectors with runs of high-entropy ones. This measures the alternation --
where each run starts, how long it is, what its period is, and which sector
contents repeat -- instead of describing it.

    python tools/gapstruct.py E 107 754
"""
import collections
import hashlib
import math
import sys

BS = chr(92)
SECTOR = 2048
ZERO = SECTOR * bytes([0x00])


def ent(b):
    c = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def main():
    letter = sys.argv[1]
    lo, hi = int(sys.argv[2]), int(sys.argv[3])
    path = BS + BS + "." + BS + letter.upper() + ":"
    data = {}
    with open(path, "rb") as f:
        for lba in range(lo, hi + 1):
            try:
                f.seek(lba * SECTOR)
                b = f.read(SECTOR)
                if len(b) == SECTOR:
                    data[lba] = b
            except OSError:
                pass
    lbas = sorted(data)
    print("LBA %d..%d, %d sectors read" % (lo, hi, len(lbas)))
    print()

    # run-length encode zero / non-zero
    runs = []
    cur = None
    for l in lbas:
        k = "zero" if data[l] == ZERO else "data"
        if cur and cur[0] == k and l == cur[2] + 1:
            cur[2] = l
        else:
            if cur:
                runs.append(cur)
            cur = [k, l, l]
    if cur:
        runs.append(cur)
    print("run-length structure (%d runs):" % len(runs))
    for k, a, b in runs:
        print("   %-5s LBA %5d..%-5d  %4d sectors" % (k, a, b, b - a + 1))
    print()

    starts = [a for k, a, b in runs if k == "data"]
    lens = [b - a + 1 for k, a, b in runs if k == "data"]
    zlens = [b - a + 1 for k, a, b in runs if k == "zero"]
    print("data runs   : %d, lengths %s" % (len(starts), sorted(set(lens))))
    print("zero runs   : %d, lengths %s" % (len(zlens), sorted(set(zlens))))
    if len(starts) > 1:
        d = [starts[i + 1] - starts[i] for i in range(len(starts) - 1)]
        print("data-run start deltas: %s" % sorted(set(d)))
        c = collections.Counter(d)
        print("  most common period: %s" % c.most_common(4))
    print()

    dig = {l: hashlib.sha1(data[l]).hexdigest() for l in lbas}
    cnt = collections.Counter(dig.values())
    print("distinct sector contents: %d" % len(cnt))
    print("repeated contents (excluding the all-zero sector):")
    zd = hashlib.sha1(ZERO).hexdigest()
    rep = [(d, c) for d, c in cnt.items() if c > 1 and d != zd]
    print("  %d distinct contents appear more than once" % len(rep))
    for d, c in sorted(rep, key=lambda x: -x[1])[:12]:
        where = [l for l in lbas if dig[l] == d]
        print("     x%-4d  %s  at %s%s"
              % (c, d[:16], where[:8], " ..." if len(where) > 8 else ""))
    print()

    nz = [l for l in lbas if data[l] != ZERO]
    if nz:
        es = [ent(data[l]) for l in nz]
        print("entropy of the %d non-zero sectors:" % len(nz))
        print("   min %.4f  max %.4f  mean %.4f"
              % (min(es), max(es), sum(es) / len(es)))
        print("   (8.0 = uniform; compressed or encrypted data sits above 7.8)")
        below = [(l, e) for l, e in zip(nz, es) if e < 7.5]
        print("   sectors below 7.5 bits/byte: %d %s"
              % (len(below), below[:10]))
    print()
    total_nz = len(nz)
    print("summary: of %d readable sectors in this range, %d carry data"
          % (len(lbas), total_nz))
    print("         = %d bytes of high-entropy content in a region that"
          % (total_nz * SECTOR))
    print("           no directory record claims.")


if __name__ == "__main__":
    main()
