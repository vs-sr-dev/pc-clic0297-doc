#!/usr/bin/env python3
"""vdmatch3.py -- the same idea as vdmatch.py, with no disc baked in.

vdmatch.py is one of the inherited tools that carries its subject's answers
inside it: its payload window is 1139..1535 and its MEASURED dictionary is
eleven boundaries of the Philosopher's Stone disc. Run here it reads a region
that is all zero on this disc, finds nothing, and prints "(none)" -- which is
true about the wrong bytes.

So: same purpose, every constant on the command line, and every constant is
echoed with the tool that produced it before any matching happens. A reader
who disagrees with a boundary can see which one was used.

    python tools/vdmatch3.py E --span 1880 2048 \
        --extents notes/isodev-extents.txt \
        --boundary "volume sectors (spti.py/vds.py)=1826656" \
        --boundary "lead-out LBA (toc.py)=1151849" \
        --boundary "MSF ceiling (msf.py)=1151849" \
        --boundary "UDF partition start (udf.py)=302" \
        --boundary "UDF partition length (udf.py)=1826354"
"""
import argparse
import re
import sys

BS = chr(92)
SECTOR = 2048


def rd(letter, lba):
    with open(BS + BS + "." + BS + letter.upper() + ":", "rb") as f:
        f.seek(lba * SECTOR)
        return f.read(SECTOR)


def load_extents(path):
    rows = []
    pat = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S.*)$")
    for line in open(path, encoding="utf-8", errors="replace"):
        if "GAP" in line or "----" in line:
            continue
        m = pat.match(line.rstrip())
        if not m:
            continue
        lba, nsec, size, slack, name = m.groups()
        rows.append((int(lba), int(nsec), int(size), name.strip()))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive")
    ap.add_argument("--lba", type=int, default=16)
    ap.add_argument("--span", type=int, nargs=2, default=[0, 2048])
    ap.add_argument("--extents", default=None)
    ap.add_argument("--boundary", action="append", default=[],
                    help='"label=value", repeatable')
    ap.add_argument("--min", type=int, default=100,
                    help="ignore matches below this, they are noise")
    a = ap.parse_args()

    lo, hi = a.span
    s = rd(a.drive, a.lba)
    print("sector %d of drive %s:, bytes %d..%d"
          % (a.lba, a.drive.upper(), lo, hi))
    print()

    measured = {}
    for spec in a.boundary:
        k, _, v = spec.rpartition("=")
        measured[k] = int(v)
    print("boundaries this run was given (%d), and where each came from:"
          % len(measured))
    for k, v in sorted(measured.items(), key=lambda kv: -kv[1]):
        print("  %-46s %12d" % (k, v))
    if not measured:
        print("  (none given -- pass --boundary label=value)")
    print()

    rows = load_extents(a.extents) if a.extents else []
    by_lba, by_last, by_size, by_sect = {}, {}, {}, {}
    for lba, nsec, size, name in rows:
        by_lba.setdefault(lba, []).append(name)
        by_last.setdefault(lba + nsec - 1, []).append(name)
        by_size.setdefault(size, []).append(name)
        by_sect.setdefault(nsec, []).append(name)
    if rows:
        print("extent map: %d file entries loaded from %s"
              % (len(rows), a.extents))
        print()

    print("every 2- and 4-byte reading, both endians, at every byte offset")
    print("in the span, tested against everything above:")
    print()
    hits = 0
    for width, endian in ((2, "little"), (2, "big"), (4, "little"), (4, "big")):
        for off in range(lo, hi - width + 1):
            v = int.from_bytes(s[off:off + width], endian)
            if v < a.min:
                continue
            what = []
            for k, mv in measured.items():
                if v == mv:
                    what.append(k)
            if v in by_lba:
                what.append("start LBA of " + by_lba[v][0])
            if v in by_last:
                what.append("last LBA of " + by_last[v][0])
            if v in by_size:
                what.append("byte length of " + by_size[v][0])
            if v in by_sect and v > 1000:
                what.append("sector length of " + by_sect[v][0])
            if what:
                print("  +%-5d %d-byte %-6s = %12d   %s"
                      % (off, width, endian, v, "; ".join(what)))
                hits += 1
    if not hits:
        print("  (no reading in this span equals any boundary given)")
    print()
    print("matches: %d" % hits)
    print()

    print("for completeness, every non-zero aligned 4-byte LE dword in the")
    print("span, matched or not -- an unmatched integer is the honest output:")
    print()
    for off in range(lo, hi - 3, 4):
        v = int.from_bytes(s[off:off + 4], "little")
        if not v:
            continue
        what = [k for k, mv in measured.items() if v == mv]
        if v in by_lba:
            what.append("start LBA of " + by_lba[v][0])
        if v in by_size:
            what.append("byte length of " + by_size[v][0])
        print("  +%-5d %12d  0x%08x   %s"
              % (off, v, v, "; ".join(what) if what else "-- no match --"))


if __name__ == "__main__":
    main()
