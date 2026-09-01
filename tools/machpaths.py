#!/usr/bin/env python3
"""machpaths.py -- absolute filesystem paths left inside shipped files.

On the 883 disc the studio's name came out of a hostname rather than out of a
document. The same class of evidence is here: a 3ds Max exporter wrote its
source-bitmap path into an Unreal package as a comment, and the path contains
a Windows domain-qualified user profile.

This finds every absolute path in every file: drive-letter paths, UNC paths,
and the `Path:` comments the exporter emits. It reports the distinct user
profiles, the distinct drive letters, and the distinct project roots, because
those are the measurable parts. It does not guess what a path means.

Note on writing this file: the backslash is the subject of the tool and the
shell in this session eats backslashes out of heredocs, so every backslash
below is built from chr(92) and every regex uses re.escape on it. There is no
literal backslash in a pattern anywhere in this source.

    python tools/machpaths.py E:/
    python tools/machpaths.py E:/ --full
"""
import collections
import os
import re
import sys

BS = chr(92)
ESC = re.escape(BS)
ESCB = ESC.encode()

# a path component may not contain control characters or these punctuation
NOTPATH = rb"[^" + bytes([0x00]) + rb"-" + bytes([0x1F]) + rb'"<>|*?]'

DRIVE = re.compile(rb"[A-Za-z]:" + ESCB + NOTPATH + rb"{4,180}")
UNC = re.compile(ESCB + ESCB + rb"[A-Za-z0-9_.-]{2,32}" + ESCB +
                 NOTPATH + rb"{2,160}")
PROFILE = re.compile(r"(?i)Documents and Settings" + ESC +
                     r"([^" + ESC + r"]+)")
WINNT = re.compile(r"(?i)(?:WINNT|WINDOWS)" + ESC + r"Profiles" + ESC +
                   r"([^" + ESC + r"]+)")


def walk(root):
    for dp, dn, fn in os.walk(root):
        for f in sorted(fn):
            yield os.path.join(dp, f)


def clean(b):
    s = b.decode("latin-1")
    for stop in ("\r", "\n", "  "):
        if stop in s:
            s = s.split(stop)[0]
    return s.rstrip(" .,;")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "E:/"
    full = "--full" in sys.argv
    hits = collections.defaultdict(list)
    profiles = collections.Counter()
    drives = collections.Counter()
    roots = collections.Counter()
    allpaths = set()
    nfiles = 0
    for p in walk(root):
        nfiles += 1
        try:
            d = open(p, "rb").read()
        except OSError as e:
            print("  !! %s unreadable: %s" % (p, e))
            continue
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        seen = set()
        for m in list(DRIVE.finditer(d)) + list(UNC.finditer(d)):
            s = clean(m.group())
            if len(s) < 8 or s in seen:
                continue
            if s.count(BS) < 2:
                continue
            seen.add(s)
            allpaths.add(s)
            hits[rel].append((m.start(), s))
            if s[1:2] == ":":
                drives[s[0].upper()] += 1
            pm = PROFILE.search(s)
            if pm:
                profiles[pm.group(1)] += 1
            wm = WINNT.search(s)
            if wm:
                profiles[wm.group(1)] += 1
            parts = s.split(BS)
            if len(parts) >= 3:
                roots[BS.join(parts[:3])] += 1

    print("files scanned            : %d" % nfiles)
    print("files containing a path  : %d" % len(hits))
    print("distinct paths           : %d" % len(allpaths))
    print()
    print("drive letters seen:")
    for k, v in drives.most_common():
        print("   %s:  %d occurrences" % (k, v))
    print()
    print("Windows user profiles named in paths:")
    if not profiles:
        print("   (none)")
    for k, v in profiles.most_common():
        print("   %-44s %d" % (k, v))
    print()
    print("path roots (first two components), most common first:")
    for k, v in roots.most_common(30):
        print("   %-56s %d" % (k, v))
    print()
    print("per file, %s:" % ("every path" if full else "up to 4 paths each"))
    for rel in sorted(hits):
        v = hits[rel]
        print("  %s  (%d)" % (rel, len(v)))
        for off, s in (v if full else v[:4]):
            print("      +0x%-8X %s" % (off, s))


if __name__ == "__main__":
    main()
