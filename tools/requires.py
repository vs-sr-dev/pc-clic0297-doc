#!/usr/bin/env python3
"""requires.py -- what each binary needed in order to run, read from its imports.

A compilation disc is a list of *dependencies* as much as a list of files. Every
executable image on it names, in a table the loader reads, the libraries it
cannot start without; and those names date the file and identify its runtime
more precisely than any string in it. `VBRUN300.DLL` in an import table is not
a guess about Visual Basic 3, it is Visual Basic 3.

Both formats are read:

  NE   the module-reference table at +0x28 indexes the imported-name table at
       +0x2a; each entry is a length-prefixed module name, no extension.
       There is no ordinal-vs-name distinction at this level: the module list
       is what the loader loads.
  PE   the import directory, data directory entry 1, walked through the
       section table to a file offset; each descriptor names one DLL.

The tool also reports, per binary, the subsystem and the minimum operating
system version in the optional header, because those two fields are the file's
own statement about what it needs -- a PE that says "Windows GUI, version 4.0"
will not start on Windows 3.1 whatever else is true.

    python tools/requires.py _work/iso _work/hfs
    python tools/requires.py _work/iso --by-library
    python tools/requires.py _work/iso --tsv notes/requires.tsv
"""
import argparse
import os
import struct
from collections import Counter, defaultdict

SUBSYS = {0: "unknown", 1: "native", 2: "Windows GUI", 3: "Windows console",
          5: "OS/2", 7: "POSIX", 9: "Windows CE"}


def ne_imports(d, off):
    n_mod = struct.unpack("<H", d[off + 0x1E:off + 0x20])[0]
    modtab = off + struct.unpack("<H", d[off + 0x28:off + 0x2A])[0]
    imptab = off + struct.unpack("<H", d[off + 0x2A:off + 0x2C])[0]
    mods = []
    for i in range(n_mod):
        p = modtab + i * 2
        if p + 2 > len(d):
            break
        rel = struct.unpack("<H", d[p:p + 2])[0]
        q = imptab + rel
        if q >= len(d):
            continue
        ln = d[q]
        mods.append(d[q + 1:q + 1 + ln].decode("latin-1", "replace"))
    ver = "%d.%d" % (d[off + 2], d[off + 3])
    exever = struct.unpack("<H", d[off + 0x3E:off + 0x40])[0]
    tgt = {1: "OS/2", 2: "Windows", 3: "MS-DOS 4.x", 4: "Windows 386",
           5: "BOSS"}.get(d[off + 0x36], "target %d" % d[off + 0x36])
    return mods, ("NE, linker %s, %s, expects Windows %d.%d"
                  % (ver, tgt, exever >> 8, exever & 0xFF))


def pe_imports(d, off):
    coff = off + 4
    nsec = struct.unpack("<H", d[coff + 2:coff + 4])[0]
    opt = coff + 20
    magic = struct.unpack("<H", d[opt:opt + 2])[0]
    lnk = "%d.%02d" % (d[opt + 2], d[opt + 3])
    plus = magic == 0x20B
    subsys = struct.unpack("<H", d[opt + (70 if plus else 68):
                                   opt + (72 if plus else 70)])[0]
    osmaj = struct.unpack("<H", d[opt + 40:opt + 42])[0]
    osmin = struct.unpack("<H", d[opt + 42:opt + 44])[0]
    ddoff = opt + (112 if plus else 96)
    imp_rva, imp_sz = struct.unpack("<II", d[ddoff + 8:ddoff + 16])
    sects = []
    sbase = opt + struct.unpack("<H", d[coff + 16:coff + 18])[0]
    for i in range(nsec):
        s = d[sbase + i * 40: sbase + i * 40 + 40]
        if len(s) < 40:
            break
        vsz, va, rsz, ra = struct.unpack("<IIII", s[8:24])
        sects.append((va, max(vsz, rsz), ra))

    def rva2off(rva):
        for va, sz, ra in sects:
            if va <= rva < va + sz:
                return ra + (rva - va)
        return None

    mods = []
    o = rva2off(imp_rva) if imp_rva else None
    if o:
        while o + 20 <= len(d):
            desc = d[o:o + 20]
            if desc == b"\x00" * 20:
                break
            name_rva = struct.unpack("<I", desc[12:16])[0]
            no = rva2off(name_rva)
            if no is None or no >= len(d):
                break
            end = d.find(b"\x00", no)
            mods.append(d[no:end].decode("latin-1", "replace"))
            o += 20
    return mods, ("PE, linker %s, %s, needs OS %d.%d"
                  % (lnk, SUBSYS.get(subsys, "subsystem %d" % subsys),
                     osmaj, osmin))


def probe(path):
    with open(path, "rb") as fh:
        d = fh.read()
    if d[:2] != b"MZ" or len(d) < 0x40:
        return None
    off = struct.unpack("<I", d[0x3C:0x40])[0]
    if off + 4 > len(d):
        return None
    sig = d[off:off + 2]
    try:
        if sig == b"NE":
            return ne_imports(d, off)
        if d[off:off + 4] == b"PE\x00\x00":
            return pe_imports(d, off)
    except (struct.error, IndexError):
        return ([], "header truncated")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--by-library", action="store_true")
    ap.add_argument("--tsv")
    a = ap.parse_args()

    rows = []
    for root in a.roots:
        for dp, dn, fn in os.walk(root):
            for f in sorted(fn):
                p = os.path.join(dp, f)
                if os.path.getsize(p) < 64:
                    continue
                r = probe(p)
                if r:
                    rows.append((os.path.relpath(p, root).replace(os.sep, "/"),
                                 os.path.getsize(p), r[1], r[0]))

    print("executable images read : %d" % len(rows))
    print()
    print("%-44s %10s  %s" % ("path", "bytes", "what the header says"))
    for rel, sz, what, mods in sorted(rows):
        print("%-44s %10d  %s" % (rel[:44], sz, what))
        if mods:
            line = ", ".join(sorted(set(m.upper() for m in mods)))
            while line:
                print("      %s" % line[:96])
                line = line[96:]
    print()

    lib = Counter()
    who = defaultdict(list)
    for rel, sz, what, mods in rows:
        for m in set(x.upper() for x in mods):
            lib[m] += 1
            who[m].append(rel)
    print("every library imported anywhere on this disc, with how many images "
          "need it:")
    print("  %-22s %5s  %s" % ("library", "n", "first two importers"))
    for m, n in lib.most_common():
        print("  %-22s %5d  %s" % (m, n, ", ".join(sorted(who[m])[:2])[:60]))

    if a.by_library:
        print()
        for m, n in lib.most_common():
            print("--- %s (%d)" % (m, n))
            for r in sorted(who[m]):
                print("      %s" % r)

    if a.tsv:
        with open(a.tsv, "w", encoding="utf-8", newline="") as fh:
            fh.write("path\tsize\theader\timports\n")
            for rel, sz, what, mods in sorted(rows):
                fh.write("%s\t%d\t%s\t%s\n"
                         % (rel, sz, what,
                            ";".join(sorted(set(m.upper() for m in mods)))))
        print()
        print("wrote %s" % a.tsv)


if __name__ == "__main__":
    main()
