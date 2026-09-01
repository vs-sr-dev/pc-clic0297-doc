#!/usr/bin/env python3
"""timeline.py - collect every datable stamp this disc carries, into one list.

The disc has five independent clocks and they do not all say the same thing,
which is the point:

  PE COFF timestamp      seconds since the Unix epoch, written by the linker,
                         always UTC
  MS-DOS date/time       inside the cabinet's file table, two-second
                         granularity, local time with no zone recorded
  ISO 9660 directory     seven bytes, local time plus a signed offset in
                         quarter-hours
  ISO 9660 volume        seventeen ASCII digits, same offset convention
  archive member mtime   the RAR the dump arrived in, which dates the rip and
                         not the disc

Everything is printed in the disc's own local time (UTC+1, which is what the
volume descriptor's offset byte says) so that the sequence can be read, with
the UTC value beside it where the source is UTC.

Usage:
    python tools/timeline.py --iso IMG --cab FILE --pe FILE [FILE...]
    python tools/timeline.py --iso IMG --cab FILE --pe-dir DIR
"""

import argparse
import datetime
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TZ = datetime.timezone(datetime.timedelta(hours=1))


def pe_timestamp(path):
    with open(path, "rb") as fh:
        d = fh.read(0x400)
    if d[:2] != b"MZ":
        return None
    e = struct.unpack_from("<I", d, 0x3C)[0]
    if d[e:e + 4] != b"PE\x00\x00":
        with open(path, "rb") as fh:
            d = fh.read(max(0x400, e + 24))
        if d[e:e + 4] != b"PE\x00\x00":
            return None
    ts = struct.unpack_from("<I", d, e + 8)[0]
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)


def dos_dt(date, time):
    try:
        return datetime.datetime(
            ((date >> 9) & 0x7F) + 1980, (date >> 5) & 0x0F, date & 0x1F,
            (time >> 11) & 0x1F, (time >> 5) & 0x3F, (time & 0x1F) * 2,
            tzinfo=TZ)
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iso")
    ap.add_argument("--cab")
    ap.add_argument("--pe", nargs="*", default=[])
    ap.add_argument("--pe-dir", nargs="*", default=[])
    ap.add_argument("--rar-listing", help="output of 'UnRAR.exe lt', to date "
                                          "the rip rather than the disc")
    a = ap.parse_args()

    events = []

    for d in a.pe_dir:
        for r, dirs, names in os.walk(d):
            for n in sorted(names):
                p = os.path.join(r, n)
                try:
                    t = pe_timestamp(p)
                except Exception:
                    t = None
                if t:
                    a.pe.append(p)

    for p in a.pe:
        t = pe_timestamp(p)
        if t:
            events.append((t.astimezone(TZ), "PE link", os.path.basename(p),
                           "%s UTC" % t.strftime("%Y-%m-%d %H:%M:%S")))

    if a.cab:
        from cab import Cab
        c = Cab(a.cab)
        stamps = {}
        for f in c.files:
            if f["dt"]:
                k = f["dt"].replace(tzinfo=TZ)
                stamps.setdefault(k, []).append(f["name"])
        for k in sorted(stamps):
            names = stamps[k]
            events.append((k, "cabinet", "%d file%s" % (len(names),
                                                        "" if len(names) == 1
                                                        else "s"),
                           names[0] if len(names) == 1 else
                           "%s, ..." % names[0]))

    if a.iso:
        from iso9660 import open_image, read_vds, pick, tree_of, dec_datetime
        fh, mm = open_image(a.iso)
        vds = read_vds(mm)
        _sec, b = pick(vds, False)
        # dec_datetime returns the date already rendered as text, plus the
        # signed quarter-hour offset and the raw bytes
        txt, tz, raw = dec_datetime(b[813:830])
        if txt:
            k = datetime.datetime.strptime(txt.split(".")[0],
                                           "%Y-%m-%d %H:%M:%S")
            events.append((k.replace(tzinfo=TZ), "ISO volume",
                           "creation date",
                           "GMT%+d quarter-hours, raw %s" % (tz, raw)))
        entries = tree_of(mm, vds, False)
        stamps = {}
        for e in entries:
            # iso9660.py hands back the directory-record date already
            # formatted, plus the raw quarter-hour offset beside it
            stamps.setdefault((e["time"], e["tz"]), []).append(
                e["path"] + e["name"])
        for (txt, tz), paths in sorted(stamps.items()):
            try:
                k = datetime.datetime.strptime(txt, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                continue
            events.append((k.replace(tzinfo=TZ), "ISO records",
                           "%d entr%s" % (len(paths),
                                          "y" if len(paths) == 1 else "ies"),
                           "GMT%+d quarter-hours; %s" % (
                               tz, paths[0] if len(paths) == 1
                               else "%s, ..." % paths[0])))

    if a.rar_listing:
        cur = None
        with open(a.rar_listing, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("Nome:") or line.startswith("Name:"):
                    cur = line.split(":", 1)[1].strip()
                if (line.startswith("Modifica:") or
                        line.startswith("mtime:")) and cur:
                    v = line.split(":", 1)[1].strip().split(",")[0]
                    try:
                        t = datetime.datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        continue
                    events.append((t.replace(tzinfo=TZ), "archive member",
                                   cur, "dates the rip, not the disc"))

    events.sort(key=lambda e: e[0])
    print("%-22s %-15s %-24s %s"
          % ("local time (UTC+1)", "source", "what", "note"))
    print("-" * 100)
    prev = None
    for t, src, what, note in events:
        gap = ""
        if prev is not None:
            d = (t - prev).total_seconds()
            if d:
                gap = "  (+%s)" % (
                    "%.0f s" % d if d < 120 else
                    "%.0f min" % (d / 60) if d < 7200 else
                    "%.1f h" % (d / 3600) if d < 172800 else
                    "%.1f days" % (d / 86400))
        print("%-22s %-15s %-24s %s%s"
              % (t.strftime("%Y-%m-%d %H:%M:%S"), src, what, note, gap))
        prev = t
    print()
    print("%d dated events" % len(events))


if __name__ == "__main__":
    main()
