#!/usr/bin/env python3
"""vdall.py -- every field of every volume descriptor, from a file, in full.

Written because vdfields.py and vdmatch.py, inherited, carry another disc's
window (bytes 1139..1535) compiled in. On a disc where that window happens to
be zero they print "(none)", which is a true statement about the wrong bytes.
This tool takes no window: it dumps the whole 1,165 bytes of the two fields
ISO 9660 leaves to the implementor -- `application use` (813 bytes at offset
883) and `reserved` (653 bytes at offset 1395) -- and states how many of them
are non-zero, per descriptor, with the offsets.

    python tools/vdall.py _work/clic11.img
    python tools/vdall.py _work/raw --cache

Field offsets are the standard's, 1-based in the text and 0-based here:
  0     type            8     system id (32)
  1..5  'CD001'        40     volume id (32)
  6     version        80     volume space (8, both-endian)
  ...
  318   volume set (128)      446  publisher (128)
  574   data preparer (128)   702  application (128)
  813   copyright file (37)   850  abstract file (37)
  ...
Different sources number these differently; the ones this tool prints are the
ones it can point at in the bytes, and the strings it recovers are the proof.
"""
import argparse
import os
import sys


def both(d, off):
    le = int.from_bytes(d[off:off + 4], "little")
    be = int.from_bytes(d[off + 4:off + 8], "big")
    return le, be


def s(d, off, n):
    return d[off:off + n].decode("latin-1")


def dt(d, off):
    raw = d[off:off + 17]
    if raw[:16] in (b"0" * 16, b" " * 16, b"\x00" * 16):
        return "(not set)", raw
    txt = raw[:16].decode("latin-1")
    off_q = raw[16]
    if off_q > 127:
        off_q -= 256
    return ("%s-%s-%s %s:%s:%s.%s  gmt offset %d (%+.1f h)"
            % (txt[0:4], txt[4:6], txt[6:8], txt[8:10], txt[10:12],
               txt[12:14], txt[14:16], off_q, off_q * 0.25)), raw


def sector(src, n, cache):
    if cache:
        p = os.path.join(src, "%06d.bin" % n)
        return open(p, "rb").read()
    fh = open(src, "rb")
    fh.seek(n * 2048)
    d = fh.read(2048)
    fh.close()
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="image file, or cache dir with --cache")
    ap.add_argument("--cache", action="store_true")
    ap.add_argument("--first", type=int, default=16)
    ap.add_argument("--last", type=int, default=32)
    a = ap.parse_args()

    total_nz = 0
    for n in range(a.first, a.last):
        d = sector(a.src, n, a.cache)
        if d[1:6] != b"CD001":
            continue
        t = d[0]
        name = {0: "boot record", 1: "primary", 2: "supplementary",
                3: "partition", 255: "terminator"}.get(t, "type %d" % t)
        print("=" * 72)
        print("sector %d : %s (type %d)  version %d" % (n, name, t, d[6]))
        if t == 255:
            rest = d[7:]
            print("  remaining %d bytes : %d non-zero"
                  % (len(rest), sum(1 for b in rest if b)))
            continue
        if t not in (1, 2):
            continue
        print("  +8    system id    %r" % s(d, 8, 32))
        print("  +40   volume id    %r" % s(d, 40, 32))
        le, be = both(d, 80)
        print("  +80   volume space %d (LE) / %d (BE)  %s   = %d bytes"
              % (le, be, "agree" if le == be else "DISAGREE", le * 2048))
        if t == 2:
            print("  +88   escape seq   %r" % s(d, 88, 32).rstrip("\x00"))
        print("  +120  set size     %d   +124 seq nr %d"
              % (int.from_bytes(d[120:122], "little"),
                 int.from_bytes(d[124:126], "little")))
        print("  +128  block size   %d"
              % int.from_bytes(d[128:130], "little"))
        print("  +132  path table   %d bytes, LBA L=%d M=%d"
              % (int.from_bytes(d[132:136], "little"),
                 int.from_bytes(d[140:144], "little"),
                 int.from_bytes(d[148:152], "big")))
        for off, nn, label in ((190, 128, "volume set"),
                               (318, 128, "publisher"),
                               (446, 128, "data preparer"),
                               (574, 128, "application"),
                               (702, 37, "copyright file"),
                               (739, 37, "abstract file"),
                               (776, 37, "bibliographic")):
            v = s(d, off, nn)
            print("  +%-4d %-14s %r" % (off, label, v.rstrip(" \x00") or ""))
        for off, label in ((813, "creation"), (830, "modification"),
                           (847, "expiration"), (864, "effective")):
            txt, raw = dt(d, off)
            print("  +%-4d %-14s %s" % (off, label, txt))
        print("  +881  file structure version %d" % d[881])
        print("  +882  reserved byte           %d" % d[882])
        au = d[883:1395]
        rs = d[1395:2048]
        nz_au = [i for i, b in enumerate(au) if b]
        nz_rs = [i for i, b in enumerate(rs) if b]
        total_nz += len(nz_au) + len(nz_rs)
        print("  +883  application use : %d bytes, %d non-zero"
              % (len(au), len(nz_au)))
        if nz_au:
            print("        first non-zero at +%d : %r"
                  % (883 + nz_au[0], au[nz_au[0]:nz_au[0] + 48]))
        print("  +1395 reserved        : %d bytes, %d non-zero"
              % (len(rs), len(nz_rs)))
        if nz_rs:
            print("        first non-zero at +%d : %r"
                  % (1395 + nz_rs[0], rs[nz_rs[0]:nz_rs[0] + 48]))
    print("=" * 72)
    print("total non-zero bytes in application-use + reserved, all descriptors : %d"
          % total_nz)


if __name__ == "__main__":
    main()
