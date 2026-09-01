#!/usr/bin/env python3
"""protscan.py -- the negative, published with the number of files behind it.

Six inherited tools in this collection look for copy protection, and every one
of them has its own subject's file layout compiled in: `safedisc.py` opens
`System/HP.exe`, `securom.py` looks for a section name it was told about.
None of those paths exists here, so they all print nothing, and "nothing" from
a tool that opened no files is not a measurement.

This opens every executable image on both sides of the disc and looks for the
literal markers each scheme leaves. It prints the count of files searched next
to the count of hits, so a zero is a zero *out of something*.

A cover disc from 1997 exists to be copied, so the expected answer is zero and
the point of running it is to be able to say zero with a denominator.

    python tools/protscan.py _work/iso _work/hfs
"""
import argparse
import os

MARKERS = [
    (b"BoG_", "SafeDisc, the BoG_ stub marker"),
    (b"SafeDisc", "SafeDisc, the product name in clear"),
    (b"SECUROM", "SecuROM, upper case"),
    (b"securom", "SecuROM, lower case"),
    (b"CMS16.DLL", "SecuROM support library"),
    (b"LaserLok", "LaserLok"),
    (b"CDCOPS", "CD-Cops"),
    (b"StarForce", "StarForce"),
    (b"TAGES", "Tages"),
    (b"SETTEC", "Alpha-ROM"),
    (b"Macrovision", "Macrovision, the vendor of SafeDisc"),
    # a positive control: four zero bytes are in almost every binary, so a low
    # number on this row would mean the search is broken, not that the disc is
    # clean.
    (b"\x00\x00\x00\x00", "POSITIVE CONTROL: four zero bytes"),
]

EXTS = (".exe", ".dll", ".x32", ".x16", ".qtc", ".drv", ".ocx", ".cpl",
        ".386", ".vxd", ".scr", ".sys")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--all-files", action="store_true",
                    help="search every file, not just executable images")
    a = ap.parse_args()

    paths = []
    for root in a.roots:
        for dp, dn, fn in os.walk(root):
            for f in fn:
                p = os.path.join(dp, f)
                if a.all_files or f.lower().endswith(EXTS):
                    paths.append(p)
                elif os.path.getsize(p) >= 2:
                    with open(p, "rb") as fh:
                        if fh.read(2) == b"MZ":
                            paths.append(p)
    paths.sort()

    counts = {m: [] for m, _ in MARKERS if m}
    for p in paths:
        with open(p, "rb") as fh:
            d = fh.read()
        for m, _ in MARKERS:
            if m and m in d:
                counts[m].append(p)

    print("roots            : %s" % ", ".join(a.roots))
    print("files searched   : %d" % len(paths))
    print("bytes searched   : %d" % sum(os.path.getsize(p) for p in paths))
    print()
    print("%-14s %-42s %6s" % ("marker", "scheme", "hits"))
    for m, label in MARKERS:
        if not m:
            continue
        print("%-14s %-42s %6d"
              % (m.decode("latin-1", "replace")[:14], label, len(counts[m])))
        for p in counts[m][:10]:
            print("                 %s" % p)
    print()
    total = sum(len(v) for v in counts.values())
    print("total hits across every marker : %d" % total)


if __name__ == "__main__":
    main()
