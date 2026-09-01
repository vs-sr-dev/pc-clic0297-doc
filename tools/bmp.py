#!/usr/bin/env python3
"""bmp.py -- read a Windows BITMAPFILEHEADER + BITMAPINFOHEADER and check that
the arithmetic closes.

The same idea as tga.py from the two earlier discs: header + palette +
width * stride * height must equal the file size, and when it does not, the
difference is the finding rather than an error. On this disc
`logo_installer.bmp` misses by two bytes in two places at once, which is why
this exists.

Row stride is `((width * bpp + 31) // 32) * 4`, which is the padding rule the
format actually specifies rather than the one people remember.

Usage:
    python tools/bmp.py FILE [FILE ...]
"""
import struct
import sys

COMPRESSION = {0: "BI_RGB (none)", 1: "BI_RLE8", 2: "BI_RLE4",
               3: "BI_BITFIELDS", 4: "BI_JPEG", 5: "BI_PNG"}


def one(path):
    with open(path, "rb") as f:
        d = f.read()
    print("file             : %s" % path)
    print("size             : %d bytes" % len(d))
    sig, declared, r1, r2, pix = struct.unpack("<2sIHHI", d[:14])
    print("signature        : %r" % sig)
    print("declared size    : %d   %s"
          % (declared, "== actual" if declared == len(d) else "!= ACTUAL"))
    print("reserved         : %d, %d" % (r1, r2))
    print("pixel data at    : %d" % pix)
    (hs, w, h, planes, bpp, comp, imgsize,
     xppm, yppm, used, important) = struct.unpack("<IiiHHIIiiII", d[14:54])
    print("DIB header size  : %d" % hs)
    print("dimensions       : %d x %d, %d bpp, %d plane(s)" % (w, h, bpp, planes))
    print("compression      : %d %s" % (comp, COMPRESSION.get(comp, "?")))
    print("palette entries  : %d used, %d important" % (used, important))
    stride = ((w * bpp + 31) // 32) * 4
    pixels = stride * abs(h)
    print("row stride       : %d   (%d * %d bits rounded up to 4 bytes)"
          % (stride, w, bpp))
    print("pixel bytes      : %d" % pixels)
    print("biSizeImage      : %d   %s"
          % (imgsize, "== computed" if imgsize == pixels
             else "differs by %+d" % (imgsize - pixels)))
    expected = pix + pixels
    print("pixel offset + pixels : %d   file is %d   %s"
          % (expected, len(d),
             "exact" if expected == len(d) else "differs by %+d"
             % (len(d) - expected)))
    tail = d[expected:]
    if tail:
        print("trailing bytes   : %d  %s   all zero: %s"
              % (len(tail), tail[:16].hex(), not any(tail)))


def main():
    for p in sys.argv[1:]:
        one(p)
        print()


if __name__ == "__main__":
    main()
