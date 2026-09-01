#!/usr/bin/env python3
"""vise.py -- pull the file manifest out of a MindVision Installer VISE archive.

`dati/install/883d.exe` is a 16-bit NE whose module name is `VISESTUB` and
whose code segments account for 2.66 % of the file. The other 97 % is the VISE
payload. Most of that payload is compressed and this tool does not decompress
it -- but VISE keeps its **manifest** in the clear, and the manifest is the
interesting part, because it names every file the installer will write and the
directory it will write it to.

The manifest is a run of records. Each record, as far as this tool needs to
care, is a length-prefixed (Pascal) file name followed by a length-prefixed
destination path, followed by binary fields this tool does not interpret --
sizes, dates, CRCs, and offsets into the compressed data. The records are
separated by long runs of 0xFF.

This tool therefore does the smallest honest thing: it walks the file looking
for Pascal strings (a length byte whose value equals the number of printable
bytes that follow it), keeps the ones that look like a file name or a path, and
prints them **in file order** so the directory tree the installer builds can be
read off. It does not claim to have parsed VISE. It claims to have listed the
strings VISE left in the clear, in order, and that claim is checkable.

Why it matters here: the paths reconstruct the layout of an Active Worlds
installation, including a pre-populated `cache\\art\\<world server>` tree. The
world server's hostname is in those paths and nowhere else on the disc.

    python tools/vise.py FILE
    python tools/vise.py FILE --tree
    python tools/vise.py FILE --min 3 --raw
"""
import argparse
import os
import re
import sys

PRINTABLE = set(range(0x20, 0x7F))

# A conservative filename/path shape: letters, digits and the punctuation a
# DOS/Windows path actually uses. Deliberately excludes space-heavy prose so
# that UI strings do not flood the listing.
PATHISH = re.compile(r"^[A-Za-z0-9_.$~!#%()&'+,;=@\-\\/ ]+$")


def pascal_strings(data, minlen):
    """Yield (offset, text) for every length-prefixed printable run."""
    n = len(data)
    i = 0
    while i < n - 1:
        ln = data[i]
        if minlen <= ln <= 200 and i + 1 + ln <= n:
            chunk = data[i + 1:i + 1 + ln]
            if all(c in PRINTABLE for c in chunk):
                yield i, chunk.decode("latin-1")
                i += 1 + ln
                continue
        i += 1


def looks_like_path(s):
    if not PATHISH.match(s):
        return False
    if s.strip() == "":
        return False
    # a bare word with no separator and no dot is probably UI text
    if "\\" in s or "/" in s:
        return True
    if "." in s and " " not in s:
        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--min", type=int, default=3)
    ap.add_argument("--tree", action="store_true")
    ap.add_argument("--raw", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

    data = open(args.file, "rb").read()
    found = list(pascal_strings(data, args.min))

    print("file            : %s" % args.file)
    print("size            : %d bytes" % len(data))
    print("pascal strings  : %d (length prefix >= %d, all bytes printable)"
          % (len(found), args.min))
    print()

    if args.raw:
        for off, s in found:
            print("%08X  %s" % (off, s))
        return

    paths = [(o, s) for o, s in found if looks_like_path(s)]
    print("=== path-shaped strings, in file order: %d ===" % len(paths))
    print()
    print("%-10s %s" % ("offset", "string"))
    for off, s in paths:
        print("%08X   %s" % (off, s))

    if args.tree:
        # Pair each name with the path that immediately follows it, which is
        # the order VISE writes them in. Reported as a pairing, not a parse.
        print()
        print("=== name/destination pairs, by adjacency ===")
        print("(a pairing inferred from file order, not from a parsed record)")
        print()
        dirs = {}
        for i in range(len(paths) - 1):
            name = paths[i][1]
            dest = paths[i + 1][1]
            if ("\\" in dest or dest in ("cache", "misc", "avatars", "models",
                                         "seqs")) and "\\" not in name:
                dirs.setdefault(dest, []).append(name)
        for d in sorted(dirs):
            print("%s" % d)
            for f in dirs[d]:
                print("    %s" % f)
        print()
        print("distinct destinations: %d" % len(dirs))
        print("files placed         : %d" % sum(len(v) for v in dirs.values()))


if __name__ == "__main__":
    main()
