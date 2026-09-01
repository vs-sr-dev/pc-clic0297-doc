#!/usr/bin/env python3
"""vdmatch.py -- test every integer in the sector-16 payload against every
number the disc's layout and the drive's behaviour produced.

The payload in the reserved area of one of the two primary descriptors holds
small integers. This asks, for each of them, whether it equals a file's start
LBA, a file's last LBA, a file's length in bytes, a file's length in sectors,
a boundary of the unallocated hole, or a boundary of the physically unreadable
region. Anything that matches nothing is reported as unmatched, because an
unmatched number is the honest output.

Input is notes/extents-iso.txt, produced by isodev.py --extents, so this tool
does not touch the drive except for sector 16 itself.

    python tools/vdmatch.py E notes/extents-iso.txt
"""
import re
import sys

BS = chr(92)
SECTOR = 2048

# measured elsewhere in this repository, each with the tool that produced it
MEASURED = {
    "gap start (isodev.py --extents)": 107,
    "gap end (isodev.py --extents)": 10106,
    "gap length (isodev.py --extents)": 10000,
    "last readable before hole (edges.py)": 754,
    "first unreadable (edges.py)": 755,
    "last unreadable (edges.py)": 10097,
    "first readable after hole (edges.py)": 10098,
    "unreadable length (edges.py)": 9343,
    "volume size (toc.py / vds.py)": 292173,
    "lead-out LBA (toc.py)": 292323,
    "lead-out minus volume (toc.py)": 150,
}


def rd16(letter):
    with open(BS + BS + "." + BS + letter.upper() + ":", "rb") as f:
        f.seek(16 * SECTOR)
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


def payload_ints(s16, s17=None):
    lo, hi = 1139, 1535
    out = []
    for width, endian in ((2, "little"), (4, "little"), (4, "big")):
        for off in range(lo, hi - width + 2):
            v = int.from_bytes(s16[off:off + width], endian)
            out.append((off, width, endian, v))
    return out


def main():
    letter = sys.argv[1] if len(sys.argv) > 1 else "E"
    expath = sys.argv[2] if len(sys.argv) > 2 else "notes/extents-iso.txt"
    s16 = rd16(letter)
    rows = load_extents(expath)
    print("extent map: %d entries loaded from %s" % (len(rows), expath))

    by_lba = {}
    by_last = {}
    by_size = {}
    by_sect = {}
    for lba, nsec, size, name in rows:
        by_lba.setdefault(lba, []).append(name)
        by_last.setdefault(lba + nsec - 1, []).append(name)
        by_size.setdefault(size, []).append(name)
        by_sect.setdefault(nsec, []).append(name)

    # the candidate integers, taken at the 4-byte-LE grid that produced
    # plausible values, plus the 2-byte-LE reading of the short runs
    grid = []
    off = 1267
    while off + 4 <= 1316:
        grid.append((off, int.from_bytes(s16[off:off + 4], "little")))
        off += 4
    print()
    print("the aligned dword run at offsets 1267..1314 (stride 4):")
    print()
    print("  %-7s %12s   %s" % ("offset", "value", "what it equals"))
    for off, v in grid:
        hits = []
        for k, mv in MEASURED.items():
            if v == mv:
                hits.append(k)
        if v in by_lba:
            hits.append("start LBA of " + ", ".join(by_lba[v]))
        if v in by_last:
            hits.append("last LBA of " + ", ".join(by_last[v]))
        if v in by_size:
            hits.append("byte length of " + ", ".join(by_size[v]))
        if v in by_sect and v > 3:
            hits.append("sector length of " + ", ".join(by_sect[v][:3]))
        print("  +%-6d %12d   %s" % (off, v, "; ".join(hits) if hits
                                     else ("(zero)" if v == 0
                                           else "-- no match --")))
    print()

    print("exhaustive sweep: every 2- and 4-byte reading of the payload span,")
    print("at every byte offset, tested against the measured boundaries:")
    print()
    seen = set()
    for off, width, endian, v in payload_ints(s16):
        for k, mv in MEASURED.items():
            if v == mv and v > 100:
                key = (off, width, endian, v)
                if key in seen:
                    continue
                seen.add(key)
                print("  +%-6d %d-byte %-6s = %8d   %s"
                      % (off, width, endian, v, k))
    if not seen:
        print("  (none)")
    print()

    print("and against file boundaries (values > 1000 only, to cut noise):")
    hits = 0
    for off, width, endian, v in payload_ints(s16):
        if v < 1000:
            continue
        w = []
        if v in by_lba:
            w.append("start LBA of " + by_lba[v][0])
        if v in by_last:
            w.append("last LBA of " + by_last[v][0])
        if w and width == 4 and endian == "little":
            print("  +%-6d %d-byte %-6s = %8d   %s"
                  % (off, width, endian, v, "; ".join(w)))
            hits += 1
    if not hits:
        print("  (none)")


if __name__ == "__main__":
    main()
