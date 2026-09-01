#!/usr/bin/env python3
"""msf.py -- convert between LBA and CD MSF, and say where the field runs out.

Written because toc.py on this disc printed a lead-out of LBA 1,151,849 on a
volume of 1,826,656 sectors, i.e. a lead-out 674,807 sectors *before* the end
of the disc, and the first thing to establish was whether that is a fact about
the disc or a fact about a one-byte field.

It has no constants belonging to any disc. Every number it prints comes from
an argument or from the definition of MSF:

    LBA = (M * 60 + S) * 75 + F - 150

and M, S, F are each one byte in the TOC that READ TOC returns, so the largest
representable address is 255:59:74.

    python tools/msf.py --max
    python tools/msf.py --lba 1826656 671664 292323
    python tools/msf.py --msf 255:59:74
"""
import argparse

PREGAP = 150
FRAMES_PER_SECOND = 75
SECONDS_PER_MINUTE = 60


def to_lba(m, s, f):
    return (m * SECONDS_PER_MINUTE + s) * FRAMES_PER_SECOND + f - PREGAP


def to_msf(lba):
    v = lba + PREGAP
    return (v // FRAMES_PER_SECOND // SECONDS_PER_MINUTE,
            v // FRAMES_PER_SECOND % SECONDS_PER_MINUTE,
            v % FRAMES_PER_SECOND)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lba", type=int, nargs="*", default=[])
    ap.add_argument("--msf", nargs="*", default=[])
    ap.add_argument("--max", action="store_true")
    a = ap.parse_args()

    if a.max or not (a.lba or a.msf):
        top = to_lba(255, 59, 74)
        print("MSF fields are one byte each in the TOC descriptor.")
        print("  largest representable MSF : 255:59:74")
        print("  that is LBA               : %d" % top)
        print("  bytes at 2048/sector      : %d" % (top * 2048))
        print()
        print("Any volume larger than %d sectors cannot have its lead-out" % top)
        print("expressed in this field, and a drive that answers anyway must")
        print("answer with something else.")
        print()

    for lba in a.lba:
        m, s, f = to_msf(lba)
        top = to_lba(255, 59, 74)
        note = "representable" if lba <= top else \
               "NOT representable: needs M=%d, field holds 255" % m
        print("LBA %10d  ->  MSF %d:%02d:%02d   %s" % (lba, m, s, f, note))
        if lba > top:
            print("            saturated value would be LBA %d, short by %d"
                  % (top, lba - top))

    for spec in a.msf:
        m, s, f = (int(x) for x in spec.replace(".", ":").split(":"))
        print("MSF %d:%02d:%02d  ->  LBA %d" % (m, s, f, to_lba(m, s, f)))


if __name__ == "__main__":
    main()
