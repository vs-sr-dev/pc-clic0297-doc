#!/usr/bin/env python3
"""dobby.py -- the level index, and the chain checked against it.

System/Dobby.int is a localisation file for a module that is not on this disc:
there is no Dobby.u, no Dobby.dll and no Dobby.unr. What it actually contains
is a table mapping map names to numbers.

That table is a SECOND, INDEPENDENT statement of the story order, written by
the people who made the game, and it can be checked against the order
mapchain.py derived from the ChangeLevel strings in the maps themselves. Two
sources, one answer, or a disagreement worth a chapter.

It also has gaps. The numbers do not run 1..N without holes, and a hole in a
shipped index is a step of the story that is numbered and has no map.

    python tools/dobby.py E:/
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def read_dobby(p):
    out = []
    sect = None
    for line in open(p, encoding="latin-1"):
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            sect = line[1:-1]
            continue
        m = re.match(r"^n_(.+?)\s*=\s*(\d+)\s*$", line)
        if m:
            out.append((m.group(1), int(m.group(2)), sect))
    return out


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "E:/"
    p = os.path.join(root, "System", "Dobby.int")
    rows = read_dobby(p)
    maps = {f[:-4].lower(): f[:-4]
            for f in os.listdir(os.path.join(root, "Maps"))
            if f.lower().endswith(".unr")}

    print("System/Dobby.int : %d bytes, %d numbered entries"
          % (os.path.getsize(p), len(rows)))
    print()
    print("%-5s %-24s %s" % ("n", "name in Dobby.int", "a map with that name"))
    for name, n, sect in sorted(rows, key=lambda r: r[1]):
        hit = maps.get(name.lower())
        print("%-5d %-24s %s" % (n, name, hit or "*** NO SUCH MAP ***"))
    print()

    nums = sorted(n for _, n, _ in rows)
    lo, hi = nums[0], nums[-1]
    missing = [i for i in range(lo, hi + 1) if i not in set(nums)]
    print("numbers run %d..%d, %d used, %d missing" % (lo, hi, len(nums),
                                                       len(missing)))
    print("missing numbers: %s" % missing)
    print()

    named = {name.lower() for name, _, _ in rows}
    notlisted = sorted(m for m in maps if m not in named)
    print("maps on the disc that Dobby.int does NOT number: %d" % len(notlisted))
    for m in notlisted:
        print("     %s" % maps[m])
    print()

    # cross-check against the ChangeLevel chain
    chain = []
    chainfile = "notes/maps-chain.txt"
    if os.path.exists(chainfile):
        started = False
        for line in open(chainfile, encoding="utf-8", errors="replace"):
            if re.match(r"^  from Lev_Tut1: ", line):
                started = True
                continue
            if started:
                m = re.match(r"^\s+\d+\.\s+(\S+)", line)
                if m:
                    chain.append(m.group(1))
                elif line.strip() == "" and chain:
                    break
    if not chain:
        print("no chain in %s to check against; run tools/mapchain.py first."
              % chainfile)
        return

    print("cross-check: the ChangeLevel chain (%d maps) against Dobby.int"
          % len(chain))
    print()
    order = {name.lower(): n for name, n, _ in rows}
    prev = None
    ok = bad = skipped = 0
    for i, m in enumerate(chain, 1):
        n = order.get(m.lower())
        if n is None:
            print("  %2d. %-24s not in Dobby.int" % (i, m))
            skipped += 1
            continue
        flag = ""
        if prev is not None and n <= prev:
            flag = "   *** OUT OF ORDER, previous was %d ***" % prev
            bad += 1
        else:
            ok += 1
        print("  %2d. %-24s Dobby n=%-4d%s" % (i, m, n, flag))
        prev = n
    print()
    print("chain positions consistent with Dobby.int : %d" % ok)
    print("chain positions contradicting Dobby.int   : %d" % bad)
    print("chain positions Dobby.int does not cover  : %d" % skipped)
    if bad == 0:
        print()
        print("The two sources agree. The order was derived from ChangeLevel")
        print("strings inside the maps and confirmed by a numbering table in a")
        print("localisation file for a module that does not exist.")


if __name__ == "__main__":
    main()
