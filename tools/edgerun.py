#!/usr/bin/env python3
"""edgerun.py -- how far into the unreadable region a sequential read gets.

edgemode.py established that the first unreadable sector is not one number:

    isolated seek, cold      first failure at 755
    sequential from 700      first failure at 764
    iso9660.py, walking the whole unallocated run   died at 818

So the boundary is a function of how much sequential momentum the drive has
when it arrives. This measures that function: start a fresh handle at several
different sectors, read forward one sector at a time, and record where each
run stops.

If the stopping point grows with the length of the run-up, the drive's
read-ahead is the mechanism and none of the three numbers is "the" border.
If every run stops at the same place regardless of where it started, then the
run-up is irrelevant and something else explains the three numbers.

Each run costs one failed read, about 6.6 s. The successful reads are ~4 ms
each once the drive is streaming.

    python tools/edgerun.py E
    python tools/edgerun.py E 107 300 500 700 750
"""
import sys
import time

BS = chr(92)
SECTOR = 2048
CEILING = 900          # never read past this; the region continues to 10097


def opendev(letter):
    return open(BS + BS + "." + BS + letter.upper() + ":", "rb")


def run_from(letter, start):
    f = opendev(letter)
    t0 = time.perf_counter()
    n = 0
    last = None
    try:
        for lba in range(start, CEILING + 1):
            f.seek(lba * SECTOR)
            b = f.read(SECTOR)
            if len(b) != SECTOR:
                f.close()
                return lba, n, time.perf_counter() - t0, "short read"
            n += 1
            last = lba
    except OSError as e:
        f.close()
        return lba, n, time.perf_counter() - t0, "errno %s" % e.errno
    f.close()
    return None, n, time.perf_counter() - t0, "reached the ceiling at %d" % last


def main():
    letter = sys.argv[1] if len(sys.argv) > 1 else "E"
    starts = [int(x) for x in sys.argv[2:]] or [107, 300, 500, 600, 700, 740,
                                                750, 754]
    print("each run: a fresh handle, sequential single-sector reads,")
    print("no retries, stopping at the first failure or at LBA %d" % CEILING)
    print()
    print("  %8s %10s %10s %10s  %s"
          % ("start", "run-up", "first fail", "seconds", "note"))
    rows = []
    for s in starts:
        fail, n, dt, note = run_from(letter, s)
        rows.append((s, n, fail))
        print("  %8d %10d %10s %10.2f  %s"
              % (s, n, fail if fail is not None else "-", dt, note))
    print()
    fails = [(s, f) for s, n, f in rows if f is not None]
    if not fails:
        print("no run failed; the ceiling is too low or the region moved.")
        return
    vals = sorted({f for _, f in fails})
    print("distinct stopping points: %s" % vals)
    print()
    if len(vals) == 1:
        print("Every run stops at the same sector regardless of run-up, so")
        print("read-ahead is NOT the mechanism and the isolated-seek boundary")
        print("of 755 needs a different explanation.")
    else:
        print("The stopping point varies with the run-up:")
        for s, f in fails:
            print("    started at %5d -> stopped at %5d   (ran %d sectors)"
                  % (s, f, f - s))
        print()
        print("So there is no single 'first unreadable sector'. There is a")
        print("region the drive can enter a little way into when it is")
        print("already streaming, and cannot enter at all from a cold seek.")


if __name__ == "__main__":
    main()
