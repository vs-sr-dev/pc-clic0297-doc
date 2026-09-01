#!/usr/bin/env python3
"""vdpayload.py -- isolate and characterise the non-zero payload that sector 16
carries and sector 17 does not.

ISO 9660 reserves PVD bytes 883..1394 for "application use" and 1395..2047 as
"reserved for future standardization". Both are zero in a normal descriptor.
On this disc one of the two primary descriptors has 344 non-zero bytes in
there. This tool measures what they look like: run structure, byte histogram,
repeated blocks at every plausible cipher block size, and whether the same
bytes occur anywhere else in the first sectors of the disc.

    python tools/vdpayload.py E
"""
import collections
import hashlib
import sys

BS = chr(92)
NUL = bytes([0x00])


def devpath(letter):
    return BS + BS + "." + BS + letter.upper() + ":"


def rd(letter, lba, n=1):
    with open(devpath(letter), "rb") as f:
        f.seek(lba * 2048)
        return f.read(2048 * n)


def runs_of_nonzero(b, base=0):
    out = []
    i = 0
    while i < len(b):
        if b[i]:
            j = i
            while j < len(b) and b[j]:
                j += 1
            out.append((base + i, base + j - 1))
            i = j
        else:
            i += 1
    return out


def repeated_blocks(b, size):
    seen = collections.Counter()
    for i in range(0, len(b) - size + 1, size):
        seen[b[i:i + size]] += 1
    return {k: v for k, v in seen.items() if v > 1 and k != NUL * size}


def entropy(b):
    if not b:
        return 0.0
    import math
    c = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def main():
    letter = sys.argv[1] if len(sys.argv) > 1 else "E"
    s16 = rd(letter, 16)
    s17 = rd(letter, 17)

    diffidx = [i for i in range(2048) if s16[i] != s17[i]]
    lo, hi = min(diffidx), max(diffidx)
    print("sector 16 vs 17 : %d differing bytes, all in [%d, %d]"
          % (len(diffidx), lo, hi))
    print("sector 17 in that span is %s"
          % ("all zero" if set(s17[lo:hi + 1]) == {0} else "NOT all zero"))
    print()
    print("ISO 9660 PVD field map for that span:")
    print("   883..1394  application use   (512 bytes, must be zero unless used)")
    print("  1395..2047  reserved          (653 bytes, must be zero)")
    print("  payload spans %d..%d, i.e. %d bytes into application use,"
          % (lo, hi, lo - 883))
    print("  and %d bytes into reserved." % max(0, hi - 1395 + 1))
    print()

    pay = s16[lo:hi + 1]
    print("payload length  : %d bytes (%d non-zero, %d zero)"
          % (len(pay), sum(1 for x in pay if x), sum(1 for x in pay if not x)))
    print("sha1            : %s" % hashlib.sha1(pay).hexdigest())
    print("shannon entropy : %.4f bits/byte (8.0 = uniform)" % entropy(pay))
    print("distinct values : %d of 256" % len(set(pay)))
    print()

    rr = runs_of_nonzero(pay, lo)
    print("non-zero runs   : %d" % len(rr))
    for a, b in rr:
        print("   %4d..%-4d  %3d bytes" % (a, b, b - a + 1))
    print()

    print("repeated blocks, by block size:")
    for size in (4, 8, 16, 24, 32):
        r = repeated_blocks(pay, size)
        if not r:
            print("  %2d bytes : none" % size)
            continue
        print("  %2d bytes : %d distinct block(s) repeat" % (size, len(r)))
        for k, v in sorted(r.items(), key=lambda kv: -kv[1]):
            print("       %s  x%d" % (k.hex(" "), v))
    print()

    # unaligned search for the repeating 8-byte block anywhere in sector 16
    for size in (8,):
        cand = collections.Counter()
        for i in range(len(pay) - size + 1):
            cand[pay[i:i + size]] += 1
        best = [(k, v) for k, v in cand.items() if v > 1 and k != NUL * size]
        print("unaligned %d-byte repeats inside the payload: %d"
              % (size, len(best)))
        for k, v in sorted(best, key=lambda kv: -kv[1])[:10]:
            offs = [lo + i for i in range(len(pay) - size + 1)
                    if pay[i:i + size] == k]
            print("   %s  x%d at offsets %s" % (k.hex(" "), v, offs))
    print()

    print("does the payload occur elsewhere in sectors 0..31?")
    head = rd(letter, 0, 32)
    # runs_of_nonzero is called with base 0 here so the indices returned are
    # into `pay` itself. Calling it with base `lo` and then subtracting `lo`
    # is the same thing done twice and yields an empty needle, which then
    # matches at every offset -- that bug is why this comment exists.
    needle = max(runs_of_nonzero(pay), key=lambda r: r[1] - r[0])
    n = pay[needle[0]:needle[1] + 1]
    hits = []
    start = 0
    while True:
        k = head.find(n, start)
        if k < 0:
            break
        hits.append(k)
        start = k + 1
    print("  longest run (%d bytes) found at %d byte offset(s)%s"
          % (len(n), len(hits),
             (": " + str(hits[:8]) + (" ..." if len(hits) > 8 else ""))
             if hits else " -- nowhere but sector 16"))
    print("  (sector 16 begins at byte offset %d)" % (16 * 2048))
    print()

    with open("_work/vd16_payload.bin", "wb") as f:
        f.write(pay)
    print("payload written to _work/vd16_payload.bin")

    print()
    print("for reference, sector 16 bytes 883..1138 (the quiet part of the")
    print("application-use field, before the payload starts):")
    quiet = s16[883:lo]
    print("  %d bytes, %s" % (len(quiet),
                              "all zero" if set(quiet) == {0} else "NOT zero"))


if __name__ == "__main__":
    main()
