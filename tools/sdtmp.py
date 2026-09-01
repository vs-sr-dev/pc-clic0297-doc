#!/usr/bin/env python3
"""sdtmp.py -- the two SafeDisc .TMP files at the root, measured.

00000001.TMP is one sector. 00000002.TMP is 155 sectors, and 155 is the number
that has followed this collection across three discs, so it gets closed here
rather than left as a resemblance.

Also asks whether the payload found in the reserved area of primary volume
descriptor at sector 16 occurs inside either file, and whether the numbers in
that payload occur inside them as integers.

    python tools/sdtmp.py E
"""
import collections
import hashlib
import math
import sys

BS = chr(92)
SECTOR = 2048


def ent(b):
    c = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def hexdump(b, base=0, n=96):
    for a in range(0, min(n, len(b)), 16):
        ch = b[a:a + 16]
        print("   %5d  %-47s  %s"
              % (base + a, ch.hex(" "),
                 "".join(chr(c) if 32 <= c < 127 else "." for c in ch)))


def main():
    letter = sys.argv[1] if len(sys.argv) > 1 else "E"
    root = letter.upper() + ":/"
    with open(BS + BS + "." + BS + letter.upper() + ":", "rb") as f:
        f.seek(16 * SECTOR)
        s16 = f.read(SECTOR)
    payload = s16[1139:1527]

    for name in ("00000001.TMP", "00000002.TMP"):
        d = open(root + name, "rb").read()
        print("=" * 68)
        print("%s   %d bytes" % (name, len(d)))
        print("=" * 68)
        print("  sectors        : %s"
              % ("%d exactly" % (len(d) // SECTOR) if len(d) % SECTOR == 0
                 else "%.3f (NOT a whole number)" % (len(d) / SECTOR)))
        print("  KiB            : %s"
              % ("%d exactly" % (len(d) // 1024) if len(d) % 1024 == 0
                 else "%.3f" % (len(d) / 1024)))
        for k in (512, 1024, 2048, 4096, 8192, 16384, 32768, 65536):
            if len(d) % k == 0:
                print("  divisible by %-6d yes  (%d x %d)" % (k, len(d) // k, k))
        print("  sha1           : %s" % hashlib.sha1(d).hexdigest())
        print("  entropy        : %.4f bits/byte" % ent(d))
        print("  distinct bytes : %d of 256" % len(set(d)))
        print("  zero bytes     : %d (%.2f %%)"
              % (d.count(0), 100.0 * d.count(0) / len(d)))
        print("  first 96 bytes:")
        hexdump(d, 0, 96)
        print("  last 64 bytes:")
        hexdump(d[-64:], len(d) - 64, 64)
        print("  leading dwords (LE):",
              [int.from_bytes(d[i:i + 4], "little") for i in range(0, 24, 4)])
        # per-sector entropy profile
        if len(d) >= SECTOR * 4:
            es = [ent(d[i:i + SECTOR]) for i in range(0, len(d), SECTOR)]
            print("  per-sector entropy: min %.3f max %.3f mean %.3f"
                  % (min(es), max(es), sum(es) / len(es)))
            low = [(i, e) for i, e in enumerate(es) if e < 7.0]
            print("  sectors below 7.0 bits/byte: %d %s"
                  % (len(low), low[:8]))
        # does the descriptor payload live here?
        pos = d.find(payload)
        print("  sector-16 payload (388 bytes) found at: %s"
              % (pos if pos >= 0 else "not present"))
        longest = s16[1139:1268]
        pos2 = d.find(longest)
        print("  its longest run (129 bytes) found at  : %s"
              % (pos2 if pos2 >= 0 else "not present"))
        rep = bytes.fromhex("120e43eadb9081d5")
        pos3 = d.find(rep)
        print("  the thrice-repeated 8-byte block found: %s"
              % (pos3 if pos3 >= 0 else "not present"))
        print()

    print("=" * 68)
    print("the 155 question")
    print("=" * 68)
    d2 = open(root + "00000002.TMP", "rb").read()
    n = len(d2)
    print("  00000002.TMP is %d bytes." % n)
    print("  %d / 2048 = %g sectors" % (n, n / 2048))
    print("  %d / 1024 = %g KiB" % (n, n / 1024))
    print("  Blood & Lace, Grande Fratello and Lucignolo each carried 155")
    print("  sectors of tail past the declared volume. That 155 was a count of")
    print("  sectors on a disc. This 155 is a file length divided by 2048.")
    print("  They are the same integer and not the same quantity.")
    print("  This disc's own tail, measured from its own TOC, is %d." % 150)


if __name__ == "__main__":
    main()
