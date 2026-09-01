#!/usr/bin/env python3
"""treecensus.py -- what is in a copied tree: counts, bytes, extensions, years.

Deliberately dumb and deliberately not inherited. Nine tools in this collection
census a tree and every one of them has another disc's constants compiled in.
This one has none: everything it prints is derived from the directory it is
pointed at, and the only opinion it holds is that a "file" is something
os.walk() returns in its filenames list.

    python tools/treecensus.py _work/iso
    python tools/treecensus.py _work/iso --tsv notes/tree.tsv

The year histogram is built from the filesystem mtime, which on a CD-ROM copied
by robocopy is the ISO 9660 directory record's recording date, converted to
local time by Windows. It is ONE of three clocks and the weakest of the three.
"""
import argparse
import datetime
import os
from collections import Counter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--tsv")
    a = ap.parse_args()

    files = []
    ndirs = 0
    for dp, dn, fn in os.walk(a.root):
        ndirs += len(dn)
        for f in fn:
            p = os.path.join(dp, f)
            st = os.stat(p)
            rel = os.path.relpath(p, a.root).replace(os.sep, "/")
            files.append((rel, st.st_size, st.st_mtime))
    files.sort()

    print("root            : %s" % a.root)
    print("files           : %d" % len(files))
    print("directories     : %d" % ndirs)
    print("bytes           : %d" % sum(f[1] for f in files))
    print()

    yr = Counter(datetime.datetime.fromtimestamp(f[2]).year for f in files)
    yb = Counter()
    for f in files:
        yb[datetime.datetime.fromtimestamp(f[2]).year] += f[1]
    print("year of the directory record:")
    print("  %-6s %6s %14s" % ("year", "files", "bytes"))
    for y in sorted(yr):
        print("  %-6d %6d %14d" % (y, yr[y], yb[y]))
    print()

    ext = Counter(os.path.splitext(f[0])[1].lower() for f in files)
    eb = Counter()
    for f in files:
        eb[os.path.splitext(f[0])[1].lower()] += f[1]
    print("extensions:")
    print("  %-10s %6s %14s" % ("ext", "files", "bytes"))
    for e, n in ext.most_common():
        print("  %-10s %6d %14d" % (e or "(none)", n, eb[e]))
    print()

    tl = Counter()
    tb = Counter()
    for f in files:
        k = f[0].split("/")[0] if "/" in f[0] else "(root)"
        tl[k] += 1
        tb[k] += f[1]
    print("top-level entries:")
    print("  %-14s %6s %14s %7s" % ("name", "files", "bytes", "pct"))
    tot = sum(f[1] for f in files)
    for k, n in sorted(tl.items(), key=lambda kv: -tb[kv[0]]):
        print("  %-14s %6d %14d %6.2f%%" % (k, n, tb[k], 100.0 * tb[k] / tot))

    if a.tsv:
        with open(a.tsv, "w", encoding="utf-8", newline="") as fh:
            fh.write("path\tsize\tmtime\n")
            for rel, sz, mt in files:
                fh.write("%s\t%d\t%s\n"
                         % (rel, sz,
                            datetime.datetime.fromtimestamp(mt)
                            .strftime("%Y-%m-%d %H:%M:%S")))
        print()
        print("wrote %s" % a.tsv)


if __name__ == "__main__":
    main()
