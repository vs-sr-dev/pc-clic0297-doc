#!/usr/bin/env python3
"""slack.py -- what is in the tail of the last sector of every file.

ISO 9660 allocates whole 2,048-byte sectors. A file of 4,152 bytes occupies
three sectors and leaves 1,992 bytes at the end of the third that belong to
nobody's data. What the mastering software puts there is a property of the
mastering software, and on a disc where every other question has been answered
this is the last place anything can be hiding.

Three possibilities and the tool distinguishes them:

  zero      the normal case: the builder zeroed its buffer
  repeated  a fill pattern
  other     bytes that came from somewhere -- uninitialised memory, the tail
            of the previous file, a buffer that was not cleared. Those are
            leaked bytes and they are counted and sampled.

Every extent in the ISO primary namespace is examined, including the
Associated-File records, because a resource fork has slack too.

    python tools/slack.py
    python tools/slack.py --samples 12
"""
import argparse
import os
import struct
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assoc

SECTOR = 2048


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="_work/clic11.img")
    ap.add_argument("--samples", type=int, default=8)
    a = ap.parse_args()

    img = assoc.Img(a.image)
    vd = img.sector(16)
    root = vd[156:190]
    recs = assoc.walk(img, struct.unpack("<I", root[2:6])[0],
                      struct.unpack("<I", root[10:14])[0], False)

    tot_slack = 0
    zero = 0
    other = 0
    nfiles = 0
    dirty = []
    bytefreq = Counter()
    for path, lba, ln, flags, when in recs:
        if flags & 2 or ln == 0:
            continue
        nfiles += 1
        rem = ln % SECTOR
        if rem == 0:
            continue
        pad = SECTOR - rem
        tot_slack += pad
        last = lba + ln // SECTOR
        d = img.sector(last)
        if d is None:
            continue
        tail = d[rem:]
        nz = sum(1 for b in tail if b)
        if nz == 0:
            zero += pad
        else:
            other += nz
            zero += pad - nz
            dirty.append((path, lba, ln, pad, nz, tail))
            for b in tail:
                if b:
                    bytefreq[b] += 1

    print("file records with a data extent : %d" % nfiles)
    print("slack bytes in last sectors     : %d" % tot_slack)
    print("  of which zero                 : %d   %.4f %%"
          % (zero, 100.0 * zero / max(tot_slack, 1)))
    print("  of which non-zero             : %d   %.4f %%"
          % (other, 100.0 * other / max(tot_slack, 1)))
    print("files whose slack is not all zero : %d of %d"
          % (len(dirty), nfiles))
    print()
    if dirty:
        print("%-46s %9s %8s %8s" % ("path", "bytes", "slack", "non-zero"))
        for path, lba, ln, pad, nz, tail in sorted(
                dirty, key=lambda r: -r[4])[:40]:
            print("%-46s %9d %8d %8d" % (path[-46:], ln, pad, nz))
        print()
        print("a sample of what is in the dirty slack:")
        for path, lba, ln, pad, nz, tail in sorted(
                dirty, key=lambda r: -r[4])[:a.samples]:
            txt = "".join(chr(b) if 32 <= b < 127 else "." for b in tail[:64])
            print("  %-40s %r" % (path[-40:], txt))
        print()
        print("the commonest non-zero byte values in slack:")
        for b, n in bytefreq.most_common(12):
            print("   0x%02x %-4s %8d" % (b, repr(chr(b)) if 32 <= b < 127 else "",
                                          n))


if __name__ == "__main__":
    main()
