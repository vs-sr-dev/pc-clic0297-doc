#!/usr/bin/env python3
"""cabdates.py -- the clock inside a cabinet, against the clock outside it.

`pecensus.py` found eleven PE files in `dati/install/win32/it/` whose
filesystem mtime is EARLIER than their own COFF link timestamp, which cannot
happen: a file is not written before it is linked. That is one line of
evidence that the mtimes in that directory are synthetic.

This is the second, independent line, and it does not involve PE at all. A
Microsoft cabinet stores, per contained file, an MS-DOS date and time written
when the cabinet was BUILT. If a cabinet whose own mtime is September 1998
contains files dated 1999, the cabinet's mtime is not when the cabinet was
made.

The MS-DOS date/time encoding, which is where a naive reader goes wrong:

    date: bits 15..9 year - 1980, bits 8..5 month, bits 4..0 day
    time: bits 15..11 hour, bits 10..5 minute, bits 4..0 second / 2

Two-second granularity, local time, no zone recorded -- the same properties as
the FAT mtime it is being compared against, which is what makes the comparison
fair. Both are wall clocks from the machine that did the writing.

It reuses `cab.py`'s reader rather than reimplementing the cabinet format.

    python tools/cabdates.py DIR
    python tools/cabdates.py FILE [FILE ...]
"""
import argparse
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cab as cabmod          # noqa: E402


def collect(path):
    """Return (files, total_uncompressed, min_date, max_date) for one cabinet.

    cab.py's class is `Cab`, its file table is the attribute `files` (a list of
    dicts, not a method), and the decoded timestamp is the key `dt`. Reading
    the raw `date` key instead would compare a packed 16-bit DOS field against
    a datetime, which sorts but means nothing.
    """
    c = cabmod.Cab(path)
    entries = c.files
    dates = [e["dt"] for e in entries if e.get("dt")]
    total = sum(e["size"] for e in entries)
    return entries, total, (min(dates) if dates else None), \
        (max(dates) if dates else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

    files = []
    for p in args.paths:
        if os.path.isdir(p):
            for dp, dn, fn in os.walk(p):
                dn.sort()
                for f in sorted(fn):
                    if f.lower().endswith(".cab"):
                        files.append(os.path.join(dp, f))
        else:
            files.append(p)

    print("%-18s %11s %11s %6s  %-19s %-19s %s"
          % ("cabinet", "on disc", "expanded", "files",
             "mtime (outside)", "newest inside", "verdict"))
    print("-" * 18 + " " + "-" * 11 + " " + "-" * 11 + " " + "-" * 6 + "  "
          + "-" * 19 + " " + "-" * 19 + " " + "-" * 22)

    rows = []
    impossible = 0
    total_disc = total_exp = total_files = 0
    for path in files:
        st = os.stat(path)
        mt = datetime.datetime.fromtimestamp(st.st_mtime)
        try:
            entries, exp, dmin, dmax = collect(path)
        except Exception as exc:
            print("%-18s %11d %11s %6s  %-19s %-19s %s"
                  % (os.path.basename(path), st.st_size, "?", "?",
                     mt.strftime("%Y-%m-%d %H:%M:%S"), "-",
                     "unreadable: %s" % str(exc)[:24]))
            continue
        verdict = ""
        if dmax and dmax > mt:
            verdict = "IMPOSSIBLE (+%d days)" % (dmax - mt).days
            impossible += 1
        rows.append((path, st.st_size, exp, len(entries), mt, dmin, dmax))
        total_disc += st.st_size
        total_exp += exp
        total_files += len(entries)
        print("%-18s %11d %11d %6d  %-19s %-19s %s"
              % (os.path.basename(path), st.st_size, exp, len(entries),
                 mt.strftime("%Y-%m-%d %H:%M:%S"),
                 dmax.strftime("%Y-%m-%d %H:%M:%S") if dmax else "-",
                 verdict))

    print()
    print("cabinets            : %d" % len(rows))
    print("bytes on disc       : %d" % total_disc)
    print("bytes expanded      : %d" % total_exp)
    if total_disc:
        print("expansion ratio     : %.3f x" % (total_exp / float(total_disc)))
    print("files inside        : %d" % total_files)
    print()
    print("cabinets whose newest INTERNAL date is later than their own mtime: %d"
          % impossible)
    print("(each one is a cabinet that was built after the date its directory")
    print(" entry claims it was written, so the directory entry is synthetic)")

    if rows:
        allmax = max(r[6] for r in rows if r[6])
        allmin = min(r[5] for r in rows if r[5])
        print()
        print("internal date range across all cabinets: %s .. %s"
              % (allmin.strftime("%Y-%m-%d"), allmax.strftime("%Y-%m-%d")))
        mts = sorted({r[4].strftime("%Y-%m-%d") for r in rows})
        print("distinct cabinet mtimes (day): %s" % ", ".join(mts))


if __name__ == "__main__":
    main()
