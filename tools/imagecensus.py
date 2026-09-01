#!/usr/bin/env python3
"""imagecensus.py -- dimensions and depths of every image outside the zip.

bmp.py reads one BMP thoroughly; jpeg.py reads one JPEG thoroughly. This is the
cheap whole-tree pass that says how many distinct shapes there are, so that the
spec sheet can carry one row per format instead of one row per file.

    python tools/imagecensus.py _work/nozip
"""
import collections
import glob
import os
import struct
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "_work/nozip"


def jpeg(b):
    i = 2
    while i < len(b) - 1:
        if b[i] != 0xFF:
            i += 1
            continue
        m = b[i + 1]
        if m in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack_from(">HH", b, i + 5)
            return w, h, b[i + 9], ("progressive" if m == 0xC2 else "baseline")
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
            i += 2
            continue
        i += 2 + struct.unpack_from(">H", b, i + 2)[0]
    return None


print("=== BMP ===")
c = collections.Counter()
for p in glob.glob(root + "/**/*.bmp", recursive=True):
    d = open(p, "rb").read(64)
    w, h, pl, bpp = struct.unpack_from("<iiHH", d, 18)
    comp = struct.unpack_from("<I", d, 30)[0]
    c[(w, h, bpp, comp, os.path.getsize(p))] += 1
for k, v in c.most_common():
    print("  %dx%d  %d bpp  compression %d  %d bytes   x%d" % (k[0], k[1], k[2], k[3], k[4], v))

print()
print("=== JPEG ===")
c = collections.Counter()
mode = collections.Counter()
for p in glob.glob(root + "/**/*.jpg", recursive=True):
    r = jpeg(open(p, "rb").read(4096))
    if r:
        c[(r[0], r[1], r[2])] += 1
        mode[r[3]] += 1
print("  files %d   modes %s" % (sum(c.values()), dict(mode)))
for k, v in c.most_common():
    print("  %dx%d  %d components   x%d" % (k[0], k[1], k[2], v))

print()
print("=== GIF ===")
c = collections.Counter()
ver = collections.Counter()
for p in glob.glob(root + "/**/*.gif", recursive=True):
    b = open(p, "rb").read(13)
    ver[b[:6].decode("latin-1")] += 1
    c[struct.unpack_from("<HH", b, 6)] += 1
print("  files %d   versions %s   distinct sizes %d" % (sum(c.values()), dict(ver), len(c)))
for k, v in c.most_common(12):
    print("  %dx%d   x%d" % (k[0], k[1], v))

print()
print("=== ICO ===")
c = collections.Counter()
for p in glob.glob(root + "/**/*.ico", recursive=True):
    b = open(p, "rb").read(4096)
    n = struct.unpack_from("<H", b, 4)[0]
    ims = []
    for i in range(n):
        w, h, col, _, pl, bc = struct.unpack_from("<BBBBHH", b, 6 + 16 * i)
        ims.append("%dx%d/%dbpp" % (w or 256, h or 256, bc))
    c[tuple(ims)] += 1
for k, v in c.most_common():
    print("  %-54s x%d" % (", ".join(k), v))

print()
print("=== the readme text files ===")
for p in sorted(glob.glob(root + "/Support/*/*.txt")):
    b = open(p, "rb").read()
    hi = sorted({x for x in b if x > 127})
    print("  %-40s %6d bytes  %3d non-ASCII  %s"
          % (os.path.relpath(p, root), len(b), sum(1 for x in b if x > 127),
             " ".join("%02x" % x for x in hi)))
    print("      %r" % b.split(b"\r\n")[0][:64])
