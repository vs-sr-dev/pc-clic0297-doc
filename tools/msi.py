#!/usr/bin/env python3
"""msi.py - read a Windows Installer database with the standard library only.

An .msi is an OLE2 compound file holding a small relational database. Three
layers have to come apart before a single row is readable, and each one is a
place to go wrong quietly:

  1. the compound file itself: a 512-byte header, a FAT of sector chains, a
     red-black directory of stream entries, and a second allocation scheme
     (the mini-FAT) for streams under 4,096 bytes;
  2. the stream names, which are packed two characters to a UTF-16 code unit
     over a 64-character alphabet, so `_Tables` is stored as something no
     text editor will show you;
  3. the database: `_StringData` and `_StringPool` hold every string in the
     file once, `_Tables` names the tables, `_Columns` gives their schema,
     and each table's own stream stores its cells column by column rather
     than row by row, with integers biased by half their range so that zero
     can mean null.

Why it is needed here: this disc ships 2,934 files in one flat cabinet whose
names collide (`piange.wav`, `piange.wav1`, ... `piange.wav36`). The real
directory tree exists only in this database, so without it the cabinet is a
heap and with it the game has a shape.

Usage:
    python tools/msi.py FILE --streams
    python tools/msi.py FILE --tables
    python tools/msi.py FILE --properties
    python tools/msi.py FILE --table NAME
    python tools/msi.py FILE --tree
    python tools/msi.py FILE --strings [--min N]
"""

import argparse
import struct
import sys

# ------------------------------------------------------------------- CFB
FREESECT, ENDOFCHAIN, FATSECT, DIFSECT = 0xFFFFFFFF, 0xFFFFFFFE, \
    0xFFFFFFFD, 0xFFFFFFFC


class Cfb(object):
    def __init__(self, path):
        with open(path, "rb") as fh:
            self.d = fh.read()
        if self.d[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            raise ValueError("not an OLE2 compound file")
        (self.minor, self.major, self.byteorder, ssz, mssz) = \
            struct.unpack_from("<HHHHH", self.d, 24)
        self.ssize = 1 << ssz
        self.msize = 1 << mssz
        (self.ndir, self.nfat, self.dirstart, _, self.cutoff,
         self.ministart, self.nmini, self.difstart, self.ndif) = \
            struct.unpack_from("<IIIIIIIII", self.d, 40)
        self._read_fat()
        self._read_dir()
        self._read_minifat()

    def sector(self, n):
        off = 512 + n * self.ssize
        return self.d[off:off + self.ssize]

    def _read_fat(self):
        difat = list(struct.unpack_from("<109I", self.d, 76))
        nxt = self.difstart
        for _ in range(self.ndif):
            if nxt in (ENDOFCHAIN, FREESECT):
                break
            blk = self.sector(nxt)
            vals = struct.unpack_from("<%dI" % (self.ssize // 4), blk, 0)
            difat.extend(vals[:-1])
            nxt = vals[-1]
        self.fat = []
        for s in difat:
            if s in (FREESECT, ENDOFCHAIN):
                continue
            blk = self.sector(s)
            self.fat.extend(struct.unpack_from("<%dI" % (self.ssize // 4),
                                               blk, 0))

    def chain(self, start):
        out = []
        s = start
        guard = 0
        while s not in (ENDOFCHAIN, FREESECT) and s < len(self.fat):
            out.append(s)
            s = self.fat[s]
            guard += 1
            if guard > len(self.fat) + 8:
                raise ValueError("FAT chain does not terminate")
        return out

    def _read_dir(self):
        raw = b"".join(self.sector(s) for s in self.chain(self.dirstart))
        self.entries = []
        for i in range(len(raw) // 128):
            e = raw[i * 128:(i + 1) * 128]
            nlen = struct.unpack_from("<H", e, 64)[0]
            name = e[:max(0, nlen - 2)].decode("utf-16-le", "replace")
            typ = e[66]
            start, size = struct.unpack_from("<IQ", e, 116)
            self.entries.append({"index": i, "name": name, "type": typ,
                                 "start": start, "size": size,
                                 "raw_name": e[:max(0, nlen - 2)]})

    def _read_minifat(self):
        self.minifat = []
        for s in self.chain(self.ministart):
            self.minifat.extend(
                struct.unpack_from("<%dI" % (self.ssize // 4), self.sector(s), 0))
        root = self.entries[0]
        self.ministream = b"".join(self.sector(s)
                                   for s in self.chain(root["start"]))

    def mini_chain(self, start):
        out = []
        s = start
        while s not in (ENDOFCHAIN, FREESECT) and s < len(self.minifat):
            out.append(s)
            s = self.minifat[s]
        return out

    def read(self, entry):
        if entry["size"] < self.cutoff and entry["index"] != 0:
            data = b"".join(
                self.ministream[s * self.msize:(s + 1) * self.msize]
                for s in self.mini_chain(entry["start"]))
        else:
            data = b"".join(self.sector(s) for s in self.chain(entry["start"]))
        return data[:entry["size"]]


# --------------------------------------------------------- MSI name coding
B64 = ("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
       "abcdefghijklmnopqrstuvwxyz._")


def demangle(name):
    """Undo the two-characters-per-code-unit packing MSI uses for stream
    names. U+4840 is not data: it is the marker prepended to every table
    stream, and leaving it in the decoded name is why `_StringPool` cannot
    be found by that name until it is stripped."""
    out = []
    for ch in name:
        c = ord(ch)
        if c == 0x4840:
            continue
        if 0x3800 <= c < 0x4800:
            v = c - 0x3800
            out.append(B64[v & 0x3F])
            out.append(B64[(v >> 6) & 0x3F])
        elif 0x4800 <= c < 0x4840:
            out.append(B64[c - 0x4800])
        else:
            out.append(ch)
    return "".join(out)


# ------------------------------------------------------------------- MSI
class Msi(object):
    def __init__(self, path):
        self.cfb = Cfb(path)
        self.streams = {}
        for e in self.cfb.entries:
            if e["type"] == 2:
                self.streams[demangle(e["name"])] = e
        self._strings()
        self._schema()

    def _strings(self):
        pool = self.cfb.read(self.streams["_StringPool"])
        data = self.cfb.read(self.streams["_StringData"])
        self.codepage = struct.unpack_from("<I", pool, 0)[0] & 0x7FFFFFFF
        self.strings = [""]
        off = 0
        i = 4
        pending = 0
        while i + 4 <= len(pool):
            ln, refs = struct.unpack_from("<HH", pool, i)
            i += 4
            if ln == 0 and refs != 0:
                pending = refs
                continue
            n = (pending << 16) | ln
            pending = 0
            enc = "cp%d" % self.codepage if self.codepage else "cp1252"
            try:
                s = data[off:off + n].decode(enc, "replace")
            except LookupError:
                s = data[off:off + n].decode("cp1252", "replace")
            self.strings.append(s)
            off += n
        self.long_strings = len(self.strings) > 0x10000

    def s(self, i):
        return self.strings[i] if 0 <= i < len(self.strings) else "<%d?>" % i

    def _schema(self):
        # _Columns has a fixed, known schema so it can bootstrap itself
        cols = self._raw_table("_Columns",
                               [("Table", 0x9D00), ("Number", 0x9502),
                                ("Name", 0x9D00), ("Type", 0x9502)])
        self.schema = {}
        for row in cols:
            self.schema.setdefault(row[0], []).append((row[1], row[2], row[3]))
        for t in self.schema:
            self.schema[t].sort()
        tabs = self._raw_table("_Tables", [("Name", 0x9D00)])
        self.tables = [r[0] for r in tabs]

    def _colwidth(self, typ):
        if typ & 0x0800:                      # string
            return 3 if self.long_strings else 2
        return typ & 0xFF                     # 2 or 4

    def _raw_table(self, name, coldefs):
        if name not in self.streams:
            return []
        raw = self.cfb.read(self.streams[name])
        widths = [self._colwidth(t) for _, t in coldefs]
        rowsize = sum(widths)
        if rowsize == 0:
            return []
        nrows = len(raw) // rowsize
        out = [[] for _ in range(nrows)]
        off = 0
        for (cname, typ), w in zip(coldefs, widths):
            for r in range(nrows):
                p = off + r * w
                if w == 2:
                    v = struct.unpack_from("<H", raw, p)[0]
                elif w == 3:
                    v = raw[p] | (raw[p + 1] << 8) | (raw[p + 2] << 16)
                else:
                    v = struct.unpack_from("<I", raw, p)[0]
                if typ & 0x0800:
                    out[r].append(self.s(v))
                elif w == 2:
                    out[r].append(v - 0x8000 if v else None)
                else:
                    out[r].append((v ^ 0x80000000) if v else None)
            off += w * nrows
        return out

    def table(self, name):
        if name not in self.schema:
            return None, None
        cols = [(c[1], c[2]) for c in self.schema[name]]
        return [c[0] for c in cols], self._raw_table(name, cols)


# ------------------------------------------------------------------ output
def cmd_streams(m):
    print("%-40s %10s  %s" % ("stream (demangled)", "bytes", "raw name"))
    for n, e in sorted(m.streams.items(), key=lambda kv: -kv[1]["size"]):
        print("%-40s %10d  %s" % (n, e["size"], e["raw_name"].hex()))
    print()
    print("streams: %d" % len(m.streams))
    print("string pool codepage: %d" % m.codepage)
    print("strings: %d" % (len(m.strings) - 1))


def cmd_tables(m):
    print("%-28s %6s %6s   columns" % ("table", "rows", "cols"))
    for t in sorted(m.tables):
        cols, rows = m.table(t)
        print("%-28s %6s %6s   %s"
              % (t, len(rows) if rows is not None else "?",
                 len(cols) if cols else "?",
                 ", ".join(cols) if cols else ""))
    print()
    print("tables: %d" % len(m.tables))


def cmd_table(m, name, limit):
    cols, rows = m.table(name)
    if cols is None:
        print("no such table: %s" % name)
        print("tables: %s" % ", ".join(sorted(m.tables)))
        return
    print("  " + " | ".join(cols))
    print("  " + "-" * 68)
    for r in rows[:limit]:
        print("  " + " | ".join("" if v is None else str(v) for v in r))
    if len(rows) > limit:
        print("  ... %d more rows" % (len(rows) - limit))
    print()
    print("%d rows" % len(rows))


def cmd_properties(m):
    cols, rows = m.table("Property")
    if not rows:
        print("no Property table")
        return
    for r in sorted(rows):
        print("  %-32s %s" % (r[0], r[1]))
    print()
    print("%d properties" % len(rows))


def cmd_tree(m):
    """Rebuild the install tree from Directory + Component + File."""
    _, dirs = m.table("Directory")
    _, comps = m.table("Component")
    _, files = m.table("File")
    if not dirs or not files:
        print("Directory or File table missing")
        return
    parent = {}
    label = {}
    for d in dirs:
        key, par, name = d[0], d[1], d[2]
        short = name.split("|")[0]
        long_ = name.split("|")[-1]
        parent[key] = par
        label[key] = long_ if long_ != "." else ""

    def path_of(key, depth=0):
        if key is None or key not in parent or depth > 32:
            return ""
        p = path_of(parent[key], depth + 1)
        l = label.get(key, "")
        if not l:
            return p
        return (p + "/" + l) if p else l

    comp_dir = {c[0]: c[2] for c in comps} if comps else {}

    rows = []
    for f in files:
        fkey, comp, name, size, ver, lang, attr, seq = f[:8]
        short = name.split("|")[0]
        long_ = name.split("|")[-1]
        d = comp_dir.get(comp)
        rows.append((path_of(d), long_, short, size, seq, fkey))

    rows.sort(key=lambda r: (r[0].lower(), r[1].lower()))
    print("%-46s %-26s %-16s %10s %6s" %
          ("directory", "name", "name in cabinet", "bytes", "seq"))
    cur = None
    total = 0
    for p, long_, short, size, seq, fkey in rows:
        if p != cur:
            print()
            print("  %s/" % (p or "(target root)"))
            cur = p
        print("      %-26s %-16s %10s %6s" % (long_, fkey, size, seq))
        total += size or 0
    print()
    print("%d files, %d bytes, %d directories"
          % (len(rows), total, len(set(r[0] for r in rows))))


def cmd_strings(m, minlen):
    for s in m.strings[1:]:
        if len(s) >= minlen:
            print(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("msi")
    ap.add_argument("--streams", action="store_true")
    ap.add_argument("--tables", action="store_true")
    ap.add_argument("--table")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--properties", action="store_true")
    ap.add_argument("--tree", action="store_true")
    ap.add_argument("--strings", action="store_true")
    ap.add_argument("--min", type=int, default=4)
    a = ap.parse_args()

    m = Msi(a.msi)
    if a.streams:
        cmd_streams(m)
    if a.tables:
        cmd_tables(m)
    if a.table:
        cmd_table(m, a.table, a.limit)
    if a.properties:
        cmd_properties(m)
    if a.tree:
        cmd_tree(m)
    if a.strings:
        cmd_strings(m, a.min)


if __name__ == "__main__":
    main()
