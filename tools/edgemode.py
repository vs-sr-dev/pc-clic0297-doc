#!/usr/bin/env python3
"""edgemode.py -- does the border of the unreadable region depend on how you ask?

edges.py binary-searched with isolated seeks and found the first unreadable
sector at 755, confirmed three times. The inherited iso9660.py, walking the
unallocated run forwards, died at sector 818 instead. Both read one 2048-byte
sector at a time. The difference is the access pattern: one seeks cold to a
sector far from the last, the other arrives sequentially.

818 is also one of the four integers in the sector-16 payload that nothing had
explained (docs/03-two-primaries.md, offset +1275), which makes the question
worth an experiment rather than a shrug.

Three passes, all single-sector reads, all with no retries:

  SEQ    read 700, 701, 702, ... until one fails
  SEEK   read only the candidate, after a seek to sector 0 to break any
         read-ahead the drive may be doing
  ALT    alternate: sector 0, then the candidate, then 0, then the next

    python tools/edgemode.py E
"""
import sys
import time

BS = chr(92)
SECTOR = 2048


def opendev(letter):
    return open(BS + BS + "." + BS + letter.upper() + ":", "rb")


def rd(f, lba):
    t0 = time.perf_counter()
    try:
        f.seek(lba * SECTOR)
        b = f.read(SECTOR)
        return (len(b) == SECTOR), time.perf_counter() - t0, ""
    except OSError as e:
        return False, time.perf_counter() - t0, "errno %s" % e.errno


def main():
    letter = sys.argv[1] if len(sys.argv) > 1 else "E"
    lo = int(sys.argv[2]) if len(sys.argv) > 2 else 700
    hi = int(sys.argv[3]) if len(sys.argv) > 3 else 830

    print("SEQUENTIAL: read %d upward, one sector at a time, same handle" % lo)
    print()
    f = opendev(letter)
    firstfail = None
    okc = 0
    t0 = time.perf_counter()
    for lba in range(lo, hi + 1):
        ok, dt, msg = rd(f, lba)
        if ok:
            okc += 1
            continue
        firstfail = lba
        print("  first failure at LBA %d after %d consecutive successes"
              " (%.3f s, %s)" % (lba, okc, dt, msg))
        break
    if firstfail is None:
        print("  no failure between %d and %d" % (lo, hi))
    print("  sequential pass wall clock: %.2f s" % (time.perf_counter() - t0))
    f.close()
    print()

    print("ISOLATED SEEK: for each candidate, seek to sector 0 first")
    print()
    cands = [754, 755, 756, 760, 800, 810, 815, 816, 817, 818, 819, 820]
    f = opendev(letter)
    res = {}
    for lba in cands:
        rd(f, 0)
        ok, dt, msg = rd(f, lba)
        res[lba] = ok
        print("  lba %6d  %-6s %7.3f s  %s"
              % (lba, "OK" if ok else "FAIL", dt, msg))
    f.close()
    print()

    print("FRESH HANDLE: one new handle per candidate, nothing read before it")
    print()
    for lba in cands:
        g = opendev(letter)
        ok, dt, msg = rd(g, lba)
        g.close()
        print("  lba %6d  %-6s %7.3f s  %s"
              % (lba, "OK" if ok else "FAIL", dt, msg))
    print()

    print("=" * 66)
    print("sequential first failure : %s" % firstfail)
    print("isolated-seek boundary   : first FAIL among %s = %s"
          % (cands, next((c for c in cands if not res[c]), None)))
    print("=" * 66)
    print()
    print("818 appears at offset +1275 of the primary volume descriptor at")
    print("sector 16 (docs/03-two-primaries.md). Whether that is the same 818")
    print("is what this run is for.")


if __name__ == "__main__":
    main()
