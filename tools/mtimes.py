#!/usr/bin/env python3
"""mtimes.py -- the only clock this copy still has.

Every previous disc in this collection arrived as an image. This one arrived as
a copied file tree, so `iso9660.py`, `timeline.py --iso` and `dates.py` have
nothing to read: there are no volume descriptors, no directory records, no
seven-byte recording dates, no offset-in-quarter-hours byte. What survived the
copy is the filesystem mtime of each of the 142 files, and that is it.

That is a smaller instrument than an ISO, but it is not a useless one, for a
reason worth stating precisely:

  FAT (and the DOS/Windows tooling that mastered CDs in the nineties) stores a
  file's modification time as a **literal wall clock with no time zone**. Two
  seconds of granularity, no offset field, no UTC. What is written down is
  whatever the writing machine's local clock said. It is therefore not an
  instant -- it is a reading, and the machine that took the reading is part of
  the measurement.

That property is what makes the subtraction against a PE's COFF timestamp
interesting. COFF *is* an instant: seconds since the Unix epoch, UTC, no zone
ambiguity, written by the linker. So for any file that went from a linker
straight onto the master with nothing in between:

    mtime (local wall clock, unknown zone) - COFF (UTC)  ==  that machine's
                                                            UTC offset

and the residue tells you which clock the file was made under. A residue of
+2:00:00 is Italian summer time. A residue of -7:00:00 is US Pacific daylight
time. A residue that is not a whole number of hours (or half hours) means the
file did not go straight from linker to master, and the gap is production time.

What this tool prints:

  --list      every file with size and mtime, sorted by mtime
  --distinct  the distinct mtimes, and the distinct calendar days, with counts
  --waves     mtimes clustered into production waves by a gap threshold
  --dirs      per-directory mtime span, which is how you see a directory that
              was assembled at one moment versus one that accreted

Times are printed exactly as stored. This tool never converts anything, because
converting requires knowing a zone and the whole point is that the zone is not
recorded. The subtraction against COFF lives in `coffdiff.py`, not here.

    python tools/mtimes.py DIR --list
    python tools/mtimes.py DIR --distinct
    python tools/mtimes.py DIR --waves --gap 3600
    python tools/mtimes.py DIR --dirs
"""
import argparse
import datetime
import os
import sys
from collections import Counter, defaultdict


def walk(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            try:
                st = os.stat(full)
            except OSError as exc:
                print("stat failed: %s: %s" % (full, exc), file=sys.stderr)
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            out.append((rel, st.st_size, st.st_mtime))
    return out


def fmt(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def do_list(rows):
    rows = sorted(rows, key=lambda r: (r[2], r[0]))
    print("%-19s %12s  %s" % ("mtime", "bytes", "path"))
    print("-" * 19 + " " + "-" * 12 + "  " + "-" * 40)
    for rel, size, ts in rows:
        print("%-19s %12d  %s" % (fmt(ts), size, rel))
    print()
    print("files: %d" % len(rows))


def do_distinct(rows):
    times = Counter(fmt(ts) for _, _, ts in rows)
    days = Counter(fmt(ts)[:10] for _, _, ts in rows)
    minutes = Counter(fmt(ts)[:16] for _, _, ts in rows)

    print("=== distinct mtimes (second granularity) ===")
    print("%-19s %5s" % ("mtime", "files"))
    for t in sorted(times):
        print("%-19s %5d" % (t, times[t]))
    print()
    print("distinct mtimes  : %d" % len(times))
    print()

    print("=== distinct minutes ===")
    print("%-16s %5s" % ("minute", "files"))
    for t in sorted(minutes):
        print("%-16s %5d" % (t, minutes[t]))
    print()
    print("distinct minutes : %d" % len(minutes))
    print()

    print("=== distinct calendar days ===")
    print("%-10s %5s" % ("day", "files"))
    for d in sorted(days):
        print("%-10s %5d" % (d, days[d]))
    print()
    print("distinct days    : %d" % len(days))
    print("earliest         : %s" % fmt(min(r[2] for r in rows)))
    print("latest           : %s" % fmt(max(r[2] for r in rows)))
    span = max(r[2] for r in rows) - min(r[2] for r in rows)
    print("span             : %.0f seconds = %.2f days" % (span, span / 86400.0))


def do_waves(rows, gap):
    rows = sorted(rows, key=lambda r: r[2])
    waves = []
    cur = [rows[0]]
    for r in rows[1:]:
        if r[2] - cur[-1][2] > gap:
            waves.append(cur)
            cur = [r]
        else:
            cur.append(r)
    waves.append(cur)

    print("=== production waves (gap threshold %d s = %.1f h) ===" % (gap, gap / 3600.0))
    print()
    total_bytes = sum(r[1] for r in rows)
    for i, w in enumerate(waves, 1):
        b = sum(r[1] for r in w)
        print("wave %-2d  %s .. %s  %3d files  %12d bytes  %6.2f%%"
              % (i, fmt(w[0][2]), fmt(w[-1][2]), len(w), b,
                 100.0 * b / total_bytes if total_bytes else 0.0))
    print()
    for i, w in enumerate(waves, 1):
        print("--- wave %d (%d files) ---" % (i, len(w)))
        for rel, size, ts in w:
            print("    %-19s %12d  %s" % (fmt(ts), size, rel))
        print()


def do_dirs(rows):
    per = defaultdict(list)
    for rel, size, ts in rows:
        d = rel.rsplit("/", 1)[0] if "/" in rel else "(root)"
        per[d].append((rel, size, ts))
    print("%-50s %5s %19s %19s %10s" % ("directory", "files", "earliest", "latest", "span(s)"))
    print("-" * 50 + " " + "-" * 5 + " " + "-" * 19 + " " + "-" * 19 + " " + "-" * 10)
    for d in sorted(per):
        ts = [r[2] for r in per[d]]
        print("%-50s %5d %19s %19s %10.0f"
              % (d, len(per[d]), fmt(min(ts)), fmt(max(ts)), max(ts) - min(ts)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--distinct", action="store_true")
    ap.add_argument("--waves", action="store_true")
    ap.add_argument("--dirs", action="store_true")
    ap.add_argument("--gap", type=int, default=3600)
    args = ap.parse_args()

    rows = walk(args.dir)
    if not rows:
        print("no files under %s" % args.dir)
        return
    if args.list:
        do_list(rows)
    elif args.distinct:
        do_distinct(rows)
    elif args.waves:
        do_waves(rows, args.gap)
    elif args.dirs:
        do_dirs(rows)
    else:
        do_distinct(rows)


if __name__ == "__main__":
    main()
