#!/usr/bin/env python3
"""szdd.py -- census the files Microsoft's compressors made, without expanding one.

An installation disc of the 1990s is full of files whose last extension
character is an underscore: DL_, EX_, NL_, HL_. The convention is older and
looser than the format, so the underscore is a *claim* and the header is the
*fact*, and this tool only reports the header.

The first version of this tool assumed one format and got a wrong answer for a
right reason: it read every container as SZDD, and SZDD's "uncompressed length"
field lands, in the other format, on two length-2 fields that mean something
else. It reported files that had grown under compression. **Two** formats
answer to the underscore convention and they must be told apart:

  SZDD   53 5A 44 44 88 F0 27 33   compress.exe, undone by expand.exe
         +8   compression mode, one byte, 'A' is the only mode ever shipped
         +9   the last character of the original file name, or 0x00 if the
              tool was not told it -- the rest of the name is the container's
         +10  the uncompressed length, four bytes little-endian
         14 bytes of header, then LZ77 with a 4 KB ring buffer

  KWAJ   4B 57 41 4A 88 F0 27 D1   the compressor of the MS-DOS 6 and
         Video for Windows setups
         +8   method, two bytes: 0 store, 1 XOR, 2 ?, 3 LZH, 4 MSZIP
         +10  offset of the compressed data
         +12  flags, two bytes; bit 0 means an uncompressed length follows,
              bit 3 a file name, bit 4 an extension
         With flags 0 there is no declared length at all, and this tool says
         so rather than inventing one.

Every number printed here is in the header. An SZDD length is *declared*, not
measured; nothing here expands a byte to check it, which is why the column is
labelled "declared".

    python tools/szdd.py _work/iso
    python tools/szdd.py _work/iso --list
    python tools/szdd.py _work/iso --tsv notes/szdd.tsv
"""
import argparse
import os
import struct
from collections import Counter

SZDD = b"SZDD\x88\xf0\x27\x33"
SZ20 = b"SZ\x20\x88\xf0\x27\x33\xd1"
KWAJ = b"KWAJ\x88\xf0\x27\xd1"

KWAJ_METHOD = {0: "store", 1: "xor", 2: "m2", 3: "LZH", 4: "MSZIP"}


def probe(path):
    """-> (format, detail, declared_len_or_None)"""
    with open(path, "rb") as fh:
        h = fh.read(16)
    if h[:8] == SZDD:
        mode = chr(h[8]) if 32 <= h[8] < 127 else "\\x%02x" % h[8]
        last = "\\x%02x" % h[9] if not (32 <= h[9] < 127) else chr(h[9])
        return ("SZDD", "mode %s, last char %s" % (mode, last),
                struct.unpack("<I", h[10:14])[0])
    if h[:8] == SZ20:
        return ("SZ20", "", struct.unpack("<I", h[10:14])[0])
    if h[:8] == KWAJ:
        meth, off, flags = struct.unpack("<HHH", h[8:14])
        det = "method %d (%s), data at +%d, flags 0x%04x" % (
            meth, KWAJ_METHOD.get(meth, "?"), off, flags)
        dec = None
        if flags & 1:
            with open(path, "rb") as fh:
                fh.seek(14)
                dec = struct.unpack("<I", fh.read(4))[0]
        return ("KWAJ", det, dec)
    return (None, "", None)


def underscore(name):
    stem, ext = os.path.splitext(name)
    return len(ext) >= 2 and ext.endswith("_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--tsv")
    a = ap.parse_args()

    hits, misses, sneaks = [], [], []
    for dp, dn, fn in os.walk(a.root):
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, a.root).replace(os.sep, "/")
            sz = os.path.getsize(p)
            fmt, det, dec = probe(p) if sz >= 16 else (None, "", None)
            if fmt:
                rec = (rel, sz, fmt, det, dec)
                hits.append(rec)
                if not underscore(f):
                    sneaks.append(rec)
            elif underscore(f):
                misses.append((rel, sz))

    if a.list:
        print("%-52s %10s %6s %12s  %s"
              % ("path", "on disc", "format", "declared", "detail"))
        for rel, sz, fmt, det, dec in sorted(hits):
            print("%-52s %10d %6s %12s  %s"
                  % (rel, sz, fmt, "-" if dec is None else dec, det))
        print()

    print("=" * 76)
    print("names ending in an underscore : %d"
          % (len([h for h in hits if underscore(h[0])]) + len(misses)))
    print("of those, a Microsoft container : %d"
          % len([h for h in hits if underscore(h[0])]))
    print("of those, NOT a container       : %d" % len(misses))
    for rel, sz in sorted(misses):
        print("   %-52s %10d" % (rel, sz))
    print("containers NOT ending in an underscore : %d" % len(sneaks))
    for rel, sz, fmt, det, dec in sorted(sneaks):
        print("   %-52s %10d  %s" % (rel, sz, fmt))
    print()

    byfmt = Counter(h[2] for h in hits)
    print("by container format:")
    print("  %-6s %6s %12s %12s  %s"
          % ("format", "n", "on disc", "declared", "note"))
    for fmt, n in byfmt.most_common():
        on = sum(h[1] for h in hits if h[2] == fmt)
        decs = [h[4] for h in hits if h[2] == fmt and h[4] is not None]
        note = ("%d of %d declare a length" % (len(decs), n)) if len(decs) < n \
            else "all declare a length"
        print("  %-6s %6d %12d %12s  %s"
              % (fmt, n, on, sum(decs) if decs else "-", note))
    print()

    szd = [h for h in hits if h[4] is not None]
    if szd:
        on = sum(h[1] for h in szd)
        dec = sum(h[4] for h in szd)
        print("over the %d containers that declare a length:" % len(szd))
        print("  bytes on the disc     : %d" % on)
        print("  bytes declared inside : %d" % dec)
        print("  stored at             : %.2f %% of the original" % (100.0 * on / dec))
        print("  bytes the disc saved  : %d" % (dec - on))
        grew = [h for h in szd if h[1] >= h[4]]
        print("  containers not smaller than their declared content : %d" % len(grew))
        for h in grew:
            print("     %-52s %10d >= %d" % (h[0], h[1], h[4]))
    print()

    print("where they live (top-level folder):")
    tl = Counter(h[0].split("/")[0] for h in hits)
    tf = Counter()
    for h in hits:
        tf[(h[0].split("/")[0], h[2])] += 1
    for k, n in tl.most_common():
        detail = ", ".join("%s %d" % (f, c) for (t, f), c in
                           sorted(tf.items()) if t == k)
        print("  %-20s %4d   (%s)" % (k, n, detail))
    print()
    print("by extension of the container:")
    ce = Counter(os.path.splitext(h[0])[1].lower() for h in hits)
    for e, n in ce.most_common():
        fmts = sorted(set(h[2] for h in hits
                          if os.path.splitext(h[0])[1].lower() == e))
        print("  %-8s %6d  %s" % (e, n, "/".join(fmts)))

    if a.tsv:
        with open(a.tsv, "w", encoding="utf-8", newline="") as fh:
            fh.write("path\ton_disc\tformat\tdeclared\tdetail\n")
            for rel, sz, fmt, det, dec in sorted(hits):
                fh.write("%s\t%d\t%s\t%s\t%s\n"
                         % (rel, sz, fmt, "" if dec is None else dec, det))
        print()
        print("wrote %s" % a.tsv)


if __name__ == "__main__":
    main()
