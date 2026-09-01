#!/usr/bin/env python3
"""mzcensus.py -- the nine executables and the overlay, one line each.

`pe.py` and `ne.py` do not apply here and say so: nothing in this folder is PE
or NE. Everything is a plain DOS `MZ`, which has no build timestamp, no
subsystem, no version block and no import table -- so a census of MZ files is a
census of *arithmetic*, and the arithmetic is the point.

What it prints, and why each column earns its place:

  cblp/cp/img   the MZ header's own statement of how long the load image is.
                `img = (cp-1)*512 + cblp` (or `cp*512` when cblp is 0). Any
                difference between `img` and the file size is data appended
                after the image, which DOS loads for nobody -- the program has
                to read it back itself.
  cblp==size%512  the briefing said `4d 5a 50 00` in CHELINGU.EXE is "MZ
                followed by P", i.e. the Borland Pascal `MZP` marker. It is
                not. `e_cblp` is the file length modulo 512, and CHELINGU.EXE
                is 4,176 bytes, and 4176 mod 512 is 80, and 80 is `P`. This
                column proves it for all nine at once.
  crlc          relocation count. A Turbo Pascal program has hundreds; a
                hand-built stub has one.
  sp            initial stack pointer. Turbo Pascal's default `{$M 16384,...}`
                puts 0x4000 here.
  banner        the compiler's own copyright string, found in the file.
  int3f         count of `CD 3F` byte pairs: in Turbo Pascal, a call to an
                overlaid routine compiles to `INT 3Fh` followed by a four-byte
                descriptor, so this counts overlay call sites.

  usage: mzcensus.py <dir>
"""
import os
import re
import struct
import sys

BANNERS = [
    (b"Portions Copyright (c) 1983,90 Borland", "Turbo Pascal 6.0 runtime"),
    (b"Borland C++ - Copyright 1991 Borland Intl.", "Borland C++ 2.0 (1991)"),
    (b"PKLITE Copr. 1990 PKWARE Inc.", "PKLITE 1.x (PKWARE)"),
    (b"LZ91", "LZEXE 0.91"),
    (b"Runtime error ", "Borland runtime error table"),
]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = sys.argv[1]
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    names = sorted(n for n in os.listdir(root) if n.upper().endswith(".EXE"))
    print("=== the nine MZ executables ===")
    print("%-14s %7s %5s %4s %7s %6s %5s %5s %6s %6s %6s"
          % ("file", "size", "cblp", "cp", "img", "slack", "crlc", "hdr", "cs:ip", "ss:sp", "int3f"))
    tot = 0
    for n in names:
        p = os.path.join(root, n)
        d = open(p, "rb").read()
        tot += len(d)
        (cblp, cp, crlc, cparhdr, minal, maxal, ss, sp, csum, ip,
         cs) = struct.unpack("<11H", d[2:24])
        img = (cp - 1) * 512 + cblp if cblp else cp * 512
        i3f = len(re.findall(re.escape(b"\xcd\x3f"), d))
        print("%-14s %7d %5d %4d %7d %6d %5d %5d  %04x:%04x %04x:%04x %6d"
              % (n, len(d), cblp, cp, img, len(d) - img, crlc, cparhdr * 16,
                 cs, ip, ss, sp, i3f))
    print("total .EXE bytes: %d" % tot)
    print("")

    print("=== e_cblp against the file length modulo 512 ===")
    print("If these agree for all nine, the third byte of the file is arithmetic,")
    print("not a signature, and there is no MZP marker in this folder.")
    agree = 0
    for n in names:
        d = open(os.path.join(root, n), "rb").read()
        cblp = struct.unpack("<H", d[2:4])[0]
        m = len(d) % 512
        agree += (cblp == m)
        print("  %-14s e_cblp=%4d  size mod 512=%4d  %s  byte2=0x%02x %s"
              % (n, cblp, m, "agree" if cblp == m else "DIFFER", d[2],
                 "('%s')" % chr(d[2]) if 32 <= d[2] < 127 else ""))
    print("  %d of %d agree" % (agree, len(names)))
    print("")

    print("=== toolchain banners ===")
    for n in names + ["MM.OVR"]:
        d = open(os.path.join(root, n), "rb").read()
        hits = [(lab, d.find(tok)) for tok, lab in BANNERS if tok in d]
        print("  %-14s %s" % (n, ", ".join("%s @0x%X" % (l, o) for l, o in hits) or "none"))
    print("")

    print("=== MM.OVR, the Borland overlay ===")
    d = open(os.path.join(root, "MM.OVR"), "rb").read()
    sig = d[:4]
    declared = struct.unpack("<I", d[4:8])[0]
    print("  signature      %r" % sig)
    print("  declared size  %d" % declared)
    print("  file size      %d" % len(d))
    print("  declared + 8   %d   closes exactly: %s"
          % (declared + 8, declared + 8 == len(d)))
    print("  first code byte at offset 8: %s  (%s)"
          % (" ".join("%02x" % c for c in d[8:16]),
             "push bp / mov bp,sp -- a standard Borland stack frame"
             if d[8:11] == b"\x55\x89\xe5" else "?"))
    i3f = len(re.findall(re.escape(b"\xcd\x3f"), d))
    print("  CD 3F pairs inside the overlay itself: %d" % i3f)
    print("")

    print("=== third-party software in this folder ===")
    found = []
    for n in sorted(os.listdir(root)):
        d = open(os.path.join(root, n), "rb").read()
        for tok, lab in BANNERS:
            if tok in d and "Borland" not in lab and "runtime" not in lab:
                found.append((n, lab, d.find(tok)))
    for n, lab, o in found:
        print("  %-14s %s at 0x%X" % (n, lab, o))
    print("  files containing a third-party packer or library banner: %d" % len(found))


if __name__ == "__main__":
    main()
