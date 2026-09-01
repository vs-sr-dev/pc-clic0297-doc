#!/usr/bin/env python3
"""machpaths2.py -- the strict pass over machpaths.py's output.

The loose pattern in machpaths.py finds 3,454 candidate paths, and most are
noise: compressed payload contains `X:` followed by printable bytes often
enough that a permissive rule reports it. This pass keeps only candidates that
look like paths a person's machine actually produced, and it states the rule
it uses so the filtering is auditable rather than eyeballed.

A candidate is kept when ALL of:
  * at least three components separated by the separator;
  * every component is 1..64 characters of letters, digits, space, and the
    punctuation Windows permits in a name;
  * at least two components contain a run of three or more letters;
  * the last component either contains a dot or is itself three-plus letters;
  * the volume is a drive letter, or a UNC host of 3+ characters that is not
    a single repeated character.

    python tools/machpaths2.py E:/
"""
import collections
import os
import re
import sys

BS = chr(92)
ESC = re.escape(BS)
ESCB = ESC.encode()
NOTPATH = rb"[^" + bytes([0x00]) + rb"-" + bytes([0x1F]) + rb'"<>|*?]'
DRIVE = re.compile(rb"[A-Za-z]:" + ESCB + NOTPATH + rb"{4,200}")
UNC = re.compile(ESCB + ESCB + rb"[A-Za-z0-9_.-]{3,32}" + ESCB +
                 NOTPATH + rb"{2,180}")

COMP = re.compile(r"^[A-Za-z0-9 _.~!#$%&'()+,;=@\[\]{}~-]{1,64}$")
THREE = re.compile(r"[A-Za-z]{3}")


def keep(s):
    if s.count(BS) < 2:
        return False
    if s.startswith(BS + BS):
        head = s[2:].split(BS)[0]
        if len(head) < 3 or len(set(head)) == 1:
            return False
        parts = s[2:].split(BS)
    else:
        if not re.match(r"^[A-Za-z]:" + ESC, s):
            return False
        parts = s[3:].split(BS)
    parts = [p for p in parts if p != ""]
    if len(parts) < 2:
        return False
    for p in parts:
        if not COMP.match(p):
            return False
    if sum(1 for p in parts if THREE.search(p)) < 2:
        return False
    last = parts[-1]
    if "." not in last and not THREE.search(last):
        return False
    return True


def clean(b):
    s = b.decode("latin-1")
    for stop in ("\r", "\n", "  ", "\t"):
        if stop in s:
            s = s.split(stop)[0]
    return s.rstrip(" .,;")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "E:/"
    perfile = collections.defaultdict(set)
    roots = collections.Counter()
    drives = collections.Counter()
    allp = collections.Counter()
    nfiles = 0
    for dp, dn, fn in os.walk(root):
        for f in sorted(fn):
            p = os.path.join(dp, f)
            nfiles += 1
            try:
                d = open(p, "rb").read()
            except OSError:
                continue
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            for m in list(DRIVE.finditer(d)) + list(UNC.finditer(d)):
                s = clean(m.group())
                if not keep(s):
                    continue
                perfile[rel].add((m.start(), s))
                allp[s] += 1
                if s[1:2] == ":":
                    drives[s[0].upper()] += 1
                parts = s.split(BS)
                roots[BS.join(parts[:3])] += 1

    print("files scanned                 : %d" % nfiles)
    print("files with at least one path  : %d" % len(perfile))
    print("distinct paths kept           : %d" % len(allp))
    print()
    print("drive letters:")
    for k, v in drives.most_common():
        print("   %s:  %d" % (k, v))
    print()
    print("project roots (first two components):")
    for k, v in roots.most_common(40):
        print("   %-58s %d" % (k, v))
    print()
    print("files, with every distinct path they carry:")
    for rel in sorted(perfile):
        v = sorted(perfile[rel])
        print()
        print("  %s   (%d distinct)" % (rel, len(v)))
        for off, s in v[:60]:
            print("      +0x%-8X %s" % (off, s))
        if len(v) > 60:
            print("      ... and %d more" % (len(v) - 60))


if __name__ == "__main__":
    main()
