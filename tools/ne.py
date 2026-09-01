#!/usr/bin/env python3
"""ne.py -- read 16-bit New Executable files, because pe.py correctly refuses.

`dati/install/883d.exe` is 3,811,012 bytes, starts `MZ`, and at the offset its
DOS header points to has `NE` rather than `PE`. It is a 16-bit Windows binary
on a CD mastered in October 1999. `pe.py` stops with "no PE signature at
e_lfanew=128", which is the right thing for it to do and is also not an answer,
so this reads the other format.

The NE header (all offsets relative to the `NE` signature, all little-endian):

    0x00 WORD  magic 'NE'          0x02 BYTE  linker version
    0x03 BYTE  linker revision     0x04 WORD  entry table offset
    0x06 WORD  entry table length  0x08 DWORD CRC
    0x0C WORD  flags               0x0E WORD  auto data segment
    0x10 WORD  initial heap        0x12 WORD  initial stack
    0x14 DWORD CS:IP               0x18 DWORD SS:SP
    0x1C WORD  segment count       0x1E WORD  module ref count
    0x20 WORD  non-resident name table length
    0x22 WORD  segment table offset    0x24 WORD resource table offset
    0x26 WORD  resident name table offset
    0x28 WORD  module ref table offset 0x2A WORD imported names table offset
    0x2C DWORD non-resident name table FILE offset  (note: file, not relative)
    0x30 WORD  movable entry count 0x32 WORD  sector alignment shift
    0x34 WORD  resource segment count
    0x36 BYTE  target OS           0x37 BYTE  other flags
    0x3E WORD  expected Windows version

The two tables that answer "who made this":

  * the **resident name table**, whose first entry is the module name;
  * the **non-resident name table**, whose first entry is the module
    *description* -- a free-text string the linker takes from the .DEF file's
    DESCRIPTION line. Installer builders put their own product name there and
    almost never clear it.

Segment offsets in the segment table are in units of 1 << ne_align, which is
why a naive reader that treats them as bytes lands in the middle of nowhere.

    python tools/ne.py FILE
    python tools/ne.py FILE --segments
    python tools/ne.py FILE --resources
    python tools/ne.py FILE --entries
"""
import argparse
import struct
import sys

TARGET_OS = {0: "unknown", 1: "OS/2", 2: "Windows", 3: "European MS-DOS 4.x",
             4: "Windows 386", 5: "BOSS"}

FLAG_BITS = [
    (0x0001, "SINGLEDATA"), (0x0002, "MULTIPLEDATA"), (0x0800, "SELFLOAD"),
    (0x1000, "LINKERROR"), (0x2000, "LIBMODULE_2"), (0x8000, "LIBMODULE"),
]

SEG_FLAGS = [
    (0x0001, "DATA"), (0x0002, "ALLOCATED"), (0x0004, "LOADED"),
    (0x0010, "MOVEABLE"), (0x0020, "SHAREABLE"), (0x0040, "PRELOAD"),
    (0x0080, "EXECUTEONLY/READONLY"), (0x0100, "RELOCINFO"),
    (0x0200, "CONFORMING"), (0x1000, "DISCARDABLE"),
]

RT_NAMES = {1: "CURSOR", 2: "BITMAP", 3: "ICON", 4: "MENU", 5: "DIALOG",
            6: "STRING", 7: "FONTDIR", 8: "FONT", 9: "ACCELERATOR",
            10: "RCDATA", 11: "MESSAGETABLE", 12: "GROUP_CURSOR",
            14: "GROUP_ICON", 16: "VERSIONINFO"}


def bits(v, table):
    out = [n for b, n in table if v & b]
    return "|".join(out) if out else "(none)"


class NE(object):
    def __init__(self, path):
        self.path = path
        self.data = open(path, "rb").read()
        d = self.data
        if d[0:2] not in (b"MZ", b"ZM"):
            raise ValueError("no MZ magic: %r" % d[0:2])
        self.e_lfanew = struct.unpack_from("<I", d, 0x3C)[0]
        if d[self.e_lfanew:self.e_lfanew + 2] != b"NE":
            raise ValueError("no NE signature at e_lfanew=%d (found %r)"
                             % (self.e_lfanew, d[self.e_lfanew:self.e_lfanew + 2]))
        h = self.e_lfanew
        self.h = h
        (self.ver, self.rev) = d[h + 2], d[h + 3]
        self.enttab = struct.unpack_from("<H", d, h + 0x04)[0]
        self.cbenttab = struct.unpack_from("<H", d, h + 0x06)[0]
        self.crc = struct.unpack_from("<I", d, h + 0x08)[0]
        self.flags = struct.unpack_from("<H", d, h + 0x0C)[0]
        self.autodata = struct.unpack_from("<H", d, h + 0x0E)[0]
        self.heap = struct.unpack_from("<H", d, h + 0x10)[0]
        self.stack = struct.unpack_from("<H", d, h + 0x12)[0]
        self.csip = struct.unpack_from("<I", d, h + 0x14)[0]
        self.sssp = struct.unpack_from("<I", d, h + 0x18)[0]
        self.cseg = struct.unpack_from("<H", d, h + 0x1C)[0]
        self.cmod = struct.unpack_from("<H", d, h + 0x1E)[0]
        self.cbnrestab = struct.unpack_from("<H", d, h + 0x20)[0]
        self.segtab = struct.unpack_from("<H", d, h + 0x22)[0]
        self.rsrctab = struct.unpack_from("<H", d, h + 0x24)[0]
        self.restab = struct.unpack_from("<H", d, h + 0x26)[0]
        self.modtab = struct.unpack_from("<H", d, h + 0x28)[0]
        self.imptab = struct.unpack_from("<H", d, h + 0x2A)[0]
        self.nrestab = struct.unpack_from("<I", d, h + 0x2C)[0]
        self.cmovent = struct.unpack_from("<H", d, h + 0x30)[0]
        self.align = struct.unpack_from("<H", d, h + 0x32)[0]
        self.cres = struct.unpack_from("<H", d, h + 0x34)[0]
        self.exetyp = d[h + 0x36]
        self.otherflags = d[h + 0x37]
        self.expver = struct.unpack_from("<H", d, h + 0x3E)[0]

    # ---- name tables ------------------------------------------------------

    def _name_table(self, off, limit):
        """Length-prefixed name entries, each followed by a WORD ordinal."""
        out = []
        p = off
        end = min(off + limit, len(self.data)) if limit else len(self.data)
        while p < end:
            n = self.data[p]
            if n == 0:
                break
            name = self.data[p + 1:p + 1 + n]
            ordv = struct.unpack_from("<H", self.data, p + 1 + n)[0] \
                if p + 3 + n <= len(self.data) else 0
            out.append((name, ordv))
            p += 1 + n + 2
        return out

    def resident_names(self):
        return self._name_table(self.h + self.restab, 0)

    def nonresident_names(self):
        return self._name_table(self.nrestab, self.cbnrestab)

    def module_refs(self):
        """Module reference table -> names in the imported-names table."""
        out = []
        for i in range(self.cmod):
            off = struct.unpack_from("<H", self.data, self.h + self.modtab + 2 * i)[0]
            p = self.h + self.imptab + off
            n = self.data[p]
            out.append(self.data[p + 1:p + 1 + n])
        return out

    def segments(self):
        out = []
        shift = self.align or 9
        for i in range(self.cseg):
            e = self.h + self.segtab + 8 * i
            sect, length, flags, minalloc = struct.unpack_from("<HHHH", self.data, e)
            out.append({
                "n": i + 1,
                "sector": sect,
                "file_off": sect << shift,
                "length": length if length else 65536,
                "raw_length": length,
                "flags": flags,
                "minalloc": minalloc,
            })
        return out

    def resources(self):
        """Resource table: type blocks, each with name-info entries."""
        if not self.rsrctab or self.rsrctab == self.restab:
            return None, []
        base = self.h + self.rsrctab
        shift = struct.unpack_from("<H", self.data, base)[0]
        p = base + 2
        types = []
        while p + 8 <= len(self.data):
            tid = struct.unpack_from("<H", self.data, p)[0]
            if tid == 0:
                break
            count = struct.unpack_from("<H", self.data, p + 2)[0]
            p += 8
            entries = []
            for _ in range(count):
                off, length, flags, rid = struct.unpack_from("<HHHH", self.data, p)
                entries.append({"off": off << shift, "len": length << shift,
                                "flags": flags, "id": rid})
                p += 12
            types.append({"tid": tid, "entries": entries})
        return shift, types


def describe(ne, show_segments=False, show_resources=False, show_entries=False):
    print("file            : %s" % ne.path)
    print("size            : %d bytes" % len(ne.data))
    print("e_lfanew        : 0x%X" % ne.e_lfanew)
    print("format          : NE (16-bit New Executable)")
    print("linker version  : %d.%02d" % (ne.ver, ne.rev))
    print("target OS       : %d %s" % (ne.exetyp, TARGET_OS.get(ne.exetyp, "?")))
    print("expected Windows: %d.%d" % (ne.expver >> 8, ne.expver & 0xFF))
    print("flags           : 0x%04X  %s" % (ne.flags, bits(ne.flags, FLAG_BITS)))
    print("segments        : %d   module refs: %d   movable entries: %d"
          % (ne.cseg, ne.cmod, ne.cmovent))
    print("segment align   : 1 << %d = %d bytes" % (ne.align, 1 << ne.align))
    print("auto data seg   : %d   heap %d   stack %d"
          % (ne.autodata, ne.heap, ne.stack))
    print("entry CS:IP     : %04X:%04X" % (ne.csip >> 16, ne.csip & 0xFFFF))
    print("initial SS:SP   : %04X:%04X" % (ne.sssp >> 16, ne.sssp & 0xFFFF))
    print("header CRC      : 0x%08X" % ne.crc)

    res = ne.resident_names()
    print()
    print("resident name table (first entry is the module name): %d entries" % len(res))
    for name, ordv in res:
        print("    ord %-5d %s" % (ordv, name.decode("latin-1")))

    nres = ne.nonresident_names()
    print()
    print("non-resident name table (first entry is the module DESCRIPTION): %d entries"
          % len(nres))
    for name, ordv in nres:
        print("    ord %-5d %s" % (ordv, name.decode("latin-1")))

    mods = ne.module_refs()
    print()
    print("imported modules: %d" % len(mods))
    for m in mods:
        print("    %s" % m.decode("latin-1"))

    segs = ne.segments()
    total = sum(s["length"] for s in segs)
    print()
    print("segment table   : %d segments, %d bytes of code/data total"
          % (len(segs), total))
    print("                  that is %.4f %% of the file"
          % (100.0 * total / len(ne.data)))
    if show_segments or True:
        print("%-4s %8s %10s %8s %s" % ("#", "sector", "file off", "length", "flags"))
        for s in segs:
            print("%-4d %8d %10d %8d 0x%04X %s"
                  % (s["n"], s["sector"], s["file_off"], s["length"],
                     s["flags"], bits(s["flags"], SEG_FLAGS)))
        last = max((s["file_off"] + s["length"]) for s in segs) if segs else 0
        print()
        print("last segment ends at byte %d; the file is %d bytes."
              % (last, len(ne.data)))
        print("bytes after the last segment: %d  (%.4f %% of the file)"
              % (len(ne.data) - last, 100.0 * (len(ne.data) - last) / len(ne.data)))

    shift, types = ne.resources()
    print()
    if types is None or not types:
        print("resource table  : empty or absent")
    else:
        print("resource table  : alignment shift %d (%d bytes), %d type blocks"
              % (shift, 1 << shift, len(types)))
        for t in types:
            nm = RT_NAMES.get(t["tid"] & 0x7FFF, "0x%04X" % t["tid"]) \
                if t["tid"] & 0x8000 else "name-string 0x%04X" % t["tid"]
            print("    type %-14s %d entries" % (nm, len(t["entries"])))
            for e in t["entries"]:
                print("        id %-6d offset %-10d length %d"
                      % (e["id"] & 0x7FFF, e["off"], e["len"]))

    if show_entries:
        print()
        print("entry table     : offset 0x%X, %d bytes" % (ne.enttab, ne.cbenttab))
        print("    %s" % ne.data[ne.h + ne.enttab:
                                 ne.h + ne.enttab + ne.cbenttab].hex(" "))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--segments", action="store_true")
    ap.add_argument("--resources", action="store_true")
    ap.add_argument("--entries", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass
    try:
        ne = NE(args.file)
    except ValueError as exc:
        print("%s: %s" % (args.file, exc))
        return 1
    describe(ne, args.segments, args.resources, args.entries)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
