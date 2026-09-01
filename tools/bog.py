#!/usr/bin/env python3
"""bog.py -- find SafeDisc's `BoG_` marker in any file and read the version.

`safedisc.py` (inherited from pc-harrypotter1-doc) does this job, but its list
of files to open is hard-coded to that disc's layout -- `System/HP.exe`,
`drvmgt.dll`, `secdrv.sys` -- and none of those paths exists here. Rather than
edit a tool that is correct for the disc it was written for, this one takes
paths on the command line.

The method is the one that disc arrived at and it is kept: the version is three
32-bit little-endian integers somewhere after the four signature bytes, and the
right offset is found by printing the triple at every offset from +4 to +96 and
letting agreement across files or plausibility pick it, rather than by assuming
one offset. On the previous disc the answer was +0x20 and the briefing's guess
of +4 gave 0.0.000.

    python tools/bog.py _work/zip/gof_f.exe
    python tools/bog.py _work/iso/*.exe --all-offsets
"""
import argparse
import os
import struct
import sys

MARK = b"BoG_"


def scan(path, args):
    with open(path, "rb") as f:
        d = f.read()
    hits = []
    p = d.find(MARK)
    while p >= 0:
        hits.append(p)
        p = d.find(MARK, p + 1)
    print("=" * 70)
    print("%s   %d bytes" % (path, len(d)))
    print("=" * 70)
    if not hits:
        print("  no BoG_ marker")
        return None
    print("  BoG_ found %d time(s): %s" % (len(hits), ", ".join("0x%X" % h for h in hits)))
    best = None
    for h in hits:
        print()
        print("  at offset 0x%X (%d):" % (h, h))
        for o in range(0, 64, 16):
            row = d[h + o:h + o + 16]
            print("    +%-3d %-47s  %s" % (o, " ".join("%02x" % x for x in row),
                                           "".join(chr(x) if 32 <= x < 127 else "." for x in row)))
        print("    version triple at every offset +4..+96:")
        for o in range(4, 97, 4):
            if h + o + 12 > len(d):
                break
            a, b, c = struct.unpack_from("<III", d, h + o)
            plausible = (0 < a < 32 and b < 256 and c < 100000)
            if plausible or args.all_offsets:
                print("      +0x%02X  %d.%02d.%03d      %s"
                      % (o, a, b, c, "<- plausible" if plausible else ""))
                if plausible and best is None:
                    best = (h, o, a, b, c)
    if best:
        h, o, a, b, c = best
        print()
        print("  first plausible reading: BoG_ at 0x%X, triple at +0x%02X" % (h, o))
        print("  SafeDisc version: %d.%02d.%03d" % (a, b, c))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--all-offsets", action="store_true")
    a = ap.parse_args()
    found = []
    for p in a.paths:
        r = scan(p, a)
        if r:
            found.append((p, r))
    print()
    print("=" * 70)
    print("summary")
    print("=" * 70)
    if not found:
        print("  no file carried a readable version triple")
    for p, (h, o, x, y, z) in found:
        print("  %-40s %d.%02d.%03d   (BoG_ 0x%X, +0x%02X)"
              % (os.path.basename(p), x, y, z, h, o))


if __name__ == "__main__":
    main()
