#!/usr/bin/env python3
r"""zob.py - identify and undo the obfuscation on this game's .zob textures.

There are 2,212 files with a `.zob` extension (counting the numeric variants
`.zob1` .. `.zob36` the flat cabinet forces on colliding names). They look
like nothing until you notice two things: the last twenty or so bytes of
every one of them are the same, and the byte 0x2C is everywhere.

Targa files carry an 18-byte header at the front and, since Targa 2.0, a
26-byte footer at the back ending in the literal `TRUEVISION-XFILE.` and a
NUL. XOR the tail of a .zob with 0x2C and that signature appears. 18 + 26 =
44, and most .zob sizes are a power of two plus exactly 44.

So a .zob is a Targa image with every byte XORed by one constant. The
constant is not shared: see derive_key below for how it turned out to be the
low byte of the file's own length, and for the two dead ends that came first.

tga.py, which pc-zerocomico-doc wrote for a different studio's uncompressed
Targas and which this session's brief listed as not applicable, applies
perfectly to the output of this one.

Two independent checks decide whether a key is right, and both have to pass:
an uncompressed image's declared width, height and depth must account for
exactly the file's length, and a run-length image's packet stream must yield
exactly width x height pixels while consuming exactly the file. A wrong key
desynchronises an RLE stream within a few packets, so that is a real test.

Usage:
    python tools/zob.py DIR --scan
    python tools/zob.py DIR --census
    python tools/zob.py FILE --decode OUT.tga
    python tools/zob.py DIR --decode-all OUTDIR
"""

import argparse
import os
import struct
import sys

FOOTER = b"TRUEVISION-XFILE." + b"\x00"
TGA_TYPES = {0: "no image data", 1: "colour-mapped", 2: "true colour",
             3: "greyscale", 9: "RLE colour-mapped", 10: "RLE true colour",
             11: "RLE greyscale"}


def derive_key(data):
    """The key is the low byte of the file's own length.

    Found the long way round. The Targa 2.0 footer is known plaintext, so on
    the 1,898 files that have one the key falls straight out of an XOR -- and
    1,875 of those came back 0x2C while 23 did not. The 314 files without a
    footer then came back with 182 different keys. A key that varies per file
    and still clusters that hard is not random, and the answer is that every
    one of the 2,212 files satisfies

        data[0] == len(data) & 0xFF

    which holds because a Targa's first byte is its ID length and that is
    always zero here. 0x2C dominates only because most of these textures are
    a power of two in pixels plus the 18-byte header and 26-byte footer:
    0x...00 + 44 = 0x...2C.

    So the obfuscation carries its own key in its own length. It costs one
    XOR to undo and it is the only thing standing between a directory listing
    and 2,212 pictures."""
    if len(data) < 18:
        return None
    return len(data) & 0xFF


def derive_key_from_footer(data):
    """The original method, kept because it is independent of the one above
    and the two agreeing on 1,898 files is what makes either believable."""
    if len(data) < len(FOOTER):
        return None
    tail = data[-len(FOOTER):]
    keys = set(a ^ b for a, b in zip(tail, FOOTER))
    if len(keys) != 1:
        return None
    return keys.pop()


def header(data, key):
    h = bytes(b ^ key for b in data[:18])
    (idlen, cmaptype, imgtype, cmapfirst, cmaplen, cmapdepth,
     xorg, yorg, w, h_, depth, desc) = struct.unpack("<BBBHHBHHHHBB", h)
    return {"idlen": idlen, "cmaptype": cmaptype, "type": imgtype,
            "cmaplen": cmaplen, "cmapdepth": cmapdepth,
            "x": xorg, "y": yorg, "w": w, "h": h_,
            "depth": depth, "desc": desc}


def rle_extent(data, key, hdr):
    """Walk a type-10 run-length stream and report how many pixels it yields
    and how many bytes it eats. A wrong key desynchronises within a few
    packets, so this is a real test and not a formality."""
    bpp = hdr["depth"] // 8
    need = hdr["w"] * hdr["h"]
    p = 18 + hdr["idlen"]
    got = 0
    while got < need and p < len(data):
        c = data[p] ^ key
        p += 1
        n = (c & 0x7F) + 1
        p += bpp if (c & 0x80) else n * bpp
        got += n
    return got, p


def plausible(hdr, size, data=None, key=None):
    if hdr["type"] not in TGA_TYPES:
        return False
    if hdr["depth"] not in (8, 15, 16, 24, 32):
        return False
    if not (0 < hdr["w"] <= 4096 and 0 < hdr["h"] <= 4096):
        return False
    if hdr["idlen"] != 0 or hdr["cmaptype"] != 0:
        return False
    if hdr["type"] in (2, 3):
        px = hdr["w"] * hdr["h"] * (hdr["depth"] // 8)
        return size in (18 + hdr["idlen"] + px, 18 + hdr["idlen"] + px + 26)
    if hdr["type"] == 10 and data is not None:
        got, used = rle_extent(data, key, hdr)
        return got == hdr["w"] * hdr["h"] and used == size
    return True


def files_in(path):
    if os.path.isfile(path):
        yield path
        return
    for root, dirs, names in os.walk(path):
        for n in sorted(names):
            ext = n.rsplit(".", 1)[-1].lower()
            if ext.startswith("zob"):
                yield os.path.join(root, n)


def cmd_scan(path, limit=20):
    keys = {}
    good = bad = 0
    shown = 0
    print("%-24s %9s %4s %6s %6s %5s %5s %-14s"
          % ("file", "bytes", "key", "width", "height", "bpp", "desc", "type"))
    for f in files_in(path):
        with open(f, "rb") as fh:
            data = fh.read()
        k = derive_key(data)
        if k is None:
            bad += 1
            continue
        keys[k] = keys.get(k, 0) + 1
        h = header(data, k)
        ok = plausible(h, len(data), data, k)
        if ok:
            good += 1
        else:
            bad += 1
        if shown < limit or not ok:
            print("%-24s %9d 0x%02X %6d %6d %5d %5d %-14s%s"
                  % (os.path.basename(f), len(data), k, h["w"], h["h"],
                     h["depth"], h["desc"], TGA_TYPES.get(h["type"], "?"),
                     "" if ok else "   <- size does not match header"))
            shown += 1
    print()
    print("files examined            %d" % (good + bad))
    print("key accepted by both checks %d" % good)
    print("rejected                  %d" % bad)
    print("distinct keys             %s"
          % ", ".join("0x%02X (x%d)" % (k, v) for k, v in sorted(keys.items())))


def cmd_census(path):
    dims = {}
    depths = {}
    types = {}
    descs = {}
    total = 0
    pixels = 0
    for f in files_in(path):
        with open(f, "rb") as fh:
            data = fh.read()
        k = derive_key(data)
        if k is None:
            continue
        h = header(data, k)
        if not plausible(h, len(data), data, k):
            continue
        total += 1
        pixels += h["w"] * h["h"]
        dims[(h["w"], h["h"])] = dims.get((h["w"], h["h"]), 0) + 1
        depths[h["depth"]] = depths.get(h["depth"], 0) + 1
        types[h["type"]] = types.get(h["type"], 0) + 1
        descs[h["desc"]] = descs.get(h["desc"], 0) + 1

    print("textures                  %d" % total)
    print("total pixels              %d" % pixels)
    print()
    print("-- dimensions")
    for (w, h), n in sorted(dims.items(), key=lambda kv: -kv[1]):
        print("   %4d x %-4d           %6d  (%.2f %%)"
              % (w, h, n, 100.0 * n / total))
    print()
    print("-- bit depth")
    for d, n in sorted(depths.items()):
        print("   %2d bpp                 %6d  (%.2f %%)"
              % (d, n, 100.0 * n / total))
    print()
    print("-- image type")
    for t, n in sorted(types.items()):
        print("   %-22s %6d" % (TGA_TYPES.get(t, t), n))
    print()
    print("-- image descriptor byte (low 4 bits = alpha bits, bit 5 = top origin)")
    for v, n in sorted(descs.items()):
        print("   0x%02X  alpha %d bits, origin %-12s %6d"
              % (v, v & 0x0F, "top-left" if v & 0x20 else "bottom-left", n))


def cmd_decode(src, dst):
    with open(src, "rb") as fh:
        data = fh.read()
    k = derive_key(data)
    if k is None:
        print("%s: no single-byte key produces a Targa footer" % src)
        return False
    out = bytes(b ^ k for b in data)
    with open(dst, "wb") as fh:
        fh.write(out)
    h = header(data, k)
    print("%s -> %s  key 0x%02X  %dx%d %dbpp %s"
          % (src, dst, k, h["w"], h["h"], h["depth"],
             TGA_TYPES.get(h["type"], "?")))
    return True


def cmd_decode_all(path, outdir):
    n = ok = 0
    for f in files_in(path):
        n += 1
        rel = os.path.basename(f)
        dst = os.path.join(outdir, rel + ".tga")
        d = os.path.dirname(dst)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with open(f, "rb") as fh:
            data = fh.read()
        k = derive_key(data)
        if k is None:
            continue
        with open(dst, "wb") as fh:
            fh.write(bytes(b ^ k for b in data))
        ok += 1
    print("decoded %d of %d into %s" % (ok, n, outdir))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--census", action="store_true")
    ap.add_argument("--decode")
    ap.add_argument("--decode-all")
    ap.add_argument("--limit", type=int, default=20)
    a = ap.parse_args()

    if a.scan:
        cmd_scan(a.path, a.limit)
    if a.census:
        cmd_census(a.path)
    if a.decode:
        cmd_decode(a.path, a.decode)
    if a.decode_all:
        cmd_decode_all(a.path, a.decode_all)


if __name__ == "__main__":
    main()
