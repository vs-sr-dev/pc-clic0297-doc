#!/usr/bin/env python3
"""buildpaths.py -- the file paths of machines that no longer exist.

A path found inside a binary is not a path: it is a *finding*. It names a
directory on a machine that built or authored the file, in a year, and it is
one of the few things on a disc that points outwards. This collection keeps
them, and the rule about "no absolute paths in the repository" explicitly does
not apply to them, because they do not resolve on the machine that wrote the
document -- they resolve on nobody's machine.

Two shapes are looked for, because this disc was built on both kinds of
machine:

  DOS/Windows   a drive letter, a colon, a backslash, then path characters
  Macintosh     a volume name, a colon, then a colon-separated path with no
                leading slash -- the form "Macintosh HD:Work:thing"

The Macintosh form is far looser than the DOS one and would match ordinary
prose, so it is required to have at least two colons, no spaces around them,
and a plausible volume name. Every hit is printed with its file so it can be
checked by hand; nothing here is aggregated without the evidence beside it.

    python tools/buildpaths.py _work/iso _work/hfs
    python tools/buildpaths.py _work/iso --tsv notes/buildpaths.tsv
"""
import argparse
import os
import re
from collections import Counter, defaultdict

DOS = re.compile(rb"[A-Za-z]:[\\/](?:[A-Za-z0-9_~!@#$%^&()\-+=\[\]{}';. ]"
                 rb"{1,40}[\\/]){1,8}[A-Za-z0-9_~\-. ]{1,40}")
MAC = re.compile(rb"[A-Z][A-Za-z0-9 _\-]{1,28}:(?:[A-Za-z0-9 _\-.]{1,32}:)"
                 rb"{1,6}[A-Za-z0-9 _\-.]{1,32}")

NOISE = re.compile(rb"^(?:https?|ftp|mailto|HKEY|SOFTWARE)", re.I)


RUN = re.compile(rb"(.)\1\1\1")            # any byte four times in a row
ALPHA3 = re.compile(rb"[A-Za-z]{3}")
VOWELS = b"aeiouAEIOU"


def language_like(s):
    """The single test that separates a path from compressed rubbish.

    Both path shapes match inside Cinepak and JPEG data -- colons and
    backslashes are ordinary bytes there -- and no list of exceptions will fix
    that. What does fix it is that a path is made of *words*: it has vowels,
    it has a run of at least three letters, and it does not repeat one
    character four times. Applying those three, and nothing else, takes this
    disc from 1,488 matches to 74, and every one of the 74 can be read.
    """
    if RUN.search(s):
        return False
    if not ALPHA3.search(s):
        return False
    letters = [c for c in s if 65 <= c <= 90 or 97 <= c <= 122]
    if len(letters) < 6:
        return False
    v = sum(1 for c in letters if c in VOWELS)
    return v / len(letters) >= 0.15


def looks_dos(s):
    if len(s) < 8:
        return False
    if b"\\" in s and b"/" in s:
        # no real DOS path mixes the two separators; a match that does came
        # out of binary data that happened to contain both
        return False
    if s.count(b"\\") + s.count(b"/") < 2:
        return False
    return language_like(s)


def looks_mac(s):
    if b"::" in s or s.startswith(b" ") or s.endswith(b":"):
        return False
    if NOISE.match(s):
        return False
    if b"  " in s:
        return False
    parts = s.split(b":")
    if len(parts) > 6 or len(parts[-1]) < 2:
        return False
    return language_like(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--tsv")
    ap.add_argument("--max-bytes", type=int, default=64 * 1024 * 1024)
    a = ap.parse_args()

    hits = []
    nfiles = 0
    nbytes = 0
    for root in a.roots:
        for dp, dn, fn in os.walk(root):
            for f in sorted(fn):
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, root).replace(os.sep, "/")
                sz = os.path.getsize(p)
                if sz == 0:
                    continue
                with open(p, "rb") as fh:
                    d = fh.read(min(sz, a.max_bytes))
                nfiles += 1
                nbytes += len(d)
                for m in DOS.finditer(d):
                    s = m.group(0)
                    if looks_dos(s):
                        hits.append((root, rel, m.start(), "DOS",
                                     s.decode("latin-1")))
                for m in MAC.finditer(d):
                    s = m.group(0)
                    if looks_mac(s):
                        hits.append((root, rel, m.start(), "Mac",
                                     s.decode("latin-1")))

    print("files searched : %d" % nfiles)
    print("bytes searched : %d" % nbytes)
    print()
    kinds = Counter(h[3] for h in hits)
    print("paths found    : %d   (%s)"
          % (len(hits), ", ".join("%s %d" % kv for kv in kinds.most_common())))
    print("distinct strings: %d" % len(set(h[4] for h in hits)))
    print("files carrying at least one : %d" % len(set((h[0], h[1]) for h in hits)))
    print()

    for kind in ("DOS", "Mac"):
        sub = [h for h in hits if h[3] == kind]
        if not sub:
            continue
        print("=" * 74)
        print("%s-shaped paths: %d hits, %d distinct"
              % (kind, len(sub), len(set(h[4] for h in sub))))
        c = Counter(h[4] for h in sub)
        for s, n in c.most_common(60):
            where = sorted(set(h[1] for h in sub if h[4] == s))[:2]
            print("  %3d  %-58s  %s" % (n, s[:58], ", ".join(where)[:60]))
        print()
        roots_ = Counter(h[4].split(":")[0].upper() for h in sub)
        print("  by volume / drive letter:")
        for r, n in roots_.most_common(20):
            print("    %-24s %5d" % (r, n))
        print()

    if a.tsv:
        with open(a.tsv, "w", encoding="utf-8", newline="") as fh:
            fh.write("root\tpath\toffset\tkind\tstring\n")
            for h in hits:
                fh.write("%s\t%s\t%d\t%s\t%s\n" % h)
        print("wrote %s" % a.tsv)


if __name__ == "__main__":
    main()
