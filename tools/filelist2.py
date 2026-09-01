#!/usr/bin/env python3
"""filelist2.py -- expand common_filelist.txt against the tree it describes.

filelist.py, inherited, has the previous disc's three manifest lines written
into its source as literals and labels them "line 1", "line 2", "line 3". Run
here it silently expands a manifest this disc does not have -- and reports a
coverage figure for it. This one reads the manifest off the disc.

The format, from the file itself: comma-separated, three fields, the third
being a path with optional wildcards and an optional " /s" meaning recurse.

    python tools/filelist2.py _work/iso
    python tools/filelist2.py _work/iso --manifest common_filelist.txt
"""
import argparse
import fnmatch
import os

BS = chr(92)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--manifest", default="common_filelist.txt")
    a = ap.parse_args()

    mpath = os.path.join(a.root, a.manifest)
    nbytes = os.path.getsize(mpath)
    raw = open(mpath, encoding="utf-8", errors="replace").read()
    lines = [l.strip() for l in raw.splitlines() if l.strip()]

    allf = set()
    for r, dirs, names in os.walk(a.root):
        for n in names:
            allf.add(os.path.relpath(os.path.join(r, n), a.root)
                     .replace("/", BS))

    print("tree              : %s" % a.root)
    print("manifest          : %s (%d bytes, %d lines)"
          % (a.manifest, nbytes, len(lines)))
    print("files in the tree : %d" % len(allf))
    print()

    covered = set()
    print("  %-3s %-46s %8s  %s" % ("#", "pattern", "matches", "recursive"))
    for i, line in enumerate(lines, 1):
        parts = line.split(",", 2)
        pat = parts[-1].strip()
        recurse = pat.lower().endswith("/s")
        if recurse:
            pat = pat[:-2].strip()
        pat = pat.replace("/", BS)
        hit = set()
        for f in allf:
            if recurse:
                # "DIR\*.*" with /s: everything under DIR
                stem = pat.rsplit(BS, 1)[0]
                if f.lower().startswith(stem.lower() + BS):
                    hit.add(f)
            else:
                d = pat.rsplit(BS, 1)[0] if BS in pat else ""
                base = pat.rsplit(BS, 1)[-1]
                fd = f.rsplit(BS, 1)[0] if BS in f else ""
                fb = f.rsplit(BS, 1)[-1]
                if fd.lower() == d.lower() and \
                        fnmatch.fnmatch(fb.lower(), base.lower()):
                    hit.add(f)
        covered |= hit
        print("  %-3d %-46s %8d  %s"
              % (i, parts[-1].strip()[:46], len(hit), "yes" if recurse else "no"))

    print()
    print("covered by the manifest      : %d" % len(covered))
    print("in the tree, not covered     : %d" % len(allf - covered))
    print()

    miss = sorted(allf - covered)
    sup = [f for f in miss if f.lower().startswith("support" + BS)]
    print("of the uncovered, %d are under Support%s -- the ones the manifest"
          % (len(sup), BS))
    print("was meant to reach:")
    for f in sup:
        print("     %s" % f)
    print()
    print("the other %d uncovered files are outside Support%s; those are the"
          % (len(miss) - len(sup), BS))
    print("files the autorun shell reads from the disc rather than installing:")
    for f in miss:
        if f not in sup:
            print("     %s" % f)


if __name__ == "__main__":
    main()
