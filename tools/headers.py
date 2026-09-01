#!/usr/bin/env python3
"""headers.py -- the first N bytes of every file, grouped by extension.

This is the base document of the session. Before any interpretation: what does
each of the twenty-one extensions actually start with, and do the files inside
one extension agree with each other?

For each extension it prints every file's first N bytes as hex and as printable
ASCII, plus the file size and, where the leading bytes decode as two or three
little-endian 16-bit words, those words in decimal -- because on this material
that is the single most common header idea and reading it as decimal is what
makes `40 01 c8 00` say "320 200" out loud.

At the end it prints an agreement summary: for each extension, how many
distinct 4-byte and 8-byte prefixes exist among its files. An extension with
one distinct prefix is one format. An extension with N distinct prefixes for N
files is either N formats or a header that starts with content.

  usage: headers.py <dir> [--n 16] [--ext .FL] [--summary]
"""
import os
import struct
import sys
from collections import defaultdict


def printable(b):
    return "".join(chr(c) if 32 <= c < 127 else "." for c in b)


def words(b):
    n = len(b) // 2
    return struct.unpack("<%dH" % n, b[:n * 2])


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    root = args[0]
    n = 16
    want = None
    summary_only = False
    if "--n" in args:
        n = int(args[args.index("--n") + 1])
    if "--ext" in args:
        want = args[args.index("--ext") + 1].lower()
    if "--summary" in args:
        summary_only = True

    byext = defaultdict(list)
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if not os.path.isfile(full):
            continue
        ext = os.path.splitext(name)[1].lower() or "(none)"
        with open(full, "rb") as fh:
            head = fh.read(n)
        byext[ext].append((name, os.path.getsize(full), head))

    order = sorted(byext, key=lambda e: (-sum(s for _, s, _ in byext[e]), e))

    if not summary_only:
        for ext in order:
            if want and ext != want:
                continue
            rows = byext[ext]
            print("=== %s === %d file(s)" % (ext, len(rows)))
            for name, size, head in rows:
                hx = " ".join("%02x" % c for c in head)
                w = words(head[:8])
                print("  %-14s %8d  %-*s |%s|  w=%s"
                      % (name, size, n * 3 - 1, hx, printable(head),
                         " ".join(str(x) for x in w)))
            print("")

    print("=== agreement ===")
    print("%-8s %5s %8s %8s   %s" % ("ext", "files", "pfx4", "pfx8", "distinct 4-byte prefixes"))
    for ext in order:
        rows = byext[ext]
        p4 = sorted({bytes(h[:4]) for _, _, h in rows})
        p8 = {bytes(h[:8]) for _, _, h in rows}
        show = ", ".join("%s" % " ".join("%02x" % c for c in p) for p in p4[:4])
        if len(p4) > 4:
            show += ", ... (%d total)" % len(p4)
        print("%-8s %5d %8d %8d   %s" % (ext, len(rows), len(p4), len(p8), show))


if __name__ == "__main__":
    main()
