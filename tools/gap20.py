#!/usr/bin/env python3
"""gap20.py -- what decides where the seventy-nine twenty-sector gaps go.

Reads the LBA-ordered extent map produced by

    python tools/isodev.py E --extents > notes/isodev-extents.txt

and, for every gap, prints the entry before it, the entry after it, the
directory both belong to, and the position of the following entry inside the
LBA-ordered list. Then tests four hypotheses in turn:

    1. the gaps are ECC-block aligned (start or end on a multiple of 16);
    2. the gaps are evenly spaced in LBA;
    3. the gaps are evenly spaced in *entry count* -- one every N entries;
    4. the gaps fall on directory boundaries.

    python tools/gap20.py notes/isodev-extents.txt
    python tools/gap20.py notes/isodev-extents.txt --size 20
"""
import argparse
import collections
import re
import sys

ENTRY = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(.*?)\s*$")
GAP = re.compile(r"GAP of (\d+) sectors \(LBA (\d+)\.\.(\d+)\)")


def parse(path):
    rows = []
    for line in open(path, encoding="utf-8", errors="replace"):
        g = GAP.search(line)
        if g:
            rows.append(("gap", int(g.group(2)), int(g.group(1)), int(g.group(3)), ""))
            continue
        if "[dir extent]" in line or re.match(r"^\s*\d+\s+\d+\s+\d+\s+\d+\s+\S", line):
            m = ENTRY.match(line)
            if m:
                rows.append(("file", int(m.group(1)), int(m.group(2)),
                             int(m.group(1)) + int(m.group(2)) - 1, m.group(5)))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--size", type=int, default=20)
    a = ap.parse_args()

    rows = parse(a.path)
    files = [r for r in rows if r[0] == "file"]
    print("parsed %d rows: %d entries, %d gaps"
          % (len(rows), len(files), len(rows) - len(files)))

    hist = collections.Counter(r[2] for r in rows if r[0] == "gap")
    print("gap histogram: %s" % sorted(hist.items(), key=lambda kv: -kv[1]))
    print()

    # index of each entry in the LBA-ordered list of entries
    idx = {}
    n = 0
    order = []
    for r in rows:
        if r[0] == "file":
            idx[r[1]] = n
            order.append(r)
            n += 1
        else:
            order.append(r)

    sel = [(i, r) for i, r in enumerate(order) if r[0] == "gap" and r[2] == a.size]
    print("=== the %d gaps of %d sectors, in context ===" % (len(sel), a.size))
    print()
    print("%9s %9s  %4s  %s" % ("gapLBA", "next", "#ent", "before  ->  after"))
    entry_positions = []
    for i, r in sel:
        before = None
        for j in range(i - 1, -1, -1):
            if order[j][0] == "file":
                before = order[j]
                break
        after = None
        for j in range(i + 1, len(order)):
            if order[j][0] == "file":
                after = order[j]
                break
        pos = idx.get(after[1]) if after else None
        entry_positions.append(pos)
        print("%9d %9d  %4s  %s  ->  %s"
              % (r[1], r[3] + 1, pos,
                 (before[4] if before else "-")[-42:],
                 (after[4] if after else "-")[-42:]))

    print()
    print("=== hypothesis 1: ECC-block (16-sector) alignment ===")
    for label, vals in (("gap start", [r[1] for _, r in sel]),
                        ("gap end+1", [r[3] + 1 for _, r in sel])):
        c = collections.Counter(v % 16 for v in vals)
        print("  %s mod 16: %s" % (label, sorted(c.items())))

    print()
    print("=== hypothesis 2: even spacing in LBA ===")
    starts = [r[1] for _, r in sel]
    d = [b - a2 for a2, b in zip(starts, starts[1:])]
    print("  first 20 deltas: %s" % d[:20])
    print("  min %d  max %d  distinct %d" % (min(d), max(d), len(set(d))))

    print()
    print("=== hypothesis 3: even spacing in entry count ===")
    d2 = [b - a2 for a2, b in zip(entry_positions, entry_positions[1:])]
    c2 = collections.Counter(d2)
    print("  deltas in entries: %s" % sorted(c2.items(), key=lambda kv: -kv[1])[:12])
    print("  first entry index with a gap before it: %s" % entry_positions[0])
    print("  all entry indices: %s" % entry_positions)

    print()
    print("=== hypothesis 4: directory boundaries ===")
    ndir = sum(1 for _, r in sel
               if "[dir extent]" in (r[4] or ""))
    print("  gaps immediately followed by a directory extent: %d" % ndir)


if __name__ == "__main__":
    main()
