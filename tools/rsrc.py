#!/usr/bin/env python3
"""rsrc.py -- walk a PE resource directory and total the bytes by type.

Written for one question on this disc: `OgrePlatform.dll` ships beside
`OgrePlatform.dll.backup`, the two share a COFF timestamp, a Rich header and
byte-identical code, and only their `.rsrc` sections differ. Comparing the
resource directories says what was changed, which turns out to be one bitmap
and two dialog templates.

It reads the three-level tree the format specifies -- type, then name or id,
then language -- and reports, per type, how many leaves there are and how many
bytes they point at. It does not extract anything.

Caveat that matters on this disc: the twenty-two PE files inside the installer
have been through Inno's call-instruction filter, which this session did not
reverse (docs/11). That rewrites four-byte operands after E8/E9 bytes anywhere
in the file, resources included. Directory *structure* and the lengths in it
come from fields the filter does not touch; the resource *contents* do not.

Usage:
    python tools/rsrc.py FILE [FILE ...]
"""
import struct
import sys

RT = {1: "CURSOR", 2: "BITMAP", 3: "ICON", 4: "MENU", 5: "DIALOG",
      6: "STRING", 7: "FONTDIR", 8: "FONT", 9: "ACCELERATOR", 10: "RCDATA",
      11: "MESSAGETABLE", 12: "GROUP_CURSOR", 14: "GROUP_ICON",
      16: "VERSION", 17: "DLGINCLUDE", 19: "PLUGPLAY", 20: "VXD",
      21: "ANICURSOR", 22: "ANIICON", 23: "HTML", 24: "MANIFEST"}


def sections(d):
    e = struct.unpack_from("<I", d, 0x3C)[0]
    nsec = struct.unpack_from("<H", d, e + 6)[0]
    opt = struct.unpack_from("<H", d, e + 20)[0]
    base = e + 24 + opt
    out = []
    for i in range(nsec):
        o = base + 40 * i
        name = d[o:o + 8].rstrip(b"\x00").decode("ascii", "replace")
        vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", d, o + 8)
        out.append((name, vaddr, vsize, raddr, rsize))
    return out


def entries(d, base, off):
    n_named, n_id = struct.unpack_from("<HH", d, base + off + 12)
    for k in range(n_named + n_id):
        name, child = struct.unpack_from("<II", d, base + off + 16 + 8 * k)
        yield name, child


def one(path):
    with open(path, "rb") as f:
        d = f.read()
    rs = [s for s in sections(d) if s[0] == ".rsrc"]
    print("file        : %s" % path)
    print("size        : %d" % len(d))
    if not rs:
        print("  no .rsrc section")
        return
    name, vaddr, vsize, raddr, rsize = rs[0]
    print("  .rsrc     : vaddr 0x%08X vsize %d rawoff 0x%X rawsize %d"
          % (vaddr, vsize, raddr, rsize))
    base = raddr
    total = 0
    for tname, tchild in entries(d, base, 0):
        label = ("named" if tname & 0x80000000
                 else RT.get(tname, "type %d" % tname))
        leaves = 0
        tbytes = 0
        for _, nchild in entries(d, base, tchild & 0x7FFFFFFF):
            for _, lchild in entries(d, base, nchild & 0x7FFFFFFF):
                o = base + (lchild & 0x7FFFFFFF)
                data_rva, size, codepage, _r = struct.unpack_from("<IIII", d, o)
                leaves += 1
                tbytes += size
        total += tbytes
        print("  %-14s leaves=%-4d bytes=%d" % (label, leaves, tbytes))
    print("  total in leaves : %d" % total)


def main():
    for p in sys.argv[1:]:
        one(p)
        print()


if __name__ == "__main__":
    main()
