#!/usr/bin/env python3
"""xfermax.py -- how many sectors will this drive hand over in one read?

Three sessions have carried an open question about the granularity of reading
an optical disc through Windows. pc-harrypotter1-doc measured the granularity
of *failure* on a damaged CD (64 sectors: one bad sector poisons its whole
64-sector neighbourhood). pc-harrypotter5-doc measured the granularity of
*access* on a DVD by timing (about 272 sectors, starting on multiples of 16).

Neither measured the third thing, which turns out to matter more than both:
**the largest transfer the device will accept at all.** A read larger than
that limit does not return a short buffer -- it fails outright, and a tool
that treats a failed read as evidence about the *disc* will report a healthy
disc as unreadable, or spend an hour re-reading a healthy region one sector at
a time.

This measures it on a region known to be readable, so that a failure can only
be the transfer size and never the medium:

    python tools/xfermax.py E
    python tools/xfermax.py E --at 100 --max 4096

It reports, for each power-of-two group size and for each size around the
first failure, whether the read succeeded and how long it took. The output is
a property of the *pair* (drive, driver), not of the disc, and it is recorded
here because every other measurement in this repository is taken through it.
"""
import argparse
import time

SECTOR = 2048
BS = chr(92)


def devpath(letter):
    return BS + BS + "." + BS + letter.upper().rstrip(":") + ":"


def attempt(fh, lba, n):
    t = time.time()
    try:
        fh.seek(lba * SECTOR)
        d = fh.read(n * SECTOR)
    except OSError as e:
        return None, time.time() - t, e.__class__.__name__
    return len(d), time.time() - t, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive")
    ap.add_argument("--at", type=int, default=0,
                    help="LBA to read from; must be in a readable region")
    ap.add_argument("--max", type=int, default=4096)
    a = ap.parse_args()

    fh = open(devpath(a.drive), "rb", buffering=0)
    print("device : %s:   starting LBA : %d" % (a.drive.upper().rstrip(":"), a.at))
    print()
    print("%8s %10s %12s %10s  %s" % ("sectors", "bytes", "returned", "seconds", "note"))
    good = 0
    n = 1
    while n <= a.max:
        got, dt, err = attempt(fh, a.at, n)
        note = err if err else ("full" if got == n * SECTOR else "SHORT")
        print("%8d %10d %12s %10.3f  %s"
              % (n, n * SECTOR, "fail" if got is None else got, dt, note))
        if got == n * SECTOR:
            good = n
        else:
            break
        n *= 2
    if good and n <= a.max:
        lo, hi = good, min(n, a.max)
        print()
        print("bisecting between %d (works) and %d (does not):" % (lo, hi))
        while hi - lo > 1:
            mid = (lo + hi) // 2
            got, dt, err = attempt(fh, a.at, mid)
            ok = (got == mid * SECTOR)
            print("%8d %10d %12s %10.3f  %s"
                  % (mid, mid * SECTOR, "fail" if got is None else got, dt,
                     err or ("full" if ok else "SHORT")))
            if ok:
                lo = mid
            else:
                hi = mid
        good = lo
    print()
    print("largest accepted read : %d sectors = %d bytes" % (good, good * SECTOR))
    if good:
        print("that is %d KiB" % (good * SECTOR // 1024))


if __name__ == "__main__":
    main()
