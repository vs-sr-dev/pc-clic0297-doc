#!/usr/bin/env python3
"""window2.py -- measure the drive's read quantum by timing instead of by failure.

`window.py` and `edgerun.py` derive the read window from where reads FAIL: the
lowest cold-seek LBA that errors is (first bad sector) - (window - 1). That
method needs a bad sector. This disc has none, so the method does not apply and
the question -- is the 64-sector window of pc-harrypotter1-doc a property of the
drive or of the CD medium? -- would go unanswered.

It can be answered another way. Ask the drive for one sector at a time, walking
forward, and time each request. If the drive prefetches N sectors per physical
access, one request in N is slow (it goes to the disc) and the other N-1 are
fast (they come out of the drive's buffer). The period of the slow ones is the
quantum.

The requests go out over SPTI, so the Windows cache is not in the path at all;
what is being measured is the drive.

    python tools/window2.py E --start 300000 --count 512
    python tools/window2.py E --start 300000 --count 512 --stride 1
    python tools/window2.py E --seek     # cold-seek timing, for contrast
"""
import argparse
import statistics
import struct
import sys
import time

sys.path.insert(0, __file__.rsplit(chr(92), 1)[0] if chr(92) in __file__ else ".")
import spti  # noqa: E402


def read10(d, lba, n=1):
    cdb = [0x28, 0] + list(struct.pack(">I", lba)) + [0] + list(struct.pack(">H", n)) + [0]
    t0 = time.perf_counter()
    r = d.cmd(cdb, 2048 * n)
    return (time.perf_counter() - t0) * 1000.0, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive")
    ap.add_argument("--start", type=int, default=300000)
    ap.add_argument("--count", type=int, default=512)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--threshold", type=float, default=0.0,
                    help="ms above which a read counts as slow; 0 = derive it")
    ap.add_argument("--seek", action="store_true")
    a = ap.parse_args()

    d = spti.Drive(a.drive)

    if a.seek:
        print("=== cold seeks: one sector each, 20,000 LBA apart ===")
        for i in range(20):
            lba = 10000 + i * 20000
            ms, r = read10(d, lba)
            print("  LBA %7d  %7.2f ms  status %d" % (lba, ms, r["status"]))
        return

    # settle the drive somewhere far away first, then walk forward
    read10(d, 10, 1)
    read10(d, a.start - 4096, 1)

    print("=== single-sector READ(10), walking forward from LBA %d ===" % a.start)
    print("    %d requests, stride %d, no OS cache in the path" % (a.count, a.stride))
    times = []
    for i in range(a.count):
        lba = a.start + i * a.stride
        ms, r = read10(d, lba)
        if r["status"] != 0:
            print("  LBA %d failed: %s" % (lba, spti.sense_str(r["sense"])))
            break
        times.append((lba, ms))

    vals = [t for _, t in times]
    med = statistics.median(vals)
    thr = a.threshold or (med * 4)
    print()
    print("  requests      : %d" % len(vals))
    print("  median        : %.3f ms" % med)
    print("  mean          : %.3f ms" % statistics.fmean(vals))
    print("  min / max     : %.3f / %.3f ms" % (min(vals), max(vals)))
    print("  slow threshold: %.3f ms  (%s)"
          % (thr, "given" if a.threshold else "4 x median"))

    slow = [(lba, ms) for lba, ms in times if ms >= thr]
    print("  slow requests : %d of %d (%.1f %%)"
          % (len(slow), len(vals), 100.0 * len(slow) / max(len(vals), 1)))
    if not slow:
        print("  no request stood out: the drive is not showing a quantum this way.")
        return

    print()
    print("  slow LBAs and the gap since the previous slow one:")
    prev = None
    gaps = []
    for lba, ms in slow:
        g = "" if prev is None else "+%d" % (lba - prev)
        if prev is not None:
            gaps.append(lba - prev)
        print("    LBA %7d  %8.2f ms  %s   mod16=%2d mod32=%2d mod64=%2d"
              % (lba, ms, g, lba % 16, lba % 32, lba % 64))
        prev = lba

    if gaps:
        import collections
        c = collections.Counter(gaps)
        print()
        print("  gaps between slow requests: %s"
              % sorted(c.items(), key=lambda kv: -kv[1]))
        q = c.most_common(1)[0][0]
        print("  most common gap = %d sectors = %d bytes" % (q, q * 2048))
        for m in (16, 32, 64, 128):
            al = sum(1 for lba, _ in slow if lba % m == 0)
            print("    slow LBAs that are multiples of %3d: %d of %d" % (m, al, len(slow)))


if __name__ == "__main__":
    main()
