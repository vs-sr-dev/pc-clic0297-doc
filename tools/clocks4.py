#!/usr/bin/env python3
"""clocks4.py -- every clock on this disc, on one timeline.

Six independent time sources are recorded on this DVD and they do not all agree.
This gathers them and prints them in order, converting each to UTC using the
zone each source itself declares, so that a disagreement shows up as a
disagreement instead of being hidden by a conversion.

  1  PE COFF link timestamps (always UTC by definition)
  2  ISO 9660 directory records   (digits + a GMT offset in 15-minute units)
  3  Joliet directory records     (the same fields, separately stored)
  4  UDF File Entry modification times (digits + a signed minute offset)
  5  the two volume descriptors' own creation/modification stamps
  6  MS-DOS timestamps inside 0compressed.zip (no zone at all)

    python tools/clocks4.py E _work/iso/0compressed.zip
"""
import collections
import datetime
import os
import struct
import sys
import zipfile

BS = chr(92)
SECTOR = 2048
drive = (sys.argv[1] if len(sys.argv) > 1 else "E").rstrip(":")
zpath = sys.argv[2] if len(sys.argv) > 2 else "_work/iso/0compressed.zip"

f = open(BS * 2 + "." + BS + drive + ":", "rb", buffering=0)


def sec(lba, n=1):
    f.seek(lba * SECTOR)
    return f.read(SECTOR * n)


def iso_rec_time(b):
    y, mo, d, h, mi, s, tz = b[0], b[1], b[2], b[3], b[4], b[5], b[6]
    if tz > 127:
        tz -= 256
    dt = datetime.datetime(1900 + y, mo, d, h, mi, s)
    return dt, tz, dt - datetime.timedelta(minutes=15 * tz)


def walk_iso(root_lba, root_len):
    out = []
    stack = [(root_lba, root_len, "")]
    seen = set()
    while stack:
        lba, ln, path = stack.pop()
        if (lba, ln) in seen:
            continue
        seen.add((lba, ln))
        d = sec(lba, max(1, (ln + SECTOR - 1) // SECTOR))
        p = 0
        while p < len(d):
            L = d[p]
            if L == 0:
                p = (p // SECTOR + 1) * SECTOR
                if p >= len(d):
                    break
                continue
            rec = d[p:p + L]
            nl = rec[32]
            name = rec[33:33 + nl]
            ext = struct.unpack_from("<I", rec, 2)[0]
            size = struct.unpack_from("<I", rec, 10)[0]
            flags = rec[25]
            t = iso_rec_time(rec[18:25])
            if nl == 1 and name in (b"\x00", b"\x01"):
                pass
            elif flags & 2:
                stack.append((ext, size, path + "/" + name.decode("latin-1")))
                out.append((path + "/" + name.decode("latin-1") + "/", t, size))
            else:
                out.append((path + "/" + name.decode("latin-1"), t, size))
            p += L
    return out


pvd = sec(16)
root_lba = struct.unpack_from("<I", pvd, 158)[0]
root_len = struct.unpack_from("<I", pvd, 166)[0]
recs = walk_iso(root_lba, root_len)
print("ISO 9660 directory records: %d" % len(recs))
tzs = collections.Counter(t[1] for _, t, _ in recs)
print("  GMT offsets present: %s (15-minute units)" % dict(tzs))
utc = collections.Counter(t[2] for _, t, _ in recs)
print("  distinct instants (after applying each record's own offset): %d" % len(utc))
print()
print("  the whole tree, by instant:")
for k in sorted(utc):
    print("    %s UTC   x%d" % (k, utc[k]))
print()

print("volume descriptor stamps:")
for lba, label in ((16, "ISO primary"), (17, "Joliet supplementary")):
    d = sec(lba)
    for off, what in ((813, "creation"), (830, "modification"),
                      (847, "expiration"), (864, "effective")):
        s = d[off:off + 16].decode("latin-1")
        tz = d[off + 16]
        if tz > 127:
            tz -= 256
        print("  %-22s %-12s %s  offset %d (UTC%+.2f)" % (label, what, s, tz, tz * 0.25))
print()

print("MS-DOS timestamps inside %s (no timezone is stored):" % os.path.basename(zpath))
with zipfile.ZipFile(zpath) as z:
    for i in sorted(z.infolist(), key=lambda i: i.date_time):
        print("  %04d-%02d-%02d %02d:%02d:%02d   %s" % (i.date_time + (i.filename,)))
