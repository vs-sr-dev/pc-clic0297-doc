#!/usr/bin/env python3
"""clockwork.py -- what the 116 mtimes can and cannot support.

The two previous sessions in this collection found their best chapter in the
clocks, and that is exactly why this tool is written to be sceptical. A folder
copied off somebody's hard disk can have its mtimes rewritten by the copy; an
image cannot. There is no second clock in this material -- no linker timestamp,
no COFF header, no volume descriptor, no `mvhd` -- so nothing here can be
subtracted from anything.

What is left is a distribution argument, and this tool prints the evidence for
it rather than asserting it:

  * how many distinct timestamps there are, and how many files share one;
  * the spread of seconds values -- a copy that rewrote times would leave a
    signature there;
  * the hour-of-day and day-of-week histograms;
  * the gaps, i.e. how the 46 days cluster into working sessions;
  * the tail: everything after the last build event.

  usage: clockwork.py <dir>
"""
import os
import sys
import time
from collections import Counter, defaultdict

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = sys.argv[1]
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    rows = []
    for n in sorted(os.listdir(root)):
        p = os.path.join(root, n)
        st = os.stat(p)
        rows.append((int(st.st_mtime), n, st.st_size))
    rows.sort()

    print("=== the shape of the clock ===")
    print("files                 : %d" % len(rows))
    print("distinct mtimes       : %d" % len({r[0] for r in rows}))
    coll = defaultdict(list)
    for t, n, _ in rows:
        coll[t].append(n)
    groups = {t: v for t, v in coll.items() if len(v) > 1}
    print("timestamps shared     : %d groups covering %d files"
          % (len(groups), sum(len(v) for v in groups.values())))
    for t in sorted(groups):
        print("    %s  %s" % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)),
                              ", ".join(sorted(groups[t]))))
    first, last = rows[0][0], rows[-1][0]
    print("first                 : %s  %s"
          % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(first)), rows[0][1]))
    print("last                  : %s  %s"
          % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last)), rows[-1][1]))
    days = {time.strftime("%Y-%m-%d", time.localtime(t)) for t, _, _ in rows}
    print("distinct calendar days: %d" % len(days))
    print("span                  : %.1f days" % ((last - first) / 86400.0))
    print("")

    print("=== seconds values ===")
    print("A FAT timestamp has two-second granularity, so every second value")
    print("must be even. If any is odd, the times did not come from FAT.")
    secs = Counter(time.localtime(t).tm_sec for t, _, _ in rows)
    odd = sum(v for k, v in secs.items() if k % 2)
    print("odd second values     : %d of %d" % (odd, len(rows)))
    print("distinct second values: %d of the 30 even ones" % len({k for k in secs}))
    print("")

    print("=== hour of day ===")
    hrs = Counter(time.localtime(t).tm_hour for t, _, _ in rows)
    for h in range(24):
        if hrs.get(h):
            print("  %02d:00  %-3d %s" % (h, hrs[h], "#" * hrs[h]))
    inwork = sum(v for k, v in hrs.items() if 9 <= k < 20)
    print("  between 09:00 and 20:00: %d of %d (%.1f %%)"
          % (inwork, len(rows), 100.0 * inwork / len(rows)))
    print("  between 00:00 and 06:00: %d"
          % sum(v for k, v in hrs.items() if k < 6))
    print("")

    print("=== day of week ===")
    dows = Counter(time.localtime(t).tm_wday for t, _, _ in rows)
    for i in range(7):
        print("  %s  %-3d %s" % (DOW[i], dows.get(i, 0), "#" * dows.get(i, 0)))
    print("  Saturday or Sunday: %d" % (dows.get(5, 0) + dows.get(6, 0)))
    print("")

    print("=== working sessions (a gap of more than 12 hours starts a new one) ===")
    sess = []
    cur = [rows[0]]
    for r in rows[1:]:
        if r[0] - cur[-1][0] > 12 * 3600:
            sess.append(cur)
            cur = [r]
        else:
            cur.append(r)
    sess.append(cur)
    print("sessions: %d" % len(sess))
    for s in sess:
        a = time.strftime("%Y-%m-%d %H:%M", time.localtime(s[0][0]))
        b = time.strftime("%H:%M", time.localtime(s[-1][0]))
        exts = Counter(os.path.splitext(x[1])[1].upper() or "(none)" for x in s)
        print("  %-16s..%s  %3d files  %s"
              % (a, b, len(s), " ".join("%s:%d" % kv for kv in exts.most_common(6))))
    print("")

    print("=== the tail: everything at or after the build event ===")
    build = None
    for t, n, _ in rows:
        if n.upper() == "MIGLIA.EXE":
            build = t
    for t, n, sz in rows:
        if t >= build:
            print("  %s  %-14s %8d" % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)), n, sz))


if __name__ == "__main__":
    main()
