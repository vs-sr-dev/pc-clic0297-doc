#!/usr/bin/env python3
"""leftovers.py -- how many bytes of this disc should not be on it, added up.

The chapter this feeds is not a diary of mistakes made during the session. It
is the list of things on the *disc* that nobody meant to publish: the scan
cache of a program that passed through, a database the Finder wrote, an
editable original left beside its export, a template that says in its own text
that it need not be distributed, a duplicate that came in with a second copy of
a folder.

Each category is measured separately with the command that measures it, and the
total at the bottom is their sum with nothing counted twice. Where a file falls
into two categories (a ScanDisk fragment that is also a duplicate) it is
counted once, in the first category that claims it, and the double membership
is printed.

    python tools/leftovers.py
"""
import argparse
import hashlib
import os
import struct
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assoc


def sha1(p):
    h = hashlib.sha1()
    with open(p, "rb") as fh:
        while True:
            b = fh.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", default="_work/iso")
    ap.add_argument("--forks", default="_work/hfs")
    ap.add_argument("--image", default="_work/clic11.img")
    a = ap.parse_args()

    files = {}
    for dp, dn, fn in os.walk(a.tree):
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, a.tree).replace(os.sep, "/")
            files[rel] = os.path.getsize(p)
    forks = {}
    for dp, dn, fn in os.walk(a.forks):
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, a.forks).replace(os.sep, "/")
            forks[rel] = os.path.getsize(p)

    disc_bytes = 661352448
    claimed = set()
    cats = []

    def add(name, items, note):
        fresh = [(p, n) for p, n in items if p not in claimed]
        dup = [p for p, n in items if p in claimed]
        for p, n in fresh:
            claimed.add(p)
        cats.append((name, fresh, sum(n for p, n in fresh), note, dup))

    # 1 -- duplicates inside the ISO volume
    byhash = defaultdict(list)
    for rel in files:
        byhash[sha1(os.path.join(a.tree, rel))].append(rel)
    dups = []
    for h, group in byhash.items():
        if len(group) > 1:
            group.sort()
            for extra in group[1:]:
                dups.append((extra, files[extra]))
    add("redundant copies inside the ISO volume", dups,
        "every group of identical files keeps one; the rest are these")

    # 2 -- editable originals left beside their exports
    old = [(p, n) for p, n in files.items() if p.upper().endswith(".OLD")]
    add("files whose extension says they are superseded", old,
        "a .OLD is the previous version of the file next to it")

    # 3 -- the Finder's own database
    fin = [(p, n) for p, n in forks.items()
           if os.path.basename(p).startswith("Desktop D")]
    add("the Macintosh Finder's desktop database", fin,
        "written by the Mac that built the HFS side, not by anyone's work")

    # 4 -- custom folder icons
    ico = [(p, n) for p, n in forks.items()
           if os.path.basename(p).startswith("Icon")]
    add("custom folder icons the Finder left behind", ico,
        "each is an empty file whose resource fork holds one icon family")

    # 5 -- setup marker files
    mark = [(p, n) for p, n in files.items()
            if os.path.basename(p).upper() in ("MSCREATE.DIR",)]
    add("Microsoft setup's directory marker", mark,
        "a hidden zero-length file setup writes so uninstall can undo a mkdir")

    # 6 -- a recovered fragment
    chk = [(p, n) for p, n in files.items() if p.upper().endswith(".CHK")]
    add("files with the extension ScanDisk gives recovered fragments", chk,
        "a .CHK is what a repaired FAT filesystem calls a lost chain")

    # 7 -- commented-out template in the Director INIs
    tmpl = []
    for rel in files:
        if not rel.upper().endswith(".INI"):
            continue
        d = open(os.path.join(a.tree, rel), "rb").read()
        lines = d.split(b"\r\n")
        com = sum(len(l) + 2 for l in lines
                  if l.strip().startswith(b";") or l.strip().startswith(b"--"))
        if com > 1000:
            tmpl.append((rel + " [comment lines only]", com))
    cats.append(("commented-out template text inside shipped INI files",
                 tmpl, sum(n for p, n in tmpl),
                 "Macromedia's example file says it need not be distributed",
                 []))

    # 8 -- FileMaker's filler
    jack = b"All work and no play makes Jack a dull boy. "
    fm = []
    for base, tree in ((a.tree, files), (a.forks, forks)):
        for rel in tree:
            p = os.path.join(base, rel)
            if os.path.getsize(p) > 8 * 1024 * 1024:
                continue
            d = open(p, "rb").read()
            n = d.count(jack)
            if n:
                fm.append((rel + " [filler]", n * len(jack)))
    cats.append(("FileMaker's free-space filler, counted by repetitions",
                 fm, sum(n for p, n in fm),
                 "the sentence Jack Torrance types, written into unused blocks",
                 []))

    print("leftovers on CLIC 11, by category")
    print("disc = %d bytes" % disc_bytes)
    print()
    grand = 0
    for name, items, total, note, dup in cats:
        print("=" * 74)
        print("%s" % name)
        print("  %s" % note)
        print("  files: %d    bytes: %d    %.4f %% of the disc"
              % (len(items), total, 100.0 * total / disc_bytes))
        for p, n in sorted(items, key=lambda x: -x[1])[:24]:
            print("     %-56s %10d" % (p[-56:], n))
        if len(items) > 24:
            print("     ... and %d more" % (len(items) - 24))
        if dup:
            print("  already counted in an earlier category: %s"
                  % ", ".join(dup))
        grand += total
    print("=" * 74)
    print()
    print("TOTAL leftover bytes          : %d" % grand)
    print("as a share of the disc        : %.4f %%"
          % (100.0 * grand / disc_bytes))
    print("as a share of the file payload: %.4f %%" % (100.0 * grand / 634121776))


if __name__ == "__main__":
    main()
