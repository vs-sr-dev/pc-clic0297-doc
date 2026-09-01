#!/usr/bin/env python3
"""hunt.py - look for a list of tokens as printable strings, not as bytes.

The wrong way to ask "is there any PlayStation toolchain in here" is to grep
the files. Compressed and encoded payload contains every four-byte sequence
sooner or later, and a case-insensitive grep over 2,954 files reported hits
for `SCES`, `SLES`, `SLUS` and `PsyQ` that were all noise.

The right way is to extract printable runs first -- the same rule strdump.py
uses -- and search those, then report where each hit landed so it can be
looked at. A token that appears only inside a file that is itself compressed
is reported separately, because a hit inside a deflate stream is not a
string.

Usage:
    python tools/hunt.py DIR --tokens A B C ...
    python tools/hunt.py DIR --tokens-file FILE
    python tools/hunt.py DIR --tokens A B --min 4 --context
"""

import argparse
import os
import re

RUN = re.compile(rb"[\x20-\x7e]{4,}")

# extensions whose contents are compressed or encoded, so a printable run
# inside them is not evidence of anything
OPAQUE = ("cab", "ogg", "lol", "msi", "zob", "jpg", "gif", "png", "zip")


def runs(path, minlen):
    with open(path, "rb") as fh:
        d = fh.read()
    for m in RUN.finditer(d):
        s = m.group()
        if len(s) >= minlen:
            yield m.start(), s.decode("latin-1")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--tokens", nargs="*", default=[])
    ap.add_argument("--tokens-file")
    ap.add_argument("--min", type=int, default=4)
    ap.add_argument("--context", action="store_true")
    ap.add_argument("--case-sensitive", action="store_true")
    a = ap.parse_args()

    tokens = list(a.tokens)
    if a.tokens_file:
        with open(a.tokens_file) as fh:
            tokens += [l.strip() for l in fh if l.strip()]
    if not tokens:
        ap.error("no tokens")

    hits = {t: [] for t in tokens}
    opaque_hits = {t: 0 for t in tokens}
    files = 0
    scanned_runs = 0

    for d in a.dirs:
        walk = [(d, [], [os.path.basename(d)])] if os.path.isfile(d) \
            else os.walk(d)
        for r, _dirs, names in walk:
            root = os.path.dirname(d) if os.path.isfile(d) else r
            for n in sorted(names):
                p = os.path.join(root, n)
                if not os.path.isfile(p):
                    continue
                files += 1
                ext = n.rsplit(".", 1)[-1].lower() if "." in n else ""
                opaque = any(ext.startswith(o) for o in OPAQUE)
                for off, s in runs(p, a.min):
                    scanned_runs += 1
                    hay = s if a.case_sensitive else s.lower()
                    for t in tokens:
                        needle = t if a.case_sensitive else t.lower()
                        if needle in hay:
                            if opaque:
                                opaque_hits[t] += 1
                            elif len(hits[t]) < 40:
                                hits[t].append((p, off, s))

    print("files scanned            %d" % files)
    print("printable runs >= %-2d     %d" % (a.min, scanned_runs))
    print("case sensitive           %s" % a.case_sensitive)
    print()
    print("%-16s %8s   %s" % ("token", "hits", "where"))
    print("-" * 72)
    for t in tokens:
        n = len(hits[t])
        extra = ("  (+%d inside compressed/encoded files, not strings)"
                 % opaque_hits[t]) if opaque_hits[t] else ""
        print("%-16s %8d%s" % (t, n, extra))
        for p, off, s in hits[t][:8 if a.context else 3]:
            print("      %s +0x%X" % (os.path.basename(p), off))
            if a.context:
                print("         %s" % s[:100])


if __name__ == "__main__":
    main()
