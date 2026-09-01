#!/usr/bin/env python3
"""mld.py -- read the `MLD` multi-language dictionary the installer carries.

`Dict/Install.mld` is 11,175 bytes beginning `4D 4C 44 03` -- "MLD" and a
version byte. It is not a documented format; this reader was written from the
bytes, and everything it asserts is checked against the file rather than
assumed:

  * the header declares the number of languages at +0x0C, and the reader
    stops when it has read that many, then reports how many bytes are left;
  * each language record declares its own length, and the reader adds up the
    fields it parsed and compares the total with that length. A record whose
    fields do not add up to its declared length is printed as a failure, not
    silently accepted.

Record layout, offsets relative to the start of the record:

     0   2   record length, including these two bytes
     2   2   ordinal
     4   2   ISO 639-1 language code, ASCII, spaces when unset
     6   2   unknown, 0 or 1
     8   2   ISO 3166 country code, ASCII, spaces when unset
    10   4   zero
    14   2   Windows LOGFONT lfCharSet, little-endian: 0 ANSI, 238
             EASTEUROPE, 204 RUSSIAN. The first version of this reader
             asserted six zero bytes here and was wrong for exactly the two
             languages that are not code page 1252, which is how the field
             was identified.
    16   2   Windows code page, little-endian
    18   1   flag: 2 on the first record, 0 on the others
    19   2+n length-prefixed name in English
         2+m length-prefixed name in the language itself
             three zero bytes

    python tools/mld.py _work/iso/Dict/Install.mld
    python tools/mld.py _work/iso/Dict/Install.mld --strings
"""
import argparse
import struct

MAGIC = b"MLD"
CHARSET_NAME = {0: "ANSI", 1: "DEFAULT", 2: "SYMBOL", 128: "SHIFTJIS",
                129: "HANGUL", 134: "GB2312", 136: "CHINESEBIG5",
                161: "GREEK", 162: "TURKISH", 177: "HEBREW", 178: "ARABIC",
                186: "BALTIC", 204: "RUSSIAN", 222: "THAI",
                238: "EASTEUROPE", 255: "OEM"}

CODEPAGE_NAME = {
    1250: "Central European",
    1251: "Cyrillic",
    1252: "Western European",
    1253: "Greek",
    1254: "Turkish",
    1255: "Hebrew",
    1256: "Arabic",
    1257: "Baltic",
    1258: "Vietnamese",
    932: "Japanese", 936: "Simplified Chinese",
    949: "Korean", 950: "Traditional Chinese",
}


def pstr(d, p):
    n = struct.unpack_from("<H", d, p)[0]
    return d[p + 2:p + 2 + n], p + 2 + n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--start", type=lambda x: int(x, 0), default=0x2A,
                    help="offset of the first language record")
    ap.add_argument("--strings", action="store_true")
    a = ap.parse_args()

    d = open(a.path, "rb").read()
    print("file        : %s" % a.path)
    print("size        : %d bytes" % len(d))
    print("magic       : %s  version byte %d" % (d[:3], d[3]))
    if d[:3] != MAGIC:
        raise SystemExit("not an MLD file")
    declared = struct.unpack_from("<H", d, 0x0C)[0]
    print("languages declared at +0x0C : %d" % declared)
    print()
    print("%-3s %-4s %-5s %-4s %-24s %-14s %-20s %-20s %s"
          % ("#", "len", "code", "ctry", "code page", "lfCharSet",
             "name (English)", "name (native)", "check"))

    p = a.start
    rows = []
    for k in range(declared):
        if p + 19 > len(d):
            print("  record %d starts past the end of the file" % k)
            break
        size = struct.unpack_from("<H", d, p)[0]
        ordinal = struct.unpack_from("<H", d, p + 2)[0]
        code = d[p + 4:p + 6].decode("latin-1")
        unk = struct.unpack_from("<H", d, p + 6)[0]
        country = d[p + 8:p + 10].decode("latin-1")
        zeros = d[p + 10:p + 14]
        charset = struct.unpack_from("<H", d, p + 14)[0]
        cp = struct.unpack_from("<H", d, p + 16)[0]
        flag = d[p + 18]
        en, q = pstr(d, p + 19)
        nat, q = pstr(d, q)
        q += 3
        ok = "ok" if q - p == size else "LENGTH %d, parsed %d" % (size, q - p)
        if zeros != bytes(4):
            ok += " (bytes 10..13 not zero: %s)" % zeros.hex()
        rows.append((code.strip(), country.strip(), cp, en, nat, charset))
        print("%-3d %-4d %-5s %-4s %-24s %-14s %-20s %-20s %s"
              % (k, size, code.strip() or "-", country.strip() or "-",
                 "%d %s" % (cp, CODEPAGE_NAME.get(cp, "?")),
                 "%d %s" % (charset, CHARSET_NAME.get(charset, "?")),
                 en.decode("latin-1"), nat.decode("latin-1"), ok))
        p = q

    print()
    print("bytes consumed by the language table : %d (0x%X .. 0x%X)"
          % (p - a.start, a.start, p))
    print("bytes remaining after it             : %d" % (len(d) - p))
    print("distinct lfCharSet values            : %s"
          % ", ".join("%d %s" % (c, CHARSET_NAME.get(c, "?"))
                      for c in sorted({r[5] for r in rows})))
    cps = sorted({r[2] for r in rows})
    print("distinct code pages                  : %s"
          % ", ".join("%d %s" % (c, CODEPAGE_NAME.get(c, "?")) for c in cps))
    print("distinct language codes              : %s"
          % ", ".join(sorted(r[0] for r in rows if r[0])))

    if a.strings:
        import re
        print()
        print("printable runs of 4+ bytes after the table:")
        for m in re.finditer(rb"[\x20-\x7e]{4,}", d[p:]):
            print("  +0x%05X  %s" % (p + m.start(),
                                     m.group().decode("latin-1")))


if __name__ == "__main__":
    main()
