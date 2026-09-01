#!/usr/bin/env python3
"""resolve.py -- do the names the product says out loud actually exist?

`refcheck.py`, inherited from pc-lucignolo-doc, looks for `..\\`-relative paths,
because that is the shape Lucignolo's engine used. This disc does not have any:
Director addresses its media by bare filename relative to the movie, and the
Lingo literal pools are full of names like `H883D2.mov` with no path at all.
So refcheck.py returns zero here and its zero means "pattern did not match",
not "no broken references". This tool asks the question refcheck.py was built
to ask, in the shape this disc actually uses.

For each candidate name it reports one of:

    EXACT      a file of that name exists, byte-for-byte the same spelling
    CASE       a file exists whose name differs only in letter case
    BASENAME   the leaf name exists somewhere in the tree, at another path
    ABSENT     nothing in the tree matches, case-insensitively

CASE is the interesting verdict and it is not pedantry. Windows and Mac OS
filesystems of 1999 are case-insensitive, so a case mismatch was invisible to
everyone who ever ran this disc; it becomes visible only when the tree is read
by something that compares strings. Counting them measures how many separate
hands touched the naming, which is a fact about the production and not about
the product.

    python tools/resolve.py NAMES.txt TREE
    python tools/resolve.py NAMES.txt TREE --verbose
"""
import argparse
import os
import sys
from collections import defaultdict


def index(root):
    """Two maps: full relative path (lower) -> real, and basename -> [real]."""
    by_path = {}
    by_base = defaultdict(list)
    for dp, dn, fn in os.walk(root):
        dn.sort()
        for f in sorted(fn):
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            by_path[rel.lower()] = rel
            by_base[f.lower()].append(rel)
    return by_path, by_base


def classify(name, by_path, by_base):
    # Normalise the separators a Director script might use. Macintosh Lingo
    # writes colons; Windows Lingo writes backslashes; both appear on this disc.
    n = name.replace(chr(92), "/").replace(":", "/")
    n = n.lstrip("./")
    low = n.lower()
    base = low.rsplit("/", 1)[-1]

    if n in by_path.values():
        return "EXACT", n
    if low in by_path:
        real = by_path[low]
        return ("EXACT", real) if real == n else ("CASE", real)
    if base in by_base:
        cands = by_base[base]
        # exact-case leaf match somewhere else in the tree?
        for c in cands:
            if c.rsplit("/", 1)[-1] == n.rsplit("/", 1)[-1]:
                return "BASENAME", c
        return "CASE", cands[0]
    return "ABSENT", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names")
    ap.add_argument("tree")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

    by_path, by_base = index(args.tree)

    cands = []
    for line in open(args.names, encoding="utf-8", errors="replace"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if " " in s and "." not in s:
            continue
        if "." not in s:
            continue
        cands.append(s)
    # drop the header prose lines the collector writes
    cands = [c for c in cands if len(c) < 80 and not c.endswith(".")]

    counts = defaultdict(int)
    print("%-30s %-9s %s" % ("referenced name", "verdict", "resolves to"))
    print("-" * 30 + " " + "-" * 9 + " " + "-" * 40)
    for c in cands:
        verdict, real = classify(c, by_path, by_base)
        counts[verdict] += 1
        print("%-30s %-9s %s" % (c, verdict, real))

    print()
    print("names checked : %d" % len(cands))
    for k in ("EXACT", "CASE", "BASENAME", "ABSENT"):
        print("  %-9s   %d" % (k, counts[k]))
    print()
    print("A CASE verdict is a reference that works on every filesystem this")
    print("disc was ever run on and fails on any case-sensitive one.")


if __name__ == "__main__":
    main()
