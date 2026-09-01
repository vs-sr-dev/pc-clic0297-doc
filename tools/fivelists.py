#!/usr/bin/env python3
"""sixlists: this disc against every published list in the collection.

listdiff.py compares two lists. By the eleventh session there are four published
lists plus eight working trees, and comparing them one pair at a time makes it
easy to report a total without saying what was in it. The tenth session's lesson
was the opposite one: *print the number of files compared next to the result,
and declare what is inside that number.*

    python tools/fivelists.py
    python tools/fivelists.py --show-matches

WHAT IS COMPARED
----------------
A SHA-1 of a whole file against a SHA-1 of a whole file. Nothing is compared by
name: two files with the same name and different bytes are not a match, and two
files with different names and the same bytes are. That is the only comparison
under which "these two discs share a file" means anything.

This disc contributes **two** lists, and they are kept apart on purpose:

  * `notes/sha1-all.txt`, the 2,374 files of the ISO 9660 volume -- the list
    another session could reproduce by putting the disc in a Windows drive;
  * `notes/sha1-hfs-only.txt`, the 38 forks of the 28 files that exist only in
    the HFS catalogue -- which no Windows machine can produce at all.

A crossing found in the second list would be a crossing no previous session
could have found, so the tool reports the two separately and never sums them.
"""
import argparse
import os
import sys

LISTS = [
    ("pc-harrypotter1-doc", "../pc-harrypotter5-doc/notes/hp1-sha1-all.txt",
     "Harry Potter and the Philosopher's Stone, 2001"),
    ("pc-harrypotter4-doc", "../pc-harrypotter4-doc/notes/sha1-all.txt",
     "Harry Potter and the Goblet of Fire, 2005"),
    ("pc-harrypotter5-doc", "../pc-harrypotter5-doc/notes/sha1-all.txt",
     "Harry Potter and the Order of the Phoenix, 2007"),
    ("pc-ageofwonders2-doc", "../pc-ageofwonders2-doc/notes/sha1-all.txt",
     "Age of Wonders II: The Wizard's Throne, 2002"),
    # added by pc-clic11-doc, 2026-08-31: the fifth published list, and the
    # first one in this collection that contains forks no Windows machine can
    # produce.
    ("pc-canediterracotta-doc", "../pc-canediterracotta-doc/notes/sha1-all.txt",
     "Il cane di terracotta, 2000"),
    ("pc-canediterracotta-doc (HFS)",
     "../pc-canediterracotta-doc/notes/sha1-hfs-only.txt",
     "Il cane di terracotta, 2000 -- the Macintosh-only forks"),
]

TREES = [
    ("pc-zerocomico-doc", "../pc-zerocomico-doc/_work"),
    ("pc-lucignolo-doc", "../pc-lucignolo-doc/_work"),
    ("pc-bloodandlace-doc", "../pc-bloodandlace-doc/_work/iso"),
    ("pc-883d-doc", "../pc-883d-doc/_work"),
    ("pc-883d-doc (tree)", "../pc-883d-doc/883"),
    ("pc-grandefratello-doc", "../pc-grandefratello-doc/_work"),
    ("pc-baronbaldric-doc", "../pc-baronbaldric-doc/_work"),
    ("pc-1000miglia-doc", "../pc-1000miglia-doc/1000 Miglia"),
    ("pc-mystictowers-doc", "../pc-mystictowers-doc/_work"),
]


def read_list(path):
    """sha1 -> [names]. Accepts 'sha1 size path' and 'sha1  path'."""
    out = {}
    if not os.path.exists(path):
        return None
    for line in open(path, encoding="utf-8", errors="replace"):
        parts = line.split()
        if len(parts) < 2 or len(parts[0]) != 40:
            continue
        try:
            int(parts[0], 16)
        except ValueError:
            continue
        name = parts[-1]
        out.setdefault(parts[0].lower(), []).append(name)
    return out


def hash_tree(root):
    import hashlib
    out = {}
    if not os.path.isdir(root):
        return None
    for dp, dn, fn in os.walk(root):
        for n in fn:
            p = os.path.join(dp, n)
            try:
                h = hashlib.sha1(open(p, "rb").read()).hexdigest()
            except OSError:
                continue
            out.setdefault(h, []).append(
                os.path.relpath(p, root).replace(os.sep, "/"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mine", default="notes/sha1-all.txt")
    ap.add_argument("--mine-hfs", default="notes/sha1-hfs-only.txt")
    ap.add_argument("--show-matches", action="store_true")
    a = ap.parse_args()

    mine = read_list(a.mine)
    mhfs = read_list(a.mine_hfs)
    if mine is None:
        raise SystemExit("no %s: run hashall.py first" % a.mine)

    print("this disc, ISO 9660 volume  : %d files, %d distinct SHA-1"
          % (sum(len(v) for v in mine.values()), len(mine)))
    if mhfs:
        print("this disc, HFS-only forks   : %d forks, %d distinct SHA-1"
              % (sum(len(v) for v in mhfs.values()), len(mhfs)))
    print()

    total_compared = 0
    total_hits = 0
    print("%-24s %8s %8s %8s  %s"
          % ("against", "records", "shared", "shared", "what it is"))
    print("%-24s %8s %8s %8s" % ("", "", "(ISO)", "(HFS)"))
    print("-" * 92)
    rows = []
    for name, path, what in LISTS:
        other = read_list(path)
        if other is None:
            print("%-24s %8s %8s %8s  LIST NOT FOUND at %s"
                  % (name, "-", "-", "-", path))
            continue
        n = sum(len(v) for v in other.values())
        hits = set(mine) & set(other)
        hitsh = set(mhfs or {}) & set(other)
        total_compared += n
        total_hits += len(hits) + len(hitsh)
        rows.append((name, other, hits, hitsh))
        print("%-24s %8d %8d %8d  %s"
              % (name, n, len(hits), len(hitsh), what))
    print()
    print("%-24s %8s %8s %8s  %s"
          % ("against (working tree)", "files", "shared", "shared", ""))
    print("-" * 92)
    for name, root in TREES:
        other = hash_tree(root)
        if other is None:
            print("%-24s %8s %8s %8s  TREE NOT PRESENT at %s"
                  % (name, "-", "-", "-", root))
            continue
        n = sum(len(v) for v in other.values())
        hits = set(mine) & set(other)
        hitsh = set(mhfs or {}) & set(other)
        total_compared += n
        total_hits += len(hits) + len(hitsh)
        rows.append((name, other, hits, hitsh))
        print("%-24s %8d %8d %8d" % (name, n, len(hits), len(hitsh)))

    print()
    print("file records compared against : %d" % total_compared)
    print("distinct SHA-1 shared with any: %d" % total_hits)
    print()
    print("What is inside that %d: four published hash lists (%d records) and"
          % (total_compared,
             sum(sum(len(v) for v in read_list(p).values())
                 for _, p, _ in LISTS if read_list(p))))
    print("the working trees of the other discs of this collection that are")
    print("present on this machine. It is a count of file records, not of discs")
    print("and not of distinct files: a list that carries the same file twice")
    print("contributes two.")

    if a.show_matches and total_hits:
        print()
        for name, other, hits, hitsh in rows:
            for h in sorted(hits):
                print("  %-24s %s" % (name, h))
                print("      here  : %s" % ", ".join(mine[h]))
                print("      there : %s" % ", ".join(other[h]))
            for h in sorted(hitsh):
                print("  %-24s %s  [HFS-only side]" % (name, h))
                print("      here  : %s" % ", ".join(mhfs[h]))
                print("      there : %s" % ", ".join(other[h]))


if __name__ == "__main__":
    main()
