#!/usr/bin/env python3
"""sdnumbers.py -- do the protection binaries contain the borders?

P48 predicted that drvmgt.dll or secdrv.sys would hold a hardcoded sector
address matching, to within 64 sectors, one of the borders measured with the
drive. This tests it instead of assuming it, by scanning both files -- and
System/HP.exe and the two .TMP -- for every 2- and 4-byte little-endian and
big-endian reading of every measured boundary, at every byte offset, and for a
window of +/- 64 around each.

It also checks the strings the briefing asserted, so that a claim quoted in a
document has a command behind it.

    python tools/sdnumbers.py E:/
"""
import os
import re
import struct
import sys

BORDERS = {
    "first unreadable (edges.py)": 755,
    "last unreadable (edges.py)": 10097,
    "last readable before hole": 754,
    "first readable after hole": 10098,
    "unreadable length": 9343,
    "gap start (isodev.py)": 107,
    "gap end (isodev.py)": 10106,
    "gap length": 10000,
    "00000001.TMP LBA": 106,
    "00000002.TMP LBA": 10107,
    "00000002.TMP last LBA": 10261,
    "volume size": 292173,
    "lead-out LBA": 292323,
}

FILES = ("drvmgt.dll", "secdrv.sys", "System/HP.exe", "00000001.TMP",
         "00000002.TMP")

STRINGS = (b"SECDRV", b"secdrv", b"BoG_", b"Macrovision", b"SafeDisc",
           b"C-Dilla", b"\\\\.\\", b"CdaC", b"SD_")


def occurrences(d, value, tol=0):
    """Byte offsets where `value` (or value +/- tol) appears as 2/4-byte int."""
    out = []
    for delta in range(-tol, tol + 1):
        v = value + delta
        if v < 0:
            continue
        for width in (2, 4):
            if v >= (1 << (8 * width)):
                continue
            for endian in ("little", "big"):
                pat = v.to_bytes(width, endian)
                start = 0
                while True:
                    i = d.find(pat, start)
                    if i < 0:
                        break
                    out.append((i, width, endian, v, delta))
                    start = i + 1
    return out


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "E:/"
    print("strings asserted elsewhere, checked here:")
    print()
    for rel in FILES:
        p = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.exists(p):
            continue
        d = open(p, "rb").read()
        found = []
        for s in STRINGS:
            n = d.count(s)
            if n:
                i = d.find(s)
                found.append("%r x%d (first at 0x%X)" % (s, n, i))
        print("  %-18s %8d bytes  %s"
              % (rel, len(d), "; ".join(found) if found else "(none of them)"))
    print()

    print("WHAT COUNTS AS A HIT, decided before reading the output:")
    print()
    print("  A 2-byte match is worthless. In a file of N bytes a given 16-bit")
    print("  value is expected N/65536 times by chance: 17 times in HP.exe,")
    print("  0.5 times in secdrv.sys. Every 2-byte hit below is noise and is")
    print("  printed only so that the noise is visible.")
    print()
    print("  A 4-byte match on a value ABOVE 4096 is meaningful: expected")
    print("  N/2**32 times, i.e. 0.0003 times in HP.exe. A 4-byte match on a")
    print("  value BELOW 4096 is not, because a small integer stored in four")
    print("  bytes is the commonest pattern in any binary.")
    print()
    print("  So the test is: does any protection binary contain a border")
    print("  ABOVE 4096 as a 4-byte integer?")
    print()

    meaningful = []
    for rel in FILES:
        p = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.exists(p):
            continue
        d = open(p, "rb").read()
        print("  %s (%d bytes; a 16-bit value is expected %.1f times here)"
              % (rel, len(d), len(d) / 65536.0))
        for name, v in sorted(BORDERS.items(), key=lambda kv: kv[1]):
            hits = occurrences(d, v, 0)
            four = [h for h in hits if h[1] == 4]
            two = [h for h in hits if h[1] == 2]
            if not hits:
                continue
            tag = ""
            if four and v > 4096:
                tag = "   <<< MEANINGFUL"
                meaningful.append((rel, name, v, four))
            elif four:
                tag = "   (4-byte, but the value is small: not evidence)"
            print("     %-32s value %-7d  %d x 4-byte, %d x 2-byte%s"
                  % (name, v, len(four), len(two), tag))
        print()

    print("near matches within +/- 64 sectors, 4-byte, value above 4096 only:")
    print()
    near = []
    for rel in FILES:
        p = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.exists(p):
            continue
        d = open(p, "rb").read()
        for name, v in sorted(BORDERS.items(), key=lambda kv: kv[1]):
            if v <= 4096:
                continue
            hits = [h for h in occurrences(d, v, 64) if h[1] == 4]
            if hits:
                near.append((rel, name, hits))
                print("  %-16s %-30s %d hit(s): %s"
                      % (rel, name, len(hits),
                         ", ".join("%d (%+d) at 0x%X" % (h[3], h[4], h[0])
                                   for h in hits[:4])))
    if not near:
        print("  none")
    print()

    print("=" * 68)
    print("VERDICT ON P48")
    print("=" * 68)
    print("P48 predicted that drvmgt.dll or secdrv.sys would contain a")
    print("hardcoded sector address matching a measured border to within 64")
    print("sectors.")
    print()
    dm = [m for m in meaningful if m[0] in ("drvmgt.dll", "secdrv.sys")]
    dn = [n for n in near if n[0] in ("drvmgt.dll", "secdrv.sys")]
    print("exact 4-byte hits above 4096 in the two named files : %d" % len(dm))
    for rel, name, v, four in dm:
        print("    %s  %s = %d at %s"
              % (rel, name, v, ["0x%X" % h[0] for h in four]))
    print("near 4-byte hits above 4096 in the two named files  : %d" % len(dn))
    for rel, name, hits in dn:
        print("    %s  %s: %s"
              % (rel, name,
                 ", ".join("%d (%+d) at 0x%X" % (h[3], h[4], h[0])
                           for h in hits[:4])))
    print()
    if not dm and not dn:
        print("P48 FAILS. Neither protection binary carries any measured")
        print("border as a 32-bit integer, exactly or within 64 sectors.")
    elif not dm:
        print("P48 is not confirmed exactly; only near hits, which at +/- 64")
        print("sectors sweep 129 candidate values per border and are therefore")
        print("129 times more likely by chance. Read them as weak.")
    else:
        print("P48 holds: a border is present as a 32-bit integer.")
    print()
    print("Where the borders actually are written down is the primary volume")
    print("descriptor at sector 16 -- see docs/03-two-primaries.md.")


if __name__ == "__main__":
    main()
