#!/usr/bin/env python3
"""pkgsame.py -- compare packages by payload rather than by name.

pkgdiff2.py matches exports by name and found that the four localised MenuArt
packages share no export name at all, because the palette objects are numbered
by import order and the import order differed. Matching by name therefore
reports "everything differs", which is true and useless.

This matches by CONTENT: the multiset of export payload digests. It answers
the question that was actually being asked -- is the artwork the same and only
the bookkeeping different, or is the artwork different too.

It also accounts for the file-size difference byte by byte: header, name
table, data region, import table, export table, so that a six-byte spread
between three files is attributed rather than described.

    python tools/pkgsame.py FILE FILE [FILE ...]
"""
import collections
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkg  # noqa: E402


def parts(k):
    first_tbl = min(x for x in (k.imp_off, k.exp_off) if x and x > k.name_end)
    return {
        "header": (0, k.name_off),
        "name table": (k.name_off, k.name_end),
        "data region": (k.name_end, first_tbl),
        "import table": (k.imp_off, k.imp_end),
        "export table": (k.exp_off, k.exp_end),
    }


def main():
    paths = sys.argv[1:]
    pkgs = []
    for p in paths:
        k = upkg.Package(p)
        k.load()
        pkgs.append(k)

    print("byte budget, region by region:")
    print()
    regions = ["header", "name table", "data region", "import table",
               "export table"]
    print("  %-24s %10s %12s %12s %12s %12s %10s"
          % ("package", "header", "name table", "data region", "import tbl",
             "export tbl", "total"))
    sizes = {}
    for k in pkgs:
        pr = parts(k)
        row = [pr[r][1] - pr[r][0] for r in regions]
        sizes[k.path] = row
        print("  %-24s %10d %12d %12d %12d %12d %10d"
              % (os.path.basename(k.path), row[0], row[1], row[2], row[3],
                 row[4], k.size))
    print()
    base = pkgs[0]
    print("difference from %s:" % os.path.basename(base.path))
    for k in pkgs[1:]:
        d = [sizes[k.path][i] - sizes[base.path][i] for i in range(5)]
        print("  %-24s %+10d %+12d %+12d %+12d %+12d %+10d"
              % (os.path.basename(k.path), d[0], d[1], d[2], d[3], d[4],
                 k.size - base.size))
    print()

    print("export payloads as a multiset of SHA-1 digests:")
    sets = {}
    for k in pkgs:
        c = collections.Counter()
        for e in k.exports:
            blob = k.d[e[6]:e[6] + e[5]] if e[5] else b""
            c[hashlib.sha1(blob).hexdigest()] += 1
        sets[os.path.basename(k.path)] = c
        print("  %-24s %d exports, %d distinct payloads"
              % (os.path.basename(k.path), sum(c.values()), len(c)))
    print()
    names = list(sets)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = sets[names[i]], sets[names[j]]
            shared = sum(min(a[x], b[x]) for x in set(a) | set(b))
            print("  %-22s vs %-22s : %d payloads in common, %d only in the "
                  "first, %d only in the second"
                  % (names[i], names[j], shared,
                     sum(a.values()) - shared, sum(b.values()) - shared))
    print()

    print("name-table byte cost, entry by entry, first package vs each other:")
    for k in pkgs:
        tot = sum(1 + len(n) + 1 + 4 for n in k.names)
        print("  %-24s %d names, %d bytes if each is (len byte + text + NUL + "
              "4 flag bytes) ; measured %d"
              % (os.path.basename(k.path), len(k.names), tot,
                 k.name_end - k.name_off))
    print()
    print("the longest and shortest name in each:")
    for k in pkgs:
        ln = sorted(k.names, key=len)
        print("  %-24s shortest %r  longest %r  total text %d chars"
              % (os.path.basename(k.path), ln[0], ln[-1],
                 sum(len(n) for n in k.names)))


if __name__ == "__main__":
    main()
