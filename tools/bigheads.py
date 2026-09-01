#!/usr/bin/env python3
"""bigheads.py -- the first bytes of the first entry inside each BIG archive.

Naming a format from an extension is a guess. Reading its first sixteen bytes
is a measurement, and it can be had cheaply: every BIG archive puts its first
entry immediately after the table, so decompressing a few kilobytes of the zip
member is enough.

    python tools/bigheads.py _work/iso/0compressed.zip
"""
import struct
import sys
import zipfile

path = sys.argv[1] if len(sys.argv) > 1 else "_work/iso/0compressed.zip"
z = zipfile.ZipFile(path)


def head(member, want):
    with z.open(member) as f:
        out = b""
        while len(out) < want:
            b = f.read(min(1 << 20, want - len(out)))
            if not b:
                break
            out += b
        return out


def table(h):
    n = struct.unpack_from(">I", h, 8)[0]
    p = 16
    ents = []
    for i in range(n):
        off, size = struct.unpack_from(">II", h, p)
        p += 8
        e = h.find(b"\x00", p)
        ents.append((off, size, h[p:e].decode("latin-1")))
        p = e + 1
    return ents


for m in [n for n in z.namelist() if n.lower().endswith(".big")]:
    ents = sorted(table(head(m, 1 << 20)), key=lambda e: e[0])
    o, s, nm = ents[0]
    blob = head(m, o + min(s, 128))[o:o + min(s, 128)]
    print("=== %s : first entry %s (%d bytes at offset %d)" % (m, nm, s, o))
    for i in range(0, min(len(blob), 64), 16):
        r = blob[i:i + 16]
        print("   %4d  %-47s  %s" % (i, " ".join("%02x" % x for x in r),
                                     "".join(chr(x) if 32 <= x < 127 else "." for x in r)))
    print()
