#!/usr/bin/env python3
"""window.py -- the read window, and where the bad sectors really start.

edges.py found the first unreadable sector at 755 by binary search with cold
seeks, three times over. edgerun.py then found that a sequential read walks
straight past 755 and stops somewhere else, and that where it stops depends on
where it started -- eight starts, eight different stopping points between 756
and 818.

Both cannot be "the border". This tests a model that makes both true.

THE MODEL

  The drive services a read of sector N by fetching sectors N .. N+W-1 in one
  operation. If ANY sector in that range is unreadable the whole operation
  fails and the caller is told that sector N failed.

  Under this model a cold read of N fails exactly when the interval
  [N, N+W-1] contains a bad sector, and a sequential run started at S fails at
  the first block boundary S + kW whose block reaches one.

Two unknowns: the window W, and the first bad sector B. Both are solved from
the observations rather than assumed, by trying every (W, B) pair and keeping
the ones that reproduce every measurement.

    python tools/window.py
    python tools/window.py E --check      re-measure the predictions it makes
"""
import sys
import time

BS = chr(92)
SECTOR = 2048

# (start, number of successful sequential reads, LBA that failed)
# from notes/edgerun.txt, every run this session made
RUNS = [
    (107, 704, 811),
    (300, 512, 812),
    (500, 256, 756),
    (600, 192, 792),
    (690, 128, 818),
    (700, 64, 764),
    (700, 64, 764),
    (740, 64, 804),
    (750, 64, 814),
    (750, 64, 814),
    (754, 64, 818),
    (754, 64, 818),
    (754, 64, 818),
    (754, 64, 818),
    (754, 64, 818),
]

# cold single-sector reads, from notes/edges-binsearch.txt, edges-confirm.txt
# and edgemode.txt: (lba, did it read)
COLD = [
    (0, True), (512, True), (640, True), (704, True), (736, True),
    (752, True), (754, True), (755, False), (756, False), (760, False),
    (768, False), (800, False), (810, False), (815, False), (816, False),
    (817, False), (818, False), (819, False), (820, False), (1024, False),
    (2048, False), (9216, False), (9728, False), (9984, False),
    (10048, False), (10080, False), (10096, False), (10097, False),
    (10098, True), (10100, True), (10104, True), (10112, True),
    (10240, True),
]


def predict_run(start, W, B, end):
    """First failing sector of a sequential run under the model."""
    b = start
    while b <= end:
        if b + W - 1 >= B and b <= B:
            return b
        if b >= B:
            return b
        b += W
    return None


def predict_cold(lba, W, B, E):
    """True if a cold read of `lba` succeeds under the model."""
    return not (lba + W - 1 >= B and lba <= E)


def main():
    args = sys.argv[1:]
    print("solving for the read window W and the first bad sector B")
    print()
    # the last bad sector is pinned by the cold reads: 10097 fails, 10098 ok,
    # and the window extends forwards, so the far edge is exact.
    E = 10097
    good = []
    for W in range(1, 257):
        for B in range(700, 900):
            ok = True
            for start, n, fail in RUNS:
                if predict_run(start, W, B, 900) != fail:
                    ok = False
                    break
            if not ok:
                continue
            for lba, res in COLD:
                if predict_cold(lba, W, B, E) != res:
                    ok = False
                    break
            if ok:
                good.append((W, B))
    print("  (W, B) pairs reproducing all %d sequential runs and all %d cold"
          " reads: %d" % (len(RUNS), len(COLD), len(good)))
    for W, B in good:
        print("     window %d sectors (%d KiB), first bad sector %d"
              % (W, W * SECTOR // 1024, B))
    if not good:
        print("  none -- the model is wrong")
        return
    W, B = good[0]
    print()
    print("=" * 68)
    print("every sequential run, predicted against measured")
    print("=" * 68)
    print("  %8s %8s %10s %10s  %s"
          % ("start", "run-up", "measured", "predicted", ""))
    for start, n, fail in RUNS:
        p = predict_run(start, W, B, 900)
        print("  %8d %8d %10d %10d  %s"
              % (start, n, fail, p, "ok" if p == fail else "*** MISMATCH ***"))
    print()
    print("=" * 68)
    print("what this means")
    print("=" * 68)
    print("  read window                    : %d sectors = %d KiB"
          % (W, W * SECTOR // 1024))
    print("  first physically bad sector    : %d" % B)
    print("  last physically bad sector     : %d" % E)
    print("  bad region                     : %d sectors = %d bytes"
          % (E - B + 1, (E - B + 1) * SECTOR))
    print()
    print("  the cold-seek boundary was     : 755")
    print("  B - (W - 1)                    : %d - %d = %d" % (B, W - 1, B - W + 1))
    print("  => the 755 measured by binary search is not where the bad")
    print("     sectors start. It is the lowest sector whose %d-sector read"
          % W)
    print("     window reaches sector %d." % B)
    print()
    print("  the far edge is exact, because the window extends FORWARDS:")
    print("     a cold read of %d fails (its window starts on a bad sector)"
          % E)
    print("     a cold read of %d succeeds (its window is entirely clean)"
          % (E + 1))
    print()
    print("  apparent region 755..%d  = %d sectors" % (E, E - 755 + 1))
    print("  actual   region %d..%d  = %d sectors" % (B, E, E - B + 1))
    print("  difference               = %d = W - 1" % (B - 755))

    if "--check" in args:
        letter = args[0] if args and not args[0].startswith("--") else "E"
        print()
        print("=" * 68)
        print("checking two predictions the model makes and nothing else does")
        print("=" * 68)
        path = BS + BS + "." + BS + letter.upper() + ":"
        tests = [(B - W, "should READ: its window ends at %d" % (B - 1)),
                 (B - W + 1, "should FAIL: its window reaches %d" % B)]
        for lba, why in tests:
            t0 = time.perf_counter()
            try:
                with open(path, "rb") as f:
                    f.seek(lba * SECTOR)
                    b = f.read(SECTOR)
                res = "READ" if len(b) == SECTOR else "SHORT"
            except OSError as e:
                res = "FAIL"
            print("  lba %6d  %-6s %6.2f s   %s"
                  % (lba, res, time.perf_counter() - t0, why))


if __name__ == "__main__":
    main()
