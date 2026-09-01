#!/usr/bin/env python3
"""edges.py -- find the borders of an unreadable region by binary search.

A failed sector read on this drive costs about three and a half seconds. A
linear scan of ten thousand sectors is therefore about ten hours. A binary
search is about twenty reads. This tool does the binary search, counts every
read, times every read, and prints the cost, because on a physical disc the
cost of a measurement is part of the measurement.

It never writes and never retries in a loop. If a sector does not read, that
is the result.

    python tools/edges.py E                      find both borders
    python tools/edges.py E --probe 106 107 10106 10107
    python tools/edges.py E --confirm 106 107 10106 10107 --repeat 3

Definitions used below:
    "readable"   open/seek/read returns exactly 2048 bytes
    "unreadable" the read raises OSError (on Windows this surfaces as
                 errno 13, EACCES, "Permission denied" -- that is how the
                 volume device reports a failed read, not an access-control
                 failure; running elevated does not change it)
"""
import sys
import time

BS = chr(92)
SECTOR = 2048


class Probe:
    def __init__(self, letter):
        self.path = BS + BS + "." + BS + letter.upper() + ":"
        self.reads = 0
        self.ok = 0
        self.bad = 0
        self.t_ok = 0.0
        self.t_bad = 0.0
        self.log = []

    def read(self, lba):
        t0 = time.perf_counter()
        try:
            with open(self.path, "rb") as f:
                f.seek(lba * SECTOR)
                b = f.read(SECTOR)
            dt = time.perf_counter() - t0
            good = (len(b) == SECTOR)
            if good:
                self.ok += 1
                self.t_ok += dt
            else:
                self.bad += 1
                self.t_bad += dt
            self.reads += 1
            self.log.append((lba, good, dt, "short read %d" % len(b)
                             if not good else ""))
            return (b if good else None), dt, ("short read (%d bytes)"
                                               % len(b) if not good else "")
        except OSError as e:
            dt = time.perf_counter() - t0
            self.reads += 1
            self.bad += 1
            self.t_bad += dt
            msg = "errno %s (%s): %s" % (e.errno, getattr(e, "strerror", "?"),
                                         type(e).__name__)
            self.log.append((lba, False, dt, msg))
            return None, dt, msg

    def readable(self, lba, verbose=True):
        b, dt, msg = self.read(lba)
        if verbose:
            print("  lba %8d  %-10s %6.3f s   %s"
                  % (lba, "OK" if b else "FAIL", dt, msg))
        return b is not None

    def summary(self):
        print()
        print("reads          : %d  (%d ok, %d failed)"
              % (self.reads, self.ok, self.bad))
        print("time in ok     : %8.3f s   mean %8.4f s"
              % (self.t_ok, self.t_ok / self.ok if self.ok else 0))
        print("time in failed : %8.3f s   mean %8.4f s"
              % (self.t_bad, self.t_bad / self.bad if self.bad else 0))
        print("total wall     : %8.3f s" % (self.t_ok + self.t_bad))
        if self.ok and self.bad:
            print("a failed read costs %.0fx a successful one"
                  % ((self.t_bad / self.bad) / (self.t_ok / self.ok)))


def first_bad(p, lo_good, hi_bad):
    """lo_good is known readable, hi_bad known unreadable. Return first bad."""
    print("binary search for the FIRST unreadable sector in (%d, %d]"
          % (lo_good, hi_bad))
    while hi_bad - lo_good > 1:
        mid = (lo_good + hi_bad) // 2
        if p.readable(mid):
            lo_good = mid
        else:
            hi_bad = mid
    print("  => last readable %d, first unreadable %d" % (lo_good, hi_bad))
    return lo_good, hi_bad


def last_bad(p, lo_bad, hi_good):
    """lo_bad known unreadable, hi_good known readable. Return last bad."""
    print("binary search for the LAST unreadable sector in [%d, %d)"
          % (lo_bad, hi_good))
    while hi_good - lo_bad > 1:
        mid = (lo_bad + hi_good) // 2
        if p.readable(mid):
            hi_good = mid
        else:
            lo_bad = mid
    print("  => last unreadable %d, first readable %d" % (lo_bad, hi_good))
    return lo_bad, hi_good


def main():
    args = sys.argv[1:]
    letter = args[0] if args else "E"
    p = Probe(letter)

    if "--probe" in args:
        i = args.index("--probe")
        print("point probes:")
        for s in args[i + 1:]:
            if s.startswith("--"):
                break
            p.readable(int(s))
        p.summary()
        return

    if "--confirm" in args:
        i = args.index("--confirm")
        rep = 1
        if "--repeat" in args:
            rep = int(args[args.index("--repeat") + 1])
        lbas = []
        for s in args[i + 1:]:
            if s.startswith("--"):
                break
            lbas.append(int(s))
        print("confirming %d sectors, %d passes each" % (len(lbas), rep))
        results = {}
        for r in range(rep):
            print("pass %d:" % (r + 1))
            for lba in lbas:
                results.setdefault(lba, []).append(p.readable(lba))
        print()
        print("stability across %d passes:" % rep)
        for lba in lbas:
            v = results[lba]
            print("  lba %8d : %s  %s"
                  % (lba, ["FAIL", "OK"][v[0]],
                     "stable" if len(set(v)) == 1 else "*** UNSTABLE %s ***" % v))
        p.summary()
        return

    t0 = time.perf_counter()
    print("anchors:")
    a_ok = p.readable(0)
    b_bad = not p.readable(2048)
    c_bad = not p.readable(9216)
    d_ok = p.readable(10240)
    if not (a_ok and b_bad and c_bad and d_ok):
        print("anchors did not behave as the sample probe reported; stopping.")
        p.summary()
        return
    print()
    lo1, hi1 = first_bad(p, 0, 2048)
    print()
    lo2, hi2 = last_bad(p, 9216, 10240)
    print()
    print("=" * 62)
    print("unreadable region : LBA %d .. %d" % (hi1, lo2))
    print("length            : %d sectors = %d bytes"
          % (lo2 - hi1 + 1, (lo2 - hi1 + 1) * SECTOR))
    print("last readable before : %d" % lo1)
    print("first readable after : %d" % hi2)
    print("=" * 62)
    p.summary()
    print()
    print("wall clock for the whole search: %.1f s" % (time.perf_counter() - t0))
    print("a linear scan of %d sectors at the observed failure cost would be"
          % (lo2 - hi1 + 1))
    mb = p.t_bad / p.bad if p.bad else 0
    print("  %d x %.3f s = %.0f s = %.1f hours"
          % (lo2 - hi1 + 1, mb, (lo2 - hi1 + 1) * mb,
             (lo2 - hi1 + 1) * mb / 3600.0))


if __name__ == "__main__":
    main()
