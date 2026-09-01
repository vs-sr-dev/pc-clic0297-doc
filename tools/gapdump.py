#!/usr/bin/env python3
"""gapdump.py -- read and characterise the sectors that no file claims.

The ISO layout leaves LBA 107..10106 unallocated. The drive refuses
755..10097. The two do not coincide, so there are two readable slivers inside
the allocated hole. This reads them and says what is in them.

    python tools/gapdump.py E 107 754
    python tools/gapdump.py E 10098 10106 --hex
"""
import collections
import hashlib
import sys

BS = chr(92)
SECTOR = 2048


def main():
    letter = sys.argv[1]
    lo, hi = int(sys.argv[2]), int(sys.argv[3])
    want_hex = "--hex" in sys.argv
    path = BS + BS + "." + BS + letter.upper() + ":"

    n = hi - lo + 1
    print("reading LBA %d..%d, %d sectors, %d bytes" % (lo, hi, n, n * SECTOR))
    data = {}
    fails = []
    with open(path, "rb") as f:
        for lba in range(lo, hi + 1):
            try:
                f.seek(lba * SECTOR)
                b = f.read(SECTOR)
                if len(b) == SECTOR:
                    data[lba] = b
                else:
                    fails.append((lba, "short read %d" % len(b)))
            except OSError as e:
                fails.append((lba, "errno %s" % e.errno))
    print("read %d sectors, %d failed" % (len(data), len(fails)))
    if fails:
        print("  failures at: %s%s"
              % ([x[0] for x in fails[:10]],
                 " ..." if len(fails) > 10 else ""))
    print()

    zero = SECTOR * bytes([0x00])
    ff = SECTOR * bytes([0xFF])
    nz = [l for l, b in data.items() if b != zero]
    allff = [l for l, b in data.items() if b == ff]
    print("all-zero sectors : %d of %d" % (len(data) - len(nz), len(data)))
    print("all-0xFF sectors : %d" % len(allff))
    print("other sectors    : %d" % (len(nz) - len(allff)))
    print()

    if nz:
        interesting = [l for l in nz if l not in allff]
        print("non-trivial sectors: %s%s"
              % (interesting[:40], " ..." if len(interesting) > 40 else ""))
        print()
        digests = collections.Counter(hashlib.sha1(data[l]).hexdigest()
                                      for l in data)
        print("distinct sector contents in this range: %d" % len(digests))
        for d, c in digests.most_common(6):
            ex = [l for l in sorted(data) if hashlib.sha1(data[l]).hexdigest() == d]
            print("   %s  x%-5d  first at LBA %d" % (d[:16], c, ex[0]))
        print()
        for l in interesting[:4]:
            b = data[l]
            print("LBA %d, first 128 bytes:" % l)
            for a in range(0, 128, 16):
                ch = b[a:a + 16]
                txt = "".join(chr(c) if 32 <= c < 127 else "." for c in ch)
                print("   %4d  %-47s  %s" % (a, ch.hex(" "), txt))
            print("   entropy of the sector: %.3f bits/byte" % ent(b))
            print()
    if want_hex and data:
        for l in sorted(data):
            b = data[l]
            print("--- LBA %d ---" % l)
            for a in range(0, SECTOR, 16):
                ch = b[a:a + 16]
                txt = "".join(chr(c) if 32 <= c < 127 else "." for c in ch)
                print("   %4d  %-47s  %s" % (a, ch.hex(" "), txt))


def ent(b):
    import math
    c = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


if __name__ == "__main__":
    main()
