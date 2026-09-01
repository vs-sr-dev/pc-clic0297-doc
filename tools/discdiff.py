#!/usr/bin/env python3
"""discdiff.py - is any file on this disc also on another disc?

compare.py, carried over from the previous two discs, compares two
*namespaces of one image*. This is the other question: two different discs,
by content hash, with no assumption that anything lines up by name or path.

It exists because the interesting answer here was zero, and zero is only
worth printing if the thing that produced it also prints how many files it
looked at.

Usage:
    python tools/discdiff.py DIR_A DIR_B [DIR_C ...]
    python tools/discdiff.py DIR_A DIR_B --by-name
"""

import argparse
import hashlib
import os


def index(root):
    by_hash = {}
    n = 0
    total = 0
    for r, dirs, names in os.walk(root):
        for name in sorted(names):
            p = os.path.join(r, name)
            try:
                with open(p, "rb") as fh:
                    h = hashlib.sha256()
                    size = 0
                    while True:
                        b = fh.read(1 << 20)
                        if not b:
                            break
                        h.update(b)
                        size += len(b)
            except OSError:
                continue
            by_hash.setdefault(h.hexdigest(), []).append((p, size))
            n += 1
            total += size
    return by_hash, n, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--by-name", action="store_true",
                    help="also report files sharing a basename but not a hash")
    a = ap.parse_args()

    idx = []
    for d in a.dirs:
        by_hash, n, total = index(d)
        idx.append((d, by_hash, n, total))
        print("%-56s %6d files, %6d distinct, %12d bytes"
              % (d, n, len(by_hash), total))
    print()

    for i in range(len(idx)):
        for j in range(i + 1, len(idx)):
            da, ha, na, _ = idx[i]
            db, hb, nb, _ = idx[j]
            common = set(ha) & set(hb)
            print("-- %s  vs  %s" % (os.path.basename(da.rstrip("/\\")),
                                     os.path.basename(db.rstrip("/\\"))))
            print("   files hashing the same on both   %d" % len(common))
            for c in sorted(common):
                print("      %-40s == %s"
                      % (os.path.basename(ha[c][0][0]),
                         os.path.basename(hb[c][0][0])))
            if a.by_name:
                na_ = {os.path.basename(p).lower(): c
                       for c, v in ha.items() for p, s in v}
                nb_ = {os.path.basename(p).lower(): c
                       for c, v in hb.items() for p, s in v}
                shared = sorted(set(na_) & set(nb_))
                diff = [n for n in shared if na_[n] != nb_[n]]
                print("   basenames on both discs          %d" % len(shared))
                print("   ... of which the bytes differ    %d" % len(diff))
                for n in diff[:40]:
                    print("      %s" % n)
            print()


if __name__ == "__main__":
    main()
