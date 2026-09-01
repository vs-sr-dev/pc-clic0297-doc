#!/usr/bin/env python3
"""pkgdiff2.py -- compare Unreal packages that are nearly the same.

Four MenuArt packages differ by a handful of bytes in total:

    MenuArt.ita_utx  709,671
    MenuArt.spa_utx  709,672
    MenuArt.por_utx  709,677
    MenuArt.hun_utx  708,620
    MenuArt.utx      577,843   (the unlocalised one, a different size entirely)

This compares them structurally instead of by size: name tables, export
counts, export names, and -- the question that matters -- whether the pixel
payloads are the same bytes. It answers "what did localising a texture package
actually change" with a count rather than an impression.

    python tools/pkgdiff2.py FILE FILE [FILE ...]
"""
import collections
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkg  # noqa: E402


def main():
    paths = [a for a in sys.argv[1:] if not a.startswith("--")]
    pkgs = []
    for p in paths:
        k = upkg.Package(p)
        k.load()
        pkgs.append(k)

    print("%-24s %8s %5s %6s %7s %7s %11s"
          % ("package", "bytes", "ver", "names", "imports", "exports",
             "data bytes"))
    for k in pkgs:
        dr = k.name_end, min(x for x in (k.imp_off, k.exp_off) if x)
        print("%-24s %8d %5d %6d %7d %7d %11d"
              % (os.path.basename(k.path), k.size, k.ver, k.name_n, k.imp_n,
                 k.exp_n, dr[1] - dr[0]))
    print()

    base = pkgs[0]
    print("name tables, against %s:" % os.path.basename(base.path))
    for k in pkgs[1:]:
        a, b = base.names, k.names
        if a == b:
            print("  %-24s IDENTICAL name table (%d entries)"
                  % (os.path.basename(k.path), len(a)))
            continue
        sa, sb = set(a), set(b)
        print("  %-24s %d entries vs %d"
              % (os.path.basename(k.path), len(a), len(b)))
        only_a = [x for x in a if x not in sb]
        only_b = [x for x in b if x not in sa]
        print("      only in %s : %s"
              % (os.path.basename(base.path), only_a[:12] or "(none)"))
        print("      only in %s : %s"
              % (os.path.basename(k.path), only_b[:12] or "(none)"))
        posdiff = [(i, x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y]
        print("      entries differing at the same index: %d %s"
              % (len(posdiff), posdiff[:6]))
    print()

    print("exports, by name, and the SHA-1 of each export's serial bytes:")
    tab = {}
    for k in pkgs:
        m = {}
        for e in k.exports:
            nm = k.name(e[3])
            blob = k.d[e[6]:e[6] + e[5]] if e[5] else b""
            m[nm] = (e[5], hashlib.sha1(blob).hexdigest())
        tab[os.path.basename(k.path)] = m
    allnames = []
    for k in pkgs:
        for e in k.exports:
            nm = k.name(e[3])
            if nm not in allnames:
                allnames.append(nm)
    files = [os.path.basename(k.path) for k in pkgs]
    same = diff = missing = 0
    print("  %-34s %s" % ("export", "  ".join("%-12s" % f[:12] for f in files)))
    for nm in allnames:
        cells = []
        digs = set()
        for f in files:
            v = tab[f].get(nm)
            if v is None:
                cells.append("%-12s" % "-")
                missing += 1
            else:
                cells.append("%-12s" % (v[1][:8] + " " + str(v[0])[:0]))
                digs.add(v[1])
        if len(digs) == 1 and missing == 0:
            same += 1
        else:
            diff += 1
        mark = "" if len(digs) <= 1 else "   <-- DIFFERS"
        print("  %-34s %s%s" % (nm[:34], "  ".join(cells), mark))
    print()
    print("exports with identical bytes in every package : %d" % same)
    print("exports that differ or are missing somewhere  : %d" % diff)
    print()

    print("whole-file digests:")
    for k in pkgs:
        print("  %-24s %s" % (os.path.basename(k.path),
                              hashlib.sha1(k.d).hexdigest()))


if __name__ == "__main__":
    main()
