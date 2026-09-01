#!/usr/bin/env python3
"""biglang.py -- the language sets inside the BIG archives, and their holes.

Reads the listing produced by

    python tools/big.py _work/iso/0compressed.zip --all --list > notes/big-list.txt

and, for each archive, groups entries by their first path component after the
top level -- which on this disc is a language name -- then compares every
language against English name by name, so that a missing file is a measurement
rather than something noticed by eye in a long list.

    python tools/biglang.py notes/big-list.txt
"""
import collections
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "notes/big-list.txt"
cur = None
inlist = False
ents = collections.defaultdict(list)
for line in open(path, encoding="utf-8", errors="replace"):
    m = re.match(r"=== (\S+) ===", line)
    if m:
        cur, inlist = m.group(1), False
        continue
    if "every entry" in line:
        inlist = True
        continue
    if inlist:
        m = re.match(r"^\s+(\d+)\s+(\d+)\s\s(.+?)\s*$", line)
        if m:
            ents[cur].append((int(m.group(2)), m.group(3)))

for archive in sorted(ents):
    rows = ents[archive]
    groups = collections.defaultdict(list)
    for sz, nm in rows:
        p = nm.replace(chr(92), "/").split("/")
        key = p[1] if len(p) > 2 else "(top level)"
        groups[key].append((p[-1], sz))
    print("=== %s : %d entries, %d groups ===" % (archive, len(rows), len(groups)))
    for g in sorted(groups, key=lambda k: -sum(s for _, s in groups[k])):
        print("  %-22s %4d files  %14d bytes"
              % (g, len(groups[g]), sum(s for _, s in groups[g])))
    ref = "English" if "English" in groups else None
    if ref:
        base = {n.rsplit(".", 1)[0] for n, _ in groups[ref]}
        print("  compared with %s, by stem:" % ref)
        for g in sorted(groups):
            if g == ref:
                continue
            s = {n.rsplit(".", 1)[0] for n, _ in groups[g]}
            print("    %-22s missing %-58s extra %s"
                  % (g, ", ".join(sorted(base - s)) or "-",
                     ", ".join(sorted(s - base)) or "-"))
        print("  extensions per group:")
        for g in sorted(groups):
            e = collections.Counter(n.rsplit(".", 1)[-1] for n, _ in groups[g])
            print("    %-22s %s" % (g, dict(e)))
    print()
