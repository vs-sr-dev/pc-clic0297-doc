#!/usr/bin/env python3
"""tga.py -- Targa header reader. 1,433 files, 12.21 % of the disc.

Reads the 18-byte header, the optional 26-byte v2 footer, and the ID field,
and checks the arithmetic: for an uncompressed image, header + id + palette +
width*height*bytes_per_pixel + footer must equal the file size exactly. When
it does not, either the image is RLE or the file is not what it claims, and
this reports which.

The point of running it over all 1,433 is to answer three questions at once:
how many distinct pixel formats an artist team used, whether anybody turned
RLE on, and which files are too small to contain an image at all.

    python tools/tga.py DIR --summary
    python tools/tga.py DIR --broken
    python tools/tga.py FILE
"""
import os
import struct
import sys
from collections import Counter, defaultdict

TYPE = {0: "no image data", 1: "colour-mapped", 2: "true colour",
        3: "greyscale", 9: "RLE colour-mapped", 10: "RLE true colour",
        11: "RLE greyscale"}


def read(path):
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        h = fh.read(18)
        if len(h) < 18:
            return dict(path=path, size=size, ok=False, why="shorter than "
                        "an 18-byte header")
        (idlen, cmaptype, imgtype, cmapfirst, cmaplen, cmapbits,
         x0, y0, w, hgt, bits, desc) = struct.unpack("<BBBHHBHHHHBB", h)
        idfield = fh.read(idlen)
        fh.seek(max(0, size - 26))
        foot = fh.read(26)
    v2 = foot[8:] == b"TRUEVISION-XFILE.\x00"
    bypp = (bits + 7) // 8
    cmapbytes = cmaplen * ((cmapbits + 7) // 8) if cmaptype else 0
    pixels = w * hgt * bypp
    expect = 18 + idlen + cmapbytes + pixels + (26 if v2 else 0)
    return dict(path=path, size=size, ok=True, idlen=idlen,
                cmaptype=cmaptype, imgtype=imgtype, cmaplen=cmaplen,
                cmapbits=cmapbits, w=w, h=hgt, bits=bits, desc=desc,
                alpha=desc & 0x0F, origin=(desc >> 4) & 3,
                v2=v2, idfield=idfield, expect=expect, pixels=pixels,
                exact=(expect == size), rle=(imgtype in (9, 10, 11)))


def collect(root):
    out = []
    if os.path.isfile(root):
        return [read(root)]
    for dp, _dn, fns in os.walk(root):
        for fn in sorted(fns):
            if not fn.lower().endswith(".tga"):
                continue
            out.append(read(os.path.join(dp, fn)))
    return out


def summary(root):
    rows = collect(root)
    good = [r for r in rows if r["ok"]]
    print("files                     : %d" % len(rows))
    print("bytes                     : %d" % sum(r["size"] for r in rows))
    print("header readable           : %d" % len(good))
    print()
    c = Counter((r["imgtype"], r["bits"]) for r in good)
    print("%-24s %5s %6s %13s" % ("image type / depth", "n", "share", "bytes"))
    tot = sum(r["size"] for r in good)
    for (t, b), n in c.most_common():
        by = sum(r["size"] for r in good
                 if r["imgtype"] == t and r["bits"] == b)
        print("%-24s %5d %5.1f%% %13d" % (
            "%s, %d bpp" % (TYPE.get(t, "type %d" % t), b), n,
            100.0 * n / len(good), by))
    print()
    print("RLE-compressed            : %d  (%.2f %%)" % (
        sum(1 for r in good if r["rle"]),
        100.0 * sum(1 for r in good if r["rle"]) / len(good)))
    print("with a v2 footer          : %d" % sum(1 for r in good if r["v2"]))
    print("with a non-empty ID field : %d" % sum(
        1 for r in good if r["idlen"]))
    print("with a colour map         : %d" % sum(
        1 for r in good if r["cmaptype"]))
    print("with an alpha channel     : %d" % sum(
        1 for r in good if r["alpha"]))
    print("size arithmetic exact     : %d of %d" % (
        sum(1 for r in good if r["exact"]), len(good)))
    print()
    c = Counter((r["w"], r["h"]) for r in good if r["exact"])
    print("%-16s %6s   %s" % ("resolution", "n", "note"))
    for (w, h), n in c.most_common(24):
        note = ""
        if w and h and (w & (w - 1)) == 0 and (h & (h - 1)) == 0:
            note = "power of two"
        print("%-16s %6d   %s" % ("%d x %d" % (w, h), n, note))
    if len(c) > 24:
        print("... %d more distinct sizes" % (len(c) - 24))
    print()
    pot = sum(1 for r in good if r["exact"] and r["w"] and r["h"]
              and (r["w"] & (r["w"] - 1)) == 0 and (r["h"] & (r["h"] - 1)) == 0)
    print("both dimensions a power of two: %d of %d (%.1f %%)" % (
        pot, sum(1 for r in good if r["exact"]),
        100.0 * pot / max(1, sum(1 for r in good if r["exact"]))))
    print("  (a software texture mapper needs this; a 2D blitter does not)")
    print()
    px = sum(r["pixels"] for r in good if r["exact"])
    print("total decoded pixel bytes : %d" % px)
    print("total file bytes          : %d" % tot)
    print("overhead (headers etc.)   : %d" % (tot - px))
    print()
    ids = Counter(bytes(r["idfield"]) for r in good if r["idlen"])
    if ids:
        print("ID field contents:")
        for k, n in ids.most_common(10):
            print("   x%-5d %r" % (n, k))


def broken(root):
    rows = collect(root)
    bad = [r for r in rows if not r["ok"] or not r["exact"]]
    print("%-64s %9s %9s %-22s %s" % (
        "file", "size", "expected", "declared", "why"))
    for r in sorted(bad, key=lambda x: x["size"]):
        if not r["ok"]:
            print("%-64s %9d %9s %-22s %s" % (
                r["path"], r["size"], "-", "-", r["why"]))
            continue
        why = "RLE, so the size cannot be predicted" if r["rle"] else \
            ("declares 0 pixels" if r["pixels"] == 0 else
             "size does not match the header")
        print("%-64s %9d %9d %-22s %s" % (
            r["path"], r["size"], r["expect"],
            "%dx%d %dbpp type %d" % (r["w"], r["h"], r["bits"],
                                     r["imgtype"]), why))
    print()
    print("files whose size does not match their header: %d of %d" % (
        len(bad), len(rows)))


def one(path):
    r = read(path)
    if not r["ok"]:
        print("%s: %s" % (path, r["why"]))
        return
    print("file            : %s" % r["path"])
    print("size            : %d bytes" % r["size"])
    print("id field length : %d  %r" % (r["idlen"], bytes(r["idfield"])))
    print("colour map type : %d  (%d entries of %d bits)" % (
        r["cmaptype"], r["cmaplen"], r["cmapbits"]))
    print("image type      : %d %s" % (r["imgtype"],
                                       TYPE.get(r["imgtype"], "?")))
    print("dimensions      : %d x %d, %d bits per pixel" % (
        r["w"], r["h"], r["bits"]))
    print("descriptor      : 0x%02X  alpha bits %d  origin %d" % (
        r["desc"], r["alpha"], r["origin"]))
    print("v2 footer       : %s" % r["v2"])
    print("pixel bytes     : %d" % r["pixels"])
    print("expected size   : %d  -> %s" % (
        r["expect"], "EXACT" if r["exact"] else
        "differs by %d" % (r["size"] - r["expect"])))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    t = sys.argv[1]
    if "--summary" in sys.argv:
        summary(t)
    elif "--broken" in sys.argv:
        broken(t)
    else:
        one(t)


if __name__ == "__main__":
    main()
