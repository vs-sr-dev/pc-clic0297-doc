#!/usr/bin/env python3
"""sweep.py -- read every sector of the disc once and report what fails.

Nine probes are a sample, not a proof. This reads the whole device from LBA 0
forward in large blocks, and on any failure falls back to sector-by-sector
inside the failing block so the exact first and last bad LBA are named rather
than bracketed.

    python tools/sweep.py E
    python tools/sweep.py E --block 512 --sha1

Prints elapsed time, bytes read, the SHA-1 of everything it read (with --sha1),
and every unreadable sector as a run. A disc with no unreadable region prints
one line saying so, and that line costs a full pass to earn.
"""
import argparse
import hashlib
import sys
import time

SECTOR = 2048
BS = chr(92)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive")
    ap.add_argument("--block", type=int, default=1024, help="sectors per read")
    ap.add_argument("--sha1", action="store_true")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--stop", type=int, default=0, help="0 = until short read")
    a = ap.parse_args()

    dev = BS + BS + "." + BS + a.drive.rstrip(":") + ":"
    fh = open(dev, "rb", buffering=0)

    h = hashlib.sha1() if a.sha1 else None
    bad = []
    lba = a.start
    ok_bytes = 0
    t0 = time.time()
    last_report = t0
    stopped = None

    while True:
        if a.stop and lba >= a.stop:
            stopped = "reached --stop"
            break
        n = a.block
        if a.stop:
            n = min(n, a.stop - lba)
        try:
            fh.seek(lba * SECTOR)
            d = fh.read(n * SECTOR)
        except OSError as e:
            d = b""
        if len(d) == n * SECTOR:
            if h:
                h.update(d)
            ok_bytes += len(d)
            lba += n
        else:
            # fall back to one sector at a time across this block
            full = 0
            for i in range(n):
                try:
                    fh.seek((lba + i) * SECTOR)
                    s = fh.read(SECTOR)
                except OSError:
                    s = b""
                if len(s) == SECTOR:
                    if h:
                        h.update(s)
                    ok_bytes += SECTOR
                    full += 1
                else:
                    bad.append(lba + i)
            lba += n
            if full == 0 and len(bad) >= 64 and all(
                    bad[-1] - k == len(bad) - 1 - j for j, k in enumerate(bad[-64:], 0)):
                pass
            if full == 0:
                # an entire block failed; if we are near the declared end, stop
                stopped = "whole block at LBA %d failed" % (lba - n)
                break
        now = time.time()
        if now - last_report > 20:
            sys.stderr.write("  ... LBA %d, %.1f MB, %.0f s\n"
                             % (lba, ok_bytes / 1e6, now - t0))
            sys.stderr.flush()
            last_report = now

    el = time.time() - t0
    print("start LBA        : %d" % a.start)
    print("stopped because  : %s" % stopped)
    print("last LBA reached : %d" % (lba - 1))
    print("sectors read OK  : %d" % (ok_bytes // SECTOR))
    print("bytes read OK    : %d" % ok_bytes)
    print("elapsed          : %.1f s  (%.2f MB/s)" % (el, ok_bytes / 1e6 / max(el, 1e-9)))
    if h:
        print("sha1 of all bytes read: %s" % h.hexdigest())

    print()
    if not bad:
        print("unreadable sectors: none in the range swept.")
    else:
        runs = []
        s = p = bad[0]
        for x in bad[1:]:
            if x == p + 1:
                p = x
            else:
                runs.append((s, p))
                s = p = x
        runs.append((s, p))
        print("unreadable sectors: %d, in %d run(s)" % (len(bad), len(runs)))
        for s, e in runs:
            print("  LBA %d..%d  (%d sectors)" % (s, e, e - s + 1))


if __name__ == "__main__":
    main()
