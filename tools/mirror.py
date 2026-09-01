#!/usr/bin/env python3
"""mirror.py -- how much of a set of parallel trees is actually the same file.

Ten language folders that look like ten translations are usually one document
plus nine copies of everything that is not text. This measures the split
instead of assuming it: for every relative path present in more than one
sibling tree, it asks whether the bytes are the same.

    python tools/mirror.py "E:/Support/European Help Files"
    python tools/mirror.py "E:/Support/European Help Files" --matrix
    python tools/mirror.py "E:/Support/European Help Files" --by-name

Prints, per sibling: file count, bytes, how many of its files are unique to it,
and the byte count that is genuinely its own. Then the whole-set totals: how
many distinct file contents exist across all siblings, and what the tree would
weigh if identical files were stored once.
"""
import argparse
import collections
import hashlib
import os
import sys


def sha1(p):
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--matrix", action="store_true")
    ap.add_argument("--by-name", action="store_true")
    ap.add_argument("--min-siblings", type=int, default=2)
    a = ap.parse_args()

    sibs = sorted(d for d in os.listdir(a.root)
                  if os.path.isdir(os.path.join(a.root, d)))
    print("root     : %s" % a.root)
    print("siblings : %d  %s" % (len(sibs), ", ".join(sibs)))
    print()

    trees = {}
    for s in sibs:
        base = os.path.join(a.root, s)
        t = {}
        for dp, dn, fn in os.walk(base):
            for f in fn:
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, base).replace(chr(92), "/")
                t[rel] = (os.path.getsize(p), sha1(p))
        trees[s] = t

    print("%-8s %7s %14s %8s %14s %8s %14s"
          % ("sibling", "files", "bytes", "unique", "unique bytes", "shared", "shared bytes"))
    # a file is "unique" if its hash appears in no other sibling
    hash_owners = collections.defaultdict(set)
    for s, t in trees.items():
        for rel, (sz, h) in t.items():
            hash_owners[h].add(s)
    tot_files = tot_bytes = 0
    for s in sibs:
        t = trees[s]
        u = [(rel, sz) for rel, (sz, h) in t.items() if len(hash_owners[h]) == 1]
        sh = [(rel, sz) for rel, (sz, h) in t.items() if len(hash_owners[h]) > 1]
        nb = sum(sz for _, sz in t.values() if True) if False else sum(v[0] for v in t.values())
        tot_files += len(t)
        tot_bytes += nb
        print("%-8s %7d %14d %8d %14d %8d %14d"
              % (s, len(t), nb, len(u), sum(x[1] for x in u),
                 len(sh), sum(x[1] for x in sh)))
    print("%-8s %7d %14d" % ("TOTAL", tot_files, tot_bytes))
    print()

    allhash = {}
    for s, t in trees.items():
        for rel, (sz, h) in t.items():
            allhash[h] = sz
    print("distinct file contents across all siblings : %d" % len(allhash))
    print("bytes if stored once                       : %d" % sum(allhash.values()))
    print("bytes as shipped                           : %d" % tot_bytes)
    print("duplication                                : %.2f %%"
          % (100.0 * (1 - sum(allhash.values()) / tot_bytes) if tot_bytes else 0))
    print()

    # names present in every sibling
    names = collections.Counter()
    for t in trees.values():
        names.update(t.keys())
    universal = [n for n, c in names.items() if c == len(sibs)]
    print("relative paths present in ALL %d siblings   : %d of %d distinct paths"
          % (len(sibs), len(universal), len(names)))
    same = 0
    diff = 0
    for n in universal:
        hs = {trees[s][n][1] for s in sibs}
        if len(hs) == 1:
            same += 1
        else:
            diff += 1
    print("  of those, byte-identical in all siblings : %d" % same)
    print("  of those, differing somewhere            : %d" % diff)
    ub = sum(trees[sibs[0]][n][0] for n in universal if
             len({trees[s][n][1] for s in sibs}) == 1)
    print("  bytes of the identical ones, per sibling : %d" % ub)
    print()

    if a.by_name:
        print("universal paths that DIFFER between siblings, by extension:")
        byext = collections.Counter()
        for n in universal:
            if len({trees[s][n][1] for s in sibs}) > 1:
                byext[os.path.splitext(n)[1].lower()] += 1
        for e, c in byext.most_common():
            print("  %-8s %d" % (e, c))
        print()
        print("universal paths that are IDENTICAL, by extension:")
        byext = collections.Counter()
        for n in universal:
            if len({trees[s][n][1] for s in sibs}) == 1:
                byext[os.path.splitext(n)[1].lower()] += 1
        for e, c in byext.most_common():
            print("  %-8s %d" % (e, c))
        print()
        print("paths NOT present in every sibling: %d" % (len(names) - len(universal)))
        for n, c in sorted(((n, c) for n, c in names.items() if c < len(sibs)),
                           key=lambda kv: (kv[1], kv[0]))[:40]:
            have = [s for s in sibs if n in trees[s]]
            print("  %-46s in %d: %s" % (n[:46], c, ",".join(have)))

    if a.matrix:
        print()
        print("pairwise: files with the same relative path AND the same bytes")
        print("%-8s %s" % ("", " ".join("%6s" % s[:6] for s in sibs)))
        for s1 in sibs:
            row = []
            for s2 in sibs:
                n = sum(1 for r in trees[s1]
                        if r in trees[s2] and trees[s1][r][1] == trees[s2][r][1])
                row.append("%6d" % n)
            print("%-8s %s" % (s1[:8], " ".join(row)))


if __name__ == "__main__":
    main()
