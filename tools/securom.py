#!/usr/bin/env python3
"""securom.py -- what replaced SafeDisc on this disc, read out of the PE.

The two earlier discs in this family carried Macrovision SafeDisc, and
bog.py found its version at a fixed offset inside a `BoG_` block. There is no
`BoG_` here, so this is a different tool for a different wrapper, and it is
deliberately written to have **no version number of its own inside it**:
everything it prints comes from the file named on the command line.

What it reads:

  * the whole section table, by NumberOfSections, so the listing cannot be
    short. (A five-row listing of a nine-section file is how a briefing came
    to say the entry point was "outside the last section listed".)
  * which section the entry point falls in, by RVA range;
  * every occurrence of the byte string of each section name, so a name that
    the loader also carries as data is visible as data;
  * the DEBUG data directory, including an RSDS record's GUID, age and PDB
    path -- which is where a build path survives a wrapper that ate the rest;
  * the bytes immediately after the last named section, and whether they are
    the certificate table.

    python tools/securom.py _work/fromzip/hp.exe
    python tools/securom.py _work/fromzip/hp.exe --around 0x8BC148
"""
import argparse
import datetime
import struct

DIRNAMES = ["EXPORT", "IMPORT", "RESOURCE", "EXCEPTION", "SECURITY",
            "BASERELOC", "DEBUG", "ARCHITECTURE", "GLOBALPTR", "TLS",
            "LOAD_CONFIG", "BOUND_IMPORT", "IAT", "DELAY_IMPORT", "CLR", "-"]

DEBUGTYPE = {0: "UNKNOWN", 1: "COFF", 2: "CODEVIEW", 3: "FPO", 4: "MISC",
             5: "EXCEPTION", 6: "FIXUP", 12: "VC_FEATURE", 13: "POGO",
             16: "REPRO"}


def hexdump(d, off, n, indent="  "):
    for i in range(off, min(off + n, len(d)), 16):
        row = d[i:i + 16]
        print("%s%08x  %-47s  %s"
              % (indent, i, " ".join("%02x" % b for b in row),
                 "".join(chr(b) if 32 <= b < 127 else "." for b in row)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--around", type=lambda s: int(s, 0), default=None)
    a = ap.parse_args()

    d = open(a.path, "rb").read()
    e = struct.unpack_from("<I", d, 0x3c)[0]
    nsec = struct.unpack_from("<H", d, e + 6)[0]
    optsz = struct.unpack_from("<H", d, e + 20)[0]
    entry = struct.unpack_from("<I", d, e + 24 + 16)[0]
    base = struct.unpack_from("<I", d, e + 24 + 28)[0]
    tbl = e + 24 + optsz

    print("file                : %s" % a.path)
    print("size                : %d bytes" % len(d))
    print("NumberOfSections    : %d   (this listing prints all of them)" % nsec)
    print("entry point RVA     : 0x%08X   (VA 0x%08X)" % (entry, base + entry))
    print()

    secs = []
    for i in range(nsec):
        o = tbl + i * 40
        raw = d[o:o + 8]
        name = raw.rstrip(b"\0").decode("latin1")
        vsize, vaddr, rsize, roff, _, _, _, flags = struct.unpack_from(
            "<IIIIIIHH", d, o + 8)[:8] if False else \
            struct.unpack_from("<IIII", d, o + 8) + \
            struct.unpack_from("<IIHH", d, o + 24)[:2] + (0, 0)
        flags = struct.unpack_from("<I", d, o + 36)[0]
        secs.append((name, raw, vaddr, vsize, roff, rsize, flags, o))

    print("  %-10s %-11s %10s %-11s %10s  %-8s %s"
          % ("name", "vaddr", "vsize", "rawoff", "rawsize", "flags", "note"))
    for name, raw, vaddr, vsize, roff, rsize, flags, o in secs:
        note = []
        if entry >= vaddr and entry < vaddr + max(vsize, rsize):
            note.append("<== ENTRY POINT")
        if flags & 0x20000000 and flags & 0x80000000:
            note.append("EXEC+WRITE")
        print("  %-10s 0x%08X %10d 0x%08X %10d  %08X  %s"
              % (name, vaddr, vsize, roff, rsize, flags, " ".join(note)))
    print()
    print("  section-table entries live at file offsets %s"
          % ", ".join("0x%X" % s[7] for s in secs))
    print()

    inside = [s[0] for s in secs
              if s[2] <= entry < s[2] + max(s[3], s[5])]
    print("entry point falls in: %s"
          % (", ".join(inside) if inside else "NO SECTION"))
    print()

    print("each section name searched for as a byte string in the whole file,")
    print("so a name the loader also carries as data shows up as data:")
    for name, raw, vaddr, vsize, roff, rsize, flags, o in secs:
        needle = name.encode("latin1")
        hits, i = [], 0
        while True:
            i = d.find(needle, i)
            if i < 0:
                break
            hits.append(i)
            i += 1
        where = []
        for h in hits:
            owner = "header"
            for n2, _, va2, vs2, ro2, rs2, f2, _o2 in secs:
                if ro2 <= h < ro2 + rs2:
                    owner = n2
            where.append("0x%X(%s)" % (h, owner))
        print("  %-10s %d occurrence(s): %s"
              % (name, len(hits), ", ".join(where[:8])))
    print()

    ddoff = e + 24 + 96
    ndd = struct.unpack_from("<I", d, e + 24 + 92)[0]
    print("data directories that are not empty:")
    dbg = None
    for i in range(ndd):
        rva, sz = struct.unpack_from("<II", d, ddoff + i * 8)
        if not (rva or sz):
            continue
        owner = "-"
        for n2, _, va2, vs2, ro2, rs2, f2, _o2 in secs:
            if va2 <= rva < va2 + max(vs2, rs2):
                owner = n2
        print("  %-13s rva 0x%08X  size %-8d  in %s"
              % (DIRNAMES[i] if i < len(DIRNAMES) else str(i), rva, sz, owner))
        if DIRNAMES[i] == "DEBUG":
            dbg = (rva, sz)
    print()

    def rva2off(rva):
        for n2, _, va2, vs2, ro2, rs2, f2, _o2 in secs:
            if va2 <= rva < va2 + max(vs2, rs2):
                return ro2 + (rva - va2)
        return None

    if dbg:
        rva, sz = dbg
        off = rva2off(rva)
        print("DEBUG directory at file offset 0x%X, %d bytes = %d entries:"
              % (off, sz, sz // 28))
        for k in range(sz // 28):
            (ch, ts, mj, mn, typ, dsz, drva, dptr) = \
                struct.unpack_from("<IIHHIIII", d, off + k * 28)
            when = datetime.datetime.fromtimestamp(
                ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            print("  [%d] type %d (%s)  TimeDateStamp %d = %s UTC"
                  % (k, typ, DEBUGTYPE.get(typ, "?"), ts, when))
            print("      SizeOfData %d  AddressOfRawData 0x%08X  "
                  "PointerToRawData 0x%X" % (dsz, drva, dptr))
            blob = d[dptr:dptr + dsz]
            if blob[:4] == b"RSDS":
                g = blob[4:20]
                guid = "%08X-%04X-%04X-%s-%s" % (
                    struct.unpack_from("<I", g, 0)[0],
                    struct.unpack_from("<H", g, 4)[0],
                    struct.unpack_from("<H", g, 6)[0],
                    g[8:10].hex().upper(), g[10:16].hex().upper())
                age = struct.unpack_from("<I", blob, 20)[0]
                pdb = blob[24:].split(b"\0")[0].decode("latin1")
                print("      RSDS  guid %s  age %d" % (guid, age))
                print("      PDB   %s" % pdb)
            elif blob:
                print("      raw   %r" % blob[:120])
        print()

    last = max(secs, key=lambda s: s[4] + s[5])
    tail = last[4] + last[5]
    print("last section by file position : %s, ends at %d"
          % (last[0], tail))
    print("bytes after it                : %d" % (len(d) - tail))
    srva, ssz = struct.unpack_from("<II", d, ddoff + 4 * 8)
    if srva:
        print("SECURITY directory offset     : %d, size %d" % (srva, ssz))
        print("  (for SECURITY the field is a file offset, not an RVA)")
        print("  tail is the certificate table : %s"
              % (srva == tail and srva + ssz == len(d)))
    print()

    if a.around is not None:
        print("bytes around 0x%X:" % a.around)
        hexdump(d, a.around - 64, 256)


if __name__ == "__main__":
    main()
