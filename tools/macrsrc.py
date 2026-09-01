#!/usr/bin/env python3
"""macrsrc.py -- read a Macintosh resource fork.

On this disc one HFS file has a data fork of **zero bytes** and a resource fork
of 19,238: `Copiami sull'Hard Disk`, type TEXT, creator ttxt, which is
SimpleText. A tool that measures files by their length would record it as empty.
It is not empty; it is a document whose entire content lives in the fork the
PC side of this disc cannot address, and reading it needs the resource-map
format rather than a text editor.

Sixteen other files on the volume also carry a resource fork, among them the
Macintosh projector (118,795 bytes) and each of the ten Xtras.

    python tools/macrsrc.py FILE.rsrc
    python tools/macrsrc.py FILE.rsrc --type TEXT --dump
    python tools/macrsrc.py FILE.rsrc --type STR# --strings

THE FORMAT, ASSERTED
--------------------
Everything is big-endian. The fork begins with a 16-byte header:

    0   4  offset to the data area
    4   4  offset to the map
    8   4  length of the data area
   12   4  length of the map

Each resource in the data area is a 4-byte length followed by that many bytes.
The map repeats the header, then:

   24   2  offset from the map to the type list
   26   2  offset from the map to the name list
   28   2  number of types, minus one

The type list holds 8-byte entries -- a four-character type, a count minus one,
and an offset from the *type list* to that type's reference list. A reference
list holds 12-byte entries: resource id, an offset into the name list or -1, an
attribute byte, and a 3-byte offset into the data area.

The two "minus one" counts are the reason a resource fork with exactly one type
and one resource looks identical to a corrupt one under a careless reader, so
they are asserted here rather than assumed.
"""
import argparse
import struct
import sys


def macstr(b):
    return b.decode("mac_roman", "replace")


class Fork(object):
    def __init__(self, data):
        self.b = data
        if len(data) < 16:
            raise ValueError("fork is %d bytes, too short for a header" % len(data))
        (self.doff, self.moff, self.dlen, self.mlen) = struct.unpack(">IIII", data[0:16])
        if self.moff + self.mlen > len(data):
            raise ValueError("map at %d+%d runs past the fork's %d bytes"
                             % (self.moff, self.mlen, len(data)))
        m = self.moff
        (self.tloff, self.nloff, ntypes_m1) = struct.unpack(">HHH", data[m + 24:m + 30])
        # The count is stored minus one, so an empty fork -- no types at all --
        # stores 0xFFFF. `DesktopPrinters DB` on this volume is exactly that: a
        # 286-byte fork with a 30-byte map, a zero-length data area and not one
        # resource. Adding one without checking asks for 65,536 type entries and
        # the reader dies on the fourth byte, which is the trap this file's own
        # docstring warns about and the first version of it walked into.
        self.ntypes = 0 if ntypes_m1 == 0xFFFF else ntypes_m1 + 1
        self.types = []
        tl = m + self.tloff
        for i in range(self.ntypes):
            off = tl + 2 + i * 8
            typ = data[off:off + 4]
            cnt_m1, rloff = struct.unpack(">HH", data[off + 4:off + 8])
            refs = []
            rl = tl + rloff
            for j in range(cnt_m1 + 1):
                r = rl + j * 12
                rid, noff = struct.unpack(">hh", data[r:r + 4])
                attrs = data[r + 4]
                doff = struct.unpack(">I", b"\0" + data[r + 5:r + 8])[0]
                name = ""
                if noff >= 0:
                    n = m + self.nloff + noff
                    ln = data[n]
                    name = macstr(data[n + 1:n + 1 + ln])
                body_at = self.doff + doff
                blen = struct.unpack(">I", data[body_at:body_at + 4])[0]
                refs.append({"id": rid, "name": name, "attrs": attrs,
                             "offset": body_at + 4, "length": blen})
            self.types.append({"type": macstr(typ), "count": cnt_m1 + 1,
                               "refs": refs})

    def body(self, ref):
        return self.b[ref["offset"]:ref["offset"] + ref["length"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--type")
    ap.add_argument("--id", type=int)
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--strings", action="store_true",
                    help="decode STR# / STR resources as MacRoman")
    ap.add_argument("--text", action="store_true",
                    help="decode TEXT resources, turning Mac CR into newlines")
    a = ap.parse_args()

    data = open(a.file, "rb").read()
    f = Fork(data)

    print("file        : %s   %d bytes" % (a.file, len(data)))
    print("data area   : offset %d  length %d" % (f.doff, f.dlen))
    print("map         : offset %d  length %d" % (f.moff, f.mlen))
    print("types       : %d" % f.ntypes)
    print()
    print("%-6s %6s %12s  %s" % ("type", "count", "bytes", "ids"))
    tot = 0
    for t in f.types:
        n = sum(r["length"] for r in t["refs"])
        tot += n
        ids = ", ".join(str(r["id"]) for r in t["refs"][:12])
        if len(t["refs"]) > 12:
            ids += ", ..."
        print("%-6s %6d %12d  %s" % (t["type"], t["count"], n, ids))
    print("%-6s %6d %12d" % ("total", sum(t["count"] for t in f.types), tot))
    print()
    print("resource bodies account for %d of the %d bytes of the data area"
          % (tot, f.dlen))

    named = [(t["type"], r) for t in f.types for r in t["refs"] if r["name"]]
    if named:
        print()
        print("named resources:")
        for typ, r in named:
            print("  %-5s %6d  %-30r %d bytes"
                  % (typ, r["id"], r["name"], r["length"]))

    if a.type:
        for t in f.types:
            if t["type"] != a.type:
                continue
            for r in t["refs"]:
                if a.id is not None and r["id"] != a.id:
                    continue
                b = f.body(r)
                print()
                print("--- %s %d %r  %d bytes ---" % (t["type"], r["id"],
                                                      r["name"], r["length"]))
                if a.text or (a.strings and t["type"] == "TEXT"):
                    print(macstr(b).replace("\r", "\n"))
                elif a.strings and t["type"] == "STR#":
                    n = struct.unpack(">H", b[0:2])[0]
                    print("(%d strings)" % n)
                    p = 2
                    for i in range(n):
                        ln = b[p]
                        print("  %3d  %r" % (i + 1, macstr(b[p + 1:p + 1 + ln])))
                        p += 1 + ln
                elif a.strings and t["type"] == "STR ":
                    ln = b[0]
                    print("  %r" % macstr(b[1:1 + ln]))
                elif a.dump:
                    sys.stdout.buffer.write(b)
                else:
                    print(" ".join("%02x" % c for c in b[:64]))


if __name__ == "__main__":
    main()
