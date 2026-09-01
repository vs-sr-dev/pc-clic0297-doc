#!/usr/bin/env python3
"""gapmap.py -- what is in the 8,451 sectors that belong to no ISO file.

isodev.py accounts for the volume and finds 1,886 gaps totalling 8,451 sectors,
2.87 % of the disc. On a disc with one filesystem that number is unallocated
space. On this one it is not: the same sectors are described by a second
catalogue, and this tool asks the HFS side what each gap is.

It answers two questions that look separate and are the same question:

  * the **six large gaps**, named one at a time, sector by sector;
  * the **1,880 small ones**, against a closed form with no free parameters.

    python tools/gapmap.py
    python tools/gapmap.py --formula
    python tools/gapmap.py --big

THE CLOSED FORM, STATED BEFORE IT IS TESTED
-------------------------------------------
The HFS volume's first allocation block begins on an exact 2,048-byte boundary
and an allocation block is 10,240 bytes, i.e. exactly five sectors. So every
file the HFS volume places begins on an LBA that is a multiple of five, and a
file of `n` bytes occupies `ceil(n/2048)` sectors and is followed by however
many sectors are needed to reach the next multiple of five:

    gap_after(file) = (-ceil(size / 2048)) mod 5

That has no fitted constant in it. It is either right on every file or it is
wrong, and `--formula` reports which, with the count of files tested printed
next to the result.
"""
import argparse
import re
import sys

SECTOR = 2048
EXT_RE = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(.*?)\s*$")
GAP_RE = re.compile(r"GAP of (\d+) sectors \(LBA (\d+)\.\.(\d+)\)")


def load(path):
    """Return (extents, gaps) from an isodev.py --extents listing."""
    ext, gaps = [], []
    for line in open(path, encoding="utf-8", errors="replace"):
        g = GAP_RE.search(line)
        if g:
            n, lo, hi = (int(x) for x in g.groups())
            gaps.append({"n": n, "lo": lo, "hi": hi})
            continue
        if "[dir extent]" in line:
            m = EXT_RE.match(line.rstrip("\n"))
            if m:
                lba, s, b, sl, name = m.groups()
                ext.append({"lba": int(lba), "sectors": int(s),
                            "bytes": int(b), "name": name, "dir": True})
            continue
        m = EXT_RE.match(line.rstrip("\n"))
        if not m:
            continue
        lba, s, b, sl, name = m.groups()
        if not name or name.startswith("---"):
            continue
        ext.append({"lba": int(lba), "sectors": int(s), "bytes": int(b),
                    "name": name, "dir": False})
    return ext, gaps


def load_hfs(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        head = f.readline().rstrip("\n").split("\t")
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < len(head):
                continue
            d = dict(zip(head, p))
            rel = d["path"][d["path"].find("/") + 1:]
            d["rel"] = rel
            rows.append(d)
    return rows


def hfs_occupancy(rows, first_alloc_lba=1610, ablk_sectors=5):
    """Every sector the HFS catalogue places a fork on, as (lo, hi, what)."""
    out = []
    for d in rows:
        for tag, ln, exts in (("data", int(d["data_len"]), d["data_extents"]),
                              ("rsrc", int(d["rsrc_len"]), d["rsrc_extents"])):
            if ln == 0 or not exts:
                continue
            ab = int(exts.split(";")[0].split("+")[0])
            lo = first_alloc_lba + ab * ablk_sectors
            hi = lo + (ln + SECTOR - 1) // SECTOR - 1
            out.append((lo, hi, "%s [%s fork]" % (d["rel"], tag)))
    out.sort()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extents", default="notes/isodev-extents.txt")
    ap.add_argument("--hfs", default="notes/hfs-files.tsv")
    ap.add_argument("--big", action="store_true")
    ap.add_argument("--formula", action="store_true")
    ap.add_argument("--threshold", type=int, default=5,
                    help="a gap of more than this many sectors is a large one")
    a = ap.parse_args()

    ext, gaps = load(a.extents)
    hrows = load_hfs(a.hfs)
    occ = hfs_occupancy(hrows)

    # A fork is not the only thing an HFS volume puts on a sector. The volume
    # header, the allocation bitmap, the extents overflow file and the catalog
    # B-tree occupy 270 sectors between them, all of them inside the gap the ISO
    # side calls 572 sectors long, and leaving them out makes that gap look half
    # unexplained when it is not. The figures come from hfs.py --mdb:
    #   partition starts at byte 3,288,064 = LBA 1605.5
    #   MDB at LBA 1606, bitmap immediately after it
    #   allocation block 0 at LBA 1610, and it holds the extents overflow file
    #   catalog at allocation blocks 1..52 = LBA 1615..1874
    occ += [(1605, 1609, "HFS volume header and allocation bitmap"),
            (1610, 1614, "HFS extents overflow file (allocation block 0)"),
            (1615, 1874, "HFS catalog B-tree (allocation blocks 1..52)")]
    occ.sort()

    print("ISO extents (files and directories) : %d" % len(ext))
    print("ISO gaps                            : %d" % len(gaps))
    print("sectors in gaps                     : %d" % sum(g["n"] for g in gaps))
    print("HFS forks with a length             : %d" % len(occ))
    print()

    hist = {}
    for g in gaps:
        hist[g["n"]] = hist.get(g["n"], 0) + 1
    print("gap size histogram")
    for k in sorted(hist):
        print("  %6d sectors : %4d gaps  %8d sectors total"
              % (k, hist[k], k * hist[k]))
    print()

    big = [g for g in gaps if g["n"] > a.threshold]
    small = [g for g in gaps if g["n"] <= a.threshold]
    print("large gaps (over %d sectors) : %d, holding %d sectors"
          % (a.threshold, len(big), sum(g["n"] for g in big)))
    print("small gaps                   : %d, holding %d sectors"
          % (len(small), sum(g["n"] for g in small)))
    print()

    if a.big or True:
        print("--- the large gaps, and what the other filesystem puts there ---")
        for g in big:
            inside = [o for o in occ if o[1] >= g["lo"] and o[0] <= g["hi"]]
            covered = set()
            for lo, hi, what in inside:
                covered |= set(range(max(lo, g["lo"]), min(hi, g["hi"]) + 1))
            print()
            print("LBA %d .. %d   %d sectors" % (g["lo"], g["hi"], g["n"]))
            if not inside:
                print("    no HFS fork lands here")
            for lo, hi, what in inside:
                print("    LBA %6d .. %-6d %4d sectors  %s"
                      % (lo, hi, hi - lo + 1, what))
            print("    accounted for by the HFS catalogue: %d of %d sectors"
                  " (%.1f %%)"
                  % (len(covered), g["n"], 100.0 * len(covered) / g["n"]))

    if a.formula:
        print()
        print("--- the closed form, tested on every file ---")
        print("    gap_after(file) = (-ceil(size / 2048)) mod 5")
        print()
        files = [e for e in ext if not e["dir"]]
        files.sort(key=lambda e: e["lba"])
        gapat = {}
        for g in gaps:
            gapat[g["lo"]] = g["n"]
        hit = miss = 0
        misses = []
        for e in files:
            end = e["lba"] + e["sectors"]
            actual = gapat.get(end, 0)
            pred = (-((e["bytes"] + SECTOR - 1) // SECTOR)) % 5
            # a gap the formula does not predict may be a large gap, which is
            # a different phenomenon and is reported separately
            if actual > 5:
                continue
            if pred == actual:
                hit += 1
            else:
                miss += 1
                misses.append((e["name"], e["bytes"], e["sectors"], pred, actual))
        tot = hit + miss
        print("files tested (those not followed by a large gap) : %d" % tot)
        print("formula agrees with the disc                     : %d" % hit)
        print("formula disagrees                                : %d" % miss)
        print("agreement                                        : %.4f %%"
              % (100.0 * hit / tot if tot else 0))
        if misses:
            print()
            print("%-28s %10s %8s %6s %7s" % ("file", "bytes", "sectors",
                                              "predicted", "actual"))
            for n, b, s, p, ac in misses[:20]:
                print("%-28s %10d %8d %6d %7d" % (n, b, s, p, ac))
            if len(misses) > 20:
                print("... and %d more" % (len(misses) - 20))


if __name__ == "__main__":
    main()
