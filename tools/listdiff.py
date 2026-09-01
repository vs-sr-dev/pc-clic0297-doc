#!/usr/bin/env python3
"""listdiff.py -- compare two published hash lists, file for file.

discdiff.py needs both trees on disk. This needs only the *lists*, which is
the point of publishing them: pc-harrypotter4-doc/notes/sha1-all.txt is 1,659
lines of "sha1  size  path" and this disc's list is the same shape, so the
comparison costs no drive time at all.

A line is "<hex>  <size>  <path>"; anything that does not parse that way
(headers, blank lines) is counted and skipped, and the count is printed, so a
list with a prose preamble does not silently shrink the comparison.

    python tools/listdiff.py notes/sha1-all.txt ../pc-harrypotter4-doc/notes/sha1-all.txt
    python tools/listdiff.py A B --by-name
"""
import argparse
import re

LINE = re.compile(r"^([0-9a-fA-F]{32,64})\s+(\d+)\s+(.*\S)\s*$")


def load(path):
    rows, skipped = [], 0
    for line in open(path, encoding="utf-8", errors="replace"):
        m = LINE.match(line)
        if m:
            rows.append((m.group(1).lower(), int(m.group(2)), m.group(3)))
        elif line.strip():
            skipped += 1
    return rows, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--by-name", action="store_true")
    a = ap.parse_args()

    ra, sa = load(a.a)
    rb, sb = load(a.b)
    print("A %s : %d files, %d bytes, %d distinct hashes (%d lines skipped)"
          % (a.a, len(ra), sum(r[1] for r in ra), len({r[0] for r in ra}), sa))
    print("B %s : %d files, %d bytes, %d distinct hashes (%d lines skipped)"
          % (a.b, len(rb), sum(r[1] for r in rb), len({r[0] for r in rb}), sb))
    print("comparing %d files against %d files" % (len(ra), len(rb)))
    print()

    bh = {}
    for h, n, p in rb:
        bh.setdefault(h, []).append(p)

    hits = [(h, n, p) for h, n, p in ra if h in bh]
    print("files in A whose content also occurs in B : %d" % len(hits))
    print("distinct shared hashes                    : %d"
          % len({h for h, n, p in hits}))
    print("bytes involved (A side)                   : %d"
          % sum(n for h, n, p in hits))
    print()
    for h, n, p in sorted(hits, key=lambda r: (r[1], r[2])):
        print("  %s  %8d  %s" % (h[:16], n, p))
        for q in bh[h]:
            print("      also at  %s" % q)

    if a.by_name:
        print()
        bn = {}
        for h, n, p in rb:
            bn.setdefault(p.lower(), []).append((h, n))
        same = diff = 0
        for h, n, p in ra:
            for q, hn in bn.items():
                if q.rsplit("/", 1)[-1] == p.rsplit("/", 1)[-1]:
                    if any(x[0] == h for x in hn):
                        same += 1
                    else:
                        diff += 1
                    break
        print("same basename, same content : %d" % same)
        print("same basename, differs      : %d" % diff)


if __name__ == "__main__":
    main()
