#!/usr/bin/env python3
"""safedisc.py -- census of the copy protection, from the bytes it left.

Four files on this disc belong to the protection and not to the game:
System/HP.exe (wrapped), drvmgt.dll, secdrv.sys, and the two .TMP at the root.
This finds the version marker, reads it at every plausible offset instead of
one, and prints all the readings so the right one is chosen by agreement
across files rather than by picking one and hoping.

The marker is the ASCII string "BoG_" followed by a fixed blob. The version is
three 32-bit little-endian integers somewhere after it; the briefing that
opened this session read them immediately after the four signature bytes and
got 0.0.000, so this prints the triple at every offset from +4 to +64 and
reports which offset yields the same non-zero triple in more than one file.
Agreement across files is the oracle.

    python tools/safedisc.py E:/
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SIG = b"BoG_"
CAND = ("System/HP.exe", "drvmgt.dll", "secdrv.sys", "00000001.TMP",
        "00000002.TMP", "AutoRun.exe", "setup/Setup.exe")


def sections(d):
    """PE section table: (name, vaddr, vsize, raw off, raw size)."""
    if d[:2] != b"MZ":
        return None
    e = struct.unpack_from("<I", d, 0x3C)[0]
    if d[e:e + 4] != b"PE" + bytes([0, 0]):
        return None
    nsec = struct.unpack_from("<H", d, e + 6)[0]
    optsz = struct.unpack_from("<H", d, e + 20)[0]
    ts = struct.unpack_from("<I", d, e + 8)[0]
    off = e + 24 + optsz
    out = []
    for i in range(nsec):
        b = d[off + 40 * i: off + 40 * i + 40]
        nm = b[:8].rstrip(bytes([0])).decode("latin-1", "replace")
        vs, va, rs, ro = struct.unpack_from("<IIII", b, 8)
        ch = struct.unpack_from("<I", b, 36)[0]
        out.append((nm, va, vs, ro, rs, ch))
    return ts, out


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "E:/"
    readings = {}
    for rel in CAND:
        p = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.exists(p):
            print("%-24s not present" % rel)
            continue
        d = open(p, "rb").read()
        print("=" * 70)
        print("%s   %d bytes" % (rel, len(d)))
        print("=" * 70)
        s = sections(d)
        if s:
            ts, secs = s
            import datetime
            print("  COFF timestamp : %d = %s UTC"
                  % (ts, datetime.datetime.fromtimestamp(
                      ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")))
            print("  %d sections:" % len(secs))
            for nm, va, vs, ro, rs, ch in secs:
                tag = ""
                if nm.startswith("stxt") or nm.startswith(".txt"):
                    tag = "   <- protection section"
                print("     %-10s vaddr 0x%08X vsize %8d  raw 0x%08X size %8d"
                      "  flags 0x%08X%s" % (nm, va, vs, ro, rs, ch, tag))
        hits = [m.start() for m in re.finditer(re.escape(SIG), d)]
        print("  %r occurrences: %d %s"
              % (SIG, len(hits), ["0x%X" % h for h in hits]))
        for h in hits:
            blob = d[h:h + 96]
            print("  at 0x%X:" % h)
            for a in range(0, 96, 16):
                ch2 = blob[a:a + 16]
                print("     +%-3d %-47s  %s"
                      % (a, ch2.hex(" "),
                         "".join(chr(c) if 32 <= c < 127 else "."
                                 for c in ch2)))
            print("  version triple read at every offset from +4 to +60:")
            for off in range(4, 61, 4):
                if h + off + 12 > len(d):
                    break
                a, b, c = struct.unpack_from("<III", d, h + off)
                flag = ""
                if 0 < a < 10 and b < 100 and c < 1000 and (a or b or c):
                    flag = "   <- plausible"
                    readings.setdefault((off, a, b, c), []).append(rel)
                print("     +0x%02X   %d.%d.%03d   (raw %d, %d, %d)%s"
                      % (off, a, b, c, a, b, c, flag))
        print()

    print("=" * 70)
    print("agreement across files")
    print("=" * 70)
    if not readings:
        print("no plausible version triple found in any file.")
        return
    for (off, a, b, c), who in sorted(readings.items(),
                                      key=lambda kv: -len(kv[1])):
        print("  offset +0x%02X -> %d.%d.%03d   seen in %d file(s): %s"
              % (off, a, b, c, len(who), ", ".join(who)))
    best = max(readings.items(), key=lambda kv: (len(kv[1]), -kv[0][0]))
    (off, a, b, c), who = best
    print()
    if len(who) > 1:
        print("the triple agreed on by the most files is %d.%d.%03d,"
              " read at BoG_ + 0x%02X in %s" % (a, b, c, off, ", ".join(who)))
    else:
        print("no triple is confirmed by two files; the single best reading is"
              " %d.%d.%03d at BoG_ + 0x%02X in %s" % (a, b, c, off, who[0]))


if __name__ == "__main__":
    main()
