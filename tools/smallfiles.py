#!/usr/bin/env python3
"""smallfiles.py -- the twenty-one files with extensions nobody explains.

Four .ffn, three .256, three .016, ten .lay, one .csv, one .bin, one .cfg,
one .inf. None of these is an extension the Unreal engine or Windows defines.
This opens each, prints its first bytes, its structure if it has one, and says
what it is -- or says that it does not know, which is also an answer.

    python tools/smallfiles.py E:/
"""
import collections
import os
import struct
import sys

EXTS = (".ffn", ".256", ".016", ".lay", ".csv", ".bin", ".cfg", ".inf",
        ".ico", ".ini", ".hdr", ".inx", ".ex_", ".sys")


def bmpinfo(d):
    if d[:2] != b"BM":
        return None
    size, _, _, off = struct.unpack_from("<IHHI", d, 2)
    hs = struct.unpack_from("<I", d, 14)[0]
    if hs >= 40:
        w, h, planes, bpp = struct.unpack_from("<iiHH", d, 18)
        comp = struct.unpack_from("<I", d, 30)[0]
        return ("BMP %dx%d, %d bpp, compression %d, header %d, pixels at %d,"
                " declared size %d" % (w, h, bpp, comp, hs, off, size))
    return "BMP, %d-byte header" % hs


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "E:/"
    found = collections.defaultdict(list)
    for dp, dn, fn in os.walk(root):
        for f in sorted(fn):
            ext = os.path.splitext(f)[1].lower()
            if ext in EXTS:
                p = os.path.join(dp, f)
                found[ext].append(p)

    for ext in EXTS:
        if ext not in found:
            continue
        ps = found[ext]
        print("=" * 70)
        print("%s   %d file(s), %d bytes"
              % (ext, len(ps), sum(os.path.getsize(x) for x in ps)))
        print("=" * 70)
        for p in ps:
            d = open(p, "rb").read()
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            print("  %-44s %8d bytes" % (rel, len(d)))
            b = bmpinfo(d)
            if b:
                print("      %s" % b)
                continue
            head = d[:16]
            print("      first 16: %s  %r"
                  % (head.hex(" "),
                     "".join(chr(c) if 32 <= c < 127 else "." for c in head)))
            printable = sum(1 for c in d if 9 <= c <= 13 or 32 <= c < 127)
            frac = printable / len(d) if d else 0
            print("      printable fraction %.3f -> %s"
                  % (frac, "text" if frac > 0.95 else "binary"))
            if frac > 0.95:
                txt = d.decode("latin-1")
                lines = txt.splitlines()
                print("      %d lines; first three:" % len(lines))
                for l in lines[:3]:
                    print("         %r" % l[:100])
                secs = [l for l in lines if l.startswith("[")]
                if secs:
                    print("      %d section headers: %s"
                          % (len(secs), secs[:8]))
            elif d[:4] == b"FNTF":
                # font file: guess the header layout and print it
                print("      FNTF: next 28 bytes as u32 LE: %s"
                      % [struct.unpack_from("<I", d, 4 + 4 * i)[0]
                         for i in range(7)])
                print("      as u16 LE: %s"
                      % [struct.unpack_from("<H", d, 4 + 2 * i)[0]
                         for i in range(14)])
        print()


if __name__ == "__main__":
    main()
