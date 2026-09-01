#!/usr/bin/env python3
"""twoclocks.py -- every file that carries its own date, against its mtime.

This repository has no disc image, so it has no ISO 9660 recording dates, no
volume descriptor, no burn timestamp. The filesystem mtimes that survived the
copy are the only disc-wide clock, and the first question any conclusion drawn
from them depends on is: **are they real?**

The answer is measured, not assumed, by finding files that carry a SECOND
timestamp inside themselves and subtracting:

    PE / COFF        seconds since the Unix epoch, UTC, written by the linker
    QuickTime mvhd   seconds since 1904-01-01, UTC, written by the authoring
                     application when the movie document was created
    MS-CAB           MS-DOS date/time per contained file, local, written when
                     the cabinet was built; this tool uses the newest one

The mtime is a FAT wall clock: local time, no zone, two-second granularity. So
for a file that went straight from its maker onto the master:

    mtime - internal = the maker's UTC offset, plus however long the write took

Italy in September is CEST, UTC+2. A residue near +2:00:00 therefore says both
clocks are telling the truth. Three things falsify that:

  * a NEGATIVE residue. A file cannot be written before it is linked or before
    its own movie header was stamped. Any negative value means one of the two
    timestamps is synthetic;
  * a residue near +2h but with the YEAR off by exactly one. That is the
    interesting case on this disc and it is not noise: month, day, hour, minute
    and second all line up, and only the year is wrong;
  * a residue of many months, which usually just means the file was made by
    somebody else long before it was shipped -- Microsoft's and Macromedia's
    binaries all look like this and it is not a finding, it is a supply chain.

The tool prints the residue, the residue with a one-year correction applied,
and says which of the two is closer to a whole number of hours.

    python tools/twoclocks.py DIR
    python tools/twoclocks.py DIR --offset 7200
    python tools/twoclocks.py DIR --only-skew
"""
import argparse
import datetime
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pe as pemod            # noqa: E402
import cab as cabmod          # noqa: E402
import mov as movmod          # noqa: E402

QT_EPOCH = datetime.datetime(1904, 1, 1)


def internal_pe(path):
    p = pemod.PE(path)
    return datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=p.timestamp)


def internal_mov(path):
    data = open(path, "rb").read()
    for off, size, atype, hdr, depth in movmod.atoms(data, 0, len(data)):
        if atype == b"mvhd":
            body = off + hdr
            if data[body] == 0:
                ct = struct.unpack_from(">I", data, body + 4)[0]
            else:
                ct = struct.unpack_from(">Q", data, body + 4)[0]
            if ct:
                return QT_EPOCH + datetime.timedelta(seconds=ct)
            return None
    return None


def internal_cab(path):
    c = cabmod.Cab(path)
    ds = [e["dt"] for e in c.files if e.get("dt")]
    return max(ds) if ds else None


READERS = [
    ((".exe", ".dll", ".x32", ".ocx"), "PE/COFF", internal_pe),
    ((".mov", ".qt"), "QT mvhd", internal_mov),
    ((".cab",), "CAB inner", internal_cab),
]


def hms(seconds):
    sign = "-" if seconds < 0 else "+"
    s = abs(int(round(seconds)))
    return "%s%d:%02d:%02d" % (sign, s // 3600, (s % 3600) // 60, s % 60)


def near_hour(seconds, tol=900):
    """Distance from the nearest whole hour, in seconds."""
    r = abs(seconds) % 3600
    return min(r, 3600 - r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--offset", type=int, default=7200,
                    help="expected UTC offset in seconds (default 7200 = CEST)")
    ap.add_argument("--only-skew", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

    rows = []
    for dp, dn, fn in os.walk(args.dir):
        dn.sort()
        for f in sorted(fn):
            low = f.lower()
            reader = kind = None
            for exts, name, fn_ in READERS:
                if low.endswith(exts):
                    reader, kind = fn_, name
                    break
            if reader is None:
                continue
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, args.dir).replace(os.sep, "/")
            mt = datetime.datetime.fromtimestamp(os.stat(full).st_mtime)
            try:
                iv = reader(full)
            except Exception:
                iv = None
            if iv is None:
                continue
            delta = (mt - iv).total_seconds()
            # the same subtraction with the mtime's year advanced by one
            try:
                mt1 = mt.replace(year=mt.year + 1)
                delta1 = (mt1 - iv).total_seconds()
            except ValueError:          # 29 February
                delta1 = None
            rows.append((rel, kind, mt, iv, delta, delta1))

    skew = []
    print("%-44s %-9s %-19s %-19s %11s %11s"
          % ("path", "clock", "mtime (local)", "internal", "mtime-int",
             "+1yr"))
    print("-" * 44 + " " + "-" * 9 + " " + "-" * 19 + " " + "-" * 19 + " "
          + "-" * 11 + " " + "-" * 11)
    for rel, kind, mt, iv, delta, delta1 in rows:
        # A one-year skew: the raw residue is about -1 year, and adding a year
        # to the mtime lands it within 20 minutes of the expected UTC offset.
        is_skew = (delta1 is not None
                   and abs(delta1 - args.offset) < 1200
                   and delta < -300 * 86400)
        if is_skew:
            skew.append((rel, kind, mt, iv, delta1))
        if args.only_skew and not is_skew:
            continue
        print("%-44s %-9s %-19s %-19s %11s %11s%s"
              % (rel[-44:], kind, mt.strftime("%Y-%m-%d %H:%M:%S"),
                 iv.strftime("%Y-%m-%d %H:%M:%S"), hms(delta),
                 hms(delta1) if delta1 is not None else "-",
                 "   <-- YEAR SKEW" if is_skew else ""))

    print()
    print("files with two clocks : %d" % len(rows))
    neg = [r for r in rows if r[4] < 0]
    print("negative residues     : %d  (mtime before the file could exist)"
          % len(neg))
    print()
    print("=== files whose mtime is exactly one year early ===")
    print("(month, day and time of day agree with the internal clock once the")
    print(" %+d s UTC offset is applied; only the year differs, by one)"
          % args.offset)
    print()
    if not skew:
        print("    none")
    else:
        print("%-44s %-9s %-19s %-19s %s"
              % ("path", "clock", "mtime (local)", "internal (UTC)",
                 "residue after +1yr"))
        for rel, kind, mt, iv, d1 in skew:
            print("%-44s %-9s %-19s %-19s %s"
                  % (rel[-44:], kind, mt.strftime("%Y-%m-%d %H:%M:%S"),
                     iv.strftime("%Y-%m-%d %H:%M:%S"), hms(d1)))
    print()
    print("year-skewed files     : %d of %d" % (len(skew), len(rows)))

    # The control: files where the two clocks AGREE on the year, which is what
    # proves the mtimes are otherwise trustworthy rather than uniformly wrong.
    agree = [r for r in rows
             if r[4] >= 0 and abs(r[4] - args.offset) < 1800]
    print()
    print("=== control: files where the two clocks agree to within 30 min ===")
    print("(residue within 30 minutes of %+d s, i.e. CEST plus write time)"
          % args.offset)
    print()
    for rel, kind, mt, iv, delta, _ in agree:
        print("%-44s %-9s %-19s %-19s %s"
              % (rel[-44:], kind, mt.strftime("%Y-%m-%d %H:%M:%S"),
                 iv.strftime("%Y-%m-%d %H:%M:%S"), hms(delta)))
    print()
    print("agreeing files        : %d of %d" % (len(agree), len(rows)))


if __name__ == "__main__":
    main()
